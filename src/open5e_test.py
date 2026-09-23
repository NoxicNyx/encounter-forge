import requests

url = "https://api.open5e.com/v2/creatures/"
params = {
    "name__iexact": "goblin"
}

response = requests.get(url, params=params)

print(response.json())