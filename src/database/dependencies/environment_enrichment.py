"""Bridge SRD 2014 habitats to SRD 2024 creatures by explicit family."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from creature_family import family_identity, populate_monster_families
from official_conversions import alias_targets_for, target_for


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "db" / "encounter_forge.db"
API_URL = "https://api.open5e.com/v2/creatures/"
VERSION_FILTER = {"document__key__in": "srd-2014"}


def fetch_json(request_url: str) -> dict:
    request = Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": "Encounter-Forge/0.1"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def load_2014_environments() -> dict[str, set[str]]:
    """Return habitats grouped under the same family bridge as the 2024 data."""
    by_family: dict[str, set[str]] = defaultdict(set)
    current_url: str | None = f"{API_URL}?{urlencode(VERSION_FILTER)}"
    while current_url is not None:
        data = fetch_json(current_url)
        for creature in data["results"]:
            name = creature.get("name")
            if not name:
                continue
            environments = {
                environment["name"]
                for environment in (creature.get("environments") or [])
                if environment.get("name")
            }
            by_family[family_identity(name)[0]].update(environments)
            # Official replacements may not share a creature family (for
            # example Orc -> Tough), so preserve their habitats separately.
            if target := target_for(name):
                by_family[f"official:{target.casefold()}"].update(environments)
            for target in alias_targets_for(name):
                by_family[f"official:{target.casefold()}"].update(environments)
        current_url = data.get("next")
    return by_family


def enrich_environments(
    database: Path = DEFAULT_DB_PATH,
    source_environments: dict[str, set[str]] | None = None,
) -> dict[str, int]:
    """Persist family-backed habitat links and return an auditable summary."""
    if source_environments is None:
        source_environments = load_2014_environments()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        cursor = connection.cursor()
        populate_monster_families(cursor)
        # These links are entirely derived from the 2014 source. Rebuild them
        # so an old broad-name match cannot survive the family migration.
        cursor.execute("DELETE FROM monster_environments")
        monsters = cursor.execute(
            """
            SELECT monsters.id, monsters.name, creature_families.family_key
            FROM monsters
            JOIN monster_creature_families
              ON monster_creature_families.monster_id = monsters.id
            JOIN creature_families
              ON creature_families.id = monster_creature_families.creature_family_id
            """
        ).fetchall()
        matched = links = 0
        for monster_id, monster_name, family_key in monsters:
            environments = source_environments.get(
                f"official:{monster_name.casefold()}",
                source_environments.get(family_key),
            )
            if not environments:
                continue
            matched += 1
            for environment_name in environments:
                cursor.execute(
                    "INSERT OR IGNORE INTO environments (name) VALUES (?)", (environment_name,)
                )
                environment_id = cursor.execute(
                    "SELECT id FROM environments WHERE name = ?", (environment_name,)
                ).fetchone()[0]
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO monster_environments (
                        monster_id, environment_id, affinity
                    ) VALUES (?, ?, NULL)
                    """,
                    (monster_id, environment_id),
                )
                links += 1
        connection.commit()
        return {
            "source_families": len(source_environments),
            "matched_monsters": matched,
            "family_matched_monsters": matched,
            "environment_links": links,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge 2014 habitats through creature families.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    summary = enrich_environments(args.database)
    print("Environment enrichment complete.")
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
