import json
import os
import sys

import cryptography.fernet as fernet
import requests
from hammock import Hammock as hammock


class Notifier:
    def __init__(self, webhook, token, key) -> None:
        self.webhook = webhook
        self.token = token
        self.fern = fernet.Fernet(key.strip().encode())
        self.job_link = None

    def get_current_run_link(self):
        if self.job_link:
            return self.job_link
        this_run = hammock(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}/jobs", auth=("github-actions", self.token)).GET()
        try:
            this_run.raise_for_status()
        except requests.HTTPError as err:
            print(err)
            return
        this_job = [i for i in this_run.json()["jobs"] if i["name"] == os.environ["JOB_NAME"]][0]
        self.job_link = this_job["html_url"]
        return self.job_link

    def notify(self, results, status):
        results = dict(results)
        results["status"] = status
        results["job_url"] = self.get_current_run_link
        if results.get("files"):
            results["files"] = {k: str(v) for k, v in results["files"].items()}

        requests.post(webhook, data=fern.encrypt(json.dumps(results).encode()))

    def notify_success(self, results):
        self.notify(results, "succeeded")

    def notify_failure(self, results):
        self.notify(results, "failed")

    def notify_error(self, results):
        self.notify(results, "errored")

