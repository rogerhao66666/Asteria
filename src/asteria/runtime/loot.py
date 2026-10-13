"""Loot on the ground (ASTERIA_SPEC §35 ARPG loot): drops become entities the player walks over or
picks up.

``LootSystem.drop(scene, x, y, items=..., currencies=..., level=...)`` scatters one ``Loot``
entity per stack: plain
items, currencies, and equipment — each piece of equipment is rolled on the spot
(``rpg.loot.roll_equipment``:
rarity, item level, random affixes) and carried on the entity until picked up. A ``Looter``
(usually the player)
collects loot inside its ``pickup_radius``: automatically by its ``auto_pickup`` rule, or on
request
(``pick_up_nearest``, e.g. bound to an input). ``collect`` hands each picked stack to the game
(``GameSession`` puts
it into the save: inventory, equipment bag, currencies). ``events`` / ``listeners`` report dropped
and picked loot;
``labels()`` gives what to draw (name and rarity colour).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from math import cos, hypot, pi, sin

from asteria.core import (
    Component,
    Entity,
    Field,
    System,
    Transform,
    component_schema,
    world_position,
)
from asteria.core.ids import new_id

LOOT_KINDS = ("item", "equipment", "currency")
AUTO_PICKUP = ("none", "currency", "items", "all", "rarity_at_least")


@component_schema(
    type_name="asteria.Loot",
    version=1,
    fields=(
        Field("kind", str, "item", choices=LOOT_KINDS),
        Field("item_id", str, "", tooltip="Item, equipment or currency id."),
        Field("amount", int, 1, minimum=1),
        Field("rarity", str, ""),
        Field("label", str, "", tooltip="Name shown over it (equipment: with its affixes)."),
        Field(
            "instance", str, "", tooltip="Equipment only: the rolled instance (saved data, JSON)."
        ),
        Field("enabled", bool, True),
    ),
)
class LootComponent(Component):
    def __init__(self):
        super().__init__()
        self.kind = "item"
        self.item_id = ""
        self.amount = 1
        self.rarity = ""
        self.label = ""
        self.instance = ""
        self.enabled = True


@component_schema(
    type_name="asteria.Looter",
    version=1,
    fields=(
        Field("pickup_radius", float, 24.0, minimum=0.0),
        Field(
            "auto_pickup",
            str,
            "currency",
            choices=AUTO_PICKUP,
            tooltip="What is collected just by walking over it; the rest waits for a pick-up "
            "press.",
        ),
        Field(
            "auto_min_rarity",
            str,
            "",
            tooltip="rarity_at_least: this rarity or rarer is collected by walking over.",
        ),
        Field("enabled", bool, True),
    ),
)
class LooterComponent(Component):
    def __init__(self):
        super().__init__()
        self.pickup_radius = 24.0
        self.auto_pickup = "currency"
        self.auto_min_rarity = ""
        self.enabled = True


@dataclass(frozen=True, slots=True)
class LootEvent:
    kind: str  # dropped, picked
    loot_id: str
    loot_kind: str
    item_id: str
    amount: int
    rarity: str = ""
    label: str = ""
    looter_id: str = ""
    data: dict = field(default_factory=dict)


class LootSystem(System):
    order = 70  # after combat (65): this frame's deaths drop before anything is picked up

    def __init__(self, database=None, *, rng=None, collect=None, scatter=18.0, luck=0.0):
        self.database = database  # RpgDatabase: equipment, items, rarities, affixes
        self.rng = rng or random.Random(0)
        self.collect = collect  # callable(looter_entity, LootComponent, equipment_item_or_None)
        self.scatter = float(scatter)
        self.luck = float(luck)
        self.events: list[LootEvent] = []
        self.listeners = []

    def _emit(self, event):
        self.events.append(event)
        for listener in tuple(self.listeners):
            listener(event)

    # -- dropping --------------------------------------------------------------------------------
    def drop(self, scene, x, y, *, items=None, currencies=None, level=1, luck=0.0):
        """Scatter loot entities around ``(x, y)``; equipment is rolled now. Returns the new
        entities."""
        db = self.database
        created = []
        stacks = []
        for item_id, amount in sorted((items or {}).items()):
            if db is not None and item_id in db.equipment:
                stacks += [("equipment", item_id, 1)] * int(amount)
            else:
                stacks.append(("item", item_id, int(amount)))
        for currency, amount in sorted((currencies or {}).items()):
            if amount > 0:
                stacks.append(("currency", currency, int(amount)))
        for kind, item_id, amount in stacks:
            loot = LootComponent()
            loot.kind, loot.item_id, loot.amount = kind, item_id, amount
            loot.label = self._name(kind, item_id)
            if kind == "equipment":
                from asteria.rpg.loot import item_display_name, roll_equipment

                rolled = roll_equipment(
                    db.equipment[item_id],
                    self.rng,
                    item_level=level,
                    rarities=db.loot_rarities(),
                    affixes=db.affixes,
                    luck=self.luck + luck,
                    instance_id=f"loot:{new_id()}",
                )
                loot.rarity = rolled.rarity
                loot.label = item_display_name(rolled, db.affixes, brief=True)
                loot.instance = json.dumps(rolled.to_data(), sort_keys=True)
            elif kind == "item" and db is not None and item_id in getattr(db, "items", {}):
                loot.rarity = getattr(db.items[item_id], "rarity", "") or ""
            angle, reach = self.rng.uniform(0, 2 * pi), self.rng.uniform(0, self.scatter)
            entity = Entity(f"Loot {loot.label}")
            entity.add_component(Transform(x + cos(angle) * reach, y + sin(angle) * reach))
            entity.add_component(loot)
            scene.add_entity(entity)
            created.append(entity)
            self._emit(
                LootEvent("dropped", entity.id, kind, item_id, amount, loot.rarity, loot.label)
            )
        return created

    def _name(self, kind, item_id):
        db = self.database
        if db is not None:
            for table in (db.equipment, getattr(db, "items", {})):
                record = table.get(item_id)
                if record is not None and getattr(record, "display_name", ""):
                    return record.display_name
        return item_id

    # -- picking up ------------------------------------------------------------------------------
    def _order(self, rarity_id):
        if self.database is None:
            return 0
        rarity = self.database.loot_rarities().get(rarity_id)
        return rarity.order if rarity is not None else 0

    def _auto(self, looter, loot):
        rule = looter.auto_pickup
        if rule == "all":
            return True
        if rule == "currency":
            return loot.kind == "currency"
        if rule == "items":
            return loot.kind in ("currency", "item")
        if rule == "rarity_at_least":
            return loot.kind == "currency" or self._order(loot.rarity) >= self._order(
                looter.auto_min_rarity
            )
        return False

    def _in_reach(self, scene, entity, looter):
        x, y = world_position(entity)
        found = []
        for other, loot in scene.query(LootComponent):
            if not loot.enabled or not other.has(Transform):
                continue
            ox, oy = world_position(other)
            distance = hypot(ox - x, oy - y)
            if distance <= looter.pickup_radius:
                found.append((distance, other, loot))
        found.sort(key=lambda row: row[0])
        return found

    def pick_up(self, scene, looter_entity, loot_entity):
        loot = loot_entity.get(LootComponent)
        equipment = None
        if loot.kind == "equipment" and loot.instance and self.database is not None:
            from asteria.rpg.items import EquippedItem

            equipment = EquippedItem.from_data(
                json.loads(loot.instance),
                equipment=self.database.equipment,
                attachments=self.database.attachments,
                growth_definitions=self.database.equipment_growth,
            )
        if self.collect is not None and self.collect(looter_entity, loot, equipment) is False:
            return False  # the game refused (e.g. a full bag)
        loot.enabled = False
        scene.remove_entity(loot_entity)
        self._emit(
            LootEvent(
                "picked",
                loot_entity.id,
                loot.kind,
                loot.item_id,
                loot.amount,
                loot.rarity,
                loot.label,
                looter_entity.id,
            )
        )
        return True

    def pick_up_nearest(self, scene, looter_entity):
        """Pick up the nearest loot in reach (a pick-up press); True if something was taken."""
        looter = looter_entity.try_get(LooterComponent)
        if looter is None or not looter.enabled:
            return False
        for _, other, _ in self._in_reach(scene, looter_entity, looter):
            if self.pick_up(scene, looter_entity, other):
                return True
        return False

    def update(self, scene, dt):
        self.events = []
        for entity, looter in scene.query(LooterComponent):
            if not looter.enabled or not entity.has(Transform):
                continue
            for _, other, loot in self._in_reach(scene, entity, looter):
                if self._auto(looter, loot):
                    self.pick_up(scene, entity, other)

    def labels(self, scene):
        """``(entity, x, y, label, (r, g, b))`` for every loot on the ground (rarity colours)."""
        rarities = self.database.loot_rarities() if self.database is not None else {}
        result = []
        for entity, loot in scene.query(LootComponent):
            if loot.enabled and entity.has(Transform):
                x, y = world_position(entity)
                rarity = rarities.get(loot.rarity)
                color = rarity.rgb() if rarity is not None else (230, 230, 230)
                text = loot.label if loot.amount == 1 else f"{loot.amount} {loot.label}"
                result.append((entity, x, y, text, color))
        return result


def register_loot_components(registry):
    registry.register(LootComponent)
    registry.register(LooterComponent)
    return registry


__all__ = [
    "AUTO_PICKUP",
    "LOOT_KINDS",
    "LootComponent",
    "LootEvent",
    "LootSystem",
    "LooterComponent",
    "register_loot_components",
]
