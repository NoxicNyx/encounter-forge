"""Import the book-anchored tactical workbook into Encounter Forge's SQLite DB.

The importer preserves every profile in the workbook. A profile is linked to an
Open5e monster only when its source name has an unambiguous case-insensitive
match, so source data is never discarded merely because a stat-block name has
changed between rules revisions.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "db" / "encounter_forge.db"
DEFAULT_SCHEMA_PATH = ROOT_DIR / "db" / "schema.sql"
SOURCE_KEY = "monsters-know-what-theyre-doing-v0-3"

PROFILE_SCORE_COLUMNS = [
    "Aggression",
    "Risk Tolerance",
    "Discipline",
    "Coordination",
    "Leadership",
    "Morale",
    "Mobility",
    "Stealth",
    "Ambush",
    "Focus Fire",
    "Positional Behaviour",
    "Terrain Dependence",
    "Cover Dependence",
    "Group Dependence",
    "Sociality",
    "Intelligence",
    "Retreat Tendency",
]

TAG_COLUMNS = {
    "Engagement Range": "engagement_range",
    "Engagement Style": "engagement_style",
    "Target Preferences": "target_preference",
    "Special Behaviours": "special_behaviour",
}


def slugify(value: str) -> str:
    """Return a stable key for a workbook label."""
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def split_values(value: Any) -> list[str]:
    """Split the workbook's comma-separated labels, ignoring blank cells."""
    if value is None:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def workbook_rows(workbook, sheet_name: str) -> Iterable[dict[str, Any]]:
    """Yield non-empty worksheet rows keyed by the header row."""
    worksheet = workbook[sheet_name]
    rows = worksheet.iter_rows(values_only=True)
    headers = next(rows)
    for row in rows:
        if not any(value is not None and value != "" for value in row):
            continue
        yield dict(zip(headers, row))


def ensure_schema(connection: sqlite3.Connection, schema_path: Path) -> None:
    connection.executescript(schema_path.read_text(encoding="utf-8"))


