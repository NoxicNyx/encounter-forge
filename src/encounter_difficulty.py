"""Calculate and persist encounter difficulty for the SRD 2024 ruleset.

The official XP budget is the primary measure. A bounded stat adjustment then
compares a monster's AC, hit points, and strongest parsed attack to peers with
the same CR, making unusual stat blocks visible without replacing CR.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence


DEFAULT_RULESET_KEY = "dnd-2024"


@dataclass(frozen=True)
class PartyCapacity:
    player_levels: tuple[int, ...]
    slider_value: int
    low_xp: float
    moderate_xp: float
    high_xp: float
    requested_budget_xp: float
    requested_label: str


@dataclass(frozen=True)
class MonsterThreat:
    monster_id: int
    name: str
    quantity: int
    base_xp: float
    stat_factor: float
    adjusted_xp: float
    uses_inferred_xp: bool


@dataclass(frozen=True)
class EncounterAssessment:
    party: PartyCapacity
    monsters: tuple[MonsterThreat, ...]
    base_monster_xp: float
    stat_adjustment_factor: float
    action_economy_factor: float
    adjusted_monster_threat_xp: float
    assessed_band: str
    is_within_requested_budget: bool


def _ruleset_id(connection: sqlite3.Connection, ruleset_key: str) -> int:
    row = connection.execute(
        "SELECT id FROM difficulty_rulesets WHERE ruleset_key = ?", (ruleset_key,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown difficulty ruleset: {ruleset_key}")
    return row[0]


def _validate_slider(slider_value: int) -> int:
    if not isinstance(slider_value, int) or not 0 <= slider_value <= 100:
        raise ValueError("Difficulty slider must be an integer from 0 to 100.")
    return slider_value


def _validate_count_influence(count_influence: int) -> int:
    if not isinstance(count_influence, int) or not 0 <= count_influence <= 100:
        raise ValueError("Count influence must be an integer from 0 to 100.")
    return count_influence


def action_economy_factor(
    enemy_count: int, party_size: int, count_influence: int = 0
) -> float:
    """Blend 2024 base XP with the 2014 multiple-monster adjustment.

    At zero the calculation is the 2024 XP-budget method. At 100 it applies
    the 2014 action-economy multiplier, including that edition's party-size
    shift. Intermediate values are a deliberate, visible house-rule blend.
    """
    count_influence = _validate_count_influence(count_influence)
    if enemy_count < 1:
        raise ValueError("At least one enemy is required.")
    if party_size < 1:
        raise ValueError("At least one player is required.")
    if enemy_count == 1:
        legacy_factor = 1.0
    elif enemy_count == 2:
        legacy_factor = 1.5
    elif enemy_count <= 6:
        legacy_factor = 2.0
    elif enemy_count <= 10:
        legacy_factor = 2.5
    elif enemy_count <= 14:
        legacy_factor = 3.0
    else:
        legacy_factor = 4.0
    if party_size < 3:
        legacy_factor = {1.0: 1.5, 1.5: 2.0, 2.0: 2.5, 2.5: 3.0, 3.0: 4.0, 4.0: 5.0}[legacy_factor]
    elif party_size >= 6:
        legacy_factor = {1.0: 0.5, 1.5: 1.0, 2.0: 1.5, 2.5: 2.0, 3.0: 2.5, 4.0: 3.0}[legacy_factor]
    return 1.0 + (legacy_factor - 1.0) * (count_influence / 100)


def _interpolate_budget(low: float, moderate: float, high: float, slider_value: int) -> float:
    if slider_value <= 50:
        return low + (moderate - low) * (slider_value / 50)
    return moderate + (high - moderate) * ((slider_value - 50) / 50)


def _slider_label(slider_value: int) -> str:
    if slider_value < 25:
        return "Low"
    if slider_value < 75:
        return "Moderate"
    return "High"


def calculate_party_capacity(
    connection: sqlite3.Connection,
    player_levels: Sequence[int],
    slider_value: int,
    ruleset_key: str = DEFAULT_RULESET_KEY,
) -> PartyCapacity:
    """Sum each player's level budget and interpolate the requested slider value."""
    if not player_levels:
        raise ValueError("At least one player level is required.")
    slider_value = _validate_slider(slider_value)
    ruleset_id = _ruleset_id(connection, ruleset_key)
    totals = [0.0, 0.0, 0.0]
    for level in player_levels:
        if not isinstance(level, int) or not 1 <= level <= 20:
            raise ValueError("Player levels must be whole numbers from 1 to 20.")
        row = connection.execute(
            """
            SELECT low_xp, moderate_xp, high_xp
            FROM player_level_difficulty_budgets
            WHERE difficulty_ruleset_id = ? AND player_level = ?
            """,
            (ruleset_id, level),
        ).fetchone()
        if row is None:
            raise ValueError(f"No difficulty budget is configured for level {level}.")
        totals = [total + value for total, value in zip(totals, row)]
    low, moderate, high = totals
    return PartyCapacity(
        tuple(player_levels),
        slider_value,
        low,
        moderate,
        high,
        _interpolate_budget(low, moderate, high, slider_value),
        _slider_label(slider_value),
    )


