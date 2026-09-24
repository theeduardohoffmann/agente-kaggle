import main as agent_module

BOARD = 10
SEASON_DAYS = 30
TURNS_PER_DAY = 24


def make_world():
    return {
        "money": 3000,
        "tiles": [[None for _ in range(BOARD)] for _ in range(BOARD)],
        "farmer": [2, 2],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
        "seeds": {},
        "shed": {},
        "inventories": [{}],
    }


def quad_of(x, y):
    if x <= 4 and y <= 4:
        return "NW"
    if x >= 5 and y <= 4:
        return "NE"
    if x <= 4 and y >= 5:
        return "SW"
    return "SE"


def build_obs(world, day, hour, step):
    return {
        "player": 0,
        "step": step,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": world["money"],
                "tiles": world["tiles"],
                "farmer": world["farmer"],
                "hands": world["hands"],
                "unlocked_quadrants": world["unlocked_quadrants"],
                "hires_today": world["hires_today"],
            },
            {
                "money": 3000, "tiles": [[None] * BOARD for _ in range(BOARD)],
                "farmer": [7, 7], "hands": [], "unlocked_quadrants": ["NW"], "hires_today": 0,
            },
        ],
        "private": {
            "shed": world["shed"],
            "seeds": world["seeds"],
            "inventories": world["inventories"],
        },
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
    }


def move(pos, op):
    x, y = pos
    if op == "NORTH":
        y -= 1
    elif op == "SOUTH":
        y += 1
    elif op == "EAST":
        x += 1
    elif op == "WEST":
        x -= 1
    return [max(0, min(BOARD - 1, x)), max(0, min(BOARD - 1, y))]


def apply_unit_op(world, pos, op, day):
    verb = op[0]
    x, y = pos
    cell = world["tiles"][y][x]

    if verb in ("NORTH", "SOUTH", "EAST", "WEST", "PASS"):
        if verb != "PASS":
            new_pos = move(pos, verb)
            pos[0], pos[1] = new_pos
        return

    if verb == "PLANT":
        crop = op[1]
        if world["seeds"].get(crop, 0) > 0 and cell is None:
            world["seeds"][crop] -= 1
            world["tiles"][y][x] = {
                "kind": "PLANT", "crop": crop, "planted_day": day,
                "watered_today": False, "consecutive_unwatered": 1, "yield_units": 1,
            }
        return

    if verb == "WATER":
        if isinstance(cell, dict) and cell.get("kind") == "PLANT":
            cell["watered_today"] = True
            cell["consecutive_unwatered"] = 0
        return

    if verb == "HARVEST":
        if isinstance(cell, dict) and cell.get("kind") == "PLANT" and cell.get("yield_units", 0) > 0:
            crop = cell["crop"]
            inv = world["_carry_ref"]
            inv[crop] = inv.get(crop, 0) + 3
            info = agent_module.CROP_INFO[crop]
            if info["ongoing"]:
                cell["yield_units"] = 0
                cell["watered_today"] = False
            else:
                world["tiles"][y][x] = None
        elif isinstance(cell, dict) and cell.get("animal") and cell.get("yield_units", 0) > 0:
            product = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}[cell["animal"]]
            inv = world["_carry_ref"]
            inv[product] = inv.get(product, 0) + cell["yield_units"]
            cell["yield_units"] = 0
        return

    if verb == "DIG":
        world["tiles"][y][x] = None
        return

    if verb == "BUILD_PASTURE":
        if cell is None:
            world["tiles"][y][x] = {"kind": "PASTURE", "animal": None}
        return

    if verb == "PLACE":
        item = op[1]
        inv = world["_carry_ref"]
        if inv.get(item, 0) > 0 and isinstance(cell, dict) and cell.get("kind") == "PASTURE" and not cell.get("animal"):
            inv[item] -= 1
            cell["animal"] = item
            cell["fed_today"] = False
            cell["cared_today"] = False
            cell["yield_units"] = 0
            cell["fertilizer_available"] = False
        return

    if verb == "PICKUP":
        item, n = op[1], op[2]
        inv = world["_carry_ref"]
        avail = world["shed"].get(item, 0)
        take = min(avail, n)
        world["shed"][item] = avail - take
        inv[item] = inv.get(item, 0) + take
        return

    if verb == "DROP":
        inv = world["_carry_ref"]
        for k, v in list(inv.items()):
            world["shed"][k] = world["shed"].get(k, 0) + v
            inv[k] = 0
        return

    if verb == "FEED":
        if isinstance(cell, dict) and cell.get("animal"):
            inv = world["_carry_ref"]
            if inv.get("WHEAT", 0) > 0:
                inv["WHEAT"] -= 1
                cell["fed_today"] = True
        return

    if verb == "CARE":
        if isinstance(cell, dict) and cell.get("animal"):
            cell["cared_today"] = True
        return

    if verb == "COLLECT_FERTILIZER":
        if isinstance(cell, dict) and cell.get("animal"):
            world["_carry_ref"]["FERTILIZER"] = world["_carry_ref"].get("FERTILIZER", 0) + 1
            cell["fertilizer_available"] = False
        return


