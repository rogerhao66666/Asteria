"""Blender side of the KayKit art build: photograph a rigged character into 2D frames.

Run by ``scripts/build_kaykit_art.py`` (never by hand, normally)::

    Blender -b --factory-startup -noaudio --python scripts/kaykit_render_blender.py \
        -- <job.json> <out dir>

The job names the character (.glb), the props it holds (gltf + bone), the animation files,
the clips to sample (``action``, ``frames``) and the views to shoot from (``yaw``, ``pitch``,
``size``). Every frame is written as ``<view>_<clip>_<nn>.png`` with a transparent
background. The camera is orthographic and never moves: the figure turns on a pivot.

Things learned the hard way (KayKit 2.0 / Character Animations 1.1, Blender 5.2):
- import with ``bone_heuristic="BLENDER"`` and delete the stray ``Icosphere`` mesh;
- the animation files carry *slotted* actions: assign ``action_slot`` after ``action``;
- a prop follows ``handslot.r`` / ``handslot.l`` through a Child Of constraint with an
  identity inverse, turned -90 degrees about X (the mesh was converted to Z-up, the bone
  frame was not);
- yaw 0 shows the left profile; yaw 90 faces the camera.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ARGS = sys.argv[sys.argv.index("--") + 1 :]
JOB = json.loads(Path(ARGS[0]).read_text(encoding="utf-8"))
OUT = Path(ARGS[1])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def imported(path, **kw):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path), **kw)
    return [o for o in bpy.data.objects if o not in before]


def without_helpers(objects):
    kept = []
    for o in objects:
        if o.type == "MESH" and o.name.startswith("Icosphere"):
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            kept.append(o)
    return kept


body = without_helpers(imported(JOB["character"], bone_heuristic="BLENDER"))
armature = next(o for o in body if o.type == "ARMATURE")

actions = {}
for path in JOB["animations"]:
    before = set(bpy.data.actions)
    for o in imported(path, bone_heuristic="BLENDER"):
        bpy.data.objects.remove(o, do_unlink=True)
    for action in bpy.data.actions:
        if action not in before:
            action.use_fake_user = True
            actions.setdefault(action.name, action)


for prop in JOB.get("props", ()):
    objects = without_helpers(imported(prop["asset"]))
    mesh = next(o for o in objects if o.type == "MESH")
    mesh.matrix_world = Matrix.Rotation(math.radians(prop.get("tilt", -90.0)), 4, "X")
    constraint = mesh.constraints.new("CHILD_OF")
    constraint.target, constraint.subtarget = armature, prop["bone"]
    constraint.inverse_matrix = Matrix.Identity(4)


def toon(bands):
    """Cartoon shading: every material's colour times a stepped light level (``bands``:
    ``[[position, level], ...]`` over the diffuse brightness), emitted flat - no soft
    gradients, so a small picture keeps a few clean tones like hand-drawn pixel art."""
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        nodes, links = material.node_tree.nodes, material.node_tree.links
        texture = next((n for n in nodes if n.type == "TEX_IMAGE"), None)
        principled = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        output = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
        if output is None:
            continue
        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        to_rgb = nodes.new("ShaderNodeShaderToRGB")
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        elements = ramp.color_ramp.elements
        while len(elements) < len(bands):
            elements.new(0.5)
        for element, (position, level) in zip(elements, bands, strict=False):
            element.position = float(position)
            element.color = (level, level, level, 1.0)
        mix = nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        emission = nodes.new("ShaderNodeEmission")
        links.new(diffuse.outputs["BSDF"], to_rgb.inputs["Shader"])
        links.new(to_rgb.outputs["Color"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], mix.inputs[6])
        if texture is not None:
            links.new(texture.outputs["Color"], mix.inputs[7])
        elif principled is not None:
            mix.inputs[7].default_value = principled.inputs["Base Color"].default_value
        links.new(mix.outputs[2], emission.inputs["Color"])
        links.new(emission.outputs["Emission"], output.inputs["Surface"])


if JOB.get("style") == "toon":
    toon(JOB.get("bands") or [[0.0, 0.62], [0.32, 0.82], [0.62, 1.0]])


def play(action_name, frame):
    data = armature.animation_data or armature.animation_data_create()
    action = actions[action_name]
    data.action = action
    if hasattr(data, "action_slot") and data.action_slot is None and action.slots:
        data.action_slot = action.slots[0]
    scene.frame_set(int(frame), subframe=frame - int(frame))


pivot = bpy.data.objects.new("pivot", None)
scene.collection.objects.link(pivot)
armature.parent = pivot

camera_data = bpy.data.cameras.new("camera")
camera_data.type = "ORTHO"
camera = bpy.data.objects.new("camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

for name, energy, rotation in (("key", 3.0, (50, 0, 60)), ("fill", 1.0, (60, 0, -120))):
    light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
    scene.collection.objects.link(light)
    light.data.energy = energy
    light.rotation_euler = tuple(math.radians(v) for v in rotation)
world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.62, 0.7, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9

scene.render.engine = "BLENDER_EEVEE"
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
OUT.mkdir(parents=True, exist_ok=True)


def aim(view):
    """Point the fixed camera: ``pitch`` degrees down from the horizon, ``ortho`` units wide."""
    pitch = math.radians(float(view.get("pitch", 12.0)))
    distance = 20.0
    camera.location = (distance * math.cos(pitch), 0.0, 1.0 + distance * math.sin(pitch))
    camera.rotation_euler = (math.radians(90) - pitch, 0.0, math.radians(90))
    camera_data.ortho_scale = float(view.get("ortho", 4.2))
    camera_data.shift_y = float(view.get("shift_y", 0.08))
    size = int(view.get("size", 384))
    scene.render.resolution_x = scene.render.resolution_y = size
    pivot.rotation_euler = (0.0, 0.0, math.radians(float(view.get("yaw", 0.0))))


count = 0
for view in JOB["views"]:
    aim(view)
    wanted = set(view.get("clips") or [c["name"] for c in JOB["clips"]])
    for clip in JOB["clips"]:
        if clip["name"] not in wanted:
            continue
        start, end = actions[clip["action"]].frame_range
        frames = int(clip["frames"])
        # a one-shot clip ends on its last pose; a loop stops one step short of its start
        span = frames - 1 if clip.get("hold_last") else frames
        for index in range(frames):
            play(clip["action"], start + (end - start) * index / max(1, span))
            scene.render.filepath = str(OUT / f"{view['name']}_{clip['name']}_{index:02d}.png")
            bpy.ops.render.render(write_still=True)
            count += 1
print(f"KAYKIT RENDER DONE {count} frames -> {OUT}")
