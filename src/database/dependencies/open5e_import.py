"""Synchronise the SRD 2024 Open5e creature catalogue into SQLite."""

from __future__ import annotations

import json
import re
import sqlite3
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
DB_PATH = ROOT_DIR / "db" / "encounter_forge.db"
SCHEMA_PATH = ROOT_DIR / "db" / "schema.sql"
API_URL = "https://api.open5e.com/v2/creatures/"
VERSION_FILTER = {"document__key__in": "srd-2024"}


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Encounter-Forge/0.1"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def name_of(value: Any) -> str | None:
    return value.get("name") if isinstance(value, dict) else value if isinstance(value, str) else None


def number_of(value: Any) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and (match := re.search(r"-?\d+(?:\.\d+)?", value)):
        number = float(match.group())
        return int(number) if number.is_integer() else number
    return None


def values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value] if value is not None else []


def key_for(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def source_id(cursor: sqlite3.Cursor, document: dict[str, Any]) -> int:
    publisher = document.get("publisher") or {}
    game_system = document.get("gamesystem") or {}
    cursor.execute(
        """INSERT INTO sources (source_key, name, display_name, publisher, game_system, permalink)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET name=excluded.name, display_name=excluded.display_name,
        publisher=excluded.publisher, game_system=excluded.game_system, permalink=excluded.permalink""",
        (document["key"], document.get("name") or document["key"], document.get("display_name"),
         publisher.get("name"), game_system.get("name"), document.get("permalink")),
    )
    return cursor.execute("SELECT id FROM sources WHERE source_key=?", (document["key"],)).fetchone()[0]


def monster_id(cursor: sqlite3.Cursor, creature: dict[str, Any], document_id: int) -> int:
    fields = (
        "source_id, creature_key, name, creature_type, size, category, subcategory, alignment, "
        "challenge_rating, proficiency_bonus, armour_class, armour_detail, hit_points, hit_dice, "
        "experience_points, initiative_bonus, passive_perception, normal_sight_range, darkvision_range, "
        "blindsight_range, tremorsense_range, truesight_range"
    )
    record = (
        document_id, creature["key"], creature["name"], name_of(creature.get("type")),
        name_of(creature.get("size")), creature.get("category"), creature.get("subcategory"),
        creature.get("alignment"), creature.get("challenge_rating"), creature.get("proficiency_bonus"),
        creature.get("armor_class"), creature.get("armor_detail"), creature.get("hit_points"),
        creature.get("hit_dice"), creature.get("experience_points"), creature.get("initiative_bonus"),
        creature.get("passive_perception"), creature.get("normal_sight_range"), creature.get("darkvision_range"),
        creature.get("blindsight_range"), creature.get("tremorsense_range"), creature.get("truesight_range"),
    )
    cursor.execute(
        f"INSERT INTO monsters ({fields}) VALUES ({','.join('?' for _ in record)}) "
        "ON CONFLICT(creature_key) DO UPDATE SET " + ", ".join(
            f"{field}=excluded.{field}" for field in fields.split(", ") if field != "creature_key"
        ),
        record,
    )
    return cursor.execute("SELECT id FROM monsters WHERE creature_key=?", (creature["key"],)).fetchone()[0]


def clear_imported_children(cursor: sqlite3.Cursor, monster: int) -> None:
    cursor.execute("DELETE FROM attack_damage_components WHERE attack_id IN (SELECT attacks.id FROM attacks JOIN monster_actions ON attacks.action_id=monster_actions.id WHERE monster_actions.monster_id=?)", (monster,))
    cursor.execute("DELETE FROM attacks WHERE action_id IN (SELECT id FROM monster_actions WHERE monster_id=?)", (monster,))
    for table in (
        "monster_actions", "monster_ability_scores", "monster_modifiers", "monster_speeds",
        "monster_languages", "monster_communication_notes", "monster_saving_throws", "monster_skills",
        "monster_defenses", "monster_condition_immunities", "monster_traits", "monster_cross_references",
        "monster_illustrations",
    ):
        cursor.execute(f"DELETE FROM {table} WHERE monster_id=?", (monster,))


def insert_scores(cursor: sqlite3.Cursor, table: str, monster: int, scores: dict[str, Any]) -> None:
    labels = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
    cursor.execute(
        f"INSERT INTO {table} (monster_id, {', '.join(labels)}) VALUES (?, {', '.join('?' for _ in labels)})",
        (monster, *(scores.get(label) for label in labels)),
    )


def insert_speeds(cursor: sqlite3.Cursor, monster: int, creature: dict[str, Any]) -> None:
    speed = creature.get("speed_all") or creature.get("speed") or {}
    labels = ("walk", "crawl", "fly", "burrow", "climb", "swim")
    cursor.execute(
        "INSERT INTO monster_speeds (monster_id, walk, crawl, fly, burrow, climb, swim, hover, unit) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (monster, *(number_of(speed.get(label)) for label in labels), speed.get("hover"), speed.get("unit") or "feet"),
    )


def insert_languages(cursor: sqlite3.Cursor, monster: int, creature: dict[str, Any]) -> None:
    source = creature.get("languages") or {}
    language_text = source.get("as_string") if isinstance(source, dict) else str(source) if source else None
    if language_text:
        cursor.execute("INSERT INTO monster_communication_notes (monster_id, languages_text) VALUES (?, ?)", (monster, language_text))
    for language in source.get("data", []) if isinstance(source, dict) else []:
        if not isinstance(language, dict) or not language.get("name"):
            continue
        language_key = language.get("key") or key_for(language["name"])
        cursor.execute(
            """INSERT INTO languages (language_key, name, description) VALUES (?, ?, ?)
            ON CONFLICT(language_key) DO UPDATE SET name=excluded.name, description=excluded.description""",
            (language_key, language["name"], language.get("desc")),
        )
        language_id = cursor.execute("SELECT id FROM languages WHERE language_key=?", (language_key,)).fetchone()[0]
        cursor.execute("INSERT INTO monster_languages (monster_id, language_id) VALUES (?, ?)", (monster, language_id))


def insert_modifiers(cursor: sqlite3.Cursor, table: str, label: str, monster: int, entries: dict[str, Any]) -> None:
    for entry_name, modifier in entries.items():
        if (number := number_of(modifier)) is not None:
            cursor.execute(f"INSERT INTO {table} (monster_id, {label}, modifier) VALUES (?, ?, ?)", (monster, entry_name, number))


def insert_defenses(cursor: sqlite3.Cursor, monster: int, creature: dict[str, Any]) -> None:
    data = creature.get("resistances_and_immunities") or {}
    for kind, field in (("resistance", "damage_resistances"), ("immunity", "damage_immunities"), ("vulnerability", "damage_vulnerabilities")):
        for entry in values(data.get(field)):
            damage = name_of(entry) if isinstance(entry, dict) else str(entry)
            if damage:
                cursor.execute("INSERT INTO monster_defenses (monster_id, defense_type, damage_type) VALUES (?, ?, ?)", (monster, kind, damage))
    for entry in values(data.get("condition_immunities")):
        condition = name_of(entry) if isinstance(entry, dict) else str(entry)
        if condition:
            cursor.execute("INSERT INTO monster_condition_immunities (monster_id, condition_name) VALUES (?, ?)", (monster, condition))


def attack_components(attack: dict[str, Any]) -> list[tuple[Any, Any, Any, Any]]:
    primary = (number_of(attack.get("damage_die_count")), attack.get("damage_die_type"), number_of(attack.get("damage_bonus")), name_of(attack.get("damage_type")))
    extra = (number_of(attack.get("extra_damage_die_count")), attack.get("extra_damage_die_type"), number_of(attack.get("extra_damage_bonus")), name_of(attack.get("extra_damage_type")))
    if any(part is not None for part in primary[:3]):
        if primary[3] is None and extra[:3] == (None, None, None):
            primary = (*primary[:3], extra[3])
            extra = (None, None, None, None)
        return [primary] + ([extra] if any(part is not None for part in extra) else [])
    return [extra] if any(part is not None for part in extra) else []


def insert_actions(cursor: sqlite3.Cursor, monster: int, creature: dict[str, Any]) -> None:
    for fallback_order, action in enumerate(creature.get("actions") or [], start=1):
        if not isinstance(action, dict) or not action.get("name"):
            continue
        limit = action.get("usage_limits") or action.get("usage") or {}
        cursor.execute(
            """INSERT INTO monster_actions (monster_id, name, description, action_type, order_in_statblock,
            legendary_action_cost, limited_to_form, usage_type, usage_parameter) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (monster, action["name"], action.get("desc") or action.get("description"), action.get("action_type") or action.get("type"),
             action.get("order_in_statblock", fallback_order), action.get("legendary_action_cost"), action.get("limited_to_form"),
             limit.get("type") if isinstance(limit, dict) else None,
             number_of(limit.get("param") or limit.get("times") or limit.get("count")) if isinstance(limit, dict) else None),
        )
        action_id = cursor.lastrowid
        for attack in values(action.get("attacks") or action.get("attack")):
            if not isinstance(attack, dict):
                continue
            components = attack_components(attack)
            component = components[0] if components else (None, None, None, None)
            cursor.execute(
                """INSERT INTO attacks (action_id, name, attack_type, to_hit_modifier, reach, range, long_range,
                target_creature_only, damage_die_count, damage_die_type, damage_bonus, damage_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (action_id, attack.get("name") or action["name"], attack.get("attack_type") or attack.get("type"),
                 number_of(attack.get("to_hit_mod") or attack.get("to_hit") or attack.get("attack_bonus")),
                 number_of(attack.get("reach")), number_of(attack.get("range")), number_of(attack.get("long_range")),
                 attack.get("target_creature_only"), *component),
            )
            attack_id = cursor.lastrowid
            cursor.executemany(
                """INSERT INTO attack_damage_components (attack_id, component_order, damage_die_count, damage_die_type, damage_bonus, damage_type)
                VALUES (?, ?, ?, ?, ?, ?)""",
                [(attack_id, order, *part) for order, part in enumerate(components, start=1)],
            )


def insert_other_fields(cursor: sqlite3.Cursor, monster: int, creature: dict[str, Any]) -> None:
    for trait in creature.get("traits") or []:
        if isinstance(trait, dict) and trait.get("name"):
            cursor.execute("INSERT INTO monster_traits (monster_id, name, description) VALUES (?, ?, ?)", (monster, trait["name"], trait.get("desc") or trait.get("description")))
    for environment in values(creature.get("environments")):
        environment_name = name_of(environment) if isinstance(environment, dict) else environment
        if not environment_name:
            continue
        cursor.execute("INSERT OR IGNORE INTO environments (name) VALUES (?)", (environment_name,))
        environment_id = cursor.execute("SELECT id FROM environments WHERE name=?", (environment_name,)).fetchone()[0]
        cursor.execute("INSERT OR IGNORE INTO monster_environments (monster_id, environment_id, affinity) VALUES (?, ?, NULL)", (monster, environment_id))
    for reference in (creature.get("crossreferences") or {}).get("to") or []:
        if isinstance(reference, dict):
            target, kind = reference.get("key") or reference.get("name"), reference.get("type") or "cross_reference"
        else:
            target, kind = str(reference), "cross_reference"
        if target:
            cursor.execute("INSERT OR IGNORE INTO monster_cross_references (monster_id, target_key, relationship_type) VALUES (?, ?, ?)", (monster, target, kind))
    image = creature.get("illustration")
    if isinstance(image, dict):
        image = image.get("url") or image.get("image_url")
    if image:
        cursor.execute("INSERT INTO monster_illustrations (monster_id, image_url) VALUES (?, ?)", (monster, str(image)))


def import_creature(cursor: sqlite3.Cursor, creature: dict[str, Any]) -> None:
    monster = monster_id(cursor, creature, source_id(cursor, creature["document"]))
    clear_imported_children(cursor, monster)
    insert_scores(cursor, "monster_ability_scores", monster, creature.get("ability_scores") or {})
    insert_scores(cursor, "monster_modifiers", monster, creature.get("modifiers") or {})
    insert_speeds(cursor, monster, creature)
    insert_languages(cursor, monster, creature)
    insert_modifiers(cursor, "monster_saving_throws", "ability", monster, creature.get("saving_throws") or {})
    insert_modifiers(cursor, "monster_skills", "skill", monster, creature.get("skill_bonuses") or {})
    insert_defenses(cursor, monster, creature)
    insert_actions(cursor, monster, creature)
    insert_other_fields(cursor, monster, creature)


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        cursor = connection.cursor()
        url: str | None = f"{API_URL}?{urlencode(VERSION_FILTER)}"
        imported = 0
        while url:
            payload = fetch_json(url)
            for creature in payload["results"]:
                import_creature(cursor, creature)
                imported += 1
            url = payload.get("next")
        connection.commit()
        print(f"Open5e import complete: {imported} SRD 2024 creatures.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
