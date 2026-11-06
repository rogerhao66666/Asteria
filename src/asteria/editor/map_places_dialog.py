"""Pick a behavior tree's places by clicking a scene's map: where ``move_to`` goes, or the places a
``patrol`` walks between. A tree is not tied to a scene, so the map opens on a scene with a
character running this tree and any other can be picked. A place a character could not stand on
is said in words, and is not refused (the Game Start does the same)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from asteria.runtime.character_control import AIController2DComponent

from .i18n import translate
from .map_point_picker import _BLOCKED, _CHOSEN, MapCanvas, spot_problem
from .record_form import Picker, _help_tip
from .record_vocabulary import vocabulary_for

CHARACTER_STUCK = "A character would be stuck here: a wall or an object is in the way."
_HELP_PLACES = (
    "Click: adds a place to walk to.\nDrag: move the view.\n"
    "Pinch or Ctrl + scroll: zoom in and out."
)
_HELP_PLACE = (
    "Click: the character goes here.\nDrag: move the view.\n"
    "Pinch or Ctrl + scroll: zoom in and out."
)
_MOST_WARNINGS = 3  # lines under the map: every place with a problem is red on it anyway
_RADIUS = 10


def characters_running(scene, tree_id):
    """The entities in ``scene`` whose AI controller runs the tree ``tree_id``."""
    found = []
    for entity in scene.entities():
        controller = entity.try_get(AIController2DComponent)
        if controller is not None and controller.tree_id == tree_id:
            found.append(entity)
    return found


def scene_for_tree(project, tree_id):
    """The scene to open on: the first with a character running this tree, else the startup
    scene, else any."""
    scenes = list(project.scenes())
    for scene in scenes:
        if tree_id and characters_running(scene, tree_id):
            return scene
    startup = project.scene(project.startup_scene_id)
    if startup is not None:
        return startup
    return scenes[0] if scenes else None


class PlacesCanvas(MapCanvas):
    """The map with the places on it: numbered and joined in the order they're walked (the last
    one back to the first, as a patrol does), or one place without a number."""

    def __init__(self, document, parent=None):
        super().__init__(document, parent)
        self.fit_margin = _RADIUS + 4  # a place in the map's corner shows its whole number
        self.places = []
        self.numbered = True
        self.blocked = frozenset()  # the indexes of the places with a problem

    def show_places(self, places, *, numbered=True, blocked=()):
        self.places = list(places)
        self.numbered = numbered
        self.blocked = frozenset(blocked)
        self.update()

    def paint_marks(self, painter):
        spots = [QPointF(*self.camera.world_to_screen(x, y)) for x, y in self.places]
        painter.setRenderHint(QPainter.Antialiasing)
        if len(spots) > 1:
            self._paint_route(painter, spots)
        for index, spot in enumerate(spots):
            self._paint_place(painter, spot, index)

    def _paint_route(self, painter, spots):
        painter.setBrush(Qt.NoBrush)
        for width, color in ((4, QColor(16, 17, 20, 200)), (2, QColor(_CHOSEN))):
            painter.setPen(QPen(color, width))
            for start, end in zip(spots, (*spots[1:], spots[0]), strict=True):
                painter.drawLine(start, end)

    def _paint_place(self, painter, spot, index):
        """A dot of the same size at any zoom, so a place shows at the whole map too."""
        painter.setPen(QPen(QColor(16, 17, 20, 220), 2))
        painter.setBrush(QColor(_BLOCKED if index in self.blocked else _CHOSEN))
        painter.drawEllipse(spot, _RADIUS, _RADIUS)
        painter.setPen(QColor("#101114"))
        if self.numbered:
            box = QRectF(spot.x() - _RADIUS, spot.y() - _RADIUS, 2 * _RADIUS, 2 * _RADIUS)
            painter.drawText(box, Qt.AlignCenter, str(index + 1))
        else:
            painter.setBrush(QColor("#101114"))
            painter.drawEllipse(spot, 3, 3)


class MapPlacesDialog(QDialog):
    """``many``: a click adds a place; else a click is the one place. ``places()``: the result."""

    def __init__(self, document, tree_id, places, *, many, parent=None):
        super().__init__(parent)
        self.document = document
        self.tree_id = tree_id
        self.many = many
        self._places = [(float(x), float(y)) for x, y in places]
        self._scenes = {scene.id: scene for scene in document.project.scenes()}
        self.setWindowTitle("Pick Places on the Map" if many else "Pick a Place on the Map")
        self.resize(880, 640)

        start = scene_for_tree(document.project, tree_id)
        self.scene_box = Picker(
            vocabulary_for(document).choices("scenes"),
            "" if start is None else start.id,
            allow_none=False,
            allow_other=False,
        )
        self.scene_box.currentIndexChanged.connect(lambda _index: self._scene_changed())
        scene_label = QLabel("Scene")
        help_tip = QLabel("ⓘ")
        help_tip.setObjectName("FormSectionHelp")
        help_tip.setToolTip(_HELP_PLACES if many else _HELP_PLACE)
        _help_tip(help_tip)
        self.remove_last = QPushButton("Remove Last")
        self.remove_last.clicked.connect(lambda _checked=False: self._remove_last())
        self.remove_last.setVisible(many)
        top = QHBoxLayout()
        top.addWidget(scene_label)
        top.addWidget(self.scene_box)
        top.addWidget(help_tip)
        top.addStretch(1)
        top.addWidget(self.remove_last)

        self.canvas = PlacesCanvas(document)
        self.canvas.picked.connect(self._clicked)
        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(f"color: {_BLOCKED};")
        self.warning.hide()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        column = QVBoxLayout(self)
        column.addLayout(top)
        column.addWidget(self.canvas, 1)
        column.addWidget(self.warning)
        column.addWidget(self.buttons)
        self._scene_changed()

    def places(self):
        return list(self._places)

    @property
    def scene(self):
        return self._scenes.get(self.scene_box.value())

    def _scene_changed(self):
        self.canvas.show_scene(self.scene)
        self._show_places()

    def _clicked(self, x, y):
        place = (float(x), float(y))
        self._places = [*self._places, place] if self.many else [place]
        self._show_places()

    def _remove_last(self):
        self._places = self._places[:-1]
        self._show_places()

    def _problems(self):
        """``[(index, words), ...]``: the places a character running this tree can't stand on."""
        scene = self.scene
        if scene is None:
            return []
        users = characters_running(scene, self.tree_id)
        body = users[0] if users else None
        return [
            (index, words)
            for index, (x, y) in enumerate(self._places)
            if (
                words := spot_problem(
                    self.document, scene, body, x, y, stuck=CHARACTER_STUCK, ignoring=users
                )
            )
        ]

    def _show_places(self):
        problems = self._problems()
        self.canvas.show_places(
            self._places, numbered=self.many, blocked=[index for index, _words in problems]
        )
        lines = [self._warning_line(index, words) for index, words in problems]
        self.warning.setText("\n".join(lines[:_MOST_WARNINGS]))
        self.warning.setVisible(bool(lines))
        self.remove_last.setEnabled(bool(self._places))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self._places))

    def _warning_line(self, index, words):
        if not self.many:
            return f"⚠  {translate(words)}"
        line = translate("Place {number}: {problem}")
        return "⚠  " + line.format(number=index + 1, problem=translate(words))
