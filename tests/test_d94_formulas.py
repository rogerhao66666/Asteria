"""D94: formulas typed or built with buttons, reading only the stats Game Systems ▸ Stats
declares; an empty formula leaves the record's other fields in charge."""

import os
import random
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from asteria.gameplay.expressions import FORMULA_FIELDS, undeclared, variables
from asteria.gameplay.stats import StatBlock
from asteria.rpg.derived_stats import DerivedStatRule, apply_derived_stats

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def test_a_formula_reads_stats_and_resources_as_variables():
    text = '0.95 + 0.003 * source.accuracy - target.evade + source.ratio("hp") + source.has("x")'
    assert variables(text) == (("accuracy", "evade"), ("hp",))
    assert undeclared("source.atk + target.current('mana') + source.hp", ["acc"], ["hp"]) == [
        "atk",
        "mana",
    ]  # source.hp reads the resource's current value: declared


def test_a_stat_formula_can_be_written_as_text():
    rule = DerivedStatRule("accuracy", expression="self.dex + 0.5 * self.luk")
    assert DerivedStatRule.from_data(rule.to_data()) == rule
    assert "expression" not in DerivedStatRule("accuracy", terms={"dex": 1}).to_data()
    stats = StatBlock({"dex": 9, "luk": 4})
    apply_derived_stats(stats, (rule,))
    assert stats.get("accuracy") == 11.0
    assert rule.formula_text() == "accuracy += self.dex + 0.5 * self.luk"
    with pytest.raises(ValueError):
        DerivedStatRule("accuracy", expression="target.dex")  # only self here
    capped = DerivedStatRule("crit", expression="self.luk * 10", maximum=30)
    stats = StatBlock({"luk": 4})
    apply_derived_stats(stats, (capped,))
    assert stats.get("crit") == 30  # the cap still applies


def test_every_formula_field_names_its_variables():
    assert FORMULA_FIELDS[("asteria.rpg.outcome_check", "chance_expression")] == (
        "source",
        "target",
    )
    assert FORMULA_FIELDS[("asteria.rpg.derived_stat", "expression")] == ("self",)


def test_an_undeclared_stat_is_an_error_only_where_stats_are_defined():
    from asteria.editor.formula_field import formula_problem

    names = ("source", "target")
    assert formula_problem("", names, ["dex"], [], True) == ""  # empty: the fields count
    assert formula_problem("source.dex * 2", names, ["dex"], [], True) == ""
    assert "luck" in formula_problem("source.luck", names, ["dex"], [], True)
    assert formula_problem("source.luck", names, ["dex"], [], False) == ""  # no definitions
    assert formula_problem("self.dex", names, ["dex"], [], True)  # self is not given here
    assert formula_problem("source.dex +", names, ["dex"], [], True)  # does not parse


# -- the Full Verification demo -----------------------------------------------------------------
@pytest.fixture(scope="module")
def project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def test_the_demo_formulas_give_the_numbers_the_fields_gave(project):
    from asteria.gameplay import GameplaySubject, ResourcePool, TagSet
    from asteria.rpg.interactions import InteractionResolver, OutcomeCheckDefinition

    db = project.rpg_database
    rule = db.derived_stats["accuracy"]
    assert rule.expression == "self.dex + 0.5 * self.luk" and not rule.terms
    for dex, luk in ((9, 4), (31, 17), (0, 0)):
        stats = StatBlock({"dex": dex, "luk": luk})
        assert rule.amount(stats) == 1.0 * dex + 0.5 * luk
    land = db.outcome_checks["land"]
    old = OutcomeCheckDefinition(
        "land",
        0.95,
        source_stat_terms={"accuracy": 0.003},
        target_stat_terms={"evade": -0.003},
        minimum_chance=0.3,
        failure_tags=("outcome.evade",),
    )
    for accuracy, evade in ((10, 50), (80, 5), (0, 400)):
        source = GameplaySubject(StatBlock({"accuracy": accuracy}), ResourcePool(), TagSet())
        target = GameplaySubject(StatBlock({"evade": evade}), ResourcePool(), TagSet())
        rolls = [
            InteractionResolver(checks=(check,)).check(
                "land", source, target, rng=random.Random(1)
            )
            for check in (land, old)
        ]
        new, before = rolls
        assert new.chance == pytest.approx(before.chance)


