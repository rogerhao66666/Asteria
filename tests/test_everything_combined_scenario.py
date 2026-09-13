from asteria.validation import EverythingCombinedScenario

def test_everything_combined_scenario_runs_end_to_end():
    report=EverythingCombinedScenario().run()
    assert report.steps==(
        "build.progression",
        "build.equipment",
        "inventory.composition",
        "party.formation",
        "battle.current_build",
        "battle.status.interaction.sequence",
        "battle.transform",
        "battle.summon.add",
        "postbattle.reward",
    )

def test_combined_build_contains_cross_source_abilities():
    report=EverythingCombinedScenario().run()
    for ability_id in ("double_strike","flame_slash","venom_edge","tempered_arc"):
        assert ability_id in report.pre_battle_abilities

def test_composition_product_survives_into_postbattle_project_state():
    scenario=EverythingCombinedScenario()
    report=scenario.run()
    assert report.crafted_item_count==1
    assert scenario.project.shared_scenario.inventory.count("healing_tonic")==1

def test_party_swap_survives_full_scenario():
    report=EverythingCombinedScenario().run()
    assert "party_08" in report.party_active_ids
    assert "party_01" not in report.party_active_ids

def test_current_build_ability_executes_in_battle():
    report=EverythingCombinedScenario().run()
    assert report.battle_damage_applied

def test_status_interaction_and_multihit_are_exercised():
    report=EverythingCombinedScenario().run()
    assert report.status_exercised

def test_transform_is_exercised_through_existing_generic_runtime():
    report=EverythingCombinedScenario().run()
    assert report.transform_exercised

def test_player_summon_and_boss_add_are_exercised():
    report=EverythingCombinedScenario().run()
    assert report.summon_exercised

def test_reward_advances_persistent_character_progression():
    report=EverythingCombinedScenario().run()
    assert report.reward_level_before==1
    assert report.reward_level_after==2

def test_reward_updates_inventory_and_arbitrary_currency():
    scenario=EverythingCombinedScenario()
    before=scenario.project.shared_scenario.inventory.count("spark_dust")
    report=scenario.run()
    assert report.reward_item_count==before+1
    assert report.reward_currency==125

def test_battle_specialized_harnesses_do_not_replace_project_persistent_build():
    scenario=EverythingCombinedScenario()
    report=scenario.run()
    build=scenario.project.resolve_build()
    assert tuple(build.abilities)==report.pre_battle_abilities
    assert "tempered_arc" in build.abilities

def test_combined_run_is_deterministic_from_clean_project():
    a=EverythingCombinedScenario().run()
    b=EverythingCombinedScenario().run()
    assert a==b
