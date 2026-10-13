from asteria.validation import PlayableRpgValidationHarness, build_reference_actor_scenario


def test_reference_actor_resolves_multiclass_progression_equipment_attachment_growth_and_passive():
    scenario = build_reference_actor_scenario()
    report = PlayableRpgValidationHarness(scenario).report()
    assert report.class_assignment_ids == ("job:vanguard", "job:alchemist")
    expected = {
        "basic_attack",
        "power_strike",
        "guard_break",
        "quick_mix",
        "field_mix",
        "double_strike",
        "flame_slash",
        "venom_edge",
        "tempered_arc",
        "echo_step",
        "reactive_tonic",
    }
    assert expected.issubset(set(report.abilities))
    assert "class" in report.source_kinds("power_strike")
    assert "allocation" in report.source_kinds("double_strike")
    assert "equipment" in report.source_kinds("flame_slash")
    assert "attachment" in report.source_kinds("venom_edge")
    assert "equipment_growth" in report.source_kinds("tempered_arc")
    assert "passive" in report.source_kinds("reactive_tonic")


def test_reference_build_has_arbitrary_resources_and_capabilities():
    report = PlayableRpgValidationHarness().report()
    assert {"vitality", "technique", "momentum", "reagent_charge"}.issubset(set(report.resources))
    assert {"capability.combo", "capability.weapon.tempered"}.issubset(set(report.capabilities))


def test_action_menu_projection_uses_resolved_build_not_special_case_commands():
    report = PlayableRpgValidationHarness().report()
    ability_entries = [x for x in report.action_entries if x.kind == "ability"]
    assert tuple(x.action_id for x in ability_entries) == report.abilities
    assert any(
        x.action_id == "field_concoction" and x.kind == "workflow" for x in report.action_entries
    )


def test_alchemy_workflow_is_generic_multistep_and_inventory_backed():
    harness = PlayableRpgValidationHarness()
    definition = harness.scenario.alchemy_workflow
    assert [x.step_id for x in definition.steps] == ["base", "reagent", "catalyst"]
    options = {x.option_id: x for x in harness.alchemy_options()}
    assert options["red_herb"].enabled and options["red_herb"].detail == "x4"
    assert options["spark_dust"].enabled and options["spark_dust"].detail == "x2"


def test_report_generation_is_read_only():
    scenario = build_reference_actor_scenario()
    before_actor = scenario.actor.snapshot().to_data()
    before_inventory = scenario.inventory.to_data()
    before_alloc = scenario.allocations.to_data()
    before_loadout = scenario.loadout.to_data()
    PlayableRpgValidationHarness(scenario).report()
    assert scenario.actor.snapshot().to_data() == before_actor
    assert scenario.inventory.to_data() == before_inventory
    assert scenario.allocations.to_data() == before_alloc
    assert scenario.loadout.to_data() == before_loadout


def test_reference_names_are_content_not_engine_taxonomy():
    report = PlayableRpgValidationHarness().report()
    assert "bp" not in report.resources
    assert "mp" not in report.resources
    assert "hp" not in report.resources
    assert "vitality" in report.resources
