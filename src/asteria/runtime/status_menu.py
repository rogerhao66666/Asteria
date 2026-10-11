"""Field status menu (UI-01, ASTERIA_SPEC §29): Status, Items, Equipment and Skills tabs.

Every tab is projected through the canonical presentation screen runtimes
(``CharacterScreenRuntime``, ``InventoryScreenRuntime``, ``EquipmentScreenRuntime``,
``AbilityScreenRuntime``) using the project's runtime UI profiles when the
project defines them (``rpg_character_screen``, ``rpg_inventory_screen``,
``rpg_equipment_screen``, ``rpg_ability_screen``), so the authored templates
decide labels, grouping and limits. Actions go through the game session:
``use_item``, ``equip_from_inventory`` / ``unequip_to_inventory``.
"""

from __future__ import annotations

from asteria.presentation.rpg_ability_screen import AbilityScreenRuntime
from asteria.presentation.rpg_character_screen import CharacterScreenRuntime
from asteria.presentation.rpg_equipment_screen import EquipmentScreenRuntime
from asteria.presentation.rpg_inventory_screen import InventoryScreenRuntime

TABS = ("status", "items", "equipment", "skills")
PROFILE_CATEGORY = {
    "status": "rpg_character_screen",
    "items": "rpg_inventory_screen",
    "equipment": "rpg_equipment_screen",
    "skills": "rpg_ability_screen",
}


def _profile(game, tab):
    library = game.project.battle_presentation_library
    category = PROFILE_CATEGORY[tab]
    try:
        ids = library.ids(category)
    except (KeyError, ValueError):
        return None
    return library.require(category, ids[0]) if ids else None


class StatusMenu:
    def __init__(self, game):
        self.game = game
        self.tab = "status"
        self.actor_index = 0
        self.row = 0
        self.message = ""
        self.screens = {
            "status": CharacterScreenRuntime(_profile(game, "status")),
            "items": InventoryScreenRuntime(_profile(game, "items")),
            "equipment": EquipmentScreenRuntime(_profile(game, "equipment")),
            "skills": AbilityScreenRuntime(_profile(game, "skills")),
        }

    # -- state ---------------------------------------------------------------------------------
    @property
    def party(self):
        return tuple(self.game.save.rpg_state.party_active_actor_ids)

    @property
    def actor_id(self):
        party = self.party
        return party[self.actor_index % len(party)] if party else None

    def next_tab(self, step=1):
        self.tab = TABS[(TABS.index(self.tab) + step) % len(TABS)]
        self.row = 0
        self.message = ""

    def next_actor(self, step=1):
        if self.party:
            self.actor_index = (self.actor_index + step) % len(self.party)
        self.row = 0

    def move(self, step):
        count = len(self.rows())
        self.row = (self.row + step) % count if count else 0

    # -- projection through the canonical screen runtimes -------------------------------------------
    def view(self):
        game, db, actor_id = self.game, self.game.project.rpg_database, self.actor_id
        state = game.save.rpg_state
        if self.tab == "items":
            return self.screens["items"].project(state.inventory, item_catalog=tuple(db.items.values()))
        if actor_id is None:
            return None
        if self.tab == "status":
            return self.screens["status"].project(
                game.resolve_actor_build(actor_id),
                loadout=state.loadouts.get(actor_id),
                actor_definition=db.actors.get(actor_id),
            )
        if self.tab == "equipment":
            owned = [db.equipment[k] for k in sorted(db.equipment) if state.inventory.count(k) > 0]
            return self.screens["equipment"].project(state.loadouts[actor_id], equipment_catalog=tuple(owned))
        return self.screens["skills"].project(
            game.resolve_actor_build(actor_id),
            ability_state=game._ability_state(actor_id),
            ability_catalog=tuple(
                game.project.gameplay_library.abilities.require(a)
                for a in game.project.gameplay_library.abilities.ids()
            ),
        )

    def rows(self):
        """Selectable rows of the current tab: ``(kind, key, label, detail)``."""
        view = self.view()
        if view is None:
            return []
        if self.tab == "items":
            return [
                ("item", i.item_id, i.label, f"x{i.count}" + ("  (use)" if i.usable else ""))
                for i in view.items
                if i.count > 0
            ]
        if self.tab == "status":
            rows = [("resource", r.resource_id, r.label, f"{r.current:g} / {r.maximum:g}") for r in view.resources]
            rows += [("stat", s.stat_id, s.label, f"{s.value:g}") for s in view.stats]
            return rows
        if self.tab == "equipment":
            rows = [
                ("slot", slot.slot_id, slot.label, ", ".join(i.label for i in slot.items) or "—") for slot in view.slots
            ]
            rows += [("candidate", c.equipment_id, c.label, f"→ {c.slot_id}") for c in view.candidates]
            return rows
        rows = [
            ("ability", a.ability_id, a.label, "learned" if a.learned else "")
            for a in view.abilities
            if a.learned or a.resolved
        ]
        rows += [("passive", p.passive_id, p.label, "active" if p.active else "") for p in view.passives]
        return rows

    # -- actions ---------------------------------------------------------------------------------
    def activate(self):
        """Enter on the selected row: use an item, equip a candidate, unequip a slot."""
        rows = self.rows()
        if not rows:
            return None
        kind, key, label, _ = rows[self.row % len(rows)]
        if kind == "item":
            result = self.game.use_item(self.actor_id, key)
            self.message = f"Used {label}" if result.used else f"{label} can't be used ({result.reason})"
            return result
        if kind == "candidate":
            self.game.equip_from_inventory(self.actor_id, key)
            self.message = f"Equipped {label}"
            return key
        if kind == "slot":
            removed = self.game.unequip_to_inventory(self.actor_id, key)
            self.message = f"Unequipped {removed}" if removed else "Nothing to unequip"
            return removed
        return None
