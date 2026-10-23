"""Multiplayer: input prediction, server sync and the shared world drawing."""

from __future__ import annotations

import math

from asteria.core import Transform
from asteria.graphics.scaling import resized

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


class MultiplayerMixin:
    def _multiplayer_connected(self):
        return self.multiplayer_bridge is not None and self.multiplayer_bridge.connected

    def _enable_authoritative_project_controls(self):
        self._authoritative_project_mode = True
        if getattr(self, "_network_legacy_attack_injected", False):
            from asteria.runtime.action_play import ARPG_ACTIONS
            from asteria.runtime.input_map import InputBinding

            self.input.input_map.set_bindings(
                "attack", [InputBinding(device, code) for device, code in ARPG_ACTIONS["attack"]]
            )
            self._network_legacy_attack_injected = False

    def _network_gameplay_frozen(self):
        return (
            getattr(self, "_authoritative_project_mode", False)
            and not self._multiplayer_connected()
        )

    def _server_save_command(self, command):
        self.multiplayer_bridge.send_command(command, {})
        self.message = (
            self.game.tr("coop.requested", "Server {command} requested", command=command)
            if self._multiplayer_connected()
            else self.game.tr("coop.required", "Server connection required · F3 to retry")
        )
        self.message_until = self.pg.time.get_ticks() + 2500

    def _send_multiplayer_input(self, move_x, move_y, actions=None):
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected:
            return False
        actions = actions or {}
        attack_value = actions.get("attack", actions.get("primary_attack", 0.0))
        input_state = {
            **dict(actions),
            "actions": dict(actions),
            "move_x": max(-1.0, min(1.0, float(move_x))),
            "move_y": max(-1.0, min(1.0, float(move_y))),
            "attack": bool(attack_value),
        }
        previous = getattr(self, "_last_network_input", {})
        changed = previous != input_state
        self._last_network_input = input_state
        sent = bridge.send_input(input_state, force=changed)
        predictor = getattr(self, "_network_predictor", None)
        sequence = getattr(bridge, "last_input_sequence", 0)
        if sent and predictor is not None and sequence:
            mappings = getattr(self, "_network_input_prediction_sequences", {})
            mappings[sequence] = getattr(self, "_network_prediction_sequence", 0)
            self._network_input_prediction_sequences = mappings
        if sent and not self.message:
            self.message = (
                self.game.tr(
                    "coop.connected_project",
                    "Co-op connected · WASD / arrows · J attack · F pickup",
                )
                if self._authoritative_project_mode
                else self.game.tr(
                    "coop.connected",
                    "Co-op connected · move with WASD / arrows · attack with F",
                )
            )
            self.message_until = self.pg.time.get_ticks() + 6000
        return sent

    def _predict_multiplayer_player(self, move_x, move_y, dt):
        """Predict the demo adapter's local player in its authoritative network coordinates."""
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected or self._authoritative_project_mode:
            return False
        state = bridge.state
        players = state.get("players", ())
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == bridge.player_id
            ),
            None,
        )
        if local is None:
            return False
        from asteria.multiplayer.smoothing import InputPredictor

        if self._network_predictor is None:
            speed = self.multiplayer_profile.get("preview_movement_speed", 4.0)
            try:
                speed = float(speed)
            except (TypeError, ValueError):
                speed = 4.0
            if not math.isfinite(speed) or speed <= 0:
                speed = 4.0
            self._network_predictor = InputPredictor(
                (float(local.get("x", 0)), float(local.get("y", 0))), speed=speed
            )
        self._network_prediction_sequence += 1
        position = self._network_predictor.apply_local(
            self._network_prediction_sequence,
            max(-1.0, min(1.0, float(move_x))),
            max(-1.0, min(1.0, float(move_y))),
            max(0.0, min(0.1, float(dt))),
        )
        from asteria.runtime.multiplayer_preview import map_network_position

        if self._network_origin is None:
            transform = self.game.player.get(Transform)
            self._network_origin = (float(transform.x), float(transform.y))
        world_x, world_y = map_network_position(
            {"x": position[0], "y": position[1]},
            state.get("boss"),
            origin=self._network_origin,
            scale=self._network_scale,
        )
        transform = self.game.player.get(Transform)
        transform.x, transform.y = world_x, world_y
        self.game.save.player_position = (world_x, world_y)
        return True

    def _sync_multiplayer_player(self):
        bridge = self.multiplayer_bridge
        if bridge is None or not bridge.connected:
            return
        from asteria.core import Transform
        from asteria.runtime.multiplayer_preview import map_network_position

        state, network_events, network_revision = bridge.snapshot()
        if state.get("schema") == "asteria.multiplayer.project_state":
            self._network_predictor = None
            self._network_input_prediction_sequences.clear()
            self._enable_authoritative_project_controls()
            from asteria.runtime.multiplayer_preview import (
                apply_project_snapshot,
                install_authoritative_commands,
            )

            install_authoritative_commands(self)
            if network_revision != self._network_revision:
                try:
                    if apply_project_snapshot(self, state, bridge.player_id):
                        self._network_revision = network_revision
                        from asteria.runtime.combat import CombatEvent

                        self.game.combat.events = tuple(
                            CombatEvent(
                                **{
                                    key: value
                                    for key, value in event.items()
                                    if key in CombatEvent.__dataclass_fields__
                                }
                            )
                            for event in network_events
                            if event.get("kind")
                            in {"damage", "staggered", "knocked_down", "state_applied"}
                        )
                except (KeyError, TypeError, ValueError) as exc:
                    self._multiplayer_error = f"Invalid server snapshot: {exc}"
            return
        boss = state.get("boss")
        players = state.get("players", ())
        player_id = bridge.player_id
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == player_id
            ),
            None,
        )
        if local is None:
            return
        if self._network_origin is None:
            transform = self.game.player.get(Transform)
            self._network_origin = (float(transform.x), float(transform.y))
        x, y = map_network_position(
            local, boss, origin=self._network_origin, scale=self._network_scale
        )
        transform = self.game.player.get(Transform)
        predictor = self._network_predictor
        if predictor is not None:
            acknowledged = bridge.acked_input_sequence
            acknowledged_prediction = max(
                (
                    prediction
                    for sequence, prediction in self._network_input_prediction_sequences.items()
                    if sequence <= acknowledged
                ),
                default=0,
            )
            if (
                acknowledged_prediction
                and network_revision > bridge.acked_input_revision
                and network_revision > self._network_prediction_reconciled_revision
            ):
                predictor.reconcile(
                    (float(local["x"]), float(local["y"])), acknowledged_prediction
                )
                self._network_prediction_reconciled_revision = network_revision
                self._network_input_prediction_sequences = {
                    sequence: prediction
                    for sequence, prediction in self._network_input_prediction_sequences.items()
                    if sequence > acknowledged
                }
            x, y = map_network_position(
                {"x": predictor.position[0], "y": predictor.position[1]},
                boss,
                origin=self._network_origin,
                scale=self._network_scale,
            )
        transform.x, transform.y = x, y
        self.game.save.player_position = (x, y)
        if network_revision > self._network_revision:
            self._network_revision = network_revision
            for event in network_events:
                if event.get("player_id") != player_id:
                    continue
                if event.get("type") == "experience_awarded":
                    amount = int(event.get("amount", 0))
                    self.message = self.game.tr(
                        "coop.boss_defeated", "Boss defeated · +{amount} XP", amount=amount
                    )
                    self.message_until = self.pg.time.get_ticks() + 6000
                elif event.get("type") == "loot_awarded":
                    self.message = self.game.tr(
                        "coop.boss_loot", "Boss loot: {item}", item=event.get("item_id", "item")
                    )
                    self.message_until = self.pg.time.get_ticks() + 6000

    def _draw_multiplayer_world(self):
        bridge = self.multiplayer_bridge
        if bridge is None:
            if self.multiplayer_profile_error:
                self.panel((12, 12, self.width - 24, 48))
                self.text(
                    self.game.tr(
                        "coop.profile_error",
                        "Co-op profile error: {error}",
                        error=self.multiplayer_profile_error,
                    ),
                    24,
                    25,
                    size=18,
                    color=(255, 154, 132),
                )
            return
        if not bridge.connected:
            status = self._multiplayer_error or self.game.tr(
                "coop.start_server", "Start the local server in Multiplayer first"
            )
            self.panel((12, 12, self.width - 24, 48))
            self.text(
                self.game.tr(
                    "coop.retry", "Co-op offline · {status} · F3 to retry", status=status
                ),
                24,
                25,
                size=18,
                color=(255, 190, 132),
            )
            return

        from asteria.runtime.multiplayer_preview import map_network_position

        state = bridge.state
        if state.get("schema") == "asteria.multiplayer.project_state":
            self.text(
                self.game.tr(
                    "coop.players", "Co-op · {count} players", count=len(state.get("players", ()))
                ),
                16,
                12,
                size=18,
                color=(170, 230, 190),
            )
            return
        boss = state.get("boss")
        players = state.get("players", ())
        if not isinstance(boss, dict) or not isinstance(players, list):
            return
        if self._network_origin is None:
            player_transform = self.game.player.get(Transform)
            self._network_origin = (float(player_transform.x), float(player_transform.y))
        origin = self._network_origin
        boss_world = map_network_position(boss, boss, origin=origin, scale=self._network_scale)
        zoom = self.field_camera.zoom
        boss_x, boss_y = self._field_screen_xy(*boss_world)
        radius = max(12, round(12 * zoom))
        boss_color = (220, 89, 84) if boss.get("alive", True) else (128, 128, 138)
        self.pg.draw.rect(
            self.screen,
            (35, 24, 31),
            (round(boss_x - radius), round(boss_y - radius), radius * 2, radius * 2),
        )
        self.pg.draw.rect(
            self.screen,
            boss_color,
            (round(boss_x - radius), round(boss_y - radius), radius * 2, radius * 2),
            max(2, round(2 * zoom)),
        )
        hp, max_hp = int(boss.get("hp", 0)), max(1, int(boss.get("max_hp", 1)))
        bar_width = max(64, round(84 * zoom))
        bar_y = round(boss_y - radius - 18 * zoom)
        self.pg.draw.rect(
            self.screen, (28, 28, 34), (round(boss_x - bar_width / 2), bar_y, bar_width, 7)
        )
        self.pg.draw.rect(
            self.screen,
            boss_color,
            (
                round(boss_x - bar_width / 2),
                bar_y,
                round(bar_width * max(0, min(max_hp, hp)) / max_hp),
                7,
            ),
        )
        self.text(
            self.game.tr("coop.boss", "Co-op Boss · {hp}/{max_hp}", hp=hp, max_hp=max_hp),
            boss_x,
            bar_y - 22,
            size=20,
            color=(255, 224, 214),
            center=True,
        )

        for drop in state.get("world_drops", []):
            if drop.get("claimed_by") or bridge.player_id in drop.get("claimed_by_players", []):
                continue
            world = map_network_position(drop, boss, origin=origin, scale=self._network_scale)
            sx, sy = self._field_screen_xy(*world)
            self.pg.draw.circle(self.screen, (249, 214, 106), (round(sx), round(sy)), 7)
            claim = self.game.tr("coop.claim", "G: claim treasure")
            self.text(claim, sx, sy + 12, size=16, color=(249, 214, 106), center=True)

        local_id = bridge.player_id
        local = next(
            (
                player
                for player in players
                if isinstance(player, dict) and player.get("player_id") == local_id
            ),
            None,
        )
        local_xp = int(local.get("experience", 0)) if local is not None else 0
        self.panel((12, 66, min(330, self.width - 24), 48))
        self.text(
            self.game.tr(
                "coop.status",
                "Co-op · {count} players · XP {xp} · B: bag / G: loot",
                count=len(players),
                xp=local_xp,
            ),
            24,
            80,
            size=20,
            color=(132, 229, 220),
        )
        frame = self._player_frame("down", False)
        source_w, source_h = frame.get_size()
        render_width = max(18, round(self.manifest["field"].get("player_render_width", 64) * zoom))
        render_height = max(1, round(source_h * render_width / max(1, source_w)))
        smooth = self.manifest["field"].get("player_scaling") == "smooth"
        frame = resized(self.pg, frame, (render_width, render_height), smooth=smooth)
        remote_positions = bridge.remote_positions()
        for index, player in enumerate(players):
            if not isinstance(player, dict) or player.get("player_id") == local_id:
                continue
            network_position = remote_positions.get(player.get("player_id"))
            positioned_player = (
                {**player, "x": network_position[0], "y": network_position[1]}
                if network_position is not None
                else player
            )
            world = map_network_position(
                positioned_player, boss, origin=origin, scale=self._network_scale
            )
            screen_x, screen_y = self._field_screen_xy(*world)
            ground = (round(screen_x), round(screen_y + 5 * zoom))
            self.pg.draw.ellipse(
                self.screen,
                (28, 34, 42),
                (ground[0] - render_width // 3, ground[1] - 4, 2 * render_width // 3, 9),
            )
            position = (
                round(screen_x - render_width / 2),
                round(screen_y - render_height + 10 * zoom),
            )
            self.screen.blit(frame, position)
            color = ((84, 196, 211), (160, 132, 234), (226, 174, 78), (106, 194, 133))[index % 4]
            self.pg.draw.circle(self.screen, color, ground, max(4, round(5 * zoom)), 2)
            label = str(player.get("display_name", self.game.tr("coop.player", "Player")))
            self.text(
                self.game.tr(
                    "coop.player_hp", "{name} · {hp} HP", name=label, hp=player.get("hp", 0)
                ),
                screen_x,
                position[1] - 20,
                size=18,
                color=color,
                center=True,
            )
