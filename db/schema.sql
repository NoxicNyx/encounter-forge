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