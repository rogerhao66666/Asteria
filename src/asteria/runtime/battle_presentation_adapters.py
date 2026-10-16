"""Battle presentation for the playable runtime: the canonical battle screen.

``CanonicalBattleAdapter`` consumes the ``BattleLogEntry`` stream produced by
``GameSessionRuntime`` (it decides no battle rule) and routes it through
``BattleScreenRuntime`` (HUD, turn timeline, action menu, value popups, camera
feedback, VFX, audio cues, hit-stop, result), rendered with
``PygameBattleUiBackend`` on the pygame or ModernGL presenter. Combatants come
from authored combatant visuals; a project without battle art gets generated
combatants built from its manifest images (or silhouettes). The legacy pygame
battle screen was retired in D19 (CB15 A9).

``entry_semantics`` is the comparison contract: the adapter records, in
``trace``, what it understood from the log.
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
from asteria.presentation.character_composition import CharacterComposition
from asteria.presentation.particles import ParticleSystem, effect_definition
from asteria.rpg import BattleOutcome
from asteria.runtime.battle_visuals import (
    BattleVisualError,
    BattleVisualResolver,
    vfx_keyframe,
    vfx_placement,
    vfx_rect,
)
from asteria.runtime.camera import Camera2D

CHANNEL_KINDS = {
    "animation": ActionCueKind.ANIMATION,
    "vfx": ActionCueKind.VFX,
    "audio": ActionCueKind.AUDIO,
    "camera": ActionCueKind.CAMERA,
    "screen_fx": ActionCueKind.SCREEN_FX,
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
            "action",
            entry.member_id,
            entry.ability_id,
            tuple(entry.target_ids),
            tuple(
                (t, _value(o), tuple(sorted(getattr(o, "outcome_tags", ()))))
                for t, o in entry.outcomes
            ),
        )
    if entry.kind == "turn":
        return ("turn", entry.member_id)
    if entry.kind == "gauge":
        return (
            "gauge",
            entry.member_id,
            entry.data.composition_id,
            tuple(x.threshold_id for x in entry.data.thresholds),
        )
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


class PygameTextureDrawer:
    """Draws ``TextureDraw`` commands (virtual coordinates) onto the host's pygame screen."""

    def __init__(self, host, resolver, scale):
        self.host = host
        self.resolver = resolver
        self.scale = float(scale)
        self.draw_count = 0

    def surface(self, asset_id):
        lookup = getattr(self.resolver, "generated_image", None)
        generated = lookup(asset_id) if lookup is not None else None
        if generated is not None:
            return generated
        return self.host.load_image(self.resolver.source_uri(asset_id))

    def blit_region(
        self,
        asset_id,
        source,
        x,
        y,
        width,
        height,
        *,
        flip_x=False,
        opacity=1.0,
        blend="normal",
        rotation_deg=0.0,
        tint=None,
    ):
        pg = self.host.pg
        image = self.surface(asset_id).subsurface(pg.Rect(*source))
        size = (max(1, round(width * self.scale)), max(1, round(height * self.scale)))
        if image.get_size() != size:
            image = pg.transform.scale(image, size)
        if flip_x:
            image = pg.transform.flip(image, True, False)
        if tint:
            image = image.copy()
            image.fill((*tint, 255), special_flags=pg.BLEND_RGBA_MULT)
        position = (round(x * self.scale), round(y * self.scale))
        if rotation_deg:
            # pygame rotates counter-clockwise and grows the surface: keep the quad centre fixed
            centre = (x * self.scale + size[0] / 2, y * self.scale + size[1] / 2)
            image = pg.transform.rotate(image, -rotation_deg)
            position = (
                round(centre[0] - image.get_width() / 2),
                round(centre[1] - image.get_height() / 2),
            )
        if opacity < 1.0 and blend == "add":
            # additive blits ignore surface alpha: fade by darkening the colour instead
            level = max(0, min(255, int(opacity * 255)))
            image = image.copy()
            image.fill((level, level, level), special_flags=pg.BLEND_RGB_MULT)
        elif opacity < 1.0:
            image = image.copy()
            image.set_alpha(max(0, min(255, int(opacity * 255))))
        flags = pg.BLEND_RGB_ADD if blend == "add" else 0
        self.host.screen.blit(image, position, special_flags=flags)
        self.draw_count += 1

    def render(self, draws):
        for draw in draws:
            self.blit_region(
                draw.texture_asset_id,
                draw.source,
                draw.screen_x,
                draw.screen_y,
                draw.width,
                draw.height,
                flip_x=draw.flip_x,
                opacity=draw.opacity,
                rotation_deg=draw.rotation_deg,
                tint=draw.tint,
            )


