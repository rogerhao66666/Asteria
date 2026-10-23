"""The title screen, the player's save and the build menu (classes, trees, gear)."""

from __future__ import annotations

from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime

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


class TitleBuildMixin:
    def _draw_title(self):
        bg = self.load_image(self.manifest["field"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg, (self.width, self.height)), (0, 0))
        shade = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        shade.fill((5, 8, 16, 150))
        self.screen.blit(shade, (0, 0))
        tr = self.game.tr
        name = tr("title.name", "ASTERIA")
        self.text(name, self.width / 2, 120, size=64, color=(255, 220, 120), center=True)
        # the game's own name (manifest "subtitle"); the reference project keeps its old text
        subtitle = self.manifest.get("subtitle") or tr("title.subtitle", "Complex Reference RPG")
        self.text(subtitle, self.width / 2, 180, size=36, center=True)
        self.panel((280, 250, 400, 150))
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self.text(tr("title.server_session", "N   Enter Server Session"), 310, 282, size=25)
            self.text(tr("title.server_save", "L   Reload Server Save"), 310, 330, size=25)
            self.text(
                tr("title.guest", "Guest: {player}", player=self.multiplayer_bridge.player_id),
                310,
                372,
                size=16,
                color=(170, 210, 240),
            )
            return
        self.text(tr("title.new_game", "N   New Game"), 330, 282, size=28)
        self.text(tr("title.load_game", "L   Load Game"), 330, 330, size=28)
        from asteria.runtime.save_slots import SaveSlots

        used = sum(
            1
            for s in SaveSlots(self.resource_root / "saves", self.project).slots()
            if self._slot_exists(s)
        )
        self.text(
            tr("title.saves", "{count} save(s) found", count=used)
            if used
            else tr("title.no_saves", "No saves yet"),
            330,
            372,
            size=18,
            color=(170, 210, 240),
        )

    def _load_player_save(self):
        if self._multiplayer_connected() or self._network_gameplay_frozen():
            self._server_save_command("load")
            self._ui_mode = "field"
            return True
        path = self.resource_root / "saves" / "playtest_autosave.asteria-save.json"
        if not path.exists():
            self.message = self.game.tr("title.no_player_save", "No player save exists yet")
            self.message_until = self.pg.time.get_ticks() + 1800
            return False
        loaded = GameRuntimeSave.load_json(path, self.project)
        self.save = loaded
        self.game = GameSessionRuntime(self.project, loaded)
        self._victory = False
        self._defeat = False
        self._ui_mode = "field"
        self.message = self.game.tr("title.loaded", "Loaded player save")
        self.message_until = self.pg.time.get_ticks() + 1800
        return True

    def _adopt_new_game_plus(self):
        """An event asked for New Game Plus: play on in the carried-over save from the start."""
        fresh = getattr(self.game, "pending_new_game", None)
        if fresh is None:
            return False
        self.game.pending_new_game = None
        self.save = fresh
        self.game = GameSessionRuntime(self.project, fresh)
        self._victory = self._defeat = False
        self._ui_mode = "field"
        self.message = self.game.tr("title.new_game_plus", "New Game+")
        self.message_until = self.pg.time.get_ticks() + 2400
        return True

    def _menu_actor_ids(self):
        return tuple(self.save.rpg_state.party_actor_ids)

    def _menu_actor(self):
        ids = self._menu_actor_ids()
        if not ids:
            return None
        self._menu_actor_index %= len(ids)
        return ids[self._menu_actor_index]

    def _current_weapon(self, actor_id):
        loadout = self.save.rpg_state.loadouts[actor_id]
        values = loadout.equipped("weapon")
        return values[0] if values else None

    def _draw_build_menu(self):
        self._draw_field(False)
        overlay = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        overlay.fill((6, 9, 18, 210))
        self.screen.blit(overlay, (0, 0))
        actor_id = self._menu_actor()
        if actor_id is None:
            return
        db = self.project.rpg_database
        state = self.save.rpg_state.actor_progression[actor_id]
        ability = self.game._ability_state(actor_id)
        weapon = self._current_weapon(actor_id)
        allocation = self.save.rpg_state.progression_allocations[actor_id]
        self.panel((24, 22, 912, 496), fill=(11, 15, 25, 242))
        tr = self.game.tr
        title = tr("build.title", "Character / Build Acceptance Menu")
        self.text(title, 44, 38, size=30, color=(255, 220, 120))
        keys = tr("build.keys", "Q/E Actor   C Close     Current: {actor}", actor=actor_id)
        self.text(keys, 44, 76, size=19)
        self.text(
            tr(
                "build.points",
                "Level {level}   EXP {exp}   AP {ap}   Ability Pts {ability_points}",
                level=state.level,
                exp=int(state.experience),
                ap=int(allocation.balance("ap")),
                ability_points=int(state.points.get("ability_points", 0)),
            ),
            44,
            106,
            size=20,
            color=(170, 220, 255),
        )
        classes = " + ".join(state.active_class_ids) or "—"
        self.text(tr("build.class", "1 Secondary Class: {value}", value=classes), 44, 148, size=20)
        passives = ", ".join(ability.active_passives[:4]) or "—"
        self.text(tr("build.passives", "3 Passives: {value}", value=passives), 44, 178, size=20)
        held = weapon.equipment.display_name if weapon else "—"
        self.text(tr("build.weapon", "4 Weapon: {value}", value=held), 44, 208, size=20)
        growth = (
            "—"
            if weapon is None or weapon.growth is None
            else ", ".join(f"{k}:{v}" for k, v in sorted(weapon.growth.ranks.items()))
            or tr("build.base", "base")
        )
        self.text(tr("build.upgrade", "5 Weapon Upgrade: {value}", value=growth), 44, 238, size=20)
        accessories = self.save.rpg_state.loadouts[actor_id].equipped("accessory")
        worn = ", ".join(x.equipment.display_name for x in accessories) or "—"
        self.text(tr("build.accessories", "6 Accessories: {value}", value=worn), 44, 268, size=20)
        active = ", ".join(self.save.rpg_state.party_active_actor_ids)
        self.text(
            tr("build.party", "7 Party / Formation: {value}", value=active), 44, 298, size=20
        )
        tree = tr("build.tree", "2 Skill Tree: allocate next available node")
        self.text(tree, 44, 328, size=20)
        graph_id = (
            state.active_class_ids[-1] if state.active_class_ids else next(iter(db.classes))
        ) + "_tree"
        graph = db.progression_graphs.get(graph_id)
        if graph is not None:
            ox, oy = 485, 150
            self.text(graph.display_name, ox, 116, size=22, color=(255, 220, 120))
            if graph.node_positions:
                ranks = allocation.allocations.get(graph.graph_id, {})
                for node in graph.nodes:
                    x, y = graph.node_positions.get(node.node_id, (0, 0))
                    x = ox + x * 0.55
                    y = oy + y * 0.65
                    for req in node.prerequisites:
                        px, py = graph.node_positions.get(req.node_id, (0, 0))
                        px = ox + px * 0.55
                        py = oy + py * 0.65
                        self.pg.draw.line(
                            self.screen,
                            (100, 120, 155),
                            (int(px + 38), int(py + 12)),
                            (int(x + 38), int(y + 12)),
                            2,
                        )
                    rect = (int(x), int(y), 78, 25)
                    self.pg.draw.rect(
                        self.screen,
                        (45, 70, 60) if ranks.get(node.node_id, 0) else (40, 46, 62),
                        rect,
                        border_radius=4,
                    )
                    self.pg.draw.rect(self.screen, (190, 200, 225), rect, 1, border_radius=4)
                    self.text(
                        node.display_name.replace(graph.display_name.split()[0], "")[:10],
                        x + 4,
                        y + 5,
                        size=14,
                    )
            else:
                ranks = allocation.allocations.get(graph.graph_id, {})
                for i, node in enumerate(graph.nodes[:6]):
                    self.text(
                        ("[x] " if ranks.get(node.node_id, 0) else "[ ] ") + node.display_name,
                        ox,
                        155 + i * 38,
                        size=18,
                    )
        self.text(
            tr(
                "build.note",
                "All changes are Runtime State and are verified again after Save/Load.",
            ),
            44,
            480,
            size=18,
            color=(170, 210, 240),
        )

    def _cycle_secondary_class(self, actor_id):
        state = self.save.rpg_state.actor_progression[actor_id]
        current = state.active_class_ids[-1] if len(state.active_class_ids) > 1 else None
        choices = [x for x in state.unlocked_class_ids if x != state.active_class_ids[0]]
        if not choices:
            return
        idx = -1 if current not in choices else choices.index(current)
        self.game.set_secondary_class(actor_id, choices[(idx + 1) % len(choices)])

    def _allocate_next_tree_node(self, actor_id):
        state = self.save.rpg_state.actor_progression[actor_id]
        cls = state.active_class_ids[-1] if state.active_class_ids else None
        if not cls:
            return
        graph_id = f"{cls}_tree"
        allocation = self.save.rpg_state.progression_allocations[actor_id]
        graph = self.project.rpg_database.progression_graphs[graph_id]
        for node in graph.nodes:
            preview = allocation.preview_allocate(graph_id, node.node_id, 1)
            if preview.allowed:
                self.game.allocate_progression(actor_id, graph_id, node.node_id, 1)
                self.message = self.game.tr(
                    "build.learned", "Learned {name}", name=node.display_name
                )
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = self.game.tr("build.no_node", "No affordable/unlocked node")
        self.message_until = self.pg.time.get_ticks() + 1400

    def _cycle_passive(self, actor_id):
        ids = sorted(self.project.rpg_database.passives)
        state = self.game._ability_state(actor_id)
        current = list(state.active_passives)
        candidate = next((x for x in ids if x not in current), ids[0] if ids else None)
        if candidate is None:
            return
        values = (current + [candidate])[-4:]
        self.game.set_passives(actor_id, values, capacity=4)

    def _cycle_weapon(self, actor_id):
        ids = sorted(
            k for k, v in self.project.rpg_database.equipment.items() if v.slot == "weapon"
        )
        current = self._current_weapon(actor_id)
        cur = None if current is None else current.equipment.equipment_id
        idx = -1 if cur not in ids else ids.index(cur)
        self.game.equip_definition(actor_id, ids[(idx + 1) % len(ids)], slot_id="weapon")

    def _upgrade_weapon(self, actor_id):
        item = self._current_weapon(actor_id)
        if item is None:
            return
        growth = item.ensure_growth(self.project.rpg_database.equipment_growth)
        for node in growth.definition.nodes:
            if growth.preview_unlock(node.node_id).allowed:
                if self._multiplayer_connected():
                    self.multiplayer_bridge.send_command(
                        "upgrade", {"slot_id": "weapon", "node_id": node.node_id}
                    )
                    return
                growth.unlock(node.node_id)
                self.message = self.game.tr(
                    "build.upgraded", "Weapon upgraded: {name}", name=node.display_name
                )
                self.message_until = self.pg.time.get_ticks() + 1400
                return
        self.message = self.game.tr("build.no_upgrade", "Weapon growth maxed or blocked")
        self.message_until = self.pg.time.get_ticks() + 1400

    def _cycle_accessory(self, actor_id):
        ids = sorted(
            k for k, v in self.project.rpg_database.equipment.items() if v.slot == "accessory"
        )
        loadout = self.save.rpg_state.loadouts[actor_id]
        if loadout.equipped("accessory"):
            if self._multiplayer_connected():
                self.game.unequip_to_bag(actor_id, "accessory")
            else:
                loadout.unequip("accessory", 0)
        self.game.equip_definition(
            actor_id, ids[(self._menu_actor_index) % len(ids)], slot_id="accessory", replace=False
        )

    def _rotate_party(self):
        roster = list(self.save.rpg_state.party_actor_ids)
        if len(roster) <= 1:
            return
        rotated = roster[1:] + roster[:1]
        chosen = rotated[: min(6, len(rotated))]
        self.game.set_active_party(
            chosen, {actor_id: f"slot_{i + 1}" for i, actor_id in enumerate(chosen)}
        )

    def _build_menu_input(self, events):
        actor = self._menu_actor()
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_c:
                self._ui_mode = "field"
            elif event.key == self.pg.K_q:
                self._menu_actor_index -= 1
            elif event.key == self.pg.K_e:
                self._menu_actor_index += 1
            elif actor is not None and event.key == self.pg.K_1:
                self._cycle_secondary_class(actor)
            elif actor is not None and event.key == self.pg.K_2:
                self._allocate_next_tree_node(actor)
            elif actor is not None and event.key == self.pg.K_3:
                self._cycle_passive(actor)
            elif actor is not None and event.key == self.pg.K_4:
                self._cycle_weapon(actor)
            elif actor is not None and event.key == self.pg.K_5:
                self._upgrade_weapon(actor)
            elif actor is not None and event.key == self.pg.K_6:
                self._cycle_accessory(actor)
            elif event.key == self.pg.K_7:
                self._rotate_party()
            elif actor is not None and event.key == self.pg.K_8:
                self._ui_mode = "workshop"
