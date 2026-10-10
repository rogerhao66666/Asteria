from types import SimpleNamespace

from asteria.presentation import (
    BattleHudProfile,
    BattleHudResourceStyle,
    BattleHudRuntime,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
)
from asteria.runtime import Camera2D


def _value(current, maximum):
    maximum = float(maximum)
    current = float(current)
    return SimpleNamespace(
        current=current,
        minimum=0.0,
        maximum=maximum,
        overflow=0.0,
        normalized=0.0 if maximum == 0 else current / maximum,
        full=maximum != 0 and current >= maximum,
    )


def _resources():
    return SimpleNamespace(
        values={
            "hero": {
                "hp": _value(75, 100),
                "bp": _value(3, 5),
                "sp": _value(17, 30),
                "atb": _value(60, 100),
                "guard": _value(2, 6),
                "limit": _value(40, 100),
                "heat": _value(4, 10),
                "secret": _value(1, 1),
            }
        }
    )


def _profile():
    return BattleHudProfile(
        (
            BattleHudResourceStyle("hp", "HP", presentation="bar", order=0),
            BattleHudResourceStyle("bp", "BP", presentation="pips", segments=5, order=10, compact=True),
            BattleHudResourceStyle("sp", "SP", presentation="number", order=20),
            BattleHudResourceStyle("atb", "ACT", presentation="action_gauge", order=30, show_value=False),
            BattleHudResourceStyle("guard", "Guard", presentation="segmented_bar", segments=6, order=40),
            BattleHudResourceStyle("limit", "Limit", presentation="ring", order=50, group="secondary"),
            BattleHudResourceStyle("heat", "Heat", presentation="heat_orbit", order=60, priority=7),
            BattleHudResourceStyle("secret", "Secret", presentation="hidden", order=70),
        )
    )


def test_resource_policy_is_project_defined_and_not_hp_mp_specific():
    profile = _profile()
    assert profile.resource_style("bp").presentation == "pips"
    assert profile.resource_style("bp").segments == 5
    assert profile.resource_style("limit").presentation == "ring"
    assert profile.resource_style("heat").presentation == "heat_orbit"
    assert profile.resource_style("secret").visible is False


def test_hud_runtime_preserves_generic_presentation_metadata_without_resource_mutation():
    profile = _profile()
    runtime = BattleHudRuntime(profile)
    source = _resources()
    before = {k: (v.current, v.maximum, v.normalized) for k, v in source.values["hero"].items()}
    member = runtime.sync_member("hero", source, SimpleNamespace(states=None))
    after = {k: (v.current, v.maximum, v.normalized) for k, v in source.values["hero"].items()}
    assert before == after

    by_id = {g.resource_id: g for g in member.gauges}
    assert "secret" not in by_id
    assert by_id["bp"].presentation == "pips"
    assert by_id["bp"].segments == 5
    assert by_id["sp"].presentation == "number"
    assert by_id["limit"].group == "secondary"
    assert by_id["heat"].priority == 7


def test_ui_composer_projects_number_pips_action_ring_and_custom_roles_without_semantic_inference():
    runtime = BattleHudRuntime(_profile())
    member = runtime.sync_member("hero", _resources(), SimpleNamespace(states=None))
    scene = BattlePresentationScene("generic.resources", "bg", ())
    frame = BattleUiComposer(scene).compose(
        Camera2D(),
        BattlePresentationFrame("generic.resources", "bg", ()),
        hud_members=(member,),
    )

    gauges = {g.resource_id: g for g in frame.gauges}
    assert gauges["hp"].presentation == "bar"
    assert gauges["bp"].presentation == "pips"
    assert gauges["bp"].segments == 5
    assert gauges["atb"].presentation == "action_gauge"
    assert gauges["guard"].presentation == "segmented_bar"
    assert gauges["limit"].presentation == "ring"
    assert gauges["heat"].presentation == "heat_orbit"
    assert "sp" not in gauges
    assert any(t.text == "17" and t.role == "resource_value:number" for t in frame.texts)


def test_resource_policy_roundtrip_is_deterministic_and_keeps_custom_roles():
    profile = _profile()
    restored = BattleHudProfile.from_data(profile.to_data())
    assert restored == profile
    assert restored.resource_style("heat").presentation == "heat_orbit"


def test_default_profile_remains_beginner_friendly_convenience_not_engine_rule():
    default = BattleHudProfile.default()
    assert default.resource_style("hp").label == "HP"
    assert default.resource_style("mp").label == "MP"
    assert default.show_unmapped_resources is True

    runtime = BattleHudRuntime(default)
    source = SimpleNamespace(values={"hero": {"momentum": _value(4, 10)}})
    member = runtime.sync_member("hero", source, SimpleNamespace(states=None))
    assert member.gauges[0].resource_id == "momentum"
    assert member.gauges[0].presentation == "bar"
