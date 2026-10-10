from asteria.authoring import run_authoring_script
from asteria.core import Entity, Scene, Transform
from asteria.project import Project


def make_project():
    p = Project("Demo")
    s = p.add_scene(Scene("Town"))
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(1, 2))
    return p, s, e


def test_selection_context_exposes_selected_entity_and_scene():
    p, _s, e = make_project()
    result = run_authoring_script(
        "print(selected.name)\nprint(entity.name)\nprint(scene.name)\nentity.transform.x = 42\n",
        p,
        selection_kind="entity",
        selection_value=e,
        filename="scripts/main.py",
    )
    assert result.success
    assert result.stdout == "Hero\nHero\nTown\n"
    assert e.get(Transform).x == 42


def test_scene_selection_exposes_scene_without_entity():
    p, s, _ = make_project()
    result = run_authoring_script(
        "print(selected.name)\nprint(scene.name)\nprint(entity)\n",
        p,
        selection_kind="scene",
        selection_value=s,
        filename="scripts/main.py",
    )
    assert result.success
    assert result.stdout == "Town\nTown\nNone\n"


def test_runtime_error_reports_script_line():
    p, _, _ = make_project()
    result = run_authoring_script(
        'x = 1\ny = 2\nraise RuntimeError("boom")\n',
        p,
        filename="scripts/main.py",
    )
    assert not result.success
    assert result.line == 3
    assert result.filename == "scripts/main.py"
    assert result.exception_type == "RuntimeError"
    assert "scripts/main.py:3" in result.diagnostic


def test_syntax_error_reports_line_and_column():
    p, _, _ = make_project()
    result = run_authoring_script(
        'x = 1\nif True print("bad")\n',
        p,
        filename="scripts/main.py",
    )
    assert not result.success
    assert result.line == 2
    assert result.column is not None
    assert result.exception_type == "SyntaxError"


def test_component_selection_wraps_owning_entity():
    p, _, e = make_project()
    transform = e.get(Transform)
    result = run_authoring_script(
        "print(selected.name)\nselected.transform.y = 77\n",
        p,
        selection_kind="component",
        selection_value=transform,
    )
    assert result.success
    assert result.stdout == "Hero\n"
    assert transform.y == 77
