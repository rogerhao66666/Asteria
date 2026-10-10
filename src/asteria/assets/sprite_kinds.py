"""Typed canonical asset kinds built on grid sprite sheets (AS §34 golden coverage, AP §22).

Phase-1 kinds the pipeline already had codecs for (icon, portrait, prop,
tileset, monster, vfx, audio, font, material) are complemented here by:

* ``character`` — a sprite sheet with named clips (walk / idle / ...).
* ``npc`` — a placed character with an interaction and a field behaviour.
* ``projectile`` — a sprite with motion, lifetime, collider and hit effect.
* ``skill`` — an ability's presentation: timed beats referencing VFX /
  audio / icon assets.
* ``ui`` — a nine-slice UI skin with named state regions.
* ``scene`` — a scene package: a tileset plus placed assets.

Sprite data ("sprite" payload)::

    {"image": "<relative path>", "frame_size": [w, h], "pivot": [x, y],
     "clips": {name: {"frames": [grid index...], "frame_duration": s,
                      "loop": bool, "events": {"<keyframe position>": [names]}}}}

Frames are row-major indices into the image grid. ``sprite_sheet`` /
``clip_set`` turn the data into the runtime's SpriteSheet and
AnimationClipSet, so the editor, golden tests and runtime share one path.
"""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import CanonicalAsset, ValidationIssue, ValidationReport
from .codecs import AssetCodec

SPRITE_KINDS = ("character", "npc", "projectile", "skill", "ui", "scene")
NPC_BEHAVIOURS = ("idle", "patrol", "wander")


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _size(value, label):
    w, h = (int(x) for x in value)
    if w <= 0 or h <= 0:
        raise ValueError(f"{label} must be positive")
    return (w, h)


# -- shared sprite data ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpriteClipData:
    name: str
    frames: tuple[int, ...]
    frame_duration: float
    loop: bool = True
    events: tuple[tuple[int, tuple[str, ...]], ...] = ()

    def __post_init__(self):
        _id(self.name, "clip name")
        if not self.frames or any(int(f) < 0 for f in self.frames):
            raise ValueError(f"clip {self.name} needs non-negative frames")
        if float(self.frame_duration) <= 0:
            raise ValueError(f"clip {self.name} frame_duration must be > 0")
        for position, _ in self.events:
            if not 0 <= int(position) < len(self.frames):
                raise ValueError(f"clip {self.name} event position out of range")

    @property
    def duration(self):
        return self.frame_duration * len(self.frames)

    def to_data(self):
        data = {"frames": list(self.frames), "frame_duration": self.frame_duration, "loop": self.loop}
        if self.events:
            data["events"] = {str(p): list(n) for p, n in self.events}
        return data

    @classmethod
    def from_data(cls, name, data):
        events = tuple(sorted((int(k), tuple(str(x) for x in v)) for k, v in dict(data.get("events", {})).items()))
        return cls(
            name,
            tuple(int(x) for x in data["frames"]),
            float(data["frame_duration"]),
            bool(data.get("loop", True)),
            events,
        )


