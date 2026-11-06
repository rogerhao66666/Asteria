"""A scene's map to pick a place on by clicking (``MapCanvas``), and the Game Start's start
position on it (``MapPointPicker``).

The map and its objects stand as the game draws them; a click gives a place, a drag moves the
view. On the Game Start the player stands there too. A place the player could not stand on is said
in words, and is not refused (an author may mean it: a cutscene may move the player on at once).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QNativeGestureEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget

from asteria.core import Transform, world_position
from asteria.graphics import RenderPlacement2D
from asteria.runtime import (
    Animator2DComponent,
    Camera2DComponent,
    SpriteRenderer2D,
    sprite_draw,
)
from asteria.runtime.character_control import CharacterController2DComponent
from asteria.runtime.collision import CollisionWorld, CombinedQuery
from asteria.runtime.tilequery import TileMapQuery

from .entity_render import build_entity_sprite_draws
from .i18n import translate
from .qt_texture_renderer import QtTextureCache, paint_texture_draws
from .scene_render import (
    build_scene_texture_draws,
    render_source_for_scene,
    resolve_texture_source,
)
from .viewport import ViewportCamera

CANVAS_HEIGHT = 260
_MOST_PIXELS = 4096  # the longer side of a map's picture: a huge map is drawn smaller
_DRAG_FROM = 4  # pixels: a shorter move is still a click
_MOST_ZOOM = 8.0
_DEFAULT_BODY = (5.0, 7.0)  # half width, half height: what the field gives a player without any
_ARROWS = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}
_CHOSEN, _SPAWN, _BLOCKED = "#46b896", "#a8acb8", "#e0605a"
PLAYER_STUCK = "The player would be stuck here: a wall or an object is in the way."


def tile_extent(tilemap):
    """``(width, height)`` of the map in world units: to its last filled tile, as the field's own
    edge (``TileMapField.world_bounds``)."""
    cells = [
        (chunk.chunk_x * tilemap.chunk_width + x, chunk.chunk_y * tilemap.chunk_height + y)
        for layer in tilemap.layers
        for chunk in layer.chunks.values()
        for y in range(chunk.height)
        for x in range(chunk.width)
        if chunk.get(x, y) != -1
    ]
    if not cells:
        return None
    return (
        (max(x for x, _ in cells) + 1) * tilemap.tile_width,
        (max(y for _, y in cells) + 1) * tilemap.tile_height,
    )


def find_player(project):
    """The player's entity, in whichever scene the project file puts it."""
    player_id = project.game_start.player_entity_id
    for scene in project.scenes() if player_id else ():
        entity = scene.get_entity(player_id)
        if entity is not None:
            return entity
    return None


def scene_bounds(document, scene):
    """``(x0, y0, x1, y1)`` of what there is to see: the map, and every object standing off it."""
    source = render_source_for_scene(document, scene)
    extent = None if source is None else tile_extent(source.tilemap)
    xs, ys = ([0.0, extent[0]], [0.0, extent[1]]) if extent else ([], [])
    for entity in scene.entities():
        if extent is None and entity.try_get(Transform) is not None:
            x, y = world_position(entity)
            xs.append(x)
            ys.append(y)
    if not xs:
        return (0.0, 0.0, 320.0, 180.0)
    margin = 0.0 if extent else 48.0
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


@dataclass(frozen=True)
class _Others:
    """A scene without the one entity that is drawn elsewhere (the player, where the page says it
    starts)."""

    scene: object
    apart: object

    def entities(self):
        return [e for e in self.scene.entities() if e is not self.apart]


def spot_problem(document, scene, body, x, y, *, stuck=PLAYER_STUCK, ignoring=()):
    """In words, what stops ``body`` (an entity, or None for the usual size) standing at
    ``(x, y)`` in ``scene``, else ``""``. It asks what the field itself asks: the map's edge, its
    blocking tiles, and solid objects, but for ``body`` itself and the ``ignoring`` ones."""
    source = render_source_for_scene(document, scene)
    queries = []
    if source is not None:
        extent = tile_extent(source.tilemap)
        if extent and not (0 <= x <= extent[0] and 0 <= y <= extent[1]):
            return "This place is outside the map."
        queries.append(TileMapQuery(source.tilemap))
    exclude = {entity.id for entity in (*ignoring, body) if entity is not None}
    queries.append(CollisionWorld.from_scene(scene).blocking_query(exclude=exclude))
    half_w, half_h = _DEFAULT_BODY
    spec = None if body is None else body.try_get(CharacterController2DComponent)
    if spec is not None:
        half_w, half_h = spec.half_width, spec.half_height
    query = CombinedQuery(*queries) if len(queries) > 1 else queries[0]
    # the body stands on the feet, its bottom edge at the position (TileMapField.step)
    corners = [(x + side * half_w, y - rise * half_h) for side in (-1, 1) for rise in (0, 2)]
    if any(query.collides_world_point(cx, cy) for cx, cy in corners):
        return stuck
    return ""


