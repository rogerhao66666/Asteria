"""Field status menu (UI-01, ASTERIA_SPEC §29): Status, Items, Equipment and Skills tabs.

Opened from a pause entry of its own (D87: Status, Items, Equipment and Skills are separate
entries) the menu is that one page, without the tab row (``single``). The Status page is a
table: the stats a stat graph raises with a + each (``stat_rows``, spent through
``allocate_stat``), and the detail stats (``detail_rows``). The Items page has tabs
(``categories``) and filters (``filters``) from Game Systems ▸ Menu Pages (``rpg.menu_rules``).

Every tab is projected through the canonical presentation screen runtimes
(``CharacterScreenRuntime``, ``InventoryScreenRuntime``, ``EquipmentScreenRuntime``,
``AbilityScreenRuntime``) using the project's runtime UI profiles when the
project defines them (``rpg_character_screen``, ``rpg_inventory_screen``,
``rpg_equipment_screen``, ``rpg_ability_screen``), so the authored templates
decide labels, grouping and limits. Actions go through the game session:
``use_item``, ``equip_from_inventory`` / ``unequip_to_inventory``.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.presentation.rpg_ability_screen import AbilityScreenRuntime
from asteria.presentation.rpg_character_screen import CharacterScreenRuntime
from asteria.presentation.rpg_equipment_screen import EquipmentScreenRuntime
from asteria.presentation.rpg_inventory_screen import InventoryScreenRuntime
from asteria.rpg.menu_rules import NO_STAT_GRAPH, ItemCategory, ItemFilter, menu_rules

TABS = ("status", "items", "equipment", "skills")
TAB_WORDS = {tab: f"status.tab.{tab}" for tab in TABS}  # the words drawn for the tabs
# why an item was not used (``ItemUseResult.reason`` codes): the words drawn for them
USE_REASONS = {
    "not_in_inventory": "status.reason.not_in_inventory",
    "effect_rejected": "status.reason.effect_rejected",
}
# tags every bag entry carries besides its own: what kind of record it is (D87)
ITEM_TAG, EQUIPMENT_TAG = "item", "equipment"


@dataclass(frozen=True, slots=True)
class StatRow:
    """A row of the Status page's stat table: one node of the stat graph."""

    node_id: str
    stat_id: str  # the stat (or resource's maximum) its first rank raises ("": none)
    label: str
    value: float | None  # the member's value of ``stat_id`` (None: no such stat)
    rank: int
    max_rank: int
    allowed: bool  # a + would spend a point now


PROFILE_CATEGORY = {
    "status": "rpg_character_screen",
    "items": "rpg_inventory_screen",
    "equipment": "rpg_equipment_screen",
    "skills": "rpg_ability_screen",
}


class _Abilities:
    """The ability library as a mapping, for ``_word`` (``.get``)."""

    def __init__(self, library):
        self.library = library

    def get(self, ability_id):
        try:
            return self.library.require(ability_id)
        except (KeyError, ValueError):
            return None


def _profile(game, tab):
    library = game.project.battle_presentation_library
    category = PROFILE_CATEGORY[tab]
    try:
        ids = library.ids(category)
    except (KeyError, ValueError):
        return None
    return library.require(category, ids[0]) if ids else None