def _monster_rows(connection: sqlite3.Connection, monster_ids: Iterable[int]) -> dict[int, sqlite3.Row]:
    monster_ids = tuple(monster_ids)
    if not monster_ids:
        return {}
    placeholders = ", ".join("?" for _ in monster_ids)
    query = f"""
        WITH action_damage AS (
            SELECT
                monster_actions.monster_id,
                attacks.action_id,
                SUM(
                    COALESCE(components.damage_die_count, 0)
                    * (CAST(SUBSTR(LOWER(components.damage_die_type), 2) AS REAL) + 1) / 2
                    + COALESCE(components.damage_bonus, 0)
                ) AS action_damage
            FROM monster_actions
            JOIN attacks ON attacks.action_id = monster_actions.id
            JOIN attack_damage_components components ON components.attack_id = attacks.id
            GROUP BY monster_actions.monster_id, attacks.action_id
        )
        SELECT monsters.id, monsters.name, monsters.challenge_rating,
               monsters.experience_points, monsters.armour_class, monsters.hit_points,
               COALESCE(MAX(action_damage.action_damage), 0) AS strongest_action_damage
        FROM monsters
        LEFT JOIN action_damage ON action_damage.monster_id = monsters.id
        WHERE monsters.id IN ({placeholders})
        GROUP BY monsters.id
    """
    return {row["id"]: row for row in connection.execute(query, monster_ids)}


def _peer_medians(connection: sqlite3.Connection, challenge_rating: float | None) -> tuple[float, float, float] | None:
    if challenge_rating is None:
        return None
    peer_rows = _monster_rows(
        connection,
        [row[0] for row in connection.execute(
            "SELECT id FROM monsters WHERE challenge_rating = ?", (challenge_rating,)
        )],
    ).values()
    ac_values = [row["armour_class"] for row in peer_rows if row["armour_class"]]
    hp_values = [row["hit_points"] for row in peer_rows if row["hit_points"]]
    damage_values = [row["strongest_action_damage"] for row in peer_rows if row["strongest_action_damage"]]
    if not ac_values or not hp_values:
        return None
    return (
        float(median(ac_values)),
        float(median(hp_values)),
        float(median(damage_values)) if damage_values else 0.0,
    )


def _stat_factor(connection: sqlite3.Connection, monster: sqlite3.Row) -> float:
    """Return a conservative 0.70–1.30 adjustment against same-CR peers."""
    peer_medians = _peer_medians(connection, monster["challenge_rating"])
    if peer_medians is None:
        return 1.0
    median_ac, median_hp, median_damage = peer_medians
    adjustment = 0.0
    if monster["armour_class"] and median_ac:
        adjustment += 0.10 * ((monster["armour_class"] / median_ac) - 1)
    if monster["hit_points"] and median_hp:
        adjustment += 0.15 * ((monster["hit_points"] / median_hp) - 1)
    if monster["strongest_action_damage"] and median_damage:
        adjustment += 0.20 * ((monster["strongest_action_damage"] / median_damage) - 1)
    return max(0.70, min(1.30, 1 + adjustment))


def calculate_monster_threats(
    connection: sqlite3.Connection,
    monsters: Sequence[tuple[int, int]],
    xp_overrides: dict[int, float] | None = None,
) -> tuple[MonsterThreat, ...]:
    """Calculate base and stat-adjusted XP for ``(monster_id, quantity)`` pairs."""
    if not monsters:
        raise ValueError("At least one monster is required.")
    connection.row_factory = sqlite3.Row
    rows = _monster_rows(connection, (monster_id for monster_id, _ in monsters))
    threats = []
    for monster_id, quantity in monsters:
        if not isinstance(quantity, int) or quantity < 1:
            raise ValueError("Monster quantities must be positive whole numbers.")
        row = rows.get(monster_id)
        if row is None:
            raise ValueError(f"Monster {monster_id} does not exist.")
        inferred_xp = (xp_overrides or {}).get(monster_id)
        experience_points = row["experience_points"] if row["experience_points"] is not None else inferred_xp
        if experience_points is None:
            raise ValueError(f"{row['name']} has no XP value and cannot be budgeted.")
        factor = _stat_factor(connection, row)
        base_xp = float(experience_points) * quantity
        threats.append(
            MonsterThreat(
                monster_id, row["name"], quantity, base_xp, factor, base_xp * factor,
                row["experience_points"] is None,
            )
        )
    return tuple(threats)


