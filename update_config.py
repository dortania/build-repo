import copy
import json
import sys
import urllib.parse
from pathlib import Path

import dateutil.parser
import git
from hammock import Hammock as hammock

token = sys.argv[1].strip()


config: dict = json.load(Path("Config/config.json").open())
plugins = json.load(Path("plugins.json").open())

# version 2 to 3

if config["_version"] == 2:
    def add_author_date(name, version):
        if version.get("date_authored", None):
            return version
        else:
            organization = repo = None
            for plugin in plugins["Plugins"]:
                if name == "AppleSupportPkg" or name == "BT4LEContinuityFixup":
                    repo = name
                    organization = "acidanthera"
                    break
                elif name == "NoTouchID":
                    repo = name
                    organization = "al3xtjames"
                    break
                if plugin["Name"] == name:
                    organization, repo = plugin["URL"].strip().replace("https://github.com/", "").split("/")
                    break
            if not repo:
                print("Product " + name + " not found")
                raise Exception
            commit_date = dateutil.parser.parse(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]["sha"]).GET(auth=("github-actions", token)).text)["commit"]["author"]["date"])
            version["date_authored"] = commit_date.isoformat()
            return version

    config = {i: v for i, v in config.items() if not i.startswith("_")}

    for i in config:
        for j, item in enumerate(config[i]["versions"]):
            config[i]["versions"][j] = add_author_date(i, item)
            print(f"Added {config[i]['versions'][j]['date_authored']} for {i} {config[i]['versions'][j]['commit']['sha']}")

        json.dump(config, Path("Config/config.json").open("w"), sort_keys=True)

    for i in config:
        for j, item in enumerate(config[i]["versions"]):
            if not config[i]["versions"][j].get("date_committed"):
                config[i]["versions"][j]["date_committed"] = config[i]["versions"][j].pop("datecommitted")
            if not config[i]["versions"][j].get("date_built"):
                config[i]["versions"][j]["date_built"] = config[i]["versions"][j].pop("dateadded")

        config[i]["versions"].sort(key=lambda x: (x["date_committed"], x["date_authored"]), reverse=True)
        json.dump(config, Path("Config/config.json").open("w"), sort_keys=True)

    config["_version"] = 3


json.dump(config, Path("Config/config.json").open("w"), sort_keys=True)

repo = git.Repo("Config")
if repo.is_dirty(untracked_files=True):
    repo.git.add(all=True)
    repo.git.commit(message="Deploying to builds")
    repo.git.push()
