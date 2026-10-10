"""Battle presentation adapters for the playable runtime (CB2, incremental).

Both adapters consume the same canonical ``BattleLogEntry`` stream produced by
``GameSessionRuntime``; neither decides any battle rule. ``LegacyPygameBattle
Adapter`` keeps the original hand-drawn pygame screen. ``CanonicalBattle
Adapter`` routes the log through ``BattleScreenRuntime`` (HUD, turn timeline,
action menu, value popups, camera feedback, result) and renders it with
``PygameBattleUiBackend``. Combatant sprites come from authored combatant
visuals when a project provides them; until then the legacy world layer is
drawn underneath.

``entry_semantics`` is the comparison contract for behaviour parity tests:
each adapter records, in ``trace``, what it understood from the log.
"""
from __future__ import annotations

from typing import Protocol

from asteria.gameplay import ActionCue, ActionCueKind, PresentationCue
from asteria.presentation import (
    BattlePresentationEventKind,
    BattlePresentationScene,
    BattleScreenRuntime,
    BattleUiRenderer,
)
from asteria.presentation.battle_action_menu import BattleActionEntry
from dataclasses import replace

from asteria.rpg import BattleOutcome
from asteria.runtime.battle_visuals import BattleVisualError, BattleVisualResolver
from asteria.runtime.camera import Camera2D

CHANNEL_KINDS = {
    "animation": ActionCueKind.ANIMATION, "vfx": ActionCueKind.VFX, "audio": ActionCueKind.AUDIO,
    "camera": ActionCueKind.CAMERA, "screen_fx": ActionCueKind.SCREEN_FX,
}

PRESENTATION_PROFILE_CATEGORIES = {
    "feedback_profile": "feedback",
    "hud_profile": "hud",
    "result_profile": "results",
    "layout": "ui_layout",
    "party_layout": "party_layout",
    "action_menu_policy": "action_menu",
    "director_profile": "director",
    "animation_timing_profile": "animation_timing",
    "layering_profile": "layering",
    "ui_polish_profile": "ui_polish",
}


def _value(outcome):
    value = getattr(outcome, "value", None)
    return round(float(getattr(value, "resolved_value", 0.0)), 6)


def entry_semantics(entry):
    """Rule-relevant meaning of one battle log entry, for parity comparison."""
    if entry.kind == "action":
        return (
            "action", entry.member_id, entry.ability_id, tuple(entry.target_ids),
            tuple((t, _value(o), tuple(sorted(getattr(o, "outcome_tags", ())))) for t, o in entry.outcomes),
        )
    if entry.kind == "turn":
        return ("turn", entry.member_id)
    if entry.kind == "gauge":
        return ("gauge", entry.member_id, entry.data.composition_id,
                tuple(x.threshold_id for x in entry.data.thresholds))
    if entry.kind == "battle_finished":
        return ("battle_finished", tuple(entry.data["winning_sides"]))
    return (entry.kind,)


class BattlePresentationAdapter(Protocol):
    name: str
    trace: list

    def begin(self) -> None: ...
    def consume(self, entries) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self) -> None: ...


class LegacyPygameBattleAdapter:
    """The original pygame battle screen, unchanged, behind the adapter interface."""

    name = "legacy"

    def __init__(self, host):
        self.host = host
        self.trace = []

    def begin(self):
        self.trace.clear()

    def consume(self, entries):
        self.trace.extend(entry_semantics(e) for e in entries)

    def update(self, dt):
        pass

    def draw(self):
        self.host._draw_battle_world()
        self.host._draw_battle_hud()


class PygameTextureDrawer:
    """Draws ``TextureDraw`` commands (virtual coordinates) onto the host's pygame screen."""

    def __init__(self, host, resolver, scale):
        self.host = host
        self.resolver = resolver
        self.scale = float(scale)
        self.draw_count = 0

    def surface(self, asset_id):
        return self.host.load_image(self.resolver.source_uri(asset_id))

    def blit_region(self, asset_id, source, x, y, width, height, *, flip_x=False, opacity=1.0):
        pg = self.host.pg
        image = self.surface(asset_id).subsurface(pg.Rect(*source))
        size = (max(1, round(width * self.scale)), max(1, round(height * self.scale)))
        if image.get_size() != size:
            image = pg.transform.scale(image, size)
        if flip_x:
            image = pg.transform.flip(image, True, False)
        if opacity < 1.0:
            image = image.copy()
            image.set_alpha(max(0, min(255, int(opacity * 255))))
        self.host.screen.blit(image, (round(x * self.scale), round(y * self.scale)))
        self.draw_count += 1

    def render(self, draws):
        for draw in draws:
            self.blit_region(draw.texture_asset_id, draw.source, draw.screen_x, draw.screen_y, draw.width,
                             draw.height, flip_x=draw.flip_x, opacity=draw.opacity)


