"""Standalone GUI for previewing the encounter-difficulty calculator."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from encounter_difficulty import assess_encounter, calculate_party_capacity


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "db" / "encounter_forge.db"


class DifficultyPreview(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Encounter Forge — Difficulty Preview")
        self.minsize(850, 620)
        self.connection = sqlite3.connect(DB_PATH)
        self.connection.row_factory = sqlite3.Row
        self.party_size = tk.IntVar(value=4)
        self.slider_value = tk.IntVar(value=50)
        self.environment = tk.StringVar(value="Any environment")
        self.monster_choice = tk.StringVar()
        self.monster_quantity = tk.IntVar(value=1)
        self.level_vars: list[tk.IntVar] = []
        self.selected_monsters: dict[int, int] = {}
        self.monster_options = self._load_monsters()
        self._build()
        self._rebuild_player_levels()
        self._refresh_assessment()

    def destroy(self) -> None:
        self.connection.close()
        super().destroy()

    def _load_monsters(self) -> dict[str, int]:
        rows = self.connection.execute(
            """
            SELECT id, name, challenge_rating, experience_points
            FROM monsters
            WHERE experience_points IS NOT NULL
            ORDER BY name
            """
        )
        return {
            f"{row['name']} (CR {row['challenge_rating']}, {row['experience_points']} XP)": row["id"]
            for row in rows
        }

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Encounter difficulty", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="SRD 2024 budgets with a bounded same-CR stat adjustment for monsters.",
        ).pack(anchor="w", pady=(0, 14))

        controls = ttk.LabelFrame(outer, text="Party and target", padding=12)
        controls.pack(fill="x")
        ttk.Label(controls, text="Players").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(controls, from_=1, to=10, textvariable=self.party_size, width=5, command=self._rebuild_player_levels).grid(row=1, column=0, sticky="w", padx=(0, 16))
        ttk.Label(controls, text="Environment").grid(row=0, column=1, sticky="w")
        environments = ["Any environment"] + [
            row[0] for row in self.connection.execute("SELECT name FROM environments ORDER BY name")
        ]
        ttk.Combobox(controls, textvariable=self.environment, values=environments, state="readonly", width=24).grid(row=1, column=1, sticky="w", padx=(0, 16))
        ttk.Label(controls, text="Difficulty slider").grid(row=0, column=2, sticky="w")
        ttk.Scale(controls, from_=0, to=100, orient="horizontal", variable=self.slider_value, command=lambda _: self._refresh_assessment()).grid(row=1, column=2, sticky="ew")
        self.slider_label = ttk.Label(controls)
        self.slider_label.grid(row=1, column=3, sticky="w", padx=(8, 0))
        controls.columnconfigure(2, weight=1)

        self.level_frame = ttk.LabelFrame(outer, text="Player levels", padding=12)
        self.level_frame.pack(fill="x", pady=(12, 0))

        monster_frame = ttk.LabelFrame(outer, text="Monster group", padding=12)
        monster_frame.pack(fill="x", pady=(12, 0))
        self.monster_combo = ttk.Combobox(monster_frame, textvariable=self.monster_choice, values=list(self.monster_options), state="readonly", width=52)
        self.monster_combo.grid(row=0, column=0, sticky="ew")
        ttk.Spinbox(monster_frame, from_=1, to=30, textvariable=self.monster_quantity, width=5).grid(row=0, column=1, padx=8)
        ttk.Button(monster_frame, text="Add monster", command=self._add_monster).grid(row=0, column=2)
        monster_frame.columnconfigure(0, weight=1)
        self.monster_tree = ttk.Treeview(monster_frame, columns=("monster", "quantity"), show="headings", height=5)
        self.monster_tree.heading("monster", text="Monster")
        self.monster_tree.heading("quantity", text="Qty")
        self.monster_tree.column("monster", width=520)
        self.monster_tree.column("quantity", width=80, anchor="center")
        self.monster_tree.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(monster_frame, text="Remove selected", command=self._remove_selected).grid(row=1, column=2, padx=(8, 0))

        result = ttk.LabelFrame(outer, text="Assessment", padding=12)
        result.pack(fill="both", expand=True, pady=(12, 0))
        self.result_text = tk.Text(result, height=9, wrap="word", state="disabled", font=("Consolas", 10))
        self.result_text.pack(fill="both", expand=True)

    def _rebuild_player_levels(self) -> None:
        for widget in self.level_frame.winfo_children():
            widget.destroy()
        old_levels = [variable.get() for variable in self.level_vars]
        self.level_vars = []
        for player_number in range(self.party_size.get()):
            level = old_levels[player_number] if player_number < len(old_levels) else 1
            variable = tk.IntVar(value=level)
            self.level_vars.append(variable)
            ttk.Label(self.level_frame, text=f"Player {player_number + 1}").grid(row=0, column=player_number, padx=5)
            spinbox = ttk.Spinbox(self.level_frame, from_=1, to=20, textvariable=variable, width=5, command=self._refresh_assessment)
            spinbox.grid(row=1, column=player_number, padx=5)
            spinbox.bind("<FocusOut>", lambda _: self._refresh_assessment())
        self._refresh_assessment()

    def _add_monster(self) -> None:
        monster_id = self.monster_options.get(self.monster_choice.get())
        if monster_id is None:
            messagebox.showinfo("Choose a monster", "Select a monster before adding it.")
            return
        self.selected_monsters[monster_id] = self.selected_monsters.get(monster_id, 0) + self.monster_quantity.get()
        self._refresh_monster_tree()
        self._refresh_assessment()

    def _remove_selected(self) -> None:
        selection = self.monster_tree.selection()
        if selection:
            self.selected_monsters.pop(int(selection[0]), None)
            self._refresh_monster_tree()
            self._refresh_assessment()

    def _refresh_monster_tree(self) -> None:
        for item in self.monster_tree.get_children():
            self.monster_tree.delete(item)
        names = {monster_id: name for name, monster_id in self.monster_options.items()}
        for monster_id, quantity in self.selected_monsters.items():
            self.monster_tree.insert("", "end", iid=str(monster_id), values=(names[monster_id], quantity))

    def _refresh_assessment(self) -> None:
        try:
            levels = [variable.get() for variable in self.level_vars]
            if not levels:
                return
            if self.selected_monsters:
                assessment = assess_encounter(
                    self.connection,
                    levels,
                    list(self.selected_monsters.items()),
                    int(self.slider_value.get()),
                )
                text = (
                    f"Target: {assessment.party.requested_budget_xp:,.0f} XP "
                    f"({assessment.party.requested_label}, slider {assessment.party.slider_value})\n"
                    f"Party bands: Low {assessment.party.low_xp:,.0f} | "
                    f"Moderate {assessment.party.moderate_xp:,.0f} | "
                    f"High {assessment.party.high_xp:,.0f}\n\n"
                    f"Monster XP: {assessment.base_monster_xp:,.0f}\n"
                    f"Stat adjustment: ×{assessment.stat_adjustment_factor:.2f}\n"
                    f"Adjusted threat: {assessment.adjusted_monster_threat_xp:,.0f} XP\n"
                    f"Assessed band: {assessment.assessed_band}\n"
                    f"Requested target: {'within budget' if assessment.is_within_requested_budget else 'over budget'}"
                )
                slider_text = f"{assessment.party.requested_label} ({assessment.party.slider_value})"
            else:
                capacity = calculate_party_capacity(self.connection, levels, int(self.slider_value.get()))
                text = (
                    f"Target: {capacity.requested_budget_xp:,.0f} XP "
                    f"({capacity.requested_label}, slider {capacity.slider_value})\n"
                    f"Party bands: Low {capacity.low_xp:,.0f} | "
                    f"Moderate {capacity.moderate_xp:,.0f} | High {capacity.high_xp:,.0f}\n\n"
                    "Add one or more monsters to assess their threat."
                )
                slider_text = f"{capacity.requested_label} ({capacity.slider_value})"
            self.slider_label.config(text=slider_text)
        except (ValueError, sqlite3.Error) as error:
            text = f"Cannot calculate difficulty: {error}"
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)
        self.result_text.config(state="disabled")


if __name__ == "__main__":
    DifficultyPreview().mainloop()
