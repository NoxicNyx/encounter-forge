import sqlite3
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "src" / "database" / "dependencies"))

from creature_family import family_identity, populate_monster_families
from curated_profile_mappings import apply_curated_profile_links, populate_curated_profile_mappings
from encounter_forge_gui import (
    migrate_family_catalogue,
    sync_conversion_bridge,
    sync_curated_mapping_bridge,
)
from encounter_generator import EncounterCandidate, _group_score
from environment_enrichment import enrich_environments
from tactical_dataset_import import load_monsters, profile_monster_matches


class CreatureFamilyTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            (ROOT_DIR / "db" / "schema.sql").read_text(encoding="utf-8")
        )
        self.connection.execute(
            "INSERT INTO sources (source_key, name) VALUES ('test', 'Test source')"
        )
        self.connection.executemany(
            """
            INSERT INTO monsters (
                source_id, creature_key, name, challenge_rating,
                armour_class, hit_points, experience_points
            ) VALUES (1, ?, ?, 0.25, 15, 7, 50)
            """,
            [
                ("goblin-warrior", "Goblin Warrior"),
                ("hobgoblin-warrior", "Hobgoblin Warrior"),
                ("goblin-boss", "Goblin Boss"),
                ("warrior-veteran", "Warrior Veteran"),
            ],
        )
        populate_monster_families(self.connection.cursor())
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_goblin_hobgoblin_and_bugbear_are_explicitly_distinct(self):
        self.assertEqual(family_identity("Goblin Warrior")[0], "goblin")
        self.assertEqual(family_identity("Hobgoblin Warrior")[0], "hobgoblin")
        self.assertEqual(family_identity("Bugbear Warrior")[0], "bugbear")
        self.assertNotEqual(family_identity("Goblin")[0], family_identity("Hobgoblin")[0])

    def test_2014_profile_bridge_reaches_goblin_variants_not_hobgoblins(self):
        matches = profile_monster_matches("Goblin", load_monsters(self.connection.cursor()))
        matched_names = {
            self.connection.execute("SELECT name FROM monsters WHERE id = ?", (monster_id,)).fetchone()[0]
            for monster_id, match_type in matches
            if match_type == "official_conversion"
        }
        self.assertEqual(matched_names, {"Goblin Warrior"})
        veteran_matches = profile_monster_matches("Veteran", load_monsters(self.connection.cursor()))
        veteran_names = {
            self.connection.execute("SELECT name FROM monsters WHERE id = ?", (monster_id,)).fetchone()[0]
            for monster_id, match_type in veteran_matches
            if match_type == "official_conversion"
        }
        self.assertEqual(veteran_names, {"Warrior Veteran"})

    def test_official_conversion_and_audited_aliases_have_distinct_link_types(self):
        self.assertEqual(
            profile_monster_matches("Acolyte", [(1, "Priest Acolyte", "priest-acolyte")]),
            [(1, "official_conversion")],
        )
        self.assertEqual(
            profile_monster_matches("Erinys", [(1, "Erinyes", "erinyes")]),
            [(1, "name_alias")],
        )

    def test_environment_bridge_uses_the_same_family_boundary(self):
        # A deterministic fixture avoids a network call while exercising the
        # actual enrichment function used by the database build.
        database = ROOT_DIR / "tests" / "_family_fixture.sqlite"
        try:
            backup = sqlite3.connect(database)
            self.connection.backup(backup)
            backup.close()
            enrich_environments(database, {"goblin": {"forest"}, "hobgoblin": {"hill"}})
            check = sqlite3.connect(database)
            rows = check.execute(
                """
                SELECT monsters.name, environments.name
                FROM monster_environments
                JOIN monsters ON monsters.id = monster_environments.monster_id
                JOIN environments ON environments.id = monster_environments.environment_id
                ORDER BY monsters.name, environments.name
                """
            ).fetchall()
            check.close()
            self.assertEqual(
                rows,
                [("Goblin Boss", "forest"), ("Goblin Warrior", "forest"), ("Hobgoblin Warrior", "hill")],
            )
        finally:
            if database.exists():
                database.unlink()

    def test_same_family_grouping_rejects_the_old_first_word_heuristic(self):
        family_ids = dict(
            self.connection.execute(
                """
                SELECT monsters.name, monster_creature_families.creature_family_id
                FROM monsters JOIN monster_creature_families
                  ON monster_creature_families.monster_id = monsters.id
                """
            )
        )
        candidates = [
            EncounterCandidate(1, "Goblin Warrior", family_ids["Goblin Warrior"], None, .25, 15, 7, 50, 50, 50, frozenset(), False, True),
            EncounterCandidate(2, "Hobgoblin Warrior", family_ids["Hobgoblin Warrior"], None, .25, 15, 7, 50, 50, 50, frozenset(), False, True),
            EncounterCandidate(3, "Goblin Boss", family_ids["Goblin Boss"], None, .25, 15, 7, 50, 50, 50, frozenset(), False, True),
        ]
        same_family = _group_score((0, 2), candidates, 100, {}, {}, None, "same_species", 4, 0)
        mixed_family = _group_score((0, 1), candidates, 100, {}, {}, None, "same_species", 4, 0)
        self.assertEqual(same_family[4], 100)
        self.assertEqual(mixed_family[4], 0)

    def test_app_database_migration_backfills_existing_catalogues(self):
        self.connection.execute("DELETE FROM monster_creature_families")
        self.connection.commit()
        migrate_family_catalogue(self.connection)
        assigned = self.connection.execute(
            "SELECT COUNT(*) FROM monster_creature_families"
        ).fetchone()[0]
        self.assertEqual(assigned, 4)

    def test_app_migration_copies_bundled_conversion_links(self):
        database = ROOT_DIR / "tests" / "_conversion_seed.sqlite"
        try:
            seed = sqlite3.connect(database)
            seed.executescript((ROOT_DIR / "db" / "schema.sql").read_text(encoding="utf-8"))
            seed.execute("INSERT INTO sources (source_key, name) VALUES ('seed', 'Seed')")
            seed.execute(
                "INSERT INTO monsters (source_id, creature_key, name) VALUES (1, 'priest-acolyte', 'Priest Acolyte')"
            )
            seed.execute("INSERT INTO tactical_sources (source_key, name) VALUES ('book', 'Book')")
            seed.execute("INSERT INTO tactical_profiles (tactical_source_id, source_name) VALUES (1, 'Acolyte')")
            seed.execute(
                "INSERT INTO tactical_profile_monster_links VALUES (1, 1, 'official_conversion')"
            )
            seed.execute(
                "INSERT INTO creature_edition_conversions VALUES ('Acolyte', 'Priest Acolyte', 'official')"
            )
            seed.commit()
            seed.close()

            self.connection.execute(
                "INSERT INTO tactical_sources (source_key, name) VALUES ('book', 'Book')"
            )
            self.connection.execute(
                "INSERT INTO tactical_profiles (tactical_source_id, source_name) VALUES (1, 'Acolyte')"
            )
            self.connection.execute(
                "INSERT INTO monsters (source_id, creature_key, name) VALUES (1, 'priest-acolyte', 'Priest Acolyte')"
            )
            self.connection.commit()
            self.assertTrue(sync_conversion_bridge(self.connection, database))
            self.assertEqual(
                self.connection.execute(
                    "SELECT match_type FROM tactical_profile_monster_links"
                ).fetchone()[0],
                "official_conversion",
            )
        finally:
            if database.exists():
                database.unlink()

    def test_app_migration_copies_source_backed_curated_links(self):
        database = ROOT_DIR / "tests" / "_curated_mapping_seed.sqlite"
        try:
            seed = sqlite3.connect(database)
            seed.executescript((ROOT_DIR / "db" / "schema.sql").read_text(encoding="utf-8"))
            seed.execute("INSERT INTO sources (source_key, name) VALUES ('seed', 'Seed')")
            seed.execute(
                "INSERT INTO monsters (source_id, creature_key, name) VALUES (1, 'goblin-minion', 'Goblin Minion')"
            )
            seed.execute(
                "INSERT INTO curated_profile_monster_mappings VALUES ('Goblin', 'goblin-minion', 'book p. 23')"
            )
            seed.commit()
            seed.close()

            self.connection.execute(
                "INSERT INTO tactical_sources (source_key, name) VALUES ('book', 'Book')"
            )
            self.connection.execute(
                "INSERT INTO tactical_profiles (tactical_source_id, source_name) VALUES (1, 'Goblin')"
            )
            self.connection.execute(
                "INSERT INTO monsters (source_id, creature_key, name) VALUES (1, 'goblin-minion', 'Goblin Minion')"
            )
            self.connection.commit()
            self.assertTrue(sync_curated_mapping_bridge(self.connection, database))
            self.assertEqual(
                self.connection.execute(
                    "SELECT match_type FROM tactical_profile_monster_links"
                ).fetchone()[0],
                "curated_mapping",
            )
        finally:
            if database.exists():
                database.unlink()

    def test_curated_dragon_mapping_uses_the_catalogue_key_and_source_reference(self):
        self.connection.execute(
            "INSERT INTO tactical_sources (source_key, name) VALUES ('book', 'Book')"
        )
        self.connection.execute(
            "INSERT INTO tactical_profiles (tactical_source_id, source_name) VALUES (1, 'Chromatic')"
        )
        self.connection.execute(
            "INSERT INTO monsters (source_id, creature_key, name) VALUES (1, 'srd-2024_adult-black-dragon', 'Adult Black Dragon')"
        )
        cursor = self.connection.cursor()
        populate_curated_profile_mappings(cursor)
        apply_curated_profile_links(cursor)
        self.assertEqual(
            self.connection.execute(
                "SELECT match_type FROM tactical_profile_monster_links"
            ).fetchone()[0],
            "curated_mapping",
        )
        reference = self.connection.execute(
            """
            SELECT source_reference FROM curated_profile_monster_mappings
            WHERE source_name = 'Chromatic' AND creature_key = 'srd-2024_adult-black-dragon'
            """
        ).fetchone()[0]
        self.assertIn("Chromatic Dragons", reference)

    def test_curated_mapping_seed_removes_only_the_invalid_legacy_key_shape(self):
        self.connection.execute(
            """
            INSERT INTO curated_profile_monster_mappings VALUES
            ('Chromatic', 'srd-2024-adult-black-dragon', 'obsolete key')
            """
        )
        populate_curated_profile_mappings(self.connection.cursor())
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM curated_profile_monster_mappings WHERE creature_key GLOB 'srd-2024-*'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM curated_profile_monster_mappings"
            ).fetchone()[0],
            44,
        )


if __name__ == "__main__":
    unittest.main()
