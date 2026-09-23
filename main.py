"""
Kaggriculture agent.

Business rules (the user's own):
  1. Never let the bank balance drop below RESERVE (1000) after any purchase.
  2. Only buy the next quadrant of land once every currently unlocked,
     farmable tile is occupied (planted / weeded / built on) -- i.e. the
     farm is "full".
  3. Never own more than MAX_COWS (13) cows.
  4. Respect season timing: don't start a crop / animal cycle that cannot be
     harvested AND sold before day 29 (the last day), and liquidate all
     inventory in the final days so nothing is left unsold (unsold stock does
     not count toward the final score -- only bank cash does).

Numbers below (seed cost, first/max yield day, production interval, max
yield, base price) and every mechanic (atomic PLANT validation, daily
farmer/hand respawn at the shed, price curves, ...) are taken directly from
the official engine source
(kaggle_environments/envs/kaggriculture/kaggriculture.py), not from
third-party docs, after those docs led to two costly wrong assumptions:

  - Every unit (farmer AND hands) respawns at the shed tile every single day
    -- nobody's position persists overnight. Tiles far from the shed cost a
    full one-way walk every morning before any work happens, so workers are
    assigned to tiles closest to the shed first.
  - THE BIG ONE: if the total number of PLANT requests for a crop in a single
    turn exceeds the seed count for that crop, the engine drops *all* of
    them, not just the overflow. Naively letting N idle workers each decide
    "I have a seed, I'll plant" independently means N-vs-2-seeds days where
    literally nobody ever plants anything, forever, since every worker keeps
    re-attempting a PLANT that always gets vetoed. See `_throttle_plant_race`.

Board convention (confirmed against the engine source): tiles are indexed
tiles[y][x], farmer/hand positions are [x, y], NORTH decreases y, SOUTH
increases y, EAST increases x, WEST decreases x.

Tuning history worth knowing before changing numbers here: a real opponent's
replay (Kaggle episode 112626139) showed a far more aggressive strategy --
land/animals/premium crops from day 0, cash tolerated near zero for a
stretch, exploding from $5.8k (day 17) to $100k+ (day 29). We tried matching
that literally (RESERVE down to 100-400, land bought as soon as tiles were
merely *assigned* rather than literally empty, hiring/seed purchases/animals
gated much more loosely, FAST_CASH_MIN_DAY lowered) and it measured WORSE
every time against analysis/bench.py, not better -- this agent's worker/tile
mechanics aren't efficient enough yet to survive that level of risk the way
the opponent's apparently are, and some of those changes also violated the
user's own RESERVE rule for no real benefit. Reverted to the validated
1000-RESERVE, conservative values everywhere. One real, unrelated bug fix
from that experiment was kept regardless of RESERVE's value: see
_tile_action's docstring on always advancing to the next tile in a batch.
"""

SEASON_DAYS = 30
RESERVE = 1000
MAX_COWS = 13
DROP_THRESHOLD = 8          # carried items before a crop-worker heads to the shed
FEED_BUFFER_PER_COW = 3     # wheat units kept back in the shed per cow, not sold

