import copy
import json
from pathlib import Path


def save_config(data: dict):
    config_dir = Path(__file__).parent.absolute() / Path("Config")
    plugin_dir = config_dir / Path("plugins")
    plugin_dir.mkdir(exist_ok=True)

    version = data["_version"]

    for plugin in data:
        if plugin == "_version":
            continue
        data[plugin]["versions"].sort(key=lambda x: (x["date_committed"], x["date_authored"]), reverse=True)
        json.dump(data[plugin] | {"_version": version}, (plugin_dir / Path(f"{plugin}.json")).open("w"), sort_keys=True)

    json.dump(data, (config_dir / Path("config.json")).open("w"), sort_keys=True)

    latest = copy.deepcopy(data)
    for plugin in latest:
        if plugin == "_version":
            continue
        latest[plugin]["versions"] = [latest[plugin]["versions"][0]]

    json.dump(latest, (config_dir / Path("latest.json")).open("w"), sort_keys=True)
    json.dump({"plugins": list(data.keys()), "_version": version}, (config_dir / Path("plugins.json")).open("w"), sort_keys=True)
