from dataclasses import dataclass
from .fidelity import HighFidelityClip, FrameTiming, VisualLayer
from .choreography import TrackEvent, ChoreographyTimeline
from .performance import BoundedDispatcher, diagnose
from .fidelity_editor import HighFidelityEditorModel


@dataclass(frozen=True, slots=True)
class ARPGWorkloadResult:
    actions: int
    events: int
    layers: int
    cancelled: int
    dispatched: int
    preserved: bool
    pressure: bool


def arpg_clip():
    f = tuple(f"realtime_{i:03d}.png" for i in range(96))
    t = tuple(FrameTiming((8.333, 10.0, 12.5, 16.667)[i % 4]) for i in range(96))
    l = tuple(
        VisualLayer(f"fx{i}", i + 1, "add" if i % 2 else "alpha", 0.8, "emissive" if i % 3 == 0 else None)
        for i in range(12)
    )
    return HighFidelityClip("reference.realtime", (640, 640), f, t, pivot=(320.25, 590.75), layers=l, loop=True)


def action_events(n=120, spacing=18.0):
    o = []
    for a in range(n):
        t = a * spacing
        for d, ch, act in (
            (0, "actor", "motion"),
            (2, "movement", "translate"),
            (4, "vfx", "trail"),
            (6, "audio", "sfx"),
            (8, "camera", "impulse"),
            (10, "project.combat_ui", "pulse"),
        ):
            o.append(TrackEvent(t + d, ch, act, {"action": a}, 12 if ch == "vfx" else 0))
    return tuple(o)


def run_arpg_reference():
    c = arpg_clip()
    m = HighFidelityEditorModel(c)
    sig = (c.frame_size, c.pivot, len(c.frames), tuple(x.duration_ms for x in c.timings))
    m.add_layer(VisualLayer("preview", 999))
    m.undo()
    pre = sig == (m.clip.frame_size, m.clip.pivot, len(m.clip.frames), tuple(x.duration_ms for x in m.clip.timings))
    e = action_events()
    cancel = 0
    for a in range(80):
        t = ChoreographyTimeline(e[a * 6 : a * 6 + 6])
        t.advance(5)
        t.cancel()
        cancel += t.cancelled
    d = BoundedDispatcher(e, 64)
    sent = 0
    while True:
        b, back = d.dispatch_through(100000)
        sent += len(b)
        if not back:
            break
    return ARPGWorkloadResult(120, len(e), len(c.layers), cancel, sent, pre, diagnose(len(e), 5000).over_budget)
