"""Import direct creature relationships stated in official 2014 rules text."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "db" / "encounter_forge.db"
SOURCE_KEY = "dnd-basic-rules-2014-creature-relationships"
SOURCE_URL = "https://www.dndbeyond.com/sources/dnd/basic-rules-2014/monsters"

# (profile source name, related profile source name, forward label, reverse label)
# The Bandit entry says bands are sometimes led by veterans; the Bandit Captain
# entry describes keeping a gang of bandits in line.
RELATIONSHIPS = (
    ("Bandit", "Veteran", "Sometimes led by a veteran", "May lead bandits"),
    ("Bandit", "Bandit captain", "Led by a bandit captain", "Leads a bandit gang"),
)


def _profile_monsters(cursor: sqlite3.Cursor, source_name: str) -> list[int]:
    return [
        row[0]
        for row in cursor.execute(
            """
            SELECT links.monster_id
            FROM tactical_profiles profiles
            JOIN tactical_profile_monster_links links
              ON links.tactical_profile_id = profiles.id
            WHERE lower(profiles.source_name) = lower(?)
            """,
            (source_name,),
        )
    ]


def enrich_official_relationships(database: Path = DEFAULT_DB_PATH) -> int:
    """Persist sourced Bandit leadership relationships without inference."""
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO tactical_sources (source_key, name, version, source_reference)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                name = excluded.name,
                version = excluded.version,
                source_reference = excluded.source_reference
            """,
            (SOURCE_KEY, "D&D Basic Rules", "2014", SOURCE_URL),
        )
        source_id = cursor.execute(
            "SELECT id FROM tactical_sources WHERE source_key = ?", (SOURCE_KEY,)
        ).fetchone()[0]
        linked = 0
        for first_name, second_name, forward, reverse in RELATIONSHIPS:
            first_ids = _profile_monsters(cursor, first_name)
            second_ids = _profile_monsters(cursor, second_name)
            for first_id in first_ids:
                for second_id in second_ids:
                    if first_id == second_id:
                        continue
                    for monster_id, related_id, label in (
                        (first_id, second_id, forward),
                        (second_id, first_id, reverse),
                    ):
                        cursor.execute(
                            """
                            INSERT INTO monster_relationships (
                                monster_id, related_monster_id, relationship_type, affinity
                            ) VALUES (?, ?, ?, 1.0)
                            ON CONFLICT(monster_id, related_monster_id) DO UPDATE SET
                                relationship_type = excluded.relationship_type,
                                affinity = excluded.affinity
                            """,
                            (monster_id, related_id, label),
                        )
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO monster_relationship_tactical_sources (
                                monster_id, related_monster_id, tactical_source_id
                            ) VALUES (?, ?, ?)
                            """,
                            (monster_id, related_id, source_id),
                        )
                        linked += 1
        connection.commit()
        return linked
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    print(f"Official relationship links: {enrich_official_relationships()}")
