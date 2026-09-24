import sqlite3

connection = sqlite3.connect("db/encounter_forge.db")

cursor = connection.cursor()

cursor.execute("""
    SELECT name, challenge_rating
    FROM monsters
    WHERE challenge_rating > 3
    ORDER BY challenge_rating DESC;
""")

results = cursor.fetchall()

for name, challenge_rating in results:
    print(f"{name}: CR {challenge_rating}")

connection.close()