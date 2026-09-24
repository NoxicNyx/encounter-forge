import re
import sqlite3

import requests


API_URL = "https://api.open5e.com/v2/creatures/"

VERSION_FILTER = {
    "document__key__in": "srd-2024"
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_name(value):
    """Return the name from an Open5e object or return the value itself."""
    if isinstance(value, dict):
        return value.get("name")
    return value


def get_number(value):
    """Return a numeric value where possible."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)

        if match:
            number = float(match.group())

            if number.is_integer():
                return int(number)

            return number

    return None


def get_text(value):
    """Convert a value into text."""
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return value.get("name") or value.get("desc") or str(value)

    return str(value)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

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

    publisher = document.get("publisher") or {}
    gamesystem = document.get("gamesystem") or {}

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
        source_key,
        document.get("name"),
        document.get("display_name"),
        publisher.get("name"),
        gamesystem.get("name"),
        document.get("permalink")
    ))

    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------

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

    creature_type = get_name(creature.get("type"))
    size = get_name(creature.get("size"))

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
        creature.get("name"),
        creature_type,
        size,
        creature.get("category"),
        creature.get("subcategory"),
        creature.get("alignment"),
        creature.get("challenge_rating"),
        creature.get("proficiency_bonus"),
        creature.get("armor_class"),
        creature.get("armor_detail"),
        creature.get("hit_points"),
        creature.get("hit_dice"),
        creature.get("experience_points"),
        creature.get("initiative_bonus"),
        creature.get("passive_perception"),
        creature.get("normal_sight_range"),
        creature.get("darkvision_range"),
        creature.get("blindsight_range"),
        creature.get("tremorsense_range"),
        creature.get("truesight_range")
    ))

    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Ability scores
# ---------------------------------------------------------------------------

def insert_ability_scores(cursor, monster_id, creature):

    scores = creature.get("ability_scores") or {}

    cursor.execute("""
        INSERT OR REPLACE INTO monster_ability_scores (
            monster_id,
            strength,
            dexterity,
            constitution,
            intelligence,
            wisdom,
            charisma
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        monster_id,
        scores.get("strength"),
        scores.get("dexterity"),
        scores.get("constitution"),
        scores.get("intelligence"),
        scores.get("wisdom"),
        scores.get("charisma")
    ))


# ---------------------------------------------------------------------------
# Ability modifiers
# ---------------------------------------------------------------------------

def insert_modifiers(cursor, monster_id, creature):

    modifiers = creature.get("modifiers") or {}

    cursor.execute("""
        INSERT OR REPLACE INTO monster_modifiers (
            monster_id,
            strength,
            dexterity,
            constitution,
            intelligence,
            wisdom,
            charisma
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        monster_id,
        modifiers.get("strength"),
        modifiers.get("dexterity"),
        modifiers.get("constitution"),
        modifiers.get("intelligence"),
        modifiers.get("wisdom"),
        modifiers.get("charisma")
    ))


# ---------------------------------------------------------------------------
# Speeds
# ---------------------------------------------------------------------------

def insert_speeds(cursor, monster_id, creature):

    speeds = creature.get("speed_all") or creature.get("speed") or {}

    cursor.execute("""
        INSERT OR REPLACE INTO monster_speeds (
            monster_id,
            walk,
            crawl,
            fly,
            burrow,
            climb,
            swim,
            hover,
            unit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        monster_id,
        get_number(speeds.get("walk")),
        get_number(speeds.get("crawl")),
        get_number(speeds.get("fly")),
        get_number(speeds.get("burrow")),
        get_number(speeds.get("climb")),
        get_number(speeds.get("swim")),
        speeds.get("hover"),
        "feet"
    ))


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

def get_or_create_language(cursor, language):

    language_name = get_text(language)

    if not language_name:
        return None

    language_key = language_name.lower().strip().replace(" ", "-")

    cursor.execute("""
        SELECT id
        FROM languages
        WHERE language_key = ?
    """, (language_key,))

    existing = cursor.fetchone()

    if existing is not None:
        return existing[0]

    cursor.execute("""
        INSERT INTO languages (
            language_key,
            name,
            description
        )
        VALUES (?, ?, ?)
    """, (
        language_key,
        language_name,
        None
    ))

    return cursor.lastrowid


