import json
import distutils.util
import zipfile
from pathlib import Path
from hammock import Hammock as hammock

plugins = hammock("https://raw.githubusercontent.com/dhinakg/ktextrepo/builds/config.json").GET()
plugins = json.loads(plugins.text)
print("Global Settings: ")
unzip = bool(distutils.util.strtobool(input("Unzip automatically and delete zip? (\"true\" or \"false\") ").lower()))
extract_dir = input("Put files in directory (leave blank for current dir): ") if unzip else None
while True:
    target = input("Enter product to download (case sensitive): ")
    dbg = input("Debug or release? (\"debug\" or \"release\") ").lower()
    try:
        to_dl = plugins[target]["versions"][0]
        dl_link = to_dl["links"][dbg]
        print(f"Downloading {target} version {to_dl['version']} sha {to_dl['commit']} and date added {to_dl['dateadded']}")
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