class _WorldThenUi:
    """Texture pass of the battle screen; afterwards the host switches drawing to its UI layer
    (VFX-02)."""

    def __init__(self, adapter, textures):
        self.adapter, self.textures, self.done = adapter, textures, False

    def render(self, draws):
        if self.textures is not None:
            self.textures.render(draws)
        self.finish()

    def finish(self):
        self.done = True
        host = self.adapter.host
        if hasattr(host, "world_done"):
            host.world_done("battle")
            self.adapter._ui_backend.screen = host.screen


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
        self.composition_errors = []
        self._cursor = 0.0
        self._clock = 0.0
        self._last_impact = 0.0
        self._schedule = []
        self._order = 0
        self._view_camera = None
        # (sequence, cue id, member) -> [cue, ParticleSystem, age drawn] (VFX-01)
        self._cue_particles = {}

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

        self._background_image = None

        self.trace.clear()
        game = self.host.game
        self._battle = game.battle
        kwargs = {
            name: self._profile(category)
            for name, category in PRESENTATION_PROFILE_CATEGORIES.items()
        }
        kwargs = {name: value for name, value in kwargs.items() if value is not None}
        from asteria.presentation.battle_ui import BattleUiLayoutProfile

        layout = self._layout = kwargs.get("layout") or BattleUiLayoutProfile()
        self.resolver = BattleVisualResolver(
            game.project, lambda uri: self.host.load_image(uri).get_size()
        )
        sides = {
            side: [m.member_id for m in party.members]
            for side, party in game.battle.parties.items()
        }
        combatants = ()
        self._register_fallback_visuals(sides, layout)
        missing = self.resolver.missing_profiles(
            [m for members in sides.values() for m in members]
        )
        self.fallback_reason = (
            f"no combatant visual profile for {', '.join(missing)}" if missing else ""
        )
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
            f"battle.{game.encounter_id}",
            getattr(game, "encounter_background", "")
            or self.host.manifest["battle"].get("background", "battle.background"),
            combatants,
        )
        self.screen = BattleScreenRuntime(
            scene,
            self.resolver.clip_set,
            self.resolver.sprite_sheet,
            placement_by_side=self.placement_by_side,
            **kwargs,
        )
        self.screen.display_names = self._display_names(game)
        self.screen.animation.compositions = self._compositions(combatants)
        self.screen.member_heights = {
            v.member_id: self.resolver.sprite_sheet(v.sprite_sheet_asset_id).frames[0].height
            / v.source_pixels_per_logical_pixel
            for v in combatants
        }
        self.screen.coordinator.attach(game.battle.hooks)
        layout = self.screen.composer.layout
        scale = min(
            self.host.width / layout.virtual_width, self.host.height / layout.virtual_height
        )
        self._ui_backend = PygameBattleUiBackend(self.host.screen, scale=scale)
        self._ui_backend.vfx_drawer = self._draw_vfx
        self.renderer = BattleUiRenderer(self._ui_backend, self._theme())
        self.textures = PygameTextureDrawer(self.host, self.resolver, scale)
        self.audio_cues.clear()
        self._cursor = self._clock = self._last_impact = 0.0
        self._schedule = []
        self._shown_down = {}
        self._start_boss_intro(game, layout)

    # -- boss intro camera (CAM-02) ---------------------------------------------------------------
    BOSS_INTRO = {"zoom": 1.35, "blend": 0.5, "hold": 0.9}

    def _start_boss_intro(self, game, layout):
        """Encounters tagged "boss" open with the camera on the boss, then ease back to the whole
        field."""
        from asteria.runtime.camera import CameraDirector, CameraShot

        self.camera_director = CameraDirector()
        self._camera_center = (layout.virtual_width / 2, layout.virtual_height / 2)
        self._intro_until = 0.0
        settings = self.host.manifest.get("battle", {}).get("presentation", {})
        encounter = game.project.rpg_database.encounters.get(game.encounter_id)
        if not self.visuals_enabled or encounter is None or "boss" not in encounter.tags:
            return
        if settings.get("boss_intro", True) is False:
            return
        db = game.project.rpg_database
        bosses = [
            m.member_id
            for m in game.battle.parties.get("enemies", ()).members
            if "boss" in getattr(db.enemies.get(m.member_id.split(":", 1)[0]), "tags", ())
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
        from asteria.runtime.camera import clamp_center_to_bounds

        layout = self.screen.composer.layout
        width, height = layout.virtual_width, layout.virtual_height
        x, y, zoom = view
        sx, sy = director.shake_offset
        x, y = clamp_center_to_bounds(
            x - sx, y - sy, width / zoom, height / zoom, (0.0, 0.0, width, height)
        )
        return (x + sx, y + sy, zoom)

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
        """True while queued action choreography (or the boss intro) has not finished playing."""
        if self.screen is None:
            return False
        intro = self._clock < getattr(self, "_intro_until", 0.0) - 1e-9
        return intro or bool(self._schedule) or self._clock < self._cursor - 1e-9

    def particle_count(self):
        return 0 if self.screen is None else len(self.screen.feedback.vfx)

    # -- projects without battle art: generated combatant and effect sheets -----------------------
    FRAME_HEIGHT = 96

    def _source_image(self, member_id, side, index):
        """The manifest image a project without battle art shows for a combatant (None: draw a
        silhouette)."""
        battle = self.host.manifest.get("battle", {})
        try:
            if side == "heroes" and battle.get("heroes"):
                return self.host.load_image(battle["heroes"][index % len(battle["heroes"])]), False
            enemy = str(member_id).split(":", 1)[0]
            rel = battle.get("enemy_sprites", {}).get(enemy)
            if rel:
                return self.host.load_image(
                    rel
                ), True  # legacy screens drew enemies facing left: flip
        except Exception as exc:  # pygame.error for an unreadable image: fall back to a silhouette
            if type(exc).__name__ not in ("error", "FileNotFoundError"):
                raise
        return None, False

    def _silhouette(self, member_id, side):
        pg = self.host.pg
        image = pg.Surface((64, 96), pg.SRCALPHA)
        color = (90, 140, 220) if side == "heroes" else (210, 90, 100)
        dark = tuple(c // 2 for c in color)
        pg.draw.ellipse(image, color, (10, 36, 44, 58))
        pg.draw.ellipse(image, dark, (10, 36, 44, 58), 3)
        pg.draw.circle(image, color, (32, 24), 18)
        pg.draw.circle(image, dark, (32, 24), 18, 3)
        pg.font.init()
        label = pg.font.Font(None, 30).render(str(member_id)[:1].upper(), True, (250, 250, 255))
        image.blit(label, label.get_rect(center=(32, 64)))
        return image

    def _combatant_sheet(self, image, *, flip):
        """Five frames from one picture: idle, attack (lunge), hit (flash), ko (fallen, dark),
        weak (slumped, pale - shown at low health when the manifest sets battle.weak_below)."""
        pg = self.host.pg
        if flip:
            image = pg.transform.flip(image, True, False)
        height = self.FRAME_HEIGHT
        w, h = image.get_size()
        width = max(1, round(w * height / h))
        if image.get_bitsize() < 24:
            image = image.convert(32, pg.SRCALPHA)
        body = pg.transform.smoothscale(image, (width, height))
        fw, fh = width + 20, height + 8
        sheet = pg.Surface((fw * 5, fh), pg.SRCALPHA)
        y = fh - height
        sheet.blit(body, (10, y))
        sheet.blit(body, (fw + 16, y - 3))  # lunge forward
        hit = body.copy()
        hit.fill((110, 110, 110, 0), special_flags=pg.BLEND_RGBA_ADD)
        sheet.blit(hit, (fw * 2 + 5, y))
        fallen = pg.transform.rotate(body, 80)
        fallen.fill((120, 115, 130, 255), special_flags=pg.BLEND_RGBA_MULT)
        if fallen.get_width() > fw or fallen.get_height() > fh:
            k = min(fw / fallen.get_width(), fh / fallen.get_height())
            fallen = pg.transform.smoothscale(
                fallen, (max(1, int(fallen.get_width() * k)), max(1, int(fallen.get_height() * k)))
            )
        sheet.blit(fallen, (fw * 3 + (fw - fallen.get_width()) // 2, fh - fallen.get_height()))
        weak = body.copy()  # worn out: slumped a little and paler
        weak.fill((205, 190, 190, 255), special_flags=pg.BLEND_RGBA_MULT)
        sheet.blit(weak, (fw * 4 + 10, y + 4))
        clips = {
            "weak": {"frames": [4], "frame_duration": 0.5, "loop": True},
            "idle": {"frames": [0], "frame_duration": 0.5, "loop": True},
            "attack": {"frames": [1, 1, 0], "frame_duration": 0.1, "loop": False},
            "hit": {"frames": [2, 2, 0], "frame_duration": 0.1, "loop": False},
            "ko": {"frames": [3], "frame_duration": 0.5, "loop": True},
        }
        return sheet, (fw, fh), clips

    def _show_new_combatants(self, game):
        """Members that joined after the battle began (SUMMON, reinforcements) get a visual and
        appear."""
        if not self.visuals_enabled:
            return
        shown = {v.member_id for v in self.screen.scene.combatants}
        sides = {
            side: [m.member_id for m in party.members]
            for side, party in game.battle.parties.items()
        }
        new = {side: [m for m in members if m not in shown] for side, members in sides.items()}
        if not any(new.values()):
            return
        self._register_fallback_visuals(new, self._layout)
        visuals = self.resolver.combatant_visuals(sides, self.placement_by_side, self._layout)
        added = [v for v in visuals if v.member_id not in shown]
        for visual in added:
            self.screen.add_combatant(visual)
            self.screen.member_heights[visual.member_id] = (
                self.resolver.sprite_sheet(visual.sprite_sheet_asset_id).frames[0].height
                / visual.source_pixels_per_logical_pixel
            )
        self.screen.display_names = self._display_names(game)
        self.screen.animation.compositions.update(self._compositions(added))

    def _register_fallback_visuals(self, sides, layout):
        """Every combatant without a combatant_visuals profile gets a generated one (no legacy
        fallback)."""
        target = (
            float(getattr(layout, "virtual_height", 180)) * 0.16
        )  # logical height of a regular combatant
        done = set()
        for side, members in sides.items():
            for index, member_id in enumerate(members):
                key = str(member_id).split(":", 1)[0]
                if key in done or self.resolver.profile_for(member_id) is not None:
                    continue
                done.add(key)
                image, flip = self._source_image(member_id, side, index)
                sheet, frame_size, clips = self._combatant_sheet(
                    image if image is not None else self._silhouette(key, side), flip=flip
                )
                asset_id = f"generated.combatant.{key}"
                self.resolver.register_generated(
                    asset_id, sheet, sheet.get_size(), frame_size=frame_size, clips=clips
                )
                size = (
                    (self.host._enemy_layout(member_id) or {}).get("size")
                    if side != "heroes"
                    else None
                )
                logical = target * (float(size[1]) / 120.0 if size else 1.0)
                self.resolver.register_generated_profile(key, asset_id, logical / frame_size[1])

    def _manifest_skill_fx(self, ability_id):
        """Generated VFX sheet for a manifest skill ``fx`` image (4 columns, ``frames`` cells), or
        None."""
        meta = self.host.manifest.get("battle", {}).get("skills", {}).get(ability_id) or {}
        if not meta.get("fx"):
            return None
        asset_id = f"generated.fx.{ability_id}"
        if not self.resolver.is_generated(asset_id):
            try:
                image = self.host.load_image(meta["fx"])
            except (
                Exception
            ) as exc:  # pygame.error / missing file: no effect, the action still plays
                if type(exc).__name__ not in ("error", "FileNotFoundError"):
                    raise
                return None
            count = int(meta.get("frames", 16))
            columns = 4
            rows = max(1, (count + columns - 1) // columns)
            frame = (image.get_width() // columns, image.get_height() // rows)
            self.resolver.register_generated(
                asset_id,
                image,
                image.get_size(),
                frame_size=frame,
                clips={
                    "play": {
                        "frames": list(range(count)),
                        "frame_duration": 0.42 / max(1, count),
                        "loop": False,
                    }
                },
                pivot=(0.5, 0.5),
                vfx={"anchor": "center", "scale": 1.0},
            )
        return asset_id

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
                self._at(
                    at,
                    lambda e=entry: coordinator.push_custom("battle.turn", source_id=e.member_id),
                )
            elif entry.kind == "action":
                self._push_action(entry, at)
            elif entry.kind == "gauge":
                self._at(self._last_impact, lambda e=entry: coordinator.push_gauge_result(e.data))
            elif entry.kind == "battle_finished":
                data = entry.data
                outcome = BattleOutcome(
                    True, tuple(data["winning_sides"]), tuple(data["defeated_sides"])
                )
                self._at(at, lambda o=outcome, d=data: self._finish(o, d))
        for event in hook_events:
            self._at(
                self._last_impact if self.visuals_enabled else self._clock,
                lambda e=event: coordinator.reemit(e),
            )
        self._sync_lifecycle()
        self._release_due()

    def _sync_state_tint(self, member_id, member):
        """Battlers carrying a state with a ``tint`` are drawn in that colour (poison green,
        frozen blue...); several tints multiply."""
        states = getattr(member.subject, "states", None)
        tints = self.screen.animation.state_tints
        colour = None
        if states is not None and states.has_active:
            for active in states.active_states():
                rgb = states.registry.require(active.state_id).tint_rgb()
                if rgb is not None:
                    colour = (
                        rgb if colour is None else tuple(a * b // 255 for a, b in zip(colour, rgb))
                    )
        if colour is None:
            tints.pop(member_id, None)
        else:
            tints[member_id] = colour

    def _weak_fraction(self):
        """Health share below which a combatant shows its ``weak`` pose (the project's
        ``BattleOptions``, else manifest ``battle.weak_below``; 0 = never)."""
        try:
            return max(0.0, min(1.0, float(self.host.battle_option("weak_below"))))
        except (TypeError, ValueError):
            return 0.0

    def _sync_weak_pose(self, visual, member):
        """Low-health combatants rest in their ``weak`` pose; it ends when they recover."""
        limit = self._weak_fraction()
        if limit <= 0 or not visual.clip_for("weak"):
            return
        resource = self.host.game.rules.knockout_resource_id
        pool = member.subject.resources
        if not resource or not pool.contains(resource) or pool.maximum(resource) <= 0:
            return
        weak = pool.current(resource) / pool.maximum(resource) <= limit
        state = self.screen.animation.combatant(visual.member_id)
        role = state.role.value if hasattr(state.role, "value") else str(state.role)
        if weak and role == "idle":
            state.set_role("weak", restart=False)
        elif not weak and role == "weak":
            state.set_role("idle", restart=False)

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
            if active:
                self._sync_weak_pose(visual, member)
            self._sync_state_tint(visual.member_id, member)
            shown_down = self._shown_down.get(visual.member_id, False)
            if not active and not shown_down:
                self._shown_down[visual.member_id] = True
                self._at(
                    self._last_impact,
                    lambda m=visual.member_id: self.screen.animation.combatant(m).mark_defeated(),
                )
            elif active and shown_down:
                self._shown_down[visual.member_id] = False
                self._at(
                    max(self._clock, self._cursor),
                    lambda m=visual.member_id: self.screen.animation.combatant(m).revive(),
                )

    def _finish(self, outcome, data):
        self.screen.present_result(outcome, perspective_side_ids=("heroes",))
        self.screen.coordinator.finish({"winning_sides": list(data["winning_sides"])})

    def _beat_cues(self, entry, beat):
        kind = CHANNEL_KINDS.get(beat.channel)
        if kind is None:
            return []
        targets = tuple(entry.target_ids) or (entry.member_id,)
        members = (
            (entry.member_id,)
            if beat.member_id in (None, "@source")
            else (targets if beat.member_id == "@target" else (beat.member_id,))
        )
        cues = []
        for member_id in members:
            payload = dict(beat.payload_dict())
            payload["member_id"] = member_id
            if kind == ActionCueKind.ANIMATION:
                payload["role"] = beat.cue
            elif kind == ActionCueKind.VFX:
                payload["asset_id"] = beat.cue
                particles = effect_definition(self.host.game.project.assets, beat.cue)
                if (
                    particles is not None
                ):  # VFX-01: emission plus the longest life, so every particle finishes
                    emit = 1.0 if particles.looping else particles.duration
                    payload.setdefault("duration", emit + particles.lifetime[1])
                else:
                    payload.setdefault(
                        "duration", max(0.05, self.resolver.clip_duration(beat.cue, "play"))
                    )
            elif kind == ActionCueKind.AUDIO:
                payload["asset_id"] = beat.cue
            else:
                payload["effect"] = beat.cue
            cues.append(
                PresentationCue(
                    f"action.{entry.ability_id}",
                    ActionCue(f"{member_id}.{beat.beat_id}", beat.at, kind, payload),
                )
            )
        return cues

    def _push_action(self, entry, start):
        coordinator = self.screen.coordinator
        targets = tuple(entry.target_ids)
        sequence = (
            self.resolver.motion_sequence(entry.ability_id) if self.visuals_enabled else None
        )

        def announce():
            coordinator.push_custom(
                "battle.action",
                source_id=entry.member_id,
                payload={"ability_id": entry.ability_id, "target_ids": list(targets)},
            )
            if targets:
                coordinator.push_target_selection(
                    targets, primary_target_id=targets[0], source_id=entry.member_id
                )

        def values():
            for target, outcome in entry.outcomes:
                coordinator.push_resolved_value(
                    outcome, target_id=target, source_id=entry.member_id
                )

        self._at(start, announce)
        if sequence is None:

            def default_cues():
                cues = [
                    PresentationCue(
                        f"action.{entry.ability_id}",
                        ActionCue(
                            f"{entry.member_id}.attack",
                            0.0,
                            ActionCueKind.ANIMATION,
                            {"member_id": entry.member_id, "role": "attack"},
                        ),
                    )
                ]
                cues.extend(
                    PresentationCue(
                        f"action.{entry.ability_id}",
                        ActionCue(
                            f"{target}.hit",
                            0.0,
                            ActionCueKind.ANIMATION,
                            {"member_id": target, "role": "hit"},
                        ),
                    )
                    for target, _ in entry.outcomes
                )
                # Effects configured per skill in the manifest (projects without motion sequences).
                skill = (
                    self.host.manifest.get("battle", {}).get("skills", {}).get(entry.ability_id)
                    or {}
                )
                fx = self._manifest_skill_fx(entry.ability_id)
                for target in [t for t, _ in entry.outcomes][:1] if fx else ():
                    cues.append(
                        PresentationCue(
                            f"action.{entry.ability_id}",
                            ActionCue(
                                f"{target}.fx",
                                0.0,
                                ActionCueKind.VFX,
                                {"member_id": target, "asset_id": fx, "duration": 0.42},
                            ),
                        )
                    )
                if skill.get("sfx"):
                    cues.append(
                        PresentationCue(
                            f"action.{entry.ability_id}",
                            ActionCue(
                                f"{entry.member_id}.sfx",
                                0.0,
                                ActionCueKind.AUDIO,
                                {"member_id": entry.member_id, "asset_id": skill["sfx"]},
                            ),
                        )
                    )
                coordinator.consume_timeline_cues(cues)

            self._at(start, default_cues)
            self._at(start, values)
            self._last_impact = start
            return
        for beat in sequence.beats:
            if (
                beat.channel == "motion_fx"
            ):  # afterimage / trail echoes of the source or targets (VFX-03)
                payload = dict(beat.payload_dict())
                hold = float(payload.pop("duration", beat.duration) or 0.3)
                members = (
                    (entry.member_id,)
                    if beat.member_id in (None, "@source")
                    else (
                        tuple(entry.target_ids)
                        if beat.member_id == "@target"
                        else (beat.member_id,)
                    )
                )
                for member in members:
                    self._at(
                        start + beat.at,
                        lambda m=member, c=beat.cue, d=hold, p=payload: (
                            self.screen.animation.start_motion_fx(m, c, d, **p)
                        ),
                    )
                continue
            if beat.channel == "timing" and beat.cue == "hit_stop":
                hold = float(beat.payload_dict().get("duration", beat.duration) or 0.0)
                self._at(start + beat.at, lambda d=hold: self._start_hit_stop(d))
                continue
            self._at(
                start + beat.at,
                lambda b=beat: coordinator.consume_timeline_cues(self._beat_cues(entry, b)),
            )
        impact = next(
            (b.at for b in sequence.beats if b.channel == "animation" and b.cue == "hit"), 0.0
        )
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
            elif (
                kind == BattlePresentationEventKind.CUSTOM
                and payload.get("event_id") == "battle.turn"
            ):
                result.append(("turn", event.source_id))
            elif (
                kind == BattlePresentationEventKind.CUSTOM
                and payload.get("event_id") == "battle.action"
            ):
                pending = [
                    event.source_id,
                    payload["ability_id"],
                    tuple(payload["target_ids"]),
                    [],
                ]
                result.append(pending)
            elif kind == BattlePresentationEventKind.RESOLVED_VALUE and pending is not None:
                pending[3].append(
                    (
                        payload["target_id"],
                        round(float(payload["value"]), 6),
                        tuple(sorted(payload["outcome_tags"])),
                    )
                )
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
            ("action", item[0], item[1], item[2], tuple(item[3]))
            if isinstance(item, list)
            else item
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
    def _start_hit_stop(self, duration):
        """Freeze the action for ``duration`` seconds at an impact (BTL-04 hit-stop)."""
        self._hit_stop = max(getattr(self, "_hit_stop", 0.0), float(duration))

    def update(self, dt):
        if not self._ensure():
            return
        game = self.host.game
        dt = float(dt)
        frozen = min(dt, getattr(self, "_hit_stop", 0.0))
        if frozen > 0:
            self._hit_stop -= frozen
            dt -= frozen  # the presentation clock and animations hold during hit-stop
        self._clock += dt
        self._release_due()
        director = getattr(self, "camera_director", None)
        if director is not None:
            self._camera_view = self._clamped_view(
                director, director.update(dt, (*self._camera_center, 1.0))
            )
        if game.battle is not None:
            self._show_new_combatants(game)
            self.screen.sync_battle(game.battle, current_member_id=self.host._battle_actor())
            actor = self.host._battle_actor()
            skills = self.host._skills_for_actor(actor)
            # Commands appear only while a hero is waiting for input.
            if actor is None or self.busy() or self.host._victory or self.host._defeat:
                skills = ()
            commands = getattr(self.host, "battle_commands", None)
            if commands is not None:  # the full command menu (skills, items, concoct, targets)
                self._show_commands(commands, actor if skills else None)
                self.screen.update(dt)
                return
            entries = []
            for i, (ability_id, meta) in enumerate(skills):
                wait = game.battle.cooldown_remaining(actor, ability_id)  # GP-02 cooldowns
                label = f"{i + 1}  {meta.get('label', ability_id)}" + (
                    f"  ({wait})" if wait else ""
                )
                reason = f"Ready in {wait} turn" + ("" if wait == 1 else "s") if wait else ""
                entries.append(
                    BattleActionEntry(
                        ability_id, label, order=i, enabled=not wait, disabled_reason=reason
                    )
                )
            capture = game.capture_targets() if skills else ()
            if capture:
                best = max(chance for _, chance, _ in capture)
                entries.append(
                    BattleActionEntry(
                        "capture", f"X  Capture ({best * 100:.0f}%)", order=len(entries)
                    )
                )
            if skills and game.rules.boost_enabled and game.max_boost_level(actor) > 0:
                amount = game.battle.battle_resources.current(actor, game.rules.boost_resource_id)
                label = game.rules.boost_resource_id.replace("_", " ").title()
                level = getattr(self.host, "_boost_level", 0)
                entries.append(
                    BattleActionEntry(
                        "boost",
                        f"B  Boost x{level + 1} ({label} {int(amount)})",
                        order=len(entries),
                    )
                )
            self.screen.set_action_entries(entries)
        self.screen.update(dt)

    def member_screen_box(self, member_id):
        """``(centre_x, top_y, feet_y)`` of a combatant on the window in pixels, or None when not
        shown."""
        view = self._view_camera
        if view is None or self.screen is None:
            return None
        try:
            visual = self.screen.scene.visual_for(member_id)
        except KeyError:
            return None
        try:
            body = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id).frames[0]
            height = body.height / visual.source_pixels_per_logical_pixel
        except (KeyError, BattleVisualError, AttributeError, IndexError):
            height = 32.0
        scale = self.textures.scale if self.textures is not None else 1.0
        x, feet = view.world_to_screen(visual.anchor.x, visual.anchor.y)
        _, top = view.world_to_screen(visual.anchor.x, visual.anchor.y - height)
        return x * scale, top * scale, feet * scale

    def _show_commands(self, commands, actor):
        menu, feedback = self.screen.action_menu, self.screen.camera_feedback
        if menu.policy.include_all_category:  # the command menu shows its own categories only
            from dataclasses import replace

            menu.policy = replace(menu.policy, include_all_category=False)
        if actor is None:
            menu.show((), "Skills", 0)
            feedback.target_ids, feedback.primary_target_id = (), None
            return
        rows = commands.entries(actor)
        if commands.mode == "root":
            menu.show(rows, "Command", commands.cursor)
        elif commands.mode == "command":
            everything = commands.skill_rows(actor)
            for name in commands.custom_categories(actor):  # a project's own menu groups
                everything = everything + commands.skill_rows(actor, name)
            everything = everything + commands.item_rows()
            if commands.style == "root":
                everything = commands.attack_rows(actor) + everything
            menu.show(everything, commands.category, commands.cursor)
        else:
            menu.show(rows, rows[0].category if rows else "Target", commands.cursor)
        target = commands.selected_target(actor)
        feedback.target_ids, feedback.primary_target_id = (
            ((target,), target) if target else ((), None)
        )

    def _background(self):
        """The battle background image, or a plain backdrop when the project has none."""
        cached = getattr(self, "_background_image", None)
        if cached is not None:
            return cached
        pg = self.host.pg
        try:
            image = self.host.load_image(self.screen.scene.background_asset_id)
        except Exception as exc:  # pygame.error / missing file
            if type(exc).__name__ not in ("error", "FileNotFoundError"):
                raise
            image = pg.Surface((self.host.width, self.host.height))
            for y in range(self.host.height):  # sky-to-ground gradient
                t = y / max(1, self.host.height - 1)
                pg.draw.line(
                    image,
                    (int(28 + 30 * t), int(34 + 50 * t), int(52 + 10 * t)),
                    (0, y),
                    (self.host.width, y),
                )
        self._background_image = image
        return image

    def draw(self):
        if not self._ensure():
            return None
        layout = self.screen.composer.layout
        cx, cy, zoom = getattr(self, "_camera_view", None) or (
            layout.virtual_width / 2,
            layout.virtual_height / 2,
            1.0,
        )
        base = Camera2D(
            cx - layout.virtual_width / (2 * zoom),
            cy - layout.virtual_height / (2 * zoom),
            layout.virtual_width,
            layout.virtual_height,
            zoom,
        )
        background = self._background()
        # The background zooms with the camera (the battlefield is the virtual layout rectangle).
        bx, by = base.world_to_screen(0.0, 0.0)
        scale = self.host.width / layout.virtual_width
        size = (round(self.host.width * zoom), round(self.host.height * zoom))
        self.host.screen.blit(
            self.host.pg.transform.smoothscale(background, size),
            (round(bx * scale), round(by * scale)),
        )
        textures = self.textures if self.screen.scene.combatants else None
        self._view_camera = self.screen.camera_feedback.camera_view(base)
        self._ui_backend.screen = self.host.screen  # the world layer, until the textures are drawn
        world_then_ui = _WorldThenUi(self, textures)
        result = self.screen.render(
            base, ui_renderer=self.renderer, texture_renderer=world_then_ui
        )
        if not world_then_ui.done:
            world_then_ui.finish()
        self.audio_cues.extend(result.audio_cues)
        return result

    def _compositions(self, combatants):
        """Attachments and layers authored on each body sheet (Character Composition tab)."""
        out = {}
        for visual in combatants:
            try:
                composition = CharacterComposition.from_meta(
                    self.resolver.sheet_meta(visual.sprite_sheet_asset_id)
                )
            except (KeyError, TypeError, ValueError) as exc:
                self.composition_errors.append(f"{visual.sprite_sheet_asset_id}: {exc}")
                continue
            if composition is not None:
                out[visual.member_id] = composition
        return out

    def _draw_vfx(self, effect):
        """Play a VFX sprite sheet cue centred on its member (camera shake applied), in the world
        layer."""
        drawing_world = getattr(self.host, "drawing_world", None)
        with self.host.profiler.section("vfx"):
            if drawing_world is None:
                self._draw_vfx_cue(effect)
            else:
                with drawing_world():
                    self._draw_vfx_cue(effect)

    def _draw_vfx_cue(self, effect):
        payload = dict(getattr(effect, "payload", {}) or {})
        asset_id = payload.get("asset_id")
        if not asset_id or self._view_camera is None:
            return
        definition = effect_definition(self.host.game.project.assets, asset_id)
        if definition is not None:  # a particle effect (VFX-01): a burst on the member
            self._draw_particle_cue(effect, definition, payload)
            return
        try:
            visual = self.screen.scene.visual_for(effect.member_id)
            sheet = self.resolver.sprite_sheet(asset_id)
            clip = self.resolver.clip_set(asset_id).get(payload.get("clip", "play"))
        except (KeyError, BattleVisualError):
            return
        if clip is None:
            return
        frame = sheet.frames[
            clip.keyframes[
                vfx_keyframe(effect.age, effect.duration, len(clip.keyframes))
            ].frame_index
        ]
        body = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id).frames[0]
        height = body.height / visual.source_pixels_per_logical_pixel
        placement = vfx_placement(self.resolver.sheet_meta(asset_id), payload)
        x, y, width, tall = vfx_rect(
            placement, visual.anchor.x, visual.anchor.y, height, frame.width, frame.height
        )
        cx, cy = self._view_camera.world_to_screen(x, y)
        self.textures.blit_region(
            asset_id,
            (frame.x, frame.y, frame.width, frame.height),
            cx - width / 2,
            cy - tall / 2,
            width,
            tall,
            opacity=placement["opacity"],
            blend=placement["blend"],
        )

    def _draw_particle_cue(self, effect, definition, payload):
        systems = self._cue_particles
        # a cue is replaced every frame as it ages: key it by what stays the same
        key = (getattr(effect, "sequence", 0), getattr(effect, "cue_id", ""), effect.member_id)
        entry = systems.get(key)
        try:
            visual = self.screen.scene.visual_for(effect.member_id)
            body = self.resolver.sprite_sheet(visual.sprite_sheet_asset_id).frames[0]
            height = body.height / visual.source_pixels_per_logical_pixel
        except (KeyError, BattleVisualError, AttributeError, IndexError):
            return
        placement = vfx_placement({}, payload)
        x, y, _, _ = vfx_rect(placement, visual.anchor.x, visual.anchor.y, height, 0.0, 0.0)
        if entry is None or effect.age < entry[2]:  # new, or the same cue started again
            emit_for = float(
                payload.get("emit_for", 1.0 if definition.looping else definition.duration)
            )
            seed = f"{key[0]}:{key[1]}:{key[2]}"
            system = ParticleSystem(
                definition, x=x, y=y, seed=seed, scale=placement["scale"], emit_for=emit_for
            )
            if len(systems) > 64:  # cues end with their beat; forget old ones
                systems.clear()
            entry = systems[key] = [effect, system, 0.0]
        entry[0] = effect
        _, system, seen_age = entry
        system.move_to(x, y)
        system.update(max(0.0, effect.age - seen_age))
        entry[2] = effect.age
        scale = self.textures.scale
        view = self._view_camera

        def to_screen(wx, wy):
            sx, sy = view.world_to_screen(wx, wy)
            return sx * scale, sy * scale

        self.host.particle_drawer.draw(
            self.host.screen,
            (system,),
            to_screen,
            view.zoom * scale,
            image=getattr(self.host, "particle_image", None),
        )


def create_battle_presentation_adapter(host):
    """The battle presentation for the manifest (``battle.presentation``): the canonical screen.

    The legacy pygame screen was retired (CB15 A9, D19); a manifest that still names ``legacy``
    gets
    the canonical screen, which draws generated combatants from the manifest images when a project
    has no battle art. ``legacy_requested`` records that for the Problems panel / logs.
    """
    settings = host.manifest.get("battle", {}).get("presentation", {})
    kind = settings.get("adapter", "canonical")
    if kind not in ("canonical", "legacy"):
        raise ValueError(f"unknown battle presentation adapter: {kind}")
    adapter = CanonicalBattleAdapter(
        host,
        profile_ids=settings.get("profiles"),
        placement_by_side=settings.get("placement_by_side"),
    )
    adapter.legacy_requested = kind == "legacy"
    return adapter
