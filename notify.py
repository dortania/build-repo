import json
import os
import sys

import cryptography.fernet as fernet
import requests
from hammock import Hammock as hammock

JOB_LINK = None

webhook = sys.argv[2].strip()
fern = fernet.Fernet(sys.argv[3].strip().encode())


def get_current_run_link(token):
    global JOB_LINK
    if JOB_LINK:
        return JOB_LINK
    this_run = hammock(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}/jobs", auth=("github-actions", token)).GET()
    try:
        this_run.raise_for_status()
    except requests.HTTPError as err:
        print(err)
        return
    this_job = [i for i in this_run.json()["jobs"] if i["name"] == os.environ['JOB_NAME']][0]
    JOB_LINK = this_job["html_url"]
    return JOB_LINK


def notify(token, results, status):
    results = dict(results)
    results["status"] = status
    results["job_url"] = get_current_run_link(token)
    results["files"] = {k: str(v) for k, v in results["files"].items()}

    requests.post(webhook, data=fern.encrypt(json.dumps(results).encode()))


def notify_success(token, results):
    notify(token, results, "succeeded")


def notify_failure(token, results):
    notify(token, results, "failed")


def notify_error(token, results):
    notify(token, results, "errored")
