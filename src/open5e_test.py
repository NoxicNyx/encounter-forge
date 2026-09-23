import requests

url = "https://api.open5e.com/v2/creatures/"

parameters = {
    "document__key__in": "srd-2024"
}



next_url = url

while next_url is not None:
    response = requests.get(next_url, params=parameters)
    data = response.json()

    for creature in data["results"]:
        print(creature["Name"])

    next_url = data["next"]
    