def insert_languages(cursor, monster_id, creature):

    languages = creature.get("languages")

    if not languages:
        return

    if isinstance(languages, str):
        languages = [languages]

    elif isinstance(languages, dict):
        languages = list(languages.values())

    for language in languages:

        language_id = get_or_create_language(
            cursor,
            language
        )

        if language_id is None:
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO monster_languages (
                monster_id,
                language_id
            )
            VALUES (?, ?)
        """, (
            monster_id,
            language_id
        ))


# ---------------------------------------------------------------------------
# Saving throws
# ---------------------------------------------------------------------------

def insert_saving_throws(cursor, monster_id, creature):

    saving_throws = creature.get("saving_throws") or {}

    for ability, modifier in saving_throws.items():

        modifier = get_number(modifier)

        if modifier is None:
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO monster_saving_throws (
                monster_id,
                ability,
                modifier
            )
            VALUES (?, ?, ?)
        """, (
            monster_id,
            ability,
            modifier
        ))


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def insert_skills(cursor, monster_id, creature):

    skills = creature.get("skill_bonuses") or {}

    for skill, modifier in skills.items():

        modifier = get_number(modifier)

        if modifier is None:
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO monster_skills (
                monster_id,
                skill,
                modifier
            )
            VALUES (?, ?, ?)
        """, (
            monster_id,
            skill,
            modifier
        ))


# ---------------------------------------------------------------------------
# Defenses
# ---------------------------------------------------------------------------

def insert_defenses(cursor, monster_id, creature):

    defense_groups = {
        "resistance": creature.get("resistances"),
        "immunity": creature.get("immunities"),
        "vulnerability": creature.get("vulnerabilities")
    }

    for defense_type, defenses in defense_groups.items():

        if not defenses:
            continue

        if isinstance(defenses, str):
            defenses = [defenses]

        for defense in defenses:

            if isinstance(defense, dict):
                damage_type = (
                    defense.get("damage_type")
                    or defense.get("type")
                    or defense.get("name")
                )
            else:
                damage_type = str(defense)

            if not damage_type:
                continue

            cursor.execute("""
                SELECT id
                FROM monster_defenses
                WHERE monster_id = ?
                AND defense_type = ?
                AND damage_type = ?
            """, (
                monster_id,
                defense_type,
                damage_type
            ))

            if cursor.fetchone() is not None:
                continue

            cursor.execute("""
                INSERT INTO monster_defenses (
                    monster_id,
                    defense_type,
                    damage_type
                )
                VALUES (?, ?, ?)
            """, (
                monster_id,
                defense_type,
                damage_type
            ))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def get_action_description(action):

    return (
        action.get("desc")
        or action.get("description")
        or action.get("text")
    )


def insert_actions(cursor, monster_id, creature):

    actions = creature.get("actions") or []

    for order, action in enumerate(actions, start=1):

        if not isinstance(action, dict):
            continue

        name = action.get("name")

        if not name:
            continue

        description = get_action_description(action)

        action_type = (
            action.get("type")
            or action.get("action_type")
        )

        usage = action.get("usage") or {}

        usage_type = None
        usage_parameter = None

        if isinstance(usage, dict):

            usage_type = (
                usage.get("type")
                or usage.get("name")
            )

            usage_parameter = get_number(
                usage.get("times")
                or usage.get("count")
                or usage.get("parameter")
            )

        cursor.execute("""
            SELECT id
            FROM monster_actions
            WHERE monster_id = ?
            AND name = ?
            AND order_in_statblock = ?
        """, (
            monster_id,
            name,
            order
        ))

        existing = cursor.fetchone()

        if existing is not None:
            action_id = existing[0]

        else:

            cursor.execute("""
                INSERT INTO monster_actions (
                    monster_id,
                    name,
                    description,
                    action_type,
                    order_in_statblock,
                    legendary_action_cost,
                    limited_to_form,
                    usage_type,
                    usage_parameter
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                monster_id,
                name,
                description,
                action_type,
                order,
                action.get("legendary_action_cost"),
                action.get("limited_to_form"),
                usage_type,
                usage_parameter
            ))

            action_id = cursor.lastrowid

        insert_attacks(
            cursor,
            action_id,
            action
        )


# ---------------------------------------------------------------------------
# Attacks
# ---------------------------------------------------------------------------

def parse_damage(damage):

    if not damage:
        return None, None, None, None

    if isinstance(damage, list):
        if not damage:
            return None, None, None, None

        damage = damage[0]

    if not isinstance(damage, dict):
        return None, None, None, None

    damage_type = get_name(
        damage.get("damage_type")
        or damage.get("type")
    )

    damage_dice = (
        damage.get("damage_dice")
        or damage.get("dice")
        or damage.get("damage")
    )

    damage_die_count = None
    damage_die_type = None
    damage_bonus = None

    if isinstance(damage_dice, str):

        match = re.search(
            r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?",
            damage_dice
        )

        if match:

            damage_die_count = int(match.group(1))
            damage_die_type = f"d{match.group(2)}"

            if match.group(3):
                bonus = int(match.group(4))

                if match.group(3) == "-":
                    bonus *= -1

                damage_bonus = bonus

    return (
        damage_die_count,
        damage_die_type,
        damage_bonus,
        damage_type
    )


