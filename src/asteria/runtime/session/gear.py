"""New gear: gaining it, the offer to wear it, taking it off, and loot on the ground."""

from __future__ import annotations

from asteria.rpg import (
    EquipmentGrowthRuntime,
    EquippedItem,
)
from asteria.rpg.built_in_text import Words

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class GearMixin:
    # -- new gear: ask before wearing it (InventoryRules.equip_offer) ---------------------------
    def gain_equipment(self, equipment_id, quantity=1):
        """New gear goes into the equipment bag; the project's ``equip_offer`` rule may then ask
        whether a party member wears it (``equip_offers``, answered by ``answer_equip_offer``)."""
        definition = self.project.rpg_database.equipment[str(equipment_id)]
        bag = self.save.rpg_state.equipment_bag
        gained = []
        # an id no piece has, in the bag or worn (D92: a second Demon Ring while the first is
        # worn is not the first one again)
        taken = {g.instance_id for g in bag}
        for loadout in self.save.rpg_state.loadouts.values():
            taken.update(g.instance_id for g in loadout.equipped())
        for _ in range(int(quantity)):
            serial = sum(1 for g in bag if g.equipment.equipment_id == definition.equipment_id)
            serial += 1
            while f"{definition.equipment_id}:bag{serial}" in taken:
                serial += 1
            taken.add(f"{definition.equipment_id}:bag{serial}")
            growth_id = definition.growth_id
            instance = EquippedItem(
                definition,
                instance_id=f"{definition.equipment_id}:bag{serial}",
                growth=(
                    EquipmentGrowthRuntime(self.project.rpg_database.equipment_growth[growth_id])
                    if growth_id
                    else None
                ),
            )
            if self.durability_rules is not None:
                self.durability_rules.ensure(instance)
            bag.append(instance)
            gained.append(instance)
            self.offer_equipment(instance)
        return tuple(gained)

    def offer_equipment(self, instance):
        """Queue the question "wear it?" for gear now in the bag, as the inventory rules say:
        ``empty_slot`` asks when a party member has a free place it fits (and can use it): its
        own slot first, then any other slot that takes it, in the slots' order (a sub weapon
        slot, D92); ``always`` then offers to swap the first piece worn in its own slot; a free
        place in a carried slot comes last; ``never`` asks nothing."""
        rules = self.save.rpg_state.inventory.rules
        mode = getattr(rules, "equip_offer", "never") if rules is not None else "never"
        if mode == "never":
            return None
        own = instance.equipment.slot
        state = self.save.rpg_state
        for actor_id in state.party_active_actor_ids:
            loadout = state.loadouts.get(actor_id)
            if loadout is None:
                continue
            capabilities = self.resolve_actor_build(actor_id).capabilities
            slots = sorted(
                (loadout.slot(x) for x in loadout.slot_ids()),
                key=lambda x: (x.slot_id != own, x.order, x.slot_id),
            )
            free = [
                slot
                for slot in slots
                if slot.takes(instance.equipment)
                and loadout.check_equip(slot.slot_id, instance, capabilities=capabilities).allowed
            ]
            worn = [x for x in free if not x.stowed]
            offer = EquipOffer(instance.instance_id, actor_id, worn[0].slot_id) if worn else None
            if (
                offer is None
                and mode == "always"
                and own in loadout._slots
                and loadout.equipped(own)
                and instance.equipment.eligibility(capabilities).allowed
            ):
                held = loadout.equipped(own)[0]
                offer = EquipOffer(instance.instance_id, actor_id, own, held.instance_id)
            if offer is None and free:  # last, a carried slot
                offer = EquipOffer(instance.instance_id, actor_id, free[0].slot_id)
            if offer is None:
                continue
            self.equip_offers.append(offer)
            return offer
        return None

    def answer_equip_offer(self, wear):
        """Answer the first waiting offer: wear the gear (a swapped piece goes to the bag) or
        leave it in the bag. Returns the offer."""
        if not self.equip_offers:
            raise GameSessionError("no gear is waiting to be worn")
        offer = self.equip_offers.pop(0)
        if not wear:
            return offer
        bag = self.save.rpg_state.equipment_bag
        item = next((g for g in bag if g.instance_id == offer.instance_id), None)
        if item is None:
            return offer  # it left the bag meanwhile (sold, worn some other way)
        loadout = self.save.rpg_state.loadouts[offer.actor_id]
        if offer.replaces:
            held = loadout.equipped(offer.slot_id)
            index = next(i for i, g in enumerate(held) if g.instance_id == offer.replaces)
            bag.append(held[index])
            loadout.unequip(offer.slot_id, index)
        capabilities = self.resolve_actor_build(offer.actor_id).capabilities
        cleared = self._clear_conflicts(loadout, offer.slot_id, item)  # a sub weapon (D92)
        try:
            loadout.equip(offer.slot_id, item, capabilities=capabilities)
        except Exception:
            for other, piece in cleared:
                loadout.equip(other, piece, validate_requirements=False)
            raise
        bag.remove(item)
        bag.extend(piece for _other, piece in cleared)
        self.refresh_actor_combatants(offer.actor_id)
        return offer

    def unequip_to_bag(self, actor_id, slot_id, index=0):
        """Take the ``index``-th piece worn in ``slot_id`` off, into the equipment bag."""
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        items = list(loadout.equipped(str(slot_id)))
        if not 0 <= int(index) < len(items):
            return None
        loadout.unequip(str(slot_id), int(index))
        self.save.rpg_state.equipment_bag.append(items[int(index)])
        self.refresh_actor_combatants(actor_id)
        return items[int(index)]

    def wear_from_bag(self, actor_id, instance_id, slot_id, index=None):
        """Wear the bag piece ``instance_id`` in ``slot_id`` (the equipment screen, U3): instead
        of the ``index``-th piece worn there (which goes back to the bag), else in a free place,
        else instead of the first piece. Its requirements are checked; nothing changes when they
        are not met. Pieces in its way (a two-handed weapon and the sub weapon, D92) go back to
        the bag too, or the rules' ``slot_conflict`` "refuse" keeps them and refuses. Returns the
        piece taken off, or None."""
        actor_id, slot_id = str(actor_id), str(slot_id)
        bag = self.save.rpg_state.equipment_bag
        item = next((g for g in bag if g.instance_id == instance_id), None)
        if item is None:
            raise GameSessionError(f"{instance_id} is not in the equipment bag")
        loadout = self.save.rpg_state.loadouts[actor_id]
        capabilities = self.resolve_actor_build(actor_id).capabilities
        held = list(loadout.equipped(slot_id))
        slot = loadout._slots.get(slot_id)
        full = slot is not None and slot.capacity is not None and len(held) >= slot.capacity
        if index is None or not 0 <= int(index) < len(held):
            index = 0 if full and held else None
        removed = None
        if index is not None:
            removed = held[int(index)]
            loadout.unequip(slot_id, int(index))
        cleared = []
        try:
            cleared = self._clear_conflicts(loadout, slot_id, item)
            loadout.equip(slot_id, item, capabilities=capabilities)
        except Exception:
            for other, piece in cleared:
                loadout.equip(other, piece, validate_requirements=False)
            if removed is not None:
                loadout.equip(slot_id, removed, validate_requirements=False)
            raise
        bag.remove(item)
        if removed is not None:
            bag.append(removed)
        bag.extend(piece for _other, piece in cleared)
        self.refresh_actor_combatants(actor_id)
        return removed

    # -- carried gear (D92): stowed slots hold pieces that give nothing until swapped in -------
    def _slot_conflict_rule(self):
        rules = self.save.rpg_state.inventory.rules
        return getattr(rules, "slot_conflict", "take_off") if rules is not None else "take_off"

    def _clear_conflicts(self, loadout, slot_id, item):
        """Take off the worn pieces in the way of ``item`` in ``slot_id``; returns them as
        ``[(slot_id, piece)]``, or refuses (``slot_conflict`` "refuse")."""
        conflicts = loadout.conflicts(slot_id, item)
        if not conflicts:
            return []
        if self._slot_conflict_rule() == "refuse":
            other, piece = conflicts[0]
            raise GameSessionError(
                Words(
                    "gear.slot_taken",
                    "Take {name} off the {slot} first",
                    name=self.name_of(piece.equipment),
                    slot=self.slot_name(other),
                )
            )
        cleared = []
        for other, piece in conflicts:
            held = loadout.equipped(other)
            index = next(i for i, g in enumerate(held) if g is piece)
            loadout.unequip(other, index)
            cleared.append((other, piece))
        return cleared

    def swap_options(self, actor_id):
        """``[(piece, slot_id)]``: each carried piece of ``actor_id`` with each worn slot it can
        go into now (the battle's Swap command, D92)."""
        loadout = self.save.rpg_state.loadouts.get(str(actor_id))
        if loadout is None or not loadout.carried():
            return []
        capabilities = self.resolve_actor_build(actor_id).capabilities
        slots = sorted(
            (loadout.slot(x) for x in loadout.slot_ids()), key=lambda x: (x.order, x.slot_id)
        )
        worn = [x for x in slots if not x.stowed and x.usable_with(capabilities)]
        options = []
        for carrier in (x for x in slots if x.stowed and x.usable_with(capabilities)):
            for piece in loadout.equipped(carrier.slot_id):
                if not piece.equipment.eligibility(capabilities).allowed:
                    continue
                options.extend((piece, x.slot_id) for x in worn if x.takes(piece.equipment))
        return options

    def swap_carried(self, actor_id, instance_id, slot_id):
        """Swap the carried piece ``instance_id`` into the worn slot ``slot_id``: the piece worn
        there (and any in the new piece's way) goes into the carried slot, or the bag when it is
        full. In battle the fighter's stats, skills and tags change at once. Returns True when
        it uses the turn (``InventoryRules.battle_swap``)."""
        actor_id, slot_id = str(actor_id), str(slot_id)
        loadout = self.save.rpg_state.loadouts[actor_id]
        found = next(
            (
                (key, index, piece)
                for key in loadout.slot_ids()
                if loadout.slot(key).stowed
                for index, piece in enumerate(loadout.equipped(key))
                if piece.instance_id == instance_id
            ),
            None,
        )
        if found is None:
            raise GameSessionError(f"{instance_id} is not carried")
        carrier, index, piece = found
        target = loadout.slot(slot_id)
        if target is None or target.stowed:
            raise GameSessionError(f"{slot_id} is not a worn slot")
        in_battle = self.mode == "battle" and self.battle is not None
        in_battle = in_battle and actor_id in self.battle.members
        before = self.resolve_actor_build(actor_id) if in_battle else None
        capabilities = self.resolve_actor_build(actor_id).capabilities
        held = list(loadout.equipped(slot_id))
        full = target.capacity is not None and len(held) >= target.capacity
        loadout.unequip(carrier, index)
        out = []
        if full and held:
            loadout.unequip(slot_id, 0)
            out.append((slot_id, held[0]))
        try:
            out += self._clear_conflicts(loadout, slot_id, piece)
            loadout.equip(slot_id, piece, capabilities=capabilities)
        except Exception:
            for other, gone in out:
                loadout.equip(other, gone, validate_requirements=False)
            loadout.equip(carrier, piece, validate_requirements=False)
            raise
        bag = self.save.rpg_state.equipment_bag
        room = loadout.slot(carrier).capacity
        for _other, gone in out:
            if room is None or len(loadout.equipped(carrier)) < room:
                loadout.equip(carrier, gone, validate_requirements=False)
            else:
                bag.append(gone)
        self.refresh_actor_combatants(actor_id)
        if in_battle:
            self._apply_build_change(actor_id, before)
            self._log("swapped", member_id=actor_id, data={"slot_id": slot_id, "piece": piece})
            self.notify(
                self.tr(
                    "battle.swapped",
                    "{name} takes up {item}",
                    name=self.name_of(self.project.rpg_database.actors[actor_id]),
                    item=piece.nickname or self.name_of(piece.equipment),
                )
            )
        rules = self.save.rpg_state.inventory.rules
        return getattr(rules, "battle_swap", "turn") != "free"

    def reset_progression(self, actor_id, graph_id=None, *, cost=None):
        """Refund every allocated skill-tree point of ``actor_id`` (one graph or all) for ``cost``
        currencies."""
        actor_id = str(actor_id)
        allocation = self.save.rpg_state.progression_allocations.get(actor_id)
        if allocation is None:
            raise GameSessionError(f"{actor_id} has no skill tree")
        currencies = self.save.rpg_state.currencies
        for currency, amount in dict(cost or {}).items():
            if currencies.get(currency, 0) < amount:
                raise GameSessionError(f"not enough {currency}")
        graphs = [str(graph_id)] if graph_id is not None else list(allocation.allocations)
        refunded = {}
        changed = True
        while changed:  # refund leaves first: a node whose dependants are gone can go next
            changed = False
            for gid in graphs:
                for node_id, rank in list(allocation.allocations[gid].items()):
                    try:
                        refund = allocation.refund(gid, node_id, rank)
                    except ValueError:
                        continue
                    for currency, amount in refund.items():
                        refunded[currency] = refunded.get(currency, 0.0) + amount
                    changed = True
        for currency, amount in dict(cost or {}).items():
            currencies[currency] = currencies.get(currency, 0) - amount
        self.refresh_actor_combatants(actor_id)
        return refunded

    @property
    def loot(self):
        """Loot on the ground (ASTERIA_SPEC §35): ``drop``, ``pick_up_nearest``, ``labels``."""
        return self._field_systems()["loot"]

    def _collect_loot(self, looter, loot, equipment):
        """A picked-up stack goes into the save: currencies, the inventory, or the equipment
        bag."""
        state = self.save.rpg_state
        if loot.kind == "currency":
            state.currencies[loot.item_id] = state.currencies.get(loot.item_id, 0) + loot.amount
            return True
        if loot.kind == "equipment":
            if equipment is None:
                return False
            state.equipment_bag.append(equipment)
            self.offer_equipment(equipment)
            return True
        room = state.inventory.room_for(loot.item_id)
        if room is not None and room < loot.amount:
            return False  # the bag is full: it stays on the ground
        state.inventory.add(loot.item_id, loot.amount)
        return True
