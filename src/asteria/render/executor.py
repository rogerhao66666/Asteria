def execute_frame(plan, backend, materials=()):
    material_map = {m.material_id: m for m in materials}
    backend.begin_scene()
    try:
        for d in plan.opaque_draws:
            backend.draw_material_sprite(d, material_map[d.material_id])
        for s in plan.shadow_casters:
            backend.draw_shadow_caster(s)
        if plan.ambient is not None:
            backend.set_ambient(plan.ambient)
        for l in plan.lights:
            backend.draw_light(l)
        for p in plan.particle_emitters:
            backend.draw_particles(p)
        for d in plan.translucent_draws:
            backend.draw_material_sprite(d, material_map[d.material_id])
        if plan.fog is not None:
            backend.apply_fog(plan.fog)
        for e in plan.post_effects:
            backend.apply_post_effect(e)
    finally:
        backend.end_scene()
