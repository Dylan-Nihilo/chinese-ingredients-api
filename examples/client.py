"""Run the API, then: python examples/client.py 番茄"""
import json
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

query = sys.argv[1] if len(sys.argv) > 1 else "番茄"
with urlopen("http://127.0.0.1:8000/v1/ingredients?" + urlencode({"q": query}), timeout=5) as response:
    data = json.load(response)
for item in data["data"]:
    print(item["id"], item["name"], " / ".join(a["name"] for a in item["aliases"]))
