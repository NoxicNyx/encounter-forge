import requests

url = "https://api.open5e.com/v2/creatures/"

versionFilter = {
    "document__key__in": "srd-2024"
}

creatureFilter = {
    "name__iexact": "goblin"
}

def creatureCheck(url, creatureFilter):
    response = requests.get(url,params=creatureFilter)
    data = response.json()
    goblin = data["results"][0]
    print(data["count"])
    for field, value in goblin.items():
        print(field, ":", value)

def nameList(url,versionFilter):
    next_url = url

    while next_url is not None:
        response = requests.get(next_url, params=versionFilter)
        data = response.json()

        for creature in data["results"]:
            print(creature["name"])

        next_url = data["next"]

creatureCheck(url, creatureFilter)