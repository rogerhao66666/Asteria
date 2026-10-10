from __future__ import annotations

from dataclasses import dataclass

from .battle_presentation_authoring import BattlePresentationInformationArchitecture


@dataclass(frozen=True, slots=True)
class BattlePresentationWorkspaceSnapshot:
    section_id: str
    category: str
    query: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    focused_child_id: str | None
    preview_mode: str
    detail_groups: tuple[str, ...]


class BattlePresentationWorkspaceModel:
    def __init__(self, controller):
        self.controller = controller
        self.architecture = BattlePresentationInformationArchitecture()
        self.section_id = "visuals"
        self.category = "combatant_visuals"
        self.query = ""
        self.selected_id = None
        self.focused_child_id = None
        self.preview_mode = "battlefield"

    def set_section(self, section_id):
        s = self.architecture.section(section_id)
        if s is None:
            raise KeyError(section_id)
        self.section_id = s.section_id
        self.category = s.categories[0]
        self.selected_id = None
        self.focused_child_id = None

    def set_category(self, category):
        s = self.architecture.section(self.section_id)
        if category not in s.categories:
            raise KeyError(category)
        self.category = str(category)
        self.selected_id = None
        self.focused_child_id = None

    def set_query(self, text):
        self.query = str(text or "").strip().lower()

    def set_preview_mode(self, mode):
        mode = str(mode)
        if mode not in {"battlefield", "hud", "timeline", "result"}:
            raise ValueError("unsupported preview mode")
        self.preview_mode = mode

    def visible_ids(self):
        ids = self.controller.library.ids(self.category)
        if not self.query:
            return ids
        q = self.query
        return tuple(x for x in ids if q in x.lower())

    def select(self, profile_id):
        profile_id = str(profile_id)
        if profile_id not in self.visible_ids():
            raise KeyError(profile_id)
        self.selected_id = profile_id
        self.focused_child_id = None

    def focus_child(self, child_id):
        if self.selected_id is None:
            raise RuntimeError("select a presentation profile first")
        self.focused_child_id = str(child_id)

    def snapshot(self):
        s = self.architecture.section(self.section_id)
        return BattlePresentationWorkspaceSnapshot(
            self.section_id,
            self.category,
            self.query,
            self.visible_ids(),
            self.selected_id,
            self.focused_child_id,
            self.preview_mode,
            s.detail_groups,
        )