@dataclass(frozen=True, slots=True)
class SpriteData:
    image: str
    frame_size: tuple[int, int]
    pivot: tuple[float, float] = (0.5, 1.0)
    clips: tuple[SpriteClipData, ...] = ()

    def __post_init__(self):
        _id(self.image, "sprite image")
        _size(self.frame_size, "frame_size")
        names = [c.name for c in self.clips]
        if len(names) != len(set(names)):
            raise ValueError("duplicate clip names")

    def clip(self, name):
        return next((c for c in self.clips if c.name == name), None)

    def grid(self, image_size):
        return image_size[0] // self.frame_size[0], image_size[1] // self.frame_size[1]

    def to_data(self):
        return {
            "image": self.image,
            "frame_size": list(self.frame_size),
            "pivot": list(self.pivot),
            "clips": {c.name: c.to_data() for c in self.clips},
        }

    @classmethod
    def from_data(cls, data):
        clips = tuple(SpriteClipData.from_data(k, v) for k, v in sorted(dict(data.get("clips", {})).items()))
        return cls(
            data["image"],
            _size(data["frame_size"], "frame_size"),
            tuple(float(x) for x in data.get("pivot", (0.5, 1.0))),
            clips,
        )

    # -- runtime -------------------------------------------------------------------
    def sprite_sheet(self, asset_id, image_size):
        from asteria.graphics import SpriteFrame, SpriteSheet

        fw, fh = self.frame_size
        columns, rows = self.grid(image_size)

        class _Texture:
            expected_kind = "texture"

            def __init__(self, value):
                self.asset_id = value

        frames = [
            SpriteFrame(c * fw, r * fh, fw, fh, self.pivot[0], self.pivot[1])
            for r in range(rows)
            for c in range(columns)
        ]
        sheet = SpriteSheet(_Texture(asset_id), frames)
        sheet.validate()
        return sheet

    def clip_set(self):
        from asteria.graphics import SpriteClip, SpriteKeyframe
        from asteria.runtime.animation_library import AnimationClipSet

        clips = {}
        for c in self.clips:
            events = dict(c.events)
            keyframes = [SpriteKeyframe(f, c.frame_duration, events.get(i, ())) for i, f in enumerate(c.frames)]
            clips[c.name] = SpriteClip(c.name, keyframes, c.loop)
        return AnimationClipSet(clips)

    def issues(self, label, image_size):
        """Dimension problems: the image must be a whole grid of frames and clips must stay inside it."""
        found = []
        fw, fh = self.frame_size
        if image_size is None:
            return [ValidationIssue("sprite.image.missing", f"{label}: {self.image}")]
        if image_size[0] % fw or image_size[1] % fh:
            found.append(
                ValidationIssue("sprite.grid.mismatch", f"{label}: {image_size} is not a grid of {self.frame_size}")
            )
        columns, rows = self.grid(image_size)
        for clip in self.clips:
            for frame in clip.frames:
                if frame >= columns * rows:
                    found.append(ValidationIssue("sprite.clip.frame", f"{label}: {clip.name} frame {frame}"))
        return found


# -- kinds -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CharacterAsset:
    canonical: CanonicalAsset
    sprite: SpriteData
    default_clip: str

    def __post_init__(self):
        if self.sprite.clip(self.default_clip) is None:
            raise ValueError("default_clip must name a clip")


@dataclass(frozen=True, slots=True)
class NpcAsset:
    canonical: CanonicalAsset
    character_id: str
    display_name: str
    interaction_event: str = ""
    prompt: str = ""
    behaviour: str = "idle"
    patrol_path: tuple[tuple[float, float], ...] = ()

    def __post_init__(self):
        _id(self.character_id, "character_id")
        if self.behaviour not in NPC_BEHAVIOURS:
            raise ValueError(f"behaviour must be one of {NPC_BEHAVIOURS}")
        if self.behaviour == "patrol" and len(self.patrol_path) < 2:
            raise ValueError("patrol needs at least two points")


@dataclass(frozen=True, slots=True)
class ProjectileAsset:
    canonical: CanonicalAsset
    sprite: SpriteData
    speed: float
    lifetime: float
    radius: float
    hit_vfx_id: str = ""

    def __post_init__(self):
        if self.speed <= 0 or self.lifetime <= 0 or self.radius <= 0:
            raise ValueError("speed, lifetime and radius must be positive")
        if self.sprite.clip("fly") is None:
            raise ValueError("projectile needs a 'fly' clip")


@dataclass(frozen=True, slots=True)
class SkillBeat:
    at: float
    channel: str
    cue: str

    def __post_init__(self):
        if self.at < 0:
            raise ValueError("beat time must be >= 0")
        if self.channel not in ("animation", "vfx", "audio", "camera", "screen_fx", "projectile"):
            raise ValueError(f"unknown beat channel {self.channel}")


