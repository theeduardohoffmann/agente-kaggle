SEASON_DAYS = 30
RESERVE = 1000  # rule 1: never spend below this bank balance
MAX_COWS = 13   # rule 3: never own more than this many cows
DROP_THRESHOLD = 8
FEED_BUFFER_PER_COW = 3

CROP_INFO = {
    "WHEAT":      {"seed": 10,  "first_yield_day": 2,  "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False, "base_price": 25},
    "CARROT":     {"seed": 20,  "first_yield_day": 2,  "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False, "base_price": 35},
    "TOMATO":     {"seed": 50,  "first_yield_day": 8,  "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True,  "base_price": 60},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True,  "base_price": 120},
    "MELON":      {"seed": 80,  "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False, "base_price": 250},
}

CROP_PRIORITY = ["MELON", "CARROT", "WHEAT", "STRAWBERRY", "TOMATO"]
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
ANIMAL_DAY_CUTOFF = 20
LAND_DAY_CUTOFF = 26
HIRE_DAY_CUTOFF = 28
LIQUIDATE_DAY = 27  # rule 4: from this day on, sell everything regardless of price
TILES_PER_WORKER = 4
ANIMAL_RESERVE_PER_QUADRANT = 3

STATE = {
    "jobs": {},
    "assigned_tiles": set(),
    "tile_queue": [],
    "known_unlocked": 0,
    "animal_tiles": [],
    "rancher_id": None,
    "want_animals": False,
    "crop_counts": {},
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
    info = CROP_INFO[crop]
    if info["ongoing"]:
        return info["first_yield_day"] + (info["max_yield"] - 1) * max(info["interval"], 1) + 1
    return info["max_yield_day"] + 1


def can_finish(crop, day):
    # rule 4: only plant if there's time left to harvest and sell before day 30
    return day + cycle_length(crop) <= SEASON_DAYS - 1


def pick_crop(day, seeds, money):
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
        reserve, rest = new_tiles[:ANIMAL_RESERVE_PER_QUADRANT], new_tiles[ANIMAL_RESERVE_PER_QUADRANT:]
        STATE["animal_tiles"].extend(reserve)
        STATE["tile_queue"].extend(rest)
        STATE["tile_queue"].sort(key=dist_to_shed)


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _pop_tile_cluster(size):
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
    remaining = list(tiles_batch)
    ordered = [remaining.pop(0)]
    while remaining:
        nxt = min(remaining, key=lambda t: _manhattan(t, ordered[-1]))
        remaining.remove(nxt)
        ordered.append(nxt)
    return ordered


def _tile_action(cell, job, day, seeds):
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
    committed = 0

    def slots_left():
        return MAX_MARKET_SLOTS - len(market_orders)

    def affordable(cost):
        # rule 1: this bank balance floor gates every purchase below
        return money - committed - cost >= RESERVE

    if hour < 4 and day <= HIRE_DAY_CUTOFF:
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

    empty_count = sum(1 for (x, y) in unlocked_tiles if tiles[y][x] is None)
    missing_quads = [q for q in LAND_ORDER if q not in unlocked]
    # rule 2: only buy the next quadrant once every unlocked tile is occupied
    if empty_count == 0 and missing_quads and day <= LAND_DAY_CUTOFF and slots_left() > 0:
        next_q = missing_quads[0]
        cost = LAND_COST[next_q]
        if affordable(cost):
            market_orders.append(["BUY_LAND"])
            committed += cost

    cows_placed = count_placed_animals(tiles, unlocked_tiles, "COW")
    cows_in_shed = shed.get("COW", 0)
    total_cows = cows_placed + cows_in_shed

    if not STATE["want_animals"] and day > ANIMAL_DAY_CUTOFF and STATE["animal_tiles"]:
        released = [t for t in STATE["animal_tiles"] if tiles[t[1]][t[0]] is None]
        for t in released:
            STATE["animal_tiles"].remove(t)
            STATE["tile_queue"].append(t)
        if released:
            STATE["tile_queue"].sort(key=dist_to_shed)

    if (not STATE["want_animals"] and day <= ANIMAL_DAY_CUTOFF
            and money - RESERVE >= 3000 and len(hands) >= 3):
        STATE["want_animals"] = True

    if STATE["want_animals"] and STATE["rancher_id"] is None and len(hands) >= 3:
        STATE["rancher_id"] = "hand0"

    # rule 3: never buy a cow that would push the herd past MAX_COWS
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

    if cows_placed > 0:
        wheat_target = cows_placed * FEED_BUFFER_PER_COW
        wheat_short = wheat_target - shed.get("WHEAT", 0)
        if wheat_short > 0 and slots_left() > 0:
            unit_price = obs.get("market", {}).get("prices", {}).get("WHEAT", BASE_PRICE["WHEAT"])
            unit_cost_est = max(unit_price, BASE_PRICE["WHEAT"]) * 2
            affordable_qty = max(0, (money - committed - RESERVE) // unit_cost_est)
            qty = min(wheat_short, affordable_qty)
            if qty > 0:
                market_orders.append(["BUY_PRODUCT", "WHEAT", qty])
                committed += qty * unit_cost_est

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
        pre_tile = job["tiles"][job["idx"] % len(job["tiles"])] if job is not None else None

        op = crop_worker_op(uid, pos, tiles, seeds, day)
        if job is not None and job.get("crop") is None:
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
    try:
        return _run(obs)
    except Exception:
        n_hands = 0
        try:
            n_hands = len(obs["farms"][obs["player"]]["hands"])
        except Exception:
            pass
        return {"farmer": ["PASS"], "hands": [["PASS"]] * n_hands, "market": []}
