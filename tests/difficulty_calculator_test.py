import sqlite3
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from encounter_difficulty import assess_encounter, calculate_party_capacity, save_assessment
from encounter_generator import generate_encounters, save_recommendation


class DifficultyCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        schema = (ROOT_DIR / "db" / "schema.sql").read_text(encoding="utf-8")
        self.connection.executescript(schema)
        self.connection.execute(
            "INSERT INTO sources (source_key, name) VALUES ('test', 'Test source')"
        )
        self.connection.execute(
            """
            INSERT INTO monsters (
                source_id, creature_key, name, challenge_rating,
                armour_class, hit_points, experience_points
            ) VALUES (1, 'test-goblin', 'Test Goblin', 0.25, 15, 7, 50)
            """
        )
        self.connection.execute(
            """
            INSERT INTO monster_actions (monster_id, name, description, order_in_statblock)
            VALUES (1, 'Scimitar', 'A quick melee weapon attack.', 1)
            """
        )
        self.connection.execute(
            """
            INSERT INTO attacks (
                action_id, name, attack_type, to_hit_modifier, reach,
                damage_die_count, damage_die_type, damage_bonus, damage_type
            ) VALUES (1, 'Scimitar', 'Melee Weapon Attack', 4, 5, 1, 'd6', 2, 'slashing')
            """
        )
        self.connection.execute("INSERT INTO environments (name) VALUES ('forest')")
        self.connection.execute(
            "INSERT INTO monster_environments (monster_id, environment_id, affinity) VALUES (1, 1, NULL)"
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_player_budgets_sum_and_slider_interpolates(self):
        capacity = calculate_party_capacity(self.connection, [1, 1, 1, 1], 25)

        self.assertEqual(capacity.low_xp, 200)
        self.assertEqual(capacity.moderate_xp, 300)
        self.assertEqual(capacity.high_xp, 400)
        self.assertEqual(capacity.requested_budget_xp, 250)
        self.assertEqual(capacity.requested_label, "Moderate")

    def test_monster_xp_is_assessed_against_the_selected_budget(self):
        assessment = assess_encounter(self.connection, [1, 1, 1, 1], [(1, 4)], 0)

        self.assertEqual(assessment.base_monster_xp, 200)
        self.assertEqual(assessment.assessed_band, "Low")
        self.assertTrue(assessment.is_within_requested_budget)

    def test_count_influence_blends_in_the_2014_action_economy_multiplier(self):
        assessment = assess_encounter(
            self.connection, [1, 1, 1, 1], [(1, 4)], 100, count_influence=100
        )

        self.assertEqual(assessment.action_economy_factor, 2)
        self.assertEqual(assessment.adjusted_monster_threat_xp, 400)

    def test_assessment_persists_party_monsters_and_slider(self):
        assessment = assess_encounter(self.connection, [1, 1, 1, 1], [(1, 4)], 50)

        result_id = save_assessment(self.connection, assessment)

        self.assertEqual(
            self.connection.execute(
                "SELECT slider_value FROM encounter_difficulty_assessments "
                "WHERE encounter_result_id = ?",
                (result_id,),
            ).fetchone()[0],
            50,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM encounter_request_players"
            ).fetchone()[0],
            4,
        )

    def test_generator_returns_a_budget_fitting_environment_match(self):
        generation = generate_encounters(
            self.connection,
            [1, 1, 1, 1],
            slider_value=50,
            environment="forest",
            preferred_enemy_count=6,
            grouping_bias="same_species",
            include_unprofiled=True,
        )

        self.assertTrue(generation.recommendations)
        recommendation = generation.recommendations[0]
        self.assertEqual(recommendation.environment_fit, 100)
        self.assertEqual(recommendation.assessment.base_monster_xp, 300)
        self.assertTrue(recommendation.assessment.is_within_requested_budget)
        self.assertEqual(len(recommendation.creature_plans), 1)
        plan = recommendation.creature_plans[0]
        self.assertEqual(plan.name, "Test Goblin")
        self.assertEqual(plan.quantity, 6)
        self.assertEqual(plan.armour_class, 15)
        self.assertEqual(plan.hit_points, 7)
        self.assertEqual(plan.speeds, "Speed unavailable")
        self.assertEqual(plan.attacks[0].name, "Scimitar")
        self.assertEqual(plan.attacks[0].to_hit_modifier, 4)
        self.assertEqual(plan.attacks[0].damage, "1d6 + 2 slashing")

        result_id = save_recommendation(self.connection, recommendation, environment_id=1)
        self.assertEqual(
            self.connection.execute(
                "SELECT tactical_score FROM encounter_results WHERE id = ?", (result_id,)
            ).fetchone()[0],
            recommendation.tactical_score,
        )
        settings = self.connection.execute(
            "SELECT preferred_enemy_count, grouping_bias, include_unprofiled "
            "FROM encounter_request_generation_settings"
        ).fetchone()
        self.assertEqual(tuple(settings), (6, "same_species", 1))

    def test_generator_prefers_and_explains_a_source_relationship(self):
        self.connection.execute(
            "UPDATE monsters SET creature_type = 'humanoid' WHERE id = 1"
        )
        self.connection.execute(
            """
            INSERT INTO monsters (
                source_id, creature_key, name, creature_type, challenge_rating,
                armour_class, hit_points, experience_points
            ) VALUES (1, 'test-goblin-captain', 'Test Goblin Captain', 'humanoid',
                      0.25, 15, 8, 50)
            """
        )
        self.connection.executemany(
            """
            INSERT INTO monster_relationships
                (monster_id, related_monster_id, relationship_type, affinity)
            VALUES (?, ?, 'book ally', 0.60)
            """,
            [(1, 2), (2, 1)],
        )
        self.connection.execute(
            "INSERT INTO tactical_sources (source_key, name) VALUES ('test-book', 'Test book')"
        )
        self.connection.executemany(
            """
            INSERT INTO tactical_profiles (tactical_source_id, source_name)
            VALUES (1, ?)
            """,
            [("Test Goblin",), ("Test Goblin Captain",)],
        )
        self.connection.executemany(
            """
            INSERT INTO tactical_profile_monster_links (tactical_profile_id, monster_id, match_type)
            VALUES (?, ?, 'exact')
            """,
            [(1, 1), (2, 2)],
        )
        self.connection.executemany(
            """
            INSERT INTO monster_relationship_tactical_sources
                (monster_id, related_monster_id, tactical_source_id)
            VALUES (?, ?, 1)
            """,
            [(1, 2), (2, 1)],
        )
        self.connection.execute(
            "INSERT INTO monster_environments (monster_id, environment_id, affinity) VALUES (2, 1, NULL)"
        )
        self.connection.commit()

        recommendation = generate_encounters(
            self.connection, [1, 1, 1, 1], slider_value=50, environment="forest"
        ).recommendations[0]

        self.assertTrue(recommendation.relationship_notes)
        self.assertIn("book ally", recommendation.relationship_notes[0])
        self.assertGreaterEqual(recommendation.stat_similarity, 90)
        self.assertGreaterEqual(recommendation.grouping_score, 88)

        species_recommendation = generate_encounters(
            self.connection, [1, 1, 1, 1], slider_value=50, environment="forest",
            grouping_bias="same_species",
        ).recommendations[0]
        self.assertEqual(species_recommendation.grouping_bias, "same_species")
        self.assertEqual(species_recommendation.grouping_score, 100)

        no_bias_recommendation = generate_encounters(
            self.connection, [1, 1, 1, 1], slider_value=50, environment="forest",
            grouping_bias="none", max_distinct_creatures=1,
        ).recommendations[0]
        self.assertIsNone(no_bias_recommendation.grouping_score)
        self.assertEqual(len(no_bias_recommendation.assessment.monsters), 1)

    def test_enemy_count_preference_reorders_recommendations(self):
        recommendation = generate_encounters(
            self.connection,
            [1, 1, 1, 1],
            slider_value=50,
            environment="forest",
            preferred_enemy_count=3,
            grouping_bias="same_species",
            include_unprofiled=True,
            max_members=6,
        ).recommendations[0]

        self.assertEqual(recommendation.preferred_enemy_count, 3)
        self.assertEqual(
            sum(threat.quantity for threat in recommendation.assessment.monsters), 3
        )


if __name__ == "__main__":
    unittest.main()
