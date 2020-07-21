from pathlib import Path
import json
import hashlib
import datetime
import dateutil.parser


def hash_file(file_path: Path):
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def expand_globs(path: str):
    path = Path(path)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    return list(Path(path.root).glob(str(Path("").joinpath(*parts))))


def add_built(plugin):
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
    if not release.get("hashes", None):
        if combined:
            release["hashes"] = {"debug": {}, "release": {}}
        else:
            release["hashes"] = {"debug" if debug else "release": {}}
    if not release["hashes"].get("debug" if debug else "release"):
        release["hashes"]["debug" if debug else "release"] = {}
    if combined:
        release["hashes"]["debug"]["sha256"] = hash_file(debug_dir / Path(files[0]["debug"]))
        release["hashes"]["release"]["sha256"] = hash_file(release_dir / Path(files[0]["release"]))
    else:
        release["hashes"]["debug" if debug else "release"]["sha256"] = hash_file(path_to_files / Path(files[0]))
    if files[1] and combined:
        for file in files[1]:
            release["hashes"][file]["sha256"] = hash_file(debug_dir / Path(file))
    elif files[1] and not combined:
        for file in files[1]:
            release["hashes"][file]["sha256"] = hash_file(path_to_files / Path(file))
    if not release.get("links", None):
        release["links"] = {}
    base_url = '/'.join(["https://raw.githubusercontent.com/dhinakg/ktextrepo/builds", category_type, name, commit_info["sha"]])
    if combined:
        for i in ["debug", "release"]:
            release["links"][i] = base_url + ("/Debug/" if i == "debug" else "/Release/") + files[0][i]
    else:
        release["links"]["debug" if debug else "release"] = base_url + ("/Debug/" if debug else "/Release/") + files[0]
    if files[1]:
        if not release.get("extras", None):
            release["extras"] = {}
        for file in files[1]:
            release["extras"][file] = base_url + ("/Debug/" if debug else "/Release/") + file
    if ind is not None:
        config[name]["versions"][ind] = release
    else:
        config[name]["versions"].insert(0, release)
    json.dump(config, config_path.open(mode="w"), indent=2, sort_keys=True)
