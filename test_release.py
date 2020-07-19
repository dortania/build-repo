import json
import os
import pprint
import purl
import requests
import sys
import time
from hammock import Hammock as hammock

pp = pprint.PrettyPrinter()

with open("gh token.txt") as f:
    token = f.read().strip()

url_string = hammock(f"https://api.github.com/repos/dhinakg/ktextrepo-beta/releases", auth=("dhinakg", token))



get_release = url_string.GET()
for i in [i["id"] for i in get_release.json()]:
    af= url_string(i).DELETE()


derp = hammock("https://api.github.com/repos/dhinakg/ktextrepo-beta/git/refs/tags/testtag", auth=("dhinakg", token)).DELETE()


create_release = url_string.POST(json={
    "tag_name": "ab5e7f8322d6c73b1888f2ecb20a5eebef63e90a",
    "target_commitish": "builds",
    "name": "AirportBrcmFixup-ab5e7f8"
})

create_release_json = create_release.json()

pp.pprint(create_release_json["id"])

add_release_asset = hammock(str(purl.Template(create_release_json["upload_url"]).expand({"name": "derp", "label": "YEEEE"})), auth=("dhinakg", token)).POST(data="hehe", headers={"content-type": "text/plain; charset=us-ascii"})
print(add_release_asset)
if str(add_release_asset.json()) != "":
    pp.pprint(add_release_asset.json())


# 28716357