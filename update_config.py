import copy
import json
import urllib.parse
from pathlib import Path

import dateutil.parser
import git
from hammock import Hammock as hammock

with open("gh token.txt") as f:
    token = f.read().strip()


config: dict = json.load(Path("Config/config.json").open())
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
        commit_date = dateutil.parser.parse(json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]).GET(auth=("github-actions", token)).text)["commit"]["committer"]["date"])
        version["datecommitted"] = commit_date.isoformat()
        return version


def add_commit_url(name, version):
    if version.get("commit", {}).get("url", None) and version.get("commit", {}).get("tree_url", None):
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
        html_url = json.loads(hammock("https://api.github.com").repos(organization, repo).commits(version["commit"]["sha"]).GET(auth=("github-actions", token)).text)["html_url"]
        version["commit"]["url"] = html_url
        version["commit"]["tree_url"] = html_url.replace("/commit/", "/tree/")
        return version


config = {i: v for i, v in config.items() if not i.startswith("_")}

for i in config:
    for j, item in enumerate(config[i]["versions"]):
        config[i]["versions"][j] = add_commit_date(i, item)
    config[i]["versions"].sort(key=lambda x: x["datecommitted"], reverse=True)

for i in config:
    for j, item in enumerate(config[i]["versions"]):
        config[i]["versions"][j].pop("knowngood", False)
        hashes = copy.deepcopy(config[i]["versions"][j]["hashes"])
        for k in config[i]["versions"][j]["hashes"]:
            if type(config[i]["versions"][j]["hashes"][k]) != dict:
                hashes[k] = {"sha256": config[i]["versions"][j]["hashes"][k]}
        config[i]["versions"][j]["hashes"] = hashes
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if not type(item.get("commit")) == dict]:
        sha = config[i]["versions"][j].pop("commit")
        desc = config[i]["versions"][j].pop("description")
        config[i]["versions"][j]["commit"] = {"sha": sha, "message": desc}
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("release", {}).get("id", None) and (not item.get("release", {}).get("description", None) or not item.get("release", {}).get("url", None))]:
        rel = json.loads(hammock("https://api.github.com/repos/dortania/build-repo/releases/" + str(config[i]["versions"][j]["release"]["id"]), auth=("github-actions", token)).GET().text)
        config[i]["versions"][j]["release"]["description"] = rel["body"] if rel.get("body") else None
        config[i]["versions"][j]["release"]["url"] = rel["html_url"] if rel.get("html_url") else None
    config[i]["versions"] = [i for i in config[i]["versions"] if i.get("release", {}).get("url", True)]
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("extras", None)]:
        item["extras"] = {i: v for i, v in item["extras"].items() if v}
    for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if not item.get("extras", True)]:
        item.pop("extras", False)
#     # Temporary
#     for j, item in [(j, item) for (j, item) in enumerate(config[i]["versions"]) if item.get("release", {}).get("description", False)]:
#         new_line = "\n"
#         item["release"]["description"] = f"""**Changes:**
# {item['commit']['message'].strip()}
# [View on GitHub]({item['commit']['url']}) ([browse tree]({item["commit"]["tree_url"]}))

# **Hashes**:
# {'**Debug:**' if item["links"].get("debug", None) else ''}
# {(Path(urllib.parse.urlparse(item["links"]["debug"]).path).name + ': ' + item['hashes']['debug']["sha256"]) if item["links"].get("debug", None) else ''}
# {'**Release:**' if item["links"].get("release", None) else ''}
# {(Path(urllib.parse.urlparse(item["links"]["release"]).path).name + ': ' + item['hashes']['release']["sha256"]) if item["links"].get("release", None) else ''}
# {'**Extras:**' if item.get("extras", None) else ''}
# {new_line.join([(Path(urllib.parse.urlparse(item["extras"][file]).path).name + ': ' + item['hashes'][file]['sha256']) for file in item["extras"]]) if item.get("extras", None) else ''}
# """.strip()

for i in config:
    for j, item in enumerate(config[i]["versions"]):
        config[i]["versions"][j] = add_commit_url(i, item)

config["_version"] = 2


json.dump(config, Path("Config/config.json").open("w"), indent=2, sort_keys=True)

repo = git.Repo("Config")
if repo.is_dirty(untracked_files=True):
    repo.git.add(all=True)
    repo.git.commit(message="Deploying to builds")
    repo.git.push()