def insert_attacks(cursor, action_id, action):

    attacks = []

    if action.get("attack") is not None:
        attacks.append(action["attack"])

    if action.get("attacks") is not None:

        if isinstance(action["attacks"], list):
            attacks.extend(action["attacks"])

        else:
            attacks.append(action["attacks"])

    if not attacks:
        return

    for attack in attacks:

        if not isinstance(attack, dict):
            continue

        name = (
            attack.get("name")
            or action.get("name")
        )

        attack_type = (
            attack.get("type")
            or attack.get("attack_type")
        )

        to_hit = (
            attack.get("to_hit")
            or attack.get("attack_bonus")
            or attack.get("bonus")
        )

        to_hit = get_number(to_hit)

        reach = get_number(
            attack.get("reach")
        )

        range_value = get_number(
            attack.get("range")
        )

        long_range = get_number(
            attack.get("long_range")
            or attack.get("long_range_value")
        )

        target_creature_only = attack.get(
            "target_creature_only"
        )

        (
            damage_die_count,
            damage_die_type,
            damage_bonus,
            damage_type
        ) = parse_damage(
            attack.get("damage")
        )

        cursor.execute("""
            SELECT id
            FROM attacks
            WHERE action_id = ?
            AND name = ?
        """, (
            action_id,
            name
        ))

        existing = cursor.fetchone()

        if existing is not None:
            continue

        cursor.execute("""
            INSERT INTO attacks (
                action_id,
                name,
                attack_type,
                to_hit_modifier,
                reach,
                range,
                long_range,
                target_creature_only,
                damage_die_count,
                damage_die_type,
                damage_bonus,
                damage_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            action_id,
            name,
            attack_type,
            to_hit,
            reach,
            range_value,
            long_range,
            target_creature_only,
            damage_die_count,
            damage_die_type,
            damage_bonus,
            damage_type
        ))


# ---------------------------------------------------------------------------
# Traits
# ---------------------------------------------------------------------------

def insert_traits(cursor, monster_id, creature):

    traits = creature.get("traits") or []

    for trait in traits:

        if not isinstance(trait, dict):
            continue

        name = trait.get("name")

        if not name:
            continue

        description = (
            trait.get("desc")
            or trait.get("description")
            or trait.get("text")
        )

        cursor.execute("""
            SELECT id
            FROM monster_traits
            WHERE monster_id = ?
            AND name = ?
        """, (
            monster_id,
            name
        ))

        if cursor.fetchone() is not None:
            continue

        cursor.execute("""
            INSERT INTO monster_traits (
                monster_id,
                name,
                description
            )
            VALUES (?, ?, ?)
        """, (
            monster_id,
            name,
            description
        ))


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

def get_or_create_environment(cursor, environment):

    environment_name = get_text(environment)

    if not environment_name:
        return None

    cursor.execute("""
        SELECT id
        FROM environments
        WHERE name = ?
    """, (
        environment_name,
    ))

    existing = cursor.fetchone()

    if existing is not None:
        return existing[0]

    cursor.execute("""
        INSERT INTO environments (
            name
        )
        VALUES (?)
    """, (
        environment_name,
    ))

    return cursor.lastrowid


def insert_environments(cursor, monster_id, creature):

    environments = creature.get("environments") or []

    if isinstance(environments, str):
        environments = [environments]

    for environment in environments:

        environment_id = get_or_create_environment(
            cursor,
            environment
        )

        if environment_id is None:
            continue

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


# ---------------------------------------------------------------------------
# Import a single creature
# ---------------------------------------------------------------------------

def import_creature(cursor, creature):

    source_id = get_or_create_source(
        cursor,
        creature["document"]
    )

    monster_id = get_or_create_monster(
        cursor,
        creature,
        source_id
    )

    insert_ability_scores(
        cursor,
        monster_id,
        creature
    )

    insert_modifiers(
        cursor,
        monster_id,
        creature
    )

    insert_speeds(
        cursor,
        monster_id,
        creature
    )

    insert_languages(
        cursor,
        monster_id,
        creature
    )

    insert_saving_throws(
        cursor,
        monster_id,
        creature
    )

    insert_skills(
        cursor,
        monster_id,
        creature
    )

    insert_defenses(
        cursor,
        monster_id,
        creature
    )

    insert_actions(
        cursor,
        monster_id,
        creature
    )

    insert_traits(
        cursor,
        monster_id,
        creature
    )

    insert_environments(
        cursor,
        monster_id,
        creature
    )


# ---------------------------------------------------------------------------
# Main importer
# ---------------------------------------------------------------------------

def main():

    connection = sqlite3.connect(
        "db/encounter_forge.db"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    cursor = connection.cursor()

    current_url = API_URL

    try:

        while current_url is not None:

            print(
                f"Processing: {current_url}"
            )

            if current_url == API_URL:

                response = requests.get(
                    current_url,
                    params=VERSION_FILTER
                )

            else:

                response = requests.get(
                    current_url
                )

            response.raise_for_status()

            data = response.json()

            for creature in data["results"]:

                import_creature(
                    cursor,
                    creature
                )

            current_url = data["next"]

        connection.commit()

        print("Import complete.")

    except Exception:

        connection.rollback()

        print(
            "Import failed. Database changes rolled back."
        )

        raise

    finally:

        connection.close()


if __name__ == "__main__":
    main()