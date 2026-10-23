"""Field menus: item use and equipment from the bag (UI-01), upgrades and sockets."""

from __future__ import annotations

from dataclasses import replace

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


class InventoryUseMixin:
    # -- field menus: item use and equipment from the bag (UI-01) ---------------------------------
    def use_item(self, actor_id, item_id):
        """Use a consumable on a party member outside battle (the canonical
        ``use_inventory_item``)."""

        from asteria.gameplay import ResourcePool, StatBlock, TagSet
        from asteria.rpg.items import use_inventory_item

        actor_id, item_id = str(actor_id), str(item_id)
        item = self.project.rpg_database.items.get(item_id)
        snapshot = self.save.rpg_state.actor_snapshots.get(actor_id)
        if item is None or snapshot is None:
            raise GameSessionError(f"cannot use {item_id} on {actor_id}")
        stats = StatBlock.from_data(snapshot.stats)
        resources = ResourcePool.from_data(snapshot.resources)
        tags = TagSet.from_data(snapshot.tags)
        result = use_inventory_item(self.save.rpg_state.inventory, item, stats, resources, tags)
        if result.used:
            self.save.rpg_state.actor_snapshots[actor_id] = replace(
                snapshot, stats=stats.to_data(), resources=resources.to_data(), tags=tags.to_data()
            )
            self.refresh_quests()
        return result

    def equip_from_inventory(self, actor_id, equipment_id, slot_id=None):
        """Move an equipment item from the bag to a slot; whatever was there goes back to the
        bag."""
        actor_id, equipment_id = str(actor_id), str(equipment_id)
        inventory = self.save.rpg_state.inventory
        if inventory.count(equipment_id) < 1:
            raise GameSessionError(f"no {equipment_id} in the bag")
        definition = self.project.rpg_database.equipment[equipment_id]
        slot_id = slot_id or definition.slot
        loadout = self.save.rpg_state.loadouts[actor_id]
        for previous in tuple(loadout.equipped(slot_id)):
            loadout.unequip(slot_id, 0)
            inventory.add(previous.equipment.equipment_id, 1)
        instance = self.equip_definition(actor_id, equipment_id, slot_id=slot_id, replace=True)
        inventory.remove(equipment_id, 1)
        return instance

    def unequip_to_inventory(self, actor_id, slot_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        items = loadout.equipped(str(slot_id))
        if not items:
            return None
        loadout.unequip(str(slot_id), 0)
        self.save.rpg_state.inventory.add(items[0].equipment.equipment_id, 1)
        return items[0].equipment.equipment_id

    def equip_definition(self, actor_id, equipment_id, *, slot_id=None, replace=True, index=0):
        """Equip ``equipment_id``; with ``replace`` the item at ``index`` of the slot goes first
        (a second hand's weapon, say, while the first stays)."""
        actor_id = str(actor_id)
        equipment_id = str(equipment_id)
        definition = self.project.rpg_database.equipment[equipment_id]
        slot_id = str(slot_id or definition.slot)
        loadout = self.save.rpg_state.loadouts[actor_id]
        held = loadout.equipped(slot_id)
        if replace and held:
            loadout.unequip(slot_id, min(int(index), len(held) - 1))
        instance = EquippedItem(
            definition,
            instance_id=f"{equipment_id}:runtime:{actor_id}:{len(loadout.equipped()) + 1}",
            growth=(
                EquipmentGrowthRuntime(
                    self.project.rpg_database.equipment_growth[definition.growth_id]
                )
                if definition.growth_id
                else None
            ),
        )
        rules = self.durability_rules
        if rules is not None:
            rules.ensure(instance)
        loadout.equip(slot_id, instance, validate_requirements=False)
        return instance

    def upgrade_equipment(self, actor_id, instance_id, node_id):
        try:
            item = self._equipped(actor_id, instance_id)  # an id, or slot:<slot id>
        except GameSessionError as error:
            raise KeyError(instance_id) from error
        growth = item.ensure_growth(self.project.rpg_database.equipment_growth)
        return growth.unlock(str(node_id))

    def attach_equipment(self, actor_id, instance_id, socket_id, attachment_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        item = next((x for x in loadout.equipped() if x.instance_id == str(instance_id)), None)
        if item is None:
            raise KeyError(instance_id)
        attachment = self.project.rpg_database.attachments[str(attachment_id)]
        if str(socket_id) in item.attachments:
            item.detach(str(socket_id))
        item.attach(str(socket_id), attachment)
        return attachment

    def _socket_item_for(self, attachment_id):
        items = self.project.rpg_database.items
        return next((x for x in items.values() if x.attachment_id == attachment_id), None)

    def rearm(self, actor_id, equipment_id, *, slot_id=None, index=0):
        """Swap a piece of equipment, in the field or mid-battle; a fighting member's abilities
        follow what it now carries."""
        instance = self.equip_definition(actor_id, equipment_id, slot_id=slot_id, index=index)
        if self.mode == "battle" and str(actor_id) in self.battle.members:
            build = self.resolve_actor_build(actor_id)
            self.battle.set_member_abilities(actor_id, build.abilities)
        return instance

    def socket_item(self, actor_id, instance_id, socket_id, item_id):
        """Spend a socketable bag item (card, gem, orb) into a socket of an equipped item. The
        attachment it replaces goes back to the bag unless its item is ``destroyed_on_removal``."""
        db = self.project.rpg_database
        definition = db.items.get(str(item_id))
        if definition is None or not definition.attachment_id:
            raise GameSessionError(f"{item_id} is not socketable")
        bag = self.save.rpg_state.inventory
        if bag.count(definition.item_id) < 1:
            raise GameSessionError(f"the bag has no {definition.item_id}")
        item = self._equipped(actor_id, instance_id)
        old = item.attachments.get(str(socket_id))
        try:
            if old is not None:
                item.detach(str(socket_id))
            item.attach(str(socket_id), db.attachments[definition.attachment_id])
        except (KeyError, ValueError) as error:
            if old is not None:
                item.attach(str(socket_id), old)
            raise GameSessionError(str(error)) from error
        bag.remove(definition.item_id, 1)
        if old is not None:
            self._return_socketed(old)
        return db.attachments[definition.attachment_id]

    def unsocket_item(self, actor_id, instance_id, socket_id):
        """Take the attachment out of a socket; its item returns to the bag unless destroyed."""
        item = self._equipped(actor_id, instance_id)
        old = item.detach(str(socket_id))
        if old is None:
            raise GameSessionError(f"socket {socket_id} is empty")
        self._return_socketed(old)
        return old

    def _return_socketed(self, attachment):
        source = self._socket_item_for(attachment.attachment_id)
        if source is not None and not source.destroyed_on_removal:
            self.save.rpg_state.inventory.add(source.item_id, 1)
