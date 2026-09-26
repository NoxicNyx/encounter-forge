import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

url = "https://api.open5e.com/v2/creatures/"

versionFilter = {
    "document__key__in": "srd-2024"
}

creatureFilter = {
    "name__icontains": "goblin"
}

combinedFilter = {**creatureFilter, **versionFilter}


def fetch_json(url_placeholder, filters):
    query = urlencode(filters)
    request = Request(
        f"{url_placeholder}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Encounter-Forge/0.1"
        }
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)

#looking at the API, which is filtered with the creatureFilter, to discover the schema of the data within the API for creatures
def creatureCheck(urlPlaceholder, Filter):
    data = fetch_json(urlPlaceholder, Filter)
    goblin = data["results"][0]
    #print(data["count"])
    for field, value in goblin.items():
        print(field, ":", value)

def nameList(urlPlaceholder,Filter):
    while urlPlaceholder is not None:
        data = fetch_json(urlPlaceholder, Filter)

        for creature in data["results"]:
            print(creature["name"])

        urlPlaceholder = data["next"]
        Filter = {}
    print(data["count"])

creatureCheck(url, combinedFilter)