def clear_tactical_data(cursor: sqlite3.Cursor) -> None:
    """Replace imported workbook data without touching Open5e source records."""
    cursor.execute(
        """
        DELETE FROM monster_relationships
        WHERE EXISTS (
            SELECT 1
            FROM monster_relationship_tactical_sources provenance
            WHERE provenance.monster_id = monster_relationships.monster_id
              AND provenance.related_monster_id = monster_relationships.related_monster_id
        )
        """
    )
    cursor.execute("DELETE FROM monster_relationship_tactical_sources")
    tables = [
        "tactical_pairwise_compatibility",
        "tactical_pairwise_affinities",
        "tactical_profile_evidence",
        "tactical_profile_environment_fits",
        "tactical_profile_tags",
        "tactical_profile_roles",
        "tactical_profile_scores",
        "tactical_profile_monster_links",
        "tactical_tags",
        "tactical_tag_categories",
        "tactical_roles",
        "tactical_dimensions",
        "tactical_profiles",
        "tactical_sources",
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")


def get_or_create_environment(cursor: sqlite3.Cursor, name: str) -> int:
    cursor.execute(
        "SELECT id FROM environments WHERE lower(name) = lower(?)", (name,)
    )
    existing = cursor.fetchone()
    if existing:
        return existing[0]

    cursor.execute("INSERT INTO environments (name) VALUES (?)", (name,))
    return cursor.lastrowid


def get_or_create_role(cursor: sqlite3.Cursor, name: str) -> int:
    key = slugify(name)
    cursor.execute(
        "INSERT INTO tactical_roles (role_key, name) VALUES (?, ?) "
        "ON CONFLICT(role_key) DO UPDATE SET name = excluded.name",
        (key, name),
    )
    return cursor.execute(
        "SELECT id FROM tactical_roles WHERE role_key = ?", (key,)
    ).fetchone()[0]


def get_or_create_tag(cursor: sqlite3.Cursor, category_key: str, name: str) -> int:
    cursor.execute(
        "INSERT INTO tactical_tag_categories (category_key, name) VALUES (?, ?) "
        "ON CONFLICT(category_key) DO UPDATE SET name = excluded.name",
        (category_key, category_key.replace("_", " ").title()),
    )
    category_id = cursor.execute(
        "SELECT id FROM tactical_tag_categories WHERE category_key = ?",
        (category_key,),
    ).fetchone()[0]
    tag_key = slugify(name)
    cursor.execute(
        "INSERT INTO tactical_tags (tactical_tag_category_id, tag_key, name) "
        "VALUES (?, ?, ?) ON CONFLICT(tactical_tag_category_id, tag_key) "
        "DO UPDATE SET name = excluded.name",
        (category_id, tag_key, name),
    )
    return cursor.execute(
        "SELECT id FROM tactical_tags "
        "WHERE tactical_tag_category_id = ? AND tag_key = ?",
        (category_id, tag_key),
    ).fetchone()[0]


def name_tokens(value: str) -> tuple[str, ...]:
    """Tokenise a name so substring matches remain whole-name matches."""
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def load_monsters(cursor: sqlite3.Cursor) -> list[tuple[int, str, tuple[str, ...]]]:
    return [
        (monster_id, name, name_tokens(name))
        for monster_id, name in cursor.execute("SELECT id, name FROM monsters")
    ]


def profile_monster_matches(
    source_name: str, monsters: list[tuple[int, str, tuple[str, ...]]]
) -> list[tuple[int, str]]:
    """Prefer exact matches, else match a complete source name within a 5e name."""
    exact_matches = [
        (monster_id, "exact")
        for monster_id, monster_name, _ in monsters
        if monster_name.casefold() == source_name.casefold()
    ]
    if exact_matches:
        return exact_matches

    source_tokens = name_tokens(source_name)
    if not source_tokens:
        return []
    match_size = len(source_tokens)
    return [
        (monster_id, "substring")
        for monster_id, _, monster_tokens in monsters
        if any(
            monster_tokens[index:index + match_size] == source_tokens
            for index in range(len(monster_tokens) - match_size + 1)
        )
    ]


def import_profiles(
    cursor: sqlite3.Cursor,
    source_id: int,
    rows: Iterable[dict[str, Any]],
    monsters: list[tuple[int, str, tuple[str, ...]]],
) -> dict[str, int]:
    """Import profile metadata, scores, roles, and tag-like list fields."""
    for dimension_name in PROFILE_SCORE_COLUMNS:
        cursor.execute(
            "INSERT INTO tactical_dimensions (dimension_key, display_name) "
            "VALUES (?, ?)",
            (slugify(dimension_name), dimension_name),
        )

    dimension_ids = {
        name: cursor.execute(
            "SELECT id FROM tactical_dimensions WHERE dimension_key = ?",
            (slugify(name),),
        ).fetchone()[0]
        for name in PROFILE_SCORE_COLUMNS
    }

    profile_ids: dict[str, int] = {}
    for row in rows:
        source_name = str(row["Monster"]).strip()
        matches = profile_monster_matches(source_name, monsters)
        exact_matches = [monster_id for monster_id, match_type in matches if match_type == "exact"]
        monster_id = exact_matches[0] if len(exact_matches) == 1 else None
        cursor.execute(
            """
            INSERT INTO tactical_profiles (
                tactical_source_id, monster_id, source_name, tactical_summary,
                confidence, uncertainty_note, target_priority_score,
                source_section, source_pdf_page, source_print_page
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                monster_id,
                source_name,
                row.get("Tactical Summary"),
                row.get("Confidence"),
                row.get("Uncertainties"),
                as_int(row.get("Target Priority Score")),
                row.get("Source Section"),
                as_int(row.get("Source Page (PDF)")),
                as_int(row.get("Source Print Page (Index)")),
            ),
        )
        profile_id = cursor.lastrowid
        profile_ids[source_name.casefold()] = profile_id

        cursor.executemany(
            """
            INSERT INTO tactical_profile_monster_links (
                tactical_profile_id, monster_id, match_type
            ) VALUES (?, ?, ?)
            """,
            [(profile_id, matched_monster_id, match_type) for matched_monster_id, match_type in matches],
        )

        for dimension_name, dimension_id in dimension_ids.items():
            score = as_int(row.get(dimension_name))
            if score is not None:
                cursor.execute(
                    "INSERT INTO tactical_profile_scores "
                    "(tactical_profile_id, tactical_dimension_id, score) "
                    "VALUES (?, ?, ?)",
                    (profile_id, dimension_id, score),
                )

        for role_name in split_values(row.get("Roles")):
            role_id = get_or_create_role(cursor, role_name)
            cursor.execute(
                "INSERT INTO tactical_profile_roles "
                "(tactical_profile_id, tactical_role_id) VALUES (?, ?)",
                (profile_id, role_id),
            )

        for column, category_key in TAG_COLUMNS.items():
            for tag_name in split_values(row.get(column)):
                tag_id = get_or_create_tag(cursor, category_key, tag_name)
                cursor.execute(
                    "INSERT INTO tactical_profile_tags "
                    "(tactical_profile_id, tactical_tag_id) VALUES (?, ?)",
                    (profile_id, tag_id),
                )

    return profile_ids


def import_environment_fits(
    cursor: sqlite3.Cursor,
    rows: Iterable[dict[str, Any]],
    profile_ids: dict[str, int],
) -> int:
    count = 0
    for row in rows:
        profile_id = profile_ids.get(str(row["Monster"]).casefold())
        environment_name = row.get("Environment")
        fit_score = row.get("Environment Fit")
        if profile_id is None or not environment_name or fit_score is None:
            continue
        environment_id = get_or_create_environment(cursor, str(environment_name).strip())
        cursor.execute(
            "INSERT INTO tactical_profile_environment_fits "
            "(tactical_profile_id, environment_id, fit_score) VALUES (?, ?, ?)",
            (profile_id, environment_id, float(fit_score)),
        )
        count += 1
    return count


def import_evidence(
    cursor: sqlite3.Cursor,
    rows: Iterable[dict[str, Any]],
    profile_ids: dict[str, int],
) -> int:
    dimension_ids = {
        display_name.casefold(): dimension_id
        for dimension_id, display_name in cursor.execute(
            "SELECT id, display_name FROM tactical_dimensions"
        )
    }
    values = []
    for row in rows:
        source_name = str(row["Monster"]).casefold()
        profile_id = profile_ids.get(source_name)
        if profile_id is None:
            continue
        attribute = str(row["Attribute"])
        values.append(
            (
                profile_id,
                dimension_ids.get(attribute.casefold()),
                attribute,
                as_int(row.get("Score")),
                row.get("Evidence Type"),
                row.get("Reasoning"),
                as_int(row.get("Source PDF Page")),
                row.get("Source Section"),
            )
        )
    cursor.executemany(
        """
        INSERT INTO tactical_profile_evidence (
            tactical_profile_id, tactical_dimension_id, attribute_name, score,
            evidence_type, reasoning, source_pdf_page, source_section
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    return len(values)


def ordered_pair(
    profile_ids: dict[str, int], monster_a: Any, monster_b: Any
) -> tuple[int, int] | None:
    first = profile_ids.get(str(monster_a).casefold())
    second = profile_ids.get(str(monster_b).casefold())
    if first is None or second is None or first == second:
        return None
    return tuple(sorted((first, second)))


def import_pairwise_affinities(
    cursor: sqlite3.Cursor,
    source_id: int,
    rows: Iterable[dict[str, Any]],
    profile_ids: dict[str, int],
) -> int:
    values = []
    for row in rows:
        pair = ordered_pair(profile_ids, row["Monster A"], row["Monster B"])
        affinity = row.get("Book Alliance Affinity")
        if pair is None or affinity is None:
            continue
        values.append(
            (
                source_id,
                *pair,
                float(affinity),
                row.get("Relationship Type"),
                row.get("Source Basis"),
                as_int(row.get("Source PDF Page")),
                row.get("Source Section"),
                row.get("Evidence Status"),
            )
        )
    cursor.executemany(
        """
        INSERT INTO tactical_pairwise_affinities (
            tactical_source_id, profile_a_id, profile_b_id, book_alliance_affinity,
            relationship_type, source_basis, source_pdf_page, source_section,
            evidence_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    return len(values)


def import_pairwise_compatibility(
    cursor: sqlite3.Cursor,
    source_id: int,
    rows: Iterable[dict[str, Any]],
    profile_ids: dict[str, int],
) -> int:
    values = []
    for row in rows:
        pair = ordered_pair(profile_ids, row["Monster A"], row["Monster B"])
        affinity = row.get("Affinity")
        friction = row.get("Behavioural Friction")
        if pair is None or affinity is None or friction is None:
            continue
        values.append((source_id, *pair, float(affinity), float(friction)))
    cursor.executemany(
        """
        INSERT INTO tactical_pairwise_compatibility (
            tactical_source_id, profile_a_id, profile_b_id, affinity,
            behavioural_friction
        ) VALUES (?, ?, ?, ?, ?)
        """,
        values,
    )
    return len(values)


def link_explicit_book_relationships(
    cursor: sqlite3.Cursor,
    rows: Iterable[dict[str, Any]],
    profile_ids: dict[str, int],
) -> int:
    """Expose explicit book relationships through the pre-existing relation table."""
    linked = 0
    for row in rows:
        first_profile = profile_ids.get(str(row["Monster A"]).casefold())
        second_profile = profile_ids.get(str(row["Monster B"]).casefold())
        if first_profile is None or second_profile is None:
            continue
        first_monsters = [
            row[0]
            for row in cursor.execute(
                "SELECT monster_id FROM tactical_profile_monster_links "
                "WHERE tactical_profile_id = ?",
                (first_profile,),
            )
        ]
        second_monsters = [
            row[0]
            for row in cursor.execute(
                "SELECT monster_id FROM tactical_profile_monster_links "
                "WHERE tactical_profile_id = ?",
                (second_profile,),
            )
        ]
        if not first_monsters or not second_monsters:
            continue
        affinity = float(row["Alliance Affinity"]) / 100
        relationship_type = row.get("Relationship Type") or "Book relationship"
        source_id = cursor.execute(
            "SELECT tactical_source_id FROM tactical_profiles WHERE id = ?",
            (first_profile,),
        ).fetchone()[0]
        for first_monster in first_monsters:
            for second_monster in second_monsters:
                if first_monster == second_monster:
                    continue
                for monster_id, related_monster_id in (
                    (first_monster, second_monster),
                    (second_monster, first_monster),
                ):
                    cursor.execute(
                        """
                        INSERT INTO monster_relationships (
                            monster_id, related_monster_id, relationship_type, affinity
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT(monster_id, related_monster_id) DO UPDATE SET
                            relationship_type = excluded.relationship_type,
                            affinity = excluded.affinity
                        """,
                        (monster_id, related_monster_id, relationship_type, affinity),
                    )
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO monster_relationship_tactical_sources (
                            monster_id, related_monster_id, tactical_source_id
                        ) VALUES (?, ?, ?)
                        """,
                        (monster_id, related_monster_id, source_id),
                    )
                    linked += 1
    return linked


def import_workbook(workbook_path: Path, db_path: Path, schema_path: Path) -> dict[str, int]:
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Tactical workbook not found: {workbook_path}")

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    required_sheets = {
        "Profiles",
        "Evidence",
        "Environment Fit",
        "Pairwise Affinity",
        "Tactical Compatibility",
        "Book Relationships",
    }
    missing_sheets = required_sheets.difference(workbook.sheetnames)
    if missing_sheets:
        raise ValueError(f"Workbook is missing required sheets: {sorted(missing_sheets)}")

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_schema(connection, schema_path)
        cursor = connection.cursor()
        clear_tactical_data(cursor)
        cursor.execute(
            """
            INSERT INTO tactical_sources (source_key, name, version, source_reference)
            VALUES (?, ?, ?, ?)
            """,
            (SOURCE_KEY, "The Monsters Know What They're Doing", "v0.3", workbook_path.name),
        )
        source_id = cursor.lastrowid
        monsters = load_monsters(cursor)
        profile_ids = import_profiles(
            cursor,
            source_id,
            workbook_rows(workbook, "Profiles"),
            monsters,
        )
        environment_fit_count = import_environment_fits(
            cursor,
            workbook_rows(workbook, "Environment Fit"),
            profile_ids,
        )
        evidence_count = import_evidence(
            cursor,
            workbook_rows(workbook, "Evidence"),
            profile_ids,
        )
        affinity_count = import_pairwise_affinities(
            cursor,
            source_id,
            workbook_rows(workbook, "Pairwise Affinity"),
            profile_ids,
        )
        compatibility_count = import_pairwise_compatibility(
            cursor,
            source_id,
            workbook_rows(workbook, "Tactical Compatibility"),
            profile_ids,
        )
        relationship_count = link_explicit_book_relationships(
            cursor,
            workbook_rows(workbook, "Book Relationships"),
            profile_ids,
        )
        linked_profiles = cursor.execute(
            "SELECT COUNT(DISTINCT tactical_profile_id) "
            "FROM tactical_profile_monster_links"
        ).fetchone()[0]
        substring_links = cursor.execute(
            "SELECT COUNT(*) FROM tactical_profile_monster_links "
            "WHERE match_type = 'substring'"
        ).fetchone()[0]
        connection.commit()
        return {
            "profiles": len(profile_ids),
            "linked_profiles": linked_profiles,
            "substring_links": substring_links,
            "evidence": evidence_count,
            "environment_fits": environment_fit_count,
            "pairwise_affinities": affinity_count,
            "pairwise_compatibility": compatibility_count,
            "relationship_links": relationship_count,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        workbook.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a book-anchored tactical workbook into Encounter Forge."
    )
    parser.add_argument("workbook", type=Path, help="Path to the tactical .xlsx file")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = import_workbook(args.workbook, args.database, args.schema)
    print("Tactical workbook import complete.")
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
