"""New gear: gaining it, the offer to wear it, taking it off, and loot on the ground."""

from __future__ import annotations

from asteria.rpg import (
    EquipmentGrowthRuntime,
    EquippedItem,
)

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
        for _ in range(int(quantity)):
            serial = sum(1 for g in bag if g.equipment.equipment_id == definition.equipment_id)
            growth_id = definition.growth_id
            instance = EquippedItem(
                definition,
                instance_id=f"{definition.equipment_id}:bag{serial + 1}",
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
        ``empty_slot`` asks when a party member has a free place it fits (and can use it),
        ``always`` also offers to swap the first piece worn there; ``never`` asks nothing."""
        rules = self.save.rpg_state.inventory.rules
        mode = getattr(rules, "equip_offer", "never") if rules is not None else "never"
        if mode == "never":
            return None
        slot_id = instance.equipment.slot
        state = self.save.rpg_state
        for actor_id in state.party_active_actor_ids:
            loadout = state.loadouts.get(actor_id)
            if loadout is None or slot_id not in loadout._slots:
                continue
            capabilities = self.resolve_actor_build(actor_id).capabilities
            if loadout.check_equip(slot_id, instance, capabilities=capabilities).allowed:
                offer = EquipOffer(instance.instance_id, actor_id, slot_id)
            elif (
                mode == "always"
                and loadout.equipped(slot_id)
                and instance.equipment.eligibility(capabilities).allowed
            ):
                worn = loadout.equipped(slot_id)[0]
                offer = EquipOffer(instance.instance_id, actor_id, slot_id, worn.instance_id)
            else:
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
        loadout.equip(offer.slot_id, item, capabilities=capabilities)
        bag.remove(item)
        self.refresh_actor_combatants(offer.actor_id)
        return offer

    def unequip_to_bag(self, actor_id, slot_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        items = list(loadout.equipped(str(slot_id)))
        if not items:
            return None
        loadout.unequip(str(slot_id), 0)
        self.save.rpg_state.equipment_bag.append(items[0])
        self.refresh_actor_combatants(actor_id)
        return items[0]

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
