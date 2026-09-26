import sqlite3
import tkinter as tk
from tkinter import ttk


DB_PATH = "db/encounter_forge.db"


# =========================================================
# COLOURS
# =========================================================

BG = "#111318"
PANEL = "#191C23"
PANEL_LIGHT = "#20242D"
BORDER = "#2B303A"

TEXT = "#F1F3F5"
TEXT_MUTED = "#9299A5"

ACCENT = "#8B5CF6"
ACCENT_HOVER = "#A78BFA"

SUCCESS = "#4ADE80"


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_distinct_values(column):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        f"""
        SELECT DISTINCT {column}
        FROM monsters
        WHERE {column} IS NOT NULL
        ORDER BY {column}
        """
    )

    values = [
        row[0]
        for row in cursor.fetchall()
    ]

    connection.close()

    return values


def get_cr_values():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT challenge_rating
        FROM monsters
        WHERE challenge_rating IS NOT NULL
        ORDER BY challenge_rating
        """
    )

    values = [
        row[0]
        for row in cursor.fetchall()
    ]

    connection.close()

    return values


def get_environments():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT name
        FROM environments
        WHERE name IS NOT NULL
        ORDER BY name
        """
    )

    values = [
        row[0]
        for row in cursor.fetchall()
    ]

    connection.close()

    return values


def search_monsters(
    name="",
    cr_operator="",
    cr_value="",
    creature_type="",
    size="",
    environment=""
):
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT DISTINCT
            monsters.id,
            monsters.name,
            monsters.creature_type,
            monsters.size,
            monsters.challenge_rating,
            monsters.armour_class,
            monsters.hit_points,
            monsters.passive_perception
        FROM monsters
    """

    parameters = []

    if environment:

        query += """
            JOIN monster_environments
                ON monsters.id = monster_environments.monster_id

            JOIN environments
                ON monster_environments.environment_id = environments.id
        """

    query += """
        WHERE 1 = 1
    """

    if name:

        query += """
            AND monsters.name LIKE ?
        """

        parameters.append(
            f"%{name}%"
        )

    if cr_operator and cr_value:

        query += f"""
            AND monsters.challenge_rating {cr_operator} ?
        """

        parameters.append(
            float(cr_value)
        )

    if creature_type:

        query += """
            AND monsters.creature_type = ?
        """

        parameters.append(
            creature_type
        )

    if size:

        query += """
            AND monsters.size = ?
        """

        parameters.append(
            size
        )

    if environment:

        query += """
            AND environments.name = ?
        """

        parameters.append(
            environment
        )

    query += """
        ORDER BY monsters.name
    """

    cursor.execute(
        query,
        parameters
    )

    monsters = cursor.fetchall()

    connection.close()

    return monsters


def get_monster(monster_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monsters
        WHERE id = ?
        """,
        (monster_id,)
    )

    monster = cursor.fetchone()

    connection.close()

    return monster


