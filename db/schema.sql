CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    display_name TEXT,
    publisher TEXT,
    game_system TEXT,
    permalink TEXT
);

CREATE TABLE IF NOT EXISTS monsters (
    id INTEGER PRIMARY KEY,

    source_id INTEGER NOT NULL,
    creature_key TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    creature_type TEXT,
    size TEXT,
    category TEXT,
    subcategory TEXT,
    alignment TEXT,

    challenge_rating REAL,
    proficiency_bonus INTEGER,

    armour_class INTEGER,
    armour_detail TEXT,

    hit_points INTEGER,
    hit_dice TEXT,
    experience_points INTEGER,

    initiative_bonus INTEGER,
    passive_perception INTEGER,

    normal_sight_range INTEGER,
    darkvision_range INTEGER,
    blindsight_range INTEGER,
    tremorsense_range INTEGER,
    truesight_range INTEGER,

    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS monster_ability_scores (
    monster_id INTEGER PRIMARY KEY,

    strength INTEGER,
    dexterity INTEGER,
    constitution INTEGER,
    intelligence INTEGER,
    wisdom INTEGER,
    charisma INTEGER,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_modifiers (
    monster_id INTEGER PRIMARY KEY,

    strength INTEGER,
    dexterity INTEGER,
    constitution INTEGER,
    intelligence INTEGER,
    wisdom INTEGER,
    charisma INTEGER,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_speeds (
    monster_id INTEGER PRIMARY KEY,

    walk INTEGER,
    crawl INTEGER,
    fly INTEGER,
    burrow INTEGER,
    climb INTEGER,
    swim INTEGER,

    hover BOOLEAN,

    unit TEXT,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);


CREATE TABLE IF NOT EXISTS languages (
    id INTEGER PRIMARY KEY,
    language_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS monster_languages (
    monster_id INTEGER NOT NULL,
    language_id INTEGER NOT NULL,

    PRIMARY KEY (monster_id, language_id),

    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    FOREIGN KEY (language_id) REFERENCES languages(id)
);

CREATE TABLE IF NOT EXISTS monster_saving_throws (
    monster_id INTEGER NOT NULL,
    ability TEXT NOT NULL,
    modifier INTEGER NOT NULL,

    PRIMARY KEY (monster_id, ability),

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_skills (
    monster_id INTEGER NOT NULL,
    skill TEXT NOT NULL,
    modifier INTEGER NOT NULL,

    PRIMARY KEY (monster_id, skill),

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_defenses (
    id INTEGER PRIMARY KEY,

    monster_id INTEGER NOT NULL,

    defense_type TEXT NOT NULL,
    damage_type TEXT NOT NULL,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_actions (
    id INTEGER PRIMARY KEY,

    monster_id INTEGER NOT NULL,

    name TEXT NOT NULL,
    description TEXT,

    action_type TEXT,
    order_in_statblock INTEGER,

    legendary_action_cost INTEGER,

    limited_to_form TEXT,

    usage_type TEXT,
    usage_parameter INTEGER,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS attacks (
    id INTEGER PRIMARY KEY,

    action_id INTEGER NOT NULL,

    name TEXT NOT NULL,
    attack_type TEXT,

    to_hit_modifier INTEGER,

    reach INTEGER,
    range INTEGER,
    long_range INTEGER,

    target_creature_only BOOLEAN,

    damage_die_count INTEGER,
    damage_die_type TEXT,
    damage_bonus INTEGER,

    damage_type TEXT,

    FOREIGN KEY (action_id) REFERENCES monster_actions(id)
);

CREATE TABLE IF NOT EXISTS monster_traits (
    id INTEGER PRIMARY KEY,

    monster_id INTEGER NOT NULL,

    name TEXT NOT NULL,
    description TEXT,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS environments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS monster_environments (
    monster_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,

    affinity REAL,

    PRIMARY KEY (monster_id, environment_id),

    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),

    CHECK (affinity >= 0 AND affinity <= 1)
);

CREATE TABLE IF NOT EXISTS monster_relationships (
    monster_id INTEGER NOT NULL,
    related_monster_id INTEGER NOT NULL,

    relationship_type TEXT NOT NULL,
    affinity REAL NOT NULL,

    PRIMARY KEY (monster_id, related_monster_id),

    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    FOREIGN KEY (related_monster_id) REFERENCES monsters(id),

    CHECK (affinity >= 0 AND affinity <= 1)
);

CREATE TABLE IF NOT EXISTS monster_relationship_tactical_sources (
    monster_id INTEGER NOT NULL,
    related_monster_id INTEGER NOT NULL,
    tactical_source_id INTEGER NOT NULL,

    PRIMARY KEY (monster_id, related_monster_id, tactical_source_id),

    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    FOREIGN KEY (related_monster_id) REFERENCES monsters(id),
    FOREIGN KEY (tactical_source_id) REFERENCES tactical_sources(id)
);

-- Open5e fields that are not represented by the initial monster schema.
CREATE TABLE IF NOT EXISTS monster_communication_notes (
    monster_id INTEGER PRIMARY KEY,
    languages_text TEXT,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_condition_immunities (
    monster_id INTEGER NOT NULL,
    condition_name TEXT NOT NULL,

    PRIMARY KEY (monster_id, condition_name),

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS attack_damage_components (
    id INTEGER PRIMARY KEY,
    attack_id INTEGER NOT NULL,
    component_order INTEGER NOT NULL,
    damage_die_count INTEGER,
    damage_die_type TEXT,
    damage_bonus INTEGER,
    damage_type TEXT,

    UNIQUE (attack_id, component_order),

    FOREIGN KEY (attack_id) REFERENCES attacks(id)
);

CREATE TABLE IF NOT EXISTS monster_cross_references (
    monster_id INTEGER NOT NULL,
    target_key TEXT NOT NULL,
    relationship_type TEXT NOT NULL,

    PRIMARY KEY (monster_id, target_key, relationship_type),

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

CREATE TABLE IF NOT EXISTS monster_illustrations (
    monster_id INTEGER PRIMARY KEY,
    image_url TEXT,

    FOREIGN KEY (monster_id) REFERENCES monsters(id)
);

-- Tactical data imported from the book-anchored workbook. Profiles retain their
-- source name even where an exact Open5e creature match is unavailable.
CREATE TABLE IF NOT EXISTS tactical_sources (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT,
    source_reference TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tactical_profiles (
    id INTEGER PRIMARY KEY,
    tactical_source_id INTEGER NOT NULL,
    monster_id INTEGER,
    source_name TEXT NOT NULL,
    tactical_summary TEXT,
    confidence TEXT,
    uncertainty_note TEXT,
    target_priority_score INTEGER,
    source_section TEXT,
    source_pdf_page INTEGER,
    source_print_page INTEGER,

    UNIQUE (tactical_source_id, source_name),

    FOREIGN KEY (tactical_source_id) REFERENCES tactical_sources(id),
    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    CHECK (target_priority_score IS NULL OR target_priority_score BETWEEN 0 AND 5)
);

CREATE TABLE IF NOT EXISTS tactical_profile_monster_links (
    tactical_profile_id INTEGER NOT NULL,
    monster_id INTEGER NOT NULL,
    match_type TEXT NOT NULL,

    PRIMARY KEY (tactical_profile_id, monster_id),

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    CHECK (match_type IN ('exact', 'substring'))
);

CREATE TABLE IF NOT EXISTS tactical_dimensions (
    id INTEGER PRIMARY KEY,
    dimension_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactical_profile_scores (
    tactical_profile_id INTEGER NOT NULL,
    tactical_dimension_id INTEGER NOT NULL,
    score INTEGER NOT NULL,

    PRIMARY KEY (tactical_profile_id, tactical_dimension_id),

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (tactical_dimension_id) REFERENCES tactical_dimensions(id),
    CHECK (score BETWEEN 0 AND 5)
);

CREATE TABLE IF NOT EXISTS tactical_roles (
    id INTEGER PRIMARY KEY,
    role_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tactical_profile_roles (
    tactical_profile_id INTEGER NOT NULL,
    tactical_role_id INTEGER NOT NULL,

    PRIMARY KEY (tactical_profile_id, tactical_role_id),

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (tactical_role_id) REFERENCES tactical_roles(id)
);

CREATE TABLE IF NOT EXISTS tactical_tag_categories (
    id INTEGER PRIMARY KEY,
    category_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactical_tags (
    id INTEGER PRIMARY KEY,
    tactical_tag_category_id INTEGER NOT NULL,
    tag_key TEXT NOT NULL,
    name TEXT NOT NULL,

    UNIQUE (tactical_tag_category_id, tag_key),

    FOREIGN KEY (tactical_tag_category_id) REFERENCES tactical_tag_categories(id)
);

CREATE TABLE IF NOT EXISTS tactical_profile_tags (
    tactical_profile_id INTEGER NOT NULL,
    tactical_tag_id INTEGER NOT NULL,

    PRIMARY KEY (tactical_profile_id, tactical_tag_id),

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (tactical_tag_id) REFERENCES tactical_tags(id)
);

CREATE TABLE IF NOT EXISTS tactical_profile_environment_fits (
    tactical_profile_id INTEGER NOT NULL,
    environment_id INTEGER NOT NULL,
    fit_score REAL NOT NULL,

    PRIMARY KEY (tactical_profile_id, environment_id),

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (environment_id) REFERENCES environments(id),
    CHECK (fit_score BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS tactical_profile_evidence (
    id INTEGER PRIMARY KEY,
    tactical_profile_id INTEGER NOT NULL,
    tactical_dimension_id INTEGER,
    attribute_name TEXT NOT NULL,
    score INTEGER,
    evidence_type TEXT,
    reasoning TEXT,
    source_pdf_page INTEGER,
    source_section TEXT,

    FOREIGN KEY (tactical_profile_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (tactical_dimension_id) REFERENCES tactical_dimensions(id),
    CHECK (score IS NULL OR score BETWEEN 0 AND 5)
);

CREATE TABLE IF NOT EXISTS tactical_pairwise_affinities (
    tactical_source_id INTEGER NOT NULL,
    profile_a_id INTEGER NOT NULL,
    profile_b_id INTEGER NOT NULL,
    book_alliance_affinity REAL NOT NULL,
    relationship_type TEXT,
    source_basis TEXT,
    source_pdf_page INTEGER,
    source_section TEXT,
    evidence_status TEXT,

    PRIMARY KEY (tactical_source_id, profile_a_id, profile_b_id),

    FOREIGN KEY (tactical_source_id) REFERENCES tactical_sources(id),
    FOREIGN KEY (profile_a_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (profile_b_id) REFERENCES tactical_profiles(id),
    CHECK (profile_a_id < profile_b_id),
    CHECK (book_alliance_affinity BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS tactical_pairwise_compatibility (
    tactical_source_id INTEGER NOT NULL,
    profile_a_id INTEGER NOT NULL,
    profile_b_id INTEGER NOT NULL,
    affinity REAL NOT NULL,
    behavioural_friction REAL NOT NULL,

    PRIMARY KEY (tactical_source_id, profile_a_id, profile_b_id),

    FOREIGN KEY (tactical_source_id) REFERENCES tactical_sources(id),
    FOREIGN KEY (profile_a_id) REFERENCES tactical_profiles(id),
    FOREIGN KEY (profile_b_id) REFERENCES tactical_profiles(id),
    CHECK (profile_a_id < profile_b_id),
    CHECK (affinity BETWEEN 0 AND 100),
    CHECK (behavioural_friction BETWEEN 0 AND 100)
);

-- Persistent inputs and outputs for the planned encounter-generation UI.
CREATE TABLE IF NOT EXISTS encounter_requests (
    id INTEGER PRIMARY KEY,
    environment_id INTEGER,
    difficulty_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (environment_id) REFERENCES environments(id)
);

CREATE TABLE IF NOT EXISTS encounter_request_players (
    encounter_request_id INTEGER NOT NULL,
    player_number INTEGER NOT NULL,
    level INTEGER NOT NULL,

    PRIMARY KEY (encounter_request_id, player_number),

    FOREIGN KEY (encounter_request_id) REFERENCES encounter_requests(id),
    CHECK (player_number > 0),
    CHECK (level BETWEEN 1 AND 20)
);

CREATE TABLE IF NOT EXISTS encounter_results (
    id INTEGER PRIMARY KEY,
    encounter_request_id INTEGER NOT NULL,
    encounter_xp INTEGER,
    tactical_score REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (encounter_request_id) REFERENCES encounter_requests(id)
);

CREATE TABLE IF NOT EXISTS encounter_result_monsters (
    encounter_result_id INTEGER NOT NULL,
    monster_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,

    PRIMARY KEY (encounter_result_id, monster_id),

    FOREIGN KEY (encounter_result_id) REFERENCES encounter_results(id),
    FOREIGN KEY (monster_id) REFERENCES monsters(id),
    CHECK (quantity > 0)
);

-- D&D 2024 encounter budgets and the inputs/results of the difficulty engine.
CREATE TABLE IF NOT EXISTS difficulty_rulesets (
    id INTEGER PRIMARY KEY,
    ruleset_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_level_difficulty_budgets (
    difficulty_ruleset_id INTEGER NOT NULL,
    player_level INTEGER NOT NULL,
    low_xp INTEGER NOT NULL,
    moderate_xp INTEGER NOT NULL,
    high_xp INTEGER NOT NULL,

    PRIMARY KEY (difficulty_ruleset_id, player_level),

    FOREIGN KEY (difficulty_ruleset_id) REFERENCES difficulty_rulesets(id),
    CHECK (player_level BETWEEN 1 AND 20),
    CHECK (low_xp > 0 AND moderate_xp >= low_xp AND high_xp >= moderate_xp)
);

CREATE TABLE IF NOT EXISTS difficulty_slider_anchors (
    difficulty_ruleset_id INTEGER NOT NULL,
    slider_value INTEGER NOT NULL,
    label TEXT NOT NULL,
    budget_column TEXT NOT NULL,

    PRIMARY KEY (difficulty_ruleset_id, slider_value),

    FOREIGN KEY (difficulty_ruleset_id) REFERENCES difficulty_rulesets(id),
    CHECK (slider_value BETWEEN 0 AND 100),
    CHECK (budget_column IN ('low_xp', 'moderate_xp', 'high_xp'))
);

CREATE TABLE IF NOT EXISTS encounter_request_difficulty_settings (
    encounter_request_id INTEGER PRIMARY KEY,
    difficulty_ruleset_id INTEGER NOT NULL,
    slider_value INTEGER NOT NULL,

    FOREIGN KEY (encounter_request_id) REFERENCES encounter_requests(id),
    FOREIGN KEY (difficulty_ruleset_id) REFERENCES difficulty_rulesets(id),
    CHECK (slider_value BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS encounter_request_generation_settings (
    encounter_request_id INTEGER PRIMARY KEY,
    preferred_enemy_count INTEGER NOT NULL,
    count_influence INTEGER NOT NULL,
    grouping_bias TEXT NOT NULL,
    variety_enabled BOOLEAN NOT NULL,
    variety_limit INTEGER,
    include_unprofiled BOOLEAN NOT NULL,
    include_missing_xp BOOLEAN NOT NULL,

    FOREIGN KEY (encounter_request_id) REFERENCES encounter_requests(id),
    CHECK (preferred_enemy_count BETWEEN 1 AND 20),
    CHECK (count_influence BETWEEN 0 AND 100),
    CHECK (grouping_bias IN ('same_species', 'book_relationships', 'none')),
    CHECK (variety_enabled IN (0, 1)),
    CHECK (variety_limit IS NULL OR variety_limit BETWEEN 1 AND 20),
    CHECK (include_unprofiled IN (0, 1)),
    CHECK (include_missing_xp IN (0, 1))
);

CREATE TABLE IF NOT EXISTS encounter_difficulty_assessments (
    encounter_result_id INTEGER PRIMARY KEY,
    difficulty_ruleset_id INTEGER NOT NULL,
    slider_value INTEGER NOT NULL,
    party_budget_xp REAL NOT NULL,
    base_monster_xp REAL NOT NULL,
    stat_adjustment_factor REAL NOT NULL,
    adjusted_monster_threat_xp REAL NOT NULL,
    assessed_band TEXT NOT NULL,

    FOREIGN KEY (encounter_result_id) REFERENCES encounter_results(id),
    FOREIGN KEY (difficulty_ruleset_id) REFERENCES difficulty_rulesets(id),
    CHECK (slider_value BETWEEN 0 AND 100),
    CHECK (stat_adjustment_factor BETWEEN 0.70 AND 1.30)
);

CREATE TABLE IF NOT EXISTS encounter_difficulty_adjustment_factors (
    encounter_result_id INTEGER PRIMARY KEY,
    stat_factor REAL NOT NULL,
    action_economy_factor REAL NOT NULL,

    FOREIGN KEY (encounter_result_id) REFERENCES encounter_results(id),
    CHECK (stat_factor BETWEEN 0.70 AND 1.30),
    CHECK (action_economy_factor BETWEEN 0.5 AND 5.0)
);

INSERT OR IGNORE INTO difficulty_rulesets (
    ruleset_key, name, source_url
) VALUES (
    'dnd-2024',
    'Dungeons & Dragons 2024 encounter budgets',
    'https://www.dndbeyond.com/sources/dnd/br-2024/dms-toolbox'
);

INSERT OR IGNORE INTO player_level_difficulty_budgets (
    difficulty_ruleset_id, player_level, low_xp, moderate_xp, high_xp
)
SELECT id, 1, 50, 75, 100 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 2, 100, 150, 200 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 3, 150, 225, 400 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 4, 250, 375, 500 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 5, 500, 750, 1100 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 6, 600, 1000, 1400 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 7, 750, 1300, 1700 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 8, 1000, 1700, 2100 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 9, 1300, 2000, 2600 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 10, 1600, 2300, 3100 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 11, 1900, 2900, 4100 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 12, 2200, 3700, 4700 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 13, 2600, 4200, 5400 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 14, 2900, 4900, 6200 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 15, 3300, 5400, 7800 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 16, 3800, 6100, 9800 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 17, 4500, 7200, 11700 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 18, 5000, 8700, 14200 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 19, 5500, 10700, 17200 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO player_level_difficulty_budgets SELECT id, 20, 6400, 13200, 22000 FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';

INSERT OR IGNORE INTO difficulty_slider_anchors (
    difficulty_ruleset_id, slider_value, label, budget_column
)
SELECT id, 0, 'Low', 'low_xp' FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO difficulty_slider_anchors SELECT id, 50, 'Moderate', 'moderate_xp' FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';
INSERT OR IGNORE INTO difficulty_slider_anchors SELECT id, 100, 'High', 'high_xp' FROM difficulty_rulesets WHERE ruleset_key = 'dnd-2024';

CREATE INDEX IF NOT EXISTS idx_monsters_challenge_rating
    ON monsters (challenge_rating);

CREATE INDEX IF NOT EXISTS idx_monster_environments_environment
    ON monster_environments (environment_id, monster_id);

CREATE INDEX IF NOT EXISTS idx_tactical_profiles_monster
    ON tactical_profiles (monster_id);

CREATE INDEX IF NOT EXISTS idx_tactical_profile_monster_links_monster
    ON tactical_profile_monster_links (monster_id, tactical_profile_id);

CREATE INDEX IF NOT EXISTS idx_tactical_profile_environment_fits_environment
    ON tactical_profile_environment_fits (environment_id, tactical_profile_id);

CREATE INDEX IF NOT EXISTS idx_tactical_evidence_profile
    ON tactical_profile_evidence (tactical_profile_id);
