from dataclasses import dataclass

@dataclass(slots=True)
class SpriteRendererState:
    texture_id:str
    frames:list
    frame_index:int=0
    flip_x:bool=False
    opacity:float=1.0

    @property
    def frame(self):
        return self.frames[self.frame_index]

    def sync_animator(self,animator):
        idx=animator.frame_index
        if idx<0 or idx>=len(self.frames):
            raise IndexError("animator frame outside sprite sheet")
        self.frame_index=idx
