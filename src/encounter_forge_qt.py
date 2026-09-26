"""Qt desktop application for Encounter Forge.

The generator and persistence logic deliberately live outside this module.  This
file is a presentation layer built with PySide6 so the application can use a
responsive, native-feeling desktop interface without changing encounter rules.
"""

from __future__ import annotations

import html
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from encounter_difficulty import calculate_party_capacity
from encounter_generator import EncounterRecommendation, generate_encounters, save_recommendation


ROOT_DIR = Path(__file__).resolve().parents[1]


def application_paths() -> tuple[Path, Path]:
    """Return a writable database and the bundled schema in source or frozen runs."""
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


STYLESHEET = """
* { font-family: "Segoe UI"; font-size: 10pt; color: #F4F7FF; }
QMainWindow, QWidget#root { background: #0B1020; }
QFrame#sidebar, QFrame#card, QGroupBox { background: #131B2E; border: 1px solid #2A395C; border-radius: 12px; }
QGroupBox { margin-top: 15px; padding: 15px 12px 12px 12px; font-weight: 700; color: #9DABC7; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLabel#eyebrow { color: #9DABC7; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
QLabel#muted { color: #9DABC7; }
QLabel#title { font-size: 24pt; font-weight: 700; }
QLabel#section { font-size: 15pt; font-weight: 700; }
QLabel#capacity { color: #55D6A4; font-size: 17pt; font-weight: 700; }
QLabel#status { background: #153C3A; color: #55D6A4; border-radius: 10px; padding: 5px 10px; font-size: 8pt; font-weight: 700; }
QPushButton { background: #1A2540; border: 0; border-radius: 8px; padding: 8px 11px; font-weight: 600; }
QPushButton:hover { background: #202E50; }
QPushButton:checked { background: #8B7CFF; color: white; }
QPushButton#primary { background: #8B7CFF; color: white; padding: 12px; font-weight: 700; }
QPushButton#primary:hover { background: #A99FFF; }
QPushButton:disabled { background: #1A2540; color: #63718E; }
QComboBox, QSpinBox { background: #1A2540; border: 1px solid #2A395C; border-radius: 7px; padding: 7px; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { background: #131B2E; selection-background-color: #202E50; }
QSlider::groove:horizontal { height: 6px; background: #202E50; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #8B7CFF; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -5px 0; border-radius: 8px; background: #F4F7FF; }
QTableWidget { background: #131B2E; border: 1px solid #2A395C; border-radius: 10px; gridline-color: #2A395C; selection-background-color: #202E50; }
QHeaderView::section { background: #1A2540; color: #9DABC7; border: 0; padding: 10px; font-size: 8pt; font-weight: 700; }
QTextBrowser { background: #131B2E; border: 1px solid #2A395C; border-radius: 10px; padding: 14px; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #131B2E; width: 10px; margin: 4px; }
QScrollBar::handle:vertical { background: #2A395C; min-height: 28px; border-radius: 5px; }
"""


