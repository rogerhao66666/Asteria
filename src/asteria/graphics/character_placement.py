from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterPlacement:
    frame_size: tuple[int, int]
    pivot: tuple[float, float] = (0.5, 1.0)
    object_character: bool = False

    def __post_init__(self):
        width, height = self.frame_size
        if width <= 0 or height <= 0:
            raise ValueError("frame dimensions must be positive")
        if not 0.0 <= self.pivot[0] <= 1.0 or not 0.0 <= self.pivot[1] <= 1.0:
            raise ValueError("pivot must be normalized")


def standing_point_for_cell(
    column: int, row: int, tile_size: tuple[int, int] = (48, 48)
) -> tuple[float, float]:
    width, height = tile_size
    if width <= 0 or height <= 0:
        raise ValueError("tile dimensions must be positive")
    return ((int(column) + 0.5) * width, (int(row) + 1.0) * height)


def frame_rect_at_standing_point(
    standing_point: tuple[float, float], placement: CharacterPlacement
) -> tuple[float, float, float, float]:
    width, height = placement.frame_size
    left = float(standing_point[0]) - width * placement.pivot[0]
    top = float(standing_point[1]) - height * placement.pivot[1]
    return (left, top, left + width, top + height)


def integer_preview_scale(frame_size: tuple[int, int], available_size: tuple[int, int]) -> int:
    width, height = frame_size
    available_width, available_height = available_size
    if min(width, height, available_width, available_height) <= 0:
        raise ValueError("dimensions must be positive")
    return max(1, min(available_width // width, available_height // height))


def feet_pivot_y(image, frames) -> float:
    """The pivot height that puts a sheet's feet on its standing point: one past the lowest
    row with an opaque pixel in any of ``frames`` (``(x, y, w, h)`` rectangles of the PIL
    ``image``), over the frame height; 1.0 (the bottom edge) when the frames are empty.

    Art often leaves empty rows under the feet; with the pivot at the frame's bottom such a
    figure is drawn that much above where it stands, so it seems to stand on whatever is
    under it and sorts wrongly against its neighbours. One value for the whole sheet: a walk
    bobs on its feet instead of the feet bobbing on the ground."""
    alpha = image.convert("RGBA").getchannel("A")
    lowest, height = -1, 0
    for x, y, w, h in frames:
        height = max(height, int(h))
        box = alpha.crop((int(x), int(y), int(x + w), int(y + h))).getbbox()
        if box is not None:
            lowest = max(lowest, box[3])  # one past the last opaque row
    if lowest <= 0 or height <= 0:
        return 1.0
    return round(min(1.0, lowest / height), 4)


def picture_box(image, frames):
    """``(width, height, offset_x, offset_y)`` of the box that covers every opaque pixel of
    ``frames`` (``(x, y, w, h, pivot_x, pivot_y)`` in the PIL ``image``), measured from the
    standing point (each frame's pivot), y down: a collider of this size at this offset
    blocks the whole picture. None when the frames are empty (D88)."""
    alpha = image.convert("RGBA").getchannel("A")
    left = top = right = bottom = None
    for x, y, w, h, pivot_x, pivot_y in frames:
        box = alpha.crop((int(x), int(y), int(x + w), int(y + h))).getbbox()
        if box is None:
            continue
        px, py = float(pivot_x) * w, float(pivot_y) * h
        l, t, r, b = box[0] - px, box[1] - py, box[2] - px, box[3] - py
        left = l if left is None else min(left, l)
        top = t if top is None else min(top, t)
        right = r if right is None else max(right, r)
        bottom = b if bottom is None else max(bottom, b)
    if left is None:
        return None
    return (right - left, bottom - top, (left + right) / 2, (top + bottom) / 2)
