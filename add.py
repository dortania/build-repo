import datetime
import hashlib
import json
from pathlib import Path

import dateutil.parser
import magic
import purl
from hammock import Hammock as hammock

mime = magic.Magic(mime=True)


def hash_file(file_path: Path):
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def expand_globs(path: str):
    path = Path(path)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    return list(Path(path.root).glob(str(Path("").joinpath(*parts))))


def upload_release_asset(release_id, token, file_path: Path):
    upload_url = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases/" + str(release_id), auth=("dhinakg", token)).GET().json()
    upload_url = upload_url["upload_url"]
    mime_type = mime.from_file(str(file_path.resolve()))
    if not mime_type[0]:
        print("Failed to guess mime type!")
        return False

    asset_upload = hammock(str(purl.Template(upload_url).expand({"name": file_path.name, "label": file_path.name})), auth=("dhinakg", token)).POST(
        data=file_path.read_bytes(),
        headers={"content-type": mime_type}
    )
    return asset_upload.json()["browser_download_url"]


def add_built(plugin, token):
    plugin_info = plugin["plugin"]
    commit_info = plugin["commit"]
    files = plugin["result"]

    script_dir = Path(__file__).parent.absolute()
    config_path = script_dir / Path("config.json")
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
        for version in config[name]["versions"]:
            if version.get("commit") == commit_info["sha"]:
                release = version
                ind = config[name]["versions"].index(version)
                # print("Found at index " + str(ind) + " (" + commit_info["sha"] + ", " + name + ")")
                break

    release["commit"] = commit_info["sha"]
    release["description"] = commit_info["commit"]["message"]
    release["version"] = files["version"]
    release["dateadded"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    release["datecommitted"] = dateutil.parser.parse(commit_info["commit"]["committer"]["date"]).isoformat()
    release["source"] = "built"

    releases_url = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases", auth=("dhinakg", token))

    # Delete previous releases
    get_all_releases = releases_url.GET()
    for i in [i["id"] for i in get_all_releases.json() if i["tag_name"] == name + "-" + release["commit"][:7]]:
        releases_url(i).DELETE()

    # Delete tags
    check_tag = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/git/refs/tags/" + name + "-" + release["commit"][:7], auth=("dhinakg", token))
    if check_tag.GET().status_code != 404:
        check_tag.DELETE()

    # Create release
    create_release = releases_url.POST(json={
        "tag_name": name + "-" + release["commit"][:7],
        "target_commitish": "builds",
        "name": name + " " + release["commit"][:7]
    })
    # print(create_release.json()["id"])
    release["releaseid"] = create_release.json()["id"]

    if not release.get("hashes", None):
        release["hashes"] = {"debug": {"sha256": ""}, "release": {"sha256": ""}}

    release["hashes"]["debug"] = {"sha256": hash_file(files["debug"])}
    release["hashes"]["release"] = {"sha256": hash_file(files["release"])}

    if files["extras"]:
        for file in files["extras"]:
            release["hashes"][file.name] = {"sha256": hash_file(file)}

    if not release.get("links", None):
        release["links"] = {}

    for i in ["debug", "release"]:
        release["links"][i] = upload_release_asset(release["releaseid"], token, files[i])

    if files["extras"]:
        if not release.get("extras", None):
            release["extras"] = {}
        for file in files["extras"]:
            release["extras"][file.name] = upload_release_asset(release["releaseid"], token, file)
    new_line = "\n"  # No escapes in f-strings

    hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases/" + str(release["releaseid"]), auth=("dhinakg", token)).POST(json={
        "body": f"""**Hashes**:
        Debug:
        {files["debug"].name + ': ' + release['hashes']['debug']["sha256"]}
        Release:
        {files["release"].name + ': ' + release['hashes']['release']["sha256"]}
        {'Extras:' if files["extras"] else ''}
        {new_line.join([file.name + ': ' + release['hashes'][file.name]['sha256'] for file in files["extras"]]) if files["extras"] else ''}
        """
    })

    if ind is not None:
        config[name]["versions"][ind] = release
    else:
        config[name]["versions"].insert(0, release)
    json.dump(config, config_path.open(mode="w"), indent=2, sort_keys=True)
