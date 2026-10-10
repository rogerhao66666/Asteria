"""Golden asset suite (ASTERIA_ASSET_SPEC §34, CB13).

The minimum golden suite is one asset per category::

    golden_character golden_npc golden_monster golden_tileset golden_prop golden_icon
    golden_vfx golden_projectile golden_skill golden_ui golden_scene

``run_golden_suite(root)`` performs the eight required checks on every asset:

1. import succeeds          — the whole folder loads through AssetStore with typed codecs
2. metadata parses          — manifest fields decode and the payload round-trips (encode -> decode)
3. dimensions match         — images exist and are whole frame grids / declared sizes
4. assets reload            — a second, independent load yields identical assets
5. runtime resolves refs    — manifest dependencies resolve, payload references are declared,
                              sprites build runtime SpriteSheets / AnimationClipSets
6. animations play          — every clip is played at 60 Hz; the frame sequence is recorded
7. events fire              — keyframe events and skill beats fire in order; the log is recorded
8. scene packages correctly — the scene and its dependency closure are packaged and reload

It returns a deterministic summary per asset (compared with committed
baselines by the tests) and a list of failures. Nothing is estimated: a
check that cannot run is a failure.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

GOLDEN_CATEGORIES = (
    "golden_character",
    "golden_npc",
    "golden_monster",
    "golden_tileset",
    "golden_prop",
    "golden_icon",
    "golden_vfx",
    "golden_projectile",
    "golden_skill",
    "golden_ui",
    "golden_scene",
)
CHECKS = (
    "import",
    "metadata",
    "dimensions",
    "reload",
    "references",
    "animations",
    "events",
    "package",
)
STEP = 1.0 / 60.0


@dataclass
class GoldenReport:
    summaries: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)  # (asset_id, check, message)
    checks_run: dict = field(default_factory=dict)  # asset_id -> [check, ...]

    def fail(self, asset_id, check, message):
        self.failures.append((asset_id, check, str(message)))

    def ran(self, asset_id, check):
        self.checks_run.setdefault(asset_id, []).append(check)

    @property
    def ok(self):
        return not self.failures


def image_size_resolver(root):
    from PIL import Image

    root = Path(root)

    def size(uri):
        path = root / str(uri)
        if not path.is_file():
            return None
        with Image.open(path) as image:
            return image.size

    return size


def _store(root):
    from asteria.assets.monster import MonsterValidator
    from asteria.assets.prop import PropValidator
    from asteria.assets.sprite_kinds import sprite_kind_validators, standard_asset_codecs
    from asteria.assets.store import AssetStore
    from asteria.assets.tileset import TilesetValidator
    from asteria.assets.vfx import VFXValidator

    validators = dict(sprite_kind_validators(image_size_resolver(root)))
    validators.update(
        tileset=TilesetValidator().validate,
        prop=PropValidator().validate,
        monster=MonsterValidator().validate,
        vfx=VFXValidator().validate,
    )
    return AssetStore(standard_asset_codecs(), validators=validators)


def _documents(root):
    docs = {}
    for path in sorted(Path(root).rglob("*.asset.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        docs[data["asset_id"]] = (str(path), data)
    return docs


def _grid_clip(name, frames, durations, loop, events=()):
    """Runtime clip from grid indices and per-frame durations (seconds)."""
    from asteria.graphics import SpriteClip, SpriteKeyframe

    event_map = dict(events)
    keyframes = [
        SpriteKeyframe(int(f), float(d), tuple(event_map.get(i, ()))) for i, (f, d) in enumerate(zip(frames, durations))
    ]
    return SpriteClip(name, keyframes, loop)


def _play(clip):
    """Play ``clip`` at 60 Hz for one cycle (two for loops); returns (frame changes, events with times)."""
    from asteria.runtime.animation import AnimatorState

    duration = sum(k.duration for k in clip.keyframes)
    animator = AnimatorState(clip)
    frames, events, t = [animator.frame_index], [], 0.0
    for name in animator.drain_events():
        events.append((0.0, name[-1] if isinstance(name, tuple) else name))
    steps = int(round((duration * (2 if clip.loop else 1)) / STEP)) + 1
    for _ in range(steps):
        animator.update(STEP)
        t += STEP
        if animator.frame_index != frames[-1]:
            frames.append(animator.frame_index)
        for item in animator.drain_events():
            events.append((round(t, 4), item[-1] if isinstance(item, tuple) else item))
    return frames, events


def _clips_of(asset):
    """``{name: SpriteClip}`` for any golden asset that animates, or ``{}``."""
    from asteria.presentation.fidelity import HighFidelityClip

    sprite = getattr(asset, "sprite", None)
    if sprite is not None:
        return dict(sprite.clip_set().clips)
    hifi = []
    for item in getattr(asset, "animations", ()) or ():  # monster
        hifi.append((item.name, item.clip))
    for item in getattr(asset, "variants", ()) or ():  # vfx
        if isinstance(getattr(item, "clip", None), HighFidelityClip):
            hifi.append((item.name, item.clip))
    clips = {}
    for tile in getattr(asset, "tiles", ()) or ():  # tileset animated tiles
        if getattr(tile, "animation", ()):
            seconds = (tile.frame_ms or 100) / 1000.0
            clips[f"tile_{tile.tile_id}"] = _grid_clip(
                f"tile_{tile.tile_id}", list(tile.animation), [seconds] * len(tile.animation), True
            )
    for name, clip in hifi:
        durations = (
            [t.duration_ms / 1000.0 for t in clip.timings]
            if len(clip.timings) > 1
            else [clip.timings[0].duration_ms / 1000.0] * len(clip.frames)
        )
        clips[name] = _grid_clip(name, [int(f) for f in clip.frames], durations, clip.loop)
    return clips


def _sprite_source(asset, manifest):
    """(image uri, frame size) the asset's frames index into, or None."""
    sprite = getattr(asset, "sprite", None)
    if sprite is not None:
        return sprite.image, sprite.frame_size
    tile_size = getattr(asset, "tile_size", None)
    if tile_size is not None:
        return manifest.source, tuple(tile_size)
    for item in list(getattr(asset, "animations", ()) or ()) + list(getattr(asset, "variants", ()) or ()):
        clip = getattr(item, "clip", None)
        if clip is not None:
            return manifest.source, tuple(clip.frame_size)
    return None


