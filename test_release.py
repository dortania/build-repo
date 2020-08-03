import json
import pprint

# import purl
from hammock import Hammock as hammock

pp = pprint.PrettyPrinter()

with open("gh token.txt") as f:
    token = f.read().strip()

url_string = hammock("https://api.github.com/repos/dortania/build-repo/releases", auth=("github-actions", token))


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

get_release = url_string.GET()
for i in [i["id"] for i in get_release.json()]:
    url_string(i).DELETE()

delete_tags = hammock("https://api.github.com/repos/dortania/build-repo/git/matching-refs/tags", auth=("github-actions", token))

delete_tags = delete_tags.GET()
for i in [i["url"] for i in delete_tags.json()]:
    hammock(i, auth=("github-actions", token)).DELETE()


# derp = hammock("https://api.github.com/repos/dortania/build-repo/git/refs/tags/testtag", auth=("github-actions", token)).DELETE()


# create_release = url_string.POST(json={
#     "tag_name": "bb5e7f8322d6c73b1888f2ecb20a5eebef63e90a",
#     "target_commitish": "builds",
#     "name": "AirportBrcmFixup-bb5e7f8"
# })

# create_release_json = create_release.json()

# pp.pprint(create_release_json["id"])

# add_release_asset = hammock(str(purl.Template(create_release_json["upload_url"]).expand({"name": "derp", "label": "YEEEE"})), auth=("github-actions", token)).POST(data="hehe", headers={"content-type": "text/plain; charset=us-ascii"})
# print(add_release_asset)
# if str(add_release_asset.json()) != "":
#     pp.pprint(add_release_asset.json())


# 28716357
