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


def standing_point_for_cell(column: int, row: int, tile_size: tuple[int, int] = (48, 48)) -> tuple[float, float]:
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
