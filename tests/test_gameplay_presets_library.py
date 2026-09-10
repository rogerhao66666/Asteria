from asteria.gameplay import (
    AbilityRuntime,
    AbilityTarget,
    GameplayLibrary,
    GameplayPresetCatalog,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
    simple_rpg_attributes,
)


def test_simple_rpg_defaults_are_immediately_usable():
    a = simple_rpg_attributes()
    assert a.resources.current("hp") == 100
    assert a.resources.current("mp") == 30
    assert a.stats.get("attack") == 10
    assert a.stats.get("defense") == 10
    assert a.tags.contains("actor.player")


def test_default_catalog_contains_beginner_ready_content():
    c = GameplayPresetCatalog.defaults()
    assert {"standard_physical", "standard_magic", "flat"} <= set(c.formulas)
    assert {"basic_attack", "simple_heal"} <= set(c.abilities)
    assert "basic_melee" in c.timelines


def test_presets_are_ordinary_canonical_values():
    c = GameplayPresetCatalog.defaults()
    assert c.abilities["basic_attack"].ability_id == "basic_attack"
    assert c.timelines["basic_melee"].timeline_id == "basic_melee"
    # No runtime preset type or special execution path exists.
    lib = GameplayLibrary()
    lib.add_ability(c.abilities["basic_attack"])
    lib.add_timeline(c.timelines["basic_melee"])
    assert lib.abilities.require("basic_attack") == c.abilities["basic_attack"]


def test_gameplay_library_roundtrip_with_defaults():
    c = GameplayPresetCatalog.defaults()
    lib = GameplayLibrary()
    for k, v in c.formulas.items():
        lib.add_formula(k, v)
    for v in c.abilities.values():
        lib.add_ability(v)
    for v in c.timelines.values():
        lib.add_timeline(v)
    restored = GameplayLibrary.from_data(lib.to_data())
    assert restored.to_data() == lib.to_data()


def test_basic_attack_preset_executes_without_advanced_configuration():
    c = GameplayPresetCatalog.defaults()
    reg = GameplayLibrary()
    reg.add_ability(c.abilities["basic_attack"])
    srcpool = ResourcePool()
    srcpool.define("hp", 100, current=100)
    tgtpool = ResourcePool()
    tgtpool.define("hp", 100, current=100)
    src = AbilityTarget(
        "hero", GameplaySubject(StatBlock(), srcpool, TagSet(["actor.player"]), None)
    )
    tgt = AbilityTarget(
        "enemy", GameplaySubject(StatBlock(), tgtpool, TagSet(["enemy"]), None)
    )
    result = AbilityRuntime(reg.abilities).execute("basic_attack", src, [tgt])
    assert result.executed
    assert tgt.subject.resources.current("hp") == 90


def test_defaults_are_copies_not_global_mutable_singletons():
    a = GameplayPresetCatalog.defaults()
    b = GameplayPresetCatalog.defaults()
    assert a is not b
    assert a.abilities is not b.abilities
    assert a.timelines is not b.timelines


def test_blank_advanced_library_remains_available():
    lib = GameplayLibrary()
    assert lib.abilities.ids() == ()
    assert lib.formulas == {}
    assert lib.timelines == {}
