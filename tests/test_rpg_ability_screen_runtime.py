from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.gameplay.abilities import AbilityDefinition
from asteria.presentation import AbilityScreenProfile, AbilityScreenRuntime
from asteria.rpg.ability_build import AbilityGrant, ActorAbilityState, PassiveDefinition
from asteria.rpg.resolved_build import ResolvedActorBuild


def _build():
    resources = ResourcePool()
    resources.define("focus", 10, current=7)
    return ResolvedActorBuild(
        actor_id="aria",
        stats=StatBlock({"power": 11}),
        resources=resources,
        tags=TagSet(("human",)),
        capabilities=("alchemy",),
        abilities=("slash", "quick_mix", "dash"),
        ability_grants=(
            AbilityGrant("slash", "class", "sword"),
            AbilityGrant("quick_mix", "class", "chemist"),
            AbilityGrant("dash", "equipment", "boots:01"),
        ),
        active_passives=("careful_measure",),
        class_assignment_ids=("sword:primary", "chemist:secondary"),
        equipment_instance_ids=("boots:01",),
        triggers=(),
        contributions=(),
    )


def _abilities():
    return (
        AbilityDefinition("slash", tags=("weapon", "physical")),
        AbilityDefinition("quick_mix", tags=("alchemy", "utility")),
        AbilityDefinition("dash", tags=("movement",)),
        AbilityDefinition("meteor", tags=("arcana", "magic")),
    )


def _passives():
    return (
        PassiveDefinition("careful_measure", "Careful Measure", tags=("alchemy",), granted_abilities=("quick_mix",)),
        PassiveDefinition("fleet_foot", "Fleet Foot", tags=("movement",)),
        PassiveDefinition("stone_skin", "Stone Skin", tags=("defense",)),
    )


def test_projects_resolved_abilities_and_provenance_without_mutation():
    build = _build()
    before = build.to_summary_data()
    state = ActorAbilityState(learned_abilities=("meteor",))
    view = AbilityScreenRuntime().project(
        build, ability_state=state, ability_catalog=_abilities(), passive_catalog=_passives()
    )
    slash = next(x for x in view.abilities if x.ability_id == "slash")
    meteor = next(x for x in view.abilities if x.ability_id == "meteor")
    assert slash.source_labels == ("class:sword",)
    assert slash.resolved is True
    assert meteor.learned is True
    assert meteor.resolved is False
    assert build.to_summary_data() == before


def test_passive_capacity_is_read_only_presentation():
    view = AbilityScreenRuntime().project(_build(), passive_catalog=_passives(), passive_capacity=3)
    assert view.active_passive_ids == ("careful_measure",)
    assert view.passive_capacity == 3
    assert view.passive_capacity_used == 1
    assert next(x for x in view.passives if x.passive_id == "careful_measure").active


def test_project_owned_categories_are_generic():
    profile = AbilityScreenProfile(
        ability_categories={"slash": "techniques", "quick_mix": "formulas", "dash": "movement", "meteor": "arcana"},
        passive_categories={"careful_measure": "craft", "fleet_foot": "mobility", "stone_skin": "guard"},
        category_labels={"formulas": "Formulas"},
    )
    view = AbilityScreenRuntime(profile).project(_build(), ability_catalog=_abilities(), passive_catalog=_passives())
    assert {x.category for x in view.abilities} >= {"techniques", "formulas", "movement", "arcana"}
    assert next(x for x in view.ability_groups if x.category_id == "formulas").label == "Formulas"


def test_query_searches_tags_categories_and_sources():
    profile = AbilityScreenProfile(
        ability_labels={"quick_mix": "Quick Mixture"},
        ability_categories={"quick_mix": "formulas"},
    )
    runtime = AbilityScreenRuntime(profile)
    runtime.set_query("alchemy")
    view = runtime.project(_build(), ability_catalog=_abilities(), passive_catalog=_passives())
    assert [x.ability_id for x in view.abilities] == ["quick_mix"]
    assert "careful_measure" in {x.passive_id for x in view.passives}


def test_large_collection_uses_display_overflow_only():
    abilities = tuple(AbilityDefinition(f"ability_{i}", tags=("bulk",)) for i in range(20))
    profile = AbilityScreenProfile(
        visible_limits={"bulk_group": 5},
        ability_categories={f"ability_{i}": "bulk_group" for i in range(20)},
    )
    view = AbilityScreenRuntime(profile).project(_build(), ability_catalog=abilities)
    group = next(x for x in view.ability_groups if x.category_id == "bulk_group")
    assert len(group.entry_ids) == 20
    assert len(group.visible_entry_ids) == 5
    assert group.overflow_count == 15


def test_tab_category_and_selection_are_presentation_only():
    runtime = AbilityScreenRuntime()
    build = _build()
    before = build.to_summary_data()
    runtime.project(build, ability_catalog=_abilities(), passive_catalog=_passives())
    runtime.set_tab("passives")
    view = runtime.project(build, ability_catalog=_abilities(), passive_catalog=_passives())
    runtime.set_category(view.passive_groups[0].category_id)
    runtime.select(view.passives[0].passive_id)
    assert build.to_summary_data() == before


def test_profile_roundtrip():
    profile = AbilityScreenProfile(
        ability_labels={"slash": "Slash"},
        passive_labels={"stone_skin": "Stone Skin"},
        ability_categories={"slash": "techniques"},
        passive_categories={"stone_skin": "guard"},
        category_labels={"guard": "Guard"},
        visible_limits={"techniques": 8},
        default_ability_category="actions",
        default_passive_category="traits",
    )
    assert AbilityScreenProfile.from_data(profile.to_data()) == profile


def test_snapshot_restore_roundtrip():
    profile = AbilityScreenProfile(
        ability_categories={"slash": "techniques"},
        passive_categories={"stone_skin": "guard"},
    )
    runtime = AbilityScreenRuntime(profile)
    runtime.project(_build(), ability_catalog=_abilities(), passive_catalog=_passives())
    runtime.set_tab("passives")
    runtime.set_query("skin")
    runtime.project(_build(), ability_catalog=_abilities(), passive_catalog=_passives())
    snap = runtime.snapshot()

    restored = AbilityScreenRuntime(profile)
    restored.restore(snap)
    assert restored.snapshot() == snap


def test_no_fixed_skill_slot_count():
    many = tuple(AbilityDefinition(f"skill_{i}", tags=("custom",)) for i in range(37))
    profile = AbilityScreenProfile(ability_categories={f"skill_{i}": "custom_set" for i in range(37)})
    view = AbilityScreenRuntime(profile).project(_build(), ability_catalog=many)
    group = next(x for x in view.ability_groups if x.category_id == "custom_set")
    assert len(group.entry_ids) == 37
