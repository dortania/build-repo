import hashlib
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import magic
import purl
from hammock import Hammock as hammock

mime = magic.Magic(mime=True)


with open("gh token.txt") as f:
    token = f.read().strip()

config: dict = json.load(Path("Config/config.json").open())
plugins = json.load(Path("plugins.json").open())


def hash_file(file_path: Path):
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def expand_globs(path: str):
    path = Path(path)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    return list(Path(path.root).glob(str(Path("").joinpath(*parts))))


def upload_release_asset(release_id, token, file, name=None):
    upload_url = hammock("https://api.github.com/repos/dortania/build-repo/releases/" + str(release_id), auth=("github-actions", token)).GET().json()
    upload_url = upload_url["upload_url"]
    if isinstance(file, Path):
        mime_type = mime.from_file(str(file.resolve()))
    elif isinstance(file, bytes):
        mime_type = mime.from_buffer(file)
    if not mime_type:
        print("Failed to guess mime type!")
        return False

    asset_upload = hammock(str(purl.Template(upload_url).expand({"name": file.name if isinstance(file, Path) else name, "label": file.name if isinstance(file, Path) else name})), auth=("github-actions", token)).POST(
        data=file.read_bytes() if isinstance(file, Path) else file,
        headers={"content-type": mime_type}
    )
    return asset_upload.json()["browser_download_url"]


def paginate(url, token):
    url = hammock(url, auth=("github-actions", token)).GET()
    if url.links == {}:
        return url.json()
    else:
        container = url.json()
        while url.links.get("next"):
            url = hammock(url.links["next"]["url"], auth=("github-actions", token)).GET()
            container += url.json()
        return container


for product in config:
    if product == "_version":
        continue
    for index, version in enumerate(config[product]["versions"]):
        if version.get("release"):  # This has a release
            continue
        # No release
        releases_url = hammock("https://api.github.com/repos/dortania/build-repo/releases", auth=("github-actions", token))

        # Delete previous releases
        for i in paginate("https://api.github.com/repos/dortania/build-repo/releases", token):
            if i["name"] == (product + " " + version["commit"]["sha"][:7]):
                print("\tDeleting previous release...")
                releases_url(i["id"]).DELETE()
                time.sleep(3)  # Prevent race conditions

        # Delete tags
        check_tag = hammock("https://api.github.com/repos/dortania/build-repo/git/refs/tags/" + product + "-" + version["commit"]["sha"][:7], auth=("github-actions", token))
        if check_tag.GET().status_code != 404:
            print("\tDeleting previous tag...")
            check_tag.DELETE()
            time.sleep(3)  # Prevent race conditions

        # Create release
        create_release = releases_url.POST(json={
            "tag_name": product + "-" + version["commit"]["sha"][:7],
            "target_commitish": "builds",
            "name": product + " " + version["commit"]["sha"][:7]
        })

        version["release"] = {"id": create_release.json()["id"], "url": create_release.json()["html_url"]}

        for i in version["links"]:
            local_path = Path(version["links"][i].replace("https://raw.githubusercontent.com/dortania/ktextrepo/builds", "Builds"))
            if local_path.exists():
                version["links"][i] = upload_release_asset(version["release"]["id"], token, local_path)
                time.sleep(3)
            else:
                file = hammock(version["links"][i]).GET().content
                name = Path(urllib.parse.urlparse(version["links"][i]).path).name
                version["links"][i] = upload_release_asset(version["release"]["id"], token, file, name)
                time.sleep(3)

        for i in version.get("extras", []):
            local_path = Path(version["extras"][i].replace("https://raw.githubusercontent.com/dortania/ktextrepo/builds", "Builds"))
            if local_path.exists():
                version["extras"][i] = upload_release_asset(version["release"]["id"], token, local_path)
                time.sleep(3)
            else:
                file = hammock(version["extras"][i]).GET().content
                version["extras"][i] = upload_release_asset(version["release"]["id"], token, file, i)
                time.sleep(3)

        new_line = "\n"  # No escapes in f-strings

        version["release"]["description"] = f"""**Changes:**
{version['commit']['message'].strip()}
[View on GitHub]({version['commit']['url']}) ([browse tree]({version["commit"]["tree_url"]}))

**Hashes**:
{'**Debug:**' if version["links"].get("debug", None) else ''}
{(Path(urllib.parse.urlparse(version["links"]["debug"]).path).name + ': ' + version['hashes']['debug']["sha256"]) if version["links"].get("debug", None) else ''}
{'**Release:**' if version["links"].get("release", None) else ''}
{(Path(urllib.parse.urlparse(version["links"]["release"]).path).name + ': ' + version['hashes']['release']["sha256"]) if version["links"].get("release", None) else ''}
{'**Extras:**' if version.get("extras", None) else ''}
{new_line.join([(Path(urllib.parse.urlparse(version["extras"][file]).path).name + ': ' + version['hashes'][file]['sha256']) for file in version["extras"]]) if version.get("extras", None) else ''}
""".strip()

        hammock("https://api.github.com/repos/dortania/build-repo/releases/" + str(version["release"]["id"]), auth=("github-actions", token)).POST(json={
            "body": version["release"]["description"]
        })

        json.dump(config, Path("Config/config.json").open(mode="w"), indent=2, sort_keys=True)

result = subprocess.run(["git", "commit", "-am", "Deploying to builds"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=(Path(__file__).parent.absolute() / Path("Config")))
if result.returncode != 0:
    print("Commit failed!")
    print(result.stdout.decode())
    sys.exit(10)
result = subprocess.run("git push".split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=(Path(__file__).parent.absolute() / Path("Config")))
if result.returncode != 0:
    print("Push failed!")
    print(result.stdout.decode())
    sys.exit(10)
