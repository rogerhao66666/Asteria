"""A world command as a form: its fields come from the command, each picked by clicking.

``WorldCommandForm`` shows one field per argument the engine reads
(``WORLD_COMMAND_ARGUMENTS``): records by their names, numbers and yes / no in boxes that stay
"Not set" (the engine's own default) until they are used. Only what the author writes - a line of
text, a command or argument the engine does not list - is typed, so nothing a project holds is
lost. ``WorldCommandDialog`` is the form in a window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from asteria.runtime.world_command_handlers import (
    WORLD_COMMAND_ARGUMENTS,
    WORLD_COMMAND_REQUIRED,
)

from .event_editing import format_world_args, parse_world_args
from .i18n import translate
from .record_vocabulary import label_for, vocabulary_for, words
from .responsive_form import ResponsiveForm
from .ui_fit import ValueCombo

NOT_SET = "Not set"
FACINGS = ("down", "up", "left", "right")
EASES = ("linear", "smooth", "ease_in", "ease_out", "cut")
DIRECTIONS = (("up", "↑"), ("down", "↓"), ("left", "←"), ("right", "→"))

NUMBERS = frozenset(
    "x y amount quantity scale duration speed volume zoom fade intensity seconds opacity level "
    "count frame columns rows frame_rate scroll_x scroll_y wave_amplitude wave_length wave_speed "
    "threshold radius duration_ms index delay max_length tile step wind to tint".split()
)
FLAGS = frozenset(
    "permanent temporary active shown party_only protect off count_up show frame_loop "
    "unlock".split()
)
COLORS = frozenset(("color", "tint_color", "text_color", "shadow_color"))
WRITTEN = frozenset(("text", "title", "nickname", "name", "default", "initial", "value", "points"))
CLOSED = {  # argument -> what it can be
    "facing": FACINGS,
    "ease": EASES,
    "easing": EASES,
    "text_align": ("left", "center", "right"),
    "balloon": ("exclamation", "question", "heart", "music", "anger", "silence", "idea", "sweat"),
    "action": ("new_game", "continue", "load", "screen", "quit"),
    "behaviour": ("still", "look_around", "wander", "wander_vertical", "wander_horizontal"),
}
CLOSED_IN = {  # the same argument name meaning something else in one command
    ("SHOW_POPUP", "kind"): ("info", "item", "warning"),
    ("SET_BATTLE_WEATHER", "kind"): (
        "none",
        "rain",
        "snow",
        "leaves",
        "dust",
        "ash",
        "sand",
        "fog",
        "sun",
    ),
    ("SHOW_PICTURE", "blend"): ("normal", "add"),
    ("SCREEN_FADE", "over"): ("world", "message_window", "everything"),
    ("SET_WEATHER", "kind"): ("none", "rain", "snow", "leaves", "dust", "ash", "sand", "fog"),
}
RECORDS = {  # argument -> the vocabulary source its names come from
    "ability_id": "abilities",
    "actor_id": "actors",
    "banner_id": "store:gacha_banners",
    "board_id": "store:quest_boards",
    "currency_id": "currencies",
    "encounter_id": "encounters",
    "enemy_id": "enemies",
    "equipment_id": "equipment",
    "faction_id": "store:factions",
    "interaction_id": "store:world_interactions",
    "item_id": "items_and_equipment",
    "level_track": "tracks",
    "locale": "store:locale_tables",
    "office_id": "store:recruit_offices",
    "owner_id": "actors",
    "quest_id": "store:quests",
    "recipe_id": "store:composition_recipes",
    "rules_id": "store:new_game_plus_rules",
    "scene_id": "scenes",
    "sequence_id": "store:action_sequences",
    "shop_id": "store:shops",
    "slot_id": "slots",
    "species_id": "store:pet_species",
    "station": "store:workstations",
    "timeline_id": "store:timelines",
}
LISTS = {"class_ids": "classes", "moves": "abilities"}
NEW_NAMES = {  # free names a project makes up: a click makes one
    "timer_id": "timer",
    "counter_id": "counter",
    "picture_id": "picture",
    "variable": "variable",
    "npc": "npc",
    "subject_id": "subject",
    "key": "key",
}
LABELS = {
    "asset_id": "Asset",
    "class_ids": "Jobs",
    "clip_set_id": "Clip Set",
    "duration_ms": "Duration (ms)",
    "over": "Covers",
    "icon_id": "Icon",
    "instance_id": "Gear",
    "interaction_id": "Interaction",
    "moves": "Moves",
    "node_id": "Upgrade",
    "objective_id": "Objective",
    "picture_id": "Picture",
    "prefab_id": "Prefab",
    "rules_id": "Rules",
    "sequence_id": "Sequence",
    "socket_id": "Socket",
    "sprite_sheet_asset_id": "Sprite Sheet",
    "subject_id": "Subject",
    "target_id": "Target",
    "timer_id": "Timer",
    "counter_id": "Counter",
    "currency_id": "Currency",
    "x": "X",
    "y": "Y",
}


def command_words(command):
    """``GIVE_ITEM`` -> "Give Item"."""
    return words(str(command).lower())


def argument_label(key):
    return LABELS.get(key) or label_for(key)


def record_names(document):
    """``names(key, value)``: the name of the record an argument points at, or None."""
    vocabulary, sources = vocabulary_for(document), {}

    def names(key, value):
        source = RECORDS.get(key)
        if source is None:
            return None
        if source not in sources:
            sources[source] = {c.value: c.label for c in vocabulary.choices(source)}
        return sources[source].get(str(value))

    return names


def value_words(value, key=None, names=None):
    """A value as the author reads it: a record by its name, names in words, numbers as they
    are."""
    if isinstance(value, bool):
        return translate("Yes" if value else "No")
    if isinstance(value, str):
        named = names(key, value) if names is not None and key else None
        if named:
            return named
        return (
            translate(words(value)) if value and " " not in value and "." not in value else value
        )
    if isinstance(value, (list, tuple)):
        return " · ".join(value_words(v, key, names) for v in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class PlainNumber(QDoubleSpinBox):
    """A number as it is written: 3, 1.5 - no trailing zeros."""

    def __init__(self):
        super().__init__()
        self.setDecimals(3)

    def textFromValue(self, value):  # noqa: N802 - Qt API
        return f"{value:.3f}".rstrip("0").rstrip(".")


# -- the fields: value() is None while unset, set_value() says whether it could hold the value ---
class _Number(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.tick = QCheckBox()
        self.box = PlainNumber()
        self.box.setRange(-1_000_000.0, 1_000_000.0)
        self.box.setEnabled(False)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.tick)
        row.addWidget(self.box, 1)
        self.tick.toggled.connect(self.box.setEnabled)
        self.tick.toggled.connect(lambda _on: self.changed.emit())
        self.box.valueChanged.connect(lambda _v: self.changed.emit())

    def value(self):
        if not self.tick.isChecked():
            return None
        number = self.box.value()
        return int(number) if float(number).is_integer() else number

    def set_value(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if round(float(value), 3) != value:  # finer than the box shows: kept as it is
            return False
        self.box.setValue(float(value))
        self.tick.setChecked(True)
        return True


class _Flag(ValueCombo):
    def __init__(self):
        super().__init__()
        self.set_choices((("yes", "Yes"), ("no", "No")), none=NOT_SET)
        self.changed = self.currentIndexChanged

    def value(self):
        return {"yes": True, "no": False}.get(self.currentText())

    def set_value(self, value):
        if not isinstance(value, bool):
            return False
        self.setCurrentText("yes" if value else "no")
        return True


class _Pick(ValueCombo):
    """One of a list; ``required``: the first is picked at once, never "Not set"."""

    def __init__(self, pairs, *, required=False, open_ended=False, new=None):
        super().__init__()
        self.setEditable(open_ended)
        self.setProperty("i18n_choices", True)
        if new:
            self.offer_new(f"New {words(new)}", f"new_{new}")
        self.set_choices(pairs, none=None if required else NOT_SET)
        if new and required and not pairs:  # it must have a name: a new one is ready to use
            self.setCurrentIndex(self.findData(self.NEW))
        self.changed = self.currentTextChanged

    def value(self):
        return self.currentText().strip() or None

    def set_value(self, value):
        if not isinstance(value, str):  # a number stays a number
            return False
        self.setCurrentText(value)
        return True


class _Written(QLineEdit):
    def __init__(self):
        super().__init__()
        self.changed = self.textChanged

    def value(self):
        return self.text() or None

    def set_value(self, value):
        if not isinstance(value, str):
            return False
        self.setText(value)
        return True


class _Color(QWidget):
    """The engine reads ``[r, g, b]`` (``as_list``, a screen colour) or ``"r,g,b"``."""

    changed = Signal()

    def __init__(self, *, as_list=False):
        from .combat_workspace import _ColorButton

        super().__init__()
        self.as_list = as_list
        self.tick = QCheckBox()
        self.button = _ColorButton()
        self.button.setEnabled(False)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.tick)
        row.addWidget(self.button, 1)
        self.tick.toggled.connect(self.button.setEnabled)
        self.tick.toggled.connect(lambda _on: self.changed.emit())
        self.button.changed.connect(self.changed)

    def value(self):
        if not self.tick.isChecked():
            return None
        digits = self.button.color.lstrip("#")
        rgb = [int(digits[at : at + 2], 16) for at in (0, 2, 4)]
        return rgb if self.as_list else ",".join(str(c) for c in rgb)

    def set_value(self, value):
        as_list = isinstance(value, (list, tuple))
        parts = value if as_list else str(value).split(",")
        if len(parts) != 3 or not all(str(c).strip().isdigit() for c in parts):
            return False  # kept as it is, under "Other Details"
        rgb = [int(str(c)) for c in parts]
        if max(rgb) > 255 or (not as_list and ",".join(map(str, rgb)) != value):
            return False
        self.as_list = as_list
        self.button.set_color("#{:02x}{:02x}{:02x}".format(*rgb))
        self.tick.setChecked(True)
        return True


class _Chips(QWidget):
    changed = Signal()

    def __init__(self, pairs, noun):
        from .record_form import ChipList
        from .record_vocabulary import Choice

        super().__init__()
        self.written = False
        self.chips = ChipList((), [Choice(v, shown) for v, shown in pairs], noun=noun)
        self.chips.edited.connect(self.changed)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.chips)

    def value(self):
        values = list(self.chips.values)
        if not values:
            return None
        return ",".join(values) if self.written else values  # the way it was written stays

    def set_value(self, value):
        self.written = isinstance(value, str)
        if self.written:
            value = [part.strip() for part in value.split(",") if part.strip()]
        if not isinstance(value, (list, tuple)):
            return False
        self.chips.values = [str(v) for v in value]
        self.chips._build()
        return True


class _Picture(QWidget):
    changed = Signal()

    def __init__(self, library):
        from .game_systems_widget import _IconPicker

        super().__init__()
        self.picker = _IconPicker(library)
        self.picker.changed.connect(self.changed)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.picker)

    def value(self):
        return self.picker.text() or None

    def set_value(self, value):
        if not isinstance(value, str):
            return False
        self.picker.setText(value)
        return True


class _Route(QWidget):
    """A walk, built with the arrows: each click is a step. ``as_list``: a list of steps
    (GRID_ROUTE: ``walk_up``), else the text MOVE_ROUTE reads (``up 3, left 2``). Steps the
    arrows cannot make (a hop, a pause) stay in their place."""

    changed = Signal()

    def __init__(self, *, as_list):
        super().__init__()
        self.as_list = as_list
        self.steps = []
        self._held = (None, None)  # the value as it was written, while its steps stand
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.buttons = {}
        for direction, arrow in DIRECTIONS:
            button = QPushButton(arrow)
            button.setToolTip(words(direction))
            button.setFixedWidth(34)
            button.clicked.connect(lambda _c=False, d=direction: self.add(d))
            row.addWidget(button)
            self.buttons[direction] = button
        self.undo = QPushButton("Undo Step")
        self.undo.clicked.connect(self.remove_last)
        row.addWidget(self.undo)
        self.shown = QLabel()
        row.addWidget(self.shown, 1)
        self._show()

    def add(self, direction):
        self.steps.append(f"walk_{direction}" if self.as_list else direction)
        self._show()
        self.changed.emit()

    def remove_last(self):
        if self.steps:
            self.steps.pop()
            self._show()
            self.changed.emit()

    def _groups(self):
        groups = []
        for step in self.steps:
            direction = str(step).removeprefix("walk_")
            if groups and groups[-1][0] == direction:
                groups[-1][1] += 1
            else:
                groups.append([direction, 1])
        return groups

    def _show(self):
        self.undo.setEnabled(bool(self.steps))
        said = ", ".join(f"{words(d)} {n}" for d, n in self._groups())
        self.shown.setText(said or translate("No steps yet"))

    def value(self):
        if not self.steps:
            return None
        if self.steps == self._held[1]:
            return self._held[0]
        if self.as_list:
            return list(self.steps)
        return ", ".join(f"{d} {n}" for d, n in self._groups())

    def set_value(self, value):
        if self.as_list:
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",") if part.strip()]
            if not isinstance(value, (list, tuple)):
                return False
            if not all(isinstance(step, str) for step in value):
                return False
            self.steps = list(value)
        else:
            steps = []
            for part in str(value).replace(";", ",").split(","):
                pieces = part.split()
                if not pieces:
                    continue
                if pieces[0].lower() not in dict(DIRECTIONS):
                    return False
                try:
                    count = int(pieces[1]) if len(pieces) > 1 else 1
                except ValueError:
                    return False
                steps.extend([pieces[0].lower()] * count)
            self.steps = steps
        self._held = (value, list(self.steps))
        self._show()
        return True


class WorldCommandForm(QWidget):
    changed = Signal()

    def __init__(self, document=None, parent=None, *, command="TRANSFER", args=None):
        super().__init__(parent)
        self.document = document
        self.fields = {}
        self.kept = {}
        self.command = ValueCombo()
        self.command.setEditable(True)  # a game's own command is named by its author
        self.command.setProperty("i18n_choices", True)
        self.command.set_choices(
            sorted(((c, command_words(c)) for c in WORLD_COMMAND_ARGUMENTS), key=lambda p: p[1])
        )
        self.command.setCurrentText(command)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.grid = None
        self.other = QLineEdit()
        self.other.setToolTip("Arguments this form has no field for: key=value, ...")
        self.other.textChanged.connect(lambda _t: self.changed.emit())
        self.other_label = QLabel("Other Details")
        self.scroll = scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.body)
        scroll.setMinimumHeight(180)
        top = QFormLayout()
        top.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        top.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        top.addRow(translate("Command"), self.command)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addWidget(self.other_label)
        row.addWidget(self.other, 1)
        layout.addLayout(row)
        self.set_command(command, args)
        self.command.currentTextChanged.connect(lambda _t: self._command_changed())

    # -- what is on offer -------------------------------------------------------------------------
    def _vocabulary(self):
        return vocabulary_for(self.document) if self.document is not None else None

    def _entities(self):
        pairs = [("player", "Player"), ("self", "This event's entity")]
        project = getattr(self.document, "project", None)
        seen = {"player", "self"}
        for scene in project.scenes() if project is not None else ():
            for entity in scene.entities():
                if entity.name and entity.name not in seen:
                    seen.add(entity.name)
                    pairs.append((entity.name, entity.name))
        return pairs

    def _programs(self):
        project = getattr(self.document, "project", None)
        ids = project.event_programs.ids() if project is not None else ()
        return [(key, words(key)) for key in ids]

    def _prefabs(self):
        project = getattr(self.document, "project", None)
        prefabs = getattr(project, "prefabs", None)
        ids = prefabs.ids() if prefabs is not None else ()
        return [(key, words(key)) for key in ids]

    def _used(self, key):
        vocabulary = self._vocabulary()
        return [(v, words(v)) for v in vocabulary.values_for(key) if v] if vocabulary else []

    def _source_pairs(self, source):
        vocabulary = self._vocabulary()
        return [(c.value, c.label) for c in vocabulary.choices(source)] if vocabulary else []

    def _field(self, command, key):
        required = key in WORLD_COMMAND_REQUIRED.get(command, ())
        if key == "route":
            return _Route(as_list=False)
        if key == "steps":
            return _Route(as_list=True)
        if key in NUMBERS or (key == "blend" and (command, key) not in CLOSED_IN):
            return _Number()
        if key in FLAGS:
            return _Flag()
        if key in COLORS:
            return _Color(as_list=key == "color")
        if key in WRITTEN:
            return _Written()
        if key in LISTS:
            noun = "job" if key == "class_ids" else "move"
            return _Chips(self._source_pairs(LISTS[key]), noun)
        if key in ("icon_id", "sprite_sheet_asset_id") and self.document is not None:
            from .image_tools import IconLibrary, SpriteSheetLibrary

            library = IconLibrary if key == "icon_id" else SpriteSheetLibrary
            return _Picture(library(self.document))
        closed = CLOSED_IN.get((command, key)) or CLOSED.get(key)
        if closed:
            return _Pick([(v, words(v)) for v in closed], required=required)
        if key == "entity":
            return _Pick(self._entities(), required=required, open_ended=True)
        if key in ("click_event", "on_expire"):
            return _Pick(self._programs(), required=required)
        if key == "prefab_id":
            return _Pick(self._prefabs(), required=required, open_ended=True)
        source = RECORDS.get(key)
        pairs = self._source_pairs(source) if source else []
        if not pairs:  # nothing to list yet, or a free name: what the project already uses
            pairs = self._used(key)
        open_ended = not source or not pairs
        return _Pick(pairs, required=required, open_ended=open_ended, new=NEW_NAMES.get(key))

    # -- the command ------------------------------------------------------------------------------
    def _command_changed(self):
        """Another command: what the two share (who it is about, say) stays."""
        command = self.command_name()
        known = WORLD_COMMAND_ARGUMENTS.get(command, ())
        try:
            held = self.result_args()
        except ValueError:
            held = {}
        self.set_command(command, {k: v for k, v in held.items() if k in known})
        self.changed.emit()

    def command_name(self):
        return self.command.currentText().strip().upper()

    def set_command(self, command, args=None):
        """Build the fields of ``command``; ``args`` fill them, and whatever no field can hold
        stays as "Other Details"."""
        self.command.blockSignals(True)
        self.command.setCurrentText(command)
        self.command.blockSignals(False)
        if self.grid is not None:
            self.body_layout.removeWidget(self.grid)
            self.grid.hide()
            self.grid.setParent(None)
            self.grid.deleteLater()
        self.fields = {}
        self.grid = ResponsiveForm(column_width=190, max_columns=3)
        self.body_layout.insertWidget(0, self.grid)
        known = WORLD_COMMAND_ARGUMENTS.get(command, ())
        for key in known:
            field = self._field(command, key)
            field.changed.connect(lambda *_a: self.changed.emit())
            self.fields[key] = field
            wide = isinstance(field, (_Chips, _Route))
            self.grid.add_row(argument_label(key), field, span=wide)
        extras, self.kept = {}, {}
        for key, value in dict(args or {}).items():
            field = self.fields.get(key)
            if field is None or not field.set_value(value):
                written = format_world_args({key: value})
                try:  # what a line of text can't say again stays untouched
                    fits = parse_world_args(written) == {key: value}
                except ValueError:
                    fits = False
                (extras if fits else self.kept)[key] = value
        self.other.setText(format_world_args(extras))
        shown = bool(extras) or command not in WORLD_COMMAND_ARGUMENTS
        self.other.setVisible(shown)
        self.other_label.setVisible(shown)

    def result_args(self):
        """The arguments that are set; ValueError when "Other Details" can't be read."""
        args = {}
        for key, field in self.fields.items():
            value = field.value()
            if value is not None:
                args[key] = value
        args.update(self.kept)
        args.update(parse_world_args(self.other.text()))
        return args

    def missing(self):
        """The labels of what the engine needs and is still empty."""
        args = self.result_args()
        needed = WORLD_COMMAND_REQUIRED.get(self.command_name(), ())
        return [argument_label(key) for key in needed if args.get(key) in (None, "")]


