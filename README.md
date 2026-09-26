# Encounter Forge

A Python-based D&D encounter generator using a relational SQL database.

## Goals

- Store structured monster data
- Model monster relationships and environments
- Generate coherent D&D encounters
- Learn Python, SQL and Git/GitHub

## Database build

Build the Open5e SRD 2024 catalogue and import the book-anchored tactical
workbook in one command:

```powershell
python src/database/build_database.py --tactical-workbook "C:\path\to\Encounter_Forge_Tactical_Dataset_v0_3_book_anchored.xlsx"
```

The database keeps Open5e stat-block data separate from book-derived tactical
profiles. Tactical profiles retain their workbook name when no exact current
Open5e creature match exists, so an import never drops source evidence. Exact
and whole-token substring matches let a source entry such as `Goblin` inform
`Goblin Warrior` without matching unrelated partial words. The environment
enrichment uses the same rule.

## Difficulty calculator

`src/encounter_difficulty.py` applies the SRD 2024 XP budget for every player
level. A 0–100 slider interpolates from Low (0), through Moderate (50), to High
(100), then compares the selected monster group against the resulting party
budget. Monster XP is the official primary threat value; a bounded adjustment
also compares AC, hit points, and strongest parsed attack against same-CR
Open5e peers. The encounter builder also exposes a Count Impact slider: 0 uses
the 2024 base-XP approach, while 100 applies the 2014 multiple-monster
action-economy multiplier, with intermediate values blending the two.

Preview it with `python src/encounter_difficulty_gui.py`. The standalone panel
has per-player level controls, a Low-to-High slider, environment selection, and
a monster-group assessment. It deliberately remains separate from the existing
monster search window while the encounter generator is built.

## Encounter builder

Run `python src/encounter_forge_qt.py` for the Qt encounter-builder application.
The previous Tkinter entry point remains available as a development fallback;
the Qt application is the supported end-user interface.
It returns several groups within the selected XP budget and scores them for
environment fit, tactical roles, pairwise compatibility, and the grouping mode
you select: Same species (first name word), Book links, or No bias. Book Links
mode is strict: every distinct creature in a result must connect to another
distinct creature through imported source-backed relationship evidence.

By default, the generator uses only creatures with tactical profiles and
published XP. The UI offers opt-in buttons for unprofiled creatures and
missing-XP creatures; the latter receive a clearly marked XP estimate from
published peers at the same CR. Selected recommendations persist the party,
difficulty, count preference and impact, grouping mode, variety limit, and data
coverage toggles alongside the generated monster group.

## Windows package

Build the portable Windows application from the repository root:

```powershell
python -m PyInstaller --noconfirm --clean --windowed --onedir --name EncounterForge --runtime-hook src\qt_runtime_hook.py --add-data "db\encounter_forge.db;db" --add-data "db\schema.sql;db" src\encounter_forge_qt.py
```

Launch `dist\EncounterForge\EncounterForge.exe`. The first run copies the
seed catalogue to `%LOCALAPPDATA%\Encounter Forge\encounter_forge.db`; later
runs use that copy, so saved encounter history and generator settings survive
updates to the application folder.
