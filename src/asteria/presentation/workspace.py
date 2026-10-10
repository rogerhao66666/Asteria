"""Presentation Workspace integration contract + headless view-model.
Qt/PySide6 is a view/controller only; canonical Sequence remains authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import Command, Kind, Node
from .editor_model import PresentationEditorModel


@dataclass(frozen=True, slots=True)
class PaletteItem:
    key: str
    label: str
    kind: Kind
    description: str


@dataclass(frozen=True, slots=True)
class InspectorField:
    name: str
    value: object
    editable: bool = True


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    mode: str = "hierarchy"
    query: str = ""
    preview_playing: bool = False
    preview_time_ms: float = 0.0


class PresentationWorkspaceModel:
    def __init__(self, editor: PresentationEditorModel):
        self.editor = editor
        self.state = WorkspaceState()

    def set_mode(self, mode):
        if mode not in ("hierarchy", "timeline"):
            raise ValueError(mode)
        self.state = WorkspaceState(mode, self.state.query, self.state.preview_playing, self.state.preview_time_ms)

    def search(self, q):
        self.state = WorkspaceState(self.state.mode, q, self.state.preview_playing, self.state.preview_time_ms)
        return self.editor.tree_rows(q)

    def palette(self, q=""):
        items = (
            PaletteItem("command", "Command", Kind.COMMAND, "Dispatch any project-defined presentation command."),
            PaletteItem("sequence", "Sequence", Kind.SEQUENCE, "Run child nodes in order."),
            PaletteItem("parallel", "Parallel", Kind.PARALLEL, "Run child nodes together."),
            PaletteItem("wait", "Wait", Kind.WAIT, "Wait for presentation time."),
            PaletteItem("wait_event", "Wait Event", Kind.WAIT_EVENT, "Resume on an arbitrary event."),
            PaletteItem("branch", "Branch", Kind.BRANCH, "Choose a path using a condition."),
            PaletteItem("loop", "Loop", Kind.LOOP, "Repeat child presentation nodes."),
            PaletteItem("emit_event", "Emit Event", Kind.EMIT_EVENT, "Emit an arbitrary project event."),
            PaletteItem("set_variable", "Set Variable", Kind.SET_VARIABLE, "Set presentation context data."),
            PaletteItem("nested", "Nested Sequence", Kind.NESTED, "Reuse another presentation sequence."),
        )
        q = q.lower().strip()
        return tuple(x for x in items if not q or q in (x.key + " " + x.label + " " + x.description).lower())

    def add_from_palette(self, parent_id, key, node_id, branch="children"):
        kind = next((x.kind for x in self.palette() if x.key == key), None)
        if kind is None:
            raise KeyError(key)
        kw = {}
        if kind == Kind.COMMAND:
            kw["command"] = Command("project.custom", "action")
        elif kind == Kind.WAIT_EVENT:
            kw["event_name"] = "project.event"
        elif kind == Kind.EMIT_EVENT:
            kw["event_name"] = "project.event"
        elif kind == Kind.LOOP:
            kw["loop_count"] = 1
        elif kind == Kind.NESTED:
            kw["sequence_ref"] = "sequence.id"
        # Branch condition intentionally requires explicit Inspector authoring; do not invent semantics.
        from .canonical import Expression

        if kind == Kind.BRANCH:
            kw["condition"] = Expression("value", (True,))
        self.editor.insert(parent_id, Node(node_id, kind, **kw), branch=branch)

    def inspector(self):
        n = self.editor.selected
        fields = [InspectorField("id", n.id, False), InspectorField("kind", n.kind.value, False)]
        if n.command:
            fields += [
                InspectorField("channel", n.command.channel),
                InspectorField("action", n.command.action),
                InspectorField("args", n.command.args),
                InspectorField("blocking", n.command.blocking),
            ]
        if n.kind == Kind.WAIT:
            fields.append(InspectorField("duration_ms", n.duration_ms))
        if n.kind in (Kind.WAIT_EVENT, Kind.EMIT_EVENT):
            fields.append(InspectorField("event_name", n.event_name))
        if n.kind == Kind.LOOP:
            fields.append(InspectorField("loop_count", n.loop_count))
        if n.kind == Kind.NESTED:
            fields.append(InspectorField("sequence_ref", n.sequence_ref))
        return tuple(fields)

    def problems(self):
        return self.editor.issues()

    def play(self):
        self.state = WorkspaceState(self.state.mode, self.state.query, True, self.state.preview_time_ms)

    def pause(self):
        self.state = WorkspaceState(self.state.mode, self.state.query, False, self.state.preview_time_ms)

    def scrub(self, time_ms):
        if time_ms < 0:
            raise ValueError("negative preview time")
        self.state = WorkspaceState(self.state.mode, self.state.query, self.state.preview_playing, float(time_ms))
