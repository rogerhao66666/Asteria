"""Characters that notice the player (SightTrigger2D): their sight lines, heights and reach."""

from __future__ import annotations

from asteria.core import Transform
from asteria.events.world_commands import WorldCommand


class FieldSightMixin:
    """Characters that notice the player (SightTrigger2D): their sight lines, heights and reach."""

    def check_sight(self):
        """A character with ``SightTrigger2D`` that sees the player standing in a clear line
        ahead of it notices them: its mark shows, its music plays, it walks up and then its
        interaction event starts. Returns the entity id, or None."""
        from asteria.runtime.field.grid_actors import (
            STEP,
            GridMover2DComponent,
            SightTrigger2DComponent,
            line_of_sight,
        )

        if self.mode != "field" or self.event_busy or not self.can_meet_wild():
            return None
        found = list(self.scene.query(SightTrigger2DComponent, Transform))
        if not found:
            return None
        switches = self.save.event_context.get_switch
        player = self.player.get(Transform)
        size = 16.0
        movers = self._grid_movers.get(self.scene.id)
        held = movers.held_cells() if movers is not None else set()
        tiles = self._tile_blocking.get(self.scene.id)
        for entity, sight, transform in found:
            if not entity.enabled or sight.range <= 0:
                continue
            if sight.done_switch and switches(sight.done_switch):
                continue
            mover = entity.try_get(GridMover2DComponent)
            if mover is not None:
                size = mover.grid_size
            own = (int(transform.x // size), int(transform.y // size))
            target = (int(player.x // size), int(player.y // size))
            facing = mover.facing if mover is not None else "down"
            ways = tuple(STEP) if sight.every_way else (facing,)

            def blocked(cell, own=own, size=size):
                if cell in held and cell != own:
                    return True
                centre = (cell[0] * size + size / 2, cell[1] * size + size / 2)
                return tiles is not None and tiles.collides_world_point(*centre)

            for facing in ways:
                between = line_of_sight(sight.range, facing, own, target, blocked)
                if between is not None:
                    break
            if between is None or self._sight_over_heights(entity, own, [*between, target]):
                continue
            if mover is not None:
                mover.facing = facing
            self.sighting = {"entity": entity.id, "phase": "emote", "time": 0.0}
            self.emotes[entity.id] = (sight.emote or "exclamation", self.SIGHT_EMOTE_SECONDS)
            if sight.music:
                self.presentation_requests.append(
                    WorldCommand("PLAY_BGM", {"asset_id": sight.music, "temporary": True})
                )
            return entity.id
        return None

    def _advance_sighting(self, dt):
        """The noticing character's mark, its walk up to the player, then its event."""
        from asteria.runtime.field.grid_actors import (
            STEP,
            GridMover2DComponent,
            SightTrigger2DComponent,
        )

        state = self.sighting
        entity = self.scene.get_entity(state["entity"])
        if entity is None:
            self.sighting = None
            return
        state["time"] += dt
        if state["phase"] == "emote":
            if state["time"] < self.SIGHT_EMOTE_SECONDS:
                return
            state["phase"], state["time"] = "reveal", 0.0
        sight = entity.get(SightTrigger2DComponent)
        if state["phase"] == "reveal":  # hidden until found: it shows itself, then comes
            context = self.save.event_context
            if sight.reveal_variable:
                if state["time"] < sight.reveal_seconds:
                    context.set_variable(sight.reveal_variable, 1)
                    return
                context.set_variable(sight.reveal_variable, 2)
            state["phase"] = "approach"
        mover_spec = entity.try_get(GridMover2DComponent)
        transform = entity.get(Transform)
        player = self.player.get(Transform)
        if state["phase"] == "approach" and sight.approach and mover_spec is not None:
            system = self.grid_movers()
            system.update(self.scene, 0.0, None, ())  # make sure it is known to the system
            mover = system.state[entity.id]
            if mover.target is not None:
                system._walk(mover_spec, mover, transform, dt)
                return
            size = mover_spec.grid_size
            own = (int(transform.x // size), int(transform.y // size))
            target = (int(player.x // size), int(player.y // size))
            ox, oy = STEP.get(mover_spec.facing, (0, 1))
            distance = (target[0] - own[0]) * ox + (target[1] - own[1]) * oy
            if distance > 1:
                mover.target = (own[0] + ox, own[1] + oy)
                return
        self.sighting = None
        if mover_spec is not None:  # the two face each other
            opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}
            self.set_player_facing(opposite.get(mover_spec.facing, self.facing))
        from asteria.runtime.field.interaction import InteractionTrigger
        from asteria.runtime.scene.components import Interaction2DComponent

        interaction = entity.try_get(Interaction2DComponent)
        if interaction is not None and interaction.event_program_id:
            self.events.start_trigger(
                InteractionTrigger(
                    entity.id,
                    interaction.event_program_id,
                    interaction.local_scope_id or entity.id,
                ),
                replace=True,
            )
            self.update_events(0.0)

    def _sight_over_heights(self, entity, own, cells):
        """Whether a change of height or a one-way edge stops a look along ``cells``."""
        heights = self.grid_heights()
        system = self._grid_movers.get(self.scene.id)
        mover = system.state.get(entity.id) if system is not None else None
        if heights is None or mover is None:
            return False
        last = own
        for cell in cells:
            if heights.stopped(last, cell, mover.height):
                return True
            last = cell
        return False

    def _out_of_reach(self, entity):
        from asteria.runtime.field.grid_heights import compatible

        system = self._grid_movers.get(self.scene.id)
        mover = system.state.get(entity.id) if system is not None else None
        return mover is not None and not compatible(mover.height, self.player_height)
