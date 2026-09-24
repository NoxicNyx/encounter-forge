import sqlite3

with open("db/schema.sql", "r") as file:
    schema = file.read()

connection = sqlite3.connect("db/encounter_forge.db")

connection.execute("PRAGMA foreign_keys = ON")

connection.executescript(schema)

cursor = connection.cursor()

cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table';
""")

tables = cursor.fetchall()

print(tables)

connection.close()