def apply_market(world, orders, day):
    for op in orders:
        verb = op[0]
        if verb == "BUY_LAND":
            missing = [q for q in agent_module.LAND_ORDER if q not in world["unlocked_quadrants"]]
            if missing:
                q = missing[0]
                cost = agent_module.LAND_COST[q]
                if world["money"] - cost >= 0:
                    world["money"] -= cost
                    world["unlocked_quadrants"].append(q)
        elif verb == "HIRE":
            cost = agent_module.fib_cost(world["hires_today"])
            world["money"] -= cost
            world["hires_today"] += 1
            new_hand_pos = [2, 2]
            world["hands"].append(new_hand_pos)
            world["inventories"].append({})
        elif verb == "BUY_SEED":
            crop, n = op[1], op[2]
            cost = agent_module.CROP_INFO[crop]["seed"] * n
            world["money"] -= cost
            world["seeds"][crop] = world["seeds"].get(crop, 0) + n
        elif verb == "BUY_PRODUCT":
            item, n = op[1], op[2]
            world["money"] -= 25 * n
            world["shed"][item] = world["shed"].get(item, 0) + n
        elif verb == "BUY_ANIMAL":
            animal, n = op[1], op[2]
            world["money"] -= 400 * n
            world["shed"][animal] = world["shed"].get(animal, 0) + n
        elif verb == "SELL":
            item, n = op[1], op[2]
            have = world["shed"].get(item, 0)
            sold = min(have, n)
            world["shed"][item] = have - sold
            price = agent_module.BASE_PRICE.get(item, 20)
            world["money"] += sold * price


def end_of_day(world, day):
    for row in world["tiles"]:
        for cell in row:
            if isinstance(cell, dict) and cell.get("kind") == "PLANT":
                if not cell.get("watered_today", False):
                    cell["consecutive_unwatered"] = cell.get("consecutive_unwatered", 0) + 1
                    if cell["consecutive_unwatered"] >= 2:
                        cell["kind"] = "WEED"
                else:
                    info = agent_module.CROP_INFO.get(cell.get("crop"), {})
                    age = day - cell.get("planted_day", day)
                    if info.get("ongoing") and age >= info.get("first_yield_day", 99):
                        cell["yield_units"] = cell.get("yield_units", 0) + 1
                cell["watered_today"] = False
            elif isinstance(cell, dict) and cell.get("animal"):
                if not cell.get("fed_today", False):
                    cell["consecutive_unfed"] = cell.get("consecutive_unfed", 0) + 1
                    if cell["consecutive_unfed"] >= 2:
                        cell["animal"] = None
                else:
                    cell["consecutive_unfed"] = 0
                    cell["yield_units"] = cell.get("yield_units", 0) + 1
                    cell["fertilizer_available"] = True
                cell["fed_today"] = False
                cell["cared_today"] = False
    shed_cap = 100
    shed_total = sum(v for k, v in world["shed"].items())
    for inv in world["inventories"]:
        for item, n in list(inv.items()):
            if n <= 0:
                continue
            room = max(0, shed_cap - shed_total)
            take = min(n, room)
            world["shed"][item] = world["shed"].get(item, 0) + take
            shed_total += take
        inv.clear()

    world["hires_today"] = 0
    world["hands"] = []
    world["inventories"] = [world["inventories"][0]]


def run():
    world = make_world()
    step = 0
    money_history = []
    violations = []
    for day in range(SEASON_DAYS):
        for hour in range(TURNS_PER_DAY):
            obs = build_obs(world, day, hour, step)
            action = agent_module.agent(obs)

            assert set(action.keys()) >= {"farmer", "hands", "market"}, action
            assert len(action["hands"]) == len(world["hands"]), (len(action["hands"]), len(world["hands"]))
            assert len(action["market"]) <= 10, action["market"]

            world["_carry_ref"] = world["inventories"][0]
            apply_unit_op(world, world["farmer"], action["farmer"], day)

            for i, h in enumerate(world["hands"]):
                world["_carry_ref"] = world["inventories"][i + 1]
                apply_unit_op(world, h, action["hands"][i], day)

            money_before = world["money"]
            apply_market(world, action["market"], day)
            spent = money_before - world["money"]
            if spent > 0 and world["money"] < 0:
                violations.append((step, "money went negative", world["money"]))
            cows = sum(
                1 for row in world["tiles"] for c in row
                if isinstance(c, dict) and c.get("animal") == "COW"
            ) + world["shed"].get("COW", 0)
            if cows > agent_module.MAX_COWS:
                violations.append((step, "cow cap exceeded", cows))

            step += 1
            money_history.append(world["money"])
        end_of_day(world, day)

    print("Final money:", world["money"])
    print("Unlocked quadrants:", world["unlocked_quadrants"])
    print("Shed:", world["shed"])
    print("Cows placed/owned:", sum(
        1 for row in world["tiles"] for c in row if isinstance(c, dict) and c.get("animal") == "COW"
    ), world["shed"].get("COW", 0))
    print("Min money ever:", min(money_history))
    print("Violations:", violations if violations else "none")


if __name__ == "__main__":
    run()
