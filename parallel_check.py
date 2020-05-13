import json
import sys
import os
from hammock import Hammock as hammock

with open("gh token.txt") as f:
    token = f.read().strip()


this_run = hammock(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}", auth=("dhinakg", token))
workflow_url = this_run.GET().json()["workflow_url"]

#workflow_output = hammock(workflow_url).GET(auth=("dhinakg", token))
#workflow_id = json.loads(workflow_output.text or workflow_url.content)["id"]

runs = hammock(workflow_url).runs.GET().json()
for run in runs["workflow_runs"]:
    if run["id"] != os.environ["GITHUB_RUN_ID"] and run["status"] != "completed":
        print("Another build is running, cancelling this one...")
        cancel_request = this_run.cancel.POST()
        if cancel_request.status_code != 202:
            sys.exit("Status code did not match: " + cancel_request.status_code)
        else:
            sys.exit(0)