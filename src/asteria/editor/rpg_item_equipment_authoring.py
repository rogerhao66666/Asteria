from __future__ import annotations
from dataclasses import dataclass

from asteria.rpg import (
    AttachmentDefinition, CompositionRecipeDefinition, EquipmentDefinition,
    EquipmentGrowthDefinition, ItemDefinition,
)


class RpgItemEquipmentAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _MapCommand:
    mapping: dict
    key: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        if self.new_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.new_value

    def undo(self):
        if self.old_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.old_value


@dataclass(frozen=True, slots=True)
class ItemEquipmentSection:
    section_id: str
    label: str
    mode: str
    detail_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemEquipmentInformationArchitecture:
    sections: tuple[ItemEquipmentSection, ...] = (
        ItemEquipmentSection(
            "items", "Items", "list_detail",
            ("Identity", "Stacking", "Tags", "Use Effects"),
        ),
        ItemEquipmentSection(
            "equipment", "Equipment", "list_detail",
            (
                "Identity", "Slot & Tags", "Requirements", "Modifiers",
                "Abilities & Triggers", "Sockets", "Growth",
            ),
        ),
        ItemEquipmentSection(
            "attachments", "Attachments", "list_detail",
            ("Identity", "Compatibility Tags", "Modifiers", "Abilities & Triggers", "Growth"),
        ),
        ItemEquipmentSection(
            "growth", "Equipment Growth", "graph_detail",
            ("Graph", "Selected Node", "Ranks & Requirements", "Prerequisites", "Rewards", "Evolution"),
        ),
        ItemEquipmentSection(
            "recipes", "Crafting / Alchemy", "recipe_detail",
            ("Recipe Identity", "Selection Steps", "Outputs", "Tags"),
        ),
    )
    primary_navigation: str = "category_sidebar"
    browser_pattern: str = "search_filter_list"
    inspector_pattern: str = "contextual_detail"
    progressive_disclosure: bool = True
    show_all_details_simultaneously: bool = False

    def section(self, key):
        return next((x for x in self.sections if x.section_id == str(key)), None)


