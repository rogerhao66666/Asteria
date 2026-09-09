class HeadlessRenderBackend:
    def __init__(self):
        self.ops = []

    def begin_scene(self):
        self.ops.append(("begin",))

    def draw_material_sprite(self, draw, material):
        self.ops.append(("sprite", draw.material_id))

    def draw_shadow_caster(self, shadow):
        self.ops.append(("shadow", shadow.caster_id))

    def draw_light(self, light):
        self.ops.append(("light", light.light_id))

    def set_ambient(self, ambient):
        self.ops.append(("ambient", ambient.intensity))

    def draw_particles(self, emitter):
        self.ops.append(("particles", emitter.emitter_id))

    def apply_fog(self, fog):
        self.ops.append(("fog", fog.density))

    def apply_post_effect(self, effect):
        self.ops.append(("post", effect.effect_id))

    def end_scene(self):
        self.ops.append(("end",))
