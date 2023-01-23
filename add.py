import datetime
import hashlib
import json
import time
import zipfile
from pathlib import Path

import dateutil.parser
import magic
import purl
from hammock import Hammock as hammock

from config_mgmt import save_config
from util import config_dir, is_prod, push_config

mime = magic.Magic(mime=True)


def hash_file(file_path: Path):
    return {"sha256": hashlib.sha256(file_path.read_bytes()).hexdigest()}


def hash_bytes(b: bytes):
    return {"sha256": hashlib.sha256(b).hexdigest()}


def expand_globs(str_path: str):
    path = Path(str_path)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    return list(Path(path.root).glob(str(Path("").joinpath(*parts))))


def upload_release_asset(release_id, token, file_path: Path):
    if is_prod():
        upload_url = hammock("https://api.github.com/repos/dortania/build-repo/releases/" + str(release_id), auth=("github-actions", token)).GET().json()
        try:
            upload_url = upload_url["upload_url"]
        except Exception:
            print(upload_url)
            raise
        mime_type = mime.from_file(str(file_path.resolve()))
        if not mime_type[0]:
            print("Failed to guess mime type!")
            raise RuntimeError

        asset_upload = hammock(str(purl.Template(upload_url).expand({"name": file_path.name, "label": file_path.name})), auth=("github-actions", token)).POST(
            data=file_path.read_bytes(), headers={"content-type": mime_type}
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


def add_built(plugin, token):
    plugin_info = plugin["plugin"]
    commit_info = plugin["commit"]
    files = plugin["files"]

    config_path = config_dir / Path("config.json")
    config_path.touch()
    config = json.load(config_path.open())

    name = plugin_info["Name"]
    plugin_type = plugin_info.get("Type", "Kext")

    ind = None

    if not config.get(name, None):
        config[name] = {}
    if not config[name].get("type", None):
        config[name]["type"] = plugin_type
    if not config[name].get("versions", None):
        config[name]["versions"] = []

    release = {}
    if config[name]["versions"]:
        config[name]["versions"] = [i for i in config[name]["versions"] if not (i.get("commit", {}).get("sha", None) == commit_info["sha"])]

    release["commit"] = {"sha": commit_info["sha"], "message": commit_info["commit"]["message"], "url": commit_info["html_url"], "tree_url": commit_info["html_url"].replace("/commit/", "/tree/")}
    release["version"] = files["version"]
    release["date_built"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    release["date_committed"] = dateutil.parser.parse(commit_info["commit"]["committer"]["date"]).isoformat()
    release["date_authored"] = dateutil.parser.parse(commit_info["commit"]["author"]["date"]).isoformat()
    release["source"] = "built"

    releases_url = hammock("https://api.github.com/repos/dortania/build-repo/releases", auth=("github-actions", token))

    if is_prod():
        # Delete previous releases
        for i in paginate("https://api.github.com/repos/dortania/build-repo/releases", token):
            if i["name"] == (name + " " + release["commit"]["sha"][:7]):
                print("\tDeleting previous release...")
                releases_url(i["id"]).DELETE()
                time.sleep(3)  # Prevent race conditions

        # Delete tags
        check_tag = hammock("https://api.github.com/repos/dortania/build-repo/git/refs/tags/" + name + "-" + release["commit"]["sha"][:7], auth=("github-actions", token))
        if check_tag.GET().status_code != 404:
            print("\tDeleting previous tag...")
            check_tag.DELETE()
            time.sleep(3)  # Prevent race conditions

        # Create release
        create_release = releases_url.POST(json={"tag_name": name + "-" + release["commit"]["sha"][:7], "target_commitish": "builds", "name": name + " " + release["commit"]["sha"][:7]})
        # print(create_release.json()["id"])
        release["release"] = {"id": create_release.json()["id"], "url": create_release.json()["html_url"]}
    else:
        release["release"] = {"id": 0, "url": ""}

    release.setdefault("hashes", {"debug": {"sha256": ""}, "release": {"sha256": ""}})

    release["hashes"]["debug"] = hash_file(files["debug"])
    release["hashes"]["release"] = hash_file(files["release"])

    if files["extras"]:
        for file in files["extras"]:
            assert file.name not in ["debug", "release"], "Extra file cannot be named debug or release"
            release["hashes"][file.name] = hash_file(file)

    release.setdefault("links", {})
    release.setdefault("fingerprints", {"debug": {}, "release": {}})

    files_to_fingerprint = plugin_info.get("Fingerprints", [f"{name}.kext/Contents/MacOS/{name}"])
    if files_to_fingerprint is False:
        files_to_fingerprint = []

    for i in ["debug", "release"]:
        release["links"][i] = upload_release_asset(release["release"]["id"], token, files[i])
        with zipfile.ZipFile(files[i]) as zip_file:
            for fingerprint_file in plugin_info.get("Fingerprints", files_to_fingerprint):
                with zip_file.open(fingerprint_file) as f:
                    release["fingerprints"][i][fingerprint_file] = hash_bytes(f.read())

    if files["extras"]:
        if not release.get("extras", None):
            release["extras"] = {}
        for file in files["extras"]:
            release["extras"][file.name] = upload_release_asset(release["release"]["id"], token, file)
    new_line = "\n"  # No escapes in f-strings

    release["release"][
        "description"
    ] = f"""**Changes:**
{release['commit']['message'].strip()}
[View on GitHub]({release['commit']['url']}) ([browse tree]({release['commit']['tree_url']}))

**Hashes**:
**Debug:**
{files["debug"].name + ': ' + release['hashes']['debug']["sha256"]}
**Release:**
{files["release"].name + ': ' + release['hashes']['release']["sha256"]}
{'**Extras:**' if files["extras"] else ''}
{new_line.join([(file.name + ': ' + release['hashes'][file.name]['sha256']) for file in files["extras"]]) if files["extras"] else ''}
""".strip()

    if is_prod():
        hammock("https://api.github.com/repos/dortania/build-repo/releases/" + str(release["release"]["id"]), auth=("github-actions", token)).POST(json={"body": release["release"]["description"]})

    config[name]["versions"].insert(0, release)
    config[name]["versions"].sort(key=lambda x: (x["date_committed"], x["date_authored"]), reverse=True)
    save_config(config)

    push_config()

    return release
