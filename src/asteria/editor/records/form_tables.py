"""Number and text tables of a record: amounts, number matrices, text tables and paired numbers."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.records.form_controls import NumberBox, PickDialog, Picker, hint_label
from asteria.editor.records.form_shapes import BASE_STAT_FIELDS, basic_first, plural
from asteria.editor.records.vocabulary import (
    Choice,
    label_for,
)
from asteria.editor.ui.fit import layout_widgets
from asteria.editor.ui.i18n import translate
from asteria.editor.ui.icons import icon as editor_icon


class AmountTable(QWidget):
    """``{name: number}``: one row per name (picked from a list) with its number. The pairs stand
    in even columns, as many as hold the longest name whole."""

    edited = Signal()
    NUMBER_WIDTH = 84
    REMOVE_WIDTH = 24
    PICTURE = 20
    SPACING = 8
    GAP = 20  # between one pair and the next
    LEAST_WRAPPED_NAME = 110  # narrower than this, two pairs a row are worse than one
    FIND_FROM = 13  # a list this long can be searched

    def __init__(self, values, choices, *, percent=False, noun="stat", icons=None, no_picture=""):
        super().__init__()
        self.values = dict(values)
        self.choices = tuple(choices)
        self.percent = percent
        self.noun = noun
        self.icons = icons
        self.no_picture = no_picture  # the name of an editor icon
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(self.SPACING)
        self.grid.setVerticalSpacing(4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.grid)
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(self._add)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Find…")
        self.find.setClearButtonEnabled(True)
        self.find.setFixedWidth(180)
        self.find.textChanged.connect(lambda _text: self._build())
        self._buttons = row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(self.find)
        row.addStretch(1)
        layout.addLayout(row)
        self._labels = {c.value: c.label for c in self.choices}
        self._pictures = {c.value: c.icon for c in self.choices}
        self.per_row = 2  # name / number pairs on a row: as many as the width holds
        self.name_width = self.least_name_width = 72  # a page may line up several tables
        self._probe = QLabel(self)
        self._probe.hide()
        self._build()

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        """One pair a row is the narrowest it goes, a long name wrapped (see _arrange)."""
        size = super().minimumSizeHint()
        one_pair = 72 + self._pair_rest() - self.GAP
        size.setWidth(max(one_pair, self._buttons.minimumSize().width()))
        return size

    def _pair_rest(self):
        """A pair's width but for its name: its number, ✕, the gap and the spaces between."""
        return self.NUMBER_WIDTH + self.REMOVE_WIDTH + self.GAP + 4 * self.SPACING

    def _arrange(self, width):
        """``(pairs a row, name width)`` at ``width``: every name whole on one line and as many
        pairs as that leaves room for (a wide page: 3, 4… not half of it empty). A narrow one
        wraps its names to keep two pairs a row, while the longest word still fits; failing
        that one pair a row, and a name longer than the row wraps too."""
        whole = max(self.least_name_width, self.wanted_name_width())
        per_row = max(1, min(6, (width + self.GAP) // (whole + self._pair_rest())))
        if per_row > 1:
            return per_row, whole
        wrapped = (width + self.GAP) // 2 - self._pair_rest()
        if wrapped >= max(self.LEAST_WRAPPED_NAME, self._widest_word()):
            return 2, wrapped  # a list of one too: its column lines up with the other lists'
        return 1, max(72, min(whole, width - self._pair_rest() + self.GAP))

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._arrange(event.size().width()) != (self.per_row, self.name_width):
            self._build()

    def wanted_name_width(self):
        """How wide this table's longest name is, whatever the others ask of it."""
        return max([72, *(self._wanted(key) for key in self.values)])

    def _name(self, key):
        return self._labels.get(key) or label_for(key)

    def _wanted(self, key):
        """How wide a row's name is as shown, with room for a picture (measured with the labels'
        own themed font). A language switch builds the page again."""
        self._probe.ensurePolished()
        width = self._probe.fontMetrics().horizontalAdvance(translate(self._name(key)))
        return width + 4 + self._picture_room()

    def _picture_room(self):
        return self.PICTURE + 6 if self._any_picture() else 0

    def _widest_word(self):
        """The room a wrapped name needs at least (a line breaks between words, or anywhere in
        Chinese): English words only."""
        self._probe.ensurePolished()
        metrics = self._probe.fontMetrics()
        words = (word for key in self.values for word in translate(self._name(key)).split())
        return max(
            (metrics.horizontalAdvance(word) for word in words if word.isascii()), default=0
        ) + 4 + self._picture_room()  # fmt: skip

    def _any_picture(self):
        return any(self._picture(key) is not None for key in self.values)

    def _picture(self, key):
        """The QIcon of what this row names, or None."""
        path = self._pictures.get(key)
        return self.icons(path) if self.icons and path else None

    def _name_cell(self, key):
        """The row's name; when the list has pictures, its own beside it (or, for a record with
        none, the picture of its kind, so the names of a column start level)."""
        name = QLabel(self._name(key))
        if self._wanted(key) > self.name_width:
            name.setWordWrap(True)
            name.ensurePolished()
            room = self.name_width - self._picture_room()
            name.setMinimumHeight(name.heightForWidth(room))  # every line of it, in any layout
        if not self._any_picture():
            return name
        cell = QWidget()
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        mark = QLabel()
        mark.setFixedSize(self.PICTURE, self.PICTURE)
        picture = self._picture(key)
        if picture is None and self.no_picture:
            picture = editor_icon(self.no_picture, "#6c7080")
        if picture is not None:
            mark.setPixmap(picture.pixmap(self.PICTURE, self.PICTURE))
        row.addWidget(mark)
        row.addWidget(name, 1)
        return cell

    def _build(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()  # gone now, not only once the event loop runs
                item.widget().deleteLater()
        if not self.values:
            self.grid.addWidget(hint_label(f"No {plural(self.noun)} yet."), 0, 0)
        order = {c.value: i for i, c in enumerate(self.choices)}
        ordered = sorted(self.values.items(), key=lambda kv: (order.get(kv[0], 1e9), kv[0]))
        # one width for every name: the columns line up, and no name is ever cut
        self.name_width = max(self.least_name_width, self.wanted_name_width())
        if self.testAttribute(Qt.WA_Resized):  # a longer name may need fewer pairs a row
            self.per_row, self.name_width = self._arrange(self.width())
        self.find.setVisible(len(self.values) >= self.FIND_FROM)
        sought = self.find.text().strip().casefold() if self.find.isVisibleTo(self) else ""
        if sought:
            ordered = [kv for kv in ordered if self._is_sought(kv[0], sought)]
        for index, (key, value) in enumerate(ordered):
            row, column = divmod(index, self.per_row)
            column *= 4
            name = self._name_cell(key)
            name.setFixedWidth(self.name_width)
            box = NumberBox(value, integer=isinstance(value, int), percent=self.percent)
            box.setFixedWidth(self.NUMBER_WIDTH)
            box.valueChanged.connect(lambda _v, k=key, b=box: self._set(k, b.number()))
            remove = QToolButton()
            remove.setText("✕")
            box.ensurePolished()  # the themed height, not the system one
            # as tall as the box: a taller ✕ made the row a pixel taller than the box, its
            # name then stood half a pixel below the box's number
            remove.setFixedSize(self.REMOVE_WIDTH, box.sizeHint().height())
            remove.setToolTip(f"Remove {self._labels.get(key, key)}")
            remove.clicked.connect(lambda _c=False, k=key: self._remove(k))
            self.grid.addWidget(name, row, column)
            self.grid.addWidget(box, row, column + 1)
            self.grid.addWidget(remove, row, column + 2)
        for column in range(4 * 6):
            self.grid.setColumnStretch(column, 0)
            between = column % 4 == 3 and column < 4 * self.per_row - 1
            self.grid.setColumnMinimumWidth(column, self.GAP if between else 0)
        self.grid.setColumnStretch(4 * self.per_row - 1, 1)

        for widget in layout_widgets(self.grid):  # new rows count at once, not once shown
            widget.show()
        # any parent layout gives the table (and its Add button) the height it needs
        self.grid.invalidate()
        self.layout().invalidate()
        self.setMinimumHeight(self.layout().sizeHint().height())

    def _is_sought(self, key, sought):
        name = self._name(key)
        return sought in name.casefold() or sought in translate(name).casefold()

    def _set(self, key, value):
        self.values[key] = value
        self.edited.emit()

    def add_row(self, key, value):
        """Add or set one row (the former key / amount table's API)."""
        self.values[str(key)] = float(value)
        self._build()
        self.edited.emit()

    def rows(self):
        return [(k, f"{v:g}") for k, v in self.values.items()]

    def _remove(self, key):
        self.values.pop(key, None)
        self._build()
        self.edited.emit()

    def _add(self):
        if self.noun == "tag":  # a new row: pick its type, then the tag, from lists
            self._pending = True
            self._build()
            return
        free = [c for c in self.choices if c.value not in self.values]
        dialog = PickDialog(f"Add {self.noun}", free, allow_new=True, parent=self)
        if dialog.exec():
            for value in dialog.values():
                self.values.setdefault(str(value), 0.0)
            self._build()
            self.edited.emit()


class NumberMatrix(QWidget):
    """``{row: {column: number}}`` as one table: a row per name (HP, MP…), a column per
    value (Current, Maximum, Minimum), ✕ removes a row, Add one more."""

    edited = Signal()
    ORDER = ("current", "maximum", "minimum")

    def __init__(self, values, labels, *, noun="entry", columns=None, heads=None, new_row=None):
        """``columns``: always these, so it can be empty; ``heads``: their words; ``new_row``:
        what an added row starts with."""
        super().__init__()
        self.labels = dict(labels)
        self.heads = dict(heads or {})
        self.keep_one = columns is None  # its columns come from its first row
        self.new_row = new_row
        self.noun = noun
        self._order(values)
        first = next(iter(self.values.values()), {})
        self.columns = (
            list(columns)
            if columns
            else sorted(first, key=lambda c: (self.ORDER.index(c) if c in self.ORDER else 9, c))
        )
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(4)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.addLayout(self.grid)
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(self._add)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        column.addLayout(row)
        self._build()

    def _order(self, values):
        rank = {"vitality": -2, "technique": -1}  # HP, MP first, then as the game lists
        rank.update({k: i for i, k in enumerate(self.labels) if k not in rank})
        ordered = sorted(values.items(), key=lambda kv: (rank.get(kv[0], 1e9), kv[0]))
        self.values = {k: dict(v) for k, v in ordered}

    def set_values(self, values):
        self._order(values)
        self._build()

    def _build(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if not self.values:
            self.grid.addWidget(hint_label(f"No {plural(self.noun)} yet."), 0, 0)
            return
        for c, name in enumerate(self.columns, 1):
            head = hint_label(self.heads.get(name) or label_for(name))
            self.grid.addWidget(head, 0, c)
        for r, (key, row) in enumerate(self.values.items(), 1):
            name = QLabel(self.labels.get(key) or label_for(key))
            name.setToolTip(key)
            name.setMinimumWidth(80)
            self.grid.addWidget(name, r, 0)
            for c, column in enumerate(self.columns, 1):
                value = row.get(column, 0.0)
                box = NumberBox(value, integer=isinstance(value, int))
                box.setMaximumWidth(120)
                box.valueChanged.connect(
                    lambda _v, k=key, n=column, b=box: self._set(k, n, b.number())
                )
                self.grid.addWidget(box, r, c)
            remove = QToolButton()
            remove.setObjectName("FormRowRemove")
            remove.setText("✕")
            remove.setToolTip(f"Remove {name.text()}")
            remove.clicked.connect(lambda _c=False, k=key: self._remove(k))
            self.grid.addWidget(remove, r, len(self.columns) + 1)
        for c in range(len(self.columns) + 3):
            self.grid.setColumnStretch(c, 0)
        self.grid.setColumnStretch(len(self.columns) + 2, 1)

    def value(self):
        return {k: dict(v) for k, v in self.values.items()}

    def _set(self, key, column, number):
        self.values[key][column] = number
        self.edited.emit()

    def _remove(self, key):
        if self.keep_one and len(self.values) <= 1:
            return
        self.values.pop(key, None)
        self._build()
        self.edited.emit()

    def _add(self):
        free = [Choice(k, v) for k, v in self.labels.items() if k not in self.values]
        dialog = PickDialog(f"Add {self.noun}", free, allow_new=True, parent=self)
        if dialog.exec():
            for value in dialog.values():
                row = self.new_row(str(value)) if self.new_row else {}
                self.values.setdefault(str(value), row or {c: 0.0 for c in self.columns})
            self._build()
            self.edited.emit()


class TextTable(QWidget):
    """``{name: text}``: rows of two text boxes."""

    edited = Signal()

    def __init__(self, values, noun="entry", choices=None):
        super().__init__()
        self.rows = [[str(k), str(v)] for k, v in dict(values).items()]
        self.noun = noun
        self.choices = choices  # name -> the records its text may name (a projectile), or None
        self._named = len(self.rows)  # rows that came with a name: shown in words
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.grid)
        add = QPushButton(f"+ Add {noun}")
        add.setObjectName("FormAddButton")
        add.clicked.connect(lambda: self._add())
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        layout.addLayout(row)
        self._build()

    def _build(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()  # gone now, not only once the event loop runs
                item.widget().deleteLater()
        for index, (key, value) in enumerate(self.rows):
            if index < self._named and key:  # a written name reads as words ("Projectile")
                k = QLabel(label_for(key))
                k.setToolTip(key)
            else:
                k = QLineEdit(key)
                k.setPlaceholderText("name")
                k.textEdited.connect(lambda t, i=index: self._set(i, 0, t))
            options = self.choices(key) if self.choices and key else None
            if options:  # it names a record: picked by its name
                v = Picker(options, value, allow_none=True)
                v.picked.connect(lambda p=v, i=index: self._set(i, 1, p.value() or ""))
            else:
                v = QLineEdit(value)
                v.setPlaceholderText("text")
                v.textEdited.connect(lambda t, i=index: self._set(i, 1, t))
            remove = QToolButton()
            remove.setText("✕")
            k.ensurePolished()
            remove.setFixedHeight(k.sizeHint().height())  # the row as tall as its boxes
            remove.clicked.connect(lambda _c=False, i=index: self._remove(i))
            self.grid.addWidget(k, index, 0)
            self.grid.addWidget(v, index, 1)
            self.grid.addWidget(remove, index, 2)

    def _set(self, index, column, text):
        self.rows[index][column] = text
        self.edited.emit()

    def _remove(self, index):
        del self.rows[index]
        self._named -= index < self._named
        self._build()
        self.edited.emit()

    def _add(self):
        self.rows.append(["", ""])
        self._build()

    def value(self):
        return {k.strip(): v for k, v in self.rows if k.strip()}


class PairedNumbers:
    """A record's stats and resources as its form groups them: HP, MP and the like among the
    stats, and under Resources only what is a mechanic of its own (a shield: a resource with a
    Battle Resources rule). An actor's Resources also say how each starts; one that doesn't
    start full or stop at 0 is listed there too, and HP can be added to give it such a start.
    Editing writes each number back where the engine keeps it."""

    def __init__(self, form, data, keys):
        self.form, self.data = form, data
        self.stats_key, self.pools_key = keys
        self.as_record = form.category == "actors"
        vocabulary = form.vocabulary
        self.special = form._special_resources()
        pools = basic_first(vocabulary.choices("resources"))
        self.pool_ids = {c.value for c in pools}
        stats = vocabulary.choices("stats")
        if self.stats_key in BASE_STAT_FIELDS.get(form.category, ()):
            stats = vocabulary.base_stat_choices(
                form.category, stats, data.get(self.stats_key) or {}
            )
        self.stats = AmountTable(
            form.compared_numbers(data, self.stats_key),
            (*(c for c in pools if c.value not in self.special), *stats),
            percent=False,
            noun="stat",
        )
        if self.as_record:
            self.pools = NumberMatrix(
                self._listed(data.get(self.pools_key) or {}),
                {c.value: c.label for c in pools},
                noun="resource",
                columns=("maximum", "current", "minimum"),
                heads={"current": "Starts At"},
                new_row=self._new_row,
            )
        else:
            self.pools = AmountTable(
                form.compared_numbers(data, self.pools_key),
                [c for c in pools if c.value in self.special],
                percent=False,
                noun="resource",
            )
        self.tables = {self.stats_key: self.stats, self.pools_key: self.pools}
        self.stats.edited.connect(lambda: self._edited(False))
        self.pools.edited.connect(lambda: self._edited(True))

    def _listed(self, pools):
        return {
            k: v
            for k, v in pools.items()
            if k in self.special or v["current"] < v["maximum"] or v["minimum"] != 0
        }

    def _new_row(self, key):
        held = (self.data.get(self.pools_key) or {}).get(key)
        if held is not None:
            return dict(held)
        project = getattr(self.form.vocabulary, "project", None)
        rule = project.rpg_database.battle_resources.get(key) if project is not None else None
        amount = (rule.maximum if rule is not None else None) or 100.0
        return {"maximum": amount, "current": amount, "minimum": 0.0}

    def _is_pool(self, key, held_pools, held_stats):
        return key in held_pools or (key not in held_stats and key in self.pool_ids)

    def _edited(self, from_pools):
        if self.as_record:
            self._actor_edited(from_pools)
            return
        held_pools = self.data.get(self.pools_key) or {}
        held_stats = self.data.get(self.stats_key) or {}
        pools = dict(self.pools.values)
        stats = {k: v for k, v in held_stats.items() if k in held_pools}  # the id is both
        for key, amount in self.stats.values.items():
            if self._is_pool(key, held_pools, held_stats):
                pools[key] = amount
            else:
                stats[key] = amount
        self.data[self.pools_key] = pools
        self.form._set(self.data, self.stats_key, stats)

    def _actor_edited(self, from_pools):
        held_pools = self.data.get(self.pools_key) or {}
        held_stats = self.data.get(self.stats_key) or {}
        rows = self.pools.values
        pools, shown = {}, dict(self.stats.values)
        stats = {k: v for k, v in held_stats.items() if k in held_pools}  # the id is both
        if from_pools:
            for key, row in rows.items():
                old = held_pools.get(key)
                full = old is not None and old["current"] >= old["maximum"]
                still = old is not None and row["current"] == old["current"]
                pools[key] = dict(row, current=row["maximum"]) if full and still else dict(row)
                if key not in self.special:  # HP here is HP among the stats
                    shown[key] = pools[key]["maximum"]
        for key, amount in shown.items():
            if not self._is_pool(key, held_pools, held_stats):
                stats[key] = amount
            elif key in pools:
                pass
            elif from_pools:  # taken off Resources: as any other, full and down to 0
                pools[key] = {"current": amount, "maximum": amount, "minimum": 0.0}
            else:
                pools[key] = self._grown(held_pools.get(key), amount)
        if not from_pools:  # the mechanics stay as they are, a removed stat leaves Resources
            for key in rows:
                if key in self.special and key not in pools:
                    pools[key] = dict(held_pools.get(key) or rows[key])
        self.data[self.pools_key] = pools
        if shown != self.stats.values:
            self.stats.values = shown
            self.stats._build()
        if not from_pools or {k: dict(v) for k, v in rows.items()} != self._listed(pools):
            listed = {k: pools[k] for k in rows if k in pools}
            self.pools.set_values({**listed, **self._listed(pools)})
        self.form._set(self.data, self.stats_key, stats)

    @staticmethod
    def _grown(old, amount):
        """One that starts full stays full; one that doesn't keeps its start."""
        if old is None:
            return {"current": amount, "maximum": amount, "minimum": 0.0}
        current = amount if old["current"] >= old["maximum"] else old["current"]
        return dict(old, maximum=amount, current=min(current, amount))
