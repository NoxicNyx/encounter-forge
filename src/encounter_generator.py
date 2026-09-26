"""Generate explainable, tactically coherent SRD 2024 encounters."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from statistics import median
from typing import Iterable, Sequence

from encounter_difficulty import (
    EncounterAssessment,
    action_economy_factor,
    assess_encounter,
    calculate_monster_threats,
    calculate_party_capacity,
    save_assessment,
)


@dataclass(frozen=True)
class EncounterCandidate:
    monster_id: int
    name: str
    creature_type: str | None
    challenge_rating: float | None
    armour_class: int | None
    hit_points: int | None
    experience_points: float
    adjusted_xp: float
    environment_fit: float
    roles: frozenset[str]
    uses_inferred_xp: bool
    has_tactical_profile: bool


@dataclass(frozen=True)
class EncounterRecommendation:
    assessment: EncounterAssessment
    environment_fit: float
    tactical_score: float
    stat_similarity: float
    grouping_score: float | None
    grouping_bias: str
    preferred_enemy_count: int | None
    count_influence: int
    max_distinct_creatures: int | None
    include_unprofiled: bool
    include_missing_xp: bool
    roles: tuple[str, ...]
    relationship_notes: tuple[str, ...]
    creature_plans: tuple["CreaturePlan", ...]
    explanation: str


@dataclass(frozen=True)
class EncounterGeneration:
    recommendations: tuple[EncounterRecommendation, ...]
    candidate_count: int
    environment_match_count: int
    message: str


@dataclass(frozen=True)
class AttackDetail:
    """A table-ready attack, retaining both structured values and source text."""

    name: str
    attack_type: str | None
    to_hit_modifier: int | None
    reach: int | None
    range: int | None
    long_range: int | None
    damage: str
    description: str | None


@dataclass(frozen=True)
class CreaturePlan:
    monster_id: int
    name: str
    quantity: int
    challenge_rating: float | None
    experience_points: int | None
    experience_points_inferred: bool
    armour_class: int | None
    hit_points: int | None
    speeds: str
    roles: tuple[str, ...]
    engagement_style: tuple[str, ...]
    target_preferences: tuple[str, ...]
    special_behaviours: tuple[str, ...]
    tactical_summary: str
    attacks: tuple[AttackDetail, ...]
    action_names: tuple[str, ...]


def _tokens(value: str) -> frozenset[str]:
    return frozenset("".join(character if character.isalnum() else " " for character in value.casefold()).split())


def _species_key(name: str) -> str:
    """Use the first name word as the player-facing species grouping key."""
    words = "".join(character if character.isalnum() else " " for character in name.casefold()).split()
    return words[0] if words else ""


def _environment_fit(selected_environment: str | None, environment_names: Iterable[str], tactical_fits: dict[str, float]) -> float:
    if not selected_environment:
        return 50.0
    selected_tokens = _tokens(selected_environment)
    best = 0.0
    for environment_name in environment_names:
        if environment_name.casefold() == selected_environment.casefold():
            best = max(best, 100.0)
        elif selected_tokens.intersection(_tokens(environment_name)):
            best = max(best, 75.0)
    for environment_name, fit in tactical_fits.items():
        if environment_name.casefold() == selected_environment.casefold():
            best = max(best, fit)
        elif selected_tokens.intersection(_tokens(environment_name)):
            best = max(best, fit * 0.75)
    return best


def _load_tactical_context(connection: sqlite3.Connection):
    environments: dict[int, set[str]] = defaultdict(set)
    for monster_id, environment_name in connection.execute(
        """
        SELECT monster_environments.monster_id, environments.name
        FROM monster_environments
        JOIN environments ON environments.id = monster_environments.environment_id
        """
    ):
        environments[monster_id].add(environment_name)

    roles: dict[int, set[str]] = defaultdict(set)
    for monster_id, role_name in connection.execute(
        """
        SELECT links.monster_id, tactical_roles.name
        FROM tactical_profile_monster_links links
        JOIN tactical_profile_roles profile_roles
          ON profile_roles.tactical_profile_id = links.tactical_profile_id
        JOIN tactical_roles ON tactical_roles.id = profile_roles.tactical_role_id
        """
    ):
        roles[monster_id].add(role_name)

    tactical_fits: dict[int, dict[str, float]] = defaultdict(dict)
    for monster_id, environment_name, fit_score in connection.execute(
        """
        SELECT links.monster_id, environments.name, MAX(fits.fit_score)
        FROM tactical_profile_monster_links links
        JOIN tactical_profile_environment_fits fits
          ON fits.tactical_profile_id = links.tactical_profile_id
        JOIN environments ON environments.id = fits.environment_id
        GROUP BY links.monster_id, environments.name
        """
    ):
        tactical_fits[monster_id][environment_name] = float(fit_score)

    profile_to_monsters: dict[int, list[int]] = defaultdict(list)
    for profile_id, monster_id in connection.execute(
        "SELECT tactical_profile_id, monster_id FROM tactical_profile_monster_links"
    ):
        profile_to_monsters[profile_id].append(monster_id)
    compatibility: dict[tuple[int, int], float] = {}
    for profile_a, profile_b, affinity in connection.execute(
        "SELECT profile_a_id, profile_b_id, affinity FROM tactical_pairwise_compatibility"
    ):
        for monster_a in profile_to_monsters.get(profile_a, []):
            for monster_b in profile_to_monsters.get(profile_b, []):
                if monster_a == monster_b:
                    continue
                key = tuple(sorted((monster_a, monster_b)))
                compatibility[key] = max(compatibility.get(key, 0.0), float(affinity))

    relationships: dict[tuple[int, int], tuple[float, str]] = {}
    for monster_id, related_id, affinity, relationship_type in connection.execute(
        """
        SELECT relationships.monster_id, relationships.related_monster_id,
               relationships.affinity, relationships.relationship_type
        FROM monster_relationships relationships
        JOIN monster_relationship_tactical_sources provenance
          ON provenance.monster_id = relationships.monster_id
         AND provenance.related_monster_id = relationships.related_monster_id
        """
    ):
        relationship = (float(affinity), relationship_type)
        relationships[(monster_id, related_id)] = relationship
        # Table relationships describe an encounter pairing, so eligibility is
        # mutual even when the imported source supplied only one direction.
        relationships.setdefault((related_id, monster_id), relationship)

    return environments, roles, tactical_fits, compatibility, relationships


def _creature_plans(
    connection: sqlite3.Connection, assessment: EncounterAssessment
) -> tuple[CreaturePlan, ...]:
    """Build concise, table-ready tactical guidance for every recommended creature."""
    plans = []
    for threat in assessment.monsters:
        monster = connection.execute(
            """
            SELECT monsters.name, monsters.challenge_rating, monsters.experience_points,
                   monsters.armour_class, monsters.hit_points,
                   speeds.walk, speeds.fly, speeds.swim, speeds.climb, speeds.burrow
            FROM monsters
            LEFT JOIN monster_speeds speeds ON speeds.monster_id = monsters.id
            WHERE monsters.id = ?
            """,
            (threat.monster_id,),
        ).fetchone()
        role_rows = connection.execute(
            """
            SELECT DISTINCT tactical_roles.name
            FROM tactical_profile_monster_links links
            JOIN tactical_profile_roles profile_roles
              ON profile_roles.tactical_profile_id = links.tactical_profile_id
            JOIN tactical_roles ON tactical_roles.id = profile_roles.tactical_role_id
            WHERE links.monster_id = ?
            ORDER BY tactical_roles.name
            """,
            (threat.monster_id,),
        ).fetchall()
        tag_rows = connection.execute(
            """
            SELECT categories.category_key, tags.name
            FROM tactical_profile_monster_links links
            JOIN tactical_profile_tags profile_tags
              ON profile_tags.tactical_profile_id = links.tactical_profile_id
            JOIN tactical_tags tags ON tags.id = profile_tags.tactical_tag_id
            JOIN tactical_tag_categories categories
              ON categories.id = tags.tactical_tag_category_id
            WHERE links.monster_id = ?
            ORDER BY categories.category_key, tags.name
            """,
            (threat.monster_id,),
        ).fetchall()
        tags: dict[str, list[str]] = defaultdict(list)
        for category_key, tag_name in tag_rows:
            if tag_name not in tags[category_key]:
                tags[category_key].append(tag_name)
        profile = connection.execute(
            """
            SELECT tactical_summary
            FROM tactical_profile_monster_links links
            JOIN tactical_profiles profiles ON profiles.id = links.tactical_profile_id
            WHERE links.monster_id = ?
            ORDER BY CASE links.match_type WHEN 'exact' THEN 0 ELSE 1 END, profiles.id
            LIMIT 1
            """,
            (threat.monster_id,),
        ).fetchone()
        attack_rows = connection.execute(
            """
            SELECT attacks.id, monster_actions.name, monster_actions.description,
                   attacks.attack_type, attacks.to_hit_modifier, attacks.reach,
                   attacks.range, attacks.long_range, attacks.damage_die_count,
                   attacks.damage_die_type, attacks.damage_bonus, attacks.damage_type
            FROM monster_actions
            JOIN attacks ON attacks.action_id = monster_actions.id
            WHERE monster_actions.monster_id = ?
            ORDER BY monster_actions.order_in_statblock, attacks.id
            LIMIT 8
            """,
            (threat.monster_id,),
        ).fetchall()
        attacks = []
        for attack in attack_rows:
            component_rows = connection.execute(
                """
                SELECT damage_die_count, damage_die_type, damage_bonus, damage_type
                FROM attack_damage_components
                WHERE attack_id = ?
                ORDER BY component_order
                """,
                (attack["id"],),
            ).fetchall()
            components = component_rows or [attack]
            damage_parts = []
            for component in components:
                dice_count = component["damage_die_count"]
                die_type = component["damage_die_type"]
                bonus = component["damage_bonus"]
                damage_type = component["damage_type"]
                if dice_count and die_type:
                    damage = f"{dice_count}{die_type}"
                    if bonus:
                        damage += f" {'+' if bonus > 0 else '-'} {abs(bonus)}"
                elif bonus is not None:
                    damage = str(bonus)
                else:
                    continue
                damage_parts.append(f"{damage} {damage_type}" if damage_type else damage)
            attacks.append(AttackDetail(
                attack["name"],
                attack["attack_type"],
                attack["to_hit_modifier"],
                attack["reach"],
                attack["range"],
                attack["long_range"],
                " + ".join(damage_parts) or "Damage not listed",
                attack["description"],
            ))
        actions = connection.execute(
            """
            SELECT name
            FROM monster_actions
            WHERE monster_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM attacks WHERE attacks.action_id = monster_actions.id
              )
            ORDER BY order_in_statblock, name
            LIMIT 6
            """,
            (threat.monster_id,),
        ).fetchall()
        speed_parts = [
            f"walk {monster['walk']} ft." if monster["walk"] else None,
            f"fly {monster['fly']} ft." if monster["fly"] else None,
            f"swim {monster['swim']} ft." if monster["swim"] else None,
            f"climb {monster['climb']} ft." if monster["climb"] else None,
            f"burrow {monster['burrow']} ft." if monster["burrow"] else None,
        ]
        plans.append(CreaturePlan(
            threat.monster_id,
            monster["name"],
            threat.quantity,
            monster["challenge_rating"],
            round(threat.base_xp / threat.quantity),
            threat.uses_inferred_xp,
            monster["armour_class"],
            monster["hit_points"],
            ", ".join(part for part in speed_parts if part) or "Speed unavailable",
            tuple(row[0] for row in role_rows),
            tuple(tags["engagement_style"]),
            tuple(tags["target_preference"]),
            tuple(tags["special_behaviour"]),
            profile[0] if profile else "No book tactical profile is linked; use the stat block and encounter context.",
            tuple(attacks),
            tuple(row[0] for row in actions),
        ))
    return tuple(plans)


def _candidate_pool(
    connection: sqlite3.Connection,
    target_xp: float,
    environment: str | None,
    grouping_bias: str,
    party_size: int,
    count_influence: int,
    include_unprofiled: bool,
    include_missing_xp: bool,
    max_candidates: int,
) -> tuple[list[EncounterCandidate], int]:
    rows = connection.execute(
        """
        SELECT id, name, creature_type, challenge_rating, armour_class, hit_points,
               experience_points
        FROM monsters
        ORDER BY challenge_rating, name
        """
    ).fetchall()
    environments, roles, tactical_fits, _, _ = _load_tactical_context(connection)
    xp_by_cr: dict[float, list[float]] = defaultdict(list)
    for row in rows:
        if row["challenge_rating"] is not None and row["experience_points"] and row["experience_points"] > 0:
            xp_by_cr[float(row["challenge_rating"])].append(float(row["experience_points"]))
    inferred_xp_by_id = {
        row["id"]: float(median(xp_by_cr[float(row["challenge_rating"])]))
        for row in rows
        if row["experience_points"] is None or row["experience_points"] <= 0
        if row["challenge_rating"] is not None and xp_by_cr.get(float(row["challenge_rating"]))
    }
    profile_monster_ids = {
        row[0] for row in connection.execute(
            "SELECT DISTINCT monster_id FROM tactical_profile_monster_links"
        )
    }
    candidates = []
    for row in rows:
        monster_id = row["id"]
        inferred_xp = inferred_xp_by_id.get(monster_id)
        uses_inferred_xp = row["experience_points"] is None or row["experience_points"] <= 0
        if uses_inferred_xp and (not include_missing_xp or inferred_xp is None):
            continue
        threat = calculate_monster_threats(
            connection, [(monster_id, 1)],
            {monster_id: inferred_xp} if inferred_xp is not None else None,
        )[0]
        if threat.adjusted_xp * action_economy_factor(1, party_size, count_influence) > target_xp:
            continue
        fit = _environment_fit(environment, environments[monster_id], tactical_fits[monster_id])
        candidates.append(
            EncounterCandidate(
                monster_id,
                row["name"],
                row["creature_type"],
                row["challenge_rating"],
                row["armour_class"],
                row["hit_points"],
                float(row["experience_points"] or inferred_xp),
                threat.adjusted_xp,
                fit,
                frozenset(roles[monster_id]),
                uses_inferred_xp,
                monster_id in profile_monster_ids,
            )
        )
    if grouping_bias == "book_relationships" or not include_unprofiled:
        candidates = [candidate for candidate in candidates if candidate.has_tactical_profile]
    environment_matches = sum(candidate.environment_fit > 0 for candidate in candidates)
    if environment and environment_matches:
        # Keep a book-linked companion eligible when its linked creature is a
        # terrain match. It receives a partial, truthful environment score;
        # otherwise an explicit relationship could never influence a filtered
        # encounter search.
        _, _, _, _, relationships = _load_tactical_context(connection)
        direct_match_ids = {
            candidate.monster_id for candidate in candidates if candidate.environment_fit > 0
        }
        linked_support_ids = {
            related_id
            for (monster_id, related_id) in relationships
            if monster_id in direct_match_ids
        }
        candidates = [
            replace(candidate, environment_fit=max(candidate.environment_fit, 50.0))
            if grouping_bias == "book_relationships" and candidate.monster_id in linked_support_ids else candidate
            for candidate in candidates
            if candidate.environment_fit > 0
            or (grouping_bias == "book_relationships" and candidate.monster_id in linked_support_ids)
        ]
    candidates.sort(
        key=lambda candidate: (
            0.70 * candidate.environment_fit
            + 30 * min(candidate.adjusted_xp / target_xp, 1.0),
            candidate.adjusted_xp,
        ),
        reverse=True,
    )
    return candidates[:max_candidates], environment_matches


def _stat_similarity(first: EncounterCandidate, second: EncounterCandidate) -> float:
    """Compare actual stat-block shape, keeping missing values neutral."""
    if first.monster_id == second.monster_id:
        return 100.0
    ratios = []
    if first.challenge_rating is not None and second.challenge_rating is not None:
        lower = min(first.challenge_rating + 0.125, second.challenge_rating + 0.125)
        higher = max(first.challenge_rating + 0.125, second.challenge_rating + 0.125)
        ratios.append(100 * lower / higher)
    if first.armour_class and second.armour_class:
        ratios.append(max(0.0, 100 - 8 * abs(first.armour_class - second.armour_class)))
    if first.hit_points and second.hit_points:
        ratios.append(100 * min(first.hit_points, second.hit_points) / max(first.hit_points, second.hit_points))
    return sum(ratios) / len(ratios) if ratios else 50.0


def _enemy_count_fit(enemy_count: int, preferred_enemy_count: int | None) -> float:
    """Score a rough headcount preference without turning it into a hard cap."""
    if preferred_enemy_count is None:
        return 50.0
    return max(0.0, 100.0 - 30.0 * abs(enemy_count - preferred_enemy_count))


def _strict_book_group(
    state: tuple[int, ...],
    candidates: Sequence[EncounterCandidate],
    relationships: dict[tuple[int, int], tuple[float, str]],
) -> bool:
    """Require every distinct creature in Book Links mode to have a source link."""
    distinct_ids = {candidates[index].monster_id for index in state}
    if len(distinct_ids) < 2:
        return False
    return all(
        any((monster_id, other_id) in relationships for other_id in distinct_ids - {monster_id})
        for monster_id in distinct_ids
    )


def _group_score(
    state: tuple[int, ...],
    candidates: Sequence[EncounterCandidate],
    target_xp: float,
    compatibility: dict[tuple[int, int], float],
    relationships: dict[tuple[int, int], tuple[float, str]],
    preferred_enemy_count: int | None,
    grouping_bias: str,
    party_size: int,
    count_influence: int,
) -> tuple[float, float, float, float, float | None, tuple[str, ...], tuple[str, ...]]:
    group = [candidates[index] for index in state]
    threat = sum(candidate.adjusted_xp for candidate in group) * action_economy_factor(
        len(group), party_size, count_influence
    )
    budget_fit = max(0.0, 1 - abs(target_xp - threat) / target_xp)
    environment_fit = sum(candidate.environment_fit for candidate in group) / len(group)
    roles = frozenset().union(*(candidate.roles for candidate in group))
    role_score = min(len(roles) / 3, 1.0)
    pair_scores = []
    species_scores = []
    relationship_scores = []
    stat_similarity_scores = []
    relationship_pairs = 0
    notes = set()
    for first_index, first in enumerate(group):
        for second in group[first_index + 1:]:
            pair_scores.append(compatibility.get(tuple(sorted((first.monster_id, second.monster_id))), 50.0))
            stat_similarity_scores.append(_stat_similarity(first, second))
            species_scores.append(
                100.0 if _species_key(first.name) and _species_key(first.name) == _species_key(second.name) else 0.0
            )
            relationship = relationships.get((first.monster_id, second.monster_id))
            if relationship is not None:
                # A book-backed link is strong evidence even if its source
                # affinity was conservatively scored during import.
                relationship_scores.append(max(88.0, relationship[0] * 100))
                relationship_pairs += 1
                notes.add(f"{first.name} / {second.name}: {relationship[1]}")
            else:
                relationship_scores.append(0.0)
    compatibility_score = sum(pair_scores) / len(pair_scores) if pair_scores else 50.0
    species_score = sum(species_scores) / len(species_scores) if species_scores else 100.0
    relationship_score = (
        max(
            sum(relationship_scores) / len(relationship_scores),
            max(relationship_scores),
        ) if relationship_scores else 50.0
    )
    stat_similarity = sum(stat_similarity_scores) / len(stat_similarity_scores) if stat_similarity_scores else 100.0
    if grouping_bias == "same_species":
        grouping_score = species_score
        tactical_score = (
            0.32 * environment_fit
            + 0.16 * compatibility_score
            + 0.24 * species_score
            + 0.20 * stat_similarity
            + 8 * role_score
        )
    elif grouping_bias == "book_relationships":
        grouping_score = relationship_score
        tactical_score = (
            0.32 * environment_fit
            + 0.16 * compatibility_score
            + 0.24 * relationship_score
            + 0.20 * stat_similarity
            + 8 * role_score
        )
        tactical_score = min(100.0, tactical_score + min(6.0, 3.0 * relationship_pairs))
    else:
        grouping_score = None
        tactical_score = (
            0.52 * environment_fit
            + 0.28 * compatibility_score
            + 20 * role_score
        )
    if preferred_enemy_count is None:
        score = 56 * budget_fit + 0.44 * tactical_score
    else:
        # This makes the player's desired table complexity meaningful while
        # preserving room for XP fit and source-backed tactical cohesion.
        score = (
            30 * budget_fit
            + 0.40 * tactical_score
            + 0.30 * _enemy_count_fit(len(group), preferred_enemy_count)
        )
    return (
        score, environment_fit, tactical_score, stat_similarity, grouping_score,
        tuple(sorted(roles)), tuple(sorted(notes)),
    )


def _can_join_cohesive_group(
    state: tuple[int, ...],
    candidate_index: int,
    candidates: Sequence[EncounterCandidate],
    relationships: dict[tuple[int, int], tuple[float, str]],
) -> bool:
    """Keep grouping preferences soft; valid mixed encounters remain available."""
    return True


def _recommendations_from_states(
    connection: sqlite3.Connection,
    states: Iterable[tuple[int, ...]],
    candidates: Sequence[EncounterCandidate],
    player_levels: Sequence[int],
    slider_value: int,
    target_xp: float,
    compatibility: dict[tuple[int, int], float],
    relationships: dict[tuple[int, int], tuple[float, str]],
    preferred_enemy_count: int | None,
    grouping_bias: str,
    count_influence: int,
    max_distinct_creatures: int | None,
    include_unprofiled: bool,
    include_missing_xp: bool,
    limit: int,
) -> tuple[EncounterRecommendation, ...]:
    scored = []
    for state in states:
        score, environment_fit, tactical_score, stat_similarity, grouping_score, roles, notes = _group_score(
            state, candidates, target_xp, compatibility, relationships, preferred_enemy_count,
            grouping_bias, len(player_levels), count_influence,
        )
        monster_counts = Counter(candidates[index].monster_id for index in state)
        if grouping_bias == "book_relationships" and not _strict_book_group(
            state, candidates, relationships
        ):
            continue
        composition = frozenset(monster_counts)
        scored.append((
            score, composition, monster_counts, environment_fit, tactical_score,
            stat_similarity, grouping_score, roles, notes,
        ))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = []
    chosen_compositions = []
    for _, composition, monster_counts, environment_fit, tactical_score, stat_similarity, grouping_score, roles, notes in scored:
        if any(
            len(composition.intersection(existing)) / len(composition.union(existing)) > 0.75
            for existing in chosen_compositions
        ):
            continue
        assessment = assess_encounter(
            connection,
            player_levels,
            list(monster_counts.items()),
            slider_value,
            count_influence=count_influence,
            xp_overrides={
                candidate.monster_id: candidate.experience_points
                for candidate in candidates
                if candidate.uses_inferred_xp
            },
        )
        description = ", ".join(
            f"{threat.quantity} x {threat.name}" for threat in assessment.monsters
        )
        enemy_count = sum(threat.quantity for threat in assessment.monsters)
        count_note = (
            f"{enemy_count} enemies against a preference for roughly {preferred_enemy_count}; "
            if preferred_enemy_count is not None else ""
        )
        explanation = (
            f"{description}. {count_note}{assessment.adjusted_monster_threat_xp:,.0f} adjusted XP "
            f"against a {assessment.party.requested_budget_xp:,.0f} XP target; "
            f"environment fit {environment_fit:.0f}/100, stat similarity {stat_similarity:.0f}/100, "
            f"and tactical score {tactical_score:.0f}/100."
        )
        recommendation = EncounterRecommendation(
            assessment,
            environment_fit,
            tactical_score,
            stat_similarity,
            grouping_score,
            grouping_bias,
            preferred_enemy_count,
            count_influence,
            max_distinct_creatures,
            include_unprofiled,
            include_missing_xp,
            roles,
            notes,
            _creature_plans(connection, assessment),
            explanation,
        )
        chosen.append(recommendation)
        chosen_compositions.append(composition)
        if len(chosen) == limit:
            break
    return tuple(chosen)


def generate_encounters(
    connection: sqlite3.Connection,
    player_levels: Sequence[int],
    slider_value: int = 50,
    environment: str | None = None,
    preferred_enemy_count: int | None = None,
    count_influence: int = 0,
    grouping_bias: str = "book_relationships",
    max_distinct_creatures: int | None = None,
    include_unprofiled: bool = False,
    include_missing_xp: bool = False,
    locked_monsters: dict[int, int] | None = None,
    limit: int = 5,
    max_members: int = 6,
    max_candidates: int = 70,
) -> EncounterGeneration:
    """Return several budget-fitting, diverse encounter recommendations.

    ``max_members`` bounds the beam search for responsive table use. The GUI
    expands that bound up to twenty when the user asks for a crowd encounter.
    """
    connection.row_factory = sqlite3.Row
    if preferred_enemy_count is not None and (
        not isinstance(preferred_enemy_count, int) or not 1 <= preferred_enemy_count <= 20
    ):
        raise ValueError("Preferred enemy count must be a whole number from 1 to 20.")
    if not isinstance(count_influence, int) or not 0 <= count_influence <= 100:
        raise ValueError("Count influence must be a whole number from 0 to 100.")
    if grouping_bias not in {"same_species", "book_relationships", "none"}:
        raise ValueError("Grouping bias must be same_species, book_relationships, or none.")
    if max_distinct_creatures is not None and (
        not isinstance(max_distinct_creatures, int) or not 1 <= max_distinct_creatures <= 20
    ):
        raise ValueError("Creature variety limit must be a whole number from 1 to 20.")
    if not isinstance(max_members, int) or not 1 <= max_members <= 20:
        raise ValueError("Maximum enemy count must be a whole number from 1 to 20.")
    locked_monsters = locked_monsters or {}
    if any(not isinstance(monster_id, int) or not isinstance(quantity, int) or quantity < 1 for monster_id, quantity in locked_monsters.items()):
        raise ValueError("Locked roster entries must use a monster id and a positive whole quantity.")
    capacity = calculate_party_capacity(connection, player_levels, slider_value)
    candidates, environment_matches = _candidate_pool(
        connection,
        capacity.requested_budget_xp,
        environment,
        grouping_bias,
        len(player_levels),
        count_influence,
        include_unprofiled,
        include_missing_xp,
        max_candidates,
    )
    if not candidates:
        return EncounterGeneration((), 0, environment_matches, "No monsters fit the selected XP budget.")
    _, _, _, compatibility, relationships = _load_tactical_context(connection)
    candidate_indexes = {candidate.monster_id: index for index, candidate in enumerate(candidates)}
    missing_locked = set(locked_monsters).difference(candidate_indexes)
    if missing_locked:
        return EncounterGeneration((), len(candidates), environment_matches, "A locked creature is not eligible for these settings.")
    locked_state = tuple(sorted(index for monster_id, quantity in locked_monsters.items() for index in [candidate_indexes[monster_id]] * quantity))
    if len(locked_state) > max_members:
        raise ValueError("Locked roster exceeds the maximum encounter size.")
    locked_threat = sum(candidates[index].adjusted_xp for index in locked_state) * action_economy_factor(len(locked_state), len(player_levels), count_influence)
    if locked_threat > capacity.requested_budget_xp:
        return EncounterGeneration((), len(candidates), environment_matches, "Locked roster exceeds the selected encounter budget.")
    beam: list[tuple[int, ...]] = [locked_state]
    all_states: list[tuple[int, ...]] = []
    for _ in range(max_members - len(locked_state)):
        expanded = []
        for state in beam:
            first_candidate = state[-1] if state else 0
            for candidate_index in range(first_candidate, len(candidates)):
                if not _can_join_cohesive_group(state, candidate_index, candidates, relationships):
                    continue
                if max_distinct_creatures is not None:
                    distinct_creatures = {candidates[index].monster_id for index in state}
                    if (
                        candidates[candidate_index].monster_id not in distinct_creatures
                        and len(distinct_creatures) >= max_distinct_creatures
                    ):
                        continue
                new_state = state + (candidate_index,)
                threat = sum(candidates[index].adjusted_xp for index in new_state)
                threat *= action_economy_factor(
                    len(new_state), len(player_levels), count_influence
                )
                if threat <= capacity.requested_budget_xp:
                    expanded.append(new_state)
        if not expanded:
            break
        all_states.extend(expanded)
        expanded.sort(
            key=lambda state: _group_score(
                state, candidates, capacity.requested_budget_xp, compatibility, relationships,
                preferred_enemy_count, grouping_bias, len(player_levels), count_influence,
            )[0],
            reverse=True,
        )
        beam = expanded[:140 if max_members > 12 else 250]
    recommendations = _recommendations_from_states(
        connection,
        all_states,
        candidates,
        player_levels,
        slider_value,
        capacity.requested_budget_xp,
        compatibility,
        relationships,
        preferred_enemy_count,
        grouping_bias,
        count_influence,
        max_distinct_creatures,
        include_unprofiled,
        include_missing_xp,
        limit,
    )
    environment_message = (
        f" {environment_matches} candidates have a direct or tactical match for {environment}."
        if environment else ""
    )
    return EncounterGeneration(
        recommendations,
        len(candidates),
        environment_matches,
        f"Searched {len(candidates)} budget-eligible candidates.{environment_message}",
    )


def save_recommendation(
    connection: sqlite3.Connection,
    recommendation: EncounterRecommendation,
    environment_id: int | None = None,
) -> int:
    """Persist a chosen recommendation and its generator-specific explanation."""
    result_id = save_assessment(
        connection,
        recommendation.assessment,
        environment_id,
        generation_settings={
            "preferred_enemy_count": recommendation.preferred_enemy_count or sum(
                threat.quantity for threat in recommendation.assessment.monsters
            ),
            "count_influence": recommendation.count_influence,
            "grouping_bias": recommendation.grouping_bias,
            "variety_enabled": recommendation.max_distinct_creatures is not None,
            "variety_limit": recommendation.max_distinct_creatures,
            "include_unprofiled": recommendation.include_unprofiled,
            "include_missing_xp": recommendation.include_missing_xp,
        },
    )
    connection.execute(
        "UPDATE encounter_results SET tactical_score = ?, notes = ? WHERE id = ?",
        (recommendation.tactical_score, recommendation.explanation, result_id),
    )
    connection.commit()
    return result_id
