from .component import Component
from .metadata import Field, component_schema

@component_schema(
    type_name="asteria.Transform",
    version=1,
    fields=(
        Field("x", float, 0.0),
        Field("y", float, 0.0),
        Field("rotation", float, 0.0),
        Field("scale_x", float, 1.0),
        Field("scale_y", float, 1.0),
    ),
)
class Transform(Component):
    def __init__(self, x=0.0, y=0.0):
        super().__init__()
        self.x = float(x)
        self.y = float(y)
        self.rotation = 0.0
        self.scale_x = 1.0
        self.scale_y = 1.0
