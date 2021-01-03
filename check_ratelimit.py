import sys
from hammock import Hammock as hammock

token = sys.argv[1].strip()
eee = hammock("https://api.github.com/rate_limit").GET(auth=("github-actions", token))
print(eee.text or eee.content)