@dataclass(frozen=True, slots=True)
class SkillAsset:
    canonical: CanonicalAsset
    ability_id: str
    icon_id: str
    duration: float
    beats: tuple[SkillBeat, ...]

    def __post_init__(self):
        _id(self.ability_id, "ability_id")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        if any(b.at > self.duration for b in self.beats):
            raise ValueError("beat after the skill ends")
        object.__setattr__(self, "beats", tuple(sorted(self.beats, key=lambda b: (b.at, b.channel, b.cue))))

    def referenced_assets(self):
        ids = [self.icon_id] if self.icon_id else []
        ids += [b.cue for b in self.beats if b.channel in ("vfx", "projectile")]
        return tuple(dict.fromkeys(ids))


@dataclass(frozen=True, slots=True)
class UiAsset:
    canonical: CanonicalAsset
    image: str
    size: tuple[int, int]
    slices: tuple[int, int, int, int]  # left, top, right, bottom
    states: tuple[tuple[str, tuple[int, int, int, int]], ...]  # name -> (x, y, w, h)

    def __post_init__(self):
        _size(self.size, "size")
        left, top, right, bottom = self.slices
        if min(self.slices) < 0:
            raise ValueError("slices must be >= 0")
        names = [n for n, _ in self.states]
        if not names or len(names) != len(set(names)):
            raise ValueError("ui needs uniquely named states")
        for name, (_, _, w, h) in self.states:
            if left + right >= w or top + bottom >= h:
                raise ValueError(f"state {name} is smaller than its nine-slice borders")


@dataclass(frozen=True, slots=True)
class ScenePlacement:
    asset_id: str
    x: float
    y: float
    layer: int = 0


@dataclass(frozen=True, slots=True)
class SceneAsset:
    canonical: CanonicalAsset
    tileset_id: str
    size: tuple[int, int]  # in tiles
    tiles: tuple[int, ...]  # row-major tile ids, -1 = empty
    placements: tuple[ScenePlacement, ...]
    spawn: tuple[float, float]

    def __post_init__(self):
        _size(self.size, "scene size")
        if len(self.tiles) != self.size[0] * self.size[1]:
            raise ValueError("tiles must fill the scene grid")

    def referenced_assets(self):
        return tuple(dict.fromkeys([self.tileset_id] + [p.asset_id for p in self.placements]))


# -- codecs -----------------------------------------------------------------------


def _canon(doc):
    return doc.manifest.canonical()


def _codec(kind, decode, encode):
    return AssetCodec(kind, decode, encode)


def character_codec():
    return _codec(
        "character",
        lambda d: CharacterAsset(_canon(d), SpriteData.from_data(d.payload["sprite"]), d.payload["default_clip"]),
        lambda a: {"sprite": a.sprite.to_data(), "default_clip": a.default_clip},
    )


def npc_codec():
    def dec(d):
        p = d.payload
        return NpcAsset(
            _canon(d),
            p["character_id"],
            p["display_name"],
            p.get("interaction_event", ""),
            p.get("prompt", ""),
            p.get("behaviour", "idle"),
            tuple(tuple(float(v) for v in pt) for pt in p.get("patrol_path", ())),
        )

    def enc(a):
        return {
            "character_id": a.character_id,
            "display_name": a.display_name,
            "interaction_event": a.interaction_event,
            "prompt": a.prompt,
            "behaviour": a.behaviour,
            "patrol_path": [list(p) for p in a.patrol_path],
        }

    return _codec("npc", dec, enc)


def projectile_codec():
    def dec(d):
        p = d.payload
        return ProjectileAsset(
            _canon(d),
            SpriteData.from_data(p["sprite"]),
            float(p["speed"]),
            float(p["lifetime"]),
            float(p["radius"]),
            p.get("hit_vfx_id", ""),
        )

    def enc(a):
        return {
            "sprite": a.sprite.to_data(),
            "speed": a.speed,
            "lifetime": a.lifetime,
            "radius": a.radius,
            "hit_vfx_id": a.hit_vfx_id,
        }

    return _codec("projectile", dec, enc)


