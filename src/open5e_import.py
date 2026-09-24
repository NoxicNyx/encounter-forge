import requests
import sqlite3

# Get an existing source from the database or create it if it doesn't exist
def get_or_create_source(cursor, document):

    # Get the source's unique key from the API response
    source_key = document["key"]

    # Check whether this source already exists in the database
    cursor.execute("""
        SELECT id
        FROM sources
        WHERE source_key = ?
    """, (source_key,))

    source = cursor.fetchone()

    # If the source already exists, return its database ID
    if source is not None:
        return source[0]

    # If the source doesn't exist, create a new record
    cursor.execute("""
        INSERT INTO sources (
            source_key,
            name,
            display_name,
            publisher,
            game_system,
            permalink
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        document["key"],
        document["name"],
        document["display_name"],
        document["publisher"]["name"],
        document["gamesystem"]["name"],
        document["permalink"]
    ))

    # Return the ID of the newly created source
    return cursor.lastrowid

# Get an existing monster from the database or create it if it doesn't exist
def get_or_create_monster(cursor, creature, source_id):

    # Get the monster's unique key from the API response
    creature_key = creature["key"]

    # Check whether this monster already exists in the database
    cursor.execute("""
        SELECT id
        FROM monsters
        WHERE creature_key = ?
    """, (creature_key,))
    
    monster = cursor.fetchone()

    # If the monster already exists, return its database ID
    if monster is not None:
        print(f"EXISTS: {creature['name']}")
        return monster[0]

    # If the monster doesn't exist, create a new record
    print(f"INSERTING: {creature['name']}")
    
    cursor.execute("""
        INSERT INTO monsters (
            source_id,
            creature_key,
            name,
            creature_type,
            size,
            category,
            subcategory,
            alignment,
            challenge_rating,
            proficiency_bonus,
            armour_class,
            armour_detail,
            hit_points,
            hit_dice,
            experience_points,
            initiative_bonus,
            passive_perception,
            normal_sight_range,
            darkvision_range,
            blindsight_range,
            tremorsense_range,
            truesight_range
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        source_id,
        creature["key"],
        creature["name"],
        creature["type"]["name"],
        creature["size"]["name"],
        creature["category"],
        creature["subcategory"],
        creature["alignment"],
        creature["challenge_rating"],
        creature["proficiency_bonus"],
        creature["armor_class"],
        creature["armor_detail"],
        creature["hit_points"],
        creature["hit_dice"],
        creature["experience_points"],
        creature["initiative_bonus"],
        creature["passive_perception"],
        creature["normal_sight_range"],
        creature["darkvision_range"],
        creature["blindsight_range"],
        creature["tremorsense_range"],
        creature["truesight_range"]
    ))
    # Return the ID of the newly created monster
    return cursor.lastrowid


# Connect to the SQLite database
connection = sqlite3.connect("db/encounter_forge.db")

# Enable foreign key enforcement for this database connection
connection.execute("PRAGMA foreign_keys = ON")

# Create a cursor for executing SQL statements
cursor = connection.cursor()


# Get creatures from Open5e
url = "https://api.open5e.com/v2/creatures/"

# Filter the API response to creatures from the 2024 SRD
version_filter = {
    "document__key__in": "srd-2024"
}

# Start with the first API page
current_url = url

# Continue requesting pages until there are no more
while current_url is not None:

    # Check page
    print(f"Processing: {current_url}")
    
    # Send a GET request to the current API page
    response = requests.get(
        current_url,
        params=version_filter
    )

    # Raise an error if the API request was unsuccessful
    response.raise_for_status()

    # Convert the API response from JSON into a Python dictionary
    data = response.json()

    # Process each creature on the current page
    for creature in data["results"]:

        source_id = get_or_create_source(
            cursor,
            creature["document"]
        )

        get_or_create_monster(
            cursor,
            creature,
            source_id
        )

    # Get the URL for the next page
    current_url = data["next"]

# Save all database changes
connection.commit()

# Close the database connection
connection.close()

