from asteria.validation import PlayableRpgRuntimeLoop


def test_character_edits_resolve_before_encounter():
    game = PlayableRpgRuntimeLoop()
    game.award_experience(180)
    game.unlock_job("alchemist")
    game.set_job("secondary", "alchemist")
    game.allocate_skill("hero_mastery", "double_strike_node")
    game.equip("main_hand", "ember_blade:lab")
    game.equip("accessory", "echo_charm:lab")
    game.attach("ember_blade:lab", "rune", "venom_rune")
    game.add_equipment_growth("ember_blade:lab", "weapon_xp", 10)

    state = game.state()
    assert state.level == 2
    assert ("secondary", "alchemist") in state.jobs
    assert "ember_blade:lab" in state.equipped_instance_ids
    assert "echo_charm:lab" in state.equipped_instance_ids
    assert "double_strike" in state.abilities
    assert "flame_slash" in state.abilities
    assert "venom_edge" in state.abilities
    assert "tempered_arc" in state.abilities


def test_monster_interaction_requires_range_and_facing():
    game = PlayableRpgRuntimeLoop()
    game.set_player_position(-100, 0)
    game.set_player_facing("right")
    assert game.field_step({"interact": 1}) is None
    game.field_step({"interact": 0})

    game.set_player_position(0, 0)
    game.set_player_facing("left")
    assert game.field_step({"interact": 1}) is None


def test_interact_in_front_starts_encounter():
    game = PlayableRpgRuntimeLoop()
    game.set_player_position(0, 0)
    game.set_player_facing("right")
    trigger = game.field_step({"interact": 1})
    assert trigger is not None
    assert trigger.source_entity_id == game.monster.id
    assert trigger.event_program_id == "encounter:training_monster"
    assert game.state().mode == "battle"
    assert game.state().active_encounter_id == "training_monster"


def test_interaction_is_edge_triggered():
    game = PlayableRpgRuntimeLoop()
    # Holding interact only produces the first edge.
    trigger = game.field_step({"interact": 1})
    assert trigger is not None
    assert game.mode == "battle"


def test_battle_is_built_from_current_equipment_and_skill_state():
    game = PlayableRpgRuntimeLoop()
    game.allocate_skill("hero_mastery", "double_strike_node")
    game.equip("main_hand", "ember_blade:lab")
    game.attach("ember_blade:lab", "rune", "venom_rune")
    before = set(game.state().abilities)
    assert {"double_strike", "flame_slash", "venom_edge"} <= before

    game.field_step({"interact": 1})
    battle_member = game.battle.scenario.battle.member(game.battle.scenario.player_member_id)
    battle_abilities = set(battle_member.ability_ids)
    assert {"double_strike", "flame_slash", "venom_edge"} <= battle_abilities


def test_player_and_enemy_can_execute_actions_in_same_encounter():
    game = PlayableRpgRuntimeLoop()
    game.allocate_skill("hero_mastery", "double_strike_node")
    game.field_step({"interact": 1})
    pv0, ev0 = game.battle_vitality()

    game.player_action("double_strike")
    pv1, ev1 = game.battle_vitality()
    assert ev1 < ev0
    assert pv1 == pv0

    game.enemy_action()
    pv2, ev2 = game.battle_vitality()
    assert pv2 < pv1
    assert ev2 == ev1


def test_finish_encounter_returns_to_field():
    game = PlayableRpgRuntimeLoop()
    game.field_step({"interact": 1})
    assert game.mode == "battle"
    state = game.finish_encounter()
    assert state.mode == "field"
    assert state.active_encounter_id is None
    assert state.battle_player_vitality is None
    assert state.battle_enemy_vitality is None


def test_inventory_and_party_systems_are_in_same_project_loop():
    game = PlayableRpgRuntimeLoop()
    before = game.inventory.count("healing_tonic")
    result = game.craft_healing_tonic()
    assert result.recipe_id == "healing_tonic_recipe"
    assert game.inventory.count("healing_tonic") == before + 1

    outgoing, incoming, slot = game.swap_party("party_01", "party_08")
    assert (outgoing, incoming) == ("party_01", "party_08")
    assert game.project.party.formation.slot_id_for("party_08") == slot


def test_runtime_state_is_inspectable_before_and_during_battle():
    game = PlayableRpgRuntimeLoop()
    field = game.state()
    assert field.mode == "field"
    assert field.nearby_monster_id == "training_monster"
    assert field.battle_enemy_vitality is None

    game.field_step({"interact": 1})
    battle = game.state()
    assert battle.mode == "battle"
    assert battle.battle_player_vitality is not None
    assert battle.battle_enemy_vitality is not None
