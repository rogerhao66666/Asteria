"""F-3: interaction (elemental weakness / resistance) multipliers reach actual battle damage.

The project's InteractionRule data is the only source of multipliers. Damage
is routed through the existing AbilityRuntime -> apply_effect pipeline inside
BattleRuntime.execute; BattleRuntime.preview_action runs the same pipeline on
cloned subjects, so preview and runtime must agree.
"""

import pytest

from asteria.gameplay import (
    AbilityDefinition, AbilityEffect, AbilityRegistry, AbilityRuntime, AbilityTargetMode, Effect,
    EffectOperation, EffectOperationKind, GameplaySubject, ResourcePool, StatBlock, TagSet, TargetingRule,
)
from asteria.rpg import BattleAction, BattleRuntime, InteractionRule, Party, PartyMember, ReactionDefinition


def _ability(ability_id, tags, value):
    return AbilityDefinition(
        ability_id, tags=tags, targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=True),
        effects=(AbilityEffect(AbilityTargetMode.SELECTED, Effect(
            f"{ability_id}.fx", (EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", value),))),),
    )


def _subject(tags):
    resources = ResourcePool()
    resources.define("hp", 1000, current=1000)
    return GameplaySubject(StatBlock({"power": 10}), resources, TagSet(tags))


ABILITIES = (
    _ability("strike", ("attack.normal",), -100),
    _ability("fire_bolt", ("element.fire",), -100),
    _ability("ice_bolt", ("element.ice",), -100),
    _ability("dark_bolt", ("element.dark",), -100),
    _ability("holy_bolt", ("element.holy",), -100),
    _ability("mend", ("support.heal", "element.fire"), 50),
)


def _rules(fire=2.0):
    return (
        InteractionRule("fire_weak", source_tags_all=("element.fire",), target_tags_all=("weak.fire",), multiplier=fire,
                        outcome_tags=("outcome.weak",)),
        InteractionRule("ice_resist", source_tags_all=("element.ice",), target_tags_all=("resist.ice",), multiplier=0.5),
        InteractionRule("dark_absorb", source_tags_all=("element.dark",), target_tags_all=("absorb.dark",), disposition="absorb"),
        InteractionRule("holy_reflect", source_tags_all=("element.holy",), target_tags_all=("reflect.holy",), disposition="reflect"),
    )


def _battle(rules, enemy_tags=("weak.fire", "resist.ice", "absorb.dark", "reflect.holy"), reactions=()):
    registry = AbilityRegistry()
    for ability in ABILITIES:
        registry.register(ability)
    ids = tuple(a.ability_id for a in ABILITIES)
    hero = PartyMember("hero", "heroes", _subject(()), ability_ids=ids, initiative=20)
    enemy = PartyMember("enemy", "enemies", _subject(enemy_tags), ability_ids=ids, initiative=1)
    return BattleRuntime((Party("heroes", (hero,)), Party("enemies", (enemy,))), AbilityRuntime(registry),
                         interaction_rules=rules, reaction_definitions=reactions, rng_seed=7)


def _hp(battle, member_id):
    return battle.member(member_id).subject.resources.current("hp")


@pytest.mark.parametrize("ability_id, enemy_change, hero_change", [
    ("strike", -100, 0),      # normal attack: no matching rule, unchanged
    ("fire_bolt", -200, 0),   # weakness x2
    ("ice_bolt", -50, 0),     # resistance x0.5
    ("dark_bolt", 100, 0),    # absorb heals the target
    ("holy_bolt", 0, -100),   # reflect hits the actor
])
def test_rules_scale_damage_and_preview_matches_runtime(ability_id, enemy_change, hero_change):
    battle = _battle(_rules())
    if enemy_change > 0:
        battle.member("enemy").subject.resources.change("hp", -500)
    action = BattleAction("hero", ability_id, ("enemy",))
    before = {m: _hp(battle, m) for m in ("hero", "enemy")}
    preview = battle.preview_action(action)
    assert {m: _hp(battle, m) for m in before} == before            # preview mutates nothing
    result = battle.execute(action)
    assert result.execution_result.executed
    assert _hp(battle, "enemy") - before["enemy"] == enemy_change
    assert _hp(battle, "hero") - before["hero"] == hero_change
    observed = {m: {"hp": _hp(battle, m) - before[m]} for m in before if _hp(battle, m) != before[m]}
    assert preview.resource_deltas == observed and preview.executable
    assert [(t, r) for t, r, _ in preview.interactions] == [(t, r) for t, r, _ in result.interactions]


def test_multipliers_come_from_project_data_not_code():
    for multiplier, expected in ((1.25, -125), (3.0, -300)):
        battle = _battle(_rules(fire=multiplier))
        battle.execute(BattleAction("hero", "fire_bolt", ("enemy",)))
        assert _hp(battle, "enemy") == 1000 + expected
    battle = _battle(())                                             # no rules: raw damage
    battle.execute(BattleAction("hero", "fire_bolt", ("enemy",)))
    assert _hp(battle, "enemy") == 900
    battle = _battle(_rules(), enemy_tags=())                        # no weakness tag: raw damage
    battle.execute(BattleAction("hero", "fire_bolt", ("enemy",)))
    assert _hp(battle, "enemy") == 900


def test_healing_is_not_treated_as_damage():
    battle = _battle(_rules())
    battle.member("enemy").subject.resources.change("hp", -200)
    battle.execute(BattleAction("hero", "mend", ("enemy",)))         # fire-tagged heal on a fire-weak target
    assert _hp(battle, "enemy") == 850


def test_reaction_counterattacks_use_the_same_pipeline():
    counter = ReactionDefinition("counter", "rpg.battle.after_action", "event_targets", target_selector="event_source",
                                 ability_id="fire_bolt", blocked_tags=("reaction",))
    battle = _battle(_rules(), enemy_tags=("weak.fire",), reactions=(counter,))
    battle.member("hero").subject.tags.add("weak.fire")
    _, chain = battle.execute_with_reactions(BattleAction("hero", "strike", ("enemy",)))
    assert [x.reaction_id for x in chain.requests] == ["counter"]
    assert _hp(battle, "enemy") == 900 and _hp(battle, "hero") == 800   # counter fire_bolt x2 on a fire-weak hero


def test_reference_session_skill_and_normal_attack_match_preview():
    from test_session_events import _session

    project, game = _session()
    game.start_encounter("boss_room")
    battle = game.battle
    boss = "astral_tyrant:1"
    hero = next(h for h in game.active_hero_ids() if "fire_arc" in battle.member(h).ability_ids)
    for ability_id in ("fire_arc", "strike"):
        if ability_id not in battle.member(hero).ability_ids:
            continue
        action = BattleAction(hero, ability_id, (boss,))
        preview = game.preview(hero, ability_id, (boss,))
        assert preview.resource_deltas == battle.preview_action(action).resource_deltas
        before = battle.member(boss).subject.resources.current("vitality")
        result = game.execute(hero, ability_id, (boss,))
        dealt = before - battle.member(boss).subject.resources.current("vitality")
        assert preview.resource_deltas.get(boss, {}).get("vitality", 0) == -dealt
        matched = {r.matched_rules for t, _, r in result.interactions if t == boss}
        assert (("weak_fire",) in matched) == (ability_id == "fire_arc")
