from pathlib import Path

try:
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QImage
except ImportError:
    QImage = None


class QtTextureCache:
    def __init__(self):
        self._cache = {}
        # each path as given -> its resolved form (resolving touches the file system)
        self._keys = {}

    def get(self, path):
        if QImage is None:
            raise RuntimeError("PySide6 is required")
        key = self._keys.get(path)
        if key is None:
            key = self._keys[path] = str(Path(path).resolve())
        image = self._cache.get(key)
        if image is None:
            image = QImage(key)
            if image.isNull():
                return None
            self._cache[key] = image
        return image

    def clear(self):
        self._cache.clear()
        self._keys.clear()


def paint_texture_draws(painter, draws, resolve_path, cache):
    """Draw ``draws`` (TextureDraw) with ``painter``; returns how many were drawn. Each
    texture is looked up once per paint - a missing picture is not looked for again for every
    tile that uses it - and the painter's opacity is set only when it changes."""
    painted = 0
    images = {}  # texture asset id -> its image (None: missing), for this paint
    painter.save()
    opacity = None
    try:
        for draw in draws:
            asset_id = draw.texture_asset_id
            if asset_id in images:
                image = images[asset_id]
            else:
                path = resolve_path(asset_id)
                image = images[asset_id] = None if path is None else cache.get(path)
            if image is None:
                continue
            alpha = max(0.0, min(1.0, float(draw.opacity)))
            if alpha != opacity:
                painter.setOpacity(alpha)
                opacity = alpha
            sx, sy, sw, sh = draw.source
            painter.drawImage(
                QRectF(
                    float(draw.screen_x),
                    float(draw.screen_y),
                    float(draw.width),
                    float(draw.height),
                ),
                image,
                QRect(int(sx), int(sy), int(sw), int(sh)),
            )
            painted += 1
    finally:
        painter.restore()
    return painted
