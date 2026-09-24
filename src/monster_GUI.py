import sqlite3
import tkinter as tk
from tkinter import ttk


DB_PATH = "db/encounter_forge.db"


def find_monsters(search_term):
    """Find every monster whose name contains the search term."""

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
        (f"%{search_term}%",)
    )

    monsters = cursor.fetchall()

    connection.close()

    return monsters


def show_monster(event):
    """Display the selected monster's details."""

    selection = monster_list.curselection()

    if not selection:
        return

    selected_index = selection[0]
    monster = search_results[selected_index]

    details_text.delete("1.0", tk.END)

    for column in monster.keys():
        value = monster[column]

        if value is None:
            value = "-"

        details_text.insert(
            tk.END,
            f"{column}: {value}\n"
        )


def search():
    """Search the database and update the results list."""

    global search_results

    search_term = search_entry.get().strip()

    if not search_term:
        return

    search_results = find_monsters(search_term)

    monster_list.delete(0, tk.END)
    details_text.delete("1.0", tk.END)

    result_label.config(
        text=f"Found {len(search_results)} monster(s)"
    )

    for monster in search_results:
        monster_list.insert(
            tk.END,
            monster["name"]
        )


# ---------------------------------------------------------
# Main window
# ---------------------------------------------------------

root = tk.Tk()

root.title("Encounter Forge")
root.geometry("1000x650")


# ---------------------------------------------------------
# Title
# ---------------------------------------------------------

title_label = ttk.Label(
    root,
    text="Encounter Forge",
    font=("Arial", 24, "bold")
)

title_label.pack(
    padx=20,
    pady=(20, 10)
)


subtitle_label = ttk.Label(
    root,
    text="Monster Database",
    font=("Arial", 12)
)

subtitle_label.pack(
    pady=(0, 20)
)


# ---------------------------------------------------------
# Search area
# ---------------------------------------------------------

search_frame = ttk.Frame(root)

search_frame.pack(
    fill="x",
    padx=20
)


search_label = ttk.Label(
    search_frame,
    text="Search monsters:"
)

search_label.pack(
    side="left",
    padx=(0, 10)
)


search_entry = ttk.Entry(
    search_frame,
    width=40
)

search_entry.pack(
    side="left",
    padx=(0, 10)
)


search_button = ttk.Button(
    search_frame,
    text="Search",
    command=search
)

search_button.pack(
    side="left"
)


# Allow pressing Enter to search
search_entry.bind(
    "<Return>",
    lambda event: search()
)


# ---------------------------------------------------------
# Result count
# ---------------------------------------------------------

result_label = ttk.Label(
    root,
    text="Enter a monster name to search."
)

result_label.pack(
    anchor="w",
    padx=20,
    pady=(15, 5)
)


# ---------------------------------------------------------
# Main content area
# ---------------------------------------------------------

content_frame = ttk.Frame(root)

content_frame.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=10
)


# ---------------------------------------------------------
# Monster list
# ---------------------------------------------------------

list_frame = ttk.LabelFrame(
    content_frame,
    text="Monsters"
)

list_frame.pack(
    side="left",
    fill="y",
    padx=(0, 10)
)


monster_list = tk.Listbox(
    list_frame,
    width=30,
    height=25
)

monster_list.pack(
    side="left",
    fill="y",
    padx=5,
    pady=5
)


list_scrollbar = ttk.Scrollbar(
    list_frame,
    orient="vertical",
    command=monster_list.yview
)

list_scrollbar.pack(
    side="right",
    fill="y"
)


monster_list.config(
    yscrollcommand=list_scrollbar.set
)


monster_list.bind(
    "<<ListboxSelect>>",
    show_monster
)


# ---------------------------------------------------------
# Monster details
# ---------------------------------------------------------

details_frame = ttk.LabelFrame(
    content_frame,
    text="Monster Details"
)

details_frame.pack(
    side="right",
    fill="both",
    expand=True
)


details_text = tk.Text(
    details_frame,
    wrap="word",
    font=("Consolas", 11)
)

details_text.pack(
    side="left",
    fill="both",
    expand=True,
    padx=5,
    pady=5
)


details_scrollbar = ttk.Scrollbar(
    details_frame,
    orient="vertical",
    command=details_text.yview
)

details_scrollbar.pack(
    side="right",
    fill="y"
)


details_text.config(
    yscrollcommand=details_scrollbar.set
)


# ---------------------------------------------------------
# Start application
# ---------------------------------------------------------

search_results = []

root.mainloop()