def test_the_problems_list_names_a_formula_reading_an_undeclared_stat(project):
    import dataclasses

    from asteria.editor.problems import _formulas

    db = project.rpg_database
    found = []
    _formulas(project, found)
    assert found == []  # the demo's formulas read declared stats only
    land = db.outcome_checks["land"]
    db.outcome_checks["land"] = dataclasses.replace(land, chance_expression="source.luck * 2")
    try:
        _formulas(project, found)
    finally:
        db.outcome_checks["land"] = land
    (problem,) = found
    assert problem.severity == "error" and "luck" in problem.message and "land" in problem.message


# -- the editor ---------------------------------------------------------------------------------
@pytest.fixture
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_buttons_insert_declared_stats_and_functions(app, project):
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.formula_field import FormulaField
    from asteria.editor.record_vocabulary import ProjectVocabulary

    field = FormulaField(("source", "target"), ProjectVocabulary(project))
    assert field.strict
    declared = {c.value for c in field.stats}
    assert declared == set(project.rpg_database.stat_definitions)
    buttons = {b.text(): b for b in field.findChildren(QToolButton)}
    assert {"source ▾", "target ▾", "+", "×", "("} <= set(buttons)
    menu = [buttons["source ▾"]]
    actions = {a.text().split("·")[-1].strip(): a for a in menu[0].menu().actions()}
    actions["source.accuracy"].trigger()
    field.insert(" * ")
    field.insert("max(, )", back=3)
    field.insert("1")
    assert field.text() == "source.accuracy * max(1, )"
    field.setText("source.accuracy * 0.003")
    assert field.valid() and "✓" in field.status.text()
    field.setText("source.luck_bonus")
    assert not field.valid() and "luck_bonus" in field.status.text()


def test_a_chance_check_takes_its_formula_from_the_field_only_when_valid(app, project):
    from asteria.editor.formula_field import FormulaField
    from asteria.editor.record_form import RecordForm
    from asteria.editor.record_vocabulary import ProjectVocabulary

    editor = RecordForm()
    editor.vocabulary = ProjectVocabulary(project)
    data = project.rpg_database.outcome_checks["land"].to_data()
    field = editor.widget_for(data, "chance_expression", data["chance_expression"])
    assert isinstance(field, FormulaField) and field.names == ("source", "target")
    field.edit.setText("0.9 + 0.002 * source.accuracy")
    assert data["chance_expression"] == "0.9 + 0.002 * source.accuracy"
    field.edit.setText("0.9 + source.not_a_stat")
    assert data["chance_expression"] == "0.9 + 0.002 * source.accuracy"  # not applied


def test_a_skill_formula_shows_while_empty():
    from asteria.editor.authoring_hub_widget import _with_formula_fields

    data = {"effects": [{"amount": {"schema": "asteria.value_formula", "terms": []}}]}
    shown = _with_formula_fields(data)
    assert shown["effects"][0]["amount"]["expression"] == ""


def test_the_stat_formula_page_has_a_formula_field_and_refuses_a_bad_one(app, project):
    from asteria.editor import EditorDocument
    from asteria.editor.formula_field import FormulaField
    from asteria.editor.game_systems_authoring import (
        GameSystemsAuthoringController,
        GameSystemsAuthoringError,
    )
    from asteria.editor.game_systems_widget import GameSystemsEditorWidget

    widget = GameSystemsEditorWidget(GameSystemsAuthoringController(EditorDocument(project)))
    from PySide6.QtCore import Qt

    widget.set_kind("derived_stats")
    rows = [widget.browser.item(i).data(Qt.UserRole) for i in range(widget.browser.count())]
    widget.browser.setCurrentRow(rows.index("accuracy"))
    form = widget.form
    field = form.widgets["expression"]
    assert isinstance(field, FormulaField) and field.text() == "self.dex + 0.5 * self.luk"
    field.edit.setText("self.dex + self.charm")
    with pytest.raises(GameSystemsAuthoringError, match="charm"):
        form.data()
    field.edit.setText("self.dex * 2")
    assert form.data()["expression"] == "self.dex * 2"
