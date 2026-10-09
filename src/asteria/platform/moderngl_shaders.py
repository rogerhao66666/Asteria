"""GLSL source strings for the moderngl backend.

Kept as plain module-level strings rather than a package/`.glsl` files: there
is one shader program in this phase (the textured sprite quad), and inline
strings avoid a second asset-loading path just to read GLSL text off disk.
Split into its own module so `moderngl_backend.py` stays readable as the
batching/orchestration logic grows across later phases.
"""

# Vertex layout per quad instance: screen-space pixel position, plus a
# per-vertex UV. Screen pixels are remapped to clip space in the vertex
# shader via `u_screen_size` rather than pre-normalizing on the CPU, so the
# same vertex data works whether the target is the window or an offscreen
# scene FBO of a different size (Phase 2).
SPRITE_VERTEX_SHADER = """
#version 330

uniform vec2 u_screen_size;

in vec2 in_position;
in vec2 in_uv;
in vec4 in_tint;

out vec2 v_uv;
out vec4 v_tint;

void main() {
    vec2 ndc = vec2(
        (in_position.x / u_screen_size.x) * 2.0 - 1.0,
        1.0 - (in_position.y / u_screen_size.y) * 2.0
    );
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
    v_tint = in_tint;
}
"""

# Nearest-neighbor sampling is set on the texture object itself (pixel-art
# filtering policy lives with the texture, not the shader); this fragment
# shader only applies the opacity/flip tint already baked into `in_tint` by
# the batcher and multiplies it against the sampled texel.
SPRITE_FRAGMENT_SHADER = """
#version 330

uniform sampler2D u_texture;

in vec2 v_uv;
in vec4 v_tint;

out vec4 f_color;

void main() {
    vec4 texel = texture(u_texture, v_uv);
    f_color = texel * v_tint;
}
"""
