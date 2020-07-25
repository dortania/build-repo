import json
from pathlib import Path

import dateutil.parser
from hammock import Hammock as hammock


with open("gh token.txt") as f:
    token = f.read().strip()


config = json.load(Path("config.json").open())
plugins = json.load(Path("plugins.json").open())

count = 0


def sort_func(name, version):
    global count
    count += 1
    if version.get("datecommitted", None):
        return dateutil.parser.parse(version["datecommitted"])
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
        #print(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]).GET(auth=("dhinakg", token)).text))
        commit_date = dateutil.parser.parse(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]).GET(auth=("dhinakg", token)).text)["commit"]["committer"]["date"])
        version["datecommitted"] = commit_date.isoformat()
        return commit_date

def add_commit_date(name, version):
    if version.get("datecommitted", None):
        return version
    else:
        print("yeetus")
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
        commit_date = dateutil.parser.parse(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]).GET(auth=("dhinakg", token)).text)["commit"]["committer"]["date"])
        version["datecommitted"] = commit_date.isoformat()
        return version


for i in config:
    for j, item in enumerate(config[i]["versions"]):
        config[i]["versions"][j] = add_commit_date(i, item)

for i in config:
    config[i]["versions"].sort(key=lambda x: x["datecommitted"])

print(count)
json.dump(config, Path("config.json").open("w"), indent=2, sort_keys=True)
