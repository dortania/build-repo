import os
import sys
import time

import requests

token = sys.argv[1].strip()

session = requests.Session()
session.auth = ("github-actions", token)

this_run_url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
workflow_url = session.get(this_run_url).json()["workflow_url"]

runs = session.get(f"{workflow_url}/runs").json()
run_index = 0

for i, run in enumerate(runs["workflow_runs"]):
    if str(run["id"]) == str(os.environ["GITHUB_RUN_ID"]):
        run_index = i
        break

for i, run in enumerate(runs["workflow_runs"]):
    if i > run_index and str(run["id"]) != str(os.environ["GITHUB_RUN_ID"]) and run["status"] != "completed":
        print(f"Another build ({run['id']} with status {run['status']}) is running, cancelling this one...")
        cancel_request = session.post(f"{this_run_url}/cancel")
        if cancel_request.status_code != 202:
            sys.exit(f"Status code did not match: {cancel_request.status_code}")
        else:
            print("Cancel request acknowledged, sleeping 10 seconds to account for delay...")
            time.sleep(10)
            sys.exit(0)
