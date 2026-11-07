"""The map's entities as the story changes them: spawning, copying, morphing, routes, icons,
balloons, movement, visibility and positions."""

from __future__ import annotations

from math import hypot

from asteria.core import Entity, Transform, world_position
from asteria.core.prefab import instantiate
from asteria.core.serialization import deserialize_component, serialize_component
from asteria.runtime.session.support import (
    GameSessionError,
)


class FieldEntitiesMixin:
    """The map's entities as the story changes them: spawning, copying, morphing, routes, icons,"""

    def spawn_prefab(self, prefab_id, x, y, *, name=None):
        """Create an entity from a project prefab at ``(x, y)`` in the present scene (an event
        spawner); returns the new entity's id."""
        from asteria.runtime.preview import build_preview_registry

        if str(prefab_id) not in self.project.prefabs.ids():
            raise GameSessionError(f"unknown prefab: {prefab_id}")
        entity = instantiate(
            self.project.prefabs, str(prefab_id), build_preview_registry(), name=name
        )
        if not entity.has(Transform):
            entity.add_component(Transform())
        transform = entity.get(Transform)
        transform.x, transform.y = float(x), float(y)
        self.scene.add_entity(entity)
        return entity.id

    def copy_entity(self, entity_key, x, y, *, name=None):
        """A copy of a scene entity (every serialisable component) placed at ``(x, y)``."""
        from asteria.runtime.preview import build_preview_registry

        source = self._sequence_entity(entity_key)
        registry = build_preview_registry()
        entity = Entity(name or source.name)
        for component in source.components():
            entity.add_component(deserialize_component(serialize_component(component), registry))
        transform = entity.get(Transform)
        transform.x, transform.y = float(x), float(y)
        self.scene.add_entity(entity)
        return entity.id

    def morph_entity(self, entity_key, prefab_id):
        """Replace an entity by a prefab instance standing where it stood (an event morph);
        returns the new entity's id."""
        source = self._sequence_entity(entity_key)
        if source is self.player:
            raise GameSessionError("the player entity cannot be morphed")
        transform = source.get(Transform)
        new_id = self.spawn_prefab(prefab_id, transform.x, transform.y, name=source.name)
        self.scene.remove_entity(source)
        return new_id

    def click_entity(self, world_x, world_y):
        """A mouse click in the field: the nearest entity whose interaction is ``click``-triggered
        and whose ``range`` reaches the point starts its event program. Returns the trigger or
        ``None``."""

        from asteria.runtime.field.interaction import InteractionTrigger
        from asteria.runtime.scene.components import Interaction2DComponent

        if self.mode != "field" or self.event_busy:
            return None
        best = None
        for entity in self.scene.entities():
            if entity is self.player or not entity.enabled:
                continue
            interaction = entity.try_get(Interaction2DComponent)
            if (
                interaction is None
                or not interaction.enabled
                or not interaction.event_program_id
                or interaction.trigger != "click"
                or not entity.has(Transform)
            ):
                continue
            ex, ey = world_position(entity)
            distance = hypot(ex - float(world_x), ey - float(world_y))
            if distance <= interaction.range and (best is None or distance < best[0]):
                best = (distance, entity, interaction)
        if best is None:
            return None
        _distance, entity, interaction = best
        trigger = InteractionTrigger(
            entity.id, interaction.event_program_id, interaction.local_scope_id or entity.id
        )
        self.events.start_trigger(trigger, replace=True)
        self.update_events(0.0)
        return trigger

    def move_route(self, entity_key, route, *, step=32.0, speed=60.0):
        """Walk an entity along a relative route such as ``"up 3, left 2"`` (steps of ``step``
        pixels, in a straight line - no pathfinding). Arrival turns on the switch
        ``walk.<entity id>.done`` like ``walk_to``. Returns the waypoints."""
        from asteria.runtime.field.navigation import PathFollower

        entity = self._sequence_entity(entity_key)
        transform = entity.get(Transform)
        x, y, waypoints = transform.x, transform.y, []
        for part in str(route).replace(";", ",").split(","):
            words = part.split()
            if not words:
                continue
            direction = self.ROUTE_DIRECTIONS.get(words[0].lower())
            if direction is None:
                raise GameSessionError(f"unknown route direction: {words[0]}")
            try:
                count = float(words[1]) if len(words) > 1 else 1.0
            except ValueError as exc:
                raise GameSessionError(f"bad route step count: {words[1]}") from exc
            x += direction[0] * count * float(step)
            y += direction[1] * count * float(step)
            waypoints.append((x, y))
        done = f"walk.{entity.id}.done"
        if not waypoints:
            self.save.event_context.set_switch(done, True)
            return []
        self.save.event_context.set_switch(done, False)
        self.walkers[entity.id] = PathFollower(waypoints, float(speed))
        return waypoints

    def set_entity_icon(self, entity_key, icon_id=""):
        """Keep an icon over an entity (a quest marker, a status of an NPC) until it is cleared
        with an empty ``icon_id``; saved with the event variables as ``icon.<entity id>``."""
        entity = self._sequence_entity(entity_key)
        key = f"{self.ENTITY_ICON_PREFIX}{entity.id}"
        self.save.event_context.set_variable(key, str(icon_id or ""))
        return entity.id

    def entity_icons(self):
        """``{entity id: icon id}`` of the icons now shown in the present scene."""
        prefix = self.ENTITY_ICON_PREFIX
        icons = {}
        for key, value in self.save.event_context.variables.items():
            if key.startswith(prefix) and value:
                entity = self.scene.get_entity(key[len(prefix) :])
                if entity is not None:
                    icons[entity.id] = str(value)
        return icons

    def show_balloon(self, entity_key, balloon="exclamation", *, duration_ms=1000.0):
        """A balloon over an entity (a short popup with the balloon's glyph)."""
        glyph = self.BALLOONS.get(str(balloon).lower(), str(balloon))
        self.notify(glyph, entity=entity_key, duration_ms=float(duration_ms), kind="balloon")

    def _advance_walkers(self, dt):
        for entity_id in tuple(self.walkers):
            entity = self.scene.get_entity(entity_id)
            follower = self.walkers[entity_id]
            if entity is None or not entity.has(Transform):
                del self.walkers[entity_id]
                continue
            transform = entity.get(Transform)
            transform.x, transform.y = follower.step(transform.x, transform.y, dt)
            if follower.done:
                del self.walkers[entity_id]
                self.save.event_context.set_switch(f"walk.{entity_id}.done", True)

    def _map_rules_ready(self):
        """Map rules bound to the scene the player is in (just after a transfer the new
        scene's tiles are not bound yet: the old rules must not read the new position)."""
        return (
            self.map_rules is not None
            and getattr(self, "_map_rules_scene", self.scene.id) == self.scene.id
        )

    def can_meet_wild(self):
        """Random encounters need someone to fight them: when creatures decide a battle, a
        standing creature in the party."""
        rules = self.pet_rules
        if rules is None or not rules.pets_decide_outcome:
            return True
        return any(self.pet_standing(pet) for pet in self.battle_pets())

    def step_arrived(self):
        """The player finished a step (a grid cell): roll the area's random encounter.
        Returns the encounter id started, or None."""
        if self.mode != "field" or self.event_busy or not self._map_rules_ready():
            return None
        self.map_rules.update(0.0)  # the areas of the cell just reached
        if not self.can_meet_wild():
            return None
        encounter_id = self.map_rules.roll_encounter(self._step_rng)
        if not encounter_id:
            return None
        self.start_encounter(encounter_id)
        return encounter_id

    def respawn_after_defeat(self):
        """The battle rules' ``defeat: respawn``: the party is healed, a share of the money is
        lost, the player goes back to the last respawn point (``SET_RESPAWN``, else where the
        game started) and the rules' ``defeat_event`` runs. Returns the money lost."""
        rules = self.rules
        self.battle = None
        self.mode = "field"
        self.events.stop()  # the event that led to the battle ends with it
        self.heal_pets()
        lost = 0.0
        currencies = self.save.rpg_state.currencies
        currency = rules.defeat_currency
        if currency and rules.defeat_currency_loss:
            have = currencies.get(currency, 0.0)
            lost = float(int(have * rules.defeat_currency_loss))
            currencies[currency] = have - lost
        point = self.save.event_context.get_variable(self.RESPAWN_VARIABLE)
        if point:
            scene_id, x, y, facing = str(point).split("|")
            x, y = float(x), float(y)
        else:
            start = self.project.game_start
            x, y = start.player_position or (None, None)
            scene_id, facing = start.scene_id or self.project.startup_scene_id, start.player_facing
        self.transfer_player(scene_id, x, y, facing=facing)
        if rules.defeat_event:
            self.events.start(rules.defeat_event)
            self.update_events(0.0)
        return lost

    def grid_route(self, entity_key, steps):
        """Walk ``entity_key`` (``"player"`` or an entity) along ``steps`` (see
        ``grid_actors.parse_step``); the switch ``route.<entity id>.done`` turns on when it is
        over, and ``route.all.done`` while no route runs. Returns the entity id."""
        entity = self._sequence_entity(entity_key)
        self.routes.start(entity.id, list(steps))
        if entity is self.player:
            self.player_story_moves += 1  # a step the player had begun is dropped
        switches = self.save.event_context
        names = {entity.id, entity.name} | ({"player"} if entity is self.player else set())
        self._route_names[entity.id] = names  # route.<id>, route.<name> and route.player
        for name in names:
            switches.set_switch(f"route.{name}.done", False)
        switches.set_switch("route.all.done", False)
        return entity.id

    def set_entity_movement(self, entity_key, behaviour="", facing=""):
        """Change how a grid character moves (``GRID_BEHAVIOURS``) and / or the way it faces;
        it starts again from where it stands."""
        from asteria.runtime.field.grid_actors import (
            FACINGS,
            GRID_BEHAVIOURS,
            GridMover2DComponent,
        )

        entity = self._sequence_entity(entity_key)
        mover = entity.try_get(GridMover2DComponent)
        if mover is None:
            raise GameSessionError(f"SET_MOVEMENT: {entity.name} is not a grid character")
        if behaviour:
            if behaviour not in GRID_BEHAVIOURS:
                raise GameSessionError(f"SET_MOVEMENT: unknown behaviour {behaviour}")
            mover.behaviour = behaviour
        if facing:
            if facing not in FACINGS:
                raise GameSessionError(f"SET_MOVEMENT: unknown facing {facing}")
            mover.facing = facing
        system = self._grid_movers.get(self.scene.id)
        if system is not None:
            system.state.pop(entity.id, None)
        return entity.id

    def show_entity(self, entity_key, shown=True):
        """Show or hide an entity: one with ``SwitchVisibility2D`` turns its switch (so it stays
        so), any other is hidden until shown or the scene changes."""
        from asteria.runtime.field.grid_actors import SwitchVisibility2DComponent

        entity = self._sequence_entity(entity_key)
        spec = entity.try_get(SwitchVisibility2DComponent)
        if spec is not None and spec.hidden_switch:
            self.save.event_context.set_switch(spec.hidden_switch, not shown)
        else:
            (self.route_hidden.discard if shown else self.route_hidden.add)(entity.id)
        return entity.id

    def set_entity_position(self, entity_key, x, y, *, facing=None, permanent=False):
        """Put an entity on ``(x, y)`` (``None``: where it is on that axis); ``permanent``
        keeps it there whenever its scene loads (saved as ``pos.<entity id>``)."""
        entity = self._sequence_entity(entity_key)
        transform = entity.get(Transform)
        x = transform.x if x is None else float(x)
        y = transform.y if y is None else float(y)
        transform.x, transform.y = x, y
        if entity is self.player:
            self.save.player_position = (transform.x, transform.y)
            self.player_story_moves += 1
            if facing:
                self.set_player_facing(facing)
        else:
            from asteria.runtime.field.grid_actors import GridMover2DComponent

            mover = entity.try_get(GridMover2DComponent)
            if mover is not None and facing:
                mover.facing = str(facing)
            system = self._grid_movers.get(self.scene.id)
            if system is not None:
                system.state.pop(entity.id, None)  # it starts again from its new cell
        if permanent:
            self.save.event_context.set_variable(
                f"{self.POSITION_PREFIX}{entity.id}", f"{float(x)}|{float(y)}|{facing or ''}"
            )
        return entity.id
