from dataclasses import dataclass

@dataclass(slots=True)
class PlayerRuntime:
    controller:object
    tile_query:object
    animator:object
    animation_controller:object
    sprite_renderer:object
    camera_follow:object|None=None

    def update(self,input_snapshot,dt):
        dx,dy=input_snapshot.movement_vector()
        moved_x,moved_y=self.controller.move(dx,dy,dt,self.tile_query)
        self.animation_controller.update_motion(moved_x,moved_y)
        self.animator.update(dt)
        self.sprite_renderer.sync_animator(self.animator)
        if self.camera_follow is not None:
            self.camera_follow.update(self.controller.x,self.controller.y,dt)
        return moved_x,moved_y
