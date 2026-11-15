"""Generic combat overlay data accepted by battle presentation."""

from dataclasses import dataclass


def _role_name(role):
    value = getattr(role, "value", role)
    name = str(value).strip()
    if not name:
        raise ValueError("animation role is required")
    return name


@dataclass(frozen=True, slots=True)
class CombatantOverlay:
    """Frame-cycled texture drawn over a combatant while it plays one role."""

    texture_asset_id: str
    frames: tuple[tuple[int, int, int, int], ...]
    role: str = "attack"
    offset: tuple[float, float] = (-64.0, 0.0)

    def __post_init__(self):
        if not str(self.texture_asset_id).strip():
            raise ValueError("texture_asset_id is required")
        if not self.frames:
            raise ValueError("overlay requires at least one frame")
        object.__setattr__(self, "frames", tuple(tuple(int(v) for v in f) for f in self.frames))
        object.__setattr__(self, "role", _role_name(self.role))
        object.__setattr__(self, "offset", (float(self.offset[0]), float(self.offset[1])))
