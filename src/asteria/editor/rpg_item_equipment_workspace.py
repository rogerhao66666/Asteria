from __future__ import annotations
from dataclasses import dataclass

from .rpg_item_equipment_authoring import ItemEquipmentInformationArchitecture


@dataclass(frozen=True, slots=True)
class ItemEquipmentWorkspaceSnapshot:
    section_id: str
    query: str
    visible_ids: tuple[str, ...]
    selected_id: str | None
    selected_node_id: str | None
    detail_groups: tuple[str, ...]
    mode: str


class RpgItemEquipmentWorkspaceModel:
    """Presentation state for dense item/equipment authoring.

    One category is browsed at a time; only the selected definition opens its
    detail groups. Growth graphs additionally focus a single node.
    """

    def __init__(self, controller):
        self.controller = controller
        self.architecture = ItemEquipmentInformationArchitecture()
        self.section_id = "items"
        self.query = ""
        self.selected_id = None
        self.selected_node_id = None

    def set_section(self, section_id):
        if self.architecture.section(section_id) is None:
            raise KeyError(f"unknown item/equipment section: {section_id}")
        self.section_id = str(section_id)
        self.selected_id = None
        self.selected_node_id = None

    def set_query(self, text):
        self.query = str(text or "").strip().lower()

    def _mapping(self):
        db = self.controller.database
        return {
            "items": db.items,
            "equipment": db.equipment,
            "attachments": db.attachments,
            "growth": db.equipment_growth,
            "recipes": db.composition_recipes,
        }[self.section_id]

    def visible_ids(self):
        ids = tuple(sorted(self._mapping()))
        if not self.query:
            return ids
        q = self.query
        result = []
        for key in ids:
            obj = self._mapping()[key]
            text = " ".join(
                [
                    key,
                    str(getattr(obj, "display_name", "")),
                    " ".join(getattr(obj, "tags", ())),
                    str(getattr(obj, "slot", "")),
                ]
            ).lower()
            if q in text:
                result.append(key)
        return tuple(result)

    def select(self, item_id):
        key = str(item_id)
        if key not in self._mapping():
            raise KeyError(f"unknown {self.section_id} definition: {key}")
        self.selected_id = key
        self.selected_node_id = None

    def select_node(self, node_id):
        if self.section_id != "growth" or self.selected_id is None:
            raise RuntimeError("select an equipment growth definition first")
        self._mapping()[self.selected_id].require_node(node_id)
        self.selected_node_id = str(node_id)

    def snapshot(self):
        section = self.architecture.section(self.section_id)
        return ItemEquipmentWorkspaceSnapshot(
            self.section_id,
            self.query,
            self.visible_ids(),
            self.selected_id,
            self.selected_node_id,
            section.detail_groups,
            section.mode,
        )
