import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kaggle_environments import make
import main as agent_module

env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=False)
env.reset(num_agents=2)

min_money = float("inf")
max_cows = 0
land_bought_before_full = False

for i in range(720):
    obs0 = env.state[0].observation
    me = obs0["farms"][0]
    tiles = me["tiles"]
    unlocked = me["unlocked_quadrants"]

    def unlocked_tiles():
        out = []
        for q in unlocked:
            xmin, xmax, ymin, ymax = agent_module.QUADRANT_BOUNDS[q]
            out.extend((x, y) for y in range(ymin, ymax + 1) for x in range(xmin, xmax + 1))
        return out

    action = agent_module.agent(obs0)
    before_money = me["money"]
    before_unlocked = list(unlocked)
    if ["BUY_LAND"] in action["market"]:
        empty = sum(1 for (x, y) in unlocked_tiles() if tiles[y][x] is None)
        if empty > 0:
            land_bought_before_full = True
            print(f"VIOLATION: BUY_LAND with {empty} empty tiles at step {i}")

    env.step([action, {"farmer": ["PASS"], "hands": [], "market": []}])
    obs_after = env.state[0].observation
    money_after = obs_after["farms"][0]["money"]
    min_money = min(min_money, money_after)

    cows = sum(1 for row in obs_after["farms"][0]["tiles"] for c in row
               if isinstance(c, dict) and c.get("animal") == "COW")
    shed_cows = obs_after["private"]["shed"].get("COW", 0)
    max_cows = max(max_cows, cows + shed_cows)

    if env.done:
        break

print("min money ever:", min_money, "(rule: must stay >= 1000)")
print("max cows ever (placed + in shed):", max_cows, "(rule: must stay <= 13)")
print("land bought while tiles still empty:", land_bought_before_full)
print("final money:", env.state[0].observation["farms"][0]["money"])