class WorldCommandDialog(QDialog):
    """``pictures_later``: a picture command is set up in its own window after this one, so here
    it is only chosen."""

    def __init__(
        self, document=None, parent=None, *, command="TRANSFER", args=None, pictures_later=False
    ):
        super().__init__(parent)
        self.setWindowTitle("World Command")
        self.pictures_later = pictures_later
        self.form = WorldCommandForm(document, self, command=command, args=args)
        self.form.changed.connect(self._show_kind)
        self.note = QLabel("Press OK to set up the picture.")
        self.error = QLabel("")
        self.error.setObjectName("ErrorLabel")
        self.error.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.form, 1)
        layout.addWidget(self.note)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self._show_kind()
        self.resize(720, 420)

    def _is_picture(self):
        from .picture_command_dialog import PICTURE_COMMANDS

        return self.pictures_later and self.command_name() in PICTURE_COMMANDS

    def _show_kind(self):
        self.note.setVisible(self._is_picture())
        self.form.scroll.setVisible(not self._is_picture())

    def command_name(self):
        return self.form.command_name()

    def result_args(self):
        return self.form.result_args()

    def accept(self):
        if self._is_picture():
            super().accept()
            return
        try:
            missing = self.form.missing()
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        if missing:
            needs = ", ".join(translate(label) for label in missing)
            self.error.setText(f"{translate('Still needed')}: {needs}")
            return
        super().accept()


__all__ = [
    "PlainNumber",
    "WorldCommandDialog",
    "WorldCommandForm",
    "argument_label",
    "command_words",
    "record_names",
    "value_words",
]
