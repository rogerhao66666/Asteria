"""The boss intro camera, the battle log in the game's words, and the presentation timeline."""

from __future__ import annotations

import heapq

from asteria.rpg.text.data_text import key as data_key
from asteria.runtime.scene.camera import CameraDirector, CameraShot, clamp_center_to_bounds


class BattleTimelineMixin:
    """The boss intro camera, the battle log in the game's words, and the presentation timeline."""

    # defaults until something sets them (code may read them first)
    _intro_until = 0.0

    def _start_boss_intro(self, game, layout):
        """Encounters tagged "boss" open with the camera on the boss, then ease back to the whole
        field."""

        self.camera_director = CameraDirector()
        self._camera_center = (layout.virtual_width / 2, layout.virtual_height / 2)
        self._intro_until = 0.0
        settings = self.host.manifest.get("battle", {}).get("presentation", {})
        encounter = game.project.rpg_database.encounters.get(game.encounter_id)
        if not self.visuals_enabled or encounter is None or "boss" not in encounter.tags:
            return
        if settings.get("boss_intro", True) is False:
            return
        bosses = [
            m.member_id
            for m in game.battle.parties.get("enemies", ()).members
            if "boss" in getattr(game.foe_definition(m.member_id.split(":", 1)[0]), "tags", ())
        ]
        if not bosses:
            return
        visual = self.screen.scene.visual_for(bosses[0])
        height = self.screen.member_heights.get(bosses[0], 0.0)
        intro = (
            {**self.BOSS_INTRO, **dict(settings.get("boss_intro") or {})}
            if isinstance(settings.get("boss_intro"), dict)
            else self.BOSS_INTRO
        )
        shot = CameraShot(
            visual.anchor.x, visual.anchor.y - height * 0.5, zoom=float(intro["zoom"])
        )
        self.camera_director.update(0.0, (*self._camera_center, 1.0))
        self.camera_director.focus(shot, blend=float(intro["blend"]))
        release_at = float(intro["blend"]) + float(intro["hold"])
        self._intro_until = release_at + float(intro["blend"])
        self.intro_boss_id = bosses[0]
        self._at(release_at, lambda: self.camera_director.release(blend=float(intro["blend"])))

    def _clamped_view(self, director, view):
        """Keep a zoomed battle camera inside the battlefield so the background always covers the
        screen."""

        layout = self.screen.composer.layout
        width, height = layout.virtual_width, layout.virtual_height
        x, y, zoom = view
        sx, sy = director.shake_offset
        x, y = clamp_center_to_bounds(
            x - sx, y - sy, width / zoom, height / zoom, (0.0, 0.0, width, height)
        )
        return (x + sx, y + sy, zoom)

    @staticmethod
    def _state_label(game):
        """The battle HUD's status labels in the player's language: the state's translated
        name (``data.state.<id>.name``) when the table has one, else the HUD style's label."""
        lookup = game.data_lookup
        if lookup is None:
            return None

        return lambda state_id, label: lookup(data_key("state", state_id)) or label

    @staticmethod
    def _display_names(game):
        """Member id -> project display name; repeated enemy kinds get their index."""
        db = game.project.rpg_database
        names = {}
        member_ids = [m.member_id for party in game.battle.parties.values() for m in party.members]
        kinds = {}
        for member_id in member_ids:
            base = member_id.split(":", 1)[0]
            kinds[base] = kinds.get(base, 0) + 1
        for member_id in member_ids:
            base, _, index = member_id.partition(":")
            if base == "pet" and game.pet_name(index):  # a pet unit: its nickname or species
                names[member_id] = game.pet_name(index)
                continue
            definition = db.actors.get(member_id) or game.foe_definition(base)
            name = game.name_of(definition) or member_id
            if index and kinds[base] > 1:
                name = f"{name} {index}"
            names[member_id] = name
        return names

    def _at(self, time, step):
        # ``_schedule`` is a heap of (time, order, step); ``order`` is unique, so steps are
        # never compared and due steps come out by time, then by when they were queued.
        self._order += 1
        heapq.heappush(self._schedule, (max(time, self._clock), self._order, step))

    def _release_due(self):
        # Take every step due now before running any: steps queued while these run wait for
        # the next release, as before.
        limit = self._clock + 1e-9
        schedule = self._schedule
        due = []
        while schedule and schedule[0][0] <= limit:
            due.append(heapq.heappop(schedule))
        for _, _, step in due:
            step()
        self._flush()

    def _flush(self):
        events = self.screen.coordinator.drain()
        if events:
            self.trace.extend(self._semantics_from_events(events))
            self.screen.consume_events(events)

    def busy(self):
        """True while queued action choreography (or the boss intro) has not finished playing."""
        if self.screen is None:
            return False
        intro = self._clock < self._intro_until - 1e-9
        return intro or bool(self._schedule) or self._clock < self._cursor - 1e-9

    def particle_count(self):
        return 0 if self.screen is None else len(self.screen.feedback.vfx)
