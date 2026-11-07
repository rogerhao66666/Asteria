"""The editor's texture painter: each texture is looked up once per paint (a missing picture
is not searched for again for every tile using it) and what it draws is unchanged."""

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from asteria.editor.assets.qt_texture_renderer import (  # noqa: E402
    QtTextureCache,
    paint_texture_draws,
)


def _draw(asset, x, opacity=1.0):
    return SimpleNamespace(
        texture_asset_id=asset,
        source=(0, 0, 4, 4),
        screen_x=x,
        screen_y=0,
        width=4,
        height=4,
        opacity=opacity,
    )


def test_each_texture_is_looked_up_once_per_paint_and_missing_ones_are_skipped(tmp_path):
    picture = QImage(4, 4, QImage.Format_ARGB32)
    picture.fill(QColor(255, 0, 0, 255))
    path = tmp_path / "red.png"
    picture.save(str(path))
    asked = []

    def resolve(asset_id):
        asked.append(asset_id)
        return path if asset_id == "red" else tmp_path / "gone.png"

    target = QImage(16, 4, QImage.Format_ARGB32)
    target.fill(QColor(0, 0, 0, 0))
    painter = QPainter(target)
    draws = [_draw("gone", 0), _draw("red", 4), _draw("gone", 8), _draw("red", 12, 0.5)]
    painted = paint_texture_draws(painter, draws, resolve, QtTextureCache())
    painter.end()
    assert painted == 2
    assert sorted(asked) == ["gone", "red"]  # once each, not once per draw
    assert target.pixelColor(5, 1).red() == 255 and target.pixelColor(5, 1).alpha() == 255
    assert target.pixelColor(1, 1).alpha() == 0  # the missing picture drew nothing
    assert 100 < target.pixelColor(13, 1).alpha() < 160  # half opacity kept per draw
