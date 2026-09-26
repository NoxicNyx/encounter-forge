"""Research-backed tactical-profile bridges for 2024 SRD stat blocks.

These records are intentionally separate from official edition conversions,
aliases, and creature families. They preserve why a broader tactical profile is
appropriate for a particular 2024 creature without pretending the two are the
same stat block.
"""

from __future__ import annotations

import sqlite3


USER_MAPPING_REFERENCE = "User-approved mapping supplied 2026-09-26"
BOOK_TITLE = "The Monsters Know What They're Doing"


def dragon_creature_keys(colours: tuple[str, ...]) -> tuple[str, ...]:
    """Return the four 2024 age bands for each named true-dragon colour."""
    keys = []
    for colour in colours:
        colour_key = colour.casefold()
        keys.extend(
            (
                f"srd-2024_adult-{colour_key}-dragon",
                f"srd-2024_ancient-{colour_key}-dragon",
                f"srd-2024_{colour_key}-dragon-wyrmling",
                f"srd-2024_young-{colour_key}-dragon",
            )
        )
    return tuple(keys)


CURATED_MAPPINGS = (
    (
        "Crawling claw",
        "srd-2024_swarm-of-crawling-claws",
        f"{USER_MAPPING_REFERENCE}; {BOOK_TITLE}, PDF p. 311 (Crawling Claws)",
    ),
    (
        "Doppelgänger",
        "srd-2024_doppelganger",
        f"{USER_MAPPING_REFERENCE}; {BOOK_TITLE}, PDF pp. 176-178 (Doppelgangers)",
    ),
    (
        "Efreet",
        "srd-2024_efreeti",
        f"{USER_MAPPING_REFERENCE}; {BOOK_TITLE}, PDF pp. 471-472 (Efreets)",
    ),
    (
        "Goblin",
        "srd-2024_goblin-minion",
        f"{USER_MAPPING_REFERENCE}; {BOOK_TITLE}, PDF pp. 23-27 (Goblinoids)",
    ),
    *(
        (
            "Chromatic",
            creature_key,
            f"{BOOK_TITLE}, PDF pp. 224-230 (Chromatic Dragons; wyrmling through ancient tactics)",
        )
        for creature_key in dragon_creature_keys(("Black", "Blue", "Green", "Red", "White"))
    ),
    *(
        (
            "Metallic",
            creature_key,
            f"{BOOK_TITLE}, PDF pp. 230-233 (Metallic Dragons; wyrmling through ancient tactics)",
        )
        for creature_key in dragon_creature_keys(("Brass", "Bronze", "Copper", "Gold", "Silver"))
    ),
)


def populate_curated_profile_mappings(cursor: sqlite3.Cursor) -> None:
    """Store curated records without changing user-authored database records."""
    # A short-lived pre-release build used a hyphen after ``srd-2024`` rather
    # than the catalogue's underscore. Those keys can never resolve to a 2024
    # creature, so remove only that invalid legacy shape before seeding.
    cursor.execute(
        "DELETE FROM curated_profile_monster_mappings WHERE creature_key GLOB 'srd-2024-*'"
    )
    cursor.executemany(
        """
        INSERT INTO curated_profile_monster_mappings (
            source_name, creature_key, source_reference
        ) VALUES (?, ?, ?)
        ON CONFLICT(source_name, creature_key) DO UPDATE SET
            source_reference = excluded.source_reference
        """,
        CURATED_MAPPINGS,
    )


def apply_curated_profile_links(cursor: sqlite3.Cursor) -> int:
    """Link known profiles to the exact catalogued 2024 creatures they cover."""
    cursor.execute(
        """
        INSERT OR IGNORE INTO tactical_profile_monster_links (
            tactical_profile_id, monster_id, match_type
        )
        SELECT profiles.id, monsters.id, 'curated_mapping'
        FROM curated_profile_monster_mappings mappings
        JOIN tactical_profiles profiles
          ON lower(profiles.source_name) = lower(mappings.source_name)
        JOIN monsters ON monsters.creature_key = mappings.creature_key
        """
    )
    return cursor.rowcount
