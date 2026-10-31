"""Asteria editor icons: small vector drawings made with QPainter (no image files, no third-party
art).

``icon(name, color=None)`` returns a QIcon drawn crisply at 1x, 2x and 3x. Each icon is drawn on a
24 x 24
grid with round strokes, plus a soft tinted fill where a shape has a body, so the set reads as one
family.
``ACCENTS`` gives each workspace and panel its colour; ``icon`` uses it when no colour is passed.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ACCENTS = {
    # workspaces
    "scene": "#46b896",
    "rpg": "#dca545",
    "battle": "#e06a5c",
    "ui": "#9a84e0",
    "events": "#4aa9dc",
    "code": "#738ee8",
    "multiplayer": "#55aeb8",
    # panels
    "project": "#46b896",
    "tiles": "#86bf58",
    "layers": "#4aa9dc",
    "inspector": "#9a84e0",
    "assets": "#dca545",
    "console": "#8f96a3",
    "debugger": "#e8894a",
    "profiler": "#52b884",
    "problems": "#dcb23e",
    # roles
    "primary": "#6a83e8",
    "success": "#3fae7a",
    "danger": "#de5a62",
    "warning": "#dcb23e",
    "muted": "#8f96a3",
}

_STROKE = 1.9


def _pen(color, width=_STROKE):
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _fill(color, alpha=70):
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def _rounded(p, x, y, w, h, r, color, fill=True):
    p.setBrush(_fill(color) if fill else Qt.NoBrush)
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _poly(points):
    path = QPainterPath(QPointF(*points[0]))
    for pt in points[1:]:
        path.lineTo(QPointF(*pt))
    return path


def _star(cx, cy, outer, inner, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        r = outer if i % 2 == 0 else inner
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    path = _poly(pts)
    path.closeSubpath()
    return path


# -- drawings -------------------------------------------------------------------------------------
# Each takes (painter, colour). The painter's pen is already the colour's stroke.


def _scene(p, c):  # a folded map
    path = _poly([(3, 6), (9, 4), (15, 6), (21, 4), (21, 18), (15, 20), (9, 18), (3, 20)])
    path.closeSubpath()
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(9, 4), QPointF(9, 18))
    p.drawLine(QPointF(15, 6), QPointF(15, 20))


def _rpg(p, c):  # an open book
    p.setBrush(_fill(c))
    p.drawPath(_poly([(12, 7), (7, 5), (3, 5.5), (3, 18.5), (7, 18), (12, 20), (12, 7)]))
    p.drawPath(_poly([(12, 7), (17, 5), (21, 5.5), (21, 18.5), (17, 18), (12, 20)]))


def _battle(p, c):  # crossed swords
    for m in (lambda x: x, lambda x: 24 - x):
        p.setPen(_pen(c, 2.2))
        p.drawLine(QPointF(m(4), 4), QPointF(m(15.5), 15.5))  # blade
        p.setPen(_pen(c))
        p.drawLine(QPointF(m(12.5), 18.5), QPointF(m(18.5), 12.5))  # guard
        p.drawLine(QPointF(m(16.5), 16.5), QPointF(m(19.5), 19.5))  # grip
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(m(20.3), 20.3), 1.2, 1.2)  # pommel


def _ui(p, c):  # a window with panels
    _rounded(p, 3, 4, 18, 16, 3, c, fill=False)
    p.drawLine(QPointF(3, 9), QPointF(21, 9))
    p.setBrush(_fill(c, 110))
    p.drawRoundedRect(QRectF(6, 12, 5, 5), 1, 1)
    p.drawLine(QPointF(14, 13), QPointF(18, 13))
    p.drawLine(QPointF(14, 16), QPointF(17, 16))


def _events(p, c):  # lightning bolt
    path = _poly([(13, 3), (5, 13.5), (11.5, 13.5), (10, 21), (19, 9.5), (12.5, 9.5), (13, 3)])
    p.setBrush(_fill(c, 110))
    p.drawPath(path)


def _code(p, c):  # </>
    p.drawPolyline([QPointF(8, 7), QPointF(3, 12), QPointF(8, 17)])
    p.drawPolyline([QPointF(16, 7), QPointF(21, 12), QPointF(16, 17)])
    p.drawLine(QPointF(13.5, 5), QPointF(10.5, 19))


def _multiplayer(p, c):  # linked participants
    p.setPen(_pen(c, 2.0))
    p.drawLine(QPointF(7, 8), QPointF(12, 12))
    p.drawLine(QPointF(17, 8), QPointF(12, 12))
    p.drawLine(QPointF(12, 12), QPointF(12, 18))
    p.setBrush(_fill(c, 90))
    p.drawEllipse(QPointF(6, 7), 3.1, 3.1)
    p.drawEllipse(QPointF(18, 7), 3.1, 3.1)
    p.drawEllipse(QPointF(12, 18), 3.5, 3.5)


def _play(p, c):
    p.setBrush(QColor(c))
    p.drawPath(_poly([(7, 4.5), (19, 12), (7, 19.5), (7, 4.5)]))


def _stop(p, c):
    p.setBrush(QColor(c))
    p.drawRoundedRect(QRectF(6, 6, 12, 12), 2.5, 2.5)


def _target(p, c):  # reset view
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(12, 12), 7, 7)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(12, 12), 2, 2)
    for a, b in (
        ((12, 2), (12, 5)),
        ((12, 19), (12, 22)),
        ((2, 12), (5, 12)),
        ((19, 12), (22, 12)),
    ):
        p.drawLine(QPointF(*a), QPointF(*b))


def _folder(p, c):
    p.setBrush(_fill(c))
    p.drawPath(
        _poly([(3, 7), (3, 19), (21, 19), (21, 8.5), (11.5, 8.5), (9.5, 6), (3, 6), (3, 7)])
    )


def _project(p, c):  # a star badge
    p.setBrush(_fill(c, 110))
    p.drawPath(_star(12, 12.5, 9, 4))


def _entity(p, c):  # a person-ish pawn
    p.setBrush(_fill(c))
    p.drawEllipse(QPointF(12, 7.5), 3.5, 3.5)
    p.drawPath(_poly([(5, 20), (6.5, 14), (17.5, 14), (19, 20), (5, 20)]))


def _prefab(p, c):  # a cube
    p.setBrush(_fill(c))
    p.drawPath(_poly([(12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5), (12, 3)]))
    p.drawPolyline([QPointF(4, 7.5), QPointF(12, 12), QPointF(20, 7.5)])
    p.drawLine(QPointF(12, 12), QPointF(12, 21))


def _image(p, c):
    _rounded(p, 3, 5, 18, 14, 2.5, c)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(8.5, 9.5), 1.6, 1.6)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(
        [
            QPointF(4, 17),
            QPointF(10, 12),
            QPointF(14, 15.5),
            QPointF(16.5, 13.5),
            QPointF(20, 16.5),
        ]
    )


def _audio(p, c):  # a note
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(7.5, 17), 3, 2.5)
    p.drawEllipse(QPointF(17, 15), 3, 2.5)
    p.setBrush(_fill(c, 140))
    p.drawPath(_poly([(10.5, 17), (10.5, 6), (20, 4), (20, 15)]))


def _grid(p, c):  # tile palette
    for x in (4, 13):
        for y in (4, 13):
            _rounded(p, x, y, 7, 7, 1.5, c, fill=(x + y) % 2 == 0)


def _layers(p, c):
    for dy, alpha in ((8, 40), (4, 70), (0, 110)):
        p.setBrush(_fill(c, alpha))
        p.drawPath(_poly([(12, 4 + dy), (21, 8 + dy), (12, 12 + dy), (3, 8 + dy), (12, 4 + dy)]))


def _sliders(p, c):  # inspector
    for y, x in ((6, 15), (12, 8), (18, 13)):
        p.drawLine(QPointF(3, y), QPointF(21, y))
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)


def _terminal(p, c):
    _rounded(p, 3, 4, 18, 16, 3, c)
    p.drawPolyline([QPointF(7, 9), QPointF(10, 12), QPointF(7, 15)])
    p.drawLine(QPointF(12, 15.5), QPointF(17, 15.5))


def _bug(p, c):
    p.setBrush(_fill(c))
    p.drawEllipse(QRectF(7, 7, 10, 13))
    p.drawLine(QPointF(12, 10), QPointF(12, 20))
    for y in (11, 15):
        p.drawLine(QPointF(7, y), QPointF(3.5, y - 1.5))
        p.drawLine(QPointF(17, y), QPointF(20.5, y - 1.5))
    p.drawLine(QPointF(9.5, 7.5), QPointF(8, 4))
    p.drawLine(QPointF(14.5, 7.5), QPointF(16, 4))


def _chart(p, c):  # profiler
    p.drawLine(QPointF(3, 20), QPointF(21, 20))
    for x, h in ((5, 6), (10, 12), (15, 8)):
        _rounded(p, x, 20 - h - 1, 3.5, h, 1, c)
    p.drawPolyline([QPointF(4, 11), QPointF(9, 6), QPointF(13, 9), QPointF(20, 3.5)])


def _warning(p, c):
    p.setBrush(_fill(c, 110))
    p.drawPath(_poly([(12, 3.5), (21, 19.5), (3, 19.5), (12, 3.5)]))
    p.drawLine(QPointF(12, 9.5), QPointF(12, 13.5))
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(12, 16.6), 0.8, 0.8)


def _plus(p, c):
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _trash(p, c):
    p.setBrush(_fill(c))
    p.drawPath(_poly([(6, 7), (7.2, 20), (16.8, 20), (18, 7)]))
    p.drawLine(QPointF(4, 7), QPointF(20, 7))
    p.drawPolyline([QPointF(9.5, 7), QPointF(10, 4), QPointF(14, 4), QPointF(14.5, 7)])
    p.drawLine(QPointF(10.5, 11), QPointF(10.5, 16.5))
    p.drawLine(QPointF(13.5, 11), QPointF(13.5, 16.5))


def _check(p, c):
    p.drawPolyline([QPointF(5, 12.5), QPointF(10, 17.5), QPointF(19.5, 6.5)])


def _save(p, c):
    _rounded(p, 4, 4, 16, 16, 2.5, c)
    p.setBrush(QColor(c))
    p.drawRect(QRectF(8, 4, 7, 4.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(7.5, 12.5, 9, 7.5), 1, 1)


def _copy(p, c):
    _rounded(p, 8, 8, 12, 12, 2.5, c)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline([QPointF(5, 15), QPointF(4, 15), QPointF(4, 4), QPointF(15, 4), QPointF(15, 5)])


def _reload(p, c):
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(5, 5, 14, 14), 60 * 16, 290 * 16)
    p.setBrush(QColor(c))
    p.drawPath(_poly([(16.5, 2.5), (19.5, 7.5), (13.5, 8), (16.5, 2.5)]))


def _search(p, c):
    p.setBrush(_fill(c, 40))
    p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
    p.drawLine(QPointF(15, 15), QPointF(20.5, 20.5))


def _gear(p, c):
    p.setBrush(_fill(c))
    p.drawPath(_star(12, 12, 9, 6.8, n=8, rot=0))
    p.setCompositionMode(QPainter.CompositionMode_Clear)
    p.setBrush(QColor(0, 0, 0))
    p.drawEllipse(QPointF(12, 12), 3, 3)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(12, 12), 3, 3)


def _export(p, c):  # a box with an up arrow
    p.setBrush(_fill(c))
    p.drawPath(_poly([(4, 11), (4, 20), (20, 20), (20, 11)]))
    p.drawLine(QPointF(12, 15), QPointF(12, 3.5))
    p.drawPolyline([QPointF(8, 7.5), QPointF(12, 3.5), QPointF(16, 7.5)])


def _person(p, c):  # actor
    p.setBrush(_fill(c, 110))
    p.drawEllipse(QPointF(12, 8), 4, 4)
    p.setBrush(_fill(c))
    path = QPainterPath(QPointF(4, 21))
    path.cubicTo(QPointF(4, 14), QPointF(20, 14), QPointF(20, 21))
    p.drawPath(path)


def _shield(p, c):  # class
    path = QPainterPath(QPointF(12, 3))
    path.lineTo(20, 6)
    path.cubicTo(QPointF(20, 14), QPointF(16, 19), QPointF(12, 21))
    path.cubicTo(QPointF(8, 19), QPointF(4, 14), QPointF(4, 6))
    path.closeSubpath()
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(12, 7), QPointF(12, 17))


def _star_icon(p, c):  # skill
    p.setBrush(_fill(c, 120))
    p.drawPath(_star(12, 12.5, 9, 3.8))


def _potion(p, c):  # item
    p.drawLine(QPointF(10, 3.5), QPointF(14, 3.5))
    path = QPainterPath(QPointF(10, 4))
    path.lineTo(10, 9)
    path.cubicTo(QPointF(4, 11), QPointF(4, 21), QPointF(12, 21))
    path.cubicTo(QPointF(20, 21), QPointF(20, 11), QPointF(14, 9))
    path.lineTo(14, 4)
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.setBrush(_fill(c, 150))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(7.5, 13, 9, 6))


def _sword(p, c):  # weapon
    p.drawLine(QPointF(5, 19), QPointF(18.5, 5.5))
    p.drawLine(QPointF(18.5, 5.5), QPointF(20, 4))
    p.drawLine(QPointF(5.5, 14), QPointF(10, 18.5))
    p.drawLine(QPointF(3.5, 20.5), QPointF(6, 18))


def _armor(p, c):
    p.setBrush(_fill(c))
    p.drawPath(
        _poly(
            [
                (8, 4),
                (12, 6),
                (16, 4),
                (21, 7),
                (19, 11),
                (17, 10),
                (17, 20),
                (7, 20),
                (7, 10),
                (5, 11),
                (3, 7),
                (8, 4),
            ]
        )
    )


def _skull(p, c):  # enemy
    path = QPainterPath(QPointF(6, 16))
    path.cubicTo(QPointF(2, 7), QPointF(8, 3), QPointF(12, 3))
    path.cubicTo(QPointF(16, 3), QPointF(22, 7), QPointF(18, 16))
    path.lineTo(17, 20)
    path.lineTo(7, 20)
    path.closeSubpath()
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(9, 11.5), 1.9, 2.1)
    p.drawEllipse(QPointF(15, 11.5), 1.9, 2.1)


def _troop(p, c):
    for dx, alpha in ((-4, 50), (4, 50), (0, 110)):
        p.setBrush(_fill(c, alpha))
        p.drawEllipse(QPointF(12 + dx, 9 if dx else 8), 3, 3)
    path = QPainterPath(QPointF(5, 20))
    path.cubicTo(QPointF(5, 13), QPointF(19, 13), QPointF(19, 20))
    p.setBrush(_fill(c))
    p.drawPath(path)


def _drop(p, c):  # state
    path = QPainterPath(QPointF(12, 3))
    path.cubicTo(QPointF(16, 9), QPointF(19, 12), QPointF(19, 15))
    path.cubicTo(QPointF(19, 19), QPointF(16, 21), QPointF(12, 21))
    path.cubicTo(QPointF(8, 21), QPointF(5, 19), QPointF(5, 15))
    path.cubicTo(QPointF(5, 12), QPointF(8, 9), QPointF(12, 3))
    p.setBrush(_fill(c, 100))
    p.drawPath(path)


def _film(p, c):  # animation
    _rounded(p, 3, 5, 18, 14, 2, c)
    for x in (6, 10, 14, 18):
        p.drawLine(QPointF(x, 5), QPointF(x - 1, 8))
    p.drawLine(QPointF(3, 8), QPointF(21, 8))
    p.setBrush(QColor(c))
    p.drawPath(_poly([(10, 11), (15, 13.5), (10, 16), (10, 11)]))


def _sparkle(p, c):  # VFX
    p.setBrush(_fill(c, 130))
    p.drawPath(_star(10, 13, 7.5, 2.2, n=4, rot=-90))
    p.drawPath(_star(18, 6, 3.5, 1.1, n=4, rot=-90))


def _gamepad(p, c):  # input map
    path = QPainterPath(QPointF(7, 7))
    path.lineTo(17, 7)
    path.cubicTo(QPointF(22, 7), QPointF(23, 19), QPointF(19, 19))
    path.cubicTo(QPointF(16.5, 19), QPointF(16, 15), QPointF(12, 15))
    path.cubicTo(QPointF(8, 15), QPointF(7.5, 19), QPointF(5, 19))
    path.cubicTo(QPointF(1, 19), QPointF(2, 7), QPointF(7, 7))
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(6, 11), QPointF(10, 11))
    p.drawLine(QPointF(8, 9), QPointF(8, 13))
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(16, 10), 1, 1)
    p.drawEllipse(QPointF(18, 12.5), 1, 1)


def _timeline(p, c):
    p.drawLine(QPointF(3, 20), QPointF(21, 20))
    for y, x0, x1 in ((6, 4, 13), (11, 8, 19), (16, 5, 11)):
        _rounded(p, x0, y - 2, x1 - x0, 4, 2, c)
    p.drawLine(QPointF(15, 3), QPointF(15, 21))


def _tree(p, c):  # behavior tree
    p.setBrush(_fill(c, 110))
    p.drawRoundedRect(QRectF(9, 3, 6, 5), 1.5, 1.5)
    for x in (3, 15):
        p.drawRoundedRect(QRectF(x, 16, 6, 5), 1.5, 1.5)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline([QPointF(12, 8), QPointF(12, 12), QPointF(6, 12), QPointF(6, 16)])
    p.drawPolyline([QPointF(12, 12), QPointF(18, 12), QPointF(18, 16)])


def _composition(p, c):  # character layers
    p.setBrush(_fill(c, 50))
    p.drawRoundedRect(QRectF(3, 6, 12, 15), 2, 2)
    p.setBrush(_fill(c, 110))
    p.drawEllipse(QPointF(15, 8), 3, 3)
    path = QPainterPath(QPointF(9, 21))
    path.cubicTo(QPointF(9, 13), QPointF(21, 13), QPointF(21, 21))
    p.drawPath(path)


def _state_machine(p, c):
    p.setBrush(_fill(c, 100))
    p.drawEllipse(QPointF(6.5, 7), 3.5, 3.5)
    p.drawEllipse(QPointF(17.5, 7), 3.5, 3.5)
    p.drawEllipse(QPointF(12, 18), 3.5, 3.5)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(10, 7), QPointF(14, 7))
    p.drawLine(QPointF(16, 10), QPointF(13.5, 14.5))
    p.drawLine(QPointF(8, 10), QPointF(10.5, 14.5))


def _flow(p, c):  # game flow
    p.setBrush(_fill(c, 100))
    p.drawRoundedRect(QRectF(3, 4, 7, 6), 1.5, 1.5)
    p.drawRoundedRect(QRectF(14, 14, 7, 6), 1.5, 1.5)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline([QPointF(6.5, 10), QPointF(6.5, 17), QPointF(14, 17)])
    p.drawPolyline([QPointF(11.5, 14.5), QPointF(14, 17), QPointF(11.5, 19.5)])


def _palette(p, c):  # presentation / runtime UI
    path = QPainterPath(QPointF(12, 3))
    path.cubicTo(QPointF(3, 3), QPointF(1, 14), QPointF(7, 19))
    path.cubicTo(QPointF(11, 22), QPointF(13, 17), QPointF(15, 18))
    path.cubicTo(QPointF(19, 20), QPointF(22, 16), QPointF(21, 11))
    path.cubicTo(QPointF(20, 6), QPointF(16, 3), QPointF(12, 3))
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    for (x, y), col in zip(
        ((8, 9), (12.5, 7), (16.5, 10)), ("#f06a6a", "#f4b545", "#56c1f5"), strict=True
    ):
        p.setBrush(QColor(col))
        p.drawEllipse(QPointF(x, y), 1.8, 1.8)


def _list(p, c):
    for y in (6, 12, 18):
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(5, y), 1.2, 1.2)
        p.drawLine(QPointF(9, y), QPointF(20, y))


def _chevron_up(p, c):
    p.drawPolyline([QPointF(6, 15), QPointF(12, 9), QPointF(18, 15)])


def _chevron_down(p, c):
    p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])


def _dialogue(p, c):
    path = QPainterPath(QPointF(5, 4))
    path.lineTo(19, 4)
    path.quadTo(21, 4, 21, 6)
    path.lineTo(21, 14)
    path.quadTo(21, 16, 19, 16)
    path.lineTo(11, 16)
    path.lineTo(6, 20.5)
    path.lineTo(7, 16)
    path.lineTo(5, 16)
    path.quadTo(3, 16, 3, 14)
    path.lineTo(3, 6)
    path.quadTo(3, 4, 5, 4)
    p.setBrush(_fill(c))
    p.drawPath(path)


def _flag(p, c):  # game start: a flag on a pole
    p.drawLine(QPointF(6, 3.5), QPointF(6, 21))
    path = QPainterPath(QPointF(6, 4.5))
    path.cubicTo(QPointF(10, 2.5), QPointF(13, 7), QPointF(19, 5))
    path.lineTo(19, 13)
    path.cubicTo(QPointF(13, 15), QPointF(10, 10.5), QPointF(6, 12.5))
    path.closeSubpath()
    p.setBrush(_fill(c))
    p.drawPath(path)


def _paw(p, c):  # pets: a paw print
    p.setBrush(_fill(c, 120))
    for x, y in ((6.5, 10.5), (10, 6.5), (14, 6.5), (17.5, 10.5)):
        p.drawEllipse(QPointF(x, y), 1.9, 2.4)
    path = QPainterPath(QPointF(12, 11.5))
    path.cubicTo(QPointF(7, 11.5), QPointF(5.5, 19), QPointF(12, 18.5))
    path.cubicTo(QPointF(18.5, 19), QPointF(17, 11.5), QPointF(12, 11.5))
    p.setBrush(_fill(c))
    p.drawPath(path)


def _gauge(p, c):  # shared gauges: a half dial with a needle
    path = QPainterPath(QPointF(3.5, 17))
    path.arcTo(QRectF(3.5, 5, 17, 24), 180, -180)
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(12, 17), QPointF(16.5, 10.5))
    p.drawLine(QPointF(3.5, 17), QPointF(20.5, 17))


def _quest(p, c):  # a scroll with a mark
    path = QPainterPath(QPointF(6, 4))
    path.lineTo(18, 4)
    path.lineTo(18, 18)
    path.cubicTo(QPointF(18, 21), QPointF(14, 21), QPointF(14, 18))
    path.lineTo(6, 18)
    path.cubicTo(QPointF(3, 18), QPointF(3, 21), QPointF(6, 21))
    path.lineTo(15, 21)
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(9, 8), QPointF(15, 8))
    p.drawLine(QPointF(9, 12), QPointF(13, 12))


def _banner(p, c):  # a hanging banner
    p.drawLine(QPointF(5, 3.5), QPointF(19, 3.5))
    path = _poly([(6, 4), (18, 4), (18, 19), (12, 15.5), (6, 19), (6, 4)])
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(9, 8), QPointF(15, 8))


def _trophy(p, c):
    path = QPainterPath(QPointF(7, 4))
    path.lineTo(17, 4)
    path.lineTo(16, 11)
    path.cubicTo(QPointF(15.5, 14), QPointF(8.5, 14), QPointF(8, 11))
    path.closeSubpath()
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.drawLine(QPointF(12, 14), QPointF(12, 18))
    p.drawLine(QPointF(8, 20), QPointF(16, 20))
    p.drawArc(QRectF(3, 5, 5, 5), 90 * 16, 180 * 16)
    p.drawArc(QRectF(16, 5, 5, 5), -90 * 16, 180 * 16)


def _chest(p, c):  # a treasure chest
    _rounded(p, 3, 10, 18, 10, 2, c)
    path = QPainterPath(QPointF(3, 10))
    path.cubicTo(QPointF(3, 3), QPointF(21, 3), QPointF(21, 10))
    p.setBrush(_fill(c, 110))
    p.drawPath(path)
    p.drawLine(QPointF(3, 12), QPointF(21, 12))
    p.setBrush(QColor(c))
    p.drawRect(QRectF(10.5, 11, 3, 4))


def _globe(p, c):
    p.drawEllipse(QPointF(12, 12), 9, 9)
    p.drawEllipse(QPointF(12, 12), 4, 9)
    p.drawLine(QPointF(3, 12), QPointF(21, 12))
    p.drawArc(QRectF(5, 5, 14, 14), 30 * 16, 120 * 16)


def _pin(p, c):  # a map pin
    path = QPainterPath(QPointF(12, 21))
    path.cubicTo(QPointF(4, 13), QPointF(4, 3), QPointF(12, 3))
    path.cubicTo(QPointF(20, 3), QPointF(20, 13), QPointF(12, 21))
    p.setBrush(_fill(c))
    p.drawPath(path)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(12, 10), 2.4, 2.4)


def _hammer(p, c):
    p.setPen(_pen(c, 2.4))
    p.drawLine(QPointF(5, 20), QPointF(14, 11))
    p.setPen(_pen(c))
    p.setBrush(_fill(c))
    p.drawPath(_poly([(11, 4), (20, 7), (18, 11), (14, 9.5), (11, 4)]))


def _cycle(p, c):  # a refresh loop
    p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 280 * 16)
    p.setBrush(QColor(c))
    p.drawPath(_poly([(19, 3), (20.5, 9.5), (14, 8.5), (19, 3)]))


def _undo(p, c):  # an arrow curving back to the left
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(19, 18))
    path.cubicTo(QPointF(19, 11), QPointF(14, 9.5), QPointF(8, 10))
    p.drawPath(path)
    p.setBrush(QColor(c))
    p.drawPath(_poly([(4, 10), (9.5, 5.5), (9.5, 14.5), (4, 10)]))


def _redo(p, c):  # the same arrow, to the right
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(5, 18))
    path.cubicTo(QPointF(5, 11), QPointF(10, 9.5), QPointF(16, 10))
    p.drawPath(path)
    p.setBrush(QColor(c))
    p.drawPath(_poly([(20, 10), (14.5, 5.5), (14.5, 14.5), (20, 10)]))


def _doodad(p, c):  # a small tree
    p.setBrush(_fill(c))
    p.drawEllipse(QPointF(12, 9), 6.5, 6)
    p.drawLine(QPointF(12, 14), QPointF(12, 21))
    p.drawLine(QPointF(9, 21), QPointF(15, 21))


def _net(p, c):  # a capture net
    p.drawEllipse(QPointF(10, 10), 6, 6)
    for x in (7, 10, 13):
        p.drawLine(QPointF(x, 5), QPointF(x, 15))
    p.drawLine(QPointF(5, 8), QPointF(15, 8))
    p.drawLine(QPointF(5, 12), QPointF(15, 12))
    p.drawLine(QPointF(14.5, 14.5), QPointF(20, 20))


def _hand_icon(p, c):  # an open hand (interactions)
    path = _poly(
        [
            (6, 12),
            (6, 7),
            (8.5, 7),
            (8.5, 11),
            (9, 4),
            (11.5, 4),
            (11.5, 11),
            (12.5, 5),
            (15, 5),
            (14.5, 12),
            (17, 8),
            (19, 9.5),
            (16.5, 17),
            (12, 20),
            (8, 18.5),
            (6, 12),
        ]
    )
    p.setBrush(_fill(c))
    p.drawPath(path)


DRAWINGS = {
    "flag": _flag,
    "paw": _paw,
    "gauge": _gauge,
    "scene": _scene,
    "rpg": _rpg,
    "battle": _battle,
    "ui": _ui,
    "events": _events,
    "code": _code,
    "multiplayer": _multiplayer,
    "play": _play,
    "stop": _stop,
    "target": _target,
    "folder": _folder,
    "project": _project,
    "entity": _entity,
    "prefab": _prefab,
    "image": _image,
    "audio": _audio,
    "tiles": _grid,
    "layers": _layers,
    "inspector": _sliders,
    "console": _terminal,
    "debugger": _bug,
    "profiler": _chart,
    "problems": _warning,
    "warning": _warning,
    "add": _plus,
    "delete": _trash,
    "apply": _check,
    "save": _save,
    "duplicate": _copy,
    "reload": _reload,
    "search": _search,
    "settings": _gear,
    "export": _export,
    "actor": _person,
    "class": _shield,
    "skill": _star_icon,
    "item": _potion,
    "weapon": _sword,
    "armor": _armor,
    "enemy": _skull,
    "troop": _troop,
    "state": _drop,
    "animation": _film,
    "vfx": _sparkle,
    "input": _gamepad,
    "timeline": _timeline,
    "behavior_tree": _tree,
    "composition": _composition,
    "state_machine": _state_machine,
    "flow": _flow,
    "presentation": _palette,
    "list": _list,
    "up": _chevron_up,
    "down": _chevron_down,
    "dialogue": _dialogue,
    "quest": _quest,
    "banner": _banner,
    "trophy": _trophy,
    "chest": _chest,
    "globe": _globe,
    "pin": _pin,
    "hammer": _hammer,
    "cycle": _cycle,
    "undo": _undo,
    "redo": _redo,
    "doodad": _doodad,
    "net": _net,
    "interact": _hand_icon,
    "assets": _folder,
}

# default colour per icon (an accent name or a hex colour)
DEFAULT_COLOR = {
    "flag": "#46b896",
    "paw": "#dca545",
    "gauge": "#e06a5c",
    "play": "success",
    "multiplayer": "multiplayer",
    "stop": "danger",
    "target": "muted",
    "folder": "assets",
    "entity": "scene",
    "prefab": "ui",
    "image": "events",
    "audio": "ui",
    "add": "success",
    "delete": "danger",
    "apply": "primary",
    "save": "primary",
    "duplicate": "muted",
    "reload": "muted",
    "search": "muted",
    "settings": "muted",
    "export": "rpg",
    "actor": "#dca545",
    "class": "#4aa9dc",
    "skill": "#9a84e0",
    "item": "#46b896",
    "weapon": "#e8894a",
    "armor": "#738ee8",
    "enemy": "#e06a5c",
    "troop": "#e06a5c",
    "state": "#52b884",
    "animation": "ui",
    "vfx": "#e8894a",
    "input": "events",
    "timeline": "battle",
    "behavior_tree": "#52b884",
    "composition": "rpg",
    "state_machine": "ui",
    "flow": "events",
    "presentation": "battle",
    "list": "muted",
    "up": "muted",
    "down": "muted",
    "dialogue": "events",
    "quest": "#dca545",
    "banner": "#e06a5c",
    "trophy": "#dcb23e",
    "chest": "#dca545",
    "globe": "#4aa9dc",
    "pin": "#46b896",
    "hammer": "#e8894a",
    "cycle": "#52b884",
    "doodad": "#86bf58",
    "net": "#9a84e0",
    "interact": "#dca545",
    "warning": "warning",
}


def color_of(name):
    value = DEFAULT_COLOR.get(name, name)
    return ACCENTS.get(value, value if str(value).startswith("#") else ACCENTS["muted"])


def pixmap(name, size=24, color=None, ratio=2.0):
    pm = QPixmap(round(size * ratio), round(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    colour = color or color_of(name)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(_pen(colour))
    painter.setBrush(Qt.NoBrush)
    DRAWINGS[name](painter, colour)
    painter.end()
    return pm


@lru_cache(maxsize=512)
def icon(name, color=None):
    """A QIcon for ``name`` (see ``DRAWINGS``); unknown names give an empty icon."""
    if name not in DRAWINGS:
        return QIcon()
    result = QIcon()
    for size in (16, 20, 24, 32):
        for ratio in (1.0, 2.0, 3.0):
            result.addPixmap(pixmap(name, size, color, ratio))
    disabled = pixmap(name, 24, "#8a8f99", 2.0)
    result.addPixmap(disabled, QIcon.Disabled)
    return result


@lru_cache(maxsize=64)
def switch_icon(name):
    """A QIcon for a checkable button: grey while off, in its colour while on or hovered.

    The workspace buttons use it so only the workspace you are in shows its colour.
    """
    if name not in DRAWINGS:
        return QIcon()
    result = QIcon()
    for size in (16, 20, 24, 32):
        for ratio in (1.0, 2.0, 3.0):
            grey = pixmap(name, size, ACCENTS["muted"], ratio)
            colour = pixmap(name, size, None, ratio)
            result.addPixmap(grey, QIcon.Normal, QIcon.Off)
            result.addPixmap(colour, QIcon.Active, QIcon.Off)
            result.addPixmap(colour, QIcon.Normal, QIcon.On)
            result.addPixmap(colour, QIcon.Active, QIcon.On)
    return result
