"""The workshop: refine, sockets and attribute points on one screen."""

from __future__ import annotations

from asteria.rpg.built_in_text import translated

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


class WorkshopMixin:
    # --- workshop: refine, sockets and attribute points on one screen --------------------

    def _workshop_input(self, events):
        """R refine the weapon, S socket the next fitting bag item, X take a gem out, A spend
        an attribute point (cycling the attribute nodes), C / Escape back to the build menu."""
        actor = self._menu_actor()
        if actor is None:
            return
        weapon = self._current_weapon(actor)
        game = self.game
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            try:
                if event.key in (self.pg.K_c, self.pg.K_ESCAPE):
                    self._ui_mode = "build"
                elif weapon is not None and event.key == self.pg.K_r:
                    result = game.refine_equipment(actor, weapon.instance_id)
                    self._workshop_message = game.tr(
                        "workshop.refined", "Refine: {outcome}", outcome=result.outcome
                    )
                elif weapon is not None and event.key == self.pg.K_s:
                    self._workshop_message = self._socket_next(actor, weapon)
                elif weapon is not None and event.key == self.pg.K_x:
                    for socket_id, attached in weapon.attachments.items():
                        game.unsocket_item(actor, weapon.instance_id, socket_id)
                        self._workshop_message = game.tr(
                            "workshop.took_out",
                            "Took {name} out of {socket}",
                            name=game.name_of(attached),
                            socket=socket_id,
                        )
                        break
                elif event.key == self.pg.K_a:
                    self._workshop_message = self._spend_attribute_point(actor)
            except Exception as exc:  # noqa: BLE001 - shown on the screen, the game goes on
                self._workshop_message = translated(exc, game.tr)

    def _socket_next(self, actor, weapon):
        game, db = self.game, self.project.rpg_database
        bag = self.save.rpg_state.inventory
        for socket in weapon.equipment.sockets:
            if socket.socket_id in weapon.attachments or socket.locked:
                continue
            for item in db.items.values():
                if not item.attachment_id or bag.count(item.item_id) < 1:
                    continue
                try:
                    game.socket_item(actor, weapon.instance_id, socket.socket_id, item.item_id)
                except Exception:  # noqa: BLE001 - a gem that does not fit this socket
                    continue
                return game.tr(
                    "workshop.socketed",
                    "Socketed {name} into {socket}",
                    name=game.name_of(item),
                    socket=socket.socket_id,
                )
        return game.tr(
            "workshop.nothing_to_socket",
            "Nothing to socket (no free socket or no fitting item in the bag)",
        )

    def _spend_attribute_point(self, actor):
        allocation = self.save.rpg_state.progression_allocations[actor]
        graph = allocation.definitions.get("attributes")
        if graph is None:
            return self.game.tr("workshop.no_attributes", "This project has no attribute graph")
        for node in graph.nodes:
            try:
                allocation.allocate("attributes", node.node_id)
            except ValueError:
                continue
            self.game.refresh_actor_combatants(actor)
            name = self.game.name_of(node)
            return self.game.tr("workshop.point_spent", "+1 {name}", name=name)
        return self.game.tr("workshop.no_points", "No attribute points left")

    def _draw_workshop(self):
        self._draw_field(False)
        overlay = self.pg.Surface((self.width, self.height), self.pg.SRCALPHA)
        overlay.fill((6, 9, 18, 220))
        self.screen.blit(overlay, (0, 0))
        actor = self._menu_actor()
        if actor is None:
            return
        game = self.game
        weapon = self._current_weapon(actor)
        allocation = self.save.rpg_state.progression_allocations[actor]
        rules = game.refine_rules
        self.panel((24, 22, 912, 496), fill=(11, 15, 25, 242))
        tr = game.tr
        self.text(tr("workshop.title", "Workshop"), 44, 38, size=30, color=(255, 220, 120))
        self.text(
            tr(
                "workshop.keys",
                "R Refine   S Socket   X Take out   A Attribute point   C Back  [{actor}]",
                actor=actor,
            ),
            44,
            76,
            size=18,
        )
        gold = self.save.rpg_state.currencies.get("gold", 0)
        gold = tr("workshop.gold", "Gold {amount}", amount=int(gold))
        self.text(gold, 760, 40, size=20, color=(255, 214, 120))
        y = 120
        if weapon is None:
            self.text(tr("workshop.no_weapon", "No weapon equipped"), 44, y, size=22)
        else:
            held = self.game.name_of(weapon.equipment)
            self.text(f"{held}  +{weapon.refine_level}", 44, y, size=26)
            if rules is not None and weapon.refine_level < rules.max_level:
                chance = round(rules.chance(weapon.refine_level) * 100)
                self.text(
                    tr(
                        "workshop.next",
                        "Next +{level}: {chance}% for {cost} {currency}",
                        level=weapon.refine_level + 1,
                        chance=chance,
                        cost=int(rules.cost(weapon.refine_level)),
                        currency=rules.currency,
                    ),
                    44,
                    y + 34,
                    size=18,
                    color=(170, 220, 255),
                )
            y += 80
            for socket in weapon.equipment.sockets:
                attached = weapon.attachments.get(socket.socket_id)
                if attached is not None:
                    label = self.game.name_of(attached)
                elif socket.locked:
                    label = tr("workshop.locked", "locked")
                else:
                    label = tr("workshop.empty", "empty")
                self.text(
                    tr(
                        "workshop.socket",
                        "Socket {socket}: {value}",
                        socket=socket.socket_id,
                        value=label,
                    ),
                    64,
                    y,
                    size=20,
                )
                y += 30
        graph = allocation.definitions.get("attributes")
        if graph is not None:
            self.text(
                tr(
                    "workshop.points",
                    "Attribute points: {count}",
                    count=int(allocation.balance("stat_points")),
                ),
                520,
                120,
                size=22,
                color=(255, 220, 120),
            )
            ranks = allocation.allocations.get("attributes", {})
            for i, node in enumerate(graph.nodes):
                self.text(
                    f"{self.game.name_of(node)}: {ranks.get(node.node_id, 0)}",
                    540,
                    160 + i * 30,
                    size=20,
                )
        self.text(getattr(self, "_workshop_message", ""), 44, 470, size=20, color=(170, 210, 240))