def assess_encounter(
    connection: sqlite3.Connection,
    player_levels: Sequence[int],
    monsters: Sequence[tuple[int, int]],
    slider_value: int = 50,
    ruleset_key: str = DEFAULT_RULESET_KEY,
    count_influence: int = 0,
    xp_overrides: dict[int, float] | None = None,
) -> EncounterAssessment:
    """Assess a monster group against a party and 0–100 difficulty slider."""
    party = calculate_party_capacity(connection, player_levels, slider_value, ruleset_key)
    count_influence = _validate_count_influence(count_influence)
    threats = calculate_monster_threats(connection, monsters, xp_overrides)
    base_xp = sum(threat.base_xp for threat in threats)
    stat_adjusted_xp = sum(threat.adjusted_xp for threat in threats)
    stat_adjustment = stat_adjusted_xp / base_xp if base_xp else 1.0
    economy_adjustment = action_economy_factor(
        sum(threat.quantity for threat in threats), len(player_levels), count_influence
    )
    adjusted_xp = stat_adjusted_xp * economy_adjustment
    if adjusted_xp <= party.low_xp:
        assessed_band = "Low"
    elif adjusted_xp <= party.moderate_xp:
        assessed_band = "Moderate"
    elif adjusted_xp <= party.high_xp:
        assessed_band = "High"
    else:
        assessed_band = "Above High"
    return EncounterAssessment(
        party,
        threats,
        base_xp,
        stat_adjustment,
        economy_adjustment,
        adjusted_xp,
        assessed_band,
        adjusted_xp <= party.requested_budget_xp,
    )


def save_assessment(
    connection: sqlite3.Connection,
    assessment: EncounterAssessment,
    environment_id: int | None = None,
    ruleset_key: str = DEFAULT_RULESET_KEY,
    generation_settings: dict[str, int | str | bool | None] | None = None,
) -> int:
    """Persist a request, its player levels, monster group, and assessment result."""
    ruleset_id = _ruleset_id(connection, ruleset_key)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO encounter_requests (environment_id, difficulty_key) VALUES (?, ?)",
        (environment_id, assessment.party.requested_label.casefold()),
    )
    request_id = cursor.lastrowid
    cursor.executemany(
        """INSERT INTO encounter_request_players (encounter_request_id, player_number, level)
        VALUES (?, ?, ?)""",
        [(request_id, number, level) for number, level in enumerate(assessment.party.player_levels, start=1)],
    )
    cursor.execute(
        """INSERT INTO encounter_request_difficulty_settings (
        encounter_request_id, difficulty_ruleset_id, slider_value) VALUES (?, ?, ?)""",
        (request_id, ruleset_id, assessment.party.slider_value),
    )
    cursor.execute(
        """INSERT INTO encounter_results (encounter_request_id, encounter_xp, tactical_score, notes)
        VALUES (?, ?, ?, ?)""",
        (request_id, round(assessment.adjusted_monster_threat_xp), None, "Stat-adjusted SRD 2024 XP assessment"),
    )
    result_id = cursor.lastrowid
    if generation_settings is not None:
        cursor.execute(
            """
            INSERT INTO encounter_request_generation_settings (
                encounter_request_id, preferred_enemy_count, count_influence,
                grouping_bias, variety_enabled, variety_limit,
                include_unprofiled, include_missing_xp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                generation_settings["preferred_enemy_count"],
                generation_settings["count_influence"],
                generation_settings["grouping_bias"],
                generation_settings["variety_enabled"],
                generation_settings["variety_limit"],
                generation_settings["include_unprofiled"],
                generation_settings["include_missing_xp"],
            ),
        )
    cursor.execute(
        """
        INSERT INTO encounter_difficulty_adjustment_factors (
            encounter_result_id, stat_factor, action_economy_factor
        ) VALUES (?, ?, ?)
        """,
        (result_id, assessment.stat_adjustment_factor, assessment.action_economy_factor),
    )
    cursor.executemany(
        """INSERT INTO encounter_result_monsters (encounter_result_id, monster_id, quantity)
        VALUES (?, ?, ?)""",
        [(result_id, threat.monster_id, threat.quantity) for threat in assessment.monsters],
    )
    cursor.execute(
        """INSERT INTO encounter_difficulty_assessments (
            encounter_result_id, difficulty_ruleset_id, slider_value, party_budget_xp,
            base_monster_xp, stat_adjustment_factor, adjusted_monster_threat_xp, assessed_band
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result_id,
            ruleset_id,
            assessment.party.slider_value,
            assessment.party.requested_budget_xp,
            assessment.base_monster_xp,
            assessment.stat_adjustment_factor,
            assessment.adjusted_monster_threat_xp,
            assessment.assessed_band,
        ),
    )
    connection.commit()
    return result_id
