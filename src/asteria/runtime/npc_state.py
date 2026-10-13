"""NPC state model (WLD-02, ASTERIA_SPEC §26): NPCs keep where they are and what happened to them.

``NpcIdentity2D`` marks a scene entity as the NPC ``npc_id``. Its saved state
(``WorldRecord.npcs``) holds scene, position, facing, visibility, alive, mood,
dialogue stage and free flags. The game session applies the state whenever a
scene is entered (hidden, dead or relocated NPCs are disabled; positions and
facing are restored) and records moves made by events and sequences.

Events change NPCs with ``SET_NPC`` (``npc``, ``key`` = visible / alive / mood /
stage / flag.<name>, ``value``) and ``MOVE_NPC`` (``npc``, ``scene_id``, ``x``, ``y``),
and test them with conditions on the ``npc`` source (``<npc_id>.<key>``).
"""

from __future__ import annotations

from asteria.core import Component, Field, Transform, component_schema

NPC_KEYS = ("visible", "alive", "mood", "stage")


@component_schema(
    type_name="asteria.NpcIdentity2D",
    version=1,
    fields=(
        Field(
            "npc_id", str, "", tooltip="Stable NPC id; its state is saved across scenes and loads."
        ),
    ),
)
class NpcIdentity2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.npc_id = ""


def npc_entities(scene):
    """``{npc_id: entity}`` for every NPC entity in ``scene`` (enabled or not)."""
    found = {}
    for entity in scene.entities():
        identity = entity.try_get(NpcIdentity2DComponent)
        if identity is not None and identity.npc_id:
            found[identity.npc_id] = entity
    return found


def apply_npc_states(scene, world, facing=None):
    """Make ``scene``'s NPC entities match their saved state; returns the npc ids applied."""
    applied = []
    for npc_id, entity in npc_entities(scene).items():
        state = world.npcs.get(npc_id)
        if state is None:
            continue
        here = state.get("scene_id") in (None, scene.id)
        entity.enabled = bool(here and state.get("visible", True) and state.get("alive", True))
        if here and state.get("position") is not None and entity.has(Transform):
            t = entity.get(Transform)
            t.x, t.y = (float(v) for v in state["position"])
        if facing is not None and state.get("facing"):
            facing[entity.id] = state["facing"]
        applied.append(npc_id)
    return applied


def coerce_npc_value(key, value):
    if key in ("visible", "alive"):
        return (
            value
            if isinstance(value, bool)
            else str(value).strip().lower() in ("1", "true", "yes", "on")
        )
    if key == "stage":
        return int(value)
    return value
