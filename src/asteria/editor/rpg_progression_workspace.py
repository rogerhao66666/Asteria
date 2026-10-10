from __future__ import annotations

from dataclasses import dataclass

from .rpg_progression_authoring import ProgressionEditorInformationArchitecture


@dataclass(frozen=True, slots=True)
class ProgressionWorkspaceSnapshot:
    section_id: str
    query: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    selected_node_id: str | None
    detail_groups: tuple[str, ...]
    show_graph: bool


class RpgProgressionWorkspaceModel:
    """Headless presentation model for a dense RPG authoring workspace.

    It deliberately exposes one category and one contextual detail target at a
    time. Filtering affects the browser only; it never mutates project data.
    """

    def __init__(self, controller):
        self.controller = controller
        self.architecture = ProgressionEditorInformationArchitecture()
        self.section_id = "abilities"
        self.query = ""
        self.selected_id = None
        self.selected_node_id = None

    def set_section(self, section_id):
        section = self.architecture.section(section_id)
        if section is None:
            raise KeyError(f"unknown progression editor section: {section_id}")
        self.section_id = section.section_id
        self.selected_id = None
        self.selected_node_id = None

    def set_query(self, text):
        self.query = str(text or "").strip().lower()

    def select(self, item_id):
        item_id = str(item_id)
        if item_id not in self._all_ids():
            raise KeyError(f"unknown item in {self.section_id}: {item_id}")
        self.selected_id = item_id
        self.selected_node_id = None

    def select_node(self, node_id):
        if self.section_id != "graphs" or self.selected_id is None:
            raise RuntimeError("select a progression graph first")
        graph = self.controller.database.progression_graphs[self.selected_id]
        graph.require_node(node_id)
        self.selected_node_id = str(node_id)

    def _all_ids(self):
        if self.section_id == "abilities":
            return tuple(self.controller.abilities.ids())
        mapping = {
            "passives": self.controller.database.passives,
            "tracks": self.controller.database.progression_tracks,
            "graphs": self.controller.database.progression_graphs,
            "evolutions": self.controller.database.ability_evolutions,
        }[self.section_id]
        return tuple(sorted(mapping))

    def visible_ids(self):
        ids = self._all_ids()
        if not self.query:
            return ids
        q = self.query
        result = []
        for item_id in ids:
            if q in item_id.lower() or q in self._search_text(item_id):
                result.append(item_id)
        return tuple(result)

    def _search_text(self, item_id):
        if self.section_id == "abilities":
            obj = self.controller.abilities.require(item_id)
            return " ".join(obj.tags).lower()
        if self.section_id == "passives":
            obj = self.controller.database.passives[item_id]
            return f"{obj.display_name} {' '.join(obj.tags)}".lower()
        if self.section_id == "tracks":
            return self.controller.database.progression_tracks[item_id].display_name.lower()
        if self.section_id == "graphs":
            obj = self.controller.database.progression_graphs[item_id]
            return f"{obj.display_name} {' '.join(obj.tags)}".lower()
        obj = self.controller.database.ability_evolutions[item_id]
        return f"{obj.source_ability_id} {obj.result_ability_id}".lower()

    def snapshot(self):
        section = self.architecture.section(self.section_id)
        return ProgressionWorkspaceSnapshot(
            self.section_id,
            self.query,
            self.visible_ids(),
            self.selected_id,
            self.selected_node_id,
            section.detail_groups,
            section.mode == "graph_detail",
        )
