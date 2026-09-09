from asteria.core import ComponentRegistry, Entity, Transform
from asteria.editor.component_picker import build_component_choices


def test_picker_is_registry_driven():
    r = ComponentRegistry()
    r.register(Transform)
    e = Entity("Hero")
    c = build_component_choices(r, e)
    assert len(c) == 1 and c[0].component_type is Transform and c[0].addable
    e.add_component(Transform())
    c = build_component_choices(r, e)
    assert not c[0].addable and c[0].reason == "Already added"
