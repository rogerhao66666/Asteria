"""GPU effect chain for the playable game (VFX-02 / VFX-03, proposal R3–R6) on the ModernGL presenter.

Per frame: the runtime's world layer (and optional normal layer) and its UI layer arrive as
textures. Passes (each only when the scene environment asks for it):

1. light map (half resolution, float): ambient + every light (radial falloff, Lambert term
   from the normal layer); a shadow-casting light is drawn alone, its occluders' shadow
   quads zeroed, then added
2. scene: world x light map, then drifting fog
3. bloom: bright pass + separable blur at half resolution
4. grade: + bloom, exposure / contrast / saturation / tint, vignette
5. screen shader: a built-in effect or a project ``shader`` asset (fixed contract, compiled once)
6. UI composited on top (never lit, graded or bloomed)

Everything runs on the GPU; Python only builds a handful of quads per light/caster. A project
shader that fails to compile is switched off and its error kept in ``errors`` - the game goes on.

Texture convention: uploaded textures (world, UI, normals) have v = 0 at the top of the screen;
textures rendered into framebuffers are sampled with v flipped (``fbo_uv``).
"""

from __future__ import annotations

import math
from array import array

VERTEX = """
#version 330
in vec2 in_pos;
in vec2 in_px;
out vec2 v_px;
void main() { gl_Position = vec4(in_pos, 0.0, 1.0); v_px = in_px; }
"""

LIGHT_FRAGMENT = """
#version 330
uniform vec2 u_screen;
uniform vec2 u_center;
uniform float u_radius;
uniform float u_height;
uniform vec3 u_color;
uniform sampler2D u_normals;
in vec2 v_px;
out vec4 f_color;
void main() {
    vec2 d = u_center - v_px;
    float dist = length(d);
    float fall = clamp(1.0 - dist / u_radius, 0.0, 1.0);
    fall = fall * fall;
    vec3 n = texture(u_normals, v_px / u_screen).rgb * 2.0 - 1.0;
    vec3 l = normalize(vec3(d.x, -d.y, u_height));
    float lambert = max(dot(normalize(n), l), 0.0);
    f_color = vec4(u_color * fall * lambert, 1.0);
}
"""

SOLID_FRAGMENT = """
#version 330
uniform vec4 u_color;
in vec2 v_px;
out vec4 f_color;
void main() { f_color = u_color; }
"""

COPY_FBO_FRAGMENT = """
#version 330
uniform sampler2D u_src;
uniform vec2 u_screen;
in vec2 v_px;
out vec4 f_color;
void main() { vec2 uv = v_px / u_screen; f_color = texture(u_src, vec2(uv.x, 1.0 - uv.y)); }
"""

SCENE_FRAGMENT = """
#version 330
uniform sampler2D u_world;
uniform sampler2D u_light;
uniform vec2 u_screen;
uniform int u_lighting;
uniform float u_fog;
uniform vec3 u_fog_color;
uniform float u_time;
uniform float u_drift;
uniform int u_water_count;
uniform vec4 u_water_rect[8];   // x0, y0, x1, y1 (screen px)
uniform vec4 u_water_wave[8];   // amplitude px, wavelength px, speed, tint strength
uniform vec3 u_water_tint[8];
in vec2 v_px;
out vec4 f_color;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
void main() {
    vec2 uv = v_px / u_screen;
    vec3 tint = vec3(0.0);
    float tint_amount = 0.0;
    for (int i = 0; i < u_water_count; ++i) {
        vec4 r = u_water_rect[i];
        if (v_px.x >= r.x && v_px.x <= r.z && v_px.y >= r.y && v_px.y <= r.w) {
            vec4 w = u_water_wave[i];
            float phase = v_px.y / w.y * 6.2831853 + u_time * w.z;
            vec2 offset = vec2(sin(phase), 0.5 * cos(phase * 0.7 + v_px.x / w.y * 3.0)) * w.x;
            vec2 sample_px = clamp(v_px + offset, r.xy, r.zw);
            uv = sample_px / u_screen;
            tint = u_water_tint[i];
            tint_amount = w.w;
        }
    }
    vec3 c = texture(u_world, uv).rgb;
    c = mix(c, c * tint * 1.6, tint_amount);
    if (u_lighting == 1) c *= texture(u_light, vec2(uv.x, 1.0 - uv.y)).rgb;
    if (u_fog > 0.0) {
        vec2 p = v_px / 96.0 + vec2(u_time * u_drift / 96.0, 0.0);
        float n = 0.55 * noise(p) + 0.3 * noise(p * 2.1 + 7.0) + 0.15 * noise(p * 4.3 + 3.0);
        c = mix(c, u_fog_color, clamp(u_fog * (0.55 + 0.9 * n), 0.0, 1.0));
    }
    f_color = vec4(c, 1.0);
}
"""