def get_monster_environments(monster_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT environments.name
        FROM environments
        JOIN monster_environments
            ON environments.id = monster_environments.environment_id
        WHERE monster_environments.monster_id = ?
        ORDER BY environments.name
        """,
        (monster_id,)
    )

    environments = [
        row["name"]
        for row in cursor.fetchall()
    ]

    connection.close()

    return environments


# =========================================================
# MAIN WINDOW
# =========================================================

root = tk.Tk()

root.title(
    "Encounter Forge"
)

root.geometry(
    "1250x780"
)

root.minsize(
    1000,
    650
)

root.configure(
    background=BG
)


# =========================================================
# TK VARIABLES
# =========================================================

name_var = tk.StringVar()

cr_operator_var = tk.StringVar(
    value="Any"
)

cr_value_var = tk.StringVar(
    value="Any"
)

type_var = tk.StringVar(
    value="Any"
)

size_var = tk.StringVar(
    value="Any"
)

environment_var = tk.StringVar(
    value="Any"
)


# =========================================================
# STYLES
# =========================================================

style = ttk.Style()

style.theme_use(
    "clam"
)


style.configure(
    ".",
    background=BG,
    foreground=TEXT,
    font=("Segoe UI", 10)
)


style.configure(
    "TFrame",
    background=BG
)


style.configure(
    "Panel.TFrame",
    background=PANEL
)


style.configure(
    "TLabel",
    background=BG,
    foreground=TEXT
)


style.configure(
    "Muted.TLabel",
    background=BG,
    foreground=TEXT_MUTED
)


style.configure(
    "Panel.TLabel",
    background=PANEL,
    foreground=TEXT
)


style.configure(
    "Title.TLabel",
    background=BG,
    foreground=TEXT,
    font=("Segoe UI", 25, "bold")
)


style.configure(
    "Subtitle.TLabel",
    background=BG,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 10)
)


style.configure(
    "Section.TLabel",
    background=PANEL,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 9, "bold")
)


style.configure(
    "TEntry",
    fieldbackground=PANEL_LIGHT,
    foreground=TEXT,
    insertcolor=TEXT,
    borderwidth=0,
    padding=8
)


style.configure(
    "TCombobox",
    fieldbackground=PANEL_LIGHT,
    background=PANEL_LIGHT,
    foreground=TEXT,
    arrowcolor=TEXT_MUTED,
    borderwidth=0,
    padding=6
)


style.map(
    "TCombobox",
    fieldbackground=[
        ("readonly", PANEL_LIGHT)
    ],
    foreground=[
        ("readonly", TEXT)
    ]
)


style.configure(
    "Search.TButton",
    background=ACCENT,
    foreground="white",
    font=("Segoe UI", 10, "bold"),
    padding=(20, 9),
    borderwidth=0
)


style.map(
    "Search.TButton",
    background=[
        ("active", ACCENT_HOVER)
    ]
)


style.configure(
    "Clear.TButton",
    background=PANEL_LIGHT,
    foreground=TEXT_MUTED,
    padding=(14, 8),
    borderwidth=0
)


style.map(
    "Clear.TButton",
    background=[
        ("active", BORDER)
    ],
    foreground=[
        ("active", TEXT)
    ]
)


style.configure(
    "Treeview",
    background=PANEL,
    foreground=TEXT,
    fieldbackground=PANEL,
    borderwidth=0,
    rowheight=34,
    font=("Segoe UI", 10)
)


style.configure(
    "Treeview.Heading",
    background=PANEL_LIGHT,
    foreground=TEXT_MUTED,
    borderwidth=0,
    font=("Segoe UI", 9, "bold"),
    padding=8
)


style.map(
    "Treeview",
    background=[
        ("selected", "#33245A")
    ],
    foreground=[
        ("selected", TEXT)
    ]
)


# =========================================================
# HEADER
# =========================================================

header = ttk.Frame(
    root
)

header.pack(
    fill="x",
    padx=32,
    pady=(28, 20)
)


brand_frame = ttk.Frame(
    header
)

brand_frame.pack(
    side="left"
)


# Small purple marker

brand_marker = tk.Label(
    brand_frame,
    text="◆",
    background=BG,
    foreground=ACCENT,
    font=("Segoe UI", 16)
)

brand_marker.pack(
    side="left",
    padx=(0, 10)
)


title_frame = ttk.Frame(
    brand_frame
)

title_frame.pack(
    side="left"
)


ttk.Label(
    title_frame,
    text="Encounter Forge",
    style="Title.TLabel"
).pack(
    anchor="w"
)


ttk.Label(
    title_frame,
    text="Monster intelligence database",
    style="Subtitle.TLabel"
).pack(
    anchor="w"
)


# Right-side database indicator

database_indicator = ttk.Frame(
    header
)

database_indicator.pack(
    side="right",
    pady=5
)


tk.Label(
    database_indicator,
    text="●",
    background=BG,
    foreground=SUCCESS,
    font=("Segoe UI", 10)
).pack(
    side="left",
    padx=(0, 6)
)


ttk.Label(
    database_indicator,
    text="SQLite database",
    style="Muted.TLabel"
).pack(
    side="left"
)


# =========================================================
# SEARCH PANEL
# =========================================================

search_panel = tk.Frame(
    root,
    background=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

search_panel.pack(
    fill="x",
    padx=32,
    pady=(0, 18)
)


# Search title

tk.Label(
    search_panel,
    text="SEARCH MONSTERS",
    background=PANEL,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 9, "bold")
).grid(
    row=0,
    column=0,
    columnspan=10,
    sticky="w",
    padx=18,
    pady=(15, 10)
)


# Name

tk.Label(
    search_panel,
    text="Name",
    background=PANEL,
    foreground=TEXT_MUTED
).grid(
    row=1,
    column=0,
    sticky="w",
    padx=(18, 6),
    pady=(0, 6)
)


name_entry = ttk.Entry(
    search_panel,
    textvariable=name_var,
    width=25
)

name_entry.grid(
    row=2,
    column=0,
    columnspan=2,
    sticky="ew",
    padx=(18, 12),
    pady=(0, 18)
)


# CR operator

tk.Label(
    search_panel,
    text="Challenge Rating",
    background=PANEL,
    foreground=TEXT_MUTED
).grid(
    row=1,
    column=2,
    columnspan=2,
    sticky="w",
    padx=6,
    pady=(0, 6)
)


cr_operator_combo = ttk.Combobox(
    search_panel,
    textvariable=cr_operator_var,
    values=[
        "Any",
        "=",
        ">",
        ">=",
        "<",
        "<="
    ],
    state="readonly",
    width=5
)

cr_operator_combo.grid(
    row=2,
    column=2,
    sticky="w",
    padx=(6, 4),
    pady=(0, 18)
)


cr_value_combo = ttk.Combobox(
    search_panel,
    textvariable=cr_value_var,
    values=[
        "Any"
    ] + get_cr_values(),
    state="readonly",
    width=9
)

cr_value_combo.grid(
    row=2,
    column=3,
    sticky="w",
    padx=(4, 12),
    pady=(0, 18)
)


# Creature type

tk.Label(
    search_panel,
    text="Creature Type",
    background=PANEL,
    foreground=TEXT_MUTED
).grid(
    row=1,
    column=4,
    sticky="w",
    padx=6,
    pady=(0, 6)
)


type_combo = ttk.Combobox(
    search_panel,
    textvariable=type_var,
    values=[
        "Any"
    ] + get_distinct_values("creature_type"),
    state="readonly",
    width=18
)

type_combo.grid(
    row=2,
    column=4,
    sticky="ew",
    padx=6,
    pady=(0, 18)
)


# Size

tk.Label(
    search_panel,
    text="Size",
    background=PANEL,
    foreground=TEXT_MUTED
).grid(
    row=1,
    column=5,
    sticky="w",
    padx=6,
    pady=(0, 6)
)


size_combo = ttk.Combobox(
    search_panel,
    textvariable=size_var,
    values=[
        "Any"
    ] + get_distinct_values("size"),
    state="readonly",
    width=12
)

size_combo.grid(
    row=2,
    column=5,
    sticky="ew",
    padx=6,
    pady=(0, 18)
)


# Environment

tk.Label(
    search_panel,
    text="Environment",
    background=PANEL,
    foreground=TEXT_MUTED
).grid(
    row=1,
    column=6,
    sticky="w",
    padx=6,
    pady=(0, 6)
)


environment_combo = ttk.Combobox(
    search_panel,
    textvariable=environment_var,
    values=[
        "Any"
    ] + get_environments(),
    state="readonly",
    width=20
)

environment_combo.grid(
    row=2,
    column=6,
    sticky="ew",
    padx=6,
    pady=(0, 18)
)


# Search button

search_button = ttk.Button(
    search_panel,
    text="SEARCH",
    style="Search.TButton",
    command=lambda: perform_search()
)

search_button.grid(
    row=2,
    column=7,
    padx=(12, 18),
    pady=(0, 18)
)


# Configure search columns

for column in range(8):
    search_panel.grid_columnconfigure(
        column,
        weight=1
    )


# =========================================================
# CONTENT AREA
# =========================================================

content = ttk.Frame(
    root
)

content.pack(
    fill="both",
    expand=True,
    padx=32,
    pady=(0, 15)
)


# =========================================================
# RESULTS PANEL
# =========================================================

results_panel = tk.Frame(
    content,
    background=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

results_panel.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(0, 10)
)


# Results header

results_header = tk.Frame(
    results_panel,
    background=PANEL
)

results_header.pack(
    fill="x",
    padx=18,
    pady=(15, 10)
)


tk.Label(
    results_header,
    text="MONSTERS",
    background=PANEL,
    foreground=TEXT,
    font=("Segoe UI", 10, "bold")
).pack(
    side="left"
)


result_label = tk.Label(
    results_header,
    text="No search performed",
    background=PANEL,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 9)
)

result_label.pack(
    side="right"
)


# Tree container

tree_container = tk.Frame(
    results_panel,
    background=PANEL
)

tree_container.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=(0, 10)
)


columns = (
    "name",
    "type",
    "size",
    "cr",
    "ac",
    "hp"
)


results_tree = ttk.Treeview(
    tree_container,
    columns=columns,
    show="headings",
    selectmode="browse"
)


results_tree.heading(
    "name",
    text="Monster"
)

results_tree.heading(
    "type",
    text="Type"
)

results_tree.heading(
    "size",
    text="Size"
)

results_tree.heading(
    "cr",
    text="CR"
)

results_tree.heading(
    "ac",
    text="AC"
)

results_tree.heading(
    "hp",
    text="HP"
)


results_tree.column(
    "name",
    width=190,
    anchor="w"
)

results_tree.column(
    "type",
    width=110,
    anchor="w"
)

results_tree.column(
    "size",
    width=80,
    anchor="center"
)

results_tree.column(
    "cr",
    width=55,
    anchor="center"
)

results_tree.column(
    "ac",
    width=55,
    anchor="center"
)

results_tree.column(
    "hp",
    width=65,
    anchor="center"
)


results_tree.pack(
    side="left",
    fill="both",
    expand=True
)


results_scrollbar = ttk.Scrollbar(
    tree_container,
    orient="vertical",
    command=results_tree.yview
)

results_scrollbar.pack(
    side="right",
    fill="y"
)


results_tree.configure(
    yscrollcommand=results_scrollbar.set
)


# =========================================================
# DETAILS PANEL
# =========================================================

details_panel = tk.Frame(
    content,
    background=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

details_panel.pack(
    side="right",
    fill="both",
    expand=True
)


# Details header

details_header = tk.Frame(
    details_panel,
    background=PANEL
)

details_header.pack(
    fill="x",
    padx=20,
    pady=(18, 5)
)


monster_name_label = tk.Label(
    details_header,
    text="Select a monster",
    background=PANEL,
    foreground=TEXT,
    font=("Segoe UI", 20, "bold")
)

monster_name_label.pack(
    anchor="w"
)


monster_type_label = tk.Label(
    details_header,
    text="",
    background=PANEL,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 10)
)

monster_type_label.pack(
    anchor="w",
    pady=(2, 10)
)


# Details content

details_container = tk.Frame(
    details_panel,
    background=PANEL
)

details_container.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=5
)


details_text = tk.Text(
    details_container,
    background=PANEL,
    foreground=TEXT,
    insertbackground=TEXT,
    selectbackground="#33245A",
    selectforeground=TEXT,
    relief="flat",
    borderwidth=0,
    font=("Consolas", 10),
    wrap="word",
    padx=5,
    pady=5
)

details_text.pack(
    side="left",
    fill="both",
    expand=True
)


details_scrollbar = ttk.Scrollbar(
    details_container,
    orient="vertical",
    command=details_text.yview
)

details_scrollbar.pack(
    side="right",
    fill="y"
)


details_text.configure(
    yscrollcommand=details_scrollbar.set
)


# =========================================================
# DETAIL TEXT STYLES
# =========================================================

details_text.tag_configure(
    "section",
    foreground=ACCENT_HOVER,
    font=("Segoe UI", 10, "bold"),
    spacing1=12,
    spacing3=5
)

details_text.tag_configure(
    "label",
    foreground=TEXT_MUTED,
    font=("Segoe UI", 9, "bold")
)

details_text.tag_configure(
    "value",
    foreground=TEXT,
    font=("Segoe UI", 10)
)


# =========================================================
# STATUS BAR
# =========================================================

status_bar = tk.Frame(
    root,
    background=PANEL_LIGHT,
    height=30
)

status_bar.pack(
    fill="x",
    side="bottom"
)


status_label = tk.Label(
    status_bar,
    text="Ready",
    background=PANEL_LIGHT,
    foreground=TEXT_MUTED,
    font=("Segoe UI", 9)
)

status_label.pack(
    side="left",
    padx=32,
    pady=6
)


# =========================================================
# SEARCH FUNCTION
# =========================================================

def perform_search():

    name = name_var.get().strip()

    cr_operator = cr_operator_var.get()

    cr_value = cr_value_var.get()

    creature_type = type_var.get()

    size = size_var.get()

    environment = environment_var.get()


    if cr_operator == "Any":
        cr_operator = ""

    if cr_value == "Any":
        cr_value = ""

    if creature_type == "Any":
        creature_type = ""

    if size == "Any":
        size = ""

    if environment == "Any":
        environment = ""


    try:

        monsters = search_monsters(
            name=name,
            cr_operator=cr_operator,
            cr_value=cr_value,
            creature_type=creature_type,
            size=size,
            environment=environment
        )

    except Exception as error:

        result_label.config(
            text="Database error"
        )

        status_label.config(
            text=f"Error: {error}"
        )

        return


    # Clear results

    for item in results_tree.get_children():

        results_tree.delete(
            item
        )


    details_text.delete(
        "1.0",
        tk.END
    )


    monster_name_label.config(
        text="Select a monster"
    )

    monster_type_label.config(
        text=""
    )


    # Add results

    for monster in monsters:

        results_tree.insert(
            "",
            "end",
            iid=str(
                monster["id"]
            ),
            values=(
                monster["name"],
                monster["creature_type"] or "-",
                monster["size"] or "-",
                monster["challenge_rating"],
                monster["armour_class"] or "-",
                monster["hit_points"] or "-"
            )
        )


    result_label.config(
        text=f"{len(monsters)} result"
        + (
            "s"
            if len(monsters) != 1
            else ""
        )
    )


    status_label.config(
        text=f"{len(monsters)} monster(s) found"
    )


# =========================================================
# CLEAR FILTERS
# =========================================================

def clear_filters():

    name_var.set("")

    cr_operator_var.set("Any")

    cr_value_var.set("Any")

    type_var.set("Any")

    size_var.set("Any")

    environment_var.set("Any")

    for item in results_tree.get_children():

        results_tree.delete(
            item
        )


    details_text.delete(
        "1.0",
        tk.END
    )


    monster_name_label.config(
        text="Select a monster"
    )

    monster_type_label.config(
        text=""
    )

    result_label.config(
        text="No search performed"
    )

    status_label.config(
        text="Ready"
    )


# =========================================================
# MONSTER DETAILS
# =========================================================

def show_monster(event):

    selection = results_tree.selection()

    if not selection:
        return


    monster_id = selection[0]

    monster = get_monster(
        monster_id
    )


    if monster is None:
        return


    environments = get_monster_environments(
        monster_id
    )


    # Header

    monster_name_label.config(
        text=monster["name"]
    )


    monster_type = monster["creature_type"] or "Unknown"

    monster_size = monster["size"] or "Unknown"

    monster_type_label.config(
        text=f"{monster_size} {monster_type}"
    )


    # Clear details

    details_text.delete(
        "1.0",
        tk.END
    )


    # Combat stats

    details_text.insert(
        tk.END,
        "COMBAT\n",
        "section"
    )


    combat_stats = [
        ("Challenge Rating", monster["challenge_rating"]),
        ("Armour Class", monster["armour_class"]),
        ("Hit Points", monster["hit_points"]),
        ("Hit Dice", monster["hit_dice"]),
        ("Proficiency Bonus", monster["proficiency_bonus"]),
        ("Initiative Bonus", monster["initiative_bonus"]),
        ("Passive Perception", monster["passive_perception"]),
    ]


    for label, value in combat_stats:

        if value is None:
            value = "-"

        details_text.insert(
            tk.END,
            f"{label:<22}",
            "label"
        )

        details_text.insert(
            tk.END,
            f"{value}\n",
            "value"
        )


    # Movement

    details_text.insert(
        tk.END,
        "\nMOVEMENT & SENSES\n",
        "section"
    )


    movement_stats = [
        ("Normal Sight", monster["normal_sight_range"]),
        ("Darkvision", monster["darkvision_range"]),
        ("Blindsight", monster["blindsight_range"]),
        ("Tremorsense", monster["tremorsense_range"]),
        ("Truesight", monster["truesight_range"]),
    ]


    for label, value in movement_stats:

        if value is None:
            continue

        details_text.insert(
            tk.END,
            f"{label:<22}",
            "label"
        )

        details_text.insert(
            tk.END,
            f"{value}\n",
            "value"
        )


    # Environment

    details_text.insert(
        tk.END,
        "\nENVIRONMENTS\n",
        "section"
    )


    if environments:

        details_text.insert(
            tk.END,
            "  • " + "\n  • ".join(environments),
            "value"
        )

        details_text.insert(
            tk.END,
            "\n"
        )

    else:

        details_text.insert(
            tk.END,
            "No environment data available.\n",
            "value"
        )


    # Remaining database fields

    details_text.insert(
        tk.END,
        "\nDATABASE RECORD\n",
        "section"
    )


    excluded_fields = {
        "id",
        "name",
        "creature_type",
        "size",
        "challenge_rating",
        "armour_class",
        "hit_points",
        "hit_dice",
        "proficiency_bonus",
        "initiative_bonus",
        "passive_perception",
        "normal_sight_range",
        "darkvision_range",
        "blindsight_range",
        "tremorsense_range",
        "truesight_range",
    }


    for column in monster.keys():

        if column in excluded_fields:
            continue


        value = monster[column]

        if value is None:
            value = "-"


        details_text.insert(
            tk.END,
            f"{column:<22}",
            "label"
        )

        details_text.insert(
            tk.END,
            f"{value}\n",
            "value"
        )


# =========================================================
# EVENTS
# =========================================================

results_tree.bind(
    "<<TreeviewSelect>>",
    show_monster
)


name_entry.bind(
    "<Return>",
    lambda event: perform_search()
)


# =========================================================
# START
# =========================================================

root.mainloop()