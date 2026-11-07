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
``trace``, what it understood from the log."""

from __future__ import annotations

from typing import Protocol

from asteria import kernels
from asteria.graphics.scaling import resized
from asteria.platform.pygame_battle_ui import PygameBattleUiBackend
from asteria.presentation import (
    BattlePresentationScene,
    BattleScreenRuntime,
    BattleUiRenderer,
)
from asteria.presentation.battle.ui import BattleUiLayoutProfile
from asteria.runtime.battle.frame import BattleFrameMixin
from asteria.runtime.battle.generated_art import GeneratedBattleArtMixin
from asteria.runtime.battle.presentation_parts import PARTY_SIDES
from asteria.runtime.battle.timeline import BattleTimelineMixin
from asteria.runtime.battle.visuals import (
    SPRITE_SHEET_KIND,
    BattleVisualError,
    BattleVisualResolver,
)
from asteria.runtime.field.ai import VisibleEncounterComponent

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

    # Scaled sprite frames kept, in pixels (4 bytes each); past it the cache starts over.
    SPRITE_PIXELS = 6_000_000

    def __init__(self, host, resolver, scale):
        self.host = host
        self.resolver = resolver
        self.scale = float(scale)
        self.draw_count = 0
        self._sprites = {}  # (asset, source, size, flip) -> (sheet, visible part, its offset)
        self._sprite_pixels = 0
        self._smooth = {}  # asset id -> whether its sheet asks for smooth (bilinear) resizing

    def smooth(self, asset_id):
        """True when the sheet's ``scaling`` metadata is ``smooth``: its frames are resized
        with blended pixels instead of the sharp nearest-neighbour pixel art gets."""
        known = self._smooth.get(asset_id)
        if known is None:
            lookup = getattr(self.resolver, "sheet_meta", None)
            try:
                meta = lookup(asset_id) if lookup is not None else {}
            except Exception:  # noqa: BLE001 - a generated or unknown sheet: pixel art
                meta = {}
            known = self._smooth[asset_id] = str(meta.get("scaling", "pixel")) == "smooth"
        return known

    def resized(self, asset_id, image, size):
        """``image`` at ``size`` the way its sheet asks (see ``smooth``)."""

        return resized(self.host.pg, image, size, smooth=self.smooth(asset_id))

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
        size = (max(1, round(width * self.scale)), max(1, round(height * self.scale)))
        if blend != "add" and not rotation_deg:
            self._blit_visible(asset_id, source, x, y, size, flip_x, opacity, tint)
            return
        image = self.resized(asset_id, self.surface(asset_id).subsurface(pg.Rect(*source)), size)
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

    def _blit_visible(self, asset_id, source, x, y, size, flip_x, opacity, tint):
        """A normal (alpha) blit without rotation: the frame is scaled and flipped once, and only
        its visible part is drawn. Fully transparent pixels leave the screen as it was, so the
        picture is the same as blitting the whole frame."""
        pg = self.host.pg
        sheet = self.surface(asset_id)
        key = (asset_id, tuple(source), size, bool(flip_x))
        known = self._sprites.get(key)
        if known is None or known[0] is not sheet:
            image = self.resized(asset_id, sheet.subsurface(pg.Rect(*source)), size)
            if flip_x:
                image = pg.transform.flip(image, True, False)
            box = image.get_bounding_rect()
            visible, pixels = image.subsurface(box), 0
            if image.get_parent() is None:  # a scaled copy: keep only the part that shows
                visible, pixels = visible.copy(), box.width * box.height
            if known is not None:  # the picture under this id was replaced
                self._sprite_pixels -= known[3]
            if self._sprite_pixels + pixels > self.SPRITE_PIXELS:
                self._sprites.clear()  # a zooming camera: every size is new, start over
                self._sprite_pixels = 0
            self._sprite_pixels += pixels
            known = self._sprites[key] = (sheet, visible, box.topleft, pixels)
        _, image, (dx, dy), _ = known
        self.draw_count += 1
        if not image.get_width() or not image.get_height():
            return  # an empty frame
        if tint:
            image = image.copy()
            image.fill((*tint, 255), special_flags=pg.BLEND_RGBA_MULT)
        if opacity < 1.0:
            image = image.copy()
            image.set_alpha(max(0, min(255, int(opacity * 255))))
        self.host.screen.blit(image, (round(x * self.scale) + dx, round(y * self.scale) + dy))

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


class CanonicalBattleAdapter(BattleTimelineMixin, GeneratedBattleArtMixin, BattleFrameMixin):
    """Canonical Battle Presentation driven by the session's battle log.

    With combatant visual profiles for every member (see
    :mod:`asteria.runtime.battle.visuals`) it draws animated combatant
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
        self._extent_cache = {}  # sprite sheet -> the extent of its drawn pixels
        self._vfx_content_cache = {}  # effect id -> its particle content
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

    def _command_pages(self):
        """The Command Menu Pages record the layout's ``command_pages`` names, else None."""
        library = self.host.project.battle_presentation_library
        name = getattr(getattr(self, "_layout", None), "command_pages", "")
        return library.require("interaction", name) if name in library.ids("interaction") else None

    def _stage_template(self, game, layout):
        """The staging record this fight stands by: the encounter's ``stage:<id>`` tag, else the
        layout's ``stage_template`` (a Side-View Positions or Portrait Party Layout id)."""
        library = self.host.project.battle_presentation_library
        options = {}
        for category in ("portrait_templates", "sideview_templates"):
            for key in library.ids(category):
                options[key] = library.require(category, key)
        chosen = game.encounter_choice("stage", options) if options else None
        name = getattr(layout, "stage_template", "")
        return chosen or options.get(name)

    def begin(self):
        self._background_image = None

        self.trace.clear()
        game = self.host.game
        self._battle = game.battle
        kwargs = {
            name: self._profile(category)
            for name, category in PRESENTATION_PROFILE_CATEGORIES.items()
        }
        kwargs = {name: value for name, value in kwargs.items() if value is not None}

        layout = self._layout = kwargs.get("layout") or BattleUiLayoutProfile()
        self.resolver = BattleVisualResolver(
            game.project, lambda uri: self.host.load_image(uri).get_size()
        )
        sides = {
            side: [m.member_id for m in party.members]
            for side, party in game.battle.parties.items()
        }
        key_for = getattr(game, "battle_profile_key", None)
        if callable(key_for):  # creatures are drawn by their species' visual profiles
            self.resolver.profile_keys = {
                m: key_for(m) for members in sides.values() for m in members
            }
        combatants = ()
        self._register_fallback_visuals(sides, layout)
        missing = self.resolver.missing_profiles(
            [m for members in sides.values() for m in members]
        )
        self.fallback_reason = (
            f"no combatant visual profile for {', '.join(missing)}" if missing else ""
        )
        portraits = self._portraits(sides)
        if not missing:
            try:
                combatants = self.resolver.combatant_visuals(
                    sides,
                    self.placement_by_side,
                    layout,
                    self._stage_template(game, layout),
                    PARTY_SIDES,
                    hud_portraits=portraits,
                )
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
        self.screen.translate = game.tr  # the screen's own words in the player's language
        self.screen.hud.state_label = self._state_label(game)  # status chips (D60)
        self.screen.result.translate = game.tr  # and the result headline (Victory...)
        self.screen.animation.compositions = self._compositions(combatants)
        self.screen.member_heights = {v.member_id: self._body_height(v) for v in combatants}
        self.screen.member_extents = {v.member_id: self._body_extents(v) for v in combatants}
        self._hide_unlisted_hud(combatants)
        self.screen.member_portraits = portraits
        self.screen.coordinator.attach(game.battle.hooks)
        layout = self.screen.composer.layout
        scale = min(
            self.host.width / layout.virtual_width, self.host.height / layout.virtual_height
        )
        self._icon_px = max(8, round(8 * scale))  # menu icons are drawn 8 layout units wide
        theme = self._theme()
        self._ui_backend = PygameBattleUiBackend(
            self.host.screen,
            scale=scale,
            resolve_icon=self._resolve_icon,
            resolve_skin=self.host.skin_image,
            font_name=self.host.skin_font(theme.font_asset_id),
            font_scale=theme.font_scale,
            # party card portraits load, fit and cache like the dialogue box's
            resolve_portrait=getattr(self.host, "dialogue_portrait", None),
        )
        self._ui_backend.vfx_drawer = self._draw_vfx
        self.renderer = BattleUiRenderer(self._ui_backend, theme)
        # the command menu fits names and costs by the widths this backend draws
        self.screen.composer.text_width = self._text_width
        self.textures = PygameTextureDrawer(self.host, self.resolver, scale)
        self.audio_cues.clear()
        self._cursor = self._clock = self._last_impact = 0.0
        self._schedule = []
        self._shown_down = {}
        self._warm_textures(combatants)
        self._start_boss_intro(game, layout)

    def _text_width(self, text, role):
        """``text`` in ``role`` as the battle UI backend draws it, in layout units."""
        backend = self._ui_backend
        drawn = backend._text_image(text, (255, 255, 255), self.renderer.theme.text_size(role))
        image = drawn[0] if isinstance(drawn, tuple) else drawn
        return image.get_width() / backend.scale

    def _warm_textures(self, combatants):
        """Load every picture the fight can show now, not in the middle of an animation: the
        combatants' sheets (long strips take a few frames to decode) and the effect sheets."""

        kernels.active()  # the particle kernels import on first use (about 60 ms)
        uris = set()
        for visual in combatants:
            try:
                uris.add(self.resolver.source_uri(visual.sprite_sheet_asset_id))
            except (KeyError, BattleVisualError):
                continue
        for asset in self.host.game.project.assets.query("sprite_sheet", tags={"vfx"}):
            try:
                uris.add(self.resolver.source_uri(asset.asset_id))
            except (KeyError, BattleVisualError):
                continue
        for uri in uris:
            try:
                self.host.load_image(uri)
            except Exception:  # noqa: BLE001 - a missing picture is reported when it is drawn
                continue

    def upcoming_images(self):
        """Pictures the next fight is likely to show, most likely first (the host loads them
        ahead in the field): the party's battle sheets, the battle background, the sheets of the
        foes on this map, the effect sheets, then every other combatant's sheet."""

        game = self.host.game
        project = game.project
        library = project.battle_presentation_library
        encounters = project.rpg_database.encounters
        profiles = library.ids("combatant_visuals")

        def sheets(keys):
            return [
                self._sheet_uri(
                    library.require("combatant_visuals", key).assets.battlefield_asset_id
                )
                for key in keys
                if key in profiles
            ]

        foes = []
        for _entity, spec in game.scene.query(VisibleEncounterComponent):
            encounter = encounters.get(spec.encounter_id)
            foes += [m.enemy_id for m in encounter.members] if encounter is not None else []
        uris = [
            *sheets(game.save.rpg_state.party_active_actor_ids),
            game._area_battle_background(),
            self.host.manifest.get("battle", {}).get("background", ""),
            *sheets(foes),
            *(
                self._sheet_uri(a.asset_id)
                for a in project.assets.query(SPRITE_SHEET_KIND, tags={"vfx"})
            ),
            *sheets(profiles),
        ]
        return [uri for uri in dict.fromkeys(uris) if uri]

    def _sheet_uri(self, asset_id):
        try:
            asset = self.host.game.project.assets.resolve(str(asset_id))
        except KeyError:
            return ""
        return asset.source.uri if asset.kind == SPRITE_SHEET_KIND else ""

    # -- boss intro camera (CAM-02) ---------------------------------------------------------------
    BOSS_INTRO = {"zoom": 1.35, "blend": 0.5, "hold": 0.9}

    # -- log translation --------------------------------------------------
    # -- presentation timeline ------------------------------------------------
    # Battle Core resolves actions instantly; the presentation replays them in
    # order on its own clock. Each choreography step is emitted into the
    # coordinator only when it is due, so presentation events stay in
    # increasing sequence order for every downstream runtime.

    # -- projects without battle art: generated combatant and effect sheets -----------------------
    FRAME_HEIGHT = 96

    _ROW_ROLES = ("action_selected", "action_entry", "action_disabled")


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
