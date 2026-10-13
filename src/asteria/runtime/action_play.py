"""Real-time play in a field scene (ASTERIA_SPEC §20; D22 A8): the scene setting, default controls
and the HUD.

``CombatSceneComponent`` (on any entity of a scene, like the environment) makes the scene an
action scene: enemies are
fought in real time instead of starting a turn-based encounter, the player moves through its
controller, falls and
respawns. ``ARPG_ACTIONS`` are the input actions action scenes use; a project's own input map
wins, these only fill in
what it lacks. ``ActionHud`` draws what a real-time fight needs on top of the field: overhead HP,
damage numbers, hit
flashes, projectiles, loot labels, the lock-on marker, the player's bars, the skill bar with
cooldowns, level-ups and
the respawn countdown — all from engine state, nothing game-specific.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core import Component, Field, Transform, component_schema, world_position

COMBAT_MODES = ("encounter", "action")
VIEWS = ("topdown", "side")

# input action -> default key / gamepad bindings, added only when the project's input map has no
# such action
ARPG_ACTIONS = {
    "attack": (("key", "j"), ("gamepad_button", "2")),
    "dodge": (("key", "k"), ("key", "left shift"), ("gamepad_button", "1")),
    "skill_1": (("key", "1"),),
    "skill_2": (("key", "2"),),
    "skill_3": (("key", "3"),),
    "skill_4": (("key", "4"),),
    "lock_on": (("key", "l"), ("key", "tab"), ("gamepad_button", "9")),
    "lock_switch": (("key", "o"),),
    "jump": (("key", "space"), ("gamepad_button", "0")),
    "pickup": (("key", "f"), ("gamepad_button", "3")),
    "bag": (("key", "b"),),
}


@component_schema(
    type_name="asteria.CombatScene",
    version=1,
    fields=(
        Field(
            "combat_mode",
            str,
            "encounter",
            choices=COMBAT_MODES,
            tooltip="encounter: touching an enemy starts a turn-based battle; action: enemies "
            "are fought in real time.",
        ),
        Field(
            "view",
            str,
            "topdown",
            choices=VIEWS,
            tooltip="How the scene is seen (the player's controller mode).",
        ),
        Field("on_player_death", str, "respawn", choices=("respawn", "game_over")),
        Field("respawn_delay", float, 2.0, minimum=0.0),
        Field("respawn_heal", bool, True, tooltip="Respawn with full resources."),
        Field(
            "draw_colliders",
            bool,
            False,
            tooltip="Draw solid colliders, slopes and ladders (block-out levels).",
        ),
        Field(
            "camera_look_ahead",
            float,
            0.0,
            minimum=0.0,
            tooltip="World units the camera leads the player by.",
        ),
        Field(
            "background_color",
            str,
            "",
            tooltip="'#rrggbb' fills the screen instead of the field image (block-outs).",
        ),
        Field(
            "player_life_resource",
            str,
            "",
            tooltip="The player's life resource when it is not 'hp'; empty keeps the combatant's.",
        ),
    ),
)
class CombatSceneComponent(Component):
    def __init__(self):
        super().__init__()
        self.combat_mode = "encounter"
        self.view = "topdown"
        self.on_player_death = "respawn"
        self.respawn_delay = 2.0
        self.respawn_heal = True
        self.draw_colliders = False
        self.camera_look_ahead = 0.0
        self.player_life_resource = ""
        self.background_color = ""


def combat_scene(scene):
    """The scene's ``CombatSceneComponent`` (the first one), or ``None``."""
    for _, settings in scene.query(CombatSceneComponent):
        return settings
    return None


def missing_action_bindings(input_map):
    """``{action: (InputBinding, ...)}`` for ARPG actions the project's input map does not
    define."""
    from .input_map import InputBinding

    known = set(input_map.actions())
    return {
        action: tuple(InputBinding(kind, code) for kind, code in bindings)
        for action, bindings in ARPG_ACTIONS.items()
        if action not in known
    }


def register_action_play_components(registry):
    registry.register(CombatSceneComponent)
    return registry


@dataclass(slots=True)
class _Float:
    x: float
    y: float
    text: str
    color: tuple
    age: float = 0.0
    life: float = 0.9


TEAM_COLORS = {"hero": (90, 170, 255), "foe": (220, 80, 90)}


