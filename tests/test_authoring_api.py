from asteria.authoring import AuthoringSession, run_authoring_script
from asteria.core import Entity, Scene, Transform
from asteria.editor.commands import CommandStack, CommandTransaction
from asteria.project import Project


def make_project():
    p = Project("Demo")
    s = p.add_scene(Scene("Town"))
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(1, 2))
    return p, s, e


def test_authoring_lookup_and_transform_mutation():
    p, _, e = make_project()
    api = AuthoringSession(p)
    hero = api.scene("Town").entity("Hero")
    hero.transform.position = (10, 20)
    assert e.get(Transform).x == 10
    assert e.get(Transform).y == 20


def test_authoring_create_entity_and_event():
    p, s, _ = make_project()
    api = AuthoringSession(p)
    npc = api.scene("Town").create_entity("Lina", x=4, y=8)
    npc.event("Greeting").dialogue("Lina", "Hello").set_switch("met_lina").end()

    assert s.get_entity(npc.id) is not None
    assert len(p.event_programs) == 1
    program = p.event_programs.programs()[0]
    assert [x.opcode for x in program.instructions] == ["DIALOGUE", "SET_SWITCH", "END"]


def test_script_runner_uses_authoring_facade():
    p, _, e = make_project()
    result = run_authoring_script(
        'hero = project.scene("Town").entity("Hero")\n'
        "hero.transform.x = 99\n"
        "print(hero.name)\n",
        p,
    )
    assert result.success
    assert result.stdout == "Hero\n"
    assert e.get(Transform).x == 99


def test_script_failure_can_be_rolled_back_transactionally():
    p, _, e = make_project()
    tx = CommandTransaction("Run Authoring Script")

    def apply(command):
        command.redo()
        tx.add(command)

    result = run_authoring_script(
        'hero = project.scene("Town").entity("Hero")\n'
        "hero.transform.x = 50\n"
        'raise RuntimeError("boom")\n',
        p,
        execute=apply,
    )
    assert not result.success
    tx.undo()
    assert e.get(Transform).x == 1


def test_successful_script_is_single_undo_step():
    p, _, e = make_project()
    stack = CommandStack()
    tx = CommandTransaction("Run Authoring Script")

    def apply(command):
        command.redo()
        tx.add(command)

    result = run_authoring_script(
        'hero = project.scene("Town").entity("Hero")\n'
        "hero.transform.position = (7, 9)\n",
        p,
        execute=apply,
    )
    assert result.success
    stack.record_applied(tx)

    assert (e.get(Transform).x, e.get(Transform).y) == (7, 9)
    assert stack.undo()
    assert (e.get(Transform).x, e.get(Transform).y) == (1, 2)
    assert stack.redo()
    assert (e.get(Transform).x, e.get(Transform).y) == (7, 9)
