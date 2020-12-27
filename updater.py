import datetime
import json
import subprocess
import sys
import traceback
from pathlib import Path

import dateutil.parser
import termcolor
from hammock import Hammock as hammock

import builder
from add import add_built


def matched_key_in_dict_array(array, key, value):
    if not array:
        return False
    for dictionary in array:
        if dictionary.get(key, None) == value:
            return True
    return False


MAX_OUTSTANDING_COMMITS = 3
DATE_DELTA = 7

theJSON = json.load(Path("plugins.json").open())
plugins = theJSON.get("Plugins", [])
config = json.load(Path("Config/config.json").open())
config_dir = Path("Config").resolve()

info = []
to_build = []
to_add = []

if Path("Config/last_updated.txt").is_file() and Path("Config/last_updated.txt").stat().st_size != 0:
    date_to_compare = dateutil.parser.parse(Path("Config/last_updated.txt").read_text())
    Path("Config/last_updated.txt").write_text(datetime.datetime.now(tz=datetime.timezone.utc).isoformat())
else:
    Path("Config/last_updated.txt").touch()
    # date_to_compare = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    date_to_compare = datetime.datetime(2020, 1, 16, tzinfo=datetime.timezone.utc)
    Path("last_updated.txt").write_text(date_to_compare.isoformat())

print("Last update date is " + date_to_compare.isoformat())

with open("gh token.txt") as f:
    token = f.read().strip()

for plugin in plugins:
    organization, repo = plugin["URL"].strip().replace("https://github.com/", "").split("/")
    base_url = hammock("https://api.github.com")

    releases_url = base_url.repos(organization, repo).releases.GET(auth=("github-actions", token), params={"per_page": 100})
    releases = json.loads(releases_url.text or releases_url.content)
    if releases_url.headers.get("Link"):
        print(releases_url.headers["Link"])

    commits_url = base_url.repos(organization, repo).commits.GET(auth=("github-actions", token), params={"per_page": 100})
    commits = json.loads(commits_url.text or commits_url.content)
    if releases_url.headers.get("Link"):
        print(releases_url.headers["Link"])

    for commit in commits:
        commit_date = dateutil.parser.parse(commit["commit"]["committer"]["date"])
        newer = commit_date >= date_to_compare - datetime.timedelta(days=DATE_DELTA)
        if isinstance(plugin.get("Force", None), str):
            force_build = commit["sha"] == plugin.get("Force")
        else:
            force_build = plugin.get("Force") and commits.index(commit) == 0
        not_in_repo = True
        for i in config.get(plugin["Name"], {}).get("versions", []):
            if i["commit"]["sha"] == commit["sha"]:
                not_in_repo = False
        within_max_outstanding = commits.index(commit) <= MAX_OUTSTANDING_COMMITS
        if (newer and not_in_repo or force_build or (not_in_repo and commits.index(commit) == 0)) and within_max_outstanding:
            if commits.index(commit) == 0:
                print(plugin["Name"] + " by " + organization + " latest commit (" + commit_date.isoformat() + ") not built")
            else:
                print(plugin["Name"] + " by " + organization + " commit " + commit["sha"] + " (" + commit_date.isoformat() + ") not built")
            to_build.append({"plugin": plugin, "commit": commit})

    for release in releases:
        release_date = dateutil.parser.parse(release["created_at"])
        if release_date >= date_to_compare:
            if releases.index(release) == 0:
                print(plugin["Name"] + " by " + organization + " latest release (" + release_date.isoformat() + ") not added")
            else:
                print(plugin["Name"] + " by " + organization + " release " + release["name"] + " (" + release_date.isoformat() + ") not added")
            to_add.append({"plugin": plugin, "release": release})


# for i in to_add: addRelease(i)


# Start setting up builder here.
builder = builder.Builder()

failed = []
succeeded = []
errored = []

termcolor.cprint("\nBuilding " + str(len(to_build)) + " things", attrs=["bold"])

for plugin in to_build:
    print("\nBuilding " + termcolor.colored(plugin["plugin"]["Name"], attrs=["bold"]))
    try:
        started = datetime.datetime.now()
        result = None
        result = builder.build(plugin["plugin"], commithash=plugin["commit"]["sha"])
    except Exception as error:
        duration = datetime.datetime.now() - started
        print("An error occurred!")
        print(error)
        traceback.print_tb(error.__traceback__)
        if result:
            print("Result was: " + str(result))
        termcolor.cprint("Building of " + termcolor.colored(plugin["plugin"]["Name"], "red", attrs=["bold"]) + termcolor.colored(" errored", "red"), "red")
        errored.append(plugin)
        print("Took " + str(duration))
        continue
    if result:
        duration = datetime.datetime.now() - started
        termcolor.cprint("Building of " + termcolor.colored(plugin["plugin"]["Name"], "green", attrs=["bold"]) + termcolor.colored(" succeeded", "green"), "green")
        eee = plugin
        eee["result"] = result
        print("Took " + str(duration))
        print("Adding to config...")
        add_built(eee, token)
        succeeded.append(eee)
    else:
        duration = datetime.datetime.now() - started
        if result:
            print("Result was: " + str(result))
        termcolor.cprint("Building of " + termcolor.colored(plugin["plugin"]["Name"], "red", attrs=["bold"]) + termcolor.colored(" failed", "red"), "red")
        failed.append(plugin)
        print("Took " + str(duration))
termcolor.cprint("\n" + str(len(succeeded)) + " of " + str(len(to_build)) + " built successfully\n", attrs=["bold"])
if len(succeeded) > 0:
    termcolor.cprint("Succeeded:", "green")
    for i in succeeded:
        print(i["plugin"]["Name"])
if len(failed) > 0:
    termcolor.cprint("\nFailed:", "red")
    for i in failed:
        print(i["plugin"]["Name"])
if len(errored) > 0:
    termcolor.cprint("\nErrored:", "red")
    for i in errored:
        print(i["plugin"]["Name"])

if len(failed) > 0 or len(errored) > 0:
    sys.exit(10)

result = subprocess.run(["git", "commit", "-am", "Deploying to builds"], capture_output=True, cwd=config_dir)
if result.returncode != 0:
    print("Failed to commit")
    print(result.stdout.decode())
    print(result.stderr.decode())
    sys.exit()
result = subprocess.run("git push".split(), capture_output=True, cwd=config_dir)
if result.returncode != 0:
    print("Failed to push!")
    print(result.stdout.decode())
    print(result.stderr.decode())
    sys.exit(10)
