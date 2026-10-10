from copy import deepcopy

from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.gameplay.states import StateDefinition, StateRegistry, StateRuntime
from asteria.presentation import (
    BattleHudProfile,
    BattleHudResourceStyle,
    BattleHudRuntime,
    BattleHudStatusStyle,
)
from asteria.rpg import BattleResourceDefinition, BattleResourceRuntime, PartyMember


def _subject():
    resources = ResourcePool()
    resources.define("hp", 100, current=75)
    resources.define("mp", 40, current=13)
    stats = StatBlock()
    tags = TagSet()
    registry = StateRegistry([StateDefinition("poison", duration=3)])
    states = StateRuntime(registry, stats, resources, tags)
    return GameplaySubject(stats, resources, tags, states)


def _runtime():
    subject = _subject()
    hero = PartyMember("hero", "player", subject, initiative=10)
    resources = BattleResourceRuntime(
        [
            BattleResourceDefinition("hp"),
            BattleResourceDefinition("mp"),
            BattleResourceDefinition("limit", minimum=0, maximum=100, start_mode="fixed", start_value=35),
        ],
        [hero],
    )
    return hero, resources


def _profile():
    return BattleHudProfile(
        resources=(
            BattleHudResourceStyle("hp", "HP", order=0, icon_asset_id="hud.hp"),
            BattleHudResourceStyle("mp", "MP", order=10, icon_asset_id="hud.mp"),
            BattleHudResourceStyle("limit", "LIMIT", order=20),
        ),
        statuses=(BattleHudStatusStyle("poison", "status.poison", label="Poison", order=5),),
    )


def test_hud_mirrors_hp_mp_and_project_defined_gauge_without_mutation():
    hero, resources = _runtime()
    hud = BattleHudRuntime(_profile())
    before = deepcopy(resources.to_data())
    view = hud.sync_member("hero", resources, hero.subject)
    assert [(x.resource_id, x.current, x.maximum) for x in view.gauges] == [
        ("hp", 75, 100),
        ("mp", 13, 40),
        ("limit", 35, 100),
    ]
    assert resources.to_data() == before


def test_hud_reflects_canonical_resource_changes_instead_of_recomputing_them():
    hero, resources = _runtime()
    hud = BattleHudRuntime(_profile())
    hud.sync_member("hero", resources, hero.subject)
    resources.change("hero", "hp", -25)
    resources.change("hero", "limit", 50)
    view = hud.sync_member("hero", resources, hero.subject)
    assert view.gauges[0].current == 50
    assert view.gauges[2].current == 85
    assert view.gauges[2].normalized == 0.85


def test_status_icons_mirror_active_state_stacks_remaining_and_source():
    hero, resources = _runtime()
    hero.subject.states.apply("poison", duration=2.5, source_id="mimic")
    hud = BattleHudRuntime(_profile())
    view = hud.sync_member("hero", resources, hero.subject)
    assert len(view.statuses) == 1
    status = view.statuses[0]
    assert (status.state_id, status.label, status.icon_asset_id) == ("poison", "Poison", "status.poison")
    assert status.stacks == 1 and status.remaining == 2.5 and status.source_id == "mimic"


def test_unmapped_resources_are_generic_and_unmapped_statuses_are_hidden_by_default():
    hero, resources = _runtime()
    hero.subject.states.apply("poison")
    hud = BattleHudRuntime(BattleHudProfile.default())
    view = hud.sync_member("hero", resources, hero.subject)
    assert [x.resource_id for x in view.gauges] == ["hp", "mp", "limit"]
    assert view.gauges[-1].label == "LIMIT"
    assert view.statuses == ()


def test_project_can_hide_unmapped_resources_and_enable_unmapped_status_fallback():
    hero, resources = _runtime()
    hero.subject.states.apply("poison")
    profile = BattleHudProfile(
        resources=(BattleHudResourceStyle("hp", "HP"),),
        show_unmapped_resources=False,
        show_unmapped_statuses=True,
    )
    view = BattleHudRuntime(profile).sync_member("hero", resources, hero.subject)
    assert [x.resource_id for x in view.gauges] == ["hp"]
    assert view.statuses[0].state_id == "poison"
    assert view.statuses[0].icon_asset_id == "status.unmapped"


def test_hud_snapshot_restore_is_deterministic_and_profile_guarded():
    hero, resources = _runtime()
    hero.subject.states.apply("poison", duration=1.75)
    hud = BattleHudRuntime(_profile())
    hud.sync_member("hero", resources, hero.subject)
    snapshot = hud.snapshot()
    restored = BattleHudRuntime(_profile())
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_profile_round_trip_keeps_project_defined_hud_semantics():
    profile = _profile()
    assert BattleHudProfile.from_data(profile.to_data()) == profile


def test_reference_hud_profile_is_canonical_and_data_driven():
    import json
    from pathlib import Path

    data = json.loads(Path("reference_data/batch98_battle_hud_profile.json").read_text())
    profile = BattleHudProfile.from_data(data)
    assert [x.resource_id for x in profile.resources] == ["hp", "mp", "limit"]
    assert [x.state_id for x in profile.statuses] == ["poison", "guard_up"]
