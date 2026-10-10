"""Headless high-fidelity editor model.
Qt/views remain thin. Progressive disclosure is view state, not canonical content.
"""

from dataclasses import dataclass, replace

from .fidelity import FrameTiming, HighFidelityClip
from .performance import FrameBudget, diagnose


@dataclass(slots=True)
class FidelityEditorViewState:
    section: str = "animation"
    selected_frame: int = 0
    selected_layer: int | None = None
    search: str = ""
    show_advanced: bool = False


class HighFidelityEditorModel:
    SECTIONS = ("animation", "layers", "events", "preview", "performance")

    def __init__(self, clip: HighFidelityClip, cues=()):
        self.clip = clip
        self.cues = list(cues)
        self.view = FidelityEditorViewState()
        self._undo = []
        self._redo = []

    def _commit(self, new):
        self._undo.append(self.clip)
        self._redo.clear()
        self.clip = new

    def set_section(self, name):
        if name not in self.SECTIONS:
            raise ValueError(name)
        self.view.section = name

    def set_frame_duration(self, index, duration_ms):
        if not 0 <= index < len(self.clip.frames):
            raise IndexError(index)
        if duration_ms <= 0:
            raise ValueError("duration")
        ts = list(self.clip.timings)
        if len(ts) == 1:
            ts = [ts[0] for _ in self.clip.frames]
        ts[index] = FrameTiming(duration_ms)
        self._commit(replace(self.clip, timings=tuple(ts)))

    def add_layer(self, layer):
        self._commit(replace(self.clip, layers=self.clip.layers + (layer,)))

    def update_layer(self, index, **changes):
        ls = list(self.clip.layers)
        ls[index] = replace(ls[index], **changes)
        self._commit(replace(self.clip, layers=tuple(ls)))

    def remove_layer(self, index):
        ls = list(self.clip.layers)
        del ls[index]
        self._commit(replace(self.clip, layers=tuple(ls)))

    def add_cue(self, cue):
        self.cues.append(cue)
        self.cues.sort(key=lambda x: x.time_ms)

    def remove_cue(self, index):
        return self.cues.pop(index)

    def filtered_layers(self):
        q = self.view.search.casefold().strip()
        return tuple(
            (i, x)
            for i, x in enumerate(self.clip.layers)
            if not q
            or q in x.asset_id.casefold()
            or q in x.blend_mode.casefold()
            or (x.material and q in x.material.casefold())
        )

    def inspector(self):
        if self.view.section == "animation":
            return {
                "frame_size": self.clip.frame_size,
                "frames": len(self.clip.frames),
                "loop": self.clip.loop,
                "pivot": self.clip.pivot,
            }
        if self.view.section == "layers":
            return {"layers": len(self.clip.layers), "selected": self.view.selected_layer}
        if self.view.section == "events":
            return {"cues": len(self.cues)}
        if self.view.section == "performance":
            return self.performance()
        return {"preview": True}

    def performance(self, budget=FrameBudget()):
        return diagnose(len(self.cues), 1 + len(self.clip.layers), budget)

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self.clip)
        self.clip = self._undo.pop()
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self.clip)
        self.clip = self._redo.pop()
        return True