# seed / first_yield_day / max_yield_day / interval / max_yield / ongoing / base_price
CROP_INFO = {
    "WHEAT":      {"seed": 10,  "first_yield_day": 2,  "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False, "base_price": 25},
    "CARROT":     {"seed": 20,  "first_yield_day": 2,  "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False, "base_price": 35},
    "TOMATO":     {"seed": 50,  "first_yield_day": 8,  "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True,  "base_price": 60},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True,  "base_price": 120},
    "MELON":      {"seed": 80,  "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False, "base_price": 250},
}

# Ranked by realized $/tile-day (full cycle revenue at base price / cycle
# length): MELON ~125/day, CARROT ~47/day, WHEAT ~37/day, STRAWBERRY ~30/day,
# TOMATO ~22/day (its 8-day unproductive ramp before first_yield_day hurts
# it badly). Actual market prices move with supply, so this is a starting
# order, not gospel -- but it beats guessing.
CROP_PRIORITY = ["MELON", "CARROT", "WHEAT", "STRAWBERRY", "TOMATO"]

# A brand-new farm has no cash flow yet, so its first workers must not sink a
# batch into a 12-day crop (MELON) before a single sale has happened -- that
# alone was enough to crash the whole economy toward RESERVE in testing.
# Only WHEAT/CARROT (first harvest in a handful of days) are eligible until
# the farm has had a real chance to earn; MELON and the rest open up after
# FAST_CASH_MIN_DAY (WHEAT's first harvest lands around day 4-5).
FAST_CROPS = ["WHEAT", "CARROT"]
FAST_CASH_MIN_DAY = 6

BASE_PRICE = {crop: info["base_price"] for crop, info in CROP_INFO.items()}
BASE_PRICE.update({"EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100})

LAND_ORDER = ["NE", "SW", "SE"]
LAND_COST = {"NE": 1000, "SW": 2000, "SE": 4000}
QUADRANT_BOUNDS = {
    "NW": (0, 4, 0, 4),
    "NE": (5, 9, 0, 4),
    "SW": (0, 4, 5, 9),
    "SE": (5, 9, 5, 9),
}
SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]
PREMIUM_PRODUCTS = {"STRAWBERRY", "MELON", "MILK", "WOOL", "EGG"}
NON_SELLABLE = {"COW", "GOOSE", "SHEEP"}
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]
MAX_MARKET_SLOTS = 10
ANIMAL_DAY_CUTOFF = 20      # don't start a fresh coop/pasture cycle after this day
LAND_DAY_CUTOFF = 26
HIRE_DAY_CUTOFF = 28
LIQUIDATE_DAY = 27          # start dumping everything regardless of price impact
TILES_PER_WORKER = 4        # a single hand can easily water/harvest several
                             # nearby tiles in one day; since hands must be
                             # re-hired from scratch every morning (fibonacci
                             # cost resets daily), one hand per tile means
                             # paying a full day's wage for ~2 useful actions
                             # and 22 idle turns -- a batch per hand cuts
                             # headcount (and hiring cost) roughly this much
                             # for the same coverage
ANIMAL_RESERVE_PER_QUADRANT = 3  # tiles set aside for animals before crop
                                  # jobs can claim every tile in a quadrant --
                                  # see the note in ensure_tile_queue

STATE = {
    "jobs": {},              # unit_id -> {"tiles": [(x,y), ...], "crop": str or None, "idx": int}
    "assigned_tiles": set(),
    "tile_queue": [],
    "known_unlocked": 0,
    "animal_tiles": [],
    "rancher_id": None,
    "want_animals": False,
    "crop_counts": {},       # crop -> number of jobs committed to it (diversification)
}


def fib_cost(n):
    if n < len(FIB):
        return FIB[n]
    return FIB[-1]


def quadrant_tiles(q):
    xmin, xmax, ymin, ymax = QUADRANT_BOUNDS[q]
    return [(x, y) for y in range(ymin, ymax + 1) for x in range(xmin, xmax + 1)]


def all_unlocked_tiles(unlocked_quads):
    tiles = []
    for q in unlocked_quads:
        tiles.extend(quadrant_tiles(q))
    return tiles


def nearest_shed_tile(pos):
    x, y = pos
    return min(SHED_TILES, key=lambda t: abs(t[0] - x) + abs(t[1] - y))


def dist_to_shed(pos):
    t = nearest_shed_tile(pos)
    return abs(t[0] - pos[0]) + abs(t[1] - pos[1])


def step_toward(cur, target):
    x, y = cur
    tx, ty = target
    if x == tx and y == ty:
        return None
    if x != tx:
        return "EAST" if tx > x else "WEST"
    return "SOUTH" if ty > y else "NORTH"


def cycle_length(crop):
    """Days from planting to a sellable harvest, including the final decay-avoidance day."""
    info = CROP_INFO[crop]
    if info["ongoing"]:
        return info["first_yield_day"] + (info["max_yield"] - 1) * max(info["interval"], 1) + 1
    return info["max_yield_day"] + 1


def can_finish(crop, day):
    return day + cycle_length(crop) <= SEASON_DAYS - 1


def pick_crop(day, seeds, money):
    """Below FAST_CASH_MIN_DAY, only WHEAT/CARROT are eligible (see the note
    by FAST_CROPS). After that, prefer whichever affordable crop the fewest
    workers have already committed to -- MELON's ~5x better $/tile-day joins
    in without every worker piling onto it and crashing its own market
    price.

    The affordability check here is plain (`money >= seed cost`), not gated
    on RESERVE: requiring the CHOICE itself to clear RESERVE recreates a
    deadlock at whatever RESERVE is once money converges near it (never
    choosing a crop again). The actual BUY_SEED purchase below is what
    enforces spending limits, with a smaller-batch fallback."""
    pool = FAST_CROPS if day < FAST_CASH_MIN_DAY else CROP_PRIORITY
    candidates = []
    for crop in pool:
        if not can_finish(crop, day):
            continue
        info = CROP_INFO[crop]
        if seeds.get(crop, 0) > 0 or money >= info["seed"]:
            candidates.append(crop)
    if not candidates:
        return None
    return min(candidates, key=lambda c: (STATE["crop_counts"].get(c, 0), CROP_PRIORITY.index(c)))


def count_placed_animals(tiles, unlocked_tiles, animal):
    n = 0
    for (x, y) in unlocked_tiles:
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") and t.get("animal") == animal:
            n += 1
    return n


def ensure_tile_queue(unlocked_tiles):
    if len(unlocked_tiles) != STATE["known_unlocked"]:
        STATE["known_unlocked"] = len(unlocked_tiles)
        new_tiles = [t for t in unlocked_tiles
                     if t not in STATE["assigned_tiles"] and t not in STATE["animal_tiles"]
                     and t not in STATE["tile_queue"]]
        new_tiles.sort(key=dist_to_shed)
        # Crop-worker batches happily eat every available tile (7 workers x
        # 4 tiles already covers all 25 in the NW quadrant), so by the time
        # `want_animals` flips on there is often nothing left in tile_queue
        # and no tile anywhere that isn't already claimed -- the herd never
        # gets a single pasture built. Set a few tiles aside for animals up
        # front, per quadrant, before crop jobs can claim them all.
        reserve, rest = new_tiles[:ANIMAL_RESERVE_PER_QUADRANT], new_tiles[ANIMAL_RESERVE_PER_QUADRANT:]
        STATE["animal_tiles"].extend(reserve)
        STATE["tile_queue"].extend(rest)
        # Everyone respawns at the shed every morning -- hand tiles closest to
        # it get worked first, so assign those before the expensive corners.
        STATE["tile_queue"].sort(key=dist_to_shed)


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _pop_tile_cluster(size):
    """Pop up to `size` mutually-close tiles from tile_queue, not just the
    next `size` entries in shed-distance order. Two tiles can be the same
    distance from the shed while sitting in opposite corners of the
    quadrant -- batching those together means a worker spends most of its
    day walking between them instead of watering, and the tiles it can't
    reach in time turn to weeds. Picking the closest overall tile as a seed
    and then its nearest neighbours keeps a worker's whole batch walkable
    in a handful of turns."""
    q = STATE["tile_queue"]
    if not q:
        return []
    seed = q.pop(0)
    cluster = [seed]
    while len(cluster) < size and q:
        nearest = min(q, key=lambda t: _manhattan(t, seed))
        q.remove(nearest)
        cluster.append(nearest)
    return cluster


def _order_by_proximity(tiles_batch):
    """Greedy nearest-neighbour ordering so the daily walk between batch
    tiles is a short loop instead of a random zig-zag."""
    remaining = list(tiles_batch)
    ordered = [remaining.pop(0)]
    while remaining:
        nxt = min(remaining, key=lambda t: _manhattan(t, ordered[-1]))
        remaining.remove(nxt)
        ordered.append(nxt)
    return ordered


def _tile_action(cell, job, day, seeds):
    """Returns (op, advance) for one tile in a worker's batch. `advance`
    tells the caller whether to move on to the next tile in the batch next
    turn. This is always True: a worker that parks on one empty, seedless
    tile and waits abandons the REST of its batch too, including tiles that
    might be sitting ready to harvest -- verified against the real engine,
    this was silently freezing farms at whatever cash they had when seeds
    ran out, no matter the reserve. The worker cycles back to a blocked tile
    on its next lap and re-registers seed demand then, so a stuck tile still
    gets noticed -- just not every single turn."""
    if cell is None:
        crop = job.get("crop")
        if crop is None or not can_finish(crop, day):
            return ["PASS"], True
        if seeds.get(crop, 0) == 0:
            return ["PASS"], True
        return ["PLANT", crop], True

    if isinstance(cell, dict):
        kind = cell.get("kind")
        if kind == "WEED":
            return ["DIG"], True
        if kind == "PLANT":
            crop = cell.get("crop")
            info = CROP_INFO.get(crop)
            age = day - cell.get("planted_day", day)
            yield_units = cell.get("yield_units", 0)
            harvest_ready = False
            if info is not None:
                if info["ongoing"]:
                    harvest_ready = yield_units > 0
                else:
                    # Wait for the full watering-bonus window (harvesting at
                    # first_yield_day instead of max_yield_day trades most of
                    # the yield away), unless the season is almost over.
                    harvest_ready = yield_units > 0 and (
                        age >= info["max_yield_day"] or day >= LIQUIDATE_DAY - 2
                    )
            if harvest_ready:
                return ["HARVEST"], True
            if not cell.get("watered_today", False):
                return ["WATER"], True
            return ["PASS"], True
    return ["PASS"], True


def crop_worker_op(unit_id, pos, tiles, seeds, day):
    """Returns the desired op. PLANT ops are provisional -- the caller must
    run them through _throttle_plant_race before submitting, since the
    engine silently rejects an entire crop's PLANT requests this turn if
    they outnumber the seed stock."""
    job = STATE["jobs"].get(unit_id)
    if job is None:
        batch = _pop_tile_cluster(TILES_PER_WORKER)
        if not batch:
            return ["PASS"]
        STATE["assigned_tiles"].update(batch)
        job = {"tiles": _order_by_proximity(batch), "crop": None, "idx": 0}
        STATE["jobs"][unit_id] = job

    batch = job["tiles"]
    idx = job["idx"] % len(batch)
    tx, ty = batch[idx]
    if pos != (tx, ty):
        return [step_toward(pos, (tx, ty))]

    cell = tiles[ty][tx]
    op, advance = _tile_action(cell, job, day, seeds)
    if advance:
        job["idx"] = (idx + 1) % len(batch)
    return op


def rancher_op(pos, carry, tiles, day, cows_in_shed=0, shed_wheat=0):
    animal_tiles = STATE["animal_tiles"]

    empty_pasture = next((t for t in animal_tiles
                           if isinstance(tiles[t[1]][t[0]], dict)
                           and tiles[t[1]][t[0]].get("kind") == "PASTURE"
                           and not tiles[t[1]][t[0]].get("animal")), None)

    placed = [t for t in animal_tiles
              if isinstance(tiles[t[1]][t[0]], dict) and tiles[t[1]][t[0]].get("animal") == "COW"]
    unfed = [t for t in placed if not tiles[t[1]][t[0]].get("fed_today", False)]

    # Feeding animals already on the farm always outranks growing the herd --
    # missing two feedings loses the animal for good, which is far worse than
    # a delayed purchase or a pasture built a little later.
    if unfed and (carry.get("WHEAT", 0) > 0 or shed_wheat > 0):
        if carry.get("WHEAT", 0) <= 0:
            shed_t = nearest_shed_tile(pos)
            if pos == shed_t:
                return ["PICKUP", "WHEAT", max(len(unfed), 1)]
            return [step_toward(pos, shed_t)]
        target = unfed[0]
        if pos == target:
            return ["FEED"]
        return [step_toward(pos, target)]

    # Place a carried cow next -- always finish what's in hand before starting
    # a new pasture, otherwise the rancher can spend forever building ahead of
    # itself while purchased cows sit unplaced in the shed.
    if carry.get("COW", 0) > 0 and empty_pasture:
        if pos == empty_pasture:
            return ["PLACE", "COW"]
        return [step_toward(pos, empty_pasture)]

    if not unfed and carry.get("COW", 0) == 0 and empty_pasture and cows_in_shed > 0:
        shed_t = nearest_shed_tile(pos)
        if pos == shed_t:
            return ["PICKUP", "COW", 1]
        return [step_toward(pos, shed_t)]

    if not unfed and empty_pasture is None:
        unbuilt = next((t for t in animal_tiles if tiles[t[1]][t[0]] is None), None)
        if unbuilt is not None:
            if pos == unbuilt:
                return ["BUILD_PASTURE"]
            return [step_toward(pos, unbuilt)]

    for t in placed:
        cell = tiles[t[1]][t[0]]
        if not cell.get("cared_today", False):
            if pos == t:
                return ["CARE"]
            return [step_toward(pos, t)]

    for t in placed:
        cell = tiles[t[1]][t[0]]
        if cell.get("fertilizer_available", False):
            if pos == t:
                return ["COLLECT_FERTILIZER"]
            return [step_toward(pos, t)]

    for t in placed:
        cell = tiles[t[1]][t[0]]
        if cell.get("yield_units", 0) > 0:
            if pos == t:
                return ["HARVEST"]
            return [step_toward(pos, t)]

    carried_products = sum(v for k, v in carry.items() if k not in ("WHEAT", "COW"))
    if carried_products > 0:
        shed_t = nearest_shed_tile(pos)
        if pos == shed_t:
            return ["DROP"]
        return [step_toward(pos, shed_t)]

    return ["PASS"]


def _throttle_plant_race(ops_by_uid, seeds):
    """The engine drops *every* PLANT request for a crop this turn if the
    count of such requests exceeds that crop's seed stock -- not just the
    overflow (see module docstring). Cap each crop's concurrent planters to
    the seed count so at least that many succeed instead of zero, and report
    how many workers actually wanted each crop so the caller can buy enough
    seed to cover everyone next turn."""
    demand = {}
    for uid, op in ops_by_uid.items():
        if op and op[0] == "PLANT":
            demand.setdefault(op[1], []).append(uid)

    for crop, uids in demand.items():
        available = seeds.get(crop, 0)
        if len(uids) > available:
            for uid in uids[available:]:
                ops_by_uid[uid] = ["PASS"]

    return {crop: len(uids) for crop, uids in demand.items()}


def _run(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    day = obs["day"]
    hour = obs["hour"]
    money = me["money"]
    tiles = me["tiles"]
    unlocked = me["unlocked_quadrants"]
    seeds = private["seeds"]
    shed = private["shed"]
    hands = me["hands"]
    inventories = private["inventories"]

    unlocked_tiles = all_unlocked_tiles(unlocked)
    ensure_tile_queue(unlocked_tiles)

    market_orders = []
    committed = 0  # money earmarked by orders already queued this turn

    def slots_left():
        return MAX_MARKET_SLOTS - len(market_orders)

    def affordable(cost):
        return money - committed - cost >= RESERVE

    # --- hire hands first: they're the whole income engine, so labour always
    # gets first claim on the budget, before land/animals/wheat-topping ---
    if hour < 4 and day <= HIRE_DAY_CUTOFF:
        # One hand covers a TILES_PER_WORKER-tile batch, not a single tile,
        # so headcount (and the recurring daily re-hire bill) scales with
        # tiles/4, not tiles/2.
        tiles_needing_workers = max(0, len(unlocked_tiles) - len(STATE["animal_tiles"]))
        desired = min(8, max(1, -(-tiles_needing_workers // TILES_PER_WORKER)))
        if day == 0:
            desired = min(desired, 4)
        elif day <= 2:
            desired = min(desired, 6)
        if STATE["want_animals"]:
            desired += 1
        hires_so_far = me["hires_today"]
        n_hired_this_turn = 0
        while len(hands) + n_hired_this_turn < desired and slots_left() > 0:
            cost = fib_cost(hires_so_far + n_hired_this_turn)
            if not affordable(cost):
                break
            market_orders.append(["HIRE"])
            committed += cost
            n_hired_this_turn += 1

    # --- rule 2: expand land only once the current farm is fully occupied ---
    empty_count = sum(1 for (x, y) in unlocked_tiles if tiles[y][x] is None)
    missing_quads = [q for q in LAND_ORDER if q not in unlocked]
    if empty_count == 0 and missing_quads and day <= LAND_DAY_CUTOFF and slots_left() > 0:
        next_q = missing_quads[0]
        cost = LAND_COST[next_q]
        if affordable(cost):
            market_orders.append(["BUY_LAND"])
            committed += cost

    # --- decide whether to run a rancher / pursue cows (rule 3 + timing) ---
    cows_placed = count_placed_animals(tiles, unlocked_tiles, "COW")
    cows_in_shed = shed.get("COW", 0)
    total_cows = cows_placed + cows_in_shed

    if not STATE["want_animals"] and day > ANIMAL_DAY_CUTOFF and STATE["animal_tiles"]:
        # Never took the herd up -- release the tiles set aside for it
        # (still empty, since nothing was ever built on them) back to crop
        # work instead of leaving them fallow for the rest of the season.
        released = [t for t in STATE["animal_tiles"] if tiles[t[1]][t[0]] is None]
        for t in released:
            STATE["animal_tiles"].remove(t)
            STATE["tile_queue"].append(t)
        if released:
            STATE["tile_queue"].sort(key=dist_to_shed)

    # Require hands to already exist before committing to animals: the main
    # farmer must never become the rancher, since with 0 hands that leaves
    # nobody at all tending crops -- the whole farm goes idle.
    if (not STATE["want_animals"] and day <= ANIMAL_DAY_CUTOFF
            and money - RESERVE >= 3000 and len(hands) >= 3):
        STATE["want_animals"] = True

    if STATE["want_animals"] and STATE["rancher_id"] is None and len(hands) >= 3:
        STATE["rancher_id"] = "hand0"

    if STATE["want_animals"] and total_cows < MAX_COWS and day <= ANIMAL_DAY_CUTOFF:
        needed = total_cows + 1
        while len(STATE["animal_tiles"]) < needed:
            candidate = next((t for t in STATE["tile_queue"] if tiles[t[1]][t[0]] is None), None)
            if candidate is None:
                candidate = next((t for t in unlocked_tiles
                                   if t not in STATE["animal_tiles"] and t not in STATE["assigned_tiles"]
                                   and tiles[t[1]][t[0]] is None), None)
            if candidate is None:
                break
            if candidate in STATE["tile_queue"]:
                STATE["tile_queue"].remove(candidate)
            STATE["animal_tiles"].append(candidate)
        STATE["animal_tiles"].sort(key=dist_to_shed)

        empty_built_pasture = next((t for t in STATE["animal_tiles"]
                                     if isinstance(tiles[t[1]][t[0]], dict)
                                     and tiles[t[1]][t[0]].get("kind") == "PASTURE"
                                     and not tiles[t[1]][t[0]].get("animal")), None)
        if empty_built_pasture and cows_in_shed == 0 and slots_left() > 0 and affordable(400):
            market_orders.append(["BUY_ANIMAL", "COW", 1])
            committed += 400

    # Keep a wheat buffer for feeding regardless of what crops are being grown
    # this turn -- letting animals starve (2 missed feeds = permanent escape)
    # is far costlier than the wheat itself.
    if cows_placed > 0:
        wheat_target = cows_placed * FEED_BUFFER_PER_COW
        wheat_short = wheat_target - shed.get("WHEAT", 0)
        if wheat_short > 0 and slots_left() > 0:
            # BUY_PRODUCT is priced dynamically off current market inventory;
            # pad the estimate generously so the reserve floor always holds.
            unit_price = obs.get("market", {}).get("prices", {}).get("WHEAT", BASE_PRICE["WHEAT"])
            unit_cost_est = max(unit_price, BASE_PRICE["WHEAT"]) * 2
            affordable_qty = max(0, (money - committed - RESERVE) // unit_cost_est)
            qty = min(wheat_short, affordable_qty)
            if qty > 0:
                market_orders.append(["BUY_PRODUCT", "WHEAT", qty])
                committed += qty * unit_cost_est

    # --- crop workers: one per unit that isn't the rancher ---
    unit_ids = ["farmer"] + [f"hand{i}" for i in range(len(hands))]
    positions = {"farmer": tuple(me["farmer"])}
    for i, h in enumerate(hands):
        positions[f"hand{i}"] = tuple(h)

    def unit_idx(uid):
        return 0 if uid == "farmer" else int(uid[4:]) + 1

    ops_by_uid = {}
    seed_needs = {}

    for uid in unit_ids:
        pos = positions[uid]
        if uid == STATE["rancher_id"]:
            carry = inventories[unit_idx(uid)] if unit_idx(uid) < len(inventories) else {}
            ops_by_uid[uid] = rancher_op(pos, carry, tiles, day, cows_in_shed=cows_in_shed,
                                          shed_wheat=shed.get("WHEAT", 0))
            continue

        job = STATE["jobs"].get(uid)
        # Capture the batch tile the worker is standing on BEFORE calling
        # crop_worker_op: that call always advances job["idx"] (see
        # _tile_action's docstring), so reading job["idx"] afterwards points
        # at the NEXT tile, not the one `pos` actually matches -- silently
        # breaking demand registration below (pos would never match, so no
        # crop would ever get bought again after the first batch ran out).
        pre_tile = job["tiles"][job["idx"] % len(job["tiles"])] if job is not None else None

        op = crop_worker_op(uid, pos, tiles, seeds, day)
        if job is not None and job.get("crop") is None:
            # One crop choice covers the whole batch of tiles this worker
            # owns -- pick it as soon as the job exists, independent of
            # which specific tile the worker happens to be standing on.
            chosen = pick_crop(day, seeds, money - committed)
            if chosen:
                job["crop"] = chosen
                STATE["crop_counts"][chosen] = STATE["crop_counts"].get(chosen, 0) + 1
                op = crop_worker_op(uid, pos, tiles, seeds, day)

        carry = inventories[unit_idx(uid)] if unit_idx(uid) < len(inventories) else {}
        carried_total = sum(carry.values())
        if carried_total >= DROP_THRESHOLD:
            shed_t = nearest_shed_tile(pos)
            op = ["DROP"] if pos == shed_t else [step_toward(pos, shed_t)]

        ops_by_uid[uid] = op

        # A job can want a crop it can't afford a seed batch big enough for
        # yet -- crop_worker_op deliberately PASSes instead of emitting PLANT
        # in that case (see its docstring on the atomic seed race), which
        # means the demand has to be read from job state directly here,
        # not inferred from which ops happened to come back as PLANT.
        if job is not None and job.get("crop") is not None and can_finish(job["crop"], day) and pre_tile is not None:
            fx, fy = pre_tile
            if pos == (fx, fy) and tiles[fy][fx] is None:
                seed_needs[job["crop"]] = seed_needs.get(job["crop"], 0) + 1

    plant_demand = _throttle_plant_race(ops_by_uid, seeds)
    for crop, wanted in plant_demand.items():
        have = seeds.get(crop, 0)
        if wanted > have:
            seed_needs[crop] = max(seed_needs.get(crop, 0), wanted)

    farmer_op = ops_by_uid.get("farmer", ["PASS"])
    hands_ops = [ops_by_uid.get(f"hand{i}", ["PASS"]) for i in range(len(hands))]

    # --- buy seeds needed this turn (sized to cover every worker who wants one) ---
    # Respects RESERVE like every other purchase (rule 1) -- we tried
    # exempting seeds from it while chasing a much lower RESERVE (see the
    # module docstring's tuning history), since a seed purchase dipping a
    # cent under an exactly-converged floor was silently freezing the farm
    # forever. That risk is real but small at RESERVE=1000 (a big buffer
    # against $10-100 seed costs) and the exemption isn't worth violating the
    # user's own "never below 1000" rule for marginal upside here.
    for crop, qty in seed_needs.items():
        if slots_left() <= 1:
            break
        seed_cost = CROP_INFO[crop]["seed"]
        cost = seed_cost * qty
        if affordable(cost):
            market_orders.append(["BUY_SEED", crop, qty])
            committed += cost
        else:
            max_qty = max(0, int((money - committed - RESERVE) // seed_cost))
            if max_qty > 0:
                market_orders.append(["BUY_SEED", crop, max_qty])
                committed += max_qty * seed_cost

    # --- sell shed inventory (drip-sell normally, liquidate near season end) ---
    liquidate = day >= LIQUIDATE_DAY
    wheat_reserve = cows_placed * FEED_BUFFER_PER_COW if STATE["want_animals"] else 0
    sell_list = []
    for item, count in shed.items():
        if count <= 0 or item in NON_SELLABLE:
            continue
        available = count
        if item == "WHEAT":
            available = max(0, count - wheat_reserve)
        if available <= 0:
            continue
        if liquidate:
            qty = available
        else:
            cap = 8 if item in PREMIUM_PRODUCTS else 30
            qty = min(available, cap)
        if qty > 0:
            sell_list.append((item, qty))

    sell_list.sort(key=lambda kv: kv[1], reverse=True)
    for item, qty in sell_list:
        if slots_left() <= 0:
            break
        market_orders.append(["SELL", item, qty])

    return {
        "farmer": farmer_op,
        "hands": hands_ops,
        "market": market_orders[:MAX_MARKET_SLOTS],
    }


def agent(obs):
    """Kept as the LAST callable defined in this file on purpose: Kaggle's
    loader (kaggle_environments.agent.get_last_callable) picks the last
    callable object found in the executed module, not one named "agent" --
    an earlier version of this file defined `_run` after the try/except
    wrapper and Kaggle silently ran the *unguarded* function on every real
    submission, meaning this safety net was dead code the whole time."""
    try:
        return _run(obs)
    except Exception:
        n_hands = 0
        try:
            n_hands = len(obs["farms"][obs["player"]]["hands"])
        except Exception:
            pass
        return {"farmer": ["PASS"], "hands": [["PASS"]] * n_hands, "market": []}
