from hammock import Hammock as hammock
import json
import sys

with open("gh token.txt") as f:
    token = f.read().strip()
eee = hammock("https://api.github.com/repos/dhinakg/ktextrepo/actions/workflows/1273918/runs").GET(auth=("dhinakg",token))
output = json.loads(eee.text or eee.content)
for z in output["workflow_runs"]:
    if z["status"] != "completed":
        sys.exit("Another build is already running!")
