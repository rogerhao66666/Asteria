from asteria.gameplay import (
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
)


def runtime(defs, tags=()):
    t = TagSet(tags)
    return StateRuntime(StateRegistry(defs), StatBlock(), ResourcePool(), t), t


def test_state_contributed_tag_removed_when_last_owner_expires():
    rt, tags = runtime([StateDefinition("burn", 1, contributed_tags=["status.hot"])])
    rt.apply("burn")
    assert tags.contains("status.hot")
    rt.remove("burn")
    assert not tags.contains("status.hot")


def test_state_never_removes_preexisting_base_tag():
    rt, tags = runtime(
        [StateDefinition("blessing", 1, contributed_tags=["holy"])], ["holy"]
    )
    rt.apply("blessing")
    rt.remove("blessing")
    assert tags.contains("holy")


def test_overlapping_state_contributions_are_reference_safe():
    defs = [
        StateDefinition("a", 10, contributed_tags=["status.controlled"]),
        StateDefinition("b", 10, contributed_tags=["status.controlled"]),
    ]
    rt, tags = runtime(defs)
    rt.apply("a")
    rt.apply("b")
    rt.remove("a")
    assert tags.contains("status.controlled")
    rt.remove("b")
    assert not tags.contains("status.controlled")


def test_state_definition_v1_backward_compatibility():
    raw = StateDefinition("old", 2).to_data()
    raw.pop("contributed_tags")
    raw.pop("on_expire")
    raw["version"] = 1
    restored = StateDefinition.from_data(raw)
    assert restored.contributed_tags == ()


def test_restore_reconstructs_state_tag_contributions_without_effect_replay():
    defs = [StateDefinition("a", 10, contributed_tags=["status.a"])]
    rt, _tags = runtime(defs)
    rt.apply("a")
    snap = rt.snapshot()
    rt2, tags2 = runtime(defs)
    rt2.restore(snap)
    assert tags2.contains("status.a")
    rt2.remove("a")
    assert not tags2.contains("status.a")
