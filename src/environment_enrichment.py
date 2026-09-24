import sqlite3
import requests


# Open5e API
url = "https://api.open5e.com/v2/creatures/"

version_filter = {
    "document__key__in": "srd-2014"
}


# ---------------------------------------------------------------------------
# Get 2014 creature environments
# ---------------------------------------------------------------------------

creature_environments = {}

current_url = url


while current_url is not None:

    # Apply the 2014 filter only to the first request
    if current_url == url:

        response = requests.get(
            current_url,
            params=version_filter
        )

    # Use the API-provided URL for subsequent pages
    else:

        response = requests.get(
            current_url
        )

    response.raise_for_status()

    data = response.json()


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
unmatched = []
environment_links = 0


for monster_id, monster_name in monsters:

    environments = creature_environments.get(
        monster_name
    )


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
    f"Unmatched: {len(unmatched)}"
)

print("Unmatched creatures:")

for monster_name in unmatched:
    print(f"  - {monster_name}")

print(
    f"Environment links created: {environment_links}"
)