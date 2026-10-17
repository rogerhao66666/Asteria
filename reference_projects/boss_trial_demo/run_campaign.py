"""Play the whole Boss Trial campaign through the game host, start to finish.

Four maps, three bosses, four party members. The script walks the way a player would - talks to
people, works the shops and the workshop, trains jobs, levels up, tames a goblin, escapes a fight,
recruits, saves and loads, wins the throne - and counts what really happened. ``run()`` returns
the facts; ``python run_campaign.py`` prints them and exits 1 when something the list asks for is
missing.
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))
for key, value in (("SDL_VIDEODRIVER", "dummy"), ("SDL_AUDIODRIVER", "dummy")):
    os.environ.setdefault(key, value)

HERO = "hero_01"
SW = "w_sunbrand:hero_01"


class Campaign:
    def __init__(self, rt=None, seed=5, log=print):
        from asteria.editor import EditorDocument
        from asteria.project import Project
        from asteria.runtime.playable_test_runtime import PlayableTestRuntime

        project = Project.load_json(
            HERE / "project.asteria.json", EditorDocument().component_registry
        )
        self.rt = rt or PlayableTestRuntime(
            project, project.game_start.instantiate(project), HERE, width=960, height=540
        )
        if rt is None:
            self.rt.open()
        self.rt._ui_mode = "field"
        self.game.refine_rng = random.Random(seed)
        self.rng = random.Random(seed)
        self.facts = Counter()
        self.used = Counter()
        self.log = log

    @property
    def game(self):
        return self.rt.game

    def note(self, text):
        self.log(f"  {text}")

    def shot(self, name):
        """A hook for a real-window run: it saves a picture at the milestones."""
        if getattr(self, "on_shot", None) is not None:
            self.frames(45 if name.startswith("battle_") else 12)  # a boss intro zoom settles
            self.on_shot(name)

    # -- walking and talking ---------------------------------------------------------------
    def frames(self, count=3, dt=0.05):
        for _ in range(count):
            self.rt._frame([], dt)

    def scene_name(self):
        return self.game.scene.name

    def go(self, door_name):
        """Walk onto a door: the scene changes."""
        from asteria.core import Transform

        door = next(e for e in self.game.scene.entities() if e.name == door_name)
        point = door.get(Transform)
        player = self.game.player.get(Transform)
        player.x, player.y = point.x + 40, point.y  # a few steps off the door, then onto it
        self.game.field_step({})
        player.x, player.y = point.x, point.y
        before = self.game.scene.id
        self.game.field_step({})
        self.resolve()
        assert self.game.scene.id != before, f"{door_name} did not lead anywhere"
        self.frames(2)
        self.facts["map_changes"] += 1
        self.shot("map_" + self.scene_name().lower().replace(" ", "_"))

    def find(self, name):
        return next(e for e in self.game.scene.entities() if e.name == name)

    def talk(self, name, picks=()):
        """Stand in front of ``name`` facing it and press the interact key; answer the menu."""
        from asteria.core import Transform

        entity = self.find(name)
        point = entity.get(Transform)
        player = self.game.player.get(Transform)
        player.x, player.y = point.x, point.y + 14
        self.game.set_player_facing("up")
        picks = list(picks)
        self.game.field_step({"interact": 1.0})
        self.resolve(picks)
        self.rt._ui_mode = "field"  # a shop or a crafting window was opened for the script's calls
        if self.game.mode == "field" and not self.game.event_busy:
            self.game.field_step({"interact": 0.0})  # the key goes up again
        self.facts["talks"] += 1
        errors = list(self.game.event_errors)
        assert not errors, f"{name}: {errors}"

    def resolve(self, picks=()):
        picks = list(picks)
        for _ in range(400):
            if not self.game.event_busy:
                break
            runner = self.game._dialogue_runner()
            dialogue = None if runner is None else runner.dialogue
            if dialogue is not None and dialogue.choice is not None:
                self.game.choose(picks.pop(0) if picks else len(dialogue.choice.choices) - 1)
            elif dialogue is not None and dialogue.dialogue is not None:
                self.game.acknowledge_dialogue()
            else:
                self.game.update_events(0.1)
        else:
            raise AssertionError("an event never finished")
        self.frames(2)

    # -- fights ----------------------------------------------------------------------------
    def touch(self, name):
        """Walk into a foe in view: the encounter starts."""
        from asteria.core import Transform

        entity = self.find(name)
        point = entity.get(Transform)
        player = self.game.player.get(Transform)
        player.x, player.y = point.x, point.y + 2
        for _ in range(8):
            self.rt._frame([], 0.05)
            if self.game.mode == "battle":
                break
        assert self.game.mode == "battle", f"{name} did not start a fight"
        self.facts["fights"] += 1
        self.shot_pending = f"battle_{self.game.encounter_id}"
        tags = self.game.battle.member(HERO).subject.tags
        for tag in tags.values():
            if tag.startswith("weather."):
                self.facts["weather_" + tag.split(".", 1)[1]] += 1
        self.rt._advance_to_hero_turn()
        self.shot(self.shot_pending)

    FIRST = (
        "call_spirit",
        "dragon_form",
        "pass_the_torch",
        "bp_gift",
        "rekindle",
        "twilight_judgment",
        "word_of_doom",
        "pilfer",
    )

    def pick(self, actor):
        """The next skill of ``actor``: heal the weak, else the least used skill that works."""
        game = self.game
        build = game.battle.member(actor).ability_ids
        pool = [a for a in build if not game.ability_unavailable(actor, a) and a != "concoct"]
        self.rng.shuffle(pool)
        pool.sort(key=lambda a: (self.used[a], a not in self.FIRST))
        pool.sort(key=lambda a: not (a in self.FIRST and self.used[a] == 0))
        resources = game.battle.member(actor).subject.resources
        low = resources.current("vitality") < 0.4 * resources.maximum("vitality")
        guards = ("mend", "second_wind", "benediction", "purge", "shield_wall", "fortify")
        pool.sort(key=lambda a: (a in guards) != low)
        return pool

    def act(self, actor):
        game = self.game
        foes = game.active_enemy_ids()
        allies = [m for m in game.active_hero_ids() if m != actor]
        weakest = min(
            (*allies, actor),
            key=lambda m: (
                game.battle.member(m).subject.resources.current("vitality")
                / max(1.0, game.battle.member(m).subject.resources.maximum("vitality"))
            ),
        )
        for ability_id in self.pick(actor):
            relation = str(game.ability_relation(ability_id)).upper()
            if "OPPONENT" in relation:
                targets = (self.rng.choice(foes),)
            elif "ALLY" in relation and "ALL" not in relation:
                targets = (weakest,)
            else:
                targets = None
            definition = game.battle.ability_runtime.registry.get(ability_id)
            form = self.rng.choice(definition.forms)["form_id"] if definition.forms else None
            try:
                game.use_ability(actor, ability_id, targets, form=form)
            except Exception:  # noqa: BLE001 - a skill that cannot be used now is skipped
                continue
            self.used[ability_id] += 1
            self.facts["skills_cast"] += 1
            return ability_id
        return None

    def fight(self, limit=120):
        """Play the running battle with the party's skills until it is won."""
        game = self.game
        for _ in range(limit):
            if game.mode != "battle":
                break
            actor = self.rt._battle_actor()
            if actor is None:
                self.rt._advance_to_hero_turn()
                actor = self.rt._battle_actor()
                if actor is None:
                    break
            if self.act(actor) is None:
                game.end_turn()
                self.rt._advance_to_hero_turn()
                continue
            self.rt._after_hero_action()
            if self.rt._defeat:
                raise AssertionError("the party was defeated")
            if self.rt._victory:
                break
        assert self.rt._victory, "the battle was not won"
        self.dismiss()

    def dismiss(self):
        """The victory screen: confirm until the field is back."""
        import pygame

        confirm = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        for _ in range(2000):  # the choreography of a long fight plays out first
            self.rt._frame(confirm, 0.25)
            if not self.rt._victory and self.game.mode == "field":
                break
        state = (self.game.mode, self.rt._victory, self.game.encounter_id)
        assert self.game.mode == "field" and not self.rt._victory, state
        self.facts["victories"] += 1
        self.heal_if_low()

    def heal_if_low(self):
        """A rest between fights (the party camps) when anyone is under half health."""
        from asteria.events.world_commands import WorldCommand

        snapshots = self.game.save.rpg_state.actor_snapshots
        for snapshot in snapshots.values():
            values = snapshot.resources["values"].get("vitality")
            if values and values["maximum"] and values["current"] < 0.5 * values["maximum"]:
                self.game.world_commands.dispatch(WorldCommand("REST_PARTY", {}))
                self.facts["camps"] += 1
                return

    # -- the stages ------------------------------------------------------------------------
    def allocate(self):
        """Spend every skill, job and attribute point the hero has (as a player would)."""
        allocation = self.game.save.rpg_state.progression_allocations[HERO]
        spent = 0
        for graph_id in [g for g in allocation.definitions]:
            graph = allocation.definitions[graph_id]
            for _ in range(8):
                for node in graph.nodes:
                    while allocation.rank(graph_id, node.node_id) < node.max_rank:
                        try:
                            allocation.allocate(graph_id, node.node_id)
                        except ValueError:
                            break
                        spent += 1
        self.facts["tree_ranks"] += spent
        self.game.refresh_actor_combatants(HERO)
        return spent

    def level(self):
        return self.game.ensure_actor_progression(HERO).level

    def town(self):
        game = self.game
        self.note("Hearthfold: the Warden, the clerk, the shrine, the job teachers")
        assert self.scene_name() == "Hearthfold" and set(game.save.rpg_state.party_actor_ids) == {
            HERO,
            "hero_02",
        }
        self.talk("Warden Thessaly")
        assert game.world.reputation.get("wardens", 0) == 0
        assert game.quest_log.status("q_patrol") == "active"
        assert game.save.rpg_state.inventory.count("healing_herb") >= 3
        self.talk("Bounty Clerk")
        for _ in range(4):  # the shrine takes gold for levels
            self.talk("Shrine", picks=(0,))
        self.facts["levels"] = self.level()
        assert self.level() >= 6, self.level()
        self.allocate()
        for teacher, job, picks in (
            ("Mystic Teacher", "mystic", ()),
            ("Duelist Teacher", "duelist", ()),
            ("Weapon Master Dojo", "weapon_master", ()),
            ("Sage's Tower", "sage", ()),
        ):
            self.talk(teacher, picks)
            assert job in game.ensure_actor_progression(HERO).active_class_ids, job
            self.facts["job_changes"] += 1
        for _ in range(3):
            self.talk("Smith", picks=(0,))
        self.talk("Smith", picks=(1,))
        self.talk("Smith", picks=(2,))
        self.talk("Jeweler", picks=(0,))
        self.talk("Jeweler", picks=(1,))
        self.talk("Card Dealer", picks=(0,))
        self.facts["sockets"] = len(self.sunbrand().attachments)
        self.talk("Jeweler", picks=(2,))
        self.talk("Jeweler", picks=(0,))
        item = self.sunbrand()
        self.facts["refine_level"] = item.refine_level
        self.talk("Alchemist")
        assert game.open_crafting_station == "alchemy"
        game.craft({"base": ["iron_ore"], "catalyst": ["fire_dust"]}, station="alchemy")
        game.open_crafting_station = None
        self.facts["crafted"] += 1
        self.talk("Merchant")
        assert game.open_shop_id == "trial_shop"
        game.buy("ruby_item", 1, shop_id="trial_shop")
        game.open_shop_id = None
        self.facts["bought"] += 1
        self.talk("Breaker", picks=(1,))
        self.facts["disassembled"] += 1
        self.talk("Armory", picks=(0,))
        self.talk("Innkeeper Marla", picks=(0,))
        self.facts["rests"] += 1
        self.allocate()
        self.shot("town_ready")
        self.showman()

    def showman(self):
        """Showman Pip: every field command the story does not need, one menu entry each."""
        from asteria.core import Transform

        # every trick (0-9), the request (10-13: start, three tricks, bow, drop), the band (14)
        for pick in (*range(10), 10, 11, 11, 11, 12, 13, 14):
            self.talk("Showman Pip", picks=(pick,))
            self.facts["field_tricks"] += 1
        assert self.game.quest_log.status("q_show") == "completed"
        names = {e.name for e in self.game.scene.entities()}
        assert {"Lantern", "PipEcho"} <= names, names
        self.rt._frame([], 0.1)
        _ = Transform

    def sunbrand(self):
        return self.game.save.rpg_state.loadouts[HERO].equipped("weapon")[0]

    def lucky(self):
        class Lucky:
            def random(self):
                return 0.0

        return Lucky()

    def woods(self):
        game = self.game
        self.note("Whispering Woods: goblins, a tame slinger, the beast, Vesper")
        self.go("Road East")
        assert self.scene_name() == "Whispering Woods"
        assert game.battle_weather() is not None and game.battle_weather()[0] == "rain"
        slinger_3 = self.find("Goblin Slinger 3")
        from asteria.core import Transform

        start = (slinger_3.get(Transform).x, slinger_3.get(Transform).y)
        player = game.player.get(Transform)
        home = (player.x, player.y)
        player.x, player.y = 56 * 16.0, 3 * 16.0  # far off in a corner: the foes roam alone
        self.frames(120, 0.1)
        player.x, player.y = home
        now = (slinger_3.get(Transform).x, slinger_3.get(Transform).y)
        self.facts["foes_roamed"] = int(now != start)
        self.talk("Camp Scout")
        self.talk("Old Cache")
        self.facts["interactions"] += 1
        # the first group: run away from it
        self.touch("Goblin Slinger 1")
        assert game.escape_unavailable() == ""
        result = game.attempt_escape(HERO, rng=self.lucky())
        assert result.succeeded and game.mode == "field"
        self.rt._victory = False
        self.rt._turn_actor = None
        self.facts["escapes"] += 1
        # an ambush of slingers: tame one, then win
        self.touch("Goblin Berserker 2")
        slinger = next(e for e in game.active_enemy_ids() if e.startswith("goblin_slinger"))
        assert game.attempt_capture(HERO, slinger, rng=self.lucky())
        self.facts["tamed"] += 1
        self.fight()
        self.touch("Goblin Slinger 3")
        self.fight()
        pet = game.active_pet()
        assert pet is not None and pet.species_id == "slinger"
        species = game.pet_species(pet)
        while pet.level < 5:
            pet.gain(species, species.exp_per_battle * 4)
        self.facts["pet_level"] = pet.level
        assert game.evolve_pet(pet.instance_id) == "war_slinger"
        self.facts["pet_evolved"] += 1
        self.save_and_reload()
        game = self.game
        # report to the warden, then the beast
        self.go("Road West")
        self.talk("Warden Thessaly")
        assert game.quest_log.status("q_patrol") == "completed", game.quest_log.status("q_patrol")
        assert game.quest_log.status("q_beast") == "active"
        self.go("Road East")
        self.touch("Goblin Beast")
        assert "no_escape" in game.escape_unavailable()
        self.fight()
        self.talk("Vesper")
        assert "hero_03" in game.save.rpg_state.party_active_actor_ids
        self.facts["recruits"] += 1
        self.report("q_beast", "q_crypt")

    def crypt(self):
        game = self.game
        self.note("Catacombs: skeletons, a locked vault, the Ancient, Cael")
        self.go("Crypt Door")
        assert self.scene_name() == "Catacombs"
        self.talk("Sealed Vault")
        for name in ("Skeleton Grunt 1", "Skeleton Hunter 2"):
            self.touch(name)
            self.fight()
        game.set_classes(HERO, ["knight", "rogue"])  # a thief's pick for the sealed vault
        self.facts["job_changes"] += 1
        self.touch("Skeleton Ancient")
        assert "no_escape" in game.escape_unavailable()
        self.rt._advance_to_hero_turn()
        actor = self.rt._battle_actor()
        boss = next(e for e in game.active_enemy_ids() if e.startswith("skeleton_ancient"))
        if "pilfer" in game.battle.member(HERO).ability_ids and actor == HERO:
            game.use_ability(HERO, "pilfer", (boss,))
            self.facts["steals"] += 1
            self.rt._after_hero_action()
        self.fight()
        self.talk("Cael")
        assert "hero_04" in game.save.rpg_state.party_active_actor_ids
        self.facts["recruits"] += 1
        self.talk("Sealed Vault")
        self.facts["interactions"] += 1
        self.go("Stairs Up")
        self.report("q_crypt", "slay_vaelor", from_woods=True)
        self.go("Crypt Door")

    def throne(self):
        game = self.game
        self.note("Ember Throne: the full party against Vaelor")
        game.set_classes(HERO, ["knight", "hero"])
        self.facts["job_changes"] += 1
        self.go("Throne Door")
        assert self.scene_name() == "Ember Throne"
        self.touch("Vaelor")
        self.fight(limit=300)
        self.talk("Victory Banner")
        self.shot("victory")
        assert game.save.event_context.get_switch("game.complete")
        self.facts["game_complete"] = 1
        self.go("Stairs Down")
        self.go("Stairs Up")
        self.go("Road West")
        self.talk("Warden Thessaly")
        assert self.game.quest_log.status("slay_vaelor") == "completed"

    def report(self, done, started, *, from_woods=False):
        """Back to the Warden in town: the finished contract is paid, the next one starts."""
        if not from_woods:
            self.go("Road West")
        else:
            self.go("Road West")
        self.talk("Warden Thessaly")
        game = self.game
        assert game.quest_log.status(done) == "completed", (done, game.quest_log.status(done))
        assert game.quest_log.status(started) == "active", (
            started,
            game.quest_log.status(started),
        )
        self.facts["reports"] += 1
        self.go("Road East")

    def save_and_reload(self):
        """Save, throw the session away and load it again: nothing may change."""
        from asteria.runtime.game_save import GameRuntimeSave
        from asteria.runtime.game_session import GameSessionRuntime

        game = self.game
        before = (
            tuple(game.save.rpg_state.party_actor_ids),
            self.level(),
            {q: p.status for q, p in game.save.rpg_state.quests.items()},
            [p.species_id for p in game.save.rpg_state.pets],
        )
        game.sync_world_state()
        data = game.save.to_data()
        restored = GameRuntimeSave.from_data(data, self.rt.project)
        self.rt.save = restored
        self.rt.game = GameSessionRuntime(self.rt.project, restored)
        self.rt._ui_mode = "field"
        after = (
            tuple(self.game.save.rpg_state.party_actor_ids),
            self.level(),
            {q: p.status for q, p in self.game.save.rpg_state.quests.items()},
            [p.species_id for p in self.game.save.rpg_state.pets],
        )
        assert after == before, (before, after)
        self.game.refine_rng = self.rng
        self.facts["save_load"] += 1

    def run(self):
        self.town()
        self.woods()
        self.crypt()
        self.throne()
        return self.finish()

    def finish(self):
        game = self.game
        state = game.save.rpg_state
        facts = self.facts
        facts["party_size"] = len(state.party_active_actor_ids)
        facts["quests_done"] = sum(1 for p in state.quests.values() if p.status == "completed")
        facts["achievements"] = len(game.world.achievements)
        facts["warden_rep"] = int(game.world.reputation.get("wardens", 0))
        facts["items"] = len(state.inventory.counts) if hasattr(state.inventory, "counts") else 0
        return facts


REQUIRED = (
    "levels", "tree_ranks", "job_changes", "sockets", "refine_level", "crafted", "bought",
    "disassembled", "rests", "map_changes", "fights", "victories", "skills_cast", "escapes",
    "tamed", "pet_evolved", "recruits", "save_load", "game_complete",
)  # fmt: skip


def run(log=print):
    return Campaign(log=log).run()


def main(argv=None):
    facts = run()
    width = max(len(k) for k in facts)
    for key in sorted(facts):
        print(f"{key:<{width}}  {facts[key]}")
    missing = [k for k in REQUIRED if not facts.get(k)]
    if facts["party_size"] != 4 or facts["quests_done"] < 4:
        missing.append("party_or_quests")
    if missing:
        print("NOT DONE:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
