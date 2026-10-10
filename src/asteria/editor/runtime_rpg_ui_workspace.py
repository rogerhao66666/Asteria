from __future__ import annotations

from dataclasses import dataclass

from .runtime_rpg_ui_authoring import RuntimeRpgUiInformationArchitecture


@dataclass(frozen=True, slots=True)
class RuntimeRpgUiWorkspaceSnapshot:
    section_id: str
    category: str
    query: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    focused_child_id: str | None
    preview_mode: str
    detail_groups: tuple[str, ...]


class RuntimeRpgUiWorkspaceModel:
    def __init__(self, controller):
        self.controller = controller
        self.architecture = RuntimeRpgUiInformationArchitecture()
        self.section_id = "character"
        self.category = "rpg_character_screen"
        self.query = ""
        self.selected_id = None
        self.focused_child_id = None
        self.preview_mode = "screen"

    def set_section(self, key):
        s = self.architecture.section(key)
        if s is None:
            raise KeyError(key)
        self.section_id = s.section_id
        self.category = s.categories[0]
        self.selected_id = None
        self.focused_child_id = None

    def set_category(self, key):
        s = self.architecture.section(self.section_id)
        if key not in s.categories:
            raise KeyError(key)
        self.category = str(key)
        self.selected_id = None
        self.focused_child_id = None

    def set_query(self, text):
        self.query = str(text or "").strip().lower()

    def visible_ids(self):
        ids = self.controller.library.ids(self.category)
        return ids if not self.query else tuple(x for x in ids if self.query in x.lower())

    def select(self, key):
        key = str(key)
        if key not in self.visible_ids():
            raise KeyError(key)
        self.selected_id = key
        self.focused_child_id = None

    def focus_child(self, key):
        if self.selected_id is None:
            raise RuntimeError("select a runtime UI profile first")
        self.focused_child_id = str(key)

    def set_preview_mode(self, mode):
        mode = str(mode)
        if mode not in {"screen", "compact", "wide", "overflow"}:
            raise ValueError("unsupported runtime UI preview mode")
        self.preview_mode = mode

    def snapshot(self):
        s = self.architecture.section(self.section_id)
        return RuntimeRpgUiWorkspaceSnapshot(
            self.section_id,
            self.category,
            self.query,
            self.visible_ids(),
            self.selected_id,
            self.focused_child_id,
            self.preview_mode,
            s.detail_groups,
        )
