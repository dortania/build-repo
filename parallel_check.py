import json
import os
import sys
import time
from hammock import Hammock as hammock

token = sys.argv[1].strip()


this_run = hammock(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}", auth=("github-actions", token))
workflow_url = this_run.GET().json()["workflow_url"]

#workflow_output = hammock(workflow_url).GET(auth=("github-actions", token))
#workflow_id = json.loads(workflow_output.text or workflow_url.content)["id"]

runs = hammock(workflow_url, auth=("github-actions", token)).runs.GET().json()
run_index = None
for run in runs["workflow_runs"]:
    if str(run["id"]) == str(os.environ["GITHUB_RUN_ID"]):
        run_index = runs["workflow_runs"].index(run)
for run in runs["workflow_runs"]:
    if runs["workflow_runs"].index(run) > run_index and str(run["id"]) != str(os.environ["GITHUB_RUN_ID"]) and run["status"] != "completed":
        print(f"Another build ({run['id']} with status {run['status']}) is running, cancelling this one...")
        cancel_request = this_run.cancel.POST()
        if cancel_request.status_code != 202:
            sys.exit("Status code did not match: " + cancel_request.status_code)
        else:
            print("Cancel request acknowledged, sleeping 10 seconds to account for delay...")
            time.sleep(10)
            sys.exit(0)