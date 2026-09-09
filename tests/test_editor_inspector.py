from asteria.core import Transform
from asteria.editor.inspector import build_inspector_fields

def test_inspector_comes_from_component_metadata():
    fields=build_inspector_fields(Transform(5.0,7.0))
    names=[f.name for f in fields]
    assert names==["x","y","rotation","scale_x","scale_y"]
    values={f.name:f.value for f in fields}
    assert values["x"]==5.0 and values["y"]==7.0
