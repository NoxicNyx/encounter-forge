import sqlite3

connection = sqlite3.connect("db/encounter_forge.db")

cursor = connection.cursor()

cursor.execute("""
    SELECT name, challenge_rating
    FROM monsters
    WHERE challenge_rating = 10;
""")

results = cursor.fetchall()

for monster in results:
    print(monster)

connection.close()