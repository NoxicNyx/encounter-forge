import requests
import sqlite3


def get_or_create_source(cursor, document):

    source_key = document["key"]

    cursor.execute("""
        SELECT id
        FROM sources
        WHERE source_key = ?
    """, (source_key,))

    source = cursor.fetchone()

    if source is not None:
        return source[0]

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

    return cursor.lastrowid


def get_or_create_monster(cursor, creature, source_id):

    creature_key = creature["key"]

    cursor.execute("""
        SELECT id
        FROM monsters
        WHERE creature_key = ?
    """, (creature_key,))
    
    monster = cursor.fetchone()

    if monster is not None:
        print(f"EXISTS: {creature['name']}")
        return monster[0]

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

    return cursor.lastrowid


# Connect to database

connection = sqlite3.connect("db/encounter_forge.db")
connection.execute("PRAGMA foreign_keys = ON")

cursor = connection.cursor()


# Get creature from Open5e

url = "https://api.open5e.com/v2/creatures/"

version_filter = {
    "document__key__in": "srd-2024"
}

response = requests.get(url, params=version_filter)
response.raise_for_status()

data = response.json()


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


# Save changes

connection.commit()
connection.close()