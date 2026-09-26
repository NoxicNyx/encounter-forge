"""Polished encounter-builder GUI for Encounter Forge."""

from __future__ import annotations

import sqlite3
import tkinter as tk
import os
import shutil
import sys
from pathlib import Path
from tkinter import messagebox, ttk

from encounter_difficulty import calculate_party_capacity
from encounter_generator import EncounterRecommendation, generate_encounters, save_recommendation


ROOT_DIR = Path(__file__).resolve().parents[1]


def application_paths() -> tuple[Path, Path]:
    """Return writable database and bundled schema paths in source or packaged runs."""
    if not getattr(sys, "frozen", False):
        return ROOT_DIR / "db" / "encounter_forge.db", ROOT_DIR / "db" / "schema.sql"
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Encounter Forge"
    data_dir.mkdir(parents=True, exist_ok=True)
    database_path = data_dir / "encounter_forge.db"
    if not database_path.exists():
        shutil.copy2(bundle_dir / "db" / "encounter_forge.db", database_path)
    return database_path, bundle_dir / "db" / "schema.sql"


DB_PATH, SCHEMA_PATH = application_paths()

BG = "#20140D"
SURFACE = "#352116"
SURFACE_LIGHT = "#4A2F1D"
SURFACE_SELECTED = "#624126"
BORDER = "#8A6135"
TEXT = "#F7E8C6"
MUTED = "#C9AA79"
ACCENT = "#C47A2C"
ACCENT_HOVER = "#E3A44D"
SUCCESS = "#8FCB8A"
WARNING = "#F1C46E"


class EncounterForgeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Encounter Forge")
        self.geometry("1380x860")
        self.minsize(1120, 700)
        self.configure(background=BG)
        self.connection = sqlite3.connect(DB_PATH)
        self.connection.row_factory = sqlite3.Row
        # Apply additive schema changes so saved encounter settings work with
        # an existing local database without requiring a full re-import.
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.party_size = tk.IntVar(value=4)
        self.slider_value = tk.IntVar(value=50)
        self.enemy_count_preference = tk.IntVar(value=4)
        self.enemy_count_preference_enabled = tk.BooleanVar(value=True)
        self.count_influence = tk.IntVar(value=0)
        self.grouping_bias = tk.StringVar(value="book_relationships")
        self.variety_enabled = tk.BooleanVar(value=False)
        self.variety_limit = tk.IntVar(value=3)
        self.include_unprofiled = tk.BooleanVar(value=False)
        self.include_missing_xp = tk.BooleanVar(value=False)
        self.environment_var = tk.StringVar(value="Any environment")
        self.level_vars: list[tk.IntVar] = []
        self.locked_roster: dict[int, int] = {}
        self.recommendations: tuple[EncounterRecommendation, ...] = ()
        self._configure_styles()
        self._build()
        self._rebuild_player_levels()
        self._refresh_capacity()
        self._refresh_enemy_count()

    def destroy(self) -> None:
        self.connection.close()
        super().destroy()

    def _refresh_sidebar_scrollregion(self, _event=None) -> None:
        region = self.sidebar_canvas.bbox("all")
        self.sidebar_canvas.configure(scrollregion=region)
        if not region:
            return
        needs_scrollbar = (region[3] - region[1]) > self.sidebar_canvas.winfo_height()
        visible = bool(self.sidebar_scrollbar.winfo_manager())
        if needs_scrollbar and not visible:
            self.sidebar_scrollbar.pack(side="right", fill="y")
        elif not needs_scrollbar and visible:
            self.sidebar_scrollbar.pack_forget()

    def _resize_sidebar_form(self, event) -> None:
        self.sidebar_canvas.itemconfigure(self.sidebar_window, width=event.width)
        self._refresh_sidebar_scrollregion()

    def _scroll_sidebar(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == self.sidebar_canvas:
                self.sidebar_canvas.yview_scroll(-int(event.delta / 120), "units")
                return "break"
            widget = widget.master
        return None

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Surface.TLabel", background=SURFACE, foreground=TEXT)
        style.configure("Caption.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9, "bold"))
        style.configure("Section.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Capacity.TLabel", background=SURFACE, foreground=SUCCESS, font=("Segoe UI", 18, "bold"))
        style.configure("TCombobox", fieldbackground=SURFACE_LIGHT, background=SURFACE_LIGHT, foreground=TEXT, arrowcolor=TEXT, padding=7, borderwidth=0)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE_LIGHT)], foreground=[("readonly", TEXT)])
        style.configure("TSpinbox", fieldbackground=SURFACE_LIGHT, foreground=TEXT, padding=6, borderwidth=0)
        style.configure("Generate.TButton", background=ACCENT, foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), padding=(18, 11), borderwidth=0)
        style.map("Generate.TButton", background=[("active", ACCENT_HOVER)])
        style.configure("Secondary.TButton", background=SURFACE_LIGHT, foreground=TEXT, padding=(12, 8), borderwidth=0)
        style.map("Secondary.TButton", background=[("active", SURFACE_SELECTED)])
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, borderwidth=0, rowheight=48, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=SURFACE_LIGHT, foreground=MUTED, borderwidth=0, font=("Segoe UI", 9, "bold"), padding=10)
        style.map("Treeview", background=[("selected", SURFACE_SELECTED)], foreground=[("selected", TEXT)])

    def _build(self) -> None:
        header = tk.Frame(self, background=BG)
        header.pack(fill="x", padx=32, pady=(26, 18))
        emblem = tk.Label(header, text="EF", background=ACCENT, foreground="white", font=("Segoe UI", 11, "bold"), width=3, height=1)
        emblem.pack(side="left", padx=(0, 12))
        title_box = tk.Frame(header, background=BG)
        title_box.pack(side="left")
        tk.Label(title_box, text="Encounter Forge", background=BG, foreground=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Tactical encounter builder", background=BG, foreground=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        self.header_status = tk.Label(header, text="READY", background="#153C3A", foreground=SUCCESS, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        self.header_status.pack(side="right", pady=8)

        content = tk.Frame(self, background=BG)
        content.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        sidebar = tk.Frame(content, background=SURFACE, highlightbackground=BORDER, highlightthickness=1, width=315)
        sidebar.pack(side="left", fill="y", padx=(0, 16))
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        workspace = tk.Frame(content, background=BG)
        workspace.pack(side="right", fill="both", expand=True)
        self._build_workspace(workspace)

    def _surface_label(self, parent, text, style="Caption.TLabel"):
        return ttk.Label(parent, text=text, style=style)

    def _build_sidebar(self, sidebar: tk.Frame) -> None:
        inner = ttk.Frame(sidebar, style="Surface.TFrame", padding=18)
        inner.pack(fill="both", expand=True)
        footer = ttk.Frame(inner, style="Surface.TFrame")
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="GENERATE ENCOUNTERS", style="Generate.TButton", command=self._generate).pack(fill="x")
        ttk.Label(
            footer,
            text="Recommendations favour your selected budget, group bias, and encounter shape.",
            style="Surface.TLabel", wraplength=260,
        ).pack(anchor="w", pady=(10, 0))

        self.sidebar_scrollbar = ttk.Scrollbar(inner, orient="vertical")
        self.sidebar_canvas = tk.Canvas(
            inner, background=SURFACE, highlightthickness=0, borderwidth=0,
            yscrollcommand=self.sidebar_scrollbar.set,
        )
        self.sidebar_canvas.pack(side="left", fill="both", expand=True)
        self.sidebar_scrollbar.config(command=self.sidebar_canvas.yview)
        form = ttk.Frame(self.sidebar_canvas, style="Surface.TFrame")
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", self._refresh_sidebar_scrollregion)
        self.sidebar_canvas.bind("<Configure>", self._resize_sidebar_form)
        self.bind_all("<MouseWheel>", self._scroll_sidebar, add="+")
        self._surface_label(form, "ENCOUNTER SETTINGS").pack(anchor="w")
        ttk.Label(form, text="Set the party, scene, and desired pressure.", style="Surface.TLabel", wraplength=260).pack(anchor="w", pady=(7, 18))

        self._surface_label(form, "PARTY SIZE").pack(anchor="w")
        party_size_spinbox = ttk.Spinbox(
            form, from_=1, to=10, textvariable=self.party_size, width=6,
            command=self._rebuild_player_levels,
        )
        party_size_spinbox.pack(anchor="w", pady=(5, 14))
        party_size_spinbox.bind("<FocusOut>", lambda _: self._rebuild_player_levels())
        party_size_spinbox.bind("<Return>", lambda _: self._rebuild_player_levels())
        self._surface_label(form, "ENVIRONMENT").pack(anchor="w")
        environments = ["Any environment"] + [row[0] for row in self.connection.execute("SELECT name FROM environments ORDER BY name")]
        ttk.Combobox(form, textvariable=self.environment_var, values=environments, state="readonly", width=28).pack(fill="x", pady=(5, 16))

        self._surface_label(form, "ENEMY COUNT").pack(anchor="w")
        self.enemy_count_hint = ttk.Label(form, style="Surface.TLabel")
        self.enemy_count_hint.pack(anchor="w", pady=(4, 2))
        tk.Scale(
            form, from_=1, to=20, orient="horizontal",
            variable=self.enemy_count_preference,
            command=lambda _: self._refresh_enemy_count(), background=SURFACE,
            foreground=TEXT, activebackground=ACCENT, highlightthickness=0,
            troughcolor=SURFACE_LIGHT, showvalue=False, sliderrelief="flat",
        ).pack(fill="x")
        count_labels = tk.Frame(form, background=SURFACE)
        count_labels.pack(fill="x", pady=(0, 14))
        tk.Label(count_labels, text="One threat", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(count_labels, text="Crowd", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8)).pack(side="right")
        self.enemy_count_toggle = tk.Button(form, command=self._toggle_enemy_count_preference, relief="flat", font=("Segoe UI", 9, "bold"), padx=9, pady=4)
        self.enemy_count_toggle.pack(anchor="w", pady=(0, 14))

        self._surface_label(form, "DIFFICULTY TARGET").pack(anchor="w")
        self.difficulty_name = ttk.Label(form, style="Capacity.TLabel")
        self.difficulty_name.pack(anchor="w", pady=(4, 0))
        self.difficulty_hint = ttk.Label(form, style="Surface.TLabel")
        self.difficulty_hint.pack(anchor="w", pady=(0, 8))
        slider = tk.Scale(form, from_=0, to=100, orient="horizontal", variable=self.slider_value, command=lambda _: self._refresh_capacity(), background=SURFACE, foreground=TEXT, activebackground=ACCENT, highlightthickness=0, troughcolor=SURFACE_LIGHT, showvalue=False, sliderrelief="flat")
        slider.pack(fill="x")
        labels = tk.Frame(form, background=SURFACE)
        labels.pack(fill="x")
        for text, anchor in (("Low", "w"), ("Moderate", "center"), ("High", "e")):
            tk.Label(labels, text=text, background=SURFACE, foreground=MUTED, font=("Segoe UI", 8)).pack(side={"w": "left", "center": "left", "e": "right"}[anchor], expand=anchor == "center")

        ttk.Separator(form).pack(fill="x", pady=18)
        self._surface_label(form, "PLAYER LEVELS").pack(anchor="w")
        self.level_frame = tk.Frame(form, background=SURFACE)
        self.level_frame.pack(fill="x", pady=(8, 18))
        ttk.Separator(form).pack(fill="x", pady=(0, 14))
        self._surface_label(form, "LOCKED ROSTER").pack(anchor="w")
        ttk.Label(form, text="Fix creatures first; Forge fills the remaining budget.", style="Surface.TLabel", wraplength=260).pack(anchor="w", pady=(5, 8))
        self.roster_names = {row[1]: row[0] for row in self.connection.execute("SELECT id, name FROM monsters ORDER BY name")}
        self.roster_all_names = list(self.roster_names)
        self.roster_choice = ttk.Combobox(form, values=self.roster_all_names, state="normal", width=28)
        self.roster_choice.pack(fill="x")
        self.roster_choice.bind("<KeyRelease>", self._filter_roster_creatures)
        self.roster_quantity = tk.IntVar(value=1)
        roster_actions = tk.Frame(form, background=SURFACE)
        roster_actions.pack(fill="x", pady=(6, 4))
        ttk.Spinbox(roster_actions, from_=1, to=20, textvariable=self.roster_quantity, width=5).pack(side="left")
        ttk.Button(roster_actions, text="Lock creature", style="Secondary.TButton", command=self._add_locked_creature).pack(side="left", padx=(7, 0))
        ttk.Button(roster_actions, text="Reset roster", style="Secondary.TButton", command=self._reset_locked_roster).pack(side="right")
        self.roster_status = ttk.Label(form, style="Surface.TLabel", wraplength=260)
        self.roster_status.pack(anchor="w", pady=(3, 14))
        self._refresh_locked_roster()
        self.after_idle(self._refresh_sidebar_scrollregion)

    def _build_workspace(self, workspace: tk.Frame) -> None:
        top = tk.Frame(workspace, background=BG)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Recommended encounters", style="Section.TLabel").pack(side="left")
        self.status_label = ttk.Label(top, text="Ready to generate", style="Muted.TLabel")
        self.status_label.pack(side="right")

        shape_controls = tk.Frame(workspace, background=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        shape_controls.pack(fill="x", pady=(0, 12))
        bias_row = tk.Frame(shape_controls, background=SURFACE)
        bias_row.pack(fill="x")
        tk.Label(bias_row, text="GROUPING BIAS", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(12, 7), pady=(7, 3))
        for label, value in (
            ("Same species", "same_species"),
            ("Book links", "book_relationships"),
            ("No bias", "none"),
        ):
            tk.Radiobutton(
                bias_row, text=label, variable=self.grouping_bias, value=value,
                command=self._on_grouping_bias_changed,
                indicatoron=0, selectcolor=SURFACE_SELECTED, background=SURFACE_LIGHT,
                foreground=TEXT, activebackground=ACCENT, activeforeground="white",
                font=("Segoe UI", 9, "bold"), relief="flat", padx=9, pady=5,
            ).pack(side="left", padx=(0, 5), pady=(5, 2))
        variety_row = tk.Frame(shape_controls, background=SURFACE)
        variety_row.pack(fill="x")
        tk.Label(variety_row, text="VARIETY", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(12, 7), pady=(2, 7))
        self.variety_button = tk.Button(
            variety_row, command=self._toggle_variety, relief="flat",
            font=("Segoe UI", 9, "bold"), padx=9, pady=4,
        )
        self.variety_button.pack(side="left", padx=(0, 8), pady=(2, 7))
        self.variety_scale = tk.Scale(
            variety_row, from_=1, to=20, orient="horizontal", variable=self.variety_limit,
            command=lambda _: self._refresh_variety_control(), background=SURFACE,
            foreground=TEXT, activebackground=ACCENT, highlightthickness=0,
            troughcolor=SURFACE_LIGHT, showvalue=False, sliderrelief="flat", length=125,
        )
        self.variety_scale.pack(side="left", pady=(0, 5))
        self.variety_hint = tk.Label(variety_row, background=SURFACE, foreground=MUTED, font=("Segoe UI", 8))
        self.variety_hint.pack(side="left", padx=(5, 10), pady=(0, 5))
        self._refresh_variety_control()

        data_controls = tk.Frame(workspace, background=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        data_controls.pack(fill="x", pady=(0, 12))
        coverage_row = tk.Frame(data_controls, background=SURFACE)
        coverage_row.pack(fill="x")
        tk.Label(coverage_row, text="DATA COVERAGE", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(12, 7), pady=(7, 2))
        self.unprofiled_button = tk.Button(coverage_row, command=self._toggle_unprofiled, relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.unprofiled_button.pack(side="left", padx=(0, 5), pady=(5, 2))
        self.missing_xp_button = tk.Button(coverage_row, command=self._toggle_missing_xp, relief="flat", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.missing_xp_button.pack(side="left", padx=(0, 12), pady=(5, 2))
        impact_row = tk.Frame(data_controls, background=SURFACE)
        impact_row.pack(fill="x")
        tk.Label(impact_row, text="COUNT IMPACT", background=SURFACE, foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(12, 7), pady=(2, 7))
        tk.Scale(
            impact_row, from_=0, to=100, orient="horizontal", variable=self.count_influence,
            command=lambda _: self._refresh_count_influence(), background=SURFACE,
            foreground=TEXT, activebackground=ACCENT, highlightthickness=0,
            troughcolor=SURFACE_LIGHT, showvalue=False, sliderrelief="flat", length=135,
        ).pack(side="left", pady=(0, 5))
        self.count_influence_hint = tk.Label(impact_row, background=SURFACE, foreground=MUTED, font=("Segoe UI", 8))
        self.count_influence_hint.pack(side="left", padx=(5, 10), pady=(0, 5))
        self._refresh_data_controls()
        self._refresh_count_influence()

        result_box = tk.Frame(workspace, background=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        result_box.pack(fill="x")
        columns = ("members", "count", "threat", "fit", "similarity", "band")
        self.result_tree = ttk.Treeview(result_box, columns=columns, show="headings", selectmode="browse", height=5)
        specs = {
            "members": ("MONSTER GROUP", 420, "w"),
            "count": ("ENEMIES", 70, "center"),
            "threat": ("THREAT", 100, "center"),
            "fit": ("ENV FIT", 95, "center"),
            "similarity": ("GROUP FIT", 100, "center"),
            "band": ("BAND", 110, "center"),
        }
        for key, (title, width, anchor) in specs.items():
            self.result_tree.heading(key, text=title)
            self.result_tree.column(key, width=width, anchor=anchor)
        self.result_tree.pack(fill="x", padx=1, pady=1)
        self.result_tree.bind("<<TreeviewSelect>>", self._show_recommendation)

        detail_header = tk.Frame(workspace, background=BG)
        detail_header.pack(fill="x", pady=(20, 10))
        ttk.Label(detail_header, text="Tactical playbook", style="Section.TLabel").pack(side="left")
        ttk.Button(detail_header, text="Save selected", style="Secondary.TButton", command=self._save_selected).pack(side="right")
        detail_box = tk.Frame(workspace, background=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        detail_box.pack(fill="both", expand=True)
        self.detail_text = tk.Text(detail_box, wrap="word", state="disabled", background=SURFACE, foreground=TEXT, insertbackground=TEXT, selectbackground=SURFACE_SELECTED, relief="flat", borderwidth=0, font=("Segoe UI", 10), padx=20, pady=16)
        self.detail_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(detail_box, orient="vertical", command=self.detail_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.detail_text.configure(yscrollcommand=scrollbar.set)
        self.detail_text.tag_configure("title", foreground=TEXT, font=("Segoe UI", 15, "bold"), spacing1=8, spacing3=4)
        self.detail_text.tag_configure("section", foreground=ACCENT_HOVER, font=("Segoe UI", 9, "bold"), spacing1=14, spacing3=4)
        self.detail_text.tag_configure("attack", foreground="#D8D2FF", spacing1=3)
        self.detail_text.tag_configure("muted", foreground=MUTED)
        self.detail_text.tag_configure("good", foreground=SUCCESS, font=("Segoe UI", 10, "bold"))
        self._set_detail("Generate encounters to see a stat-block-aware tactical plan for every creature.")

    def _rebuild_player_levels(self) -> None:
        previous_levels = [variable.get() for variable in self.level_vars]
        for widget in self.level_frame.winfo_children():
            widget.destroy()
        self.level_vars = []
        for index in range(self.party_size.get()):
            level_var = tk.IntVar(value=previous_levels[index] if index < len(previous_levels) else 1)
            self.level_vars.append(level_var)
            card = tk.Frame(self.level_frame, background=SURFACE_LIGHT)
            column = index % 3
            card.grid(row=index // 3, column=column, padx=(0, 5) if column < 2 else 0, pady=(0, 5), sticky="ew")
            tk.Label(card, text=f"P{index + 1}", background=SURFACE_LIGHT, foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(5, 2), pady=4)
            spinbox = ttk.Spinbox(card, from_=1, to=20, textvariable=level_var, width=3, command=self._refresh_capacity)
            spinbox.pack(side="right", padx=(0, 4), pady=3)
            spinbox.bind("<FocusOut>", lambda _: self._refresh_capacity())
        self.level_frame.grid_columnconfigure(0, weight=1)
        self.level_frame.grid_columnconfigure(1, weight=1)
        self.level_frame.grid_columnconfigure(2, weight=1)
        self.after_idle(self._refresh_sidebar_scrollregion)
        self._refresh_capacity()

    def _levels(self) -> list[int]:
        return [variable.get() for variable in self.level_vars]

    def _add_locked_creature(self) -> None:
        name = self.roster_choice.get()
        if not name:
            messagebox.showinfo("Choose a creature", "Choose a creature to add to the locked roster.")
            return
        monster_id = self.roster_names[name]
        self.locked_roster[monster_id] = int(self.roster_quantity.get())
        self._refresh_locked_roster()

    def _filter_roster_creatures(self, _event=None) -> None:
        query = self.roster_choice.get().casefold().strip()
        matches = [name for name in self.roster_all_names if query in name.casefold()]
        self.roster_choice.configure(values=matches[:100] if query else self.roster_all_names)

    def _reset_locked_roster(self) -> None:
        self.locked_roster.clear()
        self._refresh_locked_roster()

    def _refresh_locked_roster(self) -> None:
        names = {monster_id: name for name, monster_id in self.roster_names.items()}
        text = ", ".join(f"{quantity} x {names[monster_id]}" for monster_id, quantity in self.locked_roster.items())
        self.roster_status.config(text=text or "No creatures locked.")

    def _refresh_capacity(self) -> None:
        try:
            capacity = calculate_party_capacity(self.connection, self._levels(), int(self.slider_value.get()))
            self.difficulty_name.config(text=f"{capacity.requested_label} · {capacity.requested_budget_xp:,.0f} XP")
            self.difficulty_hint.config(text=f"Low {capacity.low_xp:,.0f}  |  Moderate {capacity.moderate_xp:,.0f}  |  High {capacity.high_xp:,.0f}")
        except ValueError as error:
            self.difficulty_name.config(text="Check party levels")
            self.difficulty_hint.config(text=str(error))

    def _refresh_enemy_count(self) -> None:
        count = int(self.enemy_count_preference.get())
        label = "enemy" if count == 1 else "enemies"
        self.enemy_count_hint.config(
            text=(f"Roughly {count} {label} — a preference, not a hard cap" if self.enemy_count_preference_enabled.get() else "No enemy-count preference")
        )
        enabled = self.enemy_count_preference_enabled.get()
        self.enemy_count_toggle.config(
            text="COUNT PREFERENCE ON" if enabled else "COUNT PREFERENCE OFF",
            background=ACCENT if enabled else SURFACE_LIGHT,
            foreground="white" if enabled else MUTED,
            activebackground=ACCENT_HOVER if enabled else SURFACE_SELECTED,
        )

    def _toggle_enemy_count_preference(self) -> None:
        self.enemy_count_preference_enabled.set(not self.enemy_count_preference_enabled.get())
        self._refresh_enemy_count()

    def _toggle_variety(self) -> None:
        self.variety_enabled.set(not self.variety_enabled.get())
        self._refresh_variety_control()

    def _refresh_variety_control(self) -> None:
        enabled = self.variety_enabled.get()
        self.variety_button.config(
            text="VARIETY ON" if enabled else "VARIETY OFF",
            background=ACCENT if enabled else SURFACE_LIGHT,
            foreground="white" if enabled else MUTED,
            activebackground=ACCENT_HOVER if enabled else SURFACE_SELECTED,
        )
        self.variety_scale.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self.variety_hint.config(
            text=f"Up to {self.variety_limit.get()} kinds" if enabled else "No cap"
        )

    def _toggle_unprofiled(self) -> None:
        self.include_unprofiled.set(not self.include_unprofiled.get())
        self._refresh_data_controls()

    def _toggle_missing_xp(self) -> None:
        self.include_missing_xp.set(not self.include_missing_xp.get())
        self._refresh_data_controls()

    def _on_grouping_bias_changed(self) -> None:
        if self.grouping_bias.get() == "book_relationships":
            self.include_unprofiled.set(False)
        self._refresh_data_controls()

    def _refresh_data_controls(self) -> None:
        book_links = self.grouping_bias.get() == "book_relationships"
        if book_links:
            self.unprofiled_button.config(
                text="BOOK LINKS: PROFILED ONLY", state=tk.DISABLED,
                background=SURFACE_LIGHT, foreground=MUTED,
            )
        else:
            enabled = self.include_unprofiled.get()
            self.unprofiled_button.config(
                text="UNPROFILED ON" if enabled else "UNPROFILED OFF",
                state=tk.NORMAL,
                background=ACCENT if enabled else SURFACE_LIGHT,
                foreground="white" if enabled else MUTED,
                activebackground=ACCENT_HOVER if enabled else SURFACE_SELECTED,
            )
        for button, enabled, enabled_text, disabled_text in (
            (self.missing_xp_button, self.include_missing_xp.get(), "MISSING XP ON", "MISSING XP OFF"),
        ):
            button.config(
                text=enabled_text if enabled else disabled_text,
                background=ACCENT if enabled else SURFACE_LIGHT,
                foreground="white" if enabled else MUTED,
                activebackground=ACCENT_HOVER if enabled else SURFACE_SELECTED,
            )

    def _refresh_count_influence(self) -> None:
        influence = int(self.count_influence.get())
        text = "2024 base XP" if influence == 0 else f"{influence}% 2014 action economy"
        self.count_influence_hint.config(text=text)

    def _generate(self) -> None:
        try:
            selected_environment = self.environment_var.get()
            generation = generate_encounters(
                self.connection,
                self._levels(),
                slider_value=int(self.slider_value.get()),
                environment=None if selected_environment == "Any environment" else selected_environment,
                preferred_enemy_count=(int(self.enemy_count_preference.get()) if self.enemy_count_preference_enabled.get() else None),
                count_influence=int(self.count_influence.get()),
                grouping_bias=self.grouping_bias.get(),
                max_distinct_creatures=(
                    int(self.variety_limit.get()) if self.variety_enabled.get() else None
                ),
                include_unprofiled=self.include_unprofiled.get(),
                include_missing_xp=self.include_missing_xp.get(),
                locked_monsters=self.locked_roster,
                max_members=min(20, max(6, int(self.enemy_count_preference.get()) + 3)),
            )
        except (ValueError, sqlite3.Error) as error:
            messagebox.showerror("Cannot generate encounter", str(error))
            return
        self.recommendations = generation.recommendations
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for index, recommendation in enumerate(self.recommendations):
            members = ", ".join(f"{threat.quantity} x {threat.name}" for threat in recommendation.assessment.monsters)
            self.result_tree.insert(
                "", "end", iid=str(index),
                values=(
                    members,
                    sum(threat.quantity for threat in recommendation.assessment.monsters),
                    f"{recommendation.assessment.adjusted_monster_threat_xp:,.0f} XP",
                    f"{recommendation.environment_fit:.0f}/100",
                    (
                        f"{recommendation.grouping_score:.0f}/100"
                        if recommendation.grouping_score is not None else "Off"
                    ),
                    recommendation.assessment.assessed_band,
                ),
            )
        self.status_label.config(text=generation.message)
        self.header_status.config(text="GENERATED", background="#153C3A", foreground=SUCCESS)
        if self.recommendations:
            self.result_tree.selection_set("0")
            self._show_recommendation()
        else:
            self._set_detail("No coherent group fits this budget. Raise the slider, select a different environment, or increase party levels.")

    def _show_recommendation(self, _event=None) -> None:
        selection = self.result_tree.selection()
        if not selection:
            return
        recommendation = self.recommendations[int(selection[0])]
        enemy_count = sum(threat.quantity for threat in recommendation.assessment.monsters)
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, "ENCOUNTER PLAN\n", "section")
        self.detail_text.insert(tk.END, recommendation.explanation + "\n", "good")
        if recommendation.preferred_enemy_count is not None:
            self.detail_text.insert(
                tk.END,
                f"Enemy-count preference: roughly {recommendation.preferred_enemy_count}; this encounter uses {enemy_count}.\n",
            )
        self.detail_text.insert(
            tk.END,
            f"Count impact: {recommendation.count_influence}% legacy action-economy adjustment "
            f"(effective factor ×{recommendation.assessment.action_economy_factor:.2f}).\n",
        )
        coverage = []
        if recommendation.include_unprofiled:
            coverage.append("unprofiled creatures allowed")
        if recommendation.include_missing_xp:
            coverage.append("missing-XP creatures allowed with CR-peer estimates")
        self.detail_text.insert(
            tk.END,
            "Data coverage: " + (", ".join(coverage) if coverage else "source-profiled creatures and published XP only") + ".\n",
        )
        self.detail_text.insert(tk.END, f"\nShared roles: {', '.join(recommendation.roles) or 'No tactical profile linked.'}\n")
        bias_labels = {
            "same_species": "Same species (first name word)",
            "book_relationships": "Book relationships",
            "none": "No grouping bias",
        }
        grouping_text = (
            f"{recommendation.grouping_score:.0f}/100"
            if recommendation.grouping_score is not None else "off"
        )
        self.detail_text.insert(
            tk.END,
            f"Grouping preference: {bias_labels[recommendation.grouping_bias]} · group fit {grouping_text}. "
            f"Stat similarity: {recommendation.stat_similarity:.0f}/100.\n",
        )
        self.detail_text.insert(tk.END, "\nRELATIONSHIP EVIDENCE\n", "section")
        relationship_fallback = {
            "same_species": "No explicit book relationship is required; this group is ranked by its shared first name word.",
            "book_relationships": "No source-backed relationship evidence was found.",
            "none": "No relationship preference was applied to this group.",
        }[recommendation.grouping_bias]
        self.detail_text.insert(
            tk.END,
            ("\n".join(f"• {note}" for note in recommendation.relationship_notes)
             if recommendation.relationship_notes else relationship_fallback) + "\n",
        )
        for plan in recommendation.creature_plans:
            self.detail_text.insert(tk.END, f"\n{plan.quantity} x {plan.name}\n", "title")
            self.detail_text.insert(tk.END, "STAT BLOCK\n", "section")
            xp_label = f"{plan.experience_points or 0:,} XP each"
            if plan.experience_points_inferred:
                xp_label += " (estimated)"
            self.detail_text.insert(tk.END, f"CR {plan.challenge_rating if plan.challenge_rating is not None else '—'}  ·  {xp_label}  ·  AC {plan.armour_class or '—'}  ·  HP {plan.hit_points or '—'}\n")
            self.detail_text.insert(tk.END, f"Movement: {plan.speeds}\n")
            self.detail_text.insert(tk.END, "HOW TO PLAY\n", "section")
            if plan.roles:
                self.detail_text.insert(tk.END, f"Role: {', '.join(plan.roles)}\n")
            if plan.engagement_style:
                self.detail_text.insert(tk.END, f"Approach: {', '.join(plan.engagement_style)}\n")
            if plan.target_preferences:
                self.detail_text.insert(tk.END, f"Prioritize: {', '.join(plan.target_preferences)}\n")
            if plan.special_behaviours:
                self.detail_text.insert(tk.END, f"Use: {', '.join(plan.special_behaviours)}\n")
            self.detail_text.insert(tk.END, plan.tactical_summary + "\n")
            if plan.attacks:
                self.detail_text.insert(tk.END, "ATTACKS\n", "section")
                for attack in plan.attacks:
                    details = [attack.attack_type or "Attack"]
                    if attack.to_hit_modifier is not None:
                        details.append(f"{attack.to_hit_modifier:+d} to hit")
                    if attack.reach is not None:
                        details.append(f"reach {attack.reach} ft.")
                    if attack.range is not None:
                        range_text = f"range {attack.range} ft."
                        if attack.long_range is not None:
                            range_text += f"/{attack.long_range} ft."
                        details.append(range_text)
                    details.append(attack.damage)
                    self.detail_text.insert(
                        tk.END, f"• {attack.name} — {' · '.join(details)}\n", "attack"
                    )
                    if attack.description:
                        description = " ".join(attack.description.split())
                        self.detail_text.insert(tk.END, f"  {description}\n", "muted")
            if plan.action_names:
                self.detail_text.insert(tk.END, "Other actions: " + ", ".join(plan.action_names) + "\n", "muted")
        self.detail_text.config(state="disabled")

    def _set_detail(self, text: str) -> None:
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text, "muted")
        self.detail_text.config(state="disabled")

    def _save_selected(self) -> None:
        selection = self.result_tree.selection()
        if not selection:
            messagebox.showinfo("Select an encounter", "Choose a recommendation before saving it.")
            return
        environment_id = None
        if self.environment_var.get() != "Any environment":
            environment_id = self.connection.execute(
                "SELECT id FROM environments WHERE name = ?", (self.environment_var.get(),)
            ).fetchone()[0]
        result_id = save_recommendation(self.connection, self.recommendations[int(selection[0])], environment_id)
        self.status_label.config(text=f"Saved encounter #{result_id}.")
        self.header_status.config(text="SAVED", background="#243957", foreground=WARNING)


if __name__ == "__main__":
    EncounterForgeApp().mainloop()
