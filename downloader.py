import json
import distutils.util
import zipfile
from pathlib import Path
from hammock import Hammock as hammock

plugins = hammock("https://raw.githubusercontent.com/dortania/build-repo/github-actions/plugins.json").GET()
plugins = json.loads(plugins.text)

config = hammock("https://raw.githubusercontent.com/dortania/build-repo/builds/config.json").GET()
config = json.loads(config.text)
print("Global Settings: ")
ensure_latest = bool(distutils.util.strtobool(input("Ensure latest? (\"true\" or \"false\") ").lower()))
unzip = bool(distutils.util.strtobool(input("Unzip automatically and delete zip? (\"true\" or \"false\") ").lower()))
extract_dir = input("Put files in directory (leave blank for current dir): ") if unzip else None
while True:
    target = input("Enter product to download (case sensitive): ")
    dbg = input("Debug or release? (\"debug\" or \"release\") ").lower()
    try:
        if ensure_latest:
            organization = repo = None
            for plugin in plugins["Plugins"]:
                if plugin["Name"] == target:
                    organization, repo = plugin["URL"].strip().replace("https://github.com/", "").split("/")
                    break
            if not repo:
                print("Product " + target + " not available\n")
                continue
            commits_url = hammock("https://api.github.com").repos(organization, repo).commits.GET(params={"per_page": 100})
            commit_hash = json.loads(commits_url.text or commits_url.content)[0]["sha"]
            to_dl = None
            for i in config[target]["versions"]:
                if i["commit"]["sha"] == commit_hash:
                    to_dl = i
                    break
            if not to_dl:
                print("Latest version (" + commit_hash + ") unavailable\n")
                continue
        else:
            to_dl = config[target]["versions"][0]
        dl_link = to_dl["links"][dbg]
        print(f"Downloading {target} version {to_dl['version']} sha {to_dl['commit']['sha']} and date built {to_dl['date_built']}")
    except KeyError as error:
        if error.args[0] == target:
            print("Product " + error.args[0] + " not available\n")
            continue
        elif error.args[0] == dbg:
            print("Version " + error.args[0] + " not available\n")
            continue
        else:
            raise error
    file_name = Path(dl_link).name
    dl_url = hammock(dl_link).GET()
    Path(file_name).write_bytes(dl_url.content or dl_url.text)
    print("Finished downloading.")
    if unzip:
        with zipfile.ZipFile(file_name, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        Path(file_name).unlink()
        print("Finished extracting.")
    print("Done.\n")