class CanonicalBattleAdapter:
    """Canonical Battle Presentation driven by the session's battle log.

    With combatant visual profiles for every member (see
    :mod:`asteria.runtime.battle_visuals`) it draws animated combatant
    sprites, plays each ability's authored motion sequence (animation, VFX,
    audio, camera, screen flash) on a presentation timeline, and delays damage
    numbers, KO poses and the result screen to the beats they belong to.
    Battle Core state is never changed here.
    """

    name = "canonical"

    # Session parties are "heroes" and "enemies". Default side-view staging puts
    # the party on the right and enemies on the left (project / manifest
    # ``placement_by_side`` overrides it).
    DEFAULT_PLACEMENT = {"heroes": "right", "enemies": "left"}

    def __init__(self, host, *, profile_ids=None, placement_by_side=None):
        self.host = host
        self.trace = []
        self.profile_ids = dict(profile_ids or {})
        self.placement_by_side = dict(placement_by_side or self.DEFAULT_PLACEMENT)
        self.screen = None
        self.renderer = None
        self._ui_backend = None
        self.audio_cues = []
        self.resolver = None
        self._battle = None
        self.textures = None
        self.visuals_enabled = False
        self.fallback_reason = ""
        self._cursor = 0.0
        self._clock = 0.0
        self._last_impact = 0.0
        self._schedule = []
        self._order = 0
        self._view_camera = None

    # -- construction -----------------------------------------------------
    def _profile(self, category):
        library = self.host.project.battle_presentation_library
        profile_id = self.profile_ids.get(category)
        if profile_id is None:
            ids = library.ids(category)
            profile_id = ids[0] if ids else None
        return None if profile_id is None else library.require(category, profile_id)

    def _theme(self):
        return self._profile("ui_theme")

    def begin(self):
        from asteria.platform.pygame_battle_ui import PygameBattleUiBackend

        self.trace.clear()
        game = self.host.game
        self._battle = game.battle
        kwargs = {name: self._profile(category) for name, category in PRESENTATION_PROFILE_CATEGORIES.items()}
        kwargs = {name: value for name, value in kwargs.items() if value is not None}
        from asteria.presentation.battle_ui import BattleUiLayoutProfile
        layout = kwargs.get("layout") or BattleUiLayoutProfile()
        self.resolver = BattleVisualResolver(game.project, lambda uri: self.host.load_image(uri).get_size())
        sides = {side: [m.member_id for m in party.members] for side, party in game.battle.parties.items()}
        combatants = ()
        missing = self.resolver.missing_profiles([m for members in sides.values() for m in members])
        self.fallback_reason = f"no combatant visual profile for {', '.join(missing)}" if missing else ""
        if not missing:
            try:
                combatants = self.resolver.combatant_visuals(sides, self.placement_by_side, layout)
            except (BattleVisualError, OSError) as exc:
                self.fallback_reason = str(exc)
            except Exception as exc:  # pygame.error for unreadable images
                if type(exc).__name__ != "error":
                    raise
                self.fallback_reason = str(exc)
        self.visuals_enabled = bool(combatants)
        scene = BattlePresentationScene(
            f"battle.{game.encounter_id}", self.host.manifest["battle"].get("background", "battle.background"),
            combatants,
        )
        self.screen = BattleScreenRuntime(
            scene, self.resolver.clip_set, self.resolver.sprite_sheet,
            placement_by_side=self.placement_by_side, **kwargs,
        )
        self.screen.display_names = self._display_names(game)
        self.screen.member_heights = {
            v.member_id: self.resolver.sprite_sheet(v.sprite_sheet_asset_id).frames[0].height
            / v.source_pixels_per_logical_pixel
            for v in combatants
        }
        self.screen.coordinator.attach(game.battle.hooks)
        layout = self.screen.composer.layout
        scale = min(self.host.width / layout.virtual_width, self.host.height / layout.virtual_height)
        self._ui_backend = PygameBattleUiBackend(self.host.screen, scale=scale)
        self._ui_backend.vfx_drawer = self._draw_vfx
        self.renderer = BattleUiRenderer(self._ui_backend, self._theme())
        self.textures = PygameTextureDrawer(self.host, self.resolver, scale)
        self.audio_cues.clear()
        self._cursor = self._clock = self._last_impact = 0.0
        self._schedule = []
        self._shown_down = {}

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
            definition = db.actors.get(member_id) or db.enemies.get(base)
            name = getattr(definition, "display_name", "") or member_id
            if index and kinds[base] > 1:
                name = f"{name} {index}"
            names[member_id] = name
        return names

    # -- log translation --------------------------------------------------
    # -- presentation timeline ------------------------------------------------
    # Battle Core resolves actions instantly; the presentation replays them in
    # order on its own clock. Each choreography step is emitted into the
    # coordinator only when it is due, so presentation events stay in
    # increasing sequence order for every downstream runtime.

    def _at(self, time, step):
        self._order += 1
        self._schedule.append((max(time, self._clock), self._order, step))

    def _release_due(self):
        due = sorted(x for x in self._schedule if x[0] <= self._clock + 1e-9)
        if due:
            self._schedule = [x for x in self._schedule if x[0] > self._clock + 1e-9]
            for _, _, step in due:
                step()
        self._flush()

    def _flush(self):
        events = self.screen.coordinator.drain()
        if events:
            self.trace.extend(self._semantics_from_events(events))
            self.screen.consume_events(events)

    def busy(self):
        """True while queued action choreography has not finished playing."""
        if self.screen is None:
            return False
        return bool(self._schedule) or self._clock < self._cursor - 1e-9

    def particle_count(self):
        return 0 if self.screen is None else len(self.screen.feedback.vfx)

    def _ensure(self):
        """Set up for the session's current battle if begin() was not called for it."""
        battle = self.host.game.battle
        if battle is not None and (self.screen is None or self._battle is not battle):
            self.begin()
        return self.screen is not None

    def consume(self, entries):
        if not self._ensure():
            return
        coordinator = self.screen.coordinator
        # Lifecycle events (KO / revive) were queued by Battle Core hooks while the
        # actions resolved; show them when the choreography reaches the end.
        hook_events = coordinator.drain()
        for entry in entries:
            at = max(self._clock, self._cursor)
            if entry.kind == "battle_started":
                coordinator.start()
            elif entry.kind == "turn":
                self._at(at, lambda e=entry: coordinator.push_custom("battle.turn", source_id=e.member_id))
            elif entry.kind == "action":
                self._push_action(entry, at)
            elif entry.kind == "gauge":
                self._at(self._last_impact, lambda e=entry: coordinator.push_gauge_result(e.data))
            elif entry.kind == "battle_finished":
                data = entry.data
                outcome = BattleOutcome(True, tuple(data["winning_sides"]), tuple(data["defeated_sides"]))
                self._at(at, lambda o=outcome, d=data: self._finish(o, d))
        for event in hook_events:
            self._at(self._last_impact if self.visuals_enabled else self._clock,
                     lambda e=event: coordinator.reemit(e))
        self._sync_lifecycle()
        self._release_due()

    def _sync_lifecycle(self):
        """Mirror Battle Core knock-outs / revivals onto combatant poses at the right beat.

        Knock-outs decided by a resource (no lifecycle hook) are read from
        ``BattleRuntime.is_active``; the KO pose waits for the impact that
        caused it, a revival waits for the end of the queued choreography.
        """
        battle = self.host.game.battle
        if battle is None or not self.visuals_enabled:
            return
        for visual in self.screen.scene.combatants:
            member = battle.members.get(visual.member_id)
            if member is None:
                continue
            active = battle.is_active(member)
            shown_down = self._shown_down.get(visual.member_id, False)
            if not active and not shown_down:
                self._shown_down[visual.member_id] = True
                self._at(self._last_impact,
                         lambda m=visual.member_id: self.screen.animation.combatant(m).mark_defeated())
            elif active and shown_down:
                self._shown_down[visual.member_id] = False
                self._at(max(self._clock, self._cursor),
                         lambda m=visual.member_id: self.screen.animation.combatant(m).revive())

    def _finish(self, outcome, data):
        self.screen.present_result(outcome, perspective_side_ids=("heroes",))
        self.screen.coordinator.finish({"winning_sides": list(data["winning_sides"])})

    def _beat_cues(self, entry, beat):
        kind = CHANNEL_KINDS.get(beat.channel)
        if kind is None:
            return []
        targets = tuple(entry.target_ids) or (entry.member_id,)
        members = (entry.member_id,) if beat.member_id in (None, "@source") else (
            targets if beat.member_id == "@target" else (beat.member_id,))
        cues = []
        for member_id in members:
            payload = dict(beat.payload_dict())
            payload["member_id"] = member_id
            if kind == ActionCueKind.ANIMATION:
                payload["role"] = beat.cue
            elif kind == ActionCueKind.VFX:
                payload["asset_id"] = beat.cue
                payload.setdefault("duration", max(0.05, self.resolver.clip_duration(beat.cue, "play")))
            elif kind == ActionCueKind.AUDIO:
                payload["asset_id"] = beat.cue
            else:
                payload["effect"] = beat.cue
            cues.append(PresentationCue(f"action.{entry.ability_id}",
                                        ActionCue(f"{member_id}.{beat.beat_id}", beat.at, kind, payload)))
        return cues

    def _push_action(self, entry, start):
        coordinator = self.screen.coordinator
        targets = tuple(entry.target_ids)
        sequence = self.resolver.motion_sequence(entry.ability_id) if self.visuals_enabled else None

        def announce():
            coordinator.push_custom("battle.action", source_id=entry.member_id,
                                    payload={"ability_id": entry.ability_id, "target_ids": list(targets)})
            if targets:
                coordinator.push_target_selection(targets, primary_target_id=targets[0], source_id=entry.member_id)

        def values():
            for target, outcome in entry.outcomes:
                coordinator.push_resolved_value(outcome, target_id=target, source_id=entry.member_id)

        self._at(start, announce)
        if sequence is None:
            def default_cues():
                cues = [PresentationCue(f"action.{entry.ability_id}", ActionCue(
                    f"{entry.member_id}.attack", 0.0, ActionCueKind.ANIMATION,
                    {"member_id": entry.member_id, "role": "attack"}))]
                cues.extend(PresentationCue(f"action.{entry.ability_id}", ActionCue(
                    f"{target}.hit", 0.0, ActionCueKind.ANIMATION, {"member_id": target, "role": "hit"},
                )) for target, _ in entry.outcomes)
                coordinator.consume_timeline_cues(cues)
            self._at(start, default_cues)
            self._at(start, values)
            self._last_impact = start
            return
        for beat in sequence.beats:
            self._at(start + beat.at, lambda b=beat: coordinator.consume_timeline_cues(self._beat_cues(entry, b)))
        impact = next((b.at for b in sequence.beats if b.channel == "animation" and b.cue == "hit"), 0.0)
        self._at(start + impact, values)
        self._last_impact = start + impact
        self._cursor = start + sequence.duration

    def _semantics_from_events(self, events):
        """Rebuild rule-relevant meaning from the presentation events actually emitted.

        An action's values may be emitted in a later batch than its
        announcement (they wait for the impact beat), so the action being
        rebuilt is kept across batches and finalized when the next fact starts.
        """
        result = []
        pending = getattr(self, "_semantic_action", None)
        if pending is not None:
            result.append(pending)
        for event in events:
            kind, payload = event.kind, event.payload
            if kind == BattlePresentationEventKind.SCENE_STARTED:
                result.append(("battle_started",))
            elif kind == BattlePresentationEventKind.CUSTOM and payload.get("event_id") == "battle.turn":
                result.append(("turn", event.source_id))
            elif kind == BattlePresentationEventKind.CUSTOM and payload.get("event_id") == "battle.action":
                pending = [event.source_id, payload["ability_id"], tuple(payload["target_ids"]), []]
                result.append(pending)
            elif kind == BattlePresentationEventKind.RESOLVED_VALUE and pending is not None:
                pending[3].append((payload["target_id"], round(float(payload["value"]), 6),
                                   tuple(sorted(payload["outcome_tags"]))))
            elif kind == BattlePresentationEventKind.GAUGE_THRESHOLD:
                key = ("gauge", event.source_id, payload["composition_id"])
                if result and isinstance(result[-1], tuple) and result[-1][:3] == key:
                    result[-1] = (*key, (*result[-1][3], payload["threshold_id"]))
                else:
                    result.append((*key, (payload["threshold_id"],)))
            elif kind == BattlePresentationEventKind.SCENE_FINISHED:
                result.append(("battle_finished", tuple(payload["result"]["winning_sides"])))
        # Keep the newest action open (its values may still arrive); report the rest.
        self._semantic_action = result.pop() if result and isinstance(result[-1], list) else None
        return [
            ("action", item[0], item[1], item[2], tuple(item[3])) if isinstance(item, list) else item
            for item in result
        ]

    def finalize_trace(self):
        """Close the action still being rebuilt (call once the presentation is idle)."""
        pending = getattr(self, "_semantic_action", None)
        if pending is not None:
            self.trace.append(("action", pending[0], pending[1], pending[2], tuple(pending[3])))
            self._semantic_action = None
        return self.trace

    # -- frame --------------------------------------------------------------
    def update(self, dt):
        if not self._ensure():
            return
        game = self.host.game
        self._clock += float(dt)
        self._release_due()
        if game.battle is not None:
            self.screen.sync_battle(game.battle, current_member_id=self.host._battle_actor())
            actor = self.host._battle_actor()
            skills = self.host._skills_for_actor(actor)
            # Commands appear only while a hero is waiting for input.
            if actor is None or self.busy() or self.host._victory or self.host._defeat:
                skills = ()
            entries = [
                BattleActionEntry(ability_id, f"{i + 1}  {meta.get('label', ability_id)}", order=i)
                for i, (ability_id, meta) in enumerate(skills)
            ]
            capture = game.capture_targets() if skills else ()
            if capture:
                best = max(chance for _, chance, _ in capture)
                entries.append(BattleActionEntry("capture", f"X  Capture ({best * 100:.0f}%)", order=len(entries)))
            self.screen.set_action_entries(entries)
        self.screen.update(dt)

    def draw(self):
        if not self._ensure():
            self.host._draw_battle_world(show_labels=False)
            return None
        layout = self.screen.composer.layout
        base = Camera2D(width=layout.virtual_width, height=layout.virtual_height)
        textures = None
        if self.screen.scene.combatants:
            background = self.host.load_image(self.screen.scene.background_asset_id)
            self.host.screen.blit(self.host.pg.transform.smoothscale(background, (self.host.width, self.host.height)), (0, 0))
            textures = self.textures
        else:
            self.host._draw_battle_world(show_labels=False)
        self._view_camera = self.screen.camera_feedback.camera_view(base)
        result = self.screen.render(base, ui_renderer=self.renderer, texture_renderer=textures)
        self.audio_cues.extend(result.audio_cues)
        return result

    def _draw_vfx(self, effect):
        """Play a VFX sprite sheet cue centred on its member (camera shake applied)."""
        payload = dict(getattr(effect, "payload", {}) or {})
        asset_id = payload.get("asset_id")
        if not asset_id or self._view_camera is None:
            return
        try:
            visual = self.screen.scene.visual_for(effect.member_id)
            sheet = self.resolver.sprite_sheet(asset_id)
            clip = self.resolver.clip_set(asset_id).get(payload.get("clip", "play"))
        except (KeyError, BattleVisualError):
            return
        if clip is None:
            return
        progress = min(0.999, max(0.0, effect.age / max(effect.duration, 1e-6)))
        frame = sheet.frames[clip.keyframes[int(progress * len(clip.keyframes))].frame_index]
        body = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id).frames[0]
        height = body.height / visual.source_pixels_per_logical_pixel
        scale = float(payload.get("scale", 0.6))
        width, tall = frame.width * scale, frame.height * scale
        cx, cy = self._view_camera.world_to_screen(visual.anchor.x, visual.anchor.y - height * 0.5)
        self.textures.blit_region(asset_id, (frame.x, frame.y, frame.width, frame.height),
                                  cx - width / 2, cy - tall / 2, width, tall)


def create_battle_presentation_adapter(host):
    """Pick the adapter named by the manifest (``battle.presentation.adapter``); legacy by default."""
    settings = host.manifest.get("battle", {}).get("presentation", {})
    kind = settings.get("adapter", "legacy")
    if kind == "legacy":
        return LegacyPygameBattleAdapter(host)
    if kind == "canonical":
        return CanonicalBattleAdapter(
            host, profile_ids=settings.get("profiles"), placement_by_side=settings.get("placement_by_side"),
        )
    raise ValueError(f"unknown battle presentation adapter: {kind}")
