"""Expressions in battle rules: value formulas, hit checks, escape odds, turn order, the final
damage step, battle counters and per-battle dice."""

import random
from pathlib import Path

import pytest

from asteria.gameplay import ResourcePool, StatBlock, TagSet
from asteria.gameplay.expressions import (
    ExpressionError,
    SubjectView,
    check_expression,
    evaluate,
)
from asteria.gameplay.formulas import FormulaContext, ValueFormula
from asteria.rpg.battle_lifecycle import BattleEscapeRule
from asteria.rpg.battle_session_rules import BattleSessionRules
from asteria.rpg.interactions import InteractionResolver, OutcomeCheckDefinition

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"


class _Subject:
    def __init__(self, stats=None, resources=None, tags=(), states=None):
        self.stats = StatBlock(stats or {})
        self.resources = ResourcePool()
        for name, (current, top, low) in (resources or {}).items():
            self.resources.define(name, top, current=current, minimum=low)
        self.tags = TagSet(tags)
        self.states = states


def test_expressions_compute_with_subjects_and_functions():
    hero = SubjectView(_Subject({"attack": 16, "level": 7}, {"hp": (10, 25, 0)}, ("type.water",)))
    names = {"source": hero}
    assert evaluate("floor(2 * source.level / 5 + 2)", names) == 4.0
    assert evaluate('source.current("hp") / source.maximum("hp")', names) == 0.4
    assert evaluate("source.hp", names) == 10.0  # a resource when there is no stat
    assert evaluate('1.5 if source.has("type.water") else 1', names) == 1.5
    assert evaluate("source.missing", names) == 0.0
    assert evaluate("stage(1, 2)", {}) == 1.5
    assert evaluate("stage(-1, 2)", {}) == pytest.approx(2 / 3)
    assert evaluate("stage(-3, 3)", {}) == 0.5
    assert evaluate("clamp(9, 0, 4) + min(1, 2) + max(1, 2)", {}) == 7.0
    assert evaluate("randint(85, 100)", {}, random.Random(1)) in range(85, 101)
    assert evaluate("2 > 1 and not 0", {}) == 1.0


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os')",
        "source.__class__",
        "[1, 2]",
        "(lambda: 1)()",
        "open('x')",
        "9 ** 999",
        "x[0]",
    ],
)
def test_unsafe_or_unknown_expressions_are_refused(text):
    with pytest.raises(ExpressionError):
        check_expression(text, ("source",))
        evaluate(text, {"source": SubjectView(_Subject())})


def test_a_value_formula_may_be_an_expression_and_keeps_its_bounds_and_data():
    formula = ValueFormula(expression="-floor(source.attack * 2 / target.defense)", maximum=-1.0)
    source, target = _Subject({"attack": 10}), _Subject({"defense": 3})
    context = FormulaContext(
        source.stats, source.resources, source.tags, target.stats, target.resources, target.tags
    )
    assert formula.evaluate(context) == -6.0
    weak = _Subject({"defense": 100})
    context = FormulaContext(
        source.stats, source.resources, source.tags, weak.stats, weak.resources, weak.tags
    )
    assert formula.evaluate(context) == -1.0  # the maximum still applies
    assert ValueFormula.from_data(formula.to_data()) == formula
    assert "expression" not in ValueFormula.constant(1).to_data()
    with pytest.raises(ExpressionError):
        ValueFormula(expression="nobody.attack")


def test_a_hit_check_chance_may_be_an_expression():
    check = OutcomeCheckDefinition(
        "land_95",
        0.95,
        failure_tags=("outcome.miss",),
        chance_expression="0.95 * stage(source.stage_accuracy - target.stage_evasion, 3)",
    )
    assert OutcomeCheckDefinition.from_data(check.to_data()) == check
    resolver = InteractionResolver((), (check,))
    blind = _Subject(resources={"stage_accuracy": (-6, 6, -6), "stage_evasion": (0, 6, -6)})
    other = _Subject(resources={"stage_accuracy": (0, 6, -6), "stage_evasion": (0, 6, -6)})
    result = resolver.check("land_95", blind, other, rng=random.Random(0))
    assert result.chance == pytest.approx(0.95 / 3)


def test_an_escape_rule_may_follow_a_speed_formula_and_counts_the_attempts():
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    rule = BattleEscapeRule(
        "run",
        "heroes",
        chance_expression="min(1, 0.1 + 0.3 * attempts)",
    )
    assert BattleEscapeRule.from_data(rule.to_data()) == rule
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    project.rpg_database.escape_rules.clear()
    project.rpg_database.add_escape_rule(rule)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    game.start_encounter(sorted(project.rpg_database.encounters)[0])
    hero = game.active_hero_ids()[0]
    chances = []
    for _ in range(3):
        chances.append(round(game.escape_chance(), 3))
        result = game.attempt_escape(hero, rng=random.Random(99))
        if result.succeeded:
            break
    assert chances[:2] == [0.1, 0.4]


def test_battle_counters_turn_order_final_damage_and_dice():
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_session import GameSessionRuntime

    rules = BattleSessionRules(
        "r",
        knockout_resource_id="vitality",
        battle_counters={"stage_speed": [-6, 6, 0]},
        initiative_expression="1000 - self.speed",  # the slowest first
        final_damage_expression="7",  # every hit deals 7
        vary_seed=True,
    )
    assert BattleSessionRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        BattleSessionRules("r", battle_counters={"x": [1, 0, 0]})
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    db = project.rpg_database
    db.battle_session_rules.clear()
    db.add_battle_session_rules(rules)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    encounter = sorted(db.encounters)[0]
    game.start_encounter(encounter)
    battle = game.battle
    member = next(iter(battle.members.values()))
    assert member.subject.resources.current("stage_speed") == 0.0
    assert member.subject.resources.get("stage_speed").minimum == -6.0
    speeds = {m: battle.member(m).subject.stats.get("speed") for m in battle.members}
    first = game.current_turn_actor()
    assert speeds[first] == min(speeds.values())
    foe = game.active_enemy_ids()[0]
    pool = battle.member(foe).subject.resources
    before = pool.current("vitality")
    ability = next(
        a for a in battle.member(first).ability_ids if game.ability_relation(a).value == "opponent"
    )
    if battle.member(first).side == "heroes":
        game.use_ability(first, ability, [foe])
        assert before - pool.current("vitality") in (0.0, 7.0)  # 0: the hit was dodged
    seeds = set()
    for _ in range(3):
        game.battle = None
        game.mode = "field"
        game.start_encounter(encounter)
        seeds.add(game.battle.rng.random())
    assert len(seeds) == 3  # each battle rolls its own dice
    assert game.world.counters[game.BATTLES_COUNTER] == 4
