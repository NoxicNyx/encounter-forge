import sqlite3

connection = sqlite3.connect("db/encounter_forge.db")
connection.execute("PRAGMA foreign_keys = ON")

cursor = connection.cursor()

cursor.execute("""
    SELECT id, name, challenge_rating, hit_points
    FROM monsters;
""")

monsters = cursor.fetchall()

for monster in monsters:
    print(monster)

cursor.execute("""
    PRAGMA table_info(monsters);
""")

columns = cursor.fetchall()
print("\n")
for column in columns:
    print(column)    