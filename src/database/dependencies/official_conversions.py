"""Official 2014-to-2024 stat-block conversions used by the importer.

Source: D&D Beyond, *How to Use a Monster*, Stat Block Conversions table.
The target may be a role equivalent rather than the same creature, so this is
deliberately separate from the narrower creature-family taxonomy.
"""

from __future__ import annotations

import sqlite3


SOURCE_REFERENCE = "https://www.dndbeyond.com/sources/dnd/br-2024/how-to-use-a-monster"

# All rows in the official table.  The importer only creates a link when the
# named 2024 target is present in the local Open5e SRD 2024 catalogue.
CONVERSIONS: dict[str, str] = {
    "Aarakocra": "Aarakocra Skirmisher",
    "Acolyte": "Priest Acolyte",
    "Adult Blue Dracolich": "Dracolich",
    "Androsphinx": "Sphinx of Valor",
    "Azer": "Azer Sentinel",
    "Bugbear": "Bugbear Warrior",
    "Bullywug": "Bullywug Warrior",
    "Centaur": "Centaur Trooper",
    "Cult fanatic": "Cultist Fanatic",
    "Cyclops": "Cyclops Sentry",
    "Deep Gnome": "Scout",
    "Drow": "Priest Acolyte",
    "Drow elite warrior": "Gladiator",
    "Drow mage": "Bandit Deceiver",
    "Drow priestess of Lolth": "Fiend Cultist",
    "Duergar": "Spy",
    "Duodrone": "Modron Duodrone",
    "Faerie dragon": "Faerie Dragon Adult",
    "Fire Snake": "Salamander Fire Snake",
    "Flying sword": "Animated Flying Sword",
    "Gas Spore": "Gas Spore Fungus",
    "Giant Poisonous Snake": "Giant Venomous Snake",
    "Gnoll": "Gnoll Warrior",
    "Goblin": "Goblin Warrior",
    "Grick alpha": "Grick Ancient",
    "Gynosphinx": "Sphinx of Lore",
    "Half-Ogre (Ogrillon)": "Ogrillon Ogre",
    "Half-Red Dragon Veteran": "Half-Dragon",
    "Hobgoblin": "Hobgoblin Warrior",
    "Kobold": "Kobold Warrior",
    "Lizardfolk": "Scout",
    "Lizardfolk shaman": "Lizardfolk Geomancer",
    "Lizard king/queen": "Lizardfolk Sovereign",
    "Merfolk": "Merfolk Skirmisher",
    "Minotaur": "Minotaur of Baphomet",
    "Monodrone": "Modron Monodrone",
    "Orc": "Tough",
    "Orc Eye of Gruumsh": "Cultist Fanatic",
    "Orc war chief": "Tough Boss",
    "Orog": "Berserker",
    "Pentadrone": "Modron Pentadrone",
    "Poisonous Snake": "Venomous Snake",
    "Quadrone": "Modron Quadrone",
    "Quaggoth Spore Servant": "Myconid Spore Servant",
    "Quipper": "Piranha",
    "Rug of smothering": "Animated Rug of Smothering",
    "Sahuagin": "Sahuagin Warrior",
    "Sahuagin priestess": "Sahuagin Priest",
    "Shrieker": "Shrieker Fungus",
    "Swarm of Poisonous Snakes": "Swarm of Venomous Snakes",
    "Swarm of Quippers": "Swarm of Piranhas",
    "Thri-kreen": "Thri-kreen Marauder",
    "Thug": "Tough",
    "Tribal warrior": "Warrior Infantry",
    "Tridrone": "Modron Tridrone",
    "Veteran": "Warrior Veteran",
    "Young Red Shadow Dragon": "Shadow Dragon",
    "Yuan-ti pureblood": "Yuan-ti Infiltrator",
}

ALIAS_REFERENCE = "D&D Basic Rules (2014) and Free Rules (2024) creature stat blocks"
NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "Erinys": ("Erinyes",),
    "Doppelg�nger": ("Doppelganger",),
    "Succubus/Incubus": ("Succubus", "Incubus"),
}


def target_for(source_name: str) -> str | None:
    """Return an official replacement, ignoring source-name case."""
    source_key = source_name.casefold()
    return next(
        (target for source, target in CONVERSIONS.items() if source.casefold() == source_key),
        None,
    )


def alias_targets_for(source_name: str) -> tuple[str, ...]:
    source_key = source_name.casefold()
    return next(
        (targets for source, targets in NAME_ALIASES.items() if source.casefold() == source_key),
        (),
    )


def populate_conversion_catalogue(cursor: sqlite3.Cursor) -> int:
    cursor.executemany(
        """
        INSERT INTO creature_edition_conversions (source_name, target_name, source_reference)
        VALUES (?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET
            target_name = excluded.target_name,
            source_reference = excluded.source_reference
        """,
        [(source, target, SOURCE_REFERENCE) for source, target in CONVERSIONS.items()],
    )
    cursor.executemany(
        """
        INSERT INTO creature_name_aliases (source_name, target_name, source_reference)
        VALUES (?, ?, ?)
        ON CONFLICT(source_name, target_name) DO UPDATE SET
            source_reference = excluded.source_reference
        """,
        [
            (source, target, ALIAS_REFERENCE)
            for source, targets in NAME_ALIASES.items()
            for target in targets
        ],
    )
    return len(CONVERSIONS) + sum(len(targets) for targets in NAME_ALIASES.values())
