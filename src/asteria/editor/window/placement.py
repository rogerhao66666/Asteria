"""Putting things on the map: characters, prefabs, tile layers and region rules, and the views
the Scene panels show for them."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from asteria.assets.kinds.character_visual import CharacterVisualSet
from asteria.core.prefab import PrefabError, PrefabInstanceComponent
from asteria.editor.project.workspace import WorkspaceMode
from asteria.editor.scene.create_character import CreateCharacterCommand
from asteria.editor.scene.place_character import DefaultAppearance, build_place_character_command

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QTransform
    from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMainWindow
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.editor.assets.resource_resolver import resolve_project_resources
from asteria.editor.project.authoring_context import scene_authoring_source
from asteria.editor.scene.tile_edit import (
    AddTileLayerCommand,
    RemoveTileLayerCommand,
    ReorderTileLayerCommand,
    SetTileLayerPropertyCommand,
    TileEditError,
)
from asteria.graphics import TileLayer


class PlacementMixin:
    """Putting things on the map."""

    # defaults until something sets them (code may read them first)
    _pending_character_name = None
    _pending_character_visual = None
    _placement_status_widget = None
    tool_strip = None

    def begin_character_placement(self, visual, status_widget=None, ghost=None):
        """Switch to Scene and wait for one map-cell click to place a ``CharacterVisualSet``;
        ``ghost`` (a QPixmap of the character) rides under the mouse until then."""
        status_widget = status_widget or self._status_sink()
        bundle = visual
        project = self.document.project
        scene = self.viewport.current_scene()
        if project is None or scene is None:
            status_widget.status.setText(
                "Open a project and select a scene before creating a character"
            )
            return None
        self._pending_character_visual = bundle
        self._placement_status_widget = status_widget
        self.workspace.set_mode(WorkspaceMode.SCENE)
        self.viewport.begin_character_placement(ghost)
        self._strip_sync("character")
        status_widget.status.setText("Click a map cell to place this character (Escape cancels)")
        return bundle

    def _strip_sync(self, mode=None):
        strip = self.tool_strip
        if strip is not None:
            strip.sync(mode or self.viewport.tile_tools.mode)

    def cancel_character_placement(self):
        """Forget the character waiting to be placed (Escape over the map)."""
        if self._pending_character_visual is None:
            return
        self._pending_character_visual = None
        self._placement_status_widget = None
        self.viewport.end_character_placement()
        self._strip_sync()
        self.statusBar().showMessage("Character placement cancelled", 4000)

    def _status_sink(self):
        """Object with ``.status.setText`` that reports to the window status bar."""
        bar = self.statusBar()
        return SimpleNamespace(
            status=SimpleNamespace(setText=lambda text: bar.showMessage(text, 6000))
        )

    def place_default_character(self):
        """The tool strip's character tool (N): carry a character that looks like the scene's
        player to a cell and click; the actor and its map entity are made there. A project
        with no sprite sheet yet asks for a walking sheet instead."""
        from asteria.editor.records.pictures import sprite_sheet_frame
        from asteria.editor.scene.place_character import default_appearance, shown_frame

        project = self.document.project
        scene = self.viewport.current_scene()
        if project is None or scene is None:
            self.statusBar().showMessage("Open a project and a scene first", 6000)
            return None
        appearance = default_appearance(self.document, scene)
        if appearance is None:
            return self.place_character_from_sheet()
        self._pending_character_name = None  # named New Character, New Character 2...
        ghost = sprite_sheet_frame(
            self.document, appearance.sprite_sheet_asset_id, shown_frame(self.document, appearance)
        )
        if ghost is not None and appearance.flip_x:
            ghost = ghost.transformed(QTransform().scale(-1, 1))
        return self.begin_character_placement(appearance, self._status_sink(), ghost)

    def place_character_from_sheet(self, path=None, name=None):
        """Place a playable character from any 3x4 walking sheet (rows down/left/right/up).

        The sheet is copied next to a saved project so the project stays
        portable; for an unsaved project it is referenced where it is.
        """
        project = self.document.project
        if project is None:
            return None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Walking Sprite Sheet", "", "Images (*.png)"
            )
            if not path:
                return None
        if name is None:
            name, ok = QInputDialog.getText(self, "Character", "Name:", text=Path(path).stem)
            if not ok or not name.strip():
                return None
        source = Path(path)
        try:
            key = CharacterVisualSet.from_walking_sheet(source, key=name).key
            uri = source
            if self.document.file_path is not None:
                target = self.document.file_path.parent / "characters" / f"{key}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve():
                    shutil.copyfile(source, target)
                uri = target.relative_to(self.document.file_path.parent)
                source = target
            visual = CharacterVisualSet.from_walking_sheet(source, key=key, uri=uri)
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Cannot use sprite sheet: {exc}", 6000)
            return None
        self._pending_character_name = name.strip()
        frame_w, frame_h = visual.frame_size
        sheet = QPixmap(str(source))
        ghost = None if sheet.isNull() else sheet.copy(frame_w, 0, frame_w, frame_h)  # standing
        return self.begin_character_placement(visual, self._status_sink(), ghost)

    def set_actor_appearance(self, actor_id=None, sprite_sheet_asset_id=None):
        """Give an Actor a field sprite and push it onto every map entity linked to it."""
        from asteria.editor.scene.actor_appearance import apply_actor_appearance

        project = self.document.project
        if project is None:
            return False
        actors = project.rpg_database.actors
        if actor_id is None:
            labels = [f"{actors[a].display_name} ({a})" for a in sorted(actors)]
            if not labels:
                self.statusBar().showMessage("The project has no actors", 6000)
                return False
            label, ok = QInputDialog.getItem(self, "Actor Appearance", "Actor:", labels, 0, False)
            if not ok:
                return False
            actor_id = sorted(actors)[labels.index(label)]
        if sprite_sheet_asset_id is None:
            sheets = list(self.document.asset_views.sprite_sheet_ids())
            if not sheets:
                self.statusBar().showMessage("No sprite sheets are loaded", 6000)
                return False
            sprite_sheet_asset_id, ok = QInputDialog.getItem(
                self, "Actor Appearance", "Sprite sheet:", sheets, 0, False
            )
            if not ok:
                return False
        applied = apply_actor_appearance(self.document, actor_id, sprite_sheet_asset_id)
        self.refresh_all()
        return applied

    def _selected_entity(self):
        sel = self.document.selection
        if sel.multiple or sel.value is None:
            return None
        if sel.kind == "entity":
            return sel.value
        if sel.kind == "component":
            return sel.value.entity
        return None

    def _run_prefab_command(self, command, message):
        try:
            self.document.execute(command)
        except (PrefabError, ValueError, KeyError) as exc:
            self.statusBar().showMessage(f"Prefab: {exc}", 6000)
            return None
        self.statusBar().showMessage(message, 6000)
        self.refresh_all()
        return command

    def create_prefab_from_selection(self, prefab_id=None):
        from asteria.editor.scene.prefab_commands import CreatePrefabFromEntityCommand

        entity = self._selected_entity()
        if entity is None or self.document.project is None:
            self.statusBar().showMessage("Select one entity to make a prefab", 6000)
            return None
        if prefab_id is None:
            prefab_id, ok = QInputDialog.getText(
                self, "Create Prefab", "Prefab id:", text=entity.name.lower().replace(" ", "_")
            )
            if not ok or not prefab_id.strip():
                return None
        command = CreatePrefabFromEntityCommand(self.document.project, entity, prefab_id.strip())
        return self._run_prefab_command(command, f"Created prefab {prefab_id.strip()}")

    def place_prefab(self, prefab_id=None, x=None, y=None):
        from asteria.editor.scene.prefab_commands import InstantiatePrefabCommand

        project, scene = self.document.project, self.viewport.current_scene()
        if project is None or scene is None:
            return None
        if prefab_id is None:
            ids = list(project.prefabs.ids())
            if not ids:
                self.statusBar().showMessage("The project has no prefabs", 6000)
                return None
            prefab_id, ok = QInputDialog.getItem(self, "Place Prefab", "Prefab:", ids, 0, False)
            if not ok:
                return None
        if x is None or y is None:
            cx, cy = self.viewport.width() / 2, self.viewport.height() / 2
            x, y = self.viewport.camera.screen_to_world(cx, cy)
        command = InstantiatePrefabCommand(
            project, self.document.component_registry, scene, prefab_id, x, y
        )
        result = self._run_prefab_command(command, f"Placed {prefab_id}")
        if result is not None:
            self.document.select_entity(command.entity)
            self.refresh_all()
        return result

    def apply_instance_to_prefab(self):
        from asteria.editor.scene.prefab_commands import apply_instance_to_prefab_command

        entity = self._selected_entity()
        if entity is None or not entity.has(PrefabInstanceComponent):
            self.statusBar().showMessage("Select a prefab instance", 6000)
            return None
        command = apply_instance_to_prefab_command(
            self.document.project, self.document.component_registry, entity
        )
        return self._run_prefab_command(
            command, "Prefab updated; other instances kept their overrides"
        )

    def revert_instance_to_prefab(self):
        from asteria.editor.scene.prefab_commands import RevertInstanceCommand

        entity = self._selected_entity()
        if entity is None or not entity.has(PrefabInstanceComponent):
            self.statusBar().showMessage("Select a prefab instance", 6000)
            return None
        command = RevertInstanceCommand(
            self.document.project, self.document.component_registry, entity
        )
        return self._run_prefab_command(command, f"{entity.name} matches its prefab again")

    def _place_character_at(self, cell):
        """Commit the pending ``CharacterVisualSet`` at the map cell clicked in Scene."""
        visual = self._pending_character_visual
        if visual is None:
            return None
        project = self.document.project
        scene = self.viewport.current_scene()
        status_widget = self._placement_status_widget or self._status_sink()
        if project is None or scene is None:
            self.viewport.end_character_placement()
            self._strip_sync()
            self._pending_character_visual = None
            self._placement_status_widget = None
            status_widget.status.setText("Character placement cancelled: no active scene")
            return None
        cell = (int(cell[0]), int(cell[1]))
        try:
            if isinstance(visual, DefaultAppearance):  # the tool strip's character
                command = build_place_character_command(
                    project,
                    scene,
                    cell,
                    visual,
                    display_name=self._pending_character_name,
                    tile_size=self.viewport._tile_size(),
                )
            else:
                command = CreateCharacterCommand(
                    visual,
                    project,
                    scene,
                    cell,
                    display_name=self._pending_character_name,
                    tile_size=self.viewport._tile_size(),
                )
            self.document.execute(command)
        except Exception as exc:
            status_widget.status.setText(f"Character creation failed: {exc}")
            return None
        self._pending_character_visual = None
        self._placement_status_widget = None
        self.viewport.end_character_placement()
        self._strip_sync()
        self.document.select_entity(command.created.entity)
        status_widget.status.setText(
            f"Created {command.created.actor.display_name} at map cell {cell[0]}, {cell[1]}"
        )
        # the new sheet joins the sprite sheet choices and draws in Scene
        if not isinstance(visual, DefaultAppearance):  # a new sheet joins the sprite sheets
            self._resolve_project_resources()
        self.refresh_all()
        return command.created

    def _resolve_project_resources(self):
        resolve_project_resources(self.document)
        self.viewport.texture_cache.clear()
        self._sync_scene_authoring_context()

    def _sync_scene_authoring_context(self):
        self.set_tilemap_render_source(scene_authoring_source(self.document))
        self._sync_region_rule_context()

    def _sync_region_rule_context(self):
        project = self.document.project
        rule_sets = project.rpg_database.map_rule_sets if project is not None else {}
        ruleset = rule_sets[sorted(rule_sets)[0]] if rule_sets else None
        layer_name = ruleset.region_layer if ruleset is not None else "regions"
        self.viewport.set_region_layer_name(layer_name)
        self.tile_palette.set_area_rule_set(ruleset)

    def _create_map_rule_set(self):
        from asteria.editor.scene.map_rule_authoring import MapRuleAuthoringController

        MapRuleAuthoringController(self.document).create_ruleset()
        self.refresh_all()

    def _set_region_rule(self, rule):
        from asteria.editor.scene.map_rule_authoring import MapRuleAuthoringController

        MapRuleAuthoringController(self.document).set_region_rule(rule)
        self.refresh_all()

    def _remove_region_rule(self, region_id):
        from asteria.editor.scene.map_rule_authoring import MapRuleAuthoringController

        if MapRuleAuthoringController(self.document).remove_region_rule(region_id):
            self.refresh_all()

    def set_animation_clip_set_view(self, clip_set_id, clip_set):
        self.document.asset_views.set_clip_set(clip_set_id, clip_set)

    def set_sprite_sheet_view(self, asset_id, sprite_sheet):
        self.document.asset_views.set_sprite_sheet(asset_id, sprite_sheet)
        self.viewport.texture_cache.clear()
        self.viewport.refresh()
        self.skeleton_viewer._texture_cache.clear()
        self.skeleton_viewer.canvas.update()

    def set_tilemap_render_source(self, source):
        self.viewport.set_render_source(source)
        texture = None
        if source is not None:
            from asteria.editor.scene.render import resolve_texture_source

            texture = resolve_texture_source(self.document, source.sprite_sheet.texture.asset_id)
        self.tile_palette.set_tileset(
            source.tileset if source is not None else None,
            source.sprite_sheet if source is not None else None,
            texture,
        )
        layer = self.viewport.tile_tools.active_layer if source is not None else None
        self.tile_palette.set_layer(layer)
        self.tile_layers.set_tilemap(source.tilemap if source is not None else None, layer)

    def _select_tile_layer(self, layer):
        self.viewport.set_active_tile_layer(layer)
        self.tile_palette.set_layer(layer)

    def _add_tile_layer(self):
        source = self.viewport.render_source
        if source is None:
            return
        names = {l.name for l in source.tilemap.layers}
        index = 1
        name = "Layer"
        while name in names:
            index += 1
            name = f"Layer {index}"
        layer = TileLayer(name, order=len(source.tilemap.layers))
        self.document.execute(AddTileLayerCommand(source.tilemap, layer))
        self.viewport.set_active_tile_layer(layer)
        self.refresh_all()

    def _remove_tile_layer(self, layer):
        source = self.viewport.render_source
        if source is None:
            return
        try:
            self.document.execute(RemoveTileLayerCommand(source.tilemap, layer))
        except TileEditError:
            return
        self.viewport.tile_tools.active_layer = source.tilemap.layers[0]
        self.refresh_all()

    def _move_tile_layer(self, layer, index):
        source = self.viewport.render_source
        if source is None:
            return
        self.document.execute(ReorderTileLayerCommand(source.tilemap, layer, index))
        self.refresh_all()

    def _set_tile_layer_visible(self, layer, value):
        self.document.execute(SetTileLayerPropertyCommand(layer, "visible", bool(value)))
        self.refresh_all()

    def _set_tile_layer_collision(self, layer, value):
        self.document.execute(SetTileLayerPropertyCommand(layer, "collision_enabled", bool(value)))
        self.refresh_all()
