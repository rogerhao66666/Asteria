"""One frame of the battle screen: updating and drawing what the presentation shows."""

from __future__ import annotations

from asteria.presentation.battle.action_menu import BattleActionEntry
from asteria.presentation.visuals.character_composition import CharacterComposition
from asteria.presentation.visuals.particles import ParticleSystem, effect_definition
from asteria.runtime.battle.commands import COMMAND_WORDS
from asteria.runtime.battle.presentation_parts import _WorldThenUi
from asteria.runtime.battle.visuals import (
    BattleVisualError,
    vfx_content_center,
    vfx_keyframe,
    vfx_placement,
    vfx_rect,
)
from asteria.runtime.scene.camera import Camera2D


class BattleFrameMixin:
    """One frame of the battle screen: updating and drawing what the presentation shows."""

    # defaults until something sets them (code may read them first)
    _background_cache = None
    _background_image = None
    _camera_view = None
    _hit_stop = 0.0
    camera_director = None

    # -- frame --------------------------------------------------------------
    def _start_hit_stop(self, duration):
        """Freeze the action for ``duration`` seconds at an impact (BTL-04 hit-stop)."""
        self._hit_stop = max(self._hit_stop, float(duration))

    def update(self, dt):
        if not self._ensure():
            return
        game = self.host.game
        dt = float(dt)
        frozen = min(dt, self._hit_stop)
        if frozen > 0:
            self._hit_stop -= frozen
            dt -= frozen  # the presentation clock and animations hold during hit-stop
        self._clock += dt
        self._release_due()
        director = self.camera_director
        if director is not None:
            self._camera_view = self._clamped_view(
                director, director.update(dt, (*self._camera_center, 1.0))
            )

        # names and captions over heads wait while the camera is zoomed in (a boss intro, a
        # close-up) and while actions play: a growing or lunging figure would run under them
        view = self._camera_view
        self.screen.overhead_hidden = (view is not None and view[2] > 1.001) or self.busy()
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
                reason = ""
                if wait:
                    key = "battle.reason.cooldown_one" if wait == 1 else "battle.reason.cooldown"
                    english = "Ready in {turns} turn" + ("" if wait == 1 else "s")
                    reason = game.tr(key, english, turns=wait)
                entries.append(
                    BattleActionEntry(
                        ability_id, label, order=i, enabled=not wait, disabled_reason=reason
                    )
                )
            capture = game.capture_targets() if skills else ()
            if capture:
                best = max(chance for _, chance, _ in capture)
                label = game.tr(
                    "battle.capture_row", "X  Capture ({chance}%)", chance=f"{best * 100:.0f}"
                )
                entries.append(BattleActionEntry("capture", label, order=len(entries)))
            if skills and game.rules.boost_enabled and game.max_boost_level(actor) > 0:
                amount = game.battle.battle_resources.current(actor, game.rules.boost_resource_id)
                label = game.rules.boost_resource_id.replace("_", " ").title()
                level = getattr(self.host, "_boost_level", 0)
                label = game.tr(
                    "battle.boost_key_row",
                    "B  Boost x{level} ({points} {amount})",
                    level=level + 1,
                    points=label,
                    amount=int(amount),
                )
                entries.append(BattleActionEntry("boost", label, order=len(entries)))
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
            height = self._body_height(visual)
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
        pages = self._command_pages()
        commands.pages = pages
        # the built-in command and menu names as the player reads them (the ids stay English)
        names = {name: commands.category_label(name) for name in COMMAND_WORDS}
        if actor is not None:  # the project's own skill groups (battle.group.<name>)
            names.update(
                {n: commands.category_label(n) for n in commands.custom_categories(actor)}
            )
        self.screen.category_names = names
        if pages is not None and menu.policy.page_size != pages.page_size:
            from dataclasses import replace

            menu.policy = replace(menu.policy, page_size=pages.page_size)
        if actor is None:
            menu.show((), "Skills", 0)
            feedback.target_ids, feedback.primary_target_id = (), None
            return
        if commands.mode == "command":
            # Every category's rows, each built once; the open category's rows are among them.
            groups = commands.command_rows(actor)
            if commands.category in groups:
                count = len(groups[commands.category])
                commands.cursor = min(commands.cursor, max(0, count - 1))
            else:
                commands.entries(actor)  # keeps the cursor on a row of the open category
            everything = [row for rows in groups.values() for row in rows]
            menu.show(everything, commands.category, commands.cursor)
            feedback.target_ids, feedback.primary_target_id = (), None
            return
        rows = commands.entries(actor)
        if commands.mode == "root":
            menu.show(rows, "Command", commands.cursor)
        else:
            menu.show(rows, rows[0].category if rows else "Target", commands.cursor)
        target = commands.selected_target(actor)
        feedback.target_ids, feedback.primary_target_id = (
            ((target,), target) if target else ((), None)
        )

    def _background(self):
        """The battle background image, or a plain backdrop when the project has none."""
        cached = self._background_image
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
        cx, cy, zoom = self._camera_view or (
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
            self._scaled_background(background, size), (round(bx * scale), round(by * scale))
        )
        textures = self.textures if self.screen.scene.combatants else None
        self._view_camera = self.screen.camera_feedback.camera_view(base)
        self._ui_backend.screen = self.host.screen  # the world layer, until the textures are drawn
        world_then_ui = _WorldThenUi(self, textures)
        composer = self.screen.composer
        menu_layout = getattr(self.host, "menu_layout", None)
        composer.screen_layout = None if menu_layout is None else menu_layout("battle")
        if composer.screen_layout is None and getattr(self.host, "_menu_preview", False):
            from asteria.presentation.screens.menu_layout import MenuLayout

            composer.screen_layout = MenuLayout("battle", ())  # the editor: boxes, same look
        result = self.screen.render(
            base, ui_renderer=self.renderer, texture_renderer=world_then_ui
        )
        if not world_then_ui.done:
            world_then_ui.finish()
        if composer.layout_boxes:  # in screen pixels, as the menus' (the editor reads them)
            ui = self._ui_backend.scale
            host = self.host
            if not isinstance(getattr(host, "_menu_boxes", None), dict):
                host._menu_boxes = {}
            host._menu_boxes["battle"] = {
                k: tuple(round(v * ui) for v in box) for k, box in composer.layout_boxes.items()
            }
            if not isinstance(getattr(host, "_menu_units", None), dict):
                host._menu_units = {}
            host._menu_units["battle"] = ui  # the screen pixels of one battle unit
        self.audio_cues.extend(result.audio_cues)
        self._pointer_spots(result.frame)
        return result

    def _pointer_spots(self, frame):
        """The command menu's rows (and in target choosing, the combatants) as mouse hotspots
        (D85): pointing moves the cursor, a click is Enter, a click on the categories Tab."""
        host, commands = self.host, getattr(self.host, "battle_commands", None)
        if commands is None or not hasattr(host, "hotspot"):
            return
        box = next((p for p in frame.panels if p.panel_id == "action_menu"), None)
        if box is None:
            return
        ui, menu = self._ui_backend.scale, self.screen.action_menu
        first = menu.view.page * menu.policy.page_size
        height = self.screen.composer.polish.interaction_row_height

        def spot(x, y, w, h):
            return x * ui, y * ui, w * ui, h * ui

        for text in frame.texts:
            if text.role == "action_categories":
                host.hotspot(spot(box.x, text.y - 2, box.width, height), key="tab")
        rows = [t for t in frame.texts if t.role in self._ROW_ROLES]
        for index, text in enumerate(rows):
            host.hotspot(
                spot(box.x, text.y - 2, box.width, height),
                lambda row=first + index: setattr(commands, "cursor", row),
            )
        if commands.mode != "target":
            return
        for index, entry in enumerate(menu.view.entries):
            place = self.member_screen_box(entry.action_id)
            if place is not None:  # the combatant itself: its body, a little wider than tall
                x, top, feet = place
                half = max(16.0, (feet - top) * 0.4)
                pick = lambda row=first + index: setattr(commands, "cursor", row)  # noqa: E731
                host.hotspot((x - half, top, 2 * half, feet - top), pick)

    def _scaled_background(self, background, size):
        """The battlefield picture at ``size``: scaled once while the camera holds still (it was
        smoothed again every frame), in the screen's pixel format (a quicker blit)."""
        cached = self._background_cache
        if cached is not None and cached[0] is background and cached[1] == size:
            return cached[2]
        pg = self.host.pg
        scaled = pg.transform.smoothscale(background, size)
        if pg.display.get_surface() is not None:
            # fully opaque (the usual battlefield): no alpha to blend, the same pixels
            opaque = (
                not scaled.get_flags() & pg.SRCALPHA
                or pg.mask.from_surface(scaled, 254).count() == size[0] * size[1]
            )
            scaled = scaled.convert() if opaque else scaled.convert_alpha()
        self._background_cache = (background, size, scaled)
        return scaled

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
        height = self._body_height(visual)  # the figure, not the whole frame: effects land on it
        meta = self.resolver.sheet_meta(asset_id)
        placement = vfx_placement(meta, payload)
        # a swing or a claw drawn travelling right turns round for a target standing on the left,
        # where the blow comes from the right (``face_attacker`` on the sheet or in the beat)
        face = payload.get("face_attacker", meta.get("face_attacker", False))
        flip = bool(face) and getattr(visual.anchor, "facing", "") == "right"
        content = self._vfx_content(asset_id, sheet, clip)
        if flip:
            content = (-content[0], content[1])
        x, y, width, tall = vfx_rect(
            placement, visual.anchor.x, visual.anchor.y, height, frame.width, frame.height, content
        )
        cx, cy = self._view_camera.world_to_screen(x, y)
        self.textures.blit_region(
            asset_id,
            (frame.x, frame.y, frame.width, frame.height),
            cx - width / 2,
            cy - tall / 2,
            width,
            tall,
            **({"flip_x": True} if flip else {}),
            opacity=placement["opacity"],
            blend=placement["blend"],
        )

    def _vfx_content(self, asset_id, sheet, clip):
        """Where the clip's picture sits inside its frames (``vfx_content_center``), measured
        once per sheet from the drawn pixels."""
        cache = self._vfx_content_cache
        if asset_id not in cache:
            boxes = []
            try:
                resolver = self.resolver
                image = (  # a sheet drawn in memory (generated effects) has no file
                    resolver.generated_image(asset_id)
                    if resolver.is_generated(asset_id)
                    else self.host.load_image(resolver.source_uri(asset_id))
                )
                for keyframe in clip.keyframes:
                    f = sheet.frames[keyframe.frame_index]
                    rect = image.subsurface((f.x, f.y, f.width, f.height)).get_bounding_rect()
                    if rect.width and rect.height:
                        boxes.append((rect.left, rect.top, rect.right, rect.bottom))
            except Exception as exc:  # pygame.error / a frame outside the image
                if type(exc).__name__ not in ("error", "ValueError", "FileNotFoundError"):
                    raise
            first = sheet.frames[0]
            cache[asset_id] = vfx_content_center(boxes, first.width, first.height)
        return cache[asset_id]

    def _draw_particle_cue(self, effect, definition, payload):
        systems = self._cue_particles
        # a cue is replaced every frame as it ages: key it by what stays the same
        key = (getattr(effect, "sequence", 0), getattr(effect, "cue_id", ""), effect.member_id)
        entry = systems.get(key)
        try:
            visual = self.screen.scene.visual_for(effect.member_id)
            height = self._body_height(visual)
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
