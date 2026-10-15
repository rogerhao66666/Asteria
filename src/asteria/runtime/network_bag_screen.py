"""Read-only view of the authoritative server inventory for opted-in projects."""

from __future__ import annotations

from asteria.runtime.game_menus import CraftingScreen
from asteria.runtime.skill_tree_screen import SkillTreeScreen


class NetworkBagScreen:
    def __init__(self, runtime):
        self.rt = runtime
        self.closed = False

    def handle(self, dt):
        if self.rt.input.just_pressed("cancel") or self.rt.input.just_pressed("bag"):
            self.closed = True

    def draw(self):
        rt = self.rt
        rt._draw_backdrop()
        bridge = rt.multiplayer_bridge
        state = bridge.state
        local = next(
            (p for p in state.get("players", []) if p["player_id"] == bridge.player_id), {}
        )
        x, y = 24, 80
        rt.panel((x, y, rt.width - 48, rt.height - 110))
        rt.text("Co-op Inventory", x + 18, y + 14, size=28, color=(255, 220, 124))
        rt.text(f"Experience: {local.get('experience', 0)}", x + 18, y + 52, size=20)
        inventory = local.get("inventory", {})
        lines = [
            f"{item.replace('_', ' ').title()} x {quantity}"
            for item, quantity in sorted(inventory.items())
        ] or ["No items yet"]
        for index, line in enumerate(lines[:6]):
            rt.text(line, x + 18, y + 86 + index * 26, size=20)
        rt.text(
            "Boss reward: full XP to contributors; loot to one contributor",
            x + 18,
            rt.height - 76,
            size=14,
        )
        rt.text("B / Esc: close", x + 18, rt.height - 52, size=16)


class NetworkCraftingScreen(CraftingScreen):
    """Keep the project's recipe display; confirmation submits its selected materials."""

    def __init__(self, runtime, station=""):
        self.rt = runtime
        super().__init__(runtime.game, station)

    def confirm(self, rng=None):
        rows = self.rows()
        if not rows:
            return None
        row = rows[min(self.index, len(rows) - 1)]
        recipe = self.game.project.rpg_database.composition_recipes[row.recipe_id]
        payload = {step.step_id: list(step.item_ids) for step in recipe.selections}
        command_id = self.game.craft(payload, station=self.station)
        self.message = "Craft requested from server"
        return command_id

    def close(self):
        self.rt.multiplayer_bridge.send_command("close_crafting", {})


class NetworkSkillTreeScreen(SkillTreeScreen):
    """Learning and numbered hotbar binding are confirmed by server snapshots."""

    def learn(self):
        graph = self.graph()
        if graph is None or self.node_id is None:
            return False
        self.rt.game.allocate_progression(self.actor_id, graph.graph_id, self.node_id)
        self._say("Learning requested from server")
        return True

    def handle(self, dt=0.0):
        super().handle(dt)
        graph = self.graph()
        if self.closed or graph is None or self.node_id is None:
            return
        allocation = self._allocation()
        rank = allocation.rank(graph.graph_id, self.node_id)
        abilities = tuple(
            ability
            for level in range(1, rank + 1)
            for ability in graph.node(self.node_id).reward_for_rank(level).granted_abilities
        )
        if not abilities:
            return
        for number in range(1, 5):
            action = f"skill_{number}"
            if self.rt.input.just_pressed(action):
                self.rt.multiplayer_bridge.send_command(
                    "bind_skill", {"action": action, "ability_id": abilities[-1]}
                )
                self._say(f"Slot {number} binding requested from server")

    def draw(self):
        super().draw()
        self.rt.text(
            "1–4: bind learned skill to slot",
            36,
            self.rt.height - 48,
            size=16,
            color=(170, 205, 230),
        )