def _payload_references(asset):
    refs = []
    for attr in ("character_id", "hit_vfx_id"):
        value = getattr(asset, attr, "")
        if value:
            refs.append(value)
    referenced = getattr(asset, "referenced_assets", None)
    if callable(referenced):
        refs.extend(referenced())
    return tuple(dict.fromkeys(refs))


def run_golden_suite(root):
    """Run the eight AS§34 checks on every golden asset under ``root``."""
    from asteria.assets.asset_package import package_assets

    root = Path(root)
    report = GoldenReport()
    image_size = image_size_resolver(root)
    store = _store(root)
    loaded = store.load(root)
    if not loaded.ok:
        for issue in loaded.issues:
            report.fail(Path(issue.path).name, "import", f"{issue.code}: {issue.message}")
        return report
    by_id = {x.manifest.asset_id: x for x in loaded.loaded}
    for category in GOLDEN_CATEGORIES:
        if category not in by_id:
            report.fail(category, "import", "golden asset missing")
    documents = _documents(root)
    codecs = store.codecs

    # 4. reload: an independent second load must produce identical assets.
    second = _store(root).load(root)
    second_by_id = {x.manifest.asset_id: x for x in second.loaded}

    for asset_id in sorted(by_id):
        item = by_id[asset_id]
        manifest, asset = item.manifest, item.asset
        summary = {"kind": manifest.kind, "dependencies": list(manifest.dependencies), "tags": list(manifest.tags)}
        report.ran(asset_id, "import")

        # 2. metadata
        report.ran(asset_id, "metadata")
        try:
            encoded = codecs.encode_asset(manifest.kind, asset)
            again = codecs.decode_document({**documents[asset_id][1], "payload": encoded})
            if again != asset:
                report.fail(asset_id, "metadata", "payload does not round-trip")
        except Exception as exc:  # noqa: BLE001 - a codec error is a failed check
            report.fail(asset_id, "metadata", exc)

        # 3. dimensions
        report.ran(asset_id, "dimensions")
        source = _sprite_source(asset, manifest)
        dims = {}
        for uri in dict.fromkeys(
            [manifest.source] + [v.image_uri for v in getattr(asset, "visuals", ())] + [getattr(asset, "image", "")]
        ):
            if uri and uri.endswith(".png"):
                size = image_size(uri)
                if size is None:
                    report.fail(asset_id, "dimensions", f"missing image {uri}")
                    dims[uri] = None
                else:
                    digest = hashlib.sha256((root / uri).read_bytes()).hexdigest()[:16]
                    dims[uri] = {"size": list(size), "sha256": digest}
        if source is not None:
            uri, frame = source
            size = image_size(uri)
            if size is None or size[0] % frame[0] or size[1] % frame[1]:
                report.fail(asset_id, "dimensions", f"{uri} {size} is not a grid of {frame}")
            else:
                dims["grid"] = [size[0] // frame[0], size[1] // frame[1]]
        tileset_size = getattr(asset, "image_size", None)
        if tileset_size is not None and image_size(manifest.source) != tuple(tileset_size):
            report.fail(
                asset_id, "dimensions", f"tileset image is {image_size(manifest.source)}, declared {tileset_size}"
            )
        for visual in getattr(asset, "visuals", ()):
            if image_size(visual.image_uri) != tuple(visual.size):
                report.fail(asset_id, "dimensions", f"prop visual {visual.image_uri} size mismatch")
        summary["dimensions"] = dims

        # 4. reload
        report.ran(asset_id, "reload")
        other = second_by_id.get(asset_id)
        if other is None or other.asset != asset:
            report.fail(asset_id, "reload", "second load differs")

        # 5. references
        report.ran(asset_id, "references")
        for dep in manifest.dependencies:
            if dep not in by_id:
                report.fail(asset_id, "references", f"unresolved dependency {dep}")
        refs = _payload_references(asset)
        undeclared = [r for r in refs if r not in manifest.dependencies]
        if undeclared:
            report.fail(asset_id, "references", f"payload references not declared as dependencies: {undeclared}")
        summary["references"] = list(refs)
        clips = {}
        try:
            clips = _clips_of(asset)
            if source is not None and clips:
                from asteria.runtime.animation_library import AnimationClipSet

                uri, frame = source
                sheet = _grid_sheet(asset_id, image_size(uri), frame)
                AnimationClipSet(clips).validate(sheet)
                summary["runtime_frames"] = len(sheet.frames)
        except Exception as exc:  # noqa: BLE001
            report.fail(asset_id, "references", f"runtime resolution failed: {exc}")

        # 6 + 7. animations play, events fire
        if clips:
            report.ran(asset_id, "animations")
            report.ran(asset_id, "events")
            played, fired = {}, {}
            for name, clip in sorted(clips.items()):
                frames, events = _play(clip)
                if len(clip.keyframes) > 1 and len(frames) < 2:
                    report.fail(asset_id, "animations", f"{name} never advanced")
                played[name] = frames
                if events:
                    fired[name] = [[t, e] for t, e in events]
            summary["animations"] = played
            summary["events"] = fired
            declared_events = sum(len(k.events) for c in clips.values() for k in c.keyframes)
            if declared_events and not fired:
                report.fail(asset_id, "events", "declared keyframe events never fired")
        beats = getattr(asset, "beats", None)
        if beats:
            report.ran(asset_id, "events")
            fired = _fire_beats(asset)
            summary["beats"] = fired
            if [b[1:] for b in fired] != [
                [b.channel, b.cue] for b in sorted(beats, key=lambda b: (b.at, b.channel, b.cue))
            ]:
                report.fail(asset_id, "events", "skill beats fired out of order")

        report.summaries[asset_id] = summary

    # 8. scene package
    scene_id = "golden_scene"
    if scene_id in by_id:
        report.ran(scene_id, "package")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                files = package_assets(root, documents, scene_id, tmp)
                reloaded = _store(tmp).load(tmp)
                if not reloaded.ok:
                    report.fail(scene_id, "package", [f"{i.code}: {i.message}" for i in reloaded.issues])
                expected = {"golden_scene", *by_id[scene_id].manifest.dependencies}
                got = {x.manifest.asset_id for x in reloaded.loaded}
                if not expected <= got:
                    report.fail(scene_id, "package", f"package lacks {sorted(expected - got)}")
                report.summaries[scene_id]["package"] = list(files)
            except Exception as exc:  # noqa: BLE001
                report.fail(scene_id, "package", exc)
    return report


def _grid_sheet(asset_id, image_size, frame_size):
    from asteria.assets.sprite_kinds import SpriteData

    return SpriteData("grid.png", tuple(frame_size)).sprite_sheet(asset_id, image_size)


def _fire_beats(asset):
    """Advance a skill's timeline at 60 Hz and record when each beat fires."""
    pending = list(asset.beats)
    fired, t = [], 0.0
    while pending and t <= asset.duration + STEP:
        while pending and pending[0].at <= t + 1e-9:
            beat = pending.pop(0)
            fired.append([round(t, 4), beat.channel, beat.cue])
        t += STEP
    return fired


def summary_json(report):
    return json.dumps(report.summaries, indent=2, sort_keys=True)
