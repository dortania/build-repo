from pathlib import Path
import json

plugins = json.load(Path("plugins.json").open())
plugins["Plugins"].sort(key=lambda x: x["Name"])
json.dump(plugins, Path("plugins.json").open("w"), indent=2, sort_keys=True)
