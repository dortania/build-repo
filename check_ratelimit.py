from hammock import Hammock as hammock

with open("gh token.txt") as f:
    token = f.read().strip()
eee = hammock("https://api.github.com/rate_limit").GET(auth=("dhinakg",token))
print(eee.text or eee.content)