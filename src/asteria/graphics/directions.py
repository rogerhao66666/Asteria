from dataclasses import dataclass

from .sprites import SpriteClip, SpriteKeyframe, SpriteSheet

VALID_DIRECTIONS = ("down", "left", "right", "up")


@dataclass(slots=True)
class DirectionalClips:
    idle: dict[str, SpriteClip]
    walk: dict[str, SpriteClip]
    run: dict[str, SpriteClip] | None = None

    def validate(self, sheet: SpriteSheet):
        for group_name, group in (("idle", self.idle), ("walk", self.walk)):
            if set(group) != set(VALID_DIRECTIONS):
                raise ValueError(f"{group_name} requires four directions")
            for clip in group.values():
                clip.validate(sheet)
        if self.run is not None:
            if set(self.run) != set(VALID_DIRECTIONS):
                raise ValueError("run requires four directions")
            for clip in self.run.values():
                clip.validate(sheet)


def grid_four_direction_clips(
    *,
    rows,
    frames_per_direction,
    frame_duration,
    row_order=VALID_DIRECTIONS,
    name_prefix="walk",
):
    if len(row_order) != 4 or set(row_order) != set(VALID_DIRECTIONS):
        raise ValueError("row_order must contain four canonical directions")
    if frames_per_direction <= 0 or frame_duration <= 0:
        raise ValueError("positive timing required")
    if rows < 4:
        raise ValueError("at least four rows required")
    result = {}
    for row, direction in enumerate(row_order):
        start = row * frames_per_direction
        result[direction] = SpriteClip(
            f"{name_prefix}_{direction}",
            [SpriteKeyframe(start + i, frame_duration) for i in range(frames_per_direction)],
            True,
        )
    return result
