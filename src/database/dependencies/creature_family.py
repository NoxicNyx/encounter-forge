"""Explicit, conservative creature-family assignments for edition bridging.

The families below are creature baselines, not broad D&D creature tags.  In
particular, the published goblinoid umbrella is intentionally *not* used as a
family: Goblins, Hobgoblins, and Bugbears have different creature entries and
must not inherit each other's tactics or habitats merely because they share a
tag or language.
"""

from __future__ import annotations

import re
import sqlite3


OFFICIAL_REFERENCE = (
    "D&D Basic Rules (2014) and D&D Free Rules (2024) creature stat blocks"
)

# Ordered longest/specific names first.  This list is intentionally
# conservative: any name not listed remains its own exact-name family rather
# than being guessed from a shared word.
CURATED_BASELINES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("hob", "goblin"), "hobgoblin", "Hobgoblin"),
    (("hobgoblin",), "hobgoblin", "Hobgoblin"),
    (("yuan", "ti"), "yuan-ti", "Yuan-ti"),
    (("githyanki",), "githyanki", "Githyanki"),
    (("githzerai",), "githzerai", "Githzerai"),
    (("lizardfolk",), "lizardfolk", "Lizardfolk"),
    (("sahuagin",), "sahuagin", "Sahuagin"),
    (("warrior", "veteran"), "veteran", "Veteran"),
    (("veteran",), "veteran", "Veteran"),
    (("duergar",), "duergar", "Duergar"),
    (("bugbear",), "bugbear", "Bugbear"),
    (("goblin",), "goblin", "Goblin"),
    (("kobold",), "kobold", "Kobold"),
    (("gnoll",), "gnoll", "Gnoll"),
    (("orc",), "orc", "Orc"),
    (("drow",), "drow", "Drow"),
    (("ogre",), "ogre", "Ogre"),
    (("troll",), "troll", "Troll"),
)


def tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def slugify(value: str) -> str:
    return "-".join(tokens(value))


def family_identity(name: str) -> tuple[str, str, str]:
    """Return key, display name, and evidence method for a creature name."""
    name_tokens = tokens(name)
    for baseline_tokens, key, display_name in CURATED_BASELINES:
        if name_tokens[: len(baseline_tokens)] == baseline_tokens:
            return key, display_name, "curated_baseline"
    # A safe fallback: distinct source names cannot be merged accidentally.
    key = slugify(name) or "unnamed-creature"
    return key, name.strip() or "Unnamed creature", "exact_name"


def _family_id(cursor: sqlite3.Cursor, identity: tuple[str, str, str]) -> int:
    key, display_name, method = identity
    cursor.execute(
        """
        INSERT INTO creature_families (
            family_key, name, taxonomy_basis, source_reference, notes
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(family_key) DO UPDATE SET
            name = excluded.name,
            taxonomy_basis = excluded.taxonomy_basis,
            source_reference = excluded.source_reference,
            notes = excluded.notes
        """,
        (
            key,
            display_name,
            method,
            OFFICIAL_REFERENCE,
            (
                "Curated baseline used to bridge role variants across 2014 and 2024."
                if method == "curated_baseline"
                else "No safe family bridge is known; this source name is kept distinct."
            ),
        ),
    )
    return cursor.execute(
        "SELECT id FROM creature_families WHERE family_key = ?", (key,)
    ).fetchone()[0]


def populate_monster_families(cursor: sqlite3.Cursor) -> int:
    """Assign every current Open5e monster to exactly one explicit family."""
    count = 0
    for monster_id, name in cursor.execute("SELECT id, name FROM monsters").fetchall():
        identity = family_identity(name)
        cursor.execute(
            """
            INSERT INTO monster_creature_families (
                monster_id, creature_family_id, assignment_method
            ) VALUES (?, ?, ?)
            ON CONFLICT(monster_id) DO UPDATE SET
                creature_family_id = excluded.creature_family_id,
                assignment_method = excluded.assignment_method
            """,
            (monster_id, _family_id(cursor, identity), identity[2]),
        )
        count += 1
    return count


def assign_profile_family(cursor: sqlite3.Cursor, profile_id: int, source_name: str) -> int:
    """Record the source creature's family alongside its tactical profile."""
    identity = family_identity(source_name)
    cursor.execute(
        """
        INSERT INTO tactical_profile_creature_families (
            tactical_profile_id, creature_family_id, assignment_method
        ) VALUES (?, ?, ?)
        ON CONFLICT(tactical_profile_id) DO UPDATE SET
            creature_family_id = excluded.creature_family_id,
            assignment_method = excluded.assignment_method
        """,
        (profile_id, _family_id(cursor, identity), identity[2]),
    )
    return identity[0]


def migrate_profile_link_constraint(connection: sqlite3.Connection) -> None:
    """Upgrade old link constraints without discarding existing profile links."""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tactical_profile_monster_links'"
    ).fetchone()
    if not row or all(
        match_type in (row[0] or "")
        for match_type in ("'name_alias'", "'curated_mapping'")
    ):
        return
    connection.executescript(
        """
        ALTER TABLE tactical_profile_monster_links RENAME TO tactical_profile_monster_links_legacy;
        CREATE TABLE tactical_profile_monster_links (
            tactical_profile_id INTEGER NOT NULL,
            monster_id INTEGER NOT NULL,
            match_type TEXT NOT NULL,
            PRIMARY KEY (tactical_profile_id, monster_id),
            FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
            FOREIGN KEY (monster_id) REFERENCES monsters(id),
            CHECK (match_type IN ('exact', 'family', 'official_conversion', 'name_alias', 'curated_mapping'))
        );
        INSERT INTO tactical_profile_monster_links (tactical_profile_id, monster_id, match_type)
        SELECT tactical_profile_id, monster_id,
               CASE WHEN match_type = 'substring' THEN 'family' ELSE match_type END
        FROM tactical_profile_monster_links_legacy;
        DROP TABLE tactical_profile_monster_links_legacy;
        """
    )
