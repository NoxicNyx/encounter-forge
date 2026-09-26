import json
import re
import sqlite3
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# Open5e API
url = "https://api.open5e.com/v2/creatures/"

version_filter = {
    "document__key__in": "srd-2014"
}


def fetch_json(request_url):
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Encounter-Forge/0.1"
        }
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


# ---------------------------------------------------------------------------
# Get 2014 creature environments
# ---------------------------------------------------------------------------

creature_environments = {}


def name_tokens(value):
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def source_name_within_monster(source_name, monster_name):
    """Allow Goblin's habitats to inform Goblin Warrior, but only by tokens."""
    source_tokens = name_tokens(source_name)
    monster_tokens = name_tokens(monster_name)
    return bool(source_tokens) and any(
        monster_tokens[index:index + len(source_tokens)] == source_tokens
        for index in range(len(monster_tokens) - len(source_tokens) + 1)
    )

current_url = f"{url}?{urlencode(version_filter)}"


while current_url is not None:

    # Apply the 2014 filter only to the first request
    data = fetch_json(current_url)


    # Store environments against each creature name
    for creature in data["results"]:

        environments = creature.get("environments") or []

        creature_environments[creature["name"]] = [
            environment["name"]
            for environment in environments
        ]


    # Move to the next page
    current_url = data["next"]


print(
    f"Loaded {len(creature_environments)} creatures from 2014."
)


# ---------------------------------------------------------------------------
# Connect to the 2024 database
# ---------------------------------------------------------------------------

connection = sqlite3.connect(
    "db/encounter_forge.db"
)

connection.execute(
    "PRAGMA foreign_keys = ON"
)

cursor = connection.cursor()


# ---------------------------------------------------------------------------
# Get all 2024 monsters
# ---------------------------------------------------------------------------

cursor.execute("""
    SELECT id, name
    FROM monsters
""")

monsters = cursor.fetchall()


# ---------------------------------------------------------------------------
# Match 2024 monsters to 2014 environments
# ---------------------------------------------------------------------------

matched = 0
substring_matched = 0
unmatched = []
environment_links = 0


for monster_id, monster_name in monsters:

    environments = creature_environments.get(monster_name)

    if environments is None:
        inherited_environments = {
            environment_name
            for source_name, source_environments in creature_environments.items()
            if source_name_within_monster(source_name, monster_name)
            for environment_name in source_environments
        }
        if inherited_environments:
            environments = sorted(inherited_environments)
            substring_matched += 1


    # No matching 2014 creature
    if environments is None:

        unmatched.append(monster_name)

        continue


    matched += 1


    # Process each environment
    for environment_name in environments:

        # Get the environment ID
        cursor.execute("""
            SELECT id
            FROM environments
            WHERE name = ?
        """, (
            environment_name,
        ))

        environment = cursor.fetchone()


        # Create environment if it doesn't exist
        if environment is None:

            cursor.execute("""
                INSERT INTO environments (
                    name
                )
                VALUES (?)
            """, (
                environment_name,
            ))

            environment_id = cursor.lastrowid

        else:

            environment_id = environment[0]


        # Connect the monster to the environment
        cursor.execute("""
            INSERT OR IGNORE INTO monster_environments (
                monster_id,
                environment_id,
                affinity
            )
            VALUES (?, ?, ?)
        """, (
            monster_id,
            environment_id,
            None
        ))


        environment_links += 1


# ---------------------------------------------------------------------------
# Save changes
# ---------------------------------------------------------------------------

connection.commit()

connection.close()


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

print(
    f"Matched: {matched}"
)

print(
    f"Substring matched: {substring_matched}"
)

print(
    f"Unmatched: {len(unmatched)}"
)

print("Unmatched creatures:")

for monster_name in unmatched:
    print(f"  - {monster_name}")

print(
    f"Environment links created: {environment_links}"
)