class EncounterForgeWindow(QMainWindow):
    """The responsive Qt front-end for the encounter builder."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Encounter Forge")
        self.resize(1420, 900)
        self.setMinimumSize(1080, 700)
        self.connection = sqlite3.connect(DB_PATH)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.recommendations: tuple[EncounterRecommendation, ...] = ()
        self.level_spins: list[QSpinBox] = []
        self._build()
        self._rebuild_player_levels()
        self._refresh_capacity()
        self._refresh_controls()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt callback name
        self.connection.close()
        event.accept()

    @staticmethod
    def _label(text: str, object_name: str | None = None, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(word_wrap)
        return label

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(30, 24, 30, 26)
        page.setSpacing(16)

        page.addLayout(self._build_header())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_workspace())
        splitter.setSizes([335, 1000])
        splitter.setStretchFactor(1, 1)
        page.addWidget(splitter, 1)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        emblem = self._label("EF")
        emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emblem.setFixedSize(38, 30)
        emblem.setStyleSheet("background:#8B7CFF; border-radius:8px; font-weight:700;")
        header.addWidget(emblem)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(self._label("Encounter Forge", "title"))
        title_box.addWidget(self._label("Tactical encounter builder", "muted"))
        header.addLayout(title_box)
        header.addStretch(1)
        self.header_status = self._label("READY", "status")
        header.addWidget(self.header_status)
        return header

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(290)
        sidebar.setMaximumWidth(370)
        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form = QWidget()
        form.setStyleSheet("background:#131B2E;")
        layout = QVBoxLayout(form)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self._label("ENCOUNTER SETTINGS", "eyebrow"))
        layout.addWidget(self._label("Set the party, scene, and desired pressure.", "muted", True))

        self.party_size = QSpinBox()
        self.party_size.setRange(1, 10)
        self.party_size.setValue(4)
        self.party_size.valueChanged.connect(self._rebuild_player_levels)
        layout.addWidget(self._field("PARTY SIZE", self.party_size))

        self.environment = QComboBox()
        self.environment.addItem("Any environment")
        self.environment.addItems([row[0] for row in self.connection.execute("SELECT name FROM environments ORDER BY name")])
        layout.addWidget(self._field("ENVIRONMENT", self.environment))

        self.enemy_count = QSlider(Qt.Orientation.Horizontal)
        self.enemy_count.setRange(1, 20)
        self.enemy_count.setValue(4)
        self.enemy_count.valueChanged.connect(self._refresh_enemy_count)
        self.enemy_count_hint = self._label("", "muted")
        enemy_box = QVBoxLayout()
        enemy_box.addWidget(self.enemy_count_hint)
        enemy_box.addWidget(self.enemy_count)
        scale_labels = QHBoxLayout()
        scale_labels.addWidget(self._label("One threat", "muted"))
        scale_labels.addStretch(1)
        scale_labels.addWidget(self._label("Crowd", "muted"))
        enemy_box.addLayout(scale_labels)
        layout.addWidget(self._field("ENEMY COUNT", enemy_box))

        self.difficulty = QSlider(Qt.Orientation.Horizontal)
        self.difficulty.setRange(0, 100)
        self.difficulty.setValue(50)
        self.difficulty.valueChanged.connect(self._refresh_capacity)
        self.difficulty_name = self._label("", "capacity")
        self.difficulty_hint = self._label("", "muted", True)
        difficulty_box = QVBoxLayout()
        difficulty_box.addWidget(self.difficulty_name)
        difficulty_box.addWidget(self.difficulty_hint)
        difficulty_box.addWidget(self.difficulty)
        difficulty_labels = QHBoxLayout()
        difficulty_labels.addWidget(self._label("Low", "muted"))
        difficulty_labels.addStretch(1)
        difficulty_labels.addWidget(self._label("Moderate", "muted"))
        difficulty_labels.addStretch(1)
        difficulty_labels.addWidget(self._label("High", "muted"))
        difficulty_box.addLayout(difficulty_labels)
        layout.addWidget(self._field("DIFFICULTY TARGET", difficulty_box))

        layout.addWidget(self._label("PLAYER LEVELS", "eyebrow"))
        self.level_grid = QGridLayout()
        self.level_grid.setSpacing(6)
        level_holder = QWidget()
        level_holder.setLayout(self.level_grid)
        layout.addWidget(level_holder)
        layout.addStretch(1)
        scroll.setWidget(form)
        outer.addWidget(scroll, 1)

        generate = QPushButton("GENERATE ENCOUNTERS")
        generate.setObjectName("primary")
        generate.clicked.connect(self._generate)
        outer.addWidget(generate)
        outer.addWidget(self._label("Recommendations balance budget, group bias, and encounter shape.", "muted", True))
        return sidebar

    def _field(self, title: str, contents: QWidget | QVBoxLayout) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 7, 10, 10)
        layout.setSpacing(4)
        if isinstance(contents, QWidget):
            layout.addWidget(contents)
        else:
            layout.addLayout(contents)
        return box

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title_row = QHBoxLayout()
        title_row.addWidget(self._label("Recommended encounters", "section"))
        title_row.addStretch(1)
        self.status_label = self._label("Ready to generate", "muted")
        title_row.addWidget(self.status_label)
        layout.addLayout(title_row)
        layout.addWidget(self._build_shape_card())
        layout.addWidget(self._build_coverage_card())

        self.results = QTableWidget(0, 6)
        self.results.setHorizontalHeaderLabels(["MONSTER GROUP", "ENEMIES", "THREAT", "ENV FIT", "GROUP FIT", "BAND"])
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results.setAlternatingRowColors(False)
        self.results.verticalHeader().setVisible(False)
        self.results.verticalHeader().setDefaultSectionSize(50)
        header = self.results.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        for column, width in ((1, 76), (2, 115), (3, 88), (4, 96), (5, 100)):
            self.results.setColumnWidth(column, width)
        self.results.itemSelectionChanged.connect(self._show_selected)
        layout.addWidget(self.results)

        playbook = QHBoxLayout()
        playbook.addWidget(self._label("Tactical playbook", "section"))
        playbook.addStretch(1)
        save = QPushButton("Save selected")
        save.clicked.connect(self._save_selected)
        playbook.addWidget(save)
        layout.addLayout(playbook)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        layout.addWidget(self.detail, 1)
        self._set_detail("Generate encounters to see a stat-block-aware tactical plan for every creature.")
        return workspace

    def _build_shape_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self._label("GROUPING BIAS", "eyebrow"))
        bias_row = QHBoxLayout()
        self.grouping = QButtonGroup(self)
        for label, value in (("Same species", "same_species"), ("Book links", "book_relationships"), ("No bias", "none")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("bias", value)
            self.grouping.addButton(button)
            bias_row.addWidget(button)
            if value == "book_relationships":
                button.setChecked(True)
        self.grouping.buttonClicked.connect(self._on_grouping_changed)
        bias_row.addStretch(1)
        layout.addLayout(bias_row)

        variety_row = QHBoxLayout()
        variety_row.addWidget(self._label("VARIETY", "eyebrow"))
        self.variety = QPushButton("VARIETY OFF")
        self.variety.setCheckable(True)
        self.variety.toggled.connect(self._refresh_controls)
        variety_row.addWidget(self.variety)
        self.variety_limit = QSlider(Qt.Orientation.Horizontal)
        self.variety_limit.setRange(1, 20)
        self.variety_limit.setValue(3)
        self.variety_limit.valueChanged.connect(self._refresh_controls)
        variety_row.addWidget(self.variety_limit, 1)
        self.variety_hint = self._label("", "muted")
        variety_row.addWidget(self.variety_hint)
        layout.addLayout(variety_row)
        return card

    def _build_coverage_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        coverage = QHBoxLayout()
        coverage.addWidget(self._label("DATA COVERAGE", "eyebrow"))
        self.unprofiled = QPushButton("UNPROFILED OFF")
        self.unprofiled.setCheckable(True)
        self.unprofiled.toggled.connect(self._refresh_controls)
        coverage.addWidget(self.unprofiled)
        self.missing_xp = QPushButton("MISSING XP OFF")
        self.missing_xp.setCheckable(True)
        self.missing_xp.toggled.connect(self._refresh_controls)
        coverage.addWidget(self.missing_xp)
        coverage.addStretch(1)
        layout.addLayout(coverage)

        impact = QHBoxLayout()
        impact.addWidget(self._label("COUNT IMPACT", "eyebrow"))
        self.count_impact = QSlider(Qt.Orientation.Horizontal)
        self.count_impact.setRange(0, 100)
        self.count_impact.valueChanged.connect(self._refresh_controls)
        impact.addWidget(self.count_impact, 1)
        self.impact_hint = self._label("", "muted")
        impact.addWidget(self.impact_hint)
        layout.addLayout(impact)
        return card

    def _rebuild_player_levels(self) -> None:
        old_levels = [spin.value() for spin in self.level_spins]
        while self.level_grid.count():
            item = self.level_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.level_spins = []
        for index in range(self.party_size.value()):
            holder = QFrame()
            holder.setStyleSheet("background:#1A2540; border-radius:7px;")
            row = QHBoxLayout(holder)
            row.setContentsMargins(6, 4, 6, 4)
            row.addWidget(self._label(f"P{index + 1}", "eyebrow"))
            spin = QSpinBox()
            spin.setRange(1, 20)
            spin.setValue(old_levels[index] if index < len(old_levels) else 1)
            spin.valueChanged.connect(self._refresh_capacity)
            row.addWidget(spin)
            self.level_grid.addWidget(holder, index // 3, index % 3)
            self.level_spins.append(spin)
        self._refresh_capacity()

    def _levels(self) -> list[int]:
        return [spin.value() for spin in self.level_spins]

    def _selected_bias(self) -> str:
        button = self.grouping.checkedButton()
        return str(button.property("bias")) if button else "book_relationships"

    def _refresh_capacity(self) -> None:
        try:
            capacity = calculate_party_capacity(self.connection, self._levels(), self.difficulty.value())
        except ValueError as error:
            self.difficulty_name.setText("Check party levels")
            self.difficulty_hint.setText(str(error))
            return
        self.difficulty_name.setText(f"{capacity.requested_label} · {capacity.requested_budget_xp:,.0f} XP")
        self.difficulty_hint.setText(
            f"Low {capacity.low_xp:,.0f}  |  Moderate {capacity.moderate_xp:,.0f}  |  High {capacity.high_xp:,.0f}"
        )

    def _refresh_enemy_count(self) -> None:
        count = self.enemy_count.value()
        self.enemy_count_hint.setText(f"Roughly {count} {'enemy' if count == 1 else 'enemies'} — a preference, not a hard cap")

    def _on_grouping_changed(self) -> None:
        if self._selected_bias() == "book_relationships":
            self.unprofiled.setChecked(False)
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        variety_on = self.variety.isChecked()
        self.variety.setText("VARIETY ON" if variety_on else "VARIETY OFF")
        self.variety_limit.setEnabled(variety_on)
        self.variety_hint.setText(f"Up to {self.variety_limit.value()} kinds" if variety_on else "No cap")
        book_links = self._selected_bias() == "book_relationships"
        self.unprofiled.setEnabled(not book_links)
        self.unprofiled.setText("BOOK LINKS: PROFILED ONLY" if book_links else ("UNPROFILED ON" if self.unprofiled.isChecked() else "UNPROFILED OFF"))
        self.missing_xp.setText("MISSING XP ON" if self.missing_xp.isChecked() else "MISSING XP OFF")
        impact = self.count_impact.value()
        self.impact_hint.setText("2024 base XP" if impact == 0 else f"{impact}% 2014 action economy")
        self._refresh_enemy_count()

    def _generate(self) -> None:
        try:
            environment = self.environment.currentText()
            generation = generate_encounters(
                self.connection,
                self._levels(),
                slider_value=self.difficulty.value(),
                environment=None if environment == "Any environment" else environment,
                preferred_enemy_count=self.enemy_count.value(),
                count_influence=self.count_impact.value(),
                grouping_bias=self._selected_bias(),
                max_distinct_creatures=self.variety_limit.value() if self.variety.isChecked() else None,
                include_unprofiled=self.unprofiled.isChecked(),
                include_missing_xp=self.missing_xp.isChecked(),
                max_members=min(20, max(6, self.enemy_count.value() + 3)),
            )
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Cannot generate encounter", str(error))
            return
        self.recommendations = generation.recommendations
        self.results.setRowCount(0)
        for index, recommendation in enumerate(self.recommendations):
            self.results.insertRow(index)
            members = ", ".join(f"{threat.quantity} x {threat.name}" for threat in recommendation.assessment.monsters)
            values = (
                members,
                str(sum(threat.quantity for threat in recommendation.assessment.monsters)),
                f"{recommendation.assessment.adjusted_monster_threat_xp:,.0f} XP",
                f"{recommendation.environment_fit:.0f}/100",
                f"{recommendation.grouping_score:.0f}/100" if recommendation.grouping_score is not None else "Off",
                recommendation.assessment.assessed_band,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.results.setItem(index, column, item)
        self.status_label.setText(generation.message)
        self.header_status.setText("GENERATED")
        if self.recommendations:
            self.results.selectRow(0)
        else:
            self._set_detail("No coherent group fits this budget. Raise the slider, select another environment, or increase party levels.")

    def _show_selected(self) -> None:
        row = self.results.currentRow()
        if row < 0 or row >= len(self.recommendations):
            return
        self._show_recommendation(self.recommendations[row])

    def _show_recommendation(self, recommendation: EncounterRecommendation) -> None:
        enemy_count = sum(threat.quantity for threat in recommendation.assessment.monsters)
        coverage = []
        if recommendation.include_unprofiled:
            coverage.append("unprofiled creatures allowed")
        if recommendation.include_missing_xp:
            coverage.append("missing-XP creatures allowed with CR-peer estimates")
        bias_labels = {
            "same_species": "Same species (first name word)",
            "book_relationships": "Book relationships",
            "none": "No grouping bias",
        }
        relationship_fallback = {
            "same_species": "No explicit book relationship is required; this group is ranked by its shared first name word.",
            "book_relationships": "No source-backed relationship evidence was found.",
            "none": "No relationship preference was applied to this group.",
        }[recommendation.grouping_bias]
        grouping_score = (
            f"{recommendation.grouping_score:.0f}/100"
            if recommendation.grouping_score is not None else "off"
        )
        sections = [
            "<h3>ENCOUNTER PLAN</h3>",
            f"<p><b style='color:#55D6A4'>{html.escape(recommendation.explanation)}</b></p>",
            f"<p>Enemy-count preference: roughly {recommendation.preferred_enemy_count}; this encounter uses {enemy_count}.<br>"
            f"Count impact: {recommendation.count_influence}% legacy action-economy adjustment (effective factor ×{recommendation.assessment.action_economy_factor:.2f}).<br>"
            f"Data coverage: {html.escape(', '.join(coverage) if coverage else 'source-profiled creatures and published XP only')}.</p>",
            f"<p>Shared roles: {html.escape(', '.join(recommendation.roles) or 'No tactical profile linked.')}<br>"
            f"Grouping preference: {bias_labels[recommendation.grouping_bias]} · group fit "
            f"{grouping_score}. Stat similarity: {recommendation.stat_similarity:.0f}/100.</p>",
        ]
        evidence = "<br>".join("• " + html.escape(note) for note in recommendation.relationship_notes)
        sections.extend(["<h3>RELATIONSHIP EVIDENCE</h3>", f"<p>{evidence or html.escape(relationship_fallback)}</p>"])
        for plan in recommendation.creature_plans:
            xp = f"{plan.experience_points or 0:,} XP each"
            if plan.experience_points_inferred:
                xp += " (estimated)"
            sections.extend([
                f"<h2>{plan.quantity} x {html.escape(plan.name)}</h2>",
                "<h3>STAT BLOCK</h3>",
                f"<p>CR {plan.challenge_rating if plan.challenge_rating is not None else '—'} · {xp} · AC {plan.armour_class or '—'} · HP {plan.hit_points or '—'}<br>"
                f"Movement: {html.escape(plan.speeds)}</p>",
                "<h3>HOW TO PLAY</h3>",
            ])
            if plan.roles:
                sections.append(f"<p><b>Role:</b> {html.escape(', '.join(plan.roles))}</p>")
            if plan.engagement_style:
                sections.append(f"<p><b>Approach:</b> {html.escape(', '.join(plan.engagement_style))}</p>")
            if plan.target_preferences:
                sections.append(f"<p><b>Prioritize:</b> {html.escape(', '.join(plan.target_preferences))}</p>")
            if plan.special_behaviours:
                sections.append(f"<p><b>Use:</b> {html.escape(', '.join(plan.special_behaviours))}</p>")
            sections.append(f"<p>{html.escape(plan.tactical_summary)}</p>")
            if plan.attacks:
                attacks = []
                for attack in plan.attacks:
                    details = [attack.attack_type or "Attack"]
                    if attack.to_hit_modifier is not None:
                        details.append(f"{attack.to_hit_modifier:+d} to hit")
                    if attack.reach is not None:
                        details.append(f"reach {attack.reach} ft.")
                    if attack.range is not None:
                        details.append(f"range {attack.range}/{attack.long_range} ft." if attack.long_range is not None else f"range {attack.range} ft.")
                    details.append(attack.damage)
                    attack_html = f"<b>{html.escape(attack.name)}</b> — {html.escape(' · '.join(details))}"
                    if attack.description:
                        attack_html += f"<br><span style='color:#9DABC7'>{html.escape(' '.join(attack.description.split()))}</span>"
                    attacks.append(attack_html)
                sections.append("<h3>ATTACKS</h3><p>" + "<br><br>".join(attacks) + "</p>")
            if plan.action_names:
                sections.append(f"<p style='color:#9DABC7'>Other actions: {html.escape(', '.join(plan.action_names))}</p>")
        self.detail.setHtml("<style>h2{color:#F4F7FF;margin-top:18px;} h3{color:#A99FFF;font-size:11px;letter-spacing:1px;margin-top:16px;} p{line-height:1.45;}</style>" + "".join(sections))

    def _set_detail(self, text: str) -> None:
        self.detail.setHtml(f"<p style='color:#9DABC7'>{html.escape(text)}</p>")

    def _save_selected(self) -> None:
        row = self.results.currentRow()
        if row < 0 or row >= len(self.recommendations):
            QMessageBox.information(self, "Select an encounter", "Choose a recommendation before saving it.")
            return
        environment_id = None
        if self.environment.currentText() != "Any environment":
            environment_id = self.connection.execute("SELECT id FROM environments WHERE name = ?", (self.environment.currentText(),)).fetchone()[0]
        result_id = save_recommendation(self.connection, self.recommendations[row], environment_id)
        self.status_label.setText(f"Saved encounter #{result_id}.")
        self.header_status.setText("SAVED")
        self.header_status.setStyleSheet("background:#243957; color:#F5C76E; border-radius:10px; padding:5px 10px; font-size:8pt; font-weight:700;")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0B1020"))
    app.setPalette(palette)
    window = EncounterForgeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