BRIGHT_FRAGMENT = """
#version 330
uniform sampler2D u_src;
uniform vec2 u_screen;
uniform float u_threshold;
in vec2 v_px;
out vec4 f_color;
void main() {
    vec2 uv = v_px / u_screen;
    vec3 c = texture(u_src, vec2(uv.x, 1.0 - uv.y)).rgb;
    float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
    f_color = vec4(c * smoothstep(u_threshold, u_threshold + 0.25, luma), 1.0);
}
"""

BLUR_FRAGMENT = """
#version 330
uniform sampler2D u_src;
uniform vec2 u_screen;
uniform vec2 u_dir;
in vec2 v_px;
out vec4 f_color;
void main() {
    vec2 uv = v_px / u_screen;
    uv = vec2(uv.x, 1.0 - uv.y);
    vec2 step = u_dir / vec2(textureSize(u_src, 0));
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    vec3 c = texture(u_src, uv).rgb * w[0];
    for (int i = 1; i < 5; ++i) {
        c += texture(u_src, uv + step * float(i)).rgb * w[i];
        c += texture(u_src, uv - step * float(i)).rgb * w[i];
    }
    f_color = vec4(c, 1.0);
}
"""

GRADE_FRAGMENT = """
#version 330
uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform vec2 u_screen;
uniform float u_bloom_intensity;
uniform float u_exposure;
uniform float u_contrast;
uniform float u_saturation;
uniform vec3 u_tint;
uniform float u_vignette;
in vec2 v_px;
out vec4 f_color;
void main() {
    vec2 uv = v_px / u_screen;
    vec2 fuv = vec2(uv.x, 1.0 - uv.y);
    vec3 c = texture(u_scene, fuv).rgb + texture(u_bloom, fuv).rgb * u_bloom_intensity;
    c *= u_exposure;
    c = (c - 0.5) * u_contrast + 0.5;
    float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(luma), c, u_saturation) * u_tint;
    if (u_vignette > 0.0) {
        vec2 q = uv - 0.5;
        c *= 1.0 - u_vignette * smoothstep(0.25, 0.75, length(q) * 1.2);
    }
    f_color = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""

BUILTIN_SHADER = """
#version 330
uniform sampler2D u_src;
uniform vec2 u_screen;
uniform int u_mode;
uniform float u_strength;
uniform float u_time;
in vec2 v_px;
out vec4 f_color;
vec3 at(vec2 uv) { return texture(u_src, vec2(uv.x, 1.0 - uv.y)).rgb; }
void main() {
    vec2 uv = v_px / u_screen;
    vec3 base = at(uv);
    vec3 c = base;
    if (u_mode == 1) { c = vec3(dot(base, vec3(0.2126, 0.7152, 0.0722))); }
    else if (u_mode == 2) {
        float l = dot(base, vec3(0.299, 0.587, 0.114));
        c = vec3(l * 1.07, l * 0.74, l * 0.43);
    }
    else if (u_mode == 3) { c = 1.0 - base; }
    else if (u_mode == 4) { c = at(uv + vec2(sin(uv.y * 40.0 + u_time * 3.0) * 0.004, 0.0)); }
    else if (u_mode == 5) {
        float scan = 0.85 + 0.15 * sin(v_px.y * 3.14159);
        c = at(uv) * scan;
    }
    else if (u_mode == 6) {
        vec2 cell = vec2(4.0) / u_screen;
        c = at(floor(uv / cell) * cell + cell * 0.5);
    }
    f_color = vec4(mix(base, c, u_strength), 1.0);
}
"""

PROJECT_SHADER_HEADER = """
#version 330
uniform sampler2D u_src;
uniform vec2 u_screen;
uniform float u_strength;
uniform float u_time;
in vec2 v_px;
out vec4 f_color;
vec4 scene(vec2 uv) { return texture(u_src, vec2(uv.x, 1.0 - uv.y)); }
#line 1
"""

PROJECT_SHADER_FOOTER = """
void main() {
    vec2 uv = v_px / u_screen;
    vec4 base = scene(uv);
    f_color = vec4(mix(base.rgb, effect(uv).rgb, u_strength), 1.0);
}
"""

UI_FRAGMENT = """
#version 330
uniform sampler2D u_scene;
uniform sampler2D u_ui;
uniform vec2 u_screen;
uniform int u_has_ui;
in vec2 v_px;
out vec4 f_color;
void main() {
    vec2 uv = v_px / u_screen;
    vec3 c = texture(u_scene, vec2(uv.x, 1.0 - uv.y)).rgb;
    if (u_has_ui == 1) {
        vec4 ui = texture(u_ui, uv);
        c = mix(c, ui.rgb, ui.a);
    }
    f_color = vec4(c, 1.0);
}
"""

BUILTIN_MODES = {"grayscale": 1, "sepia": 2, "invert": 3, "wave": 4, "crt": 5, "pixelate": 6}


class EffectChain:
    """Runs the environment's passes; ``render(world, target, ...)`` returns the number of draw calls."""

    def __init__(self, ctx, size):
        import moderngl

        self.gl = moderngl
        self.ctx = ctx
        self.size = (int(size[0]), int(size[1]))
        self.half = (max(1, self.size[0] // 2), max(1, self.size[1] // 2))
        self.environment = None
        self.ui = None  # UI layer texture for this frame (RGBA, straight alpha) or None
        self.normals = None  # normal layer texture or None (flat)
        self.time = 0.0
        self.errors = []
        self._programs = {}
        self._project_shaders = {}
        self._vbo = ctx.buffer(reserve=4 * 4 * 4 * 64, dynamic=True)
        self._flat = ctx.texture((1, 1), 4, bytes((128, 128, 255, 255)))
        self._black = ctx.texture((1, 1), 4, bytes((0, 0, 0, 255)))

        def target(size, dtype="f2"):
            texture = ctx.texture(size, 4, dtype=dtype)
            texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            texture.repeat_x = texture.repeat_y = False
            return texture, ctx.framebuffer(color_attachments=[texture])

        self.light_tex, self.light_fbo = target(self.half)
        self.shadow_tex, self.shadow_fbo = target(self.half)
        self.scene_tex, self.scene_fbo = target(self.size)
        self.bright_tex, self.bright_fbo = target(self.half)
        self.blur_tex, self.blur_fbo = target(self.half)
        self.graded_tex, self.graded_fbo = target(self.size, "f1")
        self.shaded_tex, self.shaded_fbo = target(self.size, "f1")

    # -- plumbing -------------------------------------------------------------------------------
    @property
    def active(self):
        return self.environment is not None and self.environment.active

    def _program(self, name, fragment):
        program = self._programs.get(name)
        if program is None:
            program = self._programs[name] = self.ctx.program(vertex_shader=VERTEX, fragment_shader=fragment)
        return program

    def _quad(self, program, points, size):
        """Draw a convex polygon given in pixel coordinates of a ``size`` target."""
        w, h = size
        data = array("f")
        for x, y in points:
            data.extend((x / w * 2 - 1, 1 - y / h * 2, x, y))
        self._vbo.orphan(len(data) * 4)
        self._vbo.write(data.tobytes())
        vao = self.ctx.vertex_array(program, [(self._vbo, "2f 2f", "in_pos", "in_px")])
        vao.render(self.gl.TRIANGLE_FAN, vertices=len(points))
        vao.release()

    def _fullscreen(self, program, fbo, size, **uniforms):
        fbo.use()
        self.ctx.viewport = (0, 0, *size)
        unit = 0
        for name, value in uniforms.items():
            if name not in program:
                continue
            if hasattr(value, "use"):  # texture
                value.use(unit)
                program[name] = unit
                unit += 1
            else:
                program[name] = value
        w, h = size
        self._quad(program, ((0, 0), (w, 0), (w, h), (0, h)), size)
        return 1

    def _set(self, program, **uniforms):
        unit = 0
        for name, value in uniforms.items():
            if name not in program:
                continue
            if hasattr(value, "use"):
                value.use(unit)
                program[name] = unit
                unit += 1
            else:
                program[name] = value

    # -- passes ---------------------------------------------------------------------------------
    def _light_map(self, env):
        calls = 0
        sx, sy = self.half[0] / self.size[0], self.half[1] / self.size[1]
        ambient = tuple(c * env.ambient.intensity for c in env.ambient.color)
        self.light_fbo.use()
        self.ctx.viewport = (0, 0, *self.half)
        self.light_fbo.clear(*ambient, 1.0)
        light = self._program("light", LIGHT_FRAGMENT)
        solid = self._program("solid", SOLID_FRAGMENT)
        copy = self._program("copy_fbo", COPY_FBO_FRAGMENT)
        normals = self.normals or self._flat
        for model, height, flicker in env.lights:
            scale = 1.0
            if flicker:
                scale = 1.0 - flicker * 0.5 * (1 + math.sin(self.time * 13.0 + hash(model.light_id) % 97))
            r = model.radius * sx
            cx, cy = model.x * sx, model.y * sy
            color = tuple(c * model.intensity * scale for c in model.color)
            target = self.shadow_fbo if model.casts_shadow and env.casters else self.light_fbo
            target.use()
            self.ctx.viewport = (0, 0, *self.half)
            if target is self.shadow_fbo:
                self.shadow_fbo.clear(0, 0, 0, 1)
            self.ctx.enable(self.gl.BLEND)
            self.ctx.blend_func = self.gl.ONE, self.gl.ONE
            self._set(
                light,
                u_screen=self.half,
                u_center=(cx, cy),
                u_radius=max(r, 1.0),
                u_height=height * sx,
                u_color=color,
                u_normals=normals,
            )
            self._quad(light, ((cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)), self.half)
            calls += 1
            if target is self.shadow_fbo:
                self.ctx.blend_func = self.gl.ZERO, self.gl.ZERO  # occluded: light becomes zero
                self._set(solid, u_color=(0.0, 0.0, 0.0, 1.0))
                for caster in env.casters:
                    pts = [(x * sx, y * sy) for x, y in caster.points]
                    for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
                        far = 4.0 * max(self.half)

                        def away(p, far=far, cx=cx, cy=cy):
                            dx, dy = p[0] - cx, p[1] - cy
                            n = math.hypot(dx, dy) or 1.0
                            return (p[0] + dx / n * far, p[1] + dy / n * far)

                        self._quad(solid, (a, b, away(b), away(a)), self.half)
                        calls += 1
                self.ctx.blend_func = self.gl.ONE, self.gl.ONE
                calls += self._fullscreen(copy, self.light_fbo, self.half, u_src=self.shadow_tex, u_screen=self.half)
            self.ctx.disable(self.gl.BLEND)
        return calls

    def render(self, world, target):
        env = self.environment
        calls = 0
        self.ctx.disable(self.gl.BLEND)
        if env.lighting:
            calls += self._light_map(env)
        fog = env.fog.density if env.fog is not None else 0.0
        fog_color = env.fog.color if env.fog is not None else (0.0, 0.0, 0.0)
        scene_program = self._program("scene", SCENE_FRAGMENT)
        waters = list(env.water)[:8]
        if "u_water_count" in scene_program:
            scene_program["u_water_count"] = len(waters)
            pad = [(0.0, 0.0, 0.0, 0.0)] * (8 - len(waters))
            if "u_water_rect" in scene_program:
                scene_program["u_water_rect"] = [tuple(w[:4]) for w in waters] + pad
                scene_program["u_water_wave"] = [(w[4], max(w[5], 1.0), w[6], w[8]) for w in waters] + pad
                scene_program["u_water_tint"] = [tuple(w[7]) for w in waters] + [(0.0, 0.0, 0.0)] * (8 - len(waters))
        calls += self._fullscreen(
            scene_program,
            self.scene_fbo,
            self.size,
            u_world=world,
            u_light=self.light_tex,
            u_screen=self.size,
            u_lighting=1 if env.lighting else 0,
            u_fog=fog,
            u_fog_color=fog_color,
            u_time=self.time,
            u_drift=env.fog_drift,
        )
        bloom = env.post_effect("bloom")
        bloom_tex, bloom_intensity = self._black, 0.0
        if bloom is not None:
            p = dict(bloom.parameters)
            calls += self._fullscreen(
                self._program("bright", BRIGHT_FRAGMENT),
                self.bright_fbo,
                self.half,
                u_src=self.scene_tex,
                u_screen=self.half,
                u_threshold=p.get("threshold", 0.75),
            )
            blur = self._program("blur", BLUR_FRAGMENT)
            for _ in range(2):
                calls += self._fullscreen(
                    blur, self.blur_fbo, self.half, u_src=self.bright_tex, u_screen=self.half, u_dir=(1.0, 0.0)
                )
                calls += self._fullscreen(
                    blur, self.bright_fbo, self.half, u_src=self.blur_tex, u_screen=self.half, u_dir=(0.0, 1.0)
                )
            bloom_tex, bloom_intensity = self.bright_tex, p.get("intensity", 0.8)
        grade = dict(env.post_effect("grade").parameters) if env.post_effect("grade") else {}
        vignette = (
            dict(env.post_effect("vignette").parameters).get("amount", 0.0) if env.post_effect("vignette") else 0.0
        )
        calls += self._fullscreen(
            self._program("grade", GRADE_FRAGMENT),
            self.graded_fbo,
            self.size,
            u_scene=self.scene_tex,
            u_bloom=bloom_tex,
            u_screen=self.size,
            u_bloom_intensity=bloom_intensity,
            u_exposure=grade.get("exposure", 1.0),
            u_contrast=grade.get("contrast", 1.0),
            u_saturation=grade.get("saturation", 1.0),
            u_tint=(grade.get("tint_r", 1.0), grade.get("tint_g", 1.0), grade.get("tint_b", 1.0)),
            u_vignette=vignette,
        )
        result = self.graded_tex
        shader = env.post_effect("screen_shader")
        if shader is not None:
            strength = dict(shader.parameters).get("strength", 1.0)
            program = self._screen_program(env)
            if program is not None:
                calls += self._fullscreen(
                    program,
                    self.shaded_fbo,
                    self.size,
                    u_src=self.graded_tex,
                    u_screen=self.size,
                    u_mode=BUILTIN_MODES.get(env.shader_id, 0),
                    u_strength=strength,
                    u_time=self.time,
                )
                result = self.shaded_tex
        calls += self._fullscreen(
            self._program("ui", UI_FRAGMENT),
            target,
            target.size,
            u_scene=result,
            u_ui=self.ui or self._black,
            u_screen=target.size,
            u_has_ui=1 if self.ui is not None else 0,
        )
        return calls

    def _screen_program(self, env):
        if env.shader_id in BUILTIN_MODES:
            return self._program("builtin_shader", BUILTIN_SHADER)
        if env.shader_source is None:
            return None
        key = env.shader_id
        if key not in self._project_shaders:
            try:
                self._project_shaders[key] = self.ctx.program(
                    vertex_shader=VERTEX,
                    fragment_shader=PROJECT_SHADER_HEADER + env.shader_source + PROJECT_SHADER_FOOTER,
                )
            except Exception as exc:  # noqa: BLE001 - GLSL compile/link errors: report, keep playing
                self.errors.append(f"{key}: {exc}")
                self._project_shaders[key] = None
        return self._project_shaders[key]

    def release(self):
        for item in (
            *self._programs.values(),
            *(p for p in self._project_shaders.values() if p is not None),
            self._vbo,
            self._flat,
            self._black,
            self.light_tex,
            self.light_fbo,
            self.shadow_tex,
            self.shadow_fbo,
            self.scene_tex,
            self.scene_fbo,
            self.bright_tex,
            self.bright_fbo,
            self.blur_tex,
            self.blur_fbo,
            self.graded_tex,
            self.graded_fbo,
            self.shaded_tex,
            self.shaded_fbo,
        ):
            try:
                item.release()
            except Exception:  # noqa: BLE001
                pass
