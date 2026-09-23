import requests

url = "https://api.open5e.com/v2/creatures/"

versionFilter = {
    "document__key__in": "srd-2024"
}

creatureFilter = {
    "name__icontains": "goblin"
}

combinedFilter = {**creatureFilter, **versionFilter}

#looking at the API, which is filtered with the creatureFilter, to discover the schema of the data within the API for creatures
def creatureCheck(url, Filter):
    response = requests.get(url,params=Filter)
    data = response.json()
    goblin = data["results"][0]
    print(data["count"])
    for field, value in goblin.items():
        print(field, ":", value)

def nameList(urlPlaceholder,Filter):
    while urlPlaceholder is not None:
        response = requests.get(urlPlaceholder, params=Filter)
        data = response.json()

        for creature in data["results"]:
            print(creature["name"])

        urlPlaceholder = data["next"]
    print(data["count"])

nameList(url, combinedFilter)