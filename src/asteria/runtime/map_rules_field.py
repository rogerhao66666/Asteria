"""Map area rules in the field: area keys from a tile map, and the session-side effects.

``tile_area_keys`` reads ``region:<id>`` from the map's region layer and ``tag:<name>`` from the
tags of the tiles under a point. ``FieldMapRules`` feeds the player's movement to a
``MapRulesRuntime`` and applies what comes back: floor damage to the party, footstep sound
requests, event programs, a sliding player, restricted tiles for the player and field enemies,
the stealth scale of enemy sight, the area's music and name, and random encounters on a step.
"""

from __future__ import annotations

from math import hypot

from asteria.core import Transform
from asteria.events.world_commands import WorldCommand
from asteria.graphics import EMPTY_TILE
from asteria.runtime.tilequery import TileMapQuery

CROUCH_SWITCH = "stealth.crouch"


def tile_area_keys(tilemap, tileset, region_layer="regions"):
    """A ``keys_at(x, y)`` for ``MapRulesRuntime`` over ``tilemap`` / ``tileset``."""
    query = TileMapQuery(tilemap)

    def keys_at(x, y):
        tx, ty = query.world_to_tile(x, y)
        found = []
        for layer in tilemap.ordered_layers():
            tile = query.tile_at(layer, tx, ty)
            if tile == EMPTY_TILE:
                continue
            if layer.name == region_layer:
                found.append(f"region:{tile}")
                continue
            definition = tileset.tiles.get(tile) if tileset is not None else None
            if definition is not None:
                found.extend(f"tag:{tag}" for tag in definition.tags)
        return tuple(dict.fromkeys(found))

    return keys_at


class RegionBlockQuery:
    """A ``collides_world_point`` query that is true inside areas barring ``group``."""

    def __init__(self, runtime, group):
        self.runtime = runtime
        self.group = group

    def collides_world_point(self, x, y):
        return self.runtime.blocked(self.group, x, y)


class FieldMapRules:
    def __init__(self, session, runtime):
        self.session = session
        self.runtime = runtime
        self._base_sight = {}  # entity id -> (detect_radius, lose_radius) as authored
        self._last = None

    def block_query(self, group):
        return RegionBlockQuery(self.runtime, group)

    def update(self, dt):
        """Run the rules for the player's present position (call once per field frame)."""
        session = self.session
        player = session.player
        transform = player.get(Transform)
        for event in self.runtime.advance(player.id, transform.x, transform.y, dt):
            self._dispatch(event)
        self._autorun(transform)
        moving = self._last is None or (
            hypot(transform.x - self._last[0], transform.y - self._last[1]) > 1e-6
        )
        self._last = (transform.x, transform.y)
        self._scale_enemy_sight(transform, moving)

    def shape_player_intent(self, controller):
        """Let a slippery floor carry the player on (sets the controller's intent)."""
        player = self.session.player
        transform = player.get(Transform)
        dx, dy = self.runtime.shape_movement(
            player.id, controller.intent_x, controller.intent_y, transform.x, transform.y
        )
        if (dx, dy) != (controller.intent_x, controller.intent_y):
            controller.set_intent(dx, dy, jump=controller.jump)

    def settled(self, dt, *, blocked=False):
        self.runtime.settle_slide(self.session.player.id, dt, blocked=blocked)

    # -- effects -------------------------------------------------------------------------------
    def _dispatch(self, event):
        session, rule = self.session, event.rule
        if event.kind == "damage":
            session.damage_party(rule.damage_resource, event.amount, can_kill=rule.can_kill)
            return
        if event.kind == "enter":
            if rule.music:
                session.area_music = rule.music  # the field plays it (a story track wins)
            if rule.title and rule.title != session.area_title_shown:
                session.area_title_shown = rule.title
                session.area_title_requests.append(rule.title)
        if event.kind == "footstep":
            session.presentation_requests.append(
                WorldCommand("PLAY_SE", {"asset_id": rule.footstep_cue})
            )
            return
        program = {"enter": rule.on_enter, "leave": rule.on_leave, "step": rule.on_step}[
            event.kind
        ]
        if program and not session.event_busy:
            session.events.start(program)
        elif program and event.kind == "enter":
            session.pending_area_programs.append(program)  # runs once the field is free
        if event.kind == "enter" and rule.autorun:
            context = session.save.event_context
            arrival = rule.autorun_program(context.get_switch, context.get_variable, "enter")
            if arrival:
                session.pending_area_programs.append(arrival)

    def _autorun(self, transform):
        """A queued area entry program, else an autorun program of an area the player is in."""
        session = self.session
        if session.event_busy:
            return
        if session.pending_area_programs:
            session.events.start(session.pending_area_programs.pop(0))
            return
        context = session.save.event_context
        for rule in self.runtime.rules_at(transform.x, transform.y):
            program = rule.autorun and rule.autorun_program(
                context.get_switch, context.get_variable
            )
            if program:
                session.events.start(program)
                return

    def roll_encounter(self, rng):
        """A step finished where the player stands: the encounter it starts, or ''."""
        transform = self.session.player.get(Transform)
        here = frozenset(r.key for r in self.runtime.rules_at(transform.x, transform.y))
        before, self._step_keys = getattr(self, "_step_keys", frozenset()), here
        return self.runtime.roll_encounter(transform.x, transform.y, rng, before)

    def _scale_enemy_sight(self, transform, moving):
        from asteria.runtime.field_ai import FieldAIComponent

        crouching = bool(self.session.save.event_context.get_switch(CROUCH_SWITCH))
        scale = self.runtime.visibility(
            transform.x, transform.y, crouching=crouching, moving=moving
        )
        self.session.sight_scale = scale  # behaviour-tree foes read it too
        for entity in self.session.scene.entities():
            spec = entity.try_get(FieldAIComponent)
            if spec is None:
                continue
            base = self._base_sight.setdefault(entity.id, (spec.detect_radius, spec.lose_radius))
            spec.detect_radius, spec.lose_radius = base[0] * scale, base[1] * scale
