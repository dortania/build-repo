from pathlib import Path
import json
import hashlib
import datetime
import dateutil.parser
import mimetypes
from hammock import Hammock as hammock
import purl

mimetypes.init()

def hash_file(file_path: Path):
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def expand_globs(path: str):
    path = Path(path)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    return list(Path(path.root).glob(str(Path("").joinpath(*parts))))

def upload_release_asset(release_id, token, file_path: Path):
    upload_url = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases" + str(release["releaseid"])).GET().json()["upload_url"]
    mime_type = mimetypes.guess_type(file_path)
    if not mime_type[0]:
        print("Failed to guess mime type!")
        return False
    mime_type = mime_type[0] + f"; {mime_type[1]}" if mime_type[1] else ""
    
    asset_upload = hammock(str(purl.Template(upload_url).expand({"name": file_path.name, "label": file_path.name})), auth=("dhinakg", token)).POST(
        data = file_path.read_bytes(),
        headers = {"content-type": mime_type}
    )
    print(asset_upload)
    print(asset_upload.json())
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
    category_type = {"Kext": "Kexts", "Bootloader": "Bootloaders", "Other": "Others"}.get(plugin_type)
    debug = plugin_info.get("Debug", False)
    combined = plugin_info.get("Combined", False)

    if combined:
        debug_dir = script_dir / Path("Builds") / Path(category_type) / Path(name) / Path(commit_info["sha"]) / Path("Debug")
        release_dir = script_dir / Path("Builds") / Path(category_type) / Path(name) / Path(commit_info["sha"]) / Path("Release")
    else:
        path_to_files = script_dir / Path("Builds") / Path(category_type) / Path(name) / Path(commit_info["sha"]) / Path(("Debug" if debug else "Release"))
    
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
    release["version"] = files[2]
    release["dateadded"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    release["datecommitted"] = dateutil.parser.parse(commit_info["commit"]["committer"]["date"]).isoformat()
    release["source"] = "built"
    release["knowngood"] = False

    releases_url = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases", auth=("dhinakg", token))

    if not release.get("releaseid", None):
        # Create release
        nl = "\n" # No escapes in f-strings
        print({
            "tag_name": name + "-" + release["commit"],
            "target_commitish": "builds",
            "name": name + "-" + release["commit"]
        })
        create_release = hammock(f"https://api.github.com/repos/dhinakg/ktextrepo-beta/releases", auth=("dhinakg", token)).POST(json={
            "tag_name": name + "-" + release["commit"],
            "target_commitish": "builds",
            "name": name + "-" + release["commit"]
        })
        print(releases_url)
        print(create_release)
        print(create_release.text)
        print(create_release.status_code)
        print(create_release.json())
        print(create_release.json()["id"])
        release["releaseid"] = create_release.json()["id"]

    if not release.get("hashes", None):
        if combined:
            release["hashes"] = {"debug": {}, "release": {}}
        else:
            release["hashes"] = {"debug" if debug else "release": {}}
    
    if not release["hashes"].get("debug" if debug else "release"):
        release["hashes"]["debug" if debug else "release"] = {}
    if combined:
        release["hashes"]["debug"] = hash_file(debug_dir / Path(files[0]["debug"]))
        release["hashes"]["release"] = hash_file(release_dir / Path(files[0]["release"]))
    else:
        release["hashes"]["debug" if debug else "release"]["sha256"] = hash_file(path_to_files / Path(files[0]))
    
    if files[1] and combined:
        for file in files[1]:
            release["hashes"][file] = hash_file(debug_dir / Path(file))
    elif files[1] and not combined:
        for file in files[1]:
            release["hashes"][file] = hash_file(path_to_files / Path(file))

    if not release.get("links", None):
        release["links"] = {}
    
    if combined:
        for i in ["debug", "release"]:
            release["links"][i] = upload_release_asset(release["releaseid"], token, debug_dir if i == "debug" else release_dir / Path(files[0][i]))
    else:
        release["links"]["debug" if debug else "release"] = upload_release_asset(release["releaseid"], token, path_to_files / Path(files[0]))
    
    if files[1]:
        if not release.get("extras", None):
            release["extras"] = {}
        for file in files[1]:
            release["extras"][file] = upload_release_asset(release["releaseid"], token, debug_dir if combined else path_to_files / Path(file))
    
    upload_url = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/releases" + str(release["releaseid"])).POST(json={
        "body": f"""**Hashes**:
        Debug:
        {files[0]["debug"] if combined else files[0] + ': ' + release['hashes']['debug'] if combined or not debug else ''}
        Release:
        {files[0]["release"] if combined else files[0] + ': ' + release['hashes']['release'] if combined or not debug else ''}
        Extras:
        {nl.join([file + ': ' + release['hashes'][file] for file in files[1]]) if files[1] else ''}
        """
    })

    if ind is not None:
        config[name]["versions"][ind] = release
    else:
        config[name]["versions"].insert(0, release)
    json.dump(config, config_path.open(mode="w"), indent=2, sort_keys=True)