def skill_codec():
    def dec(d):
        p = d.payload
        beats = tuple(SkillBeat(float(b["at"]), b["channel"], b["cue"]) for b in p.get("beats", ()))
        return SkillAsset(_canon(d), p["ability_id"], p.get("icon_id", ""), float(p["duration"]), beats)

    def enc(a):
        return {
            "ability_id": a.ability_id,
            "icon_id": a.icon_id,
            "duration": a.duration,
            "beats": [{"at": b.at, "channel": b.channel, "cue": b.cue} for b in a.beats],
        }

    return _codec("skill", dec, enc)


def ui_codec():
    def dec(d):
        p = d.payload
        states = tuple(sorted((k, tuple(int(x) for x in v)) for k, v in dict(p["states"]).items()))
        return UiAsset(_canon(d), p["image"], _size(p["size"], "size"), tuple(int(x) for x in p["slices"]), states)

    def enc(a):
        return {
            "image": a.image,
            "size": list(a.size),
            "slices": list(a.slices),
            "states": {k: list(v) for k, v in a.states},
        }

    return _codec("ui", dec, enc)


def scene_codec():
    def dec(d):
        p = d.payload
        placements = tuple(
            ScenePlacement(x["asset_id"], float(x["x"]), float(x["y"]), int(x.get("layer", 0))) for x in p["placements"]
        )
        return SceneAsset(
            _canon(d),
            p["tileset_id"],
            _size(p["size"], "scene size"),
            tuple(int(t) for t in p["tiles"]),
            placements,
            tuple(float(v) for v in p["spawn"]),
        )

    def enc(a):
        return {
            "tileset_id": a.tileset_id,
            "size": list(a.size),
            "tiles": list(a.tiles),
            "placements": [{"asset_id": p.asset_id, "x": p.x, "y": p.y, "layer": p.layer} for p in a.placements],
            "spawn": list(a.spawn),
        }

    return _codec("scene", dec, enc)


def install_sprite_kind_codecs(registry):
    for codec in (character_codec(), npc_codec(), projectile_codec(), skill_codec(), ui_codec(), scene_codec()):
        registry.register(codec, replace=True)
    return registry


# -- validators -------------------------------------------------------------------


def sprite_kind_validators(image_size):
    """Validators for the kinds above; ``image_size(uri) -> (w, h) | None`` measures images."""

    def report(asset, issues):
        return ValidationReport(asset.canonical.asset_id, tuple(issues))

    def sprite(asset):
        return report(asset, asset.sprite.issues(asset.canonical.asset_id, image_size(asset.sprite.image)))

    def ui(asset):
        size = image_size(asset.image)
        issues = []
        if size is None:
            issues.append(ValidationIssue("ui.image.missing", asset.image))
        else:
            if tuple(size) != asset.size:
                issues.append(ValidationIssue("ui.image.size", f"{asset.image} is {size}, declared {asset.size}"))
            for name, (x, y, w, h) in asset.states:
                if x + w > size[0] or y + h > size[1]:
                    issues.append(ValidationIssue("ui.state.bounds", name))
        return report(asset, issues)

    return {
        "character": sprite,
        "projectile": sprite,
        "ui": ui,
        # Cross-asset references are checked against manifest dependencies by
        # the loader / golden suite (validators see one asset at a time).
    }


def standard_asset_codecs():
    """Every typed codec the engine ships (Phase-1 kinds, extended kinds, passthrough fallbacks)."""
    from .builtin_codecs import install_simple_typed_codecs
    from .codecs import AssetCodecRegistry, install_common_passthrough_codecs
    from .complex_codecs import install_complex_typed_codecs

    registry = AssetCodecRegistry()
    install_common_passthrough_codecs(registry)
    install_simple_typed_codecs(registry)
    install_complex_typed_codecs(registry)
    install_sprite_kind_codecs(registry)
    return registry


__all__ = [
    "SPRITE_KINDS",
    "CharacterAsset",
    "NpcAsset",
    "ProjectileAsset",
    "SceneAsset",
    "ScenePlacement",
    "SkillAsset",
    "SkillBeat",
    "SpriteClipData",
    "SpriteData",
    "UiAsset",
    "install_sprite_kind_codecs",
    "sprite_kind_validators",
    "standard_asset_codecs",
]
