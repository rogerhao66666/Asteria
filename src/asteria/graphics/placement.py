from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class RenderPlacement2D:
    layer:int=0
    depth:float=0.0
    elevation:float=0.0
    parallax_x:float=1.0
    parallax_y:float=1.0
    def validate(self):
        if self.parallax_x<0 or self.parallax_y<0:
            raise ValueError("parallax must be non-negative")
