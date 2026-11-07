"""The record form: one friendly editor for every database, battle and presentation record.

It replaces the field / value tree. Each field gets the widget its data asks for - a check box,
a number box (chances as percentages), a drop-down of the records it refers to (with icons, so
nothing is typed by hand), tag chips with suggestions, a stat table whose stats come from a
list, cards for lists of entries (add, duplicate, move, remove) and sections for nested parts.
The name and icon head the form; internal ids and rarely used fields wait under *Advanced*.
Every field's help shows on hover (an ⓘ marks the ones that have it; nothing is printed under
the fields, so the form stays short). Edits are reported through
``changed``; the host applies them (and shows a problem with ``set_error``).

The form only edits plain record data; each record type's own decoder still validates it."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.assets.image_tools import picture_field
from asteria.editor.records.form_chips import ChipList, load_record_icon
from asteria.editor.records.form_controls import (
    ColorButton,
    NumberBox,
    Picker,
    WrappedWords,
    hint_label,
)
from asteria.editor.records.form_parts import Section, SubForm, entry_list
from asteria.editor.records.form_shapes import (
    BASE_STAT_FIELDS,
    CLIP_KEYS,
    ENUMS,
    FIRST_SECTIONS,
    FORMAT_KEYS,
    LIST_TEMPLATES,
    NAME_KEYS,
    OWN_VIEW_KEYS,
    PORTRAIT_KEYS,
    SECTION_TITLES,
    closed_choices,
    engine_template,
    entry_noun,
    entry_title,
    field_help,
    formula_names,
    fresh_ids,
    has_positions,
    is_empty_optional,
    is_empty_value,
    is_nested_record,
    is_number_map,
    is_number_matrix,
    is_scalar_list,
    is_text_map,
    lists_title,
    paired_keys,
    parse_numbers,
    pool_amount,
)
from asteria.editor.records.form_tables import AmountTable, NumberMatrix, PairedNumbers, TextTable
from asteria.editor.records.vocabulary import (
    CATEGORY_HELP,
    HELP,
    JOB_ROLES,
    NOT_REFERENCES,
    OPERATION_KINDS,
    REFERENCES,
    TECHNICAL,
    TERM_KEY_SOURCES,
    TRIGGERS,
    Choice,
    engine_enums,
    is_chance_field,
    is_tag_field,
    is_trigger_field,
    label_for,
    map_source,
    record_title,
    tag_label,
    tag_meaning,
    trigger_label,
    vocabulary_for,
    words,
)
from asteria.editor.ui.i18n import english


class RecordForm(QScrollArea):
    """Edits one record's data with a form; ``record()`` gives the edited data back."""

    # defaults until something sets them (code may read them first)
    _unbuilt = False

    changed = Signal()

    def __init__(self, parent=None, *, document=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document = document
        self._paired = {}  # the tables of PAIRED_NUMBERS being edited, by their fields
        self.field_choices = {}  # field -> callable ((value, QIcon or None), ...) (extra lists)
        self.icon_library = None
        self.category = ""
        self.optional = set()
        self.description_switch = None  # () -> a Players See It switch for the description
        self.trailer = None  # a widget kept at the end of every record's page (its Note)
        self.siblings = None  # () -> {record id: data} of the records of the same kind
        self._data = None
        self._title = None
        self._icons = {}
        self.vocabulary = vocabulary_for(document)
        self._page = QWidget()
        self._page.setObjectName("RecordFormPage")
        self.setWidget(self._page)
        self._layout = QVBoxLayout(self._page)
        self._layout.setContentsMargins(4, 4, 4, 12)
        self._layout.setSpacing(10)
        self.error = QLabel()
        self.error.setObjectName("FormError")
        self.error.setWordWrap(True)
        self.error.hide()
        self._apply_style()

    # -- public API ---------------------------------------------------------------------------
    def clear(self):
        self._data = None
        self._rebuild()

    def set_record(self, data, title=None, *, optional=(), category="", defer=False):
        """Show ``data``; ``defer`` keeps it (``record()`` has it) but builds the fields only
        when the form is first shown - a skill tree's form has thousands of fields, and it
        sits behind the graph until asked for."""
        same = (
            self._data is not None
            and data == self._data
            and title == self._title
            and set(optional) == self.optional
            and (category or self.category) == self.category
        )
        if same:  # already showing exactly this (a refresh after an edit elsewhere): keep it
            return
        self._data = deepcopy(data)
        self._title = title
        self.optional = set(optional)
        self.category = category or self.category
        self.vocabulary = vocabulary_for(self.document)
        self._unbuilt = bool(defer) and not self.isVisible()
        if not self._unbuilt:
            self._rebuild()

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        if self._unbuilt:
            self._unbuilt = False
            self._rebuild()

    def record(self):
        return None if self._data is None else deepcopy(self._data)

    # -- the structure API of the former tree editor (scripts and tests use it) --------------
    def _at(self, path):
        value = self._data
        for part in path:
            value = value[part]
        return value

    def add_entry(self, path):
        """Append an entry to the list at ``path`` (a copy of the last, else a template)."""
        entries = self._at(path)
        key = next((p for p in reversed(path) if isinstance(p, str)), "")
        if entries:
            entry = deepcopy(entries[-1])
        else:
            entry = engine_template(key) or deepcopy(LIST_TEMPLATES.get(key, {}))
        entries.append(fresh_ids(entry, entries, self))
        self.restructure()
        return entry

    def remove_entry(self, path):
        del self._at(path[:-1])[path[-1]]
        self.restructure()

    def add_field(self, path, name, value=0.0):
        self._at(path)[str(name).strip()] = value
        self.restructure()
        return name

    def set_error(self, text):
        self.error.setText("⚠  Not applied: " + text if text else "")
        self.error.setVisible(bool(text))

    # -- building -----------------------------------------------------------------------------
    def _rebuild(self):
        self._unbuilt = False
        scroll = self.verticalScrollBar().value()
        old = self.takeWidget()  # kept alive until the new page is in (the banner moves over)
        self.error.setParent(None)
        if self.trailer is not None:  # moves to the new page, never deleted with the old one
            self.trailer.setParent(None)
        self._page = QWidget()
        self._page.setObjectName("RecordFormPage")
        self._layout = QVBoxLayout(self._page)
        self._layout.setContentsMargins(4, 4, 4, 12)
        self._layout.setSpacing(10)
        self._layout.addWidget(self.error)
        if self._data is not None:
            self._build(self._data)
            if self.trailer is not None:  # last, so it scrolls with the record's fields
                self._layout.addWidget(self.trailer)
                self.trailer.show()
        self._layout.addStretch(1)
        self.setWidget(self._page)
        if old is not None:
            # takeWidget hands the old page to Python, which would free it at once - while a
            # click on one of its buttons (an "+ Add" that rebuilt the form) is still being
            # handled: a use-after-free that crashes later. It is held until deleteLater runs.
            old.hide()
            self._retired = old  # held (not a child, so it is never found among them)
            old.deleteLater()
        QTimer.singleShot(0, self._page, lambda: self.verticalScrollBar().setValue(scroll))

    def _build(self, data):
        if not isinstance(data, dict):
            section = Section("Value")
            section.add_wide(QLabel(str(data)))
            self._layout.addWidget(section)
            return
        self._header(data)
        record_id_key = self._id_key(data)
        name_key = next((k for k in NAME_KEYS if isinstance(data.get(k), str)), None)
        # small fields three to a row, labels above them: a lone number no longer owns a row
        basics = Section("Basics", hint=CATEGORY_HELP.get(self.category, ""), columns=3)
        tags = Section("Lists", columns=3)
        numbers = Section("Numbers", columns=3)
        advanced = Section(
            "Advanced", collapsed=True, hint="Filled in for you; rarely changed.", columns=3
        )
        nested = []
        for key, value in data.items():
            if key in FORMAT_KEYS or key in OWN_VIEW_KEYS or key in (record_id_key, name_key):
                continue
            if key == "icon_id":
                continue
            target = basics
            if key in TECHNICAL or (key in self.optional and is_empty_value(value)):
                target = advanced
            paired = paired_keys(self.category, key) is not None
            if paired or (
                isinstance(value, dict) and is_number_map(value) and not is_nested_record(value)
            ):
                section = target if target is advanced else numbers
                self._field(section, data, key, value)
            elif isinstance(value, list) and is_scalar_list(key, value):
                self._field(advanced if target is advanced else tags, data, key, value)
            elif isinstance(value, (dict, list)):
                nested.append((key, value, target is advanced))
            else:
                self._field(target, data, key, value)
        more = Section(
            "More fields", collapsed=True, hint="Optional, nothing written yet.", columns=3
        )
        for key in FIRST_SECTIONS.get(self.category, ()):  # a fighter's pictures first
            for entry in [n for n in nested if n[0] == key]:
                nested.remove(entry)
                box = Section(SECTION_TITLES.get((self.category, key)) or label_for(key))
                self._nested(box, data, key, entry[1])
                self._layout.addWidget(box)
        tags.toggle.setText(lists_title(tags.labels))
        for section in (basics, numbers, tags):
            if section.form.count():
                self._layout.addWidget(section)
            if section is numbers and self.category == "classes":  # an actor's jobs change
                self._layout.addWidget(self._growth_section())
            if section is numbers:
                for compare in self._comparison_sections(data):
                    self._layout.addWidget(compare)
            else:  # only empty optional fields: they wait together at the end
                for label, widget, help_text in section._more:
                    widget.show()
                    more.add_row(label, widget, help_text=help_text)
                section._more = []
        for key, value, is_advanced in nested:
            box = Section(label_for(key), collapsed=is_advanced, hint=HELP.get(key, ""))
            self._nested(box, data, key, value)
            self._layout.addWidget(box)
        if more.form.count():
            self._layout.addWidget(more)
        if advanced.has_rows():
            self._layout.addWidget(advanced)

    def _special_resources(self):
        """The resources that are a mechanic of their own: those with a Battle Resources rule."""
        project = getattr(self.vocabulary, "project", None)
        return set(getattr(getattr(project, "rpg_database", None), "battle_resources", ()) or ())

    def compared_numbers(self, record, key):
        """A record's numbers in the group its form shows them in (``record`` may be another
        record of this kind): HP and MP with the stats, a shield with the resources."""
        keys = paired_keys(self.category, key)
        if keys is None:
            return record.get(key) or {}
        special = self._special_resources()
        pools = {k: pool_amount(v) for k, v in (record.get(keys[1]) or {}).items()}
        if key == keys[1]:
            return {k: v for k, v in pools.items() if k in special}
        return {
            **(record.get(keys[0]) or {}),
            **{k: v for k, v in pools.items() if k not in special},
        }

    def _paired_table(self, data, key):
        keys = paired_keys(self.category, key)
        pair = self._paired.get(keys)
        if pair is None or pair.data is not data:
            pair = self._paired[keys] = PairedNumbers(self, data, keys)
        return pair.tables[key]

    def _comparison_sections(self, data):
        """Each list of numbers (an enemy's stats) as bars beside the other records of its
        kind, when there are some to compare with."""
        siblings = self.siblings() if self.siblings is not None else {}
        siblings = {k: v for k, v in siblings.items() if k != self._title and isinstance(v, dict)}
        if not siblings:
            return []
        from asteria.editor.rpg.growth_curves import StatComparison

        known = {c.value for kind in ("stats", "resources") for c in self.vocabulary.choices(kind)}
        sections = []
        for key, value in data.items():
            if paired_keys(self.category, key):
                value = self.compared_numbers(data, key)
            if key in TECHNICAL or not is_number_map(value) or len(value) < 3:
                continue
            if not set(value) <= known:  # stats and resources, not a position or a scale
                continue
            if not any(isinstance(other.get(key), dict) for other in siblings.values()):
                continue
            section = Section(
                f"{label_for(key)} compared",
                hint="Each bar reaches the strongest record of this kind; the tick marks the "
                "average of all of them.",
            )
            section.add_wide(StatComparison(self, key, siblings))
            sections.append(section)
        return sections

    def _growth_section(self):
        """A job's (an actor's) stats level by level, as charts (growth_curves)."""
        from asteria.editor.rpg.growth_curves import GrowthCurves

        section = Section("Growth Curves")
        self.growth_curves = GrowthCurves(self, self.category)
        section.add_wide(self.growth_curves)
        return section

    def _header(self, data):
        card = QFrame()
        card.setObjectName("FormHeader")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)
        picks = self._picture_pick(data)  # what a double-click on the picture changes
        icon_picker = None
        if "icon_id" in data and self.icon_library is not None:
            # the record's icon, chosen as a character's picture is: a framed square, a
            # double-click opens the pictures by kind (items, weapons, skills… alike)
            from asteria.editor.rpg.game_systems_widget import _IconPicker

            icon_picker = _IconPicker(self.icon_library)
            icon_picker.preview.setFixedSize(64, 64)
            icon_picker.setText(str(data.get("icon_id") or ""))
            icon_picker.changed.connect(lambda p=icon_picker: self._set(data, "icon_id", p.text()))
            icon_picker.preview.setToolTip(HELP["icon_id"])
        icon_box = None
        if icon_picker is not None and picks is not None:  # its own picture first: the icon
            icon_box = QHBoxLayout()  # beside the name, small
            icon_picker.preview.setFixedSize(36, 36)
            icon_box.addWidget(hint_label("Icon"), 0, Qt.AlignVCenter)
            icon_box.addWidget(icon_picker, 1)
        names = QVBoxLayout()
        name_key = next((k for k in NAME_KEYS if isinstance(data.get(k), str)), None)
        if name_key is not None:
            edit = QLineEdit(data[name_key])
            edit.setObjectName("FormName")
            edit.setPlaceholderText("Name players see")
            edit.textEdited.connect(lambda text, k=name_key: self._set(data, k, text))
            names.addWidget(hint_label(label_for(name_key)))
            names.addWidget(edit)
        id_key = self._id_key(data)
        if id_key is not None and name_key is None:  # no name: a title from its parts
            title = record_title(self.category, data, self.vocabulary, data.get(id_key))
            if title:
                heading = WrappedWords(title)  # a long title takes two lines, not the width
                heading.setObjectName("FormTitle")
                names.addWidget(heading)
        if id_key is None and self._title:  # a profile without a name: its id in words
            line = hint_label(words(str(self._title)))
            names.addWidget(line)
        if icon_box is not None:
            names.addSpacing(4)
            names.addLayout(icon_box)
        picture = self.record_picture(self._title, 56) if self._title else None
        if icon_picker is not None and icon_box is None:  # the icon is the record's picture
            icon_picker.name.hide()
            row.addWidget(icon_picker, 0, Qt.AlignTop)
        elif picture is not None or picks is not None:
            # the record's own picture (record_pictures); a double-click on the box picks
            # another sprite sheet: an actor's look on the map, a fighter's battlefield sheet
            from asteria.editor.records.sprite_sheet_picker import PictureBox

            portrait = PictureBox()
            portrait.setPixmap(picture)
            if picks is not None:
                portrait.setToolTip(HELP[picks])
                portrait.doubleClicked.connect(
                    lambda box=portrait, d=data: self.pick_picture(d, box)
                )
            row.addWidget(portrait, 0, Qt.AlignTop)
        row.addLayout(names, 1)
        self._layout.addWidget(card)

    def _id_key(self, data):
        """The key holding the record's own id: the one whose value is the record id the host
        gave (``actor_id`` of an actor), else the first ``*_id`` that refers to nothing."""
        for key, value in data.items():
            if key.endswith("_id") and self._title is not None and value == self._title:
                return key
        for key, value in data.items():
            if key.endswith("_id") and isinstance(value, str) and REFERENCES.get(key) is None:
                if key not in ("icon_id",):
                    return key
        return None

    def _nested(self, section, parent, key, value):
        if isinstance(value, dict):
            if is_number_map(value) and value:
                self._field(section, parent, key, value, label="")
            elif is_text_map(value) and value:
                self._field(section, parent, key, value, label="")
            elif is_number_matrix(value):  # HP, MP… each with current / maximum / minimum
                kind = map_source(str(key)) or "resources"
                labels = {c.value: c.label for c in self.vocabulary.choices(kind)}
                matrix = NumberMatrix(value, labels, noun=entry_noun(str(key)))
                matrix.edited.connect(lambda m=matrix: self._set(parent, key, m.value()))
                section.add_wide(matrix)
            else:
                inner = SubForm(self, value, key)
                section.add_wide(inner)
        else:
            if has_positions(value):  # where each entry stands, drawn above the list
                from asteria.editor.rpg.growth_curves import PositionsPreview

                names = self.vocabulary.names()
                section.add_wide(
                    PositionsPreview(
                        self, lambda v=value: [(entry_title(e, "", names), e) for e in v]
                    )
                )
            section.add_wide(entry_list(self, parent, key, value))

    def _field(self, section, data, key, value, *, label=None):
        widget = self.widget_for(data, key, value)
        if widget is None:
            return
        text = label_for(key) if label is None else label
        help_text = field_help(data, key)
        if key == "description" and label is None and data is self._data:
            from asteria.editor.records.notes import description_words

            text, help_text = description_words(self.category, text, help_text)
            switch = self.description_switch() if self.description_switch else None
            if switch is not None:  # Players See It, right under the words it is about
                holder = QWidget()
                column = QVBoxLayout(holder)
                column.setContentsMargins(0, 0, 0, 0)
                column.setSpacing(4)
                column.addWidget(widget)
                column.addWidget(switch)
                holder.setProperty("wide", True)  # long text: a whole row
                widget = holder
        source = self._reference(data, str(key)) if isinstance(value, str) else None
        about = self.vocabulary.description(source, value) if source else ""
        if about:  # what the picked skill / item does, under its picker
            help_text = f"{help_text}  ·  {about}" if help_text else about
        if not text:
            section.add_wide(widget)
        elif (
            is_empty_optional(value)
            and not section.keeps_empty
            and english(section.toggle.text()) != "Advanced"
        ):
            section.add_empty(text, widget, help_text=help_text)
        else:
            section.add_row(text, widget, help_text=help_text)

    # -- one field ----------------------------------------------------------------------------
    def widget_for(self, data, key, value):
        """The editing widget for ``data[key]``; edits write back into ``data``."""
        skey = str(key)
        source = self._reference(data, skey)
        if isinstance(value, bool):
            box = QCheckBox("Yes")
            box.setChecked(value)
            box.toggled.connect(lambda on: self._set(data, key, bool(on)))
            return box
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            box = NumberBox(value, integer=isinstance(value, int), percent=is_chance_field(skey))
            box.valueChanged.connect(lambda _v, b=box: self._set(data, key, b.number()))
            return box
        if picture_field(skey) and self.icon_library is not None:
            from asteria.editor.rpg.game_systems_widget import _IconPicker

            picker = _IconPicker(self.icon_library)
            picker.setText(str(value or ""))
            picker.changed.connect(lambda p=picker: self._set(data, key, p.text()))
            return picker
        if skey == "battlefield_asset_id" and self.document is not None:
            # a fighter's sprite sheet: the project's sheets, each with its first frame
            from asteria.editor.records.sprite_sheet_picker import SpriteSheetPicker

            picker = SpriteSheetPicker(self.document)
            picker.setText(str(value or ""))
            picker.changed.connect(lambda p=picker: self._set(data, key, p.text()))
            return picker
        if skey == "icon_asset_id" and self.icon_library is not None:
            from asteria.editor.rpg.game_systems_widget import _IconPicker

            picker = _IconPicker(self.icon_library)
            picker.setText(str(value or ""))
            picker.changed.connect(lambda p=picker: self._set(data, key, p.text() or None))
            return picker
        if skey in PORTRAIT_KEYS and self.icon_library is not None:
            # a fighter's portrait (its party card in battle): the portrait pictures, as the
            # Dialogue window offers them; none chosen stays empty (null)
            from asteria.editor.assets.image_tools import PortraitLibrary
            from asteria.editor.events.dialogue_dialog import _PortraitPicker

            picker = _PortraitPicker(PortraitLibrary(self.document))
            picker.setText(str(value or ""))
            picker.changed.connect(lambda p=picker: self._set(data, key, p.text() or None))
            return picker
        formula = formula_names(data, skey)
        if formula is not None and (isinstance(value, str) or value is None):
            from asteria.editor.records.formula_field import FormulaField

            field = FormulaField(formula, self.vocabulary)
            field.setText(value or "")
            # a formula that does not parse, or reads a stat Game Systems ▸ Stats does not
            # declare, is shown and not applied: the record keeps its last good one (D94)
            field.edited.connect(lambda f=field: f.valid() and self._set(data, key, f.text()))
            return field
        if (isinstance(value, str) or value is None) and skey in CLIP_KEYS.get(self.category, ()):
            # a pose names one of the sheet's animations: offer them, in words
            picker = Picker(self.vocabulary.choices("clips"), value or "", allow_none=True)
            picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
            return picker
        if isinstance(value, str) or value is None:
            if source is not None or skey in self.field_choices:
                choices = self._choices(source, skey)
                picker = Picker(choices, value or "", icons=self.icon)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
                return picker
            if skey == "initial_phase_id" and "phases" in data:  # an AI's starting phase
                phases = [p.get("phase_id") for p in data["phases"] if isinstance(p, dict)]
                choices = [Choice(str(p), words(str(p))) for p in phases if p]
                picker = Picker(choices, value or "", allow_none=True)
                picker.setEditable(False)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or None))
                return picker
            if skey == "role" and "class_id" in data:  # a job's role: main or sub job
                known = dict(JOB_ROLES)
                for used in [*self.vocabulary.values_for(skey), value or ""]:
                    if used:  # a project's own word stays a choice (the engine keeps it)
                        known.setdefault(used, label_for(used))
                choices = [Choice(v, words) for v, words in known.items()]
                picker = Picker(choices, value or "", allow_none=False)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker
            if skey == "cue" or (
                skey in ("member_id", "target_id") and str(value or "").startswith("@")
            ):  # a motion beat's cue, or who it acts on ("@target"): the ones in use
                return self._used_words(data, key, value)
            if skey == "step_id":  # a recipe's step (Base, Catalyst...): the ones in use
                used = [*self.vocabulary.values_for("step_id"), value or ""]
                choices = [Choice(v, words(v)) for v in dict.fromkeys(used) if v]
                picker = Picker(choices, value or "", allow_none=False)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
                return picker
            if skey == "slot_id" and self.category == "parties":  # a formation's place
                return self._party_slot(data, key, value)
            if skey == "kind" and set(data) == {"kind", "target", "value"}:
                return self._operation_kind(data, value)  # an effect's step, in words
            if skey == "kind" and set(data) == {"cue_id", "time", "kind", "payload"}:
                from asteria.gameplay.action_timeline import ActionCueKind

                choices = [Choice(k.value, words(k.value)) for k in ActionCueKind]
                picker = Picker(choices, value or "", allow_none=False)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker  # a timeline cue: Hitbox, Projectile, Gameplay Event...
            if skey.endswith("_tag") and not is_tag_field(skey):  # one tag (a hit's tag)
                picker = Picker(self.vocabulary_tags(), value or "", allow_other=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
                return picker
            if skey == "target" and str(data.get("kind", "")).startswith("tag_"):
                picker = Picker(self.vocabulary_tags(), value or "", allow_other=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
                return picker  # the tag a step adds or removes
            fixed = ENUMS.get(skey) or engine_enums().get(skey)
            if is_trigger_field(skey):  # a moment in the battle, in words
                used = self.vocabulary.values_for(skey)
                known = dict.fromkeys(fixed or (*TRIGGERS, *used))
                if value:  # the record's own moment is always one of the choices
                    known.setdefault(str(value), None)
                choices = [Choice(t, trigger_label(t)) for t in known]
                picker = Picker(choices, value or "", allow_none=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker
            if fixed or closed_choices(skey, self.vocabulary.values_for(skey)):
                options = fixed or self.vocabulary.values_for(skey)
                choices = [Choice(v, words(v)) for v in options]
                picker = Picker(choices, value or "", allow_none=True)
                picker.picked.connect(lambda p=picker: self._set(data, key, p.value()))
                return picker
            if skey.endswith("color") or skey.endswith("colour"):
                button = ColorButton(value)
                button.edited.connect(lambda b=button: self._set(data, key, b.color))
                return button
            if skey in ("description", "text", "message", "body") or len(str(value or "")) > 60:
                edit = QPlainTextEdit(str(value or ""))
                edit.setFixedHeight(64)
                edit.textChanged.connect(lambda e=edit: self._set(data, key, e.toPlainText()))
                return edit
            edit = QLineEdit(str(value or ""))
            edit.textEdited.connect(lambda text: self._set(data, key, text))
            return edit
        if isinstance(value, list) and is_scalar_list(skey, value):
            if value and all(isinstance(v, (int, float)) for v in value):
                edit = QLineEdit(", ".join(f"{v:g}" for v in value))
                edit.setToolTip("Numbers separated by commas")
                edit.textEdited.connect(lambda text: self._set(data, key, parse_numbers(text)))
                return edit
            if is_tag_field(skey):
                choices = self.vocabulary_tags()
                noun = "tag"
            else:
                if source or skey in self.field_choices:
                    choices = self._choices(source, skey)
                else:
                    choices = self._value_choices(skey)
                noun = entry_noun(skey)
            namer = None
            if noun == "tag":
                names = self.vocabulary.names()
                namer = lambda tag, n=names: tag_label(tag, n)  # noqa: E731
            db = getattr(getattr(self.vocabulary, "project", None), "rpg_database", None)
            defs = getattr(db, "tag_definitions", None) or {}
            meaning = (  # noqa: E731
                (lambda tag, n=names, d=defs: tag_meaning(tag, n, d)) if noun == "tag" else None
            )
            chips = ChipList(
                value, choices, icons=self.icon, noun=noun, namer=namer, meaning=meaning
            )
            chips.edited.connect(lambda c=chips: self._set(data, key, list(c.values)))
            return chips
        if paired_keys(self.category, skey) and data is self._data:
            return self._paired_table(data, skey)
        if isinstance(value, dict) and is_number_map(value):
            kind = map_source(skey)
            choices = self.vocabulary.choices(kind) if kind else ()
            if kind == "stats" and skey in BASE_STAT_FIELDS.get(self.category, ()):
                choices = self.vocabulary.base_stat_choices(self.category, choices, value)
            noun = {"resources": "resource", "stats": "stat", "items": "item"}.get(
                kind
            ) or entry_noun(skey)
            table = AmountTable(value, choices, percent=False, noun=noun)
            table.edited.connect(lambda t=table: self._set(data, key, dict(t.values)))
            return table
        if isinstance(value, dict) and is_text_map(value):

            def named(name, part=value):
                source = self._reference(part, name)
                return self._choices(source, name) if source else None

            table = TextTable(value, choices=named)
            table.edited.connect(lambda t=table: self._set(data, key, t.value()))
            return table
        if isinstance(value, dict):
            return SubForm(self, value, key)
        if isinstance(value, list):
            return entry_list(self, data, key, value)
        return QLabel(str(value))

    def vocabulary_tags(self):
        names = self.vocabulary.names()
        return [Choice(t, tag_label(t, names)) for t in self.vocabulary.tags()]

    def _value_choices(self, key):
        # values in words: a stat by its name ("STR", "Critical Rate"), else the id in words
        return [Choice(v, label_for(v)) for v in self.vocabulary.values_for(key)]

    def _reference(self, data, key):
        if key == "key" and isinstance(data.get("source"), str):
            return TERM_KEY_SOURCES.get(data["source"])
        if key == "target" and data.get("kind") in ("resource_delta", "resource_set"):
            return "resources"
        if key == "target" and data.get("kind") == "stat_delta":
            return "stats"
        if key in NOT_REFERENCES.get(self.category, ()):
            return None
        if key in REFERENCES:
            return REFERENCES[key]
        tail = "_".join(key.split("_")[-2:])  # roster_actor_ids -> actor_ids: the actors
        if key.endswith(("_id", "_ids")) and tail != key and REFERENCES.get(tail):
            return REFERENCES[tail]
        store = getattr(self.vocabulary, "store_for", None)
        return store(key) if store is not None else None  # formation_id, attack_id...

    def _choices(self, source, key):
        if key in self.field_choices:
            return [Choice(str(v), str(v)) for v, _icon in self.field_choices[key]()]
        return self.vocabulary.choices(source) if source else ()

    def _picture_pick(self, data):
        """Which help entry (and which change) a double-click on the record's picture makes:
        ``picture_box`` for an actor (its look on the map), ``battle_picture_box`` for a
        fighter's combatant sprites record (its battlefield sheet), else None."""
        if self.document is None or not self._title:
            return None
        if self.category == "actors":
            return "picture_box"
        if self.category == "combatant_visuals" and isinstance(data.get("assets"), dict):
            return "battle_picture_box"
        return None

    def pick_picture(self, data, box=None, sheet_id=None):
        """Give the record another picture, chosen from the project's sprite sheets (a dialog,
        or ``sheet_id`` straight away). An actor: its look on the map, every entity linked to
        it following, undoably. A fighter: its battlefield sheet."""
        from asteria.editor.records.pictures import forget_pictures
        from asteria.editor.records.sprite_sheet_picker import pick_sprite_sheet

        which = self._picture_pick(data)
        if which is None:
            return None
        if sheet_id is None:
            sheet_id = pick_sprite_sheet(self.document, self, battle=which == "battle_picture_box")
        if not sheet_id:
            return None
        if which == "picture_box":
            from asteria.editor.scene.actor_appearance import (
                apply_actor_appearance,
                standing_frame,
            )

            frame = standing_frame(self.document, sheet_id)
            apply_actor_appearance(self.document, str(self._title), str(sheet_id), frame)
        else:
            self._set(data["assets"], "battlefield_asset_id", str(sheet_id))
        forget_pictures()
        if box is not None:
            box.setPixmap(self.record_picture(self._title, 56))
        return str(sheet_id)

    def record_picture(self, record_id, size=56):
        """The record's own picture (a battle portrait or sprite), or None."""
        if self.document is None or not record_id:
            return None
        from asteria.editor.records.pictures import record_picture

        return record_picture(self.document, str(record_id), size)

    def icon(self, icon_id):
        """A QIcon for an icon id (a project picture or ``forged:<kind>``), cached."""
        if not icon_id:
            return None
        if icon_id not in self._icons:
            self._icons[icon_id] = load_record_icon(self.document, icon_id)
        return self._icons[icon_id]

    _STAND_INS = {"@source": "The User", "@target": "The Target", "@actor": "The User"}

    def _used_words(self, data, key, value):
        """A value picked from those the project uses, in words ("battle.fx.slash" reads
        "Slash", "@target" reads "The Target"); any other can be typed."""

        used = [*self.vocabulary.values_for(str(key)), value or ""]
        if str(value or "").startswith("@"):
            used = [v for v in used if v.startswith("@")] + list(self._STAND_INS)
        choices = [
            Choice(v, self._STAND_INS.get(v) or words(v.rsplit(".", 1)[-1]))
            for v in dict.fromkeys(used)
            if v
        ]
        picker = Picker(choices, value or "", allow_none=False, allow_other=True)
        picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
        return picker

    def _party_slot(self, data, key, value):
        """Where a party member stands: one of the party's formation's places, in words."""

        project = getattr(self.vocabulary, "project", None)
        formations = getattr(getattr(project, "rpg_database", None), "formations", {}) or {}
        formation = formations.get((self._data or {}).get("formation_id"))
        slots = [str(getattr(x, "slot_id", "")) for x in getattr(formation, "slots", ())]
        choices = [Choice(x, words(x)) for x in slots if x]
        picker = Picker(choices, value or "", allow_none=False)
        picker.picked.connect(lambda p=picker: self._set(data, key, p.value() or ""))
        return picker

    def _operation_kind(self, data, value):
        """An effect step's kind picked in words; a new kind gets a target and an amount it
        can use (a tag step has no amount; a stat or resource step starts at 0)."""

        choices = [Choice(k, words) for k, words in OPERATION_KINDS.items()]
        picker = Picker(choices, value or "", allow_none=False)
        picker.setEditable(False)

        def picked(p=picker):
            kind = p.value()
            if not kind or kind == data.get("kind"):
                return
            data["kind"] = kind
            if kind.startswith("tag_"):
                data["value"] = None
                options = [c.value for c in self.vocabulary_tags()] or ["tag"]
            else:
                if not isinstance(data.get("value"), (int, float, dict)):
                    data["value"] = 0.0
                source = "stats" if kind == "stat_delta" else "resources"
                options = [c.value for c in self.vocabulary.choices(source)]
            if options and data.get("target") not in options:
                data["target"] = options[0]
            QTimer.singleShot(0, self.restructure)  # the target's list follows the kind

        picker.picked.connect(picked)
        return picker

    # -- writing back ---------------------------------------------------------------------------
    def _set(self, container, key, value):
        container[key] = value
        self.changed.emit()

    def restructure(self):
        """A list gained or lost an entry: rebuild the form (the data is already changed)."""
        self._rebuild()
        self.changed.emit()

    def _apply_style(self):
        """The look comes from the editor theme (theme._form_rules), shared by every page."""
