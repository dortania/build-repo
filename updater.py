import datetime
import json
import os
import sys
import traceback
from pathlib import Path

import dateutil.parser
import git
import humanize
from hammock import Hammock as hammock
from termcolor2 import c as color

import builder
from add import add_built
from notify import notify_error, notify_failure, notify_success


def matched_key_in_dict_array(array, key, value):
    if not array:
        return False
    for dictionary in array:
        if dictionary.get(key, None) == value:
            return True
    return False


MAX_OUTSTANDING_COMMITS = 3
DATE_DELTA = 7
RETRIES_BEFORE_FAILURE = 2

theJSON = json.load(Path("plugins.json").open())
plugins = theJSON.get("Plugins", [])

config_dir = Path("Config").resolve()

config = json.load((config_dir / Path("config.json")).open())
failures = json.load((config_dir / Path("failures.json")).open())


def add_to_failures(plugin):
    if not failures.get(plugin["plugin"]["Name"]):
        failures[plugin["plugin"]["Name"]] = {plugin["commit"]["sha"]: 1}
    elif not failures[plugin["plugin"]["Name"]].get(plugin["commit"]["sha"]):
        failures[plugin["plugin"]["Name"]][plugin["commit"]["sha"]] = 1
    else:
        failures[plugin["plugin"]["Name"]][plugin["commit"]["sha"]] += 1


last_updated_path = config_dir / Path("last_updated.txt")

info = []
to_build = []
to_add = []

if last_updated_path.is_file() and last_updated_path.stat().st_size != 0:
    date_to_compare = dateutil.parser.parse(last_updated_path.read_text())
    last_updated_path.write_text(datetime.datetime.now(tz=datetime.timezone.utc).isoformat())
else:
    last_updated_path.touch()
    date_to_compare = datetime.datetime(2021, 3, 1, tzinfo=datetime.timezone.utc)
    last_updated_path.write_text(date_to_compare.isoformat())

print("Last update date is " + date_to_compare.isoformat())

token = sys.argv[1].strip()

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

    count = 1

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

        hit_failure_threshold = failures.get(plugin["Name"], {}).get(commit["sha"], 0) > RETRIES_BEFORE_FAILURE
        within_max_outstanding = count <= plugin.get("Max Per Run", MAX_OUTSTANDING_COMMITS)

        # Do not build if we hit the limit for builds per run for this plugin.
        if not within_max_outstanding:
            continue

        # Build if:
        # Newer than last checked and not in repo, OR not in repo and latest commit
        # AND must not have hit failure threshold (retries >= RETRIES_BEFORE_FAILURE)
        # OR Force is set to true (ignores blacklist as this is manual intervention)

        if (((newer and not_in_repo) or (not_in_repo and commits.index(commit) == 0)) and not hit_failure_threshold) or force_build:
            if commits.index(commit) == 0:
                print(plugin["Name"] + " by " + organization + " latest commit (" + commit_date.isoformat() + ") not built")
            else:
                print(plugin["Name"] + " by " + organization + " commit " + commit["sha"] + " (" + commit_date.isoformat() + ") not built")
            to_build.append({"plugin": plugin, "commit": commit})
            count += 1
        elif hit_failure_threshold:
            print(plugin["Name"] + " by " + organization + " commit " + commit["sha"] + " (" + commit_date.isoformat() + ") has hit failure threshold!")

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

print(color(f"\nBuilding {len(to_build)} things").bold)
for plugin in to_build:
    print(f"\nBuilding {color(plugin['plugin']['Name']).bold}")
    try:
        started = datetime.datetime.now()
        files = None
        files = builder.build(plugin["plugin"], commithash=plugin["commit"]["sha"])
    except Exception as error:
        duration = datetime.datetime.now() - started

        print("An error occurred!")
        print(error)
        traceback.print_tb(error.__traceback__)
        if files:
            print(f"Files: {files}")

        print(f"{color('Building of').red} {color(plugin['plugin']['Name']).red.bold} {color('errored').red}")
        print(f"Took {humanize.naturaldelta(duration)}")
        notify_error(token, plugin)
        errored.append(plugin)
        add_to_failures(plugin)
        continue

    duration = datetime.datetime.now() - started

    if files:
        print(f"{color('Building of').green} {color(plugin['plugin']['Name']).green.bold} {color('succeeded').green}")
        print(f"Took {humanize.naturaldelta(duration)}")

        results = plugin
        results["files"] = files

        print("Adding to config...")
        results["config_item"] = add_built(results, token)
        notify_success(token, results)
        succeeded.append(results)
    else:
        print(f"{color('Building of').red} {color(plugin['plugin']['Name']).red.bold} {color('failed').red}")
        print(f"Took {humanize.naturaldelta(duration)}")

        notify_failure(token, plugin)
        failed.append(plugin)
        add_to_failures(plugin)

print(color(f"\n{len(succeeded)} of {len(to_build)} built successfully\n").bold)
if len(succeeded) > 0:
    print(color("Succeeded:").green)
    for i in succeeded:
        print(i["plugin"]["Name"])
if len(failed) > 0:
    print(color("\nFailed:").red)
    for i in failed:
        print(i["plugin"]["Name"])
if len(errored) > 0:
    print(color("\nErrored:").red)
    for i in errored:
        print(i["plugin"]["Name"])

json.dump(failures, (config_dir / Path("failures.json")).open("w"), indent=2, sort_keys=True)


if os.environ.get("PROD", "false") == "true":
    repo = git.Repo(config_dir)
    if repo.is_dirty(untracked_files=True):
        repo.git.add(all=True)
        repo.git.commit(message="Deploying to builds")
        repo.git.push()


if len(failed) > 0 or len(errored) > 0:
    sys.exit(10)
