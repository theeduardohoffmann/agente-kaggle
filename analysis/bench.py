import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(ROOT, "src", "main.py")

from kaggle_environments import make

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
results = []
for trial in range(n):
    env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=False)
    env.run([MAIN_PY, "random"])
    me = env.steps[-1][0].observation["farms"][0]
    results.append(me["money"])
    print("trial", trial, "money=", me["money"])

print("---")
print("results:", results)
print("avg:", sum(results) / len(results))
print("min:", min(results), "max:", max(results))