class ActionHud:
    """Draws the real-time combat layer for a ``PlayableTestRuntime`` (pygame)."""

    def __init__(self):
        self.floats: list[_Float] = []
        self.flash: dict[str, float] = {}
        self.banner = ("", 0.0)

    # -- events -----------------------------------------------------------------------------------
    def observe(self, game, dt):
        """Read this frame's combat, loot and progression events (call after ``field_update``)."""
        for f in self.floats:
            f.age += dt
        self.floats = [f for f in self.floats if f.age < f.life]
        self.flash = {k: v - dt for k, v in self.flash.items() if v - dt > 0}
        text, left = self.banner
        self.banner = (text, max(0.0, left - dt))
        for event in game.combat.events:
            if event.kind == "damage" and event.amount:
                heal = event.amount < 0
                color = (
                    (120, 230, 140)
                    if heal
                    else (255, 220, 90)
                    if event.critical
                    else (255, 255, 255)
                )
                text = f"{abs(event.amount):.0f}{'!' if event.critical else ''}"
                self.floats.append(_Float(event.x, event.y - 10, text, color))
                self.flash[event.target_id] = 0.12
            elif event.kind in ("staggered", "knocked_down"):
                self.floats.append(
                    _Float(
                        event.x,
                        event.y - 22,
                        event.kind.replace("_", " "),
                        (255, 160, 90),
                        life=0.7,
                    )
                )
            elif event.kind == "state_applied":
                self.floats.append(
                    _Float(
                        event.x,
                        event.y - 22,
                        event.data.get("state", ""),
                        (200, 140, 255),
                        life=0.8,
                    )
                )
        for event in game.loot.events:
            if event.kind == "picked" and event.looter_id == game.player.id:
                x, y = world_position(game.player)
                label = event.label if event.amount == 1 else f"+{event.amount} {event.label}"
                self.floats.append(_Float(x, y - 30, label, (170, 240, 170), life=1.2))
        for result in game.progression_events:
            if result.get("levels_gained"):
                self.banner = (f"Level {result['new_level']}!", 2.0)

    # -- world layer ------------------------------------------------------------------------------
    @staticmethod
    def _unit(rt):
        """Screen pixels per world unit (the field's world-to-screen scale times the camera
        zoom)."""
        x0, _ = rt._field_screen_xy(0.0, 0.0)
        x1, _ = rt._field_screen_xy(1.0, 0.0)
        return abs(x1 - x0) or 1.0

    def draw_world(self, rt):
        tiles = getattr(rt, "tile_view", None)
        game, pg, screen = rt.game, rt.pg, rt.screen
        zoom = self._unit(rt)
        settings = combat_scene(game.scene)
        if settings is not None and settings.draw_colliders:
            self._draw_colliders(rt, zoom)
        from .combat import CombatantComponent

        placed = []
        for _entity, label_x, label_y, text, color in game.loot.labels(game.scene):
            sx, sy = rt._field_screen_xy(label_x, label_y)
            pg.draw.circle(screen, color, (int(sx), int(sy)), max(3, int(2 * zoom)))
            image = rt.pg.font.Font(None, 20).render(text, True, color)
            box = pg.Rect(0, 0, image.get_width() + 8, image.get_height() + 4)
            box.midbottom = (int(sx), int(sy - 4 * zoom))
            while any(
                box.colliderect(other) for other in placed
            ):  # stack labels of drops lying close together
                box.y -= box.height + 2
            placed.append(box)
            pg.draw.rect(screen, (12, 14, 22), box)
            screen.blit(image, (box.x + 4, box.y + 2))
        player_team = getattr(game.player.try_get(CombatantComponent), "team", "")
        for entity, combatant in game.scene.query(CombatantComponent):
            if entity is game.player or not entity.has(Transform):
                continue
            sx, sy = rt._field_screen_xy(*world_position(entity))
            sprites = rt.manifest["field"].get("entity_sprites", {})
            # a tile scene draws (and flashes) entities that have their own sprite
            drawn = tiles is not None and _has_sprite(entity)
            if entity.name not in sprites and not drawn:
                color = TEAM_COLORS.get(combatant.team, (200, 200, 120))
                radius = max(4, int(6 * zoom))
                pg.draw.circle(screen, color, (int(sx), int(sy)), radius)
                pg.draw.circle(screen, (20, 20, 28), (int(sx), int(sy)), radius, 2)
            if entity.id in self.flash and not drawn:
                pg.draw.circle(
                    screen, (255, 255, 255), (int(sx), int(sy)), max(4, int(6 * zoom)), 0
                )
            state = combatant.state
            if state is None or combatant.team == player_team or not combatant.life_resource:
                continue
            if state.resources.contains(combatant.life_resource):
                value = state.resources.get(combatant.life_resource)
                if value.current < value.maximum or entity.id == self._lock_id(game):
                    self._bar(
                        rt,
                        sx - 20,
                        sy - 11 * zoom,
                        40,
                        5,
                        value.current,
                        value.maximum,
                        (220, 70, 70),
                    )
        definitions = game.project.gameplay_library.projectiles
        for view in game.projectiles.views():
            sx, sy = rt._field_screen_xy(view.x, view.y)
            definition = definitions.get(view.projectile_id)
            image = (
                tiles.projectile_image(definition, view.vx, view.vy)
                if tiles is not None and definition is not None and definition.sprite
                else None
            )
            if image is not None:  # the projectile's own sprite, turned to where it flies
                screen.blit(
                    image, (int(sx - image.get_width() / 2), int(sy - image.get_height() / 2))
                )
                continue
            pg.draw.circle(screen, (255, 230, 140), (int(sx), int(sy)), max(3, int(1.5 * zoom)))
            speed = (view.vx * view.vx + view.vy * view.vy) ** 0.5 or 1.0
            tail = (int(sx - view.vx / speed * 4 * zoom), int(sy - view.vy / speed * 4 * zoom))
            pg.draw.line(screen, (255, 180, 80), tail, (int(sx), int(sy)), 2)
        target = game.scene.get_entity(self._lock_id(game)) if self._lock_id(game) else None
        if target is not None:
            sx, sy = rt._field_screen_xy(*world_position(target))
            pg.draw.circle(screen, (255, 220, 90), (int(sx), int(sy)), max(8, int(10 * zoom)), 2)
        font = pg.font.Font(None, 26)
        for f in self.floats:
            sx, sy = rt._field_screen_xy(f.x, f.y)
            image = font.render(f.text, True, f.color)
            image.set_alpha(int(255 * max(0.0, 1.0 - f.age / f.life)))
            screen.blit(
                image, (int(sx - image.get_width() / 2), int(sy - 30 * f.age - image.get_height()))
            )

    @staticmethod
    def _lock_id(game):
        from .action_combat import ActionCombatComponent

        spec = game.player.try_get(ActionCombatComponent)
        return spec.lock_target_id if spec is not None else ""

    def _draw_colliders(self, rt, zoom):
        from .collision import Collider2DComponent

        pg, screen = rt.pg, rt.screen
        for entity, collider in rt.game.scene.query(Collider2DComponent):
            if (
                entity is rt.game.player
                or entity.has(_combatant_type())
                or not entity.has(Transform)
            ):
                continue
            x, y = world_position(entity)
            x, y = x + collider.offset_x, y + collider.offset_y
            w, h = collider.width / 2, collider.height / 2
            corners = {
                "tl": rt._field_screen_xy(x - w, y - h),
                "tr": rt._field_screen_xy(x + w, y - h),
                "bl": rt._field_screen_xy(x - w, y + h),
                "br": rt._field_screen_xy(x + w, y + h),
            }
            if collider.ladder:
                left, right = corners["tl"][0], corners["tr"][0]
                for k in range(
                    int(corners["tl"][1]), int(corners["bl"][1]), max(6, int(6 * zoom))
                ):
                    pg.draw.line(screen, (190, 140, 80), (int(left), k), (int(right), k), 2)
                pg.draw.line(screen, (150, 100, 60), corners["tl"], corners["bl"], 3)
                pg.draw.line(screen, (150, 100, 60), corners["tr"], corners["br"], 3)
            elif collider.shape == "slope_right":
                pg.draw.polygon(
                    screen, (88, 96, 120), [corners["bl"], corners["br"], corners["tr"]]
                )
            elif collider.shape == "slope_left":
                pg.draw.polygon(
                    screen, (88, 96, 120), [corners["bl"], corners["br"], corners["tl"]]
                )
            elif collider.shape == "box" and not collider.is_trigger:
                color = (120, 110, 90) if collider.one_way else (70, 78, 100)
                rect = pg.Rect(
                    int(corners["tl"][0]),
                    int(corners["tl"][1]),
                    int(corners["br"][0] - corners["tl"][0]),
                    int(corners["br"][1] - corners["tl"][1]),
                )
                pg.draw.rect(screen, color, rect)
                pg.draw.rect(screen, (150, 160, 190), rect, 1)

    # -- screen layer -----------------------------------------------------------------------------
    def _bar(self, rt, x, y, w, h, current, maximum, color):
        pg, screen = rt.pg, rt.screen
        pg.draw.rect(screen, (20, 22, 30), (int(x) - 1, int(y) - 1, int(w) + 2, int(h) + 2))
        fill = 0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
        pg.draw.rect(screen, (48, 52, 64), (int(x), int(y), int(w), int(h)))
        pg.draw.rect(screen, color, (int(x), int(y), int(w * fill), int(h)))

    def draw_overlay(self, rt):
        game = rt.game
        from .action_combat import ActionCombatComponent, parse_bindings
        from .combat import CombatantComponent

        combatant = game.player.try_get(CombatantComponent)
        # built on demand: the bars show before the first hit
        state = game.combat.state(game.player) if combatant is not None else None
        rt.panel((14, rt.height - 104, 380, 92))
        if state is not None:
            names = list(state.resources.names())
            life = combatant.life_resource
            if life in names:  # the life resource first
                names.remove(life)
                names.insert(0, life)
            colors = [(220, 70, 70), (80, 140, 255), (240, 200, 80)]
            for row, name in enumerate(names[:3]):
                value = state.resources.get(name)
                y = rt.height - 96 + row * 22
                label = name.upper() if len(name) <= 3 else name.capitalize()  # HP, MP, Rage
                rt.text(label, 26, y, size=18, color=(220, 225, 235))
                self._bar(rt, 120, y + 4, 170, 12, value.current, value.maximum, colors[row % 3])
                rt.text(f"{value.current:.0f}/{value.maximum:.0f}", 300, y, size=18)
        actor_id = game._actor_of(game.player)
        if actor_id is not None:
            progress = game.ensure_actor_progression(actor_id)
            threshold = float(game.action_progression.get("level_threshold", 1000.0))
            into = progress.experience - (progress.level - 1) * threshold
            rt.text(f"Lv {progress.level}", 26, rt.height - 30, size=18, color=(255, 220, 124))
            self._bar(rt, 120, rt.height - 25, 170, 6, into, threshold, (240, 200, 80))
        spec = game.player.try_get(ActionCombatComponent)
        if spec is not None:
            bindings = list(parse_bindings(spec.bindings).items())
            # centred, but never under the bars panel on the left
            x0 = max(rt.width / 2 - len(bindings) * 64 / 2, 14 + 380 + 16)
            labels = rt.manifest.get("battle", {}).get("skills", {})
            for index, (action, value) in enumerate(bindings):
                x = x0 + index * 64
                y = rt.height - 74
                rt.panel((int(x), y, 60, 46), fill=(16, 20, 32, 230))
                ability_id = game.action_combat.bound_ability(game.player, value)
                key = {"attack": "J", "dodge": "K"}.get(action, action.replace("skill_", ""))
                rt.text(key, x + 30, y + 34, size=15, color=(255, 220, 124), center=True)
                if not ability_id:  # nothing learned for this slot yet
                    rt.text("—", x + 30, y + 14, size=17, color=(110, 118, 135), center=True)
                    continue
                ability = game.project.gameplay_library.abilities.get(ability_id)
                left = game.action_combat.cooldown(game.player, ability_id)
                total = getattr(ability, "cooldown_seconds", 0.0) or left
                if left > 0 and total > 0:
                    shade = rt.pg.Surface((60, int(46 * min(1.0, left / total))), rt.pg.SRCALPHA)
                    shade.fill((0, 0, 0, 170))
                    rt.screen.blit(shade, (int(x), y))
                name = labels.get(ability_id, {}).get("label") or (
                    ability_id.split("_", 1)[-1] if ability_id.count("_") else ability_id
                )
                rt.text(name[:8], x + 30, y + 14, size=17, center=True)
                for cost in getattr(ability, "costs", ()):  # items it spends: how many are left
                    if cost.resource.startswith("item:"):
                        have = game.save.rpg_state.inventory.count(cost.resource[5:])
                        rt.text(f"x{have}", x + 42, y + 2, size=15, color=(170, 235, 190))
        rt.text(
            "Move: WASD  J: Attack  K: Dodge  1-4: Skills  L: Lock  F: Pick up  B: Bag  C: "
            "Skills  Esc: Pause",
            rt.width / 2,
            rt.height - 14,
            size=16,
            color=(170, 180, 200),
            center=True,
        )
        text, left = self.banner
        if left > 0:
            rt.text(text, rt.width / 2, 70, size=40, color=(255, 220, 124), center=True)
        down = getattr(game, "player_down", 0.0)
        if down > 0:
            shade = rt.pg.Surface((rt.width, rt.height), rt.pg.SRCALPHA)
            shade.fill((20, 0, 0, 120))
            rt.screen.blit(shade, (0, 0))
            rt.text(
                f"You fell — back in {down:.1f}s",
                rt.width / 2,
                rt.height / 2,
                size=36,
                color=(255, 200, 200),
                center=True,
            )


def _has_sprite(entity):
    from .components2d import SpriteRenderer2D

    sprite = entity.try_get(SpriteRenderer2D)
    return sprite is not None and bool(sprite.sprite_sheet_asset_id)


def _combatant_type():
    from .combat import CombatantComponent

    return CombatantComponent


__all__ = [
    "ARPG_ACTIONS",
    "COMBAT_MODES",
    "VIEWS",
    "ActionHud",
    "CombatSceneComponent",
    "combat_scene",
    "missing_action_bindings",
    "register_action_play_components",
]
