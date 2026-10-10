"""Demanding reference workloads. These are fixtures, never engine vocabulary."""

from dataclasses import dataclass

from .choreography import ChoreographyTimeline, TrackEvent, hold, time_scale
from .composition import SyncCue
from .fidelity import FrameTiming, HighFidelityClip, VisualLayer
from .fidelity_editor import HighFidelityEditorModel
from .performance import BoundedDispatcher


@dataclass(slots=True)
class WorkloadResult:
    frames: int
    layers: int
    cues: int
    timeline_events: int
    custom_channels: int
    editor_preserved: bool
    bounded_dispatch: bool
    presentation_only_time_control: bool


def premium_clip():
    frames = tuple(f"hero_attack_{i:03d}.png" for i in range(72))
    timings = tuple(FrameTiming(8.333 if i < 18 else 16.667 if i < 60 else 33.333) for i in range(72))
    layers = (
        VisualLayer("weapon", 10, "alpha", 1, "metal"),
        VisualLayer("rim_light", 20, "add", 0.65, "emissive"),
        VisualLayer("trail", 30, "add", 0.8, "distortion"),
        VisualLayer("particles", 40, "screen", 0.75, "soft_particle"),
        VisualLayer("foreground_sparks", 50, "add", 0.9, "emissive"),
    )
    return HighFidelityClip("reference.hero.action", (768, 768), frames, timings, pivot=(384.5, 704.25), layers=layers)


def jrpg_reference_events():
    # Names intentionally live in fixture data, not engine types.
    spec = [
        (0, "actor", "anticipation"),
        (60, "audio", "cloth"),
        (110, "camera", "push"),
        (145, "vfx", "charge"),
        (190, "actor", "dash"),
        (190, "vfx", "trail"),
        (224, "audio", "impact_1"),
        (224, "vfx", "impact_1"),
        (224, "camera", "shake"),
        (249, "audio", "impact_2"),
        (249, "vfx", "impact_2"),
        (287, "audio", "impact_3"),
        (287, "vfx", "impact_3"),
        (287, "camera", "shake"),
        (340, "ui.custom", "accent"),
        (390, "actor", "recovery"),
        (420, "project.weather", "refract"),
    ]
    return tuple(TrackEvent(t, ch, a, {}, 18 if ch == "vfx" else 0) for t, ch, a in spec)


def run_jrpg_reference():
    clip = premium_clip()
    cues = tuple(SyncCue(e.time_ms, e.track, e.action, e.payload) for e in jrpg_reference_events())
    editor = HighFidelityEditorModel(clip, cues)
    before = (
        editor.clip.frame_size,
        editor.clip.pivot,
        len(editor.clip.frames),
        tuple(x.duration_ms for x in editor.clip.timings),
    )
    editor.view.section = "layers"
    editor.view.search = "trail"
    _ = editor.filtered_layers()
    editor.add_layer(VisualLayer("temporary_preview_overlay", 999, "alpha", 0.2))
    editor.undo()
    after = (
        editor.clip.frame_size,
        editor.clip.pivot,
        len(editor.clip.frames),
        tuple(x.duration_ms for x in editor.clip.timings),
    )
    timeline = ChoreographyTimeline(jrpg_reference_events(), (hold(224, 12), time_scale(300, 60, 0.65)))
    f = timeline.advance(500)
    dispatcher = BoundedDispatcher(jrpg_reference_events(), 5)
    batches = []
    while True:
        b, back = dispatcher.dispatch_through(1000)
        batches.extend(b)
        if not back:
            break
    return WorkloadResult(
        len(clip.frames),
        len(clip.layers),
        len(cues),
        len(f.events),
        len({e.track for e in f.events}),
        before == after,
        len(batches) == len(jrpg_reference_events()),
        f.presentation_time_ms < 500,
    )
