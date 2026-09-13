from asteria.validation import AsteriaRpgValidationProject

def test_project_shares_one_actor_scenario_across_labs():
    project=AsteriaRpgValidationProject()
    assert project.character.scenario is project.equipment.scenario
    assert project.character.scenario is project.inventory.scenario
    assert project.shared_scenario is project.character.scenario

def test_character_progression_changes_reach_project_resolved_build():
    project=AsteriaRpgValidationProject()
    assert "double_strike" not in project.resolve_build().abilities
    project.character.allocate_node("hero_mastery","double_strike_node")
    assert "double_strike" in project.resolve_build().abilities

def test_job_switch_changes_build_used_by_project():
    project=AsteriaRpgValidationProject()
    project.character.clear_job("secondary")
    project.character.unlock_job("alchemist")
    project.character.set_job("primary","alchemist")
    build=project.resolve_build()
    assert "quick_mix" in build.abilities
    assert "power_strike" not in build.abilities

def test_equipment_changes_reach_same_resolved_build():
    project=AsteriaRpgValidationProject()
    assert "flame_slash" not in project.resolve_build().abilities
    project.equipment.equip("main_hand","ember_blade:lab")
    assert "flame_slash" in project.resolve_build().abilities

def test_attachment_and_growth_changes_reach_same_build():
    project=AsteriaRpgValidationProject()
    project.equipment.equip("main_hand","ember_blade:lab")
    project.equipment.attach("ember_blade:lab","rune","venom_rune")
    unlocked=project.equipment.add_growth_progress("ember_blade:lab","weapon_xp",10)
    assert ("tempered",1) in unlocked
    build=project.resolve_build()
    assert "venom_edge" in build.abilities
    assert "tempered_arc" in build.abilities
    assert "capability.weapon.tempered" in build.capabilities

def test_crafting_mutates_project_inventory_state():
    project=AsteriaRpgValidationProject()
    inv=project.inventory
    inv.begin()
    inv.select("red_herb"); inv.advance()
    inv.select("glass_vial"); inv.advance()
    inv.advance()
    result=inv.craft()
    assert result.recipe_id=="healing_tonic_recipe"
    assert project.shared_scenario.inventory.count("healing_tonic")==1

def test_party_operations_are_part_of_same_project_flow():
    project=AsteriaRpgValidationProject()
    project.party.swap_active_with_reserve("party_01","party_08")
    snap=project.snapshot()
    assert "party_08" in snap.party_active_ids
    assert "party_01" in snap.party_reserve_ids

def test_battle_arena_uses_current_resolved_build_not_fresh_reference_actor():
    project=AsteriaRpgValidationProject()
    project.character.allocate_node("hero_mastery","double_strike_node")
    project.equipment.equip("main_hand","ember_blade:lab")
    arena=project.build_battle_arena()
    member=arena.scenario.battle.member(arena.scenario.player_member_id)
    assert "double_strike" in member.ability_ids
    assert "flame_slash" in member.ability_ids

def test_battle_arena_executes_ability_unlocked_before_entry():
    project=AsteriaRpgValidationProject()
    project.character.allocate_node("hero_mastery","double_strike_node")
    arena=project.build_battle_arena()
    before=arena.scenario.battle.member(arena.scenario.enemy_member_id).subject.resources.current("vitality")
    arena.player_action("double_strike")
    after=arena.scenario.battle.member(arena.scenario.enemy_member_id).subject.resources.current("vitality")
    assert after < before

def test_battle_arena_captures_equipment_derived_stats():
    project=AsteriaRpgValidationProject()
    base_power=project.resolve_build().stats.get("power")
    project.equipment.equip("main_hand","ember_blade:lab")
    equipped_power=project.resolve_build().stats.get("power")
    assert equipped_power > base_power
    arena=project.build_battle_arena()
    player=arena.scenario.battle.member(arena.scenario.player_member_id)
    assert player.subject.stats.get("power")==equipped_power

def test_snapshot_summarizes_cross_system_state():
    project=AsteriaRpgValidationProject()
    project.character.award_experience(120)
    project.character.allocate_node("hero_mastery","double_strike_node")
    project.equipment.equip("main_hand","ember_blade:lab")
    project.party.swap_active_with_reserve("party_03","party_10")
    snap=project.snapshot()
    assert snap.level==2
    assert "double_strike" in snap.abilities
    assert "ember_blade:lab" in snap.equipment_instance_ids
    assert "party_10" in snap.party_active_ids

def test_build_battle_arena_does_not_mutate_outside_battle_project_state():
    project=AsteriaRpgValidationProject()
    before=project.snapshot()
    arena=project.build_battle_arena()
    arena.run_exchange("power_strike")
    after=project.snapshot()
    assert after==before
