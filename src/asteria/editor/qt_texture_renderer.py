from pathlib import Path

try:
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QImage
except ImportError:
    QImage = None


class QtTextureCache:
    def __init__(self):
        self._cache = {}

    def get(self, path):
        if QImage is None:
            raise RuntimeError("PySide6 is required")
        key = str(Path(path).resolve())
        image = self._cache.get(key)
        if image is None:
            image = QImage(key)
            if image.isNull():
                return None
            self._cache[key] = image
        return image

    def clear(self):
        self._cache.clear()


def paint_texture_draws(painter, draws, resolve_path, cache):
    painted = 0
    for draw in draws:
        path = resolve_path(draw.texture_asset_id)
        if path is None:
            continue
        image = cache.get(path)
        if image is None:
            continue
        sx, sy, sw, sh = draw.source
        source = QRect(int(sx), int(sy), int(sw), int(sh))
        target = QRectF(
            float(draw.screen_x),
            float(draw.screen_y),
            float(draw.width),
            float(draw.height),
        )
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, float(draw.opacity))))
        painter.drawImage(target, image, source)
        painter.restore()
        painted += 1
    return painted
