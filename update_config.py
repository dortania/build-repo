import json
from pathlib import Path

import dateutil.parser
from hammock import Hammock as hammock


with open("gh token.txt") as f:
    token = f.read().strip()


config: dict = json.load(Path("config.json").open())
plugins = json.load(Path("plugins.json").open())


def add_commit_date(name, version):
    if version.get("datecommitted", None):
        return version
    else:
        organization = repo = None
        for plugin in plugins["Plugins"]:
            if name == "AppleSupportPkg":
                repo = name
                organization = "acidanthera"
                break
            if plugin["Name"] == name:
                organization, repo = plugin["URL"].strip().replace("https://github.com/", "").split("/")
                break
        if not repo:
            print("Product " + name + " not found")
            raise Exception
        commit_date = dateutil.parser.parse(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]).GET(auth=("dhinakg", token)).text)["commit"]["committer"]["date"])
        version["datecommitted"] = commit_date.isoformat()
        return version


config = {i: v for i, v in config.items() if not i.startswith("_")}

for i in config:
    for j, item in enumerate(config[i]["versions"]):
        config[i]["versions"][j] = add_commit_date(i, item)
    config[i]["versions"].sort(key=lambda x: x["datecommitted"], reverse=True)

for i in config:
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if not type(item.get("commit")) == dict]:
        sha = config[i]["versions"][j].pop("commit")
        desc = config[i]["versions"][j].pop("description")
        config[i]["versions"][j]["commit"] = {"sha": sha, "message": desc}
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("releaseid", None)]:
        relid = config[i]["versions"][j].pop("releaseid")
        config[i]["versions"][j]["release"] = {"id": relid}
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("release", {}).get("id", None) and not item.get("release", {}).get("description", None)]:
        rel = json.loads(hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases/" + str(config[i]["versions"][j]["release"]["id"]), auth=("dhinakg", token)).GET().text)
        config[i]["versions"][j]["release"]["description"] = rel["body"] if rel.get("body") else None
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("release", {}).get("id", None) and not item.get("release", {}).get("url", None)]:
        rel = json.loads(hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases/" + str(config[i]["versions"][j]["release"]["id"]), auth=("dhinakg", token)).GET().text)
        config[i]["versions"][j]["release"]["url"] = rel["html_url"] if rel.get("html_url") else None


config["_version"] = 2


json.dump(config, Path("config.json").open("w"), indent=2, sort_keys=True)
