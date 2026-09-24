import sqlite3


DB_PATH = "db/encounter_forge.db"


def find_monsters(name):
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monsters
        WHERE name LIKE ?
        ORDER BY name
        """,
        (f"%{name}%",)
    )

    monsters = cursor.fetchall()

    connection.close()

    return monsters


name = input("Enter monster name: ")

monsters = find_monsters(name)

print()
print(f"Found {len(monsters)} monster(s) matching '{name}'.")

for monster in monsters:
    print()
    print("=" * 60)
    print(monster["name"])
    print("=" * 60)

    for column in monster.keys():
        print(f"{column}: {monster[column]}")