class StatusMenu:
    def __init__(self, game, page=None):
        self.game = game
        self.single = page in TABS  # one page of its own: no tab row
        self.tab = page if self.single else "status"
        self.actor_index = 0
        self.row = 0
        self.message = ""
        self.rules = menu_rules(game.project.rpg_database)
        self.category = 0  # the Items page's tab
        self.filter = -1  # the Items page's filter (-1: none)
        rules = getattr(game, "rules", None)
        lead = (getattr(rules, "knockout_resource_id", ""),)  # HP first, as in the HUD
        self.screens = {
            "status": CharacterScreenRuntime(_profile(game, "status"), lead_resources=lead),
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
        if self.single:
            return
        self.tab = TABS[(TABS.index(self.tab) + step) % len(TABS)]
        self.row = 0
        self.message = ""

    def next_actor(self, step=1):
        if self.party:
            self.actor_index = (self.actor_index + step) % len(self.party)
        self.row = 0

    def move(self, step):
        rows = self.rows()
        count = len(rows)
        if self.tab == "status":  # only the stat table's rows take the cursor
            count = sum(1 for r in rows if r[0] == "ap") or count
        self.row = (self.row + step) % count if count else 0

    # -- the Status page's table (D87) -----------------------------------------------------------
    def _allocation(self):
        actor_id = self.actor_id
        state = self.game.save.rpg_state
        return state.progression_allocations.get(actor_id) if actor_id else None

    def stat_graph(self):
        """The progression graph the stat table's + spend points in: Menu Pages' ``stat_graph``,
        else the first graph tagged ``attributes`` the member has; None for no + at all."""
        allocation = self._allocation()
        if allocation is None:
            return None
        graphs = self.game.project.rpg_database.progression_graphs
        wanted = self.rules.stat_graph if self.rules is not None else ""
        if wanted == NO_STAT_GRAPH:
            return None
        if wanted:
            return graphs.get(wanted) if wanted in allocation.definitions else None
        for graph_id in sorted(graphs):
            graph = graphs[graph_id]
            if graph_id in allocation.definitions and "attributes" in {
                t.lower() for t in graph.tags
            }:
                return graph
        return None

    def _status_view(self):
        actor_id = self.actor_id
        if actor_id is None:
            return None
        game, state = self.game, self.game.save.rpg_state
        return self.screens["status"].project(
            game.resolve_actor_build(actor_id),
            loadout=state.loadouts.get(actor_id),
            actor_definition=game.project.rpg_database.actors.get(actor_id),
        )

    def stat_points(self):
        """``(points name, balance)`` of each currency the stat graph's ranks cost."""
        graph, allocation = self.stat_graph(), self._allocation()
        if graph is None:
            return []
        currencies = sorted({c for n in graph.nodes for cost in n.rank_costs for c in cost})
        return [(self.game.points_name(c), allocation.balance(c)) for c in currencies]

    def stat_rows(self):
        """One :class:`StatRow` per node of the stat graph, in the graph's order."""
        graph, allocation = self.stat_graph(), self._allocation()
        if graph is None:
            return []
        view = self._status_view()
        values = {s.stat_id: s.value for s in view.stats} if view is not None else {}
        for resource in view.resources if view is not None else ():  # a rank that adds HP
            values.setdefault(resource.resource_id, resource.maximum)
        rows = []
        for node in graph.nodes:
            reward = node.rewards[0] if node.rewards else None
            bonuses = {**reward.stat_bonuses, **reward.resource_bonuses} if reward else {}
            stat_id = next(iter(bonuses), "")
            preview = allocation.preview_allocate(graph.graph_id, node.node_id, 1)
            rows.append(
                StatRow(
                    node.node_id,
                    stat_id,
                    self.game.name_of(node, node.node_id),
                    values.get(stat_id),
                    allocation.rank(graph.graph_id, node.node_id),
                    node.max_rank,
                    not preview.reasons,
                )
            )
        return rows

    def detail_rows(self):
        """``(stat id, label, value)`` of the Status page's detail table: Menu Pages'
        ``stat_rows``, else every stat formula's stat by its order, then the member's other
        stats; the stats the stat table already shows are left out."""
        view = self._status_view()
        if view is None:
            return []
        values = {s.stat_id: s for s in view.stats}
        db = self.game.project.rpg_database
        if self.rules is not None and self.rules.stat_rows:
            order = list(self.rules.stat_rows)
        else:
            shown = {r.stat_id for r in self.stat_rows()}
            formulas = sorted(db.derived_stats.values(), key=lambda r: (r.order, r.stat_id))
            order = [r.stat_id for r in formulas]
            order += [s for s in values if s not in order and s not in shown]
        rows = []
        for stat_id in order:
            stat = values.get(stat_id)
            rule = db.derived_stats.get(stat_id)
            label = stat.label if stat is not None else stat_id
            if label == stat_id:  # the screen has no word for it: the formula's, the table's
                label = self.game.stat_name(stat_id)
                if label == stat_id and rule is not None:
                    label = self.game.name_of(rule, stat_id)
            else:
                label = self._word("stat", stat_id, label)
            rows.append((stat_id, label, stat.value if stat is not None else 0.0))
        return rows

    def allocate_stat(self, node_id):
        """Spend a point on the stat graph's ``node_id`` (the + of its row)."""
        graph, allocation = self.stat_graph(), self._allocation()
        if graph is None:
            return False
        tr = self.game.tr
        row = next((r for r in self.stat_rows() if r.node_id == node_id), None)
        name = row.label if row is not None else node_id
        reasons = allocation.preview_allocate(graph.graph_id, node_id, 1).reasons
        if reasons:
            if any(r.startswith("maximum rank") for r in reasons):
                reason = tr("status.reason.max_rank", "at its highest")
            elif any(r.startswith("insufficient") for r in reasons):
                reason = tr("status.reason.no_points", "no points left")
            else:
                reason = reasons[0]
            self.message = tr(
                "status.cannot_raise",
                "{name} can't be raised ({reason})",
                name=name,
                reason=reason,
            )
            return False
        self.game.allocate_progression(self.actor_id, graph.graph_id, node_id)
        self.message = tr("status.raised", "{name} +1", name=name)
        return True

    # -- the Items page's tabs and filters (D87) -------------------------------------------------
    def categories(self):
        """The Items page's tabs: Menu Pages' ``item_categories``, else All, and Items and
        Equipment when the game has both."""
        if self.rules is not None and self.rules.item_categories:
            return self.rules.item_categories
        tr, db = self.game.tr, self.game.project.rpg_database
        tabs = [ItemCategory("all", tr("status.items.all", "All"))]
        if db.items and db.equipment:
            tabs.append(ItemCategory(ITEM_TAG, tr("status.items.items", "Items"), (ITEM_TAG,)))
            tabs.append(
                ItemCategory(
                    EQUIPMENT_TAG, tr("status.items.equipment", "Equipment"), (EQUIPMENT_TAG,)
                )
            )
        return tuple(tabs)

    def filters(self):
        """What F narrows the tab to: Menu Pages' ``item_filters``, else "usable"."""
        if self.rules is not None and self.rules.item_filters:
            return self.rules.item_filters
        return (ItemFilter("usable", self.game.tr("status.items.usable", "Usable"), usable=True),)

    def category_name(self, category):
        return self.game.name_of(category, category.category_id)

    def filter_name(self, item_filter):
        return self.game.name_of(item_filter, item_filter.filter_id)

    def next_category(self, step=1):
        count = len(self.categories())
        self.category = (self.category + step) % count if count else 0
        self.row = 0

    def next_filter(self):
        """None, then each filter in turn, then none again."""
        count = len(self.filters())
        self.filter = self.filter + 1 if self.filter + 1 < count else -1
        self.row = 0

    def item_tags(self, item_id):
        db = self.game.project.rpg_database
        if item_id in db.items:
            return (*db.items[item_id].tags, ITEM_TAG)
        if item_id in db.equipment:
            return (*db.equipment[item_id].tags, EQUIPMENT_TAG)
        return ()

    def _keeps(self, item_id, usable):
        tags = self.item_tags(item_id)
        categories = self.categories()
        if categories and not categories[self.category % len(categories)].holds(tags):
            return False
        filters = self.filters()
        if 0 <= self.filter < len(filters):
            return filters[self.filter].keeps(tags, usable)
        return True

    # -- projection through the canonical screen runtimes -----------------------------------------
    def view(self):
        game, db, actor_id = self.game, self.game.project.rpg_database, self.actor_id
        state = game.save.rpg_state
        if self.tab == "items":
            return self.screens["items"].project(
                state.inventory, item_catalog=tuple(db.items.values())
            )
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
            return self.screens["equipment"].project(
                state.loadouts[actor_id], equipment_catalog=tuple(owned)
            )
        return self.screens["skills"].project(
            game.resolve_actor_build(actor_id),
            ability_state=game._ability_state(actor_id),
            ability_catalog=tuple(
                game.project.gameplay_library.abilities.require(a)
                for a in game.project.gameplay_library.abilities.ids()
            ),
        )

    # the record a row of each kind names (its own name stands in when the screen has only
    # the id: the equipment page's labels are ids unless a screen profile names them)
    _RECORDS = {
        "item": lambda game: game.project.rpg_database.items,
        "equipment": lambda game: game.project.rpg_database.equipment,
        "passive": lambda game: game.project.rpg_database.passives,
        "ability": lambda game: _Abilities(game.project.gameplay_library.abilities),
    }

    def _word(self, kind, record_id, label):
        """``label`` in the player's language: the locale table's ``data.<kind>.<id>.name``
        when it has one, else the record's own name when ``label`` is only its id, else
        ``label`` as the screen made it (D60, D61)."""
        lookup = self.game.data_lookup
        if lookup is not None:
            from asteria.rpg.data_text import key

            translated = lookup(key(kind, record_id))
            if translated:
                return translated
        if label == record_id and kind in self._RECORDS:
            record = self._RECORDS[kind](self.game).get(record_id)
            return self.game.name_of(record, label)
        return label

    def rows(self):
        """Selectable rows of the current tab: ``(kind, key, label, detail)``."""
        view = self.view()
        if view is None:
            return []
        tr, word = self.game.tr, self._word
        if self.tab == "items":
            equipment = self.game.project.rpg_database.equipment
            usable = "  " + tr("status.usable", "(use)")
            return [
                (
                    "item",
                    i.item_id,
                    self.game.name_of(equipment[i.item_id])
                    if i.label == i.item_id and i.item_id in equipment
                    else word("item", i.item_id, i.label),
                    f"x{i.count}" + (usable if i.usable else ""),
                )
                for i in view.items
                if i.count > 0 and self._keeps(i.item_id, i.usable)
            ]
        if self.tab == "status":
            rows = [  # the stat table's rows first: they take the cursor
                ("ap", r.node_id, r.label, "" if r.value is None else f"{r.value:g}")
                for r in self.stat_rows()
            ]
            rows += [
                (
                    "resource",
                    r.resource_id,
                    word("resource", r.resource_id, r.label),
                    f"{r.current:g} / {r.maximum:g}",
                )
                for r in view.resources
            ]
            rows += [
                ("stat", s.stat_id, word("stat", s.stat_id, s.label), f"{s.value:g}")
                for s in view.stats
            ]
            return rows
        if self.tab == "equipment":
            rows = [
                (
                    "slot",
                    slot.slot_id,
                    self.game.slot_name(slot.slot_id)
                    if slot.label == slot.slot_id
                    else word("slot", slot.slot_id, slot.label),
                    ", ".join(word("equipment", i.equipment_id, i.label) for i in slot.items)
                    or "—",
                )
                for slot in view.slots
            ]
            rows += [
                (
                    "candidate",
                    c.equipment_id,
                    word("equipment", c.equipment_id, c.label),
                    f"→ {c.slot_id}",
                )
                for c in view.candidates
            ]
            return rows
        learned, active = tr("status.learned", "learned"), tr("status.active", "active")
        rows = [
            (
                "ability",
                a.ability_id,
                word("ability", a.ability_id, a.label),
                learned if a.learned else "",
            )
            for a in view.abilities
            if a.learned or a.resolved
        ]
        rows += [
            (
                "passive",
                p.passive_id,
                word("passive", p.passive_id, p.label),
                active if p.active else "",
            )
            for p in view.passives
        ]
        return rows

    # -- actions ---------------------------------------------------------------------------------
    def row_icons(self):
        """The icon id of each row of ``rows()`` (``""`` for none): items, equipment, and a slot's
        first item."""
        from .menu_icons import record_icon_id

        project = self.game.project
        if self.tab == "equipment":
            view = self.view()
            firsts = (
                {s.slot_id: (s.items[0].equipment_id if s.items else "") for s in view.slots}
                if view
                else {}
            )
        icons = []
        for kind, key, _label, _detail in self.rows():
            if kind == "slot":
                icons.append(record_icon_id(project, "equipment", firsts.get(key, "")))
            else:
                icons.append(record_icon_id(project, kind, key))
        return icons

    def activate(self):
        """Enter on the selected row: use an item, equip a candidate, unequip a slot."""
        rows = self.rows()
        if not rows:
            return None
        kind, key, label, _ = rows[self.row % len(rows)]
        tr = self.game.tr
        if kind == "ap":
            return self.allocate_stat(key)
        if kind == "item":
            result = self.game.use_item(self.actor_id, key)
            if result.used:
                self.message = tr("status.used", "Used {name}", name=label)
            else:
                code = str(result.reason)
                reason = tr(USE_REASONS[code], code) if code in USE_REASONS else code
                self.message = tr(
                    "status.cannot_use",
                    "{name} can't be used ({reason})",
                    name=label,
                    reason=reason,
                )
            return result
        if kind == "candidate":
            self.game.equip_from_inventory(self.actor_id, key)
            self.message = tr("status.equipped", "Equipped {name}", name=label)
            return key
        if kind == "slot":
            removed = self.game.unequip_to_inventory(self.actor_id, key)
            if removed:
                self.message = tr("status.unequipped", "Unequipped {name}", name=removed)
            else:
                self.message = tr("status.nothing_to_unequip", "Nothing to unequip")
            return removed
        return None
