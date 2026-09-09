from asteria.core import Component
from asteria.core.metadata import Field, component_schema
from asteria.editor.inspector import build_inspector_fields


@component_schema(
    fields=(
        Field(
            "speed",
            float,
            1.0,
            label="Move Speed",
            minimum=0.0,
            maximum=10.0,
            tooltip="units/sec",
        ),
        Field("runtime", int, 0, serialize=False),
    )
)
class Demo(Component):
    def __init__(self):
        super().__init__()
        self.speed = 3.0
        self.runtime = 7


def test_inspector_preserves_canonical_metadata():
    fields = {f.name: f for f in build_inspector_fields(Demo())}
    assert fields["speed"].label == "Move Speed"
    assert fields["speed"].minimum == 0.0 and fields["speed"].maximum == 10.0
    assert fields["speed"].tooltip == "units/sec"
    assert fields["runtime"].editable is False
