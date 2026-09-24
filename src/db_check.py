import sqlite3


connection = sqlite3.connect("db/encounter_forge.db")
cursor = connection.cursor()

tables = [
    "sources",
    "monsters",
    "monster_ability_scores",
    "monster_modifiers",
    "monster_speeds",
    "languages",
    "monster_languages",
    "monster_saving_throws",
    "monster_skills",
    "monster_defenses",
    "monster_actions",
    "attacks",
    "monster_traits",
    "environments",
    "monster_environments",
]


for table in tables:

    cursor.execute(
        f"SELECT COUNT(*) FROM {table}"
    )

    count = cursor.fetchone()[0]

    print(f"{table}: {count}")


connection.close()