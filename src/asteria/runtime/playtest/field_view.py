"""The field: camera, effects, tile view, skeletons, normals, compositions and the map draw."""

from __future__ import annotations

from pathlib import Path

from asteria.core import Transform
from asteria.graphics.scaling import resized
from asteria.presentation.motion_fx import EchoSettings, MotionEchoes
from asteria.runtime.battle_visuals import vfx_rect
from asteria.runtime.field_camera import (
    FieldViewCamera,
    scene_camera_follow,
)
from asteria.runtime.field_presentation import (
    FieldEffects,
)

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class FieldViewMixin:
    @property
    def field_camera(self):
        """Field view camera (CAM-02); identity unless an event focuses or shakes it."""
        camera = getattr(self, "_field_camera", None)
        if camera is None:
            scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
            follow = self.manifest["field"].get("camera", {}).get("follow")
            from asteria.runtime.tile_scene_view import TileSceneView

            scene = self.game.scene
            if not follow and not TileSceneView.available(scene):
                # a picture field follows the scene's own Camera entity, as authored in the
                # editor (a tile scene has a camera of its own)
                follow = scene_camera_follow(scene, self.width / scale)
            camera = self._field_camera = FieldViewCamera(
                self.width, self.height, scale, follow=follow
            )
        return camera

    @property
    def field_effects(self):
        """Screen fades and field VFX started by event programs (EVT-02 / EVT-04)."""
        effects = getattr(self, "_field_effects", None)
        if effects is None:
            effects = self._field_effects = FieldEffects()
        return effects

    def _field_vfx_content(self, asset_id, sheet, frames, fw, fh, columns):
        """Where a field VFX clip's picture sits inside its frames (source pixels), once."""
        from asteria.runtime.battle_visuals import vfx_content_center

        cache = self.__dict__.setdefault("_field_vfx_content_cache", {})
        if asset_id not in cache:
            boxes = []
            for index in frames:
                area = ((index % columns) * fw, (index // columns) * fh, fw, fh)
                try:
                    rect = sheet.subsurface(area).get_bounding_rect()
                except ValueError:  # a frame outside the sheet
                    continue
                if rect.width and rect.height:
                    boxes.append((rect.left, rect.top, rect.right, rect.bottom))
            cache[asset_id] = vfx_content_center(boxes, fw, fh)
        return cache[asset_id]

    def _draw_field_effects(self):
        scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
        tiles = self.tile_view
        # screen pixels per world unit, and the world -> screen mapping of the scene being shown
        # (a tile scene has its own camera)
        pixels = tiles.camera.zoom if tiles is not None else scale * self.field_camera.zoom
        to_screen = self._field_screen_xy
        for effect in self.field_effects.vfx:
            asset = self.game.project.assets.resolve(effect.asset_id)
            meta = asset.meta()
            frames = meta["clips"]["play"]["frames"]
            fw, fh = meta["frame_size"]
            sheet = self.load_image(asset.source.uri)
            columns = max(1, sheet.get_width() // fw)
            index = frames[FieldEffects.keyframe(effect, len(frames))]
            if effect.entity_id is not None:
                entity = self.game.scene.get_entity(effect.entity_id)
                if entity is None:
                    continue
                t = entity.get(Transform)
                ax, ay = t.x, t.y
            else:
                ax, ay = effect.x, effect.y
            cx, cy = self._field_vfx_content(effect.asset_id, sheet, frames, fw, fh, columns)
            x, y, w, h = vfx_rect(
                effect.placement,
                ax,
                ay,
                FIELD_BODY_HEIGHT,
                fw / scale,
                fh / scale,
                (cx / scale, cy / scale),
            )
            sx, sy = to_screen(x, y)
            size = (max(1, round(w * pixels)), max(1, round(h * pixels)))
            image = resized(
                self.pg,
                sheet.subsurface(((index % columns) * fw, (index // columns) * fh, fw, fh)),
                size,
            )
            if effect.placement["opacity"] < 1.0:
                image.set_alpha(int(effect.placement["opacity"] * 255))
            flags = self.pg.BLEND_RGB_ADD if effect.placement["blend"] == "add" else 0
            self.screen.blit(
                image, (round(sx - size[0] / 2), round(sy - size[1] / 2)), special_flags=flags
            )
        systems = [p.system for p in self.field_effects.all_particles()]
        if systems:
            with self.profiler.section("vfx"):
                self.particles_drawn = self.particle_drawer.draw(
                    self.screen,
                    systems,
                    to_screen,
                    pixels,
                    image=self.particle_image,
                )
        self.world_done("field")
        alpha = self.field_effects.fade_alpha
        if alpha > 0:
            shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
            shade.fill((*self.field_effects.fade_color, int(alpha * 255)))
            self.screen.blit(shade, (0, 0))
        if self.game.cutscene_active:  # letterbox while a cutscene runs
            bar = int(self.height * 0.09)
            self.pg.draw.rect(self.screen, (0, 0, 0), (0, 0, self.width, bar))
            self.pg.draw.rect(self.screen, (0, 0, 0), (0, self.height - bar, self.width, bar))
            if self.game.cutscene_skippable:
                self.text(
                    self.game.tr("field.skip_cutscene", "Esc: skip"),
                    self.width - 130,
                    self.height - bar + 8,
                    size=18,
                    color=(190, 200, 215),
                )

    @property
    def tile_view(self):
        """The tile-map scene view (D22 A10) when the current scene is bound to a TileMap2D,
        else None."""
        from asteria.runtime.tile_scene_view import TileSceneView

        scene = self.game.scene
        # whether a scene is a tile scene is looked up once per scene, not per entity per frame
        known = self.__dict__.get("_tile_scene")
        if known is None or known[0] is not scene:
            known = self._tile_scene = (scene, TileSceneView.available(scene))
        if not known[1]:
            return None
        view = getattr(self, "_tile_view", None)
        if view is not None and view.session is not self.game:
            view = None  # a loaded save is a new session: the old view still holds the old one
        if view is None:
            view = self._tile_view = TileSceneView(
                self.game, self.resource_root, self.width, self.height, self.pg
            )
            field = self.manifest.get("field", {})
            if field.get("jump_shadow"):  # drawn under a player hopping a ledge
                view.jump_shadow = self.load_image(field["jump_shadow"])
                view.jump_shadow_offset = float(field.get("jump_shadow_offset", 4.0))
        elif view.scene_id != scene.id:
            view.load()
        if self._multiplayer_connected():
            # Network snapshots already choose each guest's own class appearance.
            if not hasattr(view, "_offline_class_looks"):
                view._offline_class_looks = view._apply_class_looks
                view._apply_class_looks = lambda: None
        elif not getattr(self, "_authoritative_project_mode", False) and hasattr(
            view, "_offline_class_looks"
        ):
            view._apply_class_looks = view._offline_class_looks
            del view._offline_class_looks
        return view

    def _field_screen_xy(self, world_x, world_y):
        view = self.tile_view
        if view is not None:
            return view.world_to_screen(world_x, world_y)
        return self.field_camera.world_to_screen(world_x, world_y)

    def _field_world_xy(self, screen_x, screen_y):
        """The world point under a screen pixel (inverse of the field's affine view)."""
        ox, oy = self._field_screen_xy(0.0, 0.0)
        ax, ay = self._field_screen_xy(1.0, 0.0)
        bx, by = self._field_screen_xy(0.0, 1.0)
        a, c, b, d = ax - ox, ay - oy, bx - ox, by - oy  # screen = origin + x*(a, c) + y*(b, d)
        det = a * d - b * c
        if abs(det) < 1e-12:
            return screen_x - ox, screen_y - oy
        dx, dy = screen_x - ox, screen_y - oy
        return (d * dx - b * dy) / det, (a * dy - c * dx) / det

    def _asset_source_path(self, asset_id, kind):
        record = self.project.assets.get(str(asset_id))
        if record is not None:
            if record.kind != kind:
                return None
            uri = record.source_path
        else:
            try:
                asset = self.project.assets.resolve(str(asset_id))
            except KeyError:
                return None
            if asset.kind != kind:
                return None
            uri = asset.source.uri
        path = Path(uri)
        return path if path.is_absolute() else self.resource_root / path

    def _skeleton_sheet(self, asset_id):
        from asteria.reference_data import load_sprite_sheet

        if asset_id not in self._skeleton_sheet_cache:
            path = self._asset_source_path(asset_id, "sprite_sheet")
            if path is None:
                return None
            self._skeleton_sheet_cache[asset_id] = load_sprite_sheet(path)
        return self._skeleton_sheet_cache[asset_id]

    def _draw_skeleton_entities(self):
        if self.tile_view is not None:
            return
        scale = float(self.manifest["field"].get("world_to_screen_scale", 3.0))
        runtime = self

        class Camera:
            zoom = scale * runtime.field_camera.zoom

            @staticmethod
            def world_to_screen(x, y):
                return runtime._field_screen_xy(x, y)

        for entity in self.game.scene.entities():
            try:
                draws = self._skeleton_scene_runtime.draw_entity(
                    entity, Camera(), self._skeleton_sheet
                )
                for draw in draws:
                    path = self._asset_source_path(draw.texture_asset_id, "texture")
                    if path is None:
                        continue
                    image = self.load_image(path)
                    image = image.subsurface(self.pg.Rect(draw.source)).copy()
                    image = resized(self.pg, image, (round(draw.width), round(draw.height)))
                    if draw.flip_x:
                        image = self.pg.transform.flip(image, True, False)
                    if draw.rotation_deg:
                        image = self.pg.transform.rotate(image, -draw.rotation_deg)
                    if draw.opacity < 1:
                        image.set_alpha(round(255 * draw.opacity))
                    center = (
                        round(draw.screen_x + draw.width / 2),
                        round(draw.screen_y + draw.height / 2),
                    )
                    self.screen.blit(image, image.get_rect(center=center))
            except (OSError, TypeError, ValueError, KeyError):
                continue

    def _player_frame(self, facing, moving):
        sheet = self.load_image(self.manifest["field"]["player_sheet"])
        fw, fh = self.manifest["field"]["player_frame_size"]
        row = walking_row_index(facing)
        col = walking_pattern_index(self._field_step) if moving else 1
        return sheet.subsurface((col * fw, row * fh, fw, fh))

    def _interaction_candidate(self):
        try:
            return self.game.interaction.query.nearest(
                self.game.scene, self.game.player, self.game.facing
            )
        except Exception:
            return None

    def _normal_image(self, image_path):
        """The normal map for an image, from its canonical asset's ``material.normal_asset_id`` (or
        None)."""
        cache = self.__dict__.setdefault("_normal_images", {})
        if image_path not in cache:
            normal = None
            for asset in self.project.assets.snapshot():
                if asset.source.uri != image_path:
                    continue
                normal_id = dict(asset.meta().get("material") or {}).get("normal_asset_id")
                if normal_id:
                    try:
                        normal = self.load_image(self.project.assets.resolve(normal_id).source.uri)
                    except KeyError:
                        normal = None
                break
            cache[image_path] = normal
        return cache[image_path]

    def _begin_normals(self):
        """Prepare a flat normal layer when last frame's environment lit the world on the GPU."""
        if self.gpu is None or not getattr(self, "_lit_last_frame", False):
            self._normal_layer_active = False
            return
        if getattr(self, "_normal_layer", None) is None or self._normal_layer.get_size() != (
            self.width,
            self.height,
        ):
            self._normal_layer = self.pg.Surface((self.width, self.height), 0, 32)
        self._normal_layer.fill((128, 128, 255))
        self._normal_layer_active = True

    def _blit_normal(self, image_path, source_rect, size, position):
        """Draw the normal-map frame matching a world sprite blit (same source rect, size and
        place)."""
        if not getattr(self, "_normal_layer_active", False):
            return
        normal = self._normal_image(image_path)
        if normal is None:
            return
        frame = normal.subsurface(source_rect) if source_rect is not None else normal
        self._normal_layer.blit(resized(self.pg, frame, tuple(size)), position)

    def _blit_with_trail(self, entity, image, position):
        """Blit a field sprite; with MotionTrail2D, fading echoes of earlier positions go behind it
        (VFX-03)."""
        from asteria.runtime.environment2d import MotionTrail2DComponent

        trail = entity.try_get(MotionTrail2DComponent)
        if trail is not None and trail.enabled:
            echoes = self.__dict__.setdefault("_field_echoes", MotionEchoes())
            settings = EchoSettings.of(
                trail.kind,
                interval=trail.interval,
                count=trail.count,
                fade=trail.fade,
                lifetime=trail.lifetime,
            )
            echo = echoes.get(entity.id, settings)
            t = entity.get(Transform)
            last = self.__dict__.setdefault("_trail_last_xy", {}).get(entity.id)
            moving = last is not None and (abs(t.x - last[0]) + abs(t.y - last[1])) > 1e-3
            self._trail_last_xy[entity.id] = (t.x, t.y)
            for ghost_image, ghost_position, opacity in (
                (img, pos, a) for (img, pos), a in echo.ghosts(self._clock_seconds)
            ):
                ghost = ghost_image.copy()
                ghost.set_alpha(int(200 * opacity))
                self.screen.blit(ghost, ghost_position)
            echo.record(
                self._clock_seconds,
                (image, position),
                moving=moving or not trail.only_while_moving,
            )
        self.screen.blit(image, position)

    def _field_composition(self, image_path):
        """CharacterComposition of the canonical sprite-sheet asset whose image is ``image_path``
        (CMP-01)."""
        cache = self.__dict__.setdefault("_field_compositions", {})
        if image_path not in cache:
            from asteria.presentation.character_composition import CharacterComposition

            composition = None
            for asset in self.project.assets.snapshot():
                if asset.source.uri == image_path and asset.kind == "sprite_sheet":
                    composition = CharacterComposition.from_meta(asset.meta())
                    break
            cache[image_path] = composition
        return cache[image_path]

    def _composition_parts(self, image_path, frame_index, clip, frame_size, render_size, position):
        """``(behind, front)`` lists of ``(surface, position)`` for a field sprite's layers and
        attachments."""
        composition = self._field_composition(image_path)
        if composition is None:
            return (), ()
        scale = render_size[0] / frame_size[0]
        pivot = (
            position[0] + render_size[0] / 2,
            position[1] + render_size[1],
        )  # feet: bottom centre
        behind, front = [], []
        for part in composition.parts(clip, frame_index):
            try:
                asset = self.project.assets.resolve(part.asset_id)
            except KeyError:
                continue
            meta = asset.meta()
            fw, fh = meta.get("frame_size", frame_size)
            sheet = self.load_image(asset.source.uri)
            columns = max(1, sheet.get_width() // fw)
            index = part.frame_index % max(1, columns * max(1, sheet.get_height() // fh))
            image = sheet.subsurface(((index % columns) * fw, (index // columns) * fh, fw, fh))
            size = (
                max(1, round(fw * part.scale_x * scale)),
                max(1, round(fh * part.scale_y * scale)),
            )
            image = resized(self.pg, image, size)
            if part.rotation_deg:
                image = self.pg.transform.rotate(image, -part.rotation_deg)
            if part.opacity < 1.0:
                image.set_alpha(int(part.opacity * 255))
            if part.kind == "layer":
                x, y = position[0] + part.x * scale, position[1] + part.y * scale
            else:
                x, y = pivot[0] + part.x * scale, pivot[1] + part.y * scale
            (behind if part.behind else front).append((image, (round(x), round(y))))
        return behind, front

    def _prune_field_echoes(self):
        echoes = self.__dict__.get("_field_echoes")
        if echoes is None:
            return
        alive = {e.id for e in self.game.scene.entities() if e.enabled}
        echoes.prune(alive)  # entity removed / hidden / another scene: its echoes go too

    def _draw_field(self, moving=False):
        self._begin_normals()
        self._prune_field_echoes()
        zoom = self.field_camera.zoom
        settings = self.game.combat_scene
        tiles = self.tile_view
        if tiles is not None:
            hud = self.action_hud if self.game.action_scene else None
            tiles.draw(self.screen, flash=hud.flash if hud is not None else ())
            self._draw_field_overlays()
            return
        if (
            settings is not None and settings.background_color
        ):  # a block-out level: a flat colour, no field image
            color = settings.background_color.lstrip("#")
            self.screen.fill(tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)))
        else:
            bg = self.load_image(self.manifest["field"]["background"])
            bx, by, bw, bh = self.field_camera.background_rect()
            self.screen.blit(
                self.pg.transform.smoothscale(bg, (round(bw), round(bh))), (round(bx), round(by))
            )

        sprites = self.manifest["field"].get("entity_sprites", {})
        from asteria.runtime.field_ai import FieldAIComponent, VisibleEncounterComponent

        for entity in self.game.scene.entities():
            if not entity.enabled:
                continue  # hidden / relocated NPCs (WLD-02) and disabled entities are not drawn
            spec = sprites.get(entity.name)
            if (
                spec is None
                and entity is not self.game.player
                and entity.has(Transform)
                and (entity.has(FieldAIComponent) or entity.has(VisibleEncounterComponent))
            ):
                # Field enemies without a manifest sprite still need to be visible.
                et = entity.get(Transform)
                ex, ey = self._field_screen_xy(et.x, et.y)
                self.pg.draw.circle(self.screen, (200, 70, 80), (int(ex), int(ey)), int(14 * zoom))
                self.pg.draw.circle(
                    self.screen, (255, 230, 230), (int(ex), int(ey)), int(14 * zoom), 2
                )
                continue
            if spec is None or entity is self.game.player:
                continue
            et = entity.get(Transform)
            ex, ey = self._field_screen_xy(et.x, et.y)
            w, h = (v * zoom for v in spec.get("size", (96, 112)))
            size = (int(w), int(h))
            image = self._scaled.get(  # resized once per size, not once per frame
                (spec["sprite"], size),
                lambda rel=spec["sprite"], size=size: resized(self.pg, self.load_image(rel), size),
            )
            position = (int(ex - w / 2), int(ey - h + 12 * zoom))
            self._blit_with_trail(entity, image, position)
            self._blit_normal(spec["sprite"], None, (int(w), int(h)), position)

        self._draw_skeleton_entities()
        pt = self.game.player.get(Transform)
        px, py = self._field_screen_xy(pt.x, pt.y)
        frame = self._player_frame(self.game.facing, moving)
        render_w, render_h = field_player_render_size(
            frame.get_size(), self.manifest["field"].get("player_render_width", 64) * zoom
        )
        # a painted or rendered walker asks for blended pixels (player_scaling "smooth"),
        # pixel art for a sharp grid; either way each step is resized once per size
        smooth = self.manifest["field"].get("player_scaling") == "smooth"
        step = walking_pattern_index(self._field_step) if moving else 1
        pf = self._scaled.get(
            ("player", self.game.facing, step, render_w, render_h, smooth),
            lambda: resized(self.pg, frame, (render_w, render_h), smooth=smooth),
        )
        position = (int(px - render_w / 2), int(py - render_h + 10 * zoom))
        sheet_path = self.manifest["field"]["player_sheet"]
        fw, fh = self.manifest["field"]["player_frame_size"]
        sheet_columns = max(1, self.load_image(sheet_path).get_width() // fw)
        frame_index = walking_row_index(self.game.facing) * sheet_columns + (
            walking_pattern_index(self._field_step) if moving else 1
        )
        clip = f"{'walk' if moving else 'idle'}_{self.game.facing}"
        behind, front = self._composition_parts(
            sheet_path, frame_index, clip, (fw, fh), (render_w, render_h), position
        )
        for image, at in behind:
            self.screen.blit(image, at)
        self._blit_with_trail(self.game.player, pf, position)
        for image, at in front:
            self.screen.blit(image, at)
        if (
            getattr(self, "_normal_layer_active", False)
            and self._normal_image(sheet_path) is not None
        ):
            fw, fh = self.manifest["field"]["player_frame_size"]
            row = walking_row_index(self.game.facing)
            col = walking_pattern_index(self._field_step) if moving else 1
            self._blit_normal(
                sheet_path, (col * fw, row * fh, fw, fh), (render_w, render_h), position
            )
        self._draw_field_overlays()
