import json
import datetime
import copy
from pathlib import Path
from hammock import Hammock as hammock
import dateutil.parser
import termcolor
import builder
from add import add_built


def matched_key_in_dict_array(array, key, value):
    if not array:
        return False
    for d in array:
        if d.get(key, None) == value:
            return True
    return False

MAX_OUTSTANDING_COMMITS = 3

theJSON = json.load(Path("plugins.json").open())
plugins = theJSON.get("Plugins", [])
config = json.load(Path("config.json").open())

info = []
to_build = []
to_add = []

if Path("last_updated.txt").is_file() and Path("last_updated.txt").stat().st_size != 0:
    date_to_compare = dateutil.parser.parse(Path("last_updated.txt").read_text())
    Path("last_updated.txt").write_text(datetime.datetime.now(tz=datetime.timezone.utc).isoformat())
else:
    Path("last_updated.txt").touch()
    # date_to_compare = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    date_to_compare = datetime.datetime(2020, 1, 16, tzinfo=datetime.timezone.utc)
    Path("last_updated.txt").write_text(date_to_compare.isoformat())

print("Last update date is " + date_to_compare.isoformat())

with open("gh token.txt") as f:
    token = f.read().strip()

for plugin in plugins:
    organization, repo = plugin["URL"].strip().replace("https://github.com/", "").split("/")
    base_url = hammock("https://api.github.com")

    releases_url = base_url.repos(organization, repo).releases.GET(auth=("dhinakg", token), params={"per_page": 100})
    releases = json.loads(releases_url.text or releases_url.content)
    if releases_url.headers.get("Link"):
        print(releases_url.headers["Link"])

    commits_url = base_url.repos(organization, repo).commits.GET(auth=("dhinakg", token), params={"per_page": 100})
    commits = json.loads(commits_url.text or commits_url.content)
    if releases_url.headers.get("Link"):
        print(releases_url.headers["Link"])

    for commit in commits:
        commit_date = dateutil.parser.parse(commit["commit"]["committer"]["date"])
        newer = commit_date >= date_to_compare
        force_build = plugin.get("Force") and commits.index(commit) == 0
        not_in_repo = not matched_key_in_dict_array(config.get(repo, {}).get("versions", []), "commit", commit["sha"])
        within_max_outstanding = commits.index(commit) <= MAX_OUTSTANDING_COMMITS
        if (newer and not_in_repo or force_build) and within_max_outstanding:
            if commits.index(commit) == 0:
                print(repo + " by " + organization + " latest commit (" + commit_date.isoformat() + ") not built")
            else:
                print(repo + " by " + organization + " commit " + commit["sha"] + " (" + commit_date.isoformat() + ") not built")
            to_build.append({"plugin": plugin, "commit": commit})

    for release in releases:
        release_date = dateutil.parser.parse(release["created_at"])
        if release_date >= date_to_compare:
            if releases.index(release) == 0:
                print(repo + " by " + organization + " latest release (" + release_date.isoformat() + ") not added")
            else:
                print(repo + " by " + organization + " release " + release["name"] + " (" + release_date.isoformat() + ") not added")
            to_add.append({"plugin": plugin, "release": release})


# for i in to_add: addRelease(i)


# Start setting up builder here.
builder = builder.Builder()

failed = []
succeeded = []

for plugin in to_build:
    plugin["plugin"]["Debug"] = False
debug_builds = copy.deepcopy(to_build)
for plugin in debug_builds:
    plugin["plugin"]["Debug"] = True
to_build.extend([i for i in debug_builds if not i["plugin"].get("Combined", False)])

termcolor.cprint("\nBuilding " + str(len(to_build)) + " things", attrs=["bold"])

for plugin in to_build:
    print("\nBuilding " + termcolor.colored(plugin["plugin"]["Name"], attrs=["bold"]))
    try:
        started = datetime.datetime.now()
        result = builder.build(plugin["plugin"], commithash=plugin["commit"]["sha"])
    except Exception as error:
        duration = datetime.datetime.now() - started
        print(error)
        if result:
            print(result)
        termcolor.cprint("Building of " + termcolor.colored(plugin["plugin"]["Name"], "red", attrs=["bold"]) + termcolor.colored(" failed", "red"), "red")
        failed.append(plugin)
        print("Took " + str(duration))
        continue
    if result:
        duration = datetime.datetime.now() - started
        termcolor.cprint("Building of " + termcolor.colored(plugin["plugin"]["Name"], "green", attrs=["bold"]) + termcolor.colored(" succeeded", "green"), "green")
        eee = plugin
        eee["result"] = result
        succeeded.append(eee)
        print("Took " + str(duration))
    else:
        duration = datetime.datetime.now() - started
        print(result)
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
if len(succeeded) > 0:
    print("\nAdding to config...")
    for i in succeeded:
        add_built(i)