class RpgItemEquipmentAuthoringController:
    information_architecture = ItemEquipmentInformationArchitecture()

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise RpgItemEquipmentAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    def _execute(self, command):
        self.document.execute(command)
        return command

    def _coerce(self, value, cls):
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.from_data(value)
        raise TypeError(f"value must be {cls.__name__} or serialized data")

    def _ability_ids(self):
        return set(self.project.gameplay_library.abilities.ids())

    def _validate_definition(self, value):
        ability_ids = []
        if hasattr(value, "granted_abilities"):
            ability_ids.extend(value.granted_abilities)
        if isinstance(value, EquipmentGrowthDefinition):
            for node in value.nodes:
                for reward in node.rewards:
                    ability_ids.extend(reward.granted_abilities)
        missing = sorted(set(ability_ids) - self._ability_ids())
        if missing:
            raise RpgItemEquipmentAuthoringError(
                "unknown abilities: " + ", ".join(missing)
            )

        growth_id = getattr(value, "growth_id", None)
        if (
            not isinstance(value, EquipmentGrowthDefinition)
            and growth_id is not None
            and growth_id not in self.database.equipment_growth
        ):
            raise RpgItemEquipmentAuthoringError(
                f"unknown equipment growth: {growth_id}"
            )

        if isinstance(value, EquipmentGrowthDefinition):
            for node in value.nodes:
                for reward in node.rewards:
                    target = reward.evolution_equipment_id
                    if target is not None and target not in self.database.equipment:
                        raise RpgItemEquipmentAuthoringError(
                            f"unknown evolution equipment: {target}"
                        )

        if isinstance(value, CompositionRecipeDefinition):
            known = set(self.database.items)
            refs = {
                x for selection in value.selections for x in selection.item_ids
            } | {x.item_id for x in value.outputs}
            missing = sorted(refs - known)
            if missing:
                raise RpgItemEquipmentAuthoringError(
                    "unknown recipe items: " + ", ".join(missing)
                )

    def _create(self, mapping, key, value, label):
        if key in mapping:
            raise RpgItemEquipmentAuthoringError(f"duplicate definition: {key}")
        self._validate_definition(value)
        self._execute(_MapCommand(mapping, key, value, None, label))
        return value

    def _replace(self, mapping, key, value, label):
        old = mapping.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown definition: {key}")
        self._validate_definition(value)
        self._execute(_MapCommand(mapping, key, value, old, label))
        return value

    def create_item(self, value):
        value = self._coerce(value, ItemDefinition)
        return self._create(
            self.database.items, value.item_id, value, f"Add Item {value.item_id}"
        )

    def edit_item(self, item_id, value):
        value = self._coerce(value, ItemDefinition)
        key = str(item_id)
        if value.item_id != key:
            raise RpgItemEquipmentAuthoringError("item id cannot change during edit")
        return self._replace(self.database.items, key, value, f"Edit Item {key}")

    def delete_item(self, item_id):
        key = str(item_id)
        old = self.database.items.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown item: {key}")
        refs = []
        for recipe in self.database.composition_recipes.values():
            if any(key in x.item_ids for x in recipe.selections) or any(
                x.item_id == key for x in recipe.outputs
            ):
                refs.append(f"recipe:{recipe.recipe_id}")
        for enemy in self.database.enemies.values():
            if any(x.item_id == key for x in enemy.reward.loot):
                refs.append(f"enemy:{enemy.enemy_id}")
        if refs:
            raise RpgItemEquipmentAuthoringError(
                f"item {key} is referenced by " + ", ".join(sorted(refs))
            )
        self._execute(
            _MapCommand(self.database.items, key, None, old, f"Delete Item {key}")
        )

    def create_equipment(self, value):
        value = self._coerce(value, EquipmentDefinition)
        return self._create(
            self.database.equipment,
            value.equipment_id,
            value,
            f"Add Equipment {value.equipment_id}",
        )

    def edit_equipment(self, equipment_id, value):
        value = self._coerce(value, EquipmentDefinition)
        key = str(equipment_id)
        if value.equipment_id != key:
            raise RpgItemEquipmentAuthoringError(
                "equipment id cannot change during edit"
            )
        return self._replace(
            self.database.equipment, key, value, f"Edit Equipment {key}"
        )

    def delete_equipment(self, equipment_id):
        key = str(equipment_id)
        old = self.database.equipment.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown equipment: {key}")
        refs = []
        for growth in self.database.equipment_growth.values():
            for node in growth.nodes:
                if any(
                    reward.evolution_equipment_id == key
                    for reward in node.rewards
                ):
                    refs.append(f"growth:{growth.growth_id}:{node.node_id}")
        if refs:
            raise RpgItemEquipmentAuthoringError(
                f"equipment {key} is referenced by " + ", ".join(sorted(refs))
            )
        self._execute(
            _MapCommand(
                self.database.equipment, key, None, old, f"Delete Equipment {key}"
            )
        )

    def create_attachment(self, value):
        value = self._coerce(value, AttachmentDefinition)
        return self._create(
            self.database.attachments,
            value.attachment_id,
            value,
            f"Add Attachment {value.attachment_id}",
        )

    def edit_attachment(self, attachment_id, value):
        value = self._coerce(value, AttachmentDefinition)
        key = str(attachment_id)
        if value.attachment_id != key:
            raise RpgItemEquipmentAuthoringError(
                "attachment id cannot change during edit"
            )
        return self._replace(
            self.database.attachments, key, value, f"Edit Attachment {key}"
        )

    def delete_attachment(self, attachment_id):
        key = str(attachment_id)
        old = self.database.attachments.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown attachment: {key}")
        self._execute(
            _MapCommand(
                self.database.attachments, key, None, old, f"Delete Attachment {key}"
            )
        )

    def create_growth(self, value):
        value = self._coerce(value, EquipmentGrowthDefinition)
        return self._create(
            self.database.equipment_growth,
            value.growth_id,
            value,
            f"Add Equipment Growth {value.growth_id}",
        )

    def edit_growth(self, growth_id, value):
        value = self._coerce(value, EquipmentGrowthDefinition)
        key = str(growth_id)
        if value.growth_id != key:
            raise RpgItemEquipmentAuthoringError("growth id cannot change during edit")
        return self._replace(
            self.database.equipment_growth,
            key,
            value,
            f"Edit Equipment Growth {key}",
        )

    def delete_growth(self, growth_id):
        key = str(growth_id)
        old = self.database.equipment_growth.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown growth: {key}")
        refs = [
            f"equipment:{x.equipment_id}"
            for x in self.database.equipment.values()
            if x.growth_id == key
        ]
        refs += [
            f"attachment:{x.attachment_id}"
            for x in self.database.attachments.values()
            if x.growth_id == key
        ]
        if refs:
            raise RpgItemEquipmentAuthoringError(
                f"growth {key} is referenced by " + ", ".join(sorted(refs))
            )
        self._execute(
            _MapCommand(
                self.database.equipment_growth,
                key,
                None,
                old,
                f"Delete Equipment Growth {key}",
            )
        )

    def create_recipe(self, value):
        value = self._coerce(value, CompositionRecipeDefinition)
        return self._create(
            self.database.composition_recipes,
            value.recipe_id,
            value,
            f"Add Recipe {value.recipe_id}",
        )

    def edit_recipe(self, recipe_id, value):
        value = self._coerce(value, CompositionRecipeDefinition)
        key = str(recipe_id)
        if value.recipe_id != key:
            raise RpgItemEquipmentAuthoringError("recipe id cannot change during edit")
        return self._replace(
            self.database.composition_recipes, key, value, f"Edit Recipe {key}"
        )

    def delete_recipe(self, recipe_id):
        key = str(recipe_id)
        old = self.database.composition_recipes.get(key)
        if old is None:
            raise RpgItemEquipmentAuthoringError(f"unknown recipe: {key}")
        self._execute(
            _MapCommand(
                self.database.composition_recipes,
                key,
                None,
                old,
                f"Delete Recipe {key}",
            )
        )

    def validate(self):
        try:
            self.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()
