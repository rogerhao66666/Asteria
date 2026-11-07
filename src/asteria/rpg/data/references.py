"""Cross-record references of an RPG database: every id one record names that the database
does not define (the Problems panel, EDT-15)."""

from __future__ import annotations


def reference_errors(db):
    """Every dangling cross-record reference of ``db`` (an ``RpgDatabase``), one message each,
    sorted."""
    errors = []
    for actor in db.actors.values():
        for assignment in actor.class_assignments:
            if assignment.class_id not in db.classes:
                errors.append(
                    f"actor {actor.actor_id} class assignment {assignment.assignment_id} "
                    f"references unknown class {assignment.class_id}"
                )
            for track_id in assignment.progression_track_ids:
                if track_id not in db.progression_tracks:
                    errors.append(
                        f"actor {actor.actor_id} class assignment {assignment.assignment_id} "
                        f"references unknown progression track {track_id}"
                    )
    for rule in db.ability_evolutions.values():
        if (
            rule.progression_track_id is not None
            and rule.progression_track_id not in db.progression_tracks
        ):
            errors.append(
                f"ability evolution {rule.rule_id} references unknown progression track "
                f"{rule.progression_track_id}"
            )
    for graph in db.progression_graphs.values():
        for node in graph.nodes:
            for reward in node.rewards:
                for passive_id in reward.unlocked_passives:
                    if passive_id not in db.passives:
                        errors.append(
                            f"progression graph {graph.graph_id} node {node.node_id} "
                            f"references unknown passive {passive_id}"
                        )
    for equipment in db.equipment.values():
        if equipment.growth_id is not None and equipment.growth_id not in db.equipment_growth:
            errors.append(
                f"equipment {equipment.equipment_id} references unknown equipment growth "
                f"{equipment.growth_id}"
            )
    for attachment in db.attachments.values():
        if attachment.growth_id is not None and attachment.growth_id not in db.equipment_growth:
            errors.append(
                f"attachment {attachment.attachment_id} references unknown equipment "
                f"growth {attachment.growth_id}"
            )
    for growth in db.equipment_growth.values():
        for node in growth.nodes:
            for reward in node.rewards:
                if (
                    reward.evolution_equipment_id is not None
                    and reward.evolution_equipment_id not in db.equipment
                ):
                    errors.append(
                        f"equipment growth {growth.growth_id} node {node.node_id} "
                        f"references unknown evolution equipment "
                        f"{reward.evolution_equipment_id}"
                    )
                for socket_id in reward.unlocked_sockets:
                    owners = [
                        e
                        for e in db.equipment.values()
                        if e.growth_id == growth.growth_id
                        and any(s.socket_id == socket_id for s in e.sockets)
                    ]
                    if not owners:
                        errors.append(
                            f"equipment growth {growth.growth_id} node {node.node_id} "
                            f"unlocks unknown socket {socket_id}"
                        )
    for binding in db.enemy_behavior_bindings.values():
        if binding.enemy_id not in db.enemies:
            errors.append(f"enemy behavior binding references unknown enemy {binding.enemy_id}")
        if binding.ai_id not in db.enemy_ai:
            errors.append(
                f"enemy behavior binding for {binding.enemy_id} references unknown AI "
                f"{binding.ai_id}"
            )
    for party in db.party_setups.values():
        for actor_id in party.roster_actor_ids:
            if actor_id not in db.actors:
                errors.append(f"party setup {party.party_id} references unknown actor {actor_id}")
        if party.formation_id is not None:
            formation = db.formations.get(party.formation_id)
            if formation is None:
                errors.append(
                    f"party setup {party.party_id} references unknown formation "
                    f"{party.formation_id}"
                )
            else:
                known_slots = {x.slot_id for x in formation.slots}
                for placement in party.placements:
                    if placement.slot_id not in known_slots:
                        errors.append(
                            f"party setup {party.party_id} references unknown formation "
                            f"slot {placement.slot_id}"
                        )
    for recipe in db.composition_recipes.values():
        for selection in recipe.selections:
            for item_id in selection.item_ids:
                if item_id not in db.items:
                    errors.append(
                        f"composition recipe {recipe.recipe_id} references unknown input "
                        f"item {item_id}"
                    )
        for item_id in recipe.all_output_item_ids():
            if item_id not in db.items:
                errors.append(
                    f"composition recipe {recipe.recipe_id} references unknown output item "
                    f"{item_id}"
                )
        for track_id in recipe.experience:
            if track_id not in db.progression_tracks:
                errors.append(
                    f"composition recipe {recipe.recipe_id} references unknown progression "
                    f"track {track_id}"
                )
    for equipment_set in db.equipment_sets.values():
        for equipment_id in equipment_set.equipment_ids:
            if equipment_id not in db.equipment:
                errors.append(
                    f"equipment set {equipment_set.set_id} references unknown equipment "
                    f"{equipment_id}"
                )
    for tree in db.behavior_trees.values():
        for encounter_id in sorted(tree.encounter_ids()):
            if encounter_id not in db.encounters:
                errors.append(
                    f"behavior tree {tree.tree_id} references unknown encounter {encounter_id}"
                )
    for table in db.drop_tables.values():
        for item_id in sorted(table.item_ids()):
            if (
                item_id not in db.items and item_id not in db.equipment
            ):  # equipment drops are rolled loot
                errors.append(f"drop table {table.table_id} references unknown item {item_id}")
    for enemy in db.enemies.values():
        if enemy.reward.drop_table_id and enemy.reward.drop_table_id not in db.drop_tables:
            errors.append(
                f"enemy {enemy.enemy_id} reward references unknown drop table "
                f"{enemy.reward.drop_table_id}"
            )
    for interaction in db.world_interactions.values():
        where = f"world interaction {interaction.interaction_id}"
        for item_id in {*interaction.cost_items, *interaction.success_items} | (
            {interaction.required_item} if interaction.required_item else set()
        ):
            if item_id not in db.items:
                errors.append(f"{where} references unknown item {item_id}")
        for faction_id in interaction.reputation:
            if faction_id not in db.factions:
                errors.append(f"{where} references unknown faction {faction_id}")
    for species in db.pet_species.values():
        for evolution in species.evolutions:
            if evolution.to_species_id not in db.pet_species:
                errors.append(
                    f"pet species {species.species_id} evolves into unknown species "
                    f"{evolution.to_species_id}"
                )
            if evolution.item_id and evolution.item_id not in db.items:
                errors.append(
                    f"pet species {species.species_id} evolution needs unknown item "
                    f"{evolution.item_id}"
                )
    for ruleset in db.map_rule_sets.values():
        for area in ruleset.rules:
            for encounter_id, _weight in area.encounters:
                if encounter_id not in db.encounters:
                    errors.append(
                        f"map area {area.key} references unknown encounter {encounter_id}"
                    )
    for rule in db.capture_rules.values():
        if (
            rule.enemy_id not in db.enemies
            and rule.enemy_id not in db.pet_species
            and rule.enemy_id != "*"
        ):
            errors.append(f"capture rule references unknown enemy {rule.enemy_id}")
        for item_id in rule.item_bonuses:
            if item_id not in db.items:
                errors.append(f"capture rule {rule.enemy_id} references unknown item {item_id}")
        if rule.actor_id and rule.actor_id not in db.actors:
            errors.append(f"capture rule {rule.enemy_id} references unknown actor {rule.actor_id}")
        if rule.pet_species_id and rule.pet_species_id not in db.pet_species:
            errors.append(
                f"capture rule {rule.enemy_id} references unknown pet species "
                f"{rule.pet_species_id}"
            )
        if rule.pet_item_id and rule.pet_item_id not in db.items:
            errors.append(
                f"capture rule {rule.enemy_id} references unknown pet item {rule.pet_item_id}"
            )
        if rule.item_id and rule.item_id not in db.items:
            errors.append(f"capture rule {rule.enemy_id} references unknown item {rule.item_id}")
    for achievement in db.achievements.values():
        store = {
            "defeated": db.enemies,
            "reputation": db.factions,
            "quest": db.quests,
        }.get(achievement.kind)
        if store is not None and achievement.target not in store:
            errors.append(
                f"achievement {achievement.achievement_id} references unknown "
                f"{achievement.kind} target {achievement.target}"
            )
    for shop in db.shops.values():
        for entry in shop.entries:
            if entry.item_id not in db.items and entry.item_id not in db.equipment:
                errors.append(f"shop {shop.shop_id} references unknown item {entry.item_id}")
    for quest in db.quests.values():
        for quest_id in quest.prerequisites + quest.next_quest_ids:
            if quest_id not in db.quests:
                errors.append(f"quest {quest.quest_id} references unknown quest {quest_id}")
        for objective in quest.objectives:
            if objective.kind == "item" and objective.target not in db.items:
                errors.append(f"quest {quest.quest_id} references unknown item {objective.target}")
            if objective.kind == "defeat_enemy" and objective.target not in db.enemies:
                errors.append(
                    f"quest {quest.quest_id} references unknown enemy {objective.target}"
                )
        for entry in quest.reward.loot:
            if entry.item_id not in db.items:
                errors.append(
                    f"quest {quest.quest_id} reward references unknown item {entry.item_id}"
                )
        for track_id in quest.reward.experience:
            if track_id not in db.progression_tracks:
                errors.append(
                    f"quest {quest.quest_id} reward references unknown progression track "
                    f"{track_id}"
                )
    for encounter in db.encounters.values():
        for member in encounter.members:
            if member.pet_species_id and member.pet_species_id not in db.pet_species:
                errors.append(
                    f"encounter {encounter.encounter_id} references unknown pet species "
                    f"{member.pet_species_id}"
                )
            if member.enemy_id and member.enemy_id not in db.enemies:
                errors.append(
                    f"encounter {encounter.encounter_id} references unknown enemy "
                    f"{member.enemy_id}"
                )
    for enemy in db.enemies.values():
        for entry in enemy.reward.loot:
            if entry.item_id not in db.items:
                errors.append(
                    f"enemy {enemy.enemy_id} reward references unknown item {entry.item_id}"
                )
        for track_id in enemy.reward.experience:
            if track_id not in db.progression_tracks:
                errors.append(
                    f"enemy {enemy.enemy_id} reward references unknown progression track "
                    f"{track_id}"
                )
    return sorted(errors)