class MapCanvas(QWidget):
    """The map itself. ``picked`` gives the world place of a click; what a place is for is
    painted over it by a subclass (``paint_marks``). ``height`` fixes its height, else it grows
    with the window."""

    picked = Signal(int, int)

    def __init__(self, document, parent=None, *, height=None, tip=""):
        super().__init__(parent)
        self.document = document
        self.scene = None
        self.apart = None  # left out of the map's picture: it's drawn by the marks instead
        self.fit_margin = 0  # pixels kept around the whole map: room for marks on its edge
        self.camera = ViewportCamera(max_zoom=_MOST_ZOOM)
        self.bounds = (0.0, 0.0, 320.0, 180.0)
        self._cache = QtTextureCache()
        self._picture = None
        self._fitted = True  # follows the widget's size until the author zooms or drags
        self._press = None
        self._dragging = False
        if height is None:
            self.setMinimumHeight(CANVAS_HEIGHT)
        else:
            self.setFixedHeight(height)
        self.setMinimumWidth(160)
        self.setCursor(Qt.CrossCursor)
        if tip:
            self.setToolTip(tip)
        self.minus = self._button("−", "Zoom out", lambda: self.zoom_by(1 / 1.5))
        self.plus = self._button("+", "Zoom in", lambda: self.zoom_by(1.5))
        self.fit_button = self._button("⤢", "Show the whole map", self.fit)

    def _button(self, text, tip, action):
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tip)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.ArrowCursor)
        button.setStyleSheet(
            "QToolButton { background: rgba(24, 26, 30, 200); color: #e6e8ee;"
            " border: 1px solid #4a4e58; border-radius: 4px; }"
            "QToolButton:hover { background: rgba(70, 184, 150, 200); }"
        )
        button.clicked.connect(lambda _checked=False: action())
        return button

    # -- what it shows -----------------------------------------------------------------------
    def show_scene(self, scene, apart=None):
        if scene is self.scene and apart is self.apart:
            return
        self.scene, self.apart = scene, apart
        self._picture = None
        self.bounds = (0.0, 0.0, 320.0, 180.0) if scene is None else (
            scene_bounds(self.document, scene)
        )  # fmt: skip
        self.fit()

    # -- the view ----------------------------------------------------------------------------
    def _fit_zoom(self):
        x0, y0, x1, y1 = self.bounds
        side = 2 * self.fit_margin
        return min(
            max(1, self.width() - side) / max(1.0, x1 - x0),
            max(1, self.height() - side) / max(1.0, y1 - y0),
        )

    def fit(self):
        """The whole map in the middle."""
        self._fitted = True
        x0, y0, x1, y1 = self.bounds
        zoom = self._fit_zoom()
        self.camera.min_zoom = min(zoom, 1.0)
        self.camera.zoom = zoom
        self.camera.pan_x = (self.width() - (x1 - x0) * zoom) / 2 - x0 * zoom
        self.camera.pan_y = (self.height() - (y1 - y0) * zoom) / 2 - y0 * zoom
        self.update()

    def zoom_by(self, factor, anchor=None):
        self._fitted = False
        middle = (self.width() / 2, self.height() / 2)
        self.camera.zoom_by(factor, anchor or middle)
        self.update()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        side = self.width() - 6
        for button in (self.fit_button, self.plus, self.minus):
            side -= button.width()
            button.move(side, 6)
            side -= 2
        if self._fitted:
            self.fit()

    # -- the picture -------------------------------------------------------------------------
    def _map_picture(self):
        """The map and its objects, drawn once: painting them per tile at a small zoom leaves
        seams between the tiles, and would be done again on every move of the marker."""
        if self._picture is None and self.scene is not None:
            x0, y0, x1, y1 = self.bounds
            scale = min(1.0, _MOST_PIXELS / max(1.0, x1 - x0, y1 - y0))
            image = QImage(
                max(1, ceil((x1 - x0) * scale)),
                max(1, ceil((y1 - y0) * scale)),
                QImage.Format_ARGB32_Premultiplied,
            )
            image.fill(QColor(40, 43, 49))
            camera = ViewportCamera(pan_x=-x0 * scale, pan_y=-y0 * scale, zoom=scale, min_zoom=0.0)
            painter = QPainter(image)
            source = render_source_for_scene(self.document, self.scene)
            draws = ()
            if source is not None:
                draws = build_scene_texture_draws(source, camera, image.width(), image.height())
            self._paint_draws(painter, draws)
            self._paint_draws(
                painter,
                build_entity_sprite_draws(
                    _Others(self.scene, self.apart),
                    camera,
                    self.document.asset_views.sprite_sheet,
                ),
            )
            painter.end()
            self._picture = image
        return self._picture

    def _paint_draws(self, painter, draws):
        paint_texture_draws(
            painter, draws, lambda aid: resolve_texture_source(self.document, aid), self._cache
        )

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(28, 30, 34))
        picture = self._map_picture()
        if picture is not None:
            x0, y0, x1, y1 = self.bounds
            left, top = self.camera.world_to_screen(x0, y0)
            right, bottom = self.camera.world_to_screen(x1, y1)
            # below 1:1 a map is smoothed, so a path stays a path; above, its pixels stay pixels
            painter.setRenderHint(QPainter.SmoothPixmapTransform, self.camera.zoom < 1.0)
            painter.drawImage(QRectF(left, top, right - left, bottom - top), picture)
        self._paint_unpictured(painter)
        self.paint_marks(painter)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(QColor(74, 78, 88), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def paint_marks(self, painter):
        """What a place is for, over the map: nothing here."""

    def _paint_unpictured(self, painter):
        """A scene with no map: what stands in it, by name, so a place can be chosen beside it."""
        if self.scene is None or render_source_for_scene(self.document, self.scene) is not None:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        for entity in self.scene.entities():
            sprite = entity.try_get(SpriteRenderer2D)
            if (
                entity is self.apart
                or entity.try_get(Transform) is None
                or entity.try_get(Camera2DComponent) is not None
                or (sprite is not None and sprite.visible)
            ):
                continue
            x, y = self.camera.world_to_screen(*world_position(entity))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#738ee8"))
            painter.drawEllipse(QPointF(x, y), 4, 4)
            painter.setPen(QColor("#c8cbd6"))
            painter.drawText(QPointF(x + 7, y + 4), translate(entity.name))

    # -- the mouse ---------------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self._press = event.position().toPoint()
            self._dragging = False

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        if self._press is None:
            return
        here = event.position().toPoint()
        moved: QPoint = here - self._press
        if not self._dragging and moved.manhattanLength() < _DRAG_FROM:
            return
        self._dragging = True
        self._fitted = False
        self.setCursor(Qt.ClosedHandCursor)
        self.camera.pan_by(moved.x(), moved.y())
        self._press = here
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if event.button() != Qt.LeftButton or self._press is None:
            return
        clicked = not self._dragging
        self._press = None
        self._dragging = False
        self.setCursor(Qt.CrossCursor)
        if clicked and self.scene is not None:
            at = event.position()
            x, y = self.camera.screen_to_world(at.x(), at.y())
            x0, y0, x1, y1 = self.bounds
            self.picked.emit(round(min(max(x, x0), x1)), round(min(max(y, y0), y1)))

    def wheelEvent(self, event):  # noqa: N802 - Qt API
        if not event.modifiers() & Qt.ControlModifier:
            event.ignore()  # the wheel scrolls the page
            return
        at = event.position()
        self.zoom_by(1.25 if event.angleDelta().y() > 0 else 1 / 1.25, (at.x(), at.y()))

    def event(self, event):
        if event.type() == QEvent.NativeGesture and isinstance(event, QNativeGestureEvent):
            if event.gestureType() == Qt.ZoomNativeGesture:
                at = event.position()
                self.zoom_by(1.0 + event.value(), (at.x(), at.y()))
                return True
        return super().event(event)


class PlayerMapCanvas(MapCanvas):
    """The map with the player standing on it: the Game Start's own."""

    def __init__(self, document, parent=None):
        super().__init__(
            document,
            parent,
            height=CANVAS_HEIGHT,
            tip=(
                "Click: the player starts here.\nDrag: move the view.\n"
                "Pinch or Ctrl + scroll: zoom in and out."
            ),
        )
        self.point = None  # the place chosen; None: the player's own place in the scene
        self.facing = "down"
        self.problem = ""

    @property
    def player(self):
        return self.apart

    def show_point(self, point, facing, problem=""):
        self.point = None if point is None else (float(point[0]), float(point[1]))
        self.facing = str(facing or "down")
        self.problem = problem
        self.update()

    def player_place(self):
        """Where the player starts: the place chosen, else where the scene has it."""
        if self.point is not None:
            return self.point
        if self.player is None or self.player.try_get(Transform) is None:
            return None
        return world_position(self.player)

    def paint_marks(self, painter):
        place = self.player_place()
        if place is not None:
            self._paint_player(painter, place)

    def _frame(self, renderer):
        """The picture of the player facing the way the page says."""
        animator = None if self.player is None else self.player.try_get(Animator2DComponent)
        clips = None
        if animator is not None and animator.clip_set_id:
            clips = self.document.asset_views.clip_set(animator.clip_set_id)
        clip = None if clips is None else clips.get(f"idle_{self.facing}")
        return clip.keyframes[0].frame_index if clip is not None else renderer.frame_index

    def _paint_player(self, painter, place):
        renderer = None if self.player is None else self.player.try_get(SpriteRenderer2D)
        sheet = None
        if renderer is not None:
            sheet = self.document.asset_views.sprite_sheet(renderer.sprite_sheet_asset_id)
        if sheet is not None:
            frame = self._frame(renderer)
            if 0 <= frame < len(sheet.frames):
                draw = sprite_draw(
                    sheet=sheet,
                    frame_index=frame,
                    world_x=place[0],
                    world_y=place[1],
                    camera=self.camera,
                    placement=RenderPlacement2D(layer=0, depth=0.0, elevation=0.0),
                    opacity=1.0 if self.point is not None else 0.7,
                    flip_x=renderer.flip_x,
                )
                self._paint_draws(painter, (draw,))
        x, y = self.camera.world_to_screen(*place)
        self._paint_marker(painter, x, y)

    def _paint_marker(self, painter, x, y):
        """A ring at the feet and an arrow the way the player faces, the same size at any zoom:
        at the whole map the player's picture is a few pixels."""
        tint = _BLOCKED if self.problem else (_CHOSEN if self.point is not None else _SPAWN)
        color = QColor(tint)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(16, 17, 20, 220), 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(x, y), 8, 8)
        painter.setPen(QPen(color, 2))
        painter.drawEllipse(QPointF(x, y), 8, 8)
        dx, dy = _ARROWS.get(self.facing, (0, 1))
        tip = QPointF(x + dx * 18, y + dy * 18)
        base = QPointF(x + dx * 10, y + dy * 10)
        side = QPointF(-dy * 5, dx * 5)
        painter.setPen(QPen(QColor(16, 17, 20, 220), 1))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([tip, base + side, base - side]))
        if self.point is None:  # the switch is off: this is the scene's place, not a choice
            text = translate("Spawn point")
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(text) + 10
            box = QRectF(x - width / 2, y + 22, width, metrics.height() + 2)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(16, 17, 20, 200))
            painter.drawRoundedRect(box, 3, 3)
            painter.setPen(QColor("#e6e8ee"))
            painter.drawText(box, Qt.AlignCenter, text)


class MapPointPicker(QWidget):
    """The map and, under it, what is wrong with the place chosen if anything is."""

    picked = Signal(int, int)

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.canvas = PlayerMapCanvas(document)
        self.canvas.picked.connect(self.picked)
        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(f"color: {_BLOCKED};")
        self.warning.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.canvas)
        layout.addWidget(self.warning)

    def show_place(self, scene_id, point, facing):
        """Show ``scene_id`` (empty: the project's startup scene) with the player at ``point``
        (None: where the scene has it), facing ``facing``."""
        project = self.document.project
        scene = project.scene(scene_id or project.startup_scene_id)
        player = find_player(project)
        self.canvas.show_scene(scene, player)
        place = point
        if place is None and player is not None and player.try_get(Transform) is not None:
            place = world_position(player)
        problem = ""
        if scene is not None and place is not None:
            problem = spot_problem(self.document, scene, player, float(place[0]), float(place[1]))
        self.canvas.show_point(point, facing, problem)
        self.warning.setText("⚠  " + translate(problem) if problem else "")
        self.warning.setVisible(bool(problem))
