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
    TRACKED = ("party_rush", "rush_blow", "intercept", "chase_strike")  # from the battle log
    PICKED = (  # counted when the party uses them
        "momentum_strike",
        "soul_burst",
        "elemental_weave",
        "art_rending_gale",
        "art_whirlwind",
        "art_dawn_edge",
        "art_iron_vow",
    )

    def _watch(self):
        """Count what really happened in fights (covers, follow-ups, combos, blocked blows)."""
        from asteria.runtime.game_session import GameSessionRuntime

        if getattr(GameSessionRuntime, "_campaign_watch", False):
            return
        original = GameSessionRuntime._log
        facts = self.facts

        def counting(session, kind, **values):
            entry = original(session, kind, **values)
            if kind == "action" and entry.ability_id in self.TRACKED:
                facts[f"used_{entry.ability_id}"] += 1
            if kind == "hit_check" and "outcome.block" in str(entry.data):
                facts["blocked_blows"] += 1  # a defender's Block halved a blow
            return entry

        GameSessionRuntime._log = counting
        GameSessionRuntime._campaign_watch = True

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
        self._watch()
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

        self.resolve()  # an event still queued (a battle's tally) finishes first
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

        self.resolve()  # a line still open (a battle event's) is read first
        entity = self.find(name)
        point = entity.get(Transform)
        player = self.game.player.get(Transform)
        player.x, player.y = point.x, point.y + 14
        self.game.set_player_facing("up")
        picks = list(picks)
        self.game.field_step({"interact": 0.0})  # a key held before (a real press) goes up first
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
        "momentum_strike",
        "soul_burst",
        "party_rush",
        "call_spirit",
        "dragon_form",
        "pass_the_torch",
        "bp_gift",
        "rekindle",
        "twilight_judgment",
        "word_of_doom",
        "pilfer",
        "elemental_weave",
        "art_rending_gale",
        "art_whirlwind",
        "art_dawn_edge",
        "art_iron_vow",
    )

    def pick(self, actor):
        """The next skill of ``actor``: heal the weak, else the least used skill that works."""
        game = self.game
        build = game.battle.member(actor).ability_ids
        pool = [
            a
            for a in build
            if not game.ability_unavailable(actor, a) and a not in ("concoct", "rush_blow")
        ]
        self.rng.shuffle(pool)
        pool.sort(key=lambda a: (self.used[a], a not in self.FIRST))
        pool.sort(key=lambda a: not (a in self.FIRST and self.used[a] == 0))
        resources = game.battle.member(actor).subject.resources
        low = resources.current("vitality") < 0.4 * resources.maximum("vitality")
        guards = ("mend", "second_wind", "benediction", "purge", "shield_wall", "fortify")
        pool.sort(key=lambda a: (a in guards) != low)
        if not self.facts["used_momentum_strike"] and "party_rush" in pool:
            pool.remove("party_rush")  # Momentum is saved for the strike first
        for finisher in ("soul_burst", "momentum_strike"):  # a finisher goes as soon as it can
            if finisher in pool and not low:
                pool.remove(finisher)
                pool.insert(0, finisher)
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
            if ability_id in self.PICKED:
                self.facts[f"used_{ability_id}"] += 1
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

    def strike(self, name, ability_id, distance):
        """Swing or sling at a foe in view from ``distance`` to its left: the hit starts its fight
        preemptive (the foe gives up the first round)."""
        from asteria.core import Transform

        game = self.game
        self.resolve()
        foe = self.find(name).get(Transform)
        player = game.player.get(Transform)
        player.x, player.y = foe.x - distance, foe.y
        game.set_player_facing("right")
        before = game.struck_encounters
        result = game.action_combat.use(game.player, ability_id)
        assert result in (None, "used", "combo") or result is True, result
        for _ in range(30):
            self.rt._frame([], 0.03)
            if game.mode == "battle":
                break
        assert game.mode == "battle" and game.struck_encounters == before + 1, name
        assert game.opening == "preemptive", game.opening
        self.facts[f"field_{ability_id}"] += 1
        self.facts["fights"] += 1
        self.rt._advance_to_hero_turn()
        self.shot(f"battle_{game.encounter_id}_struck")

    def menu_choose(self, actor, action_id):
        """Press through the battle command menu to the row ``action_id`` (opening the More
        page when the command waits there) and confirm it."""
        commands = self.rt.battle_commands
        for _ in range(2):
            ids = [r.action_id for r in commands.entries(actor)]
            if action_id in ids:
                commands.cursor = ids.index(action_id)
                return commands.press("confirm", actor)
            if "root:More" not in ids:
                break
            commands.cursor = ids.index("root:More")
            commands.press("confirm", actor)
            self.facts["command_more_page"] += 1
        raise AssertionError(f"{action_id} is not in the menu: {ids}")

    def turn_of(self, actor_id, limit=40):
        """Play the others' turns until ``actor_id`` acts."""
        for _ in range(limit):
            actor = self.rt._battle_actor()
            if actor is None:
                self.rt._advance_to_hero_turn()
                continue
            if actor == actor_id:
                return actor
            if self.act(actor) is None:
                self.game.end_turn()
                self.rt._advance_to_hero_turn()
            else:
                self.rt._after_hero_action()
        raise AssertionError(f"{actor_id} never got a turn")

    def menus(self):
        """The command pages and the weave's input steps, through the real command menu."""
        game = self.game
        commands = self.rt.battle_commands
        hero = self.turn_of(HERO)
        commands.reset()
        labels = {r.action_id: r.label for r in commands.entries(hero)}
        assert labels.get("root:Attack") == "Fight", labels
        self.menu_choose(hero, "root:Escape")  # on the More page; running is not taken here
        if game.mode != "battle":
            raise AssertionError("ran away by mistake")
        commands.reset()
        if self.menu_choose(hero, "root:Attack") is False:
            ids = [r.action_id for r in commands.entries(hero)]
            self.menu_choose(hero, ids[0])
            if commands.mode == "target":
                self.menu_choose(hero, commands.entries(hero)[0].action_id)
        self.rt._after_hero_action()
        vesper = self.turn_of("hero_03")
        commands.reset()
        self.menu_choose(vesper, "root:Skills")
        self.menu_choose(vesper, "elemental_weave")
        assert commands.mode == "steps", commands.mode
        self.menu_choose(vesper, "storm")
        self.menu_choose(vesper, "overcharge")
        acted = self.menu_choose(vesper, "step:done")
        if not acted and commands.mode == "target":
            acted = self.menu_choose(vesper, commands.entries(vesper)[0].action_id)
        assert acted, commands.message
        self.facts["weave_steps"] += 1
        self.facts["used_elemental_weave"] += 1
        self.rt._after_hero_action()

    def staged(self, kind):
        """The fight stands by its staging record (the adapter's combatant anchors)."""
        screen = self.rt._battle_presentation.screen
        visuals = {v.member_id: v for v in screen.scene.combatants}
        heroes = [v for k, v in visuals.items() if k.startswith("hero_")]
        if kind == "portrait":
            assert heroes and all(v.body_hidden for v in heroes), "party bodies are drawn"
        else:
            xs = sorted(round(v.anchor.x) for v in heroes)
            assert xs and xs[0] == 236 and len(set(xs)) == len(xs), xs
        self.facts[f"staged_{kind}"] += 1

    def learn_arts(self):
        """The Old Master teaches four arts; two slots hold them at first."""
        from asteria.runtime.game_session import GameSessionError

        game = self.game
        self.talk("Old Master", picks=(0,))
        arts = ("art_rending_gale", "art_whirlwind", "art_dawn_edge", "art_iron_vow")
        assert set(arts) <= set(game.slot_candidates(HERO)), game.slot_candidates(HERO)
        _equipped, capacity = game.ability_slots(HERO)
        for art in arts[:capacity]:
            game.equip_ability(HERO, art)
        try:
            game.equip_ability(HERO, arts[capacity])
        except GameSessionError:
            self.facts["slots_full"] += 1
        build = game.resolve_actor_build(HERO).abilities
        assert arts[0] in build and arts[capacity] not in build, build
        self.facts["arts_learned"] = len(arts)

    def reslot(self):
        """At a higher level the slots grow: every art is set, one swapped out and back."""
        game = self.game
        arts = ("art_rending_gale", "art_whirlwind", "art_dawn_edge", "art_iron_vow")
        equipped, capacity = game.ability_slots(HERO)
        assert capacity == 4, capacity
        for art in arts:
            if art not in game.ability_slots(HERO)[0]:
                game.equip_ability(HERO, art)
        game.unequip_ability(HERO, "art_whirlwind")
        assert "art_whirlwind" not in game.resolve_actor_build(HERO).abilities
        game.equip_ability(HERO, "art_whirlwind")
        self.facts["slots_grown"] += 1

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
    def allocate(self, actor_id=HERO):
        """Spend every skill, job and attribute point ``actor_id`` has (as a player would)."""
        allocation = self.game.save.rpg_state.progression_allocations.get(actor_id)
        if allocation is None:
            return 0
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
        self.game.refresh_actor_combatants(actor_id)
        return spent

    HALL = {"hero_02": 0, "hero_04": 6, "hero_03": 3}  # Job Hall menu: advance, advance, train

    def advance(self, actor_id, job, tier, level):
        """At the Job Hall: train ``actor_id`` up to ``level``, then take ``job`` (tier 1 or 2)."""
        base = self.HALL[actor_id]
        for _ in range(8):
            if self.game.ensure_actor_progression(actor_id).level >= level:
                break
            self.talk("Job Master", picks=(base + 2,))
            self.facts["trainings"] += 1
        self.talk("Job Master", picks=(base + tier - 1,))
        active = self.game.ensure_actor_progression(actor_id).active_class_ids
        assert job in active and len(active) == 2, (actor_id, active)  # main job + sub job
        self.facts["job_advances"] += 1
        self.allocate(actor_id)

    def level(self):
        return self.game.ensure_actor_progression(HERO).level

    def town(self):
        game = self.game
        self.note("Hearthfold: the Warden, the clerk, the shrine, the job teachers")
        assert self.scene_name() == "Hearthfold"
        assert list(game.save.rpg_state.party_actor_ids) == [HERO]  # the hero sets out alone
        self.recruit("Mira", "hero_02")  # the guild: Mira is there from the start
        self.talk("Guildmaster Orla", picks=(0,))  # she waits at the guild again...
        assert "hero_02" not in game.save.rpg_state.party_actor_ids
        self.facts["partings"] += 1
        self.recruit("Mira", "hero_02")  # ...and comes back when asked
        self.advance("hero_02", "priest", 1, 5)  # Cleric -> Priest at the Job Hall
        self.outfit("hero_02")
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
        self.learn_arts()  # slot-limited arts from the Old Master
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

    def recruit(self, name, actor_id):
        """Talk to a companion waiting at the guild: they join the party."""
        self.talk(name)
        assert actor_id in self.game.save.rpg_state.party_active_actor_ids, name
        self.facts["recruits"] += 1

    OUTFIT = {"hero_02": (0, "dawn"), "hero_03": (1, "grave"), "hero_04": (2, "zealot")}

    def outfit(self, actor_id, *, card=None):
        """At the Outfitter and the workshop: the companion's set, a fused gem and a card in its
        sockets, an enchant on its set weapon, a protected refine of its armour."""
        game = self.game
        pick, set_id = self.OUTFIT[actor_id]
        self.talk("Outfitter", picks=(pick,))
        loadout = game.save.rpg_state.loadouts[actor_id]
        worn = {x.equipment.equipment_id for x in loadout.equipped()}
        pieces = [e for e in game.project.rpg_database.equipment_sets[set_id].equipment_ids]
        assert set(pieces) <= worn, (actor_id, worn)
        active = {(set_, bonus.pieces) for set_, bonus in loadout.active_set_bonuses()}
        assert (set_id, 3) in active, ("no 3-piece set bonus", actor_id, active)
        self.facts["sets_worn"] += 1
        # fuse two gems into a flawless one and set it in the weapon
        gem = {"hero_02": "topaz", "hero_03": "amethyst", "hero_04": "ruby"}[actor_id]
        state = game.save.rpg_state
        state.currencies["gold"] = state.currencies.get("gold", 0.0)
        while state.inventory.count(f"{gem}_item") < 2:
            if gem == "amethyst":
                game.craft(
                    {"base": ["moon_shard"], "catalyst": ["ice_crystal"]}, station="alchemy"
                )
            else:
                game.open_shop("trial_shop")
                game.buy(f"{gem}_item", 1, shop_id="trial_shop")
                game.open_shop_id = None
        game.craft({"base": [f"{gem}_item"], "catalyst": [f"{gem}_item"]}, station="alchemy")
        self.facts["gems_fused"] += 1
        game.socket_item(actor_id, "slot:weapon", "g1", f"flawless_{gem}_item")
        if card is not None:  # a boss card goes into the armour
            assert state.inventory.count(card) >= 1, f"{card} did not drop"
            game.socket_item(actor_id, "slot:armor", "c1", card)
            self.facts["cards_socketed"] += 1
        game.upgrade_equipment(actor_id, "slot:weapon", "kindle")  # opens the card socket
        game.upgrade_equipment(actor_id, "slot:weapon", "star")
        self.facts["enchants"] += 1
        game.open_shop("trial_shop")
        game.buy("blessed_scroll", 1, shop_id="trial_shop")
        game.buy("silver_ore", 3, shop_id="trial_shop")
        game.open_shop_id = None
        for protect in (False, False, True):
            result = game.refine_equipment(actor_id, "slot:armor", protect=protect)
            self.facts["armor_refines"] += 1
            self.facts["protected_refines"] += int(protect)
            _ = result
        game.refresh_actor_combatants(actor_id)

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
        self.talk("Camp Scout")  # before the goblins start roaming toward the road
        self.talk("Old Cache")
        self.facts["interactions"] += 1
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
        # the first group: run away from it
        self.touch("Goblin Slinger 1")
        assert game.escape_unavailable() == ""
        result = game.attempt_escape(HERO, rng=self.lucky())
        assert result.succeeded and game.mode == "field"
        self.rt._victory = False
        self.rt._turn_actor = None
        self.facts["escapes"] += 1
        # an ambush of slingers: tame one, then win
        self.touch("Goblin Slinger 2")
        slinger = next(e for e in game.active_enemy_ids() if e.startswith("goblin_slinger"))
        assert game.attempt_capture(HERO, slinger, rng=self.lucky())
        self.facts["tamed"] += 1
        self.fight()
        self.strike("Goblin Slinger 3", "field_slash", 16)
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
        self.talk("Vesper")  # she will wait at the guild in town
        assert "hero_03" not in game.save.rpg_state.party_active_actor_ids
        self.report("q_beast", "q_crypt", hire=("Vesper", "hero_03"))

    def crypt(self):
        game = self.game
        self.note("Catacombs: skeletons, a locked vault, the Ancient, Cael")
        self.go("Crypt Door")
        assert self.scene_name() == "Catacombs"
        self.talk("Sealed Vault")
        self.strike("Skeleton Hunter 1", "sling_throw", 56)  # a stone from afar
        self.fight()
        self.touch("Skeleton Hunter 2")  # the guards stand in their rank (side-view template)
        self.staged("sideview")
        self.menus()
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
        self.talk("Cael")  # he will wait at the guild in town
        self.talk("Sealed Vault")
        self.facts["interactions"] += 1
        self.go("Stairs Up")
        self.report("q_crypt", "slay_vaelor", from_woods=True, hire=("Cael", "hero_04"))
        self.go("Crypt Door")

    def throne(self):
        game = self.game
        self.note("Ember Throne: the full party against Vaelor")
        game.set_classes(HERO, ["knight", "hero"])
        self.facts["job_changes"] += 1
        self.go("Stairs Up")  # back to town: every companion takes the third job of their line
        self.go("Road West")
        for actor_id, job in (
            ("hero_02", "bishop"),
            ("hero_03", "death_lord"),
            ("hero_04", "heretic"),
        ):
            self.advance(actor_id, job, 2, 10)
        self.go("Road East")
        self.go("Crypt Door")
        self.go("Throne Door")
        assert self.scene_name() == "Ember Throne"
        self.reslot()
        self.touch("Acolyte Vigil")  # hold out eight rounds (round turns, gauntlet rules)
        assert game.rules.rules_id == "vigil_gauntlet", game.rules.rules_id
        self.staged("portrait")  # the party only in its HUD
        self.fight(limit=300)
        self.facts["vigil_survived"] += 1
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

    def report(self, done, started, *, from_woods=False, hire=None):
        """Back to the Warden in town: the finished contract is paid, the next one starts;
        ``hire`` = (name, actor id) of a companion waiting at the guild."""
        _ = from_woods
        self.go("Road West")
        if hire is not None:
            self.recruit(*hire)
            job = {"hero_03": "lich", "hero_04": "zealot"}[hire[1]]
            self.advance(hire[1], job, 1, 5)
            card = {"hero_03": "card_beast_item", "hero_04": "card_ancient_item"}[hire[1]]
            self.outfit(hire[1], card=card)
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
    "tamed", "pet_evolved", "recruits", "partings", "save_load", "game_complete",
    "job_advances", "trainings", "sets_worn", "gems_fused", "cards_socketed", "enchants",
    "armor_refines", "protected_refines", "vigil_survived", "used_party_rush",
    "used_rush_blow", "used_momentum_strike", "used_soul_burst", "used_intercept",
    "used_chase_strike", "blocked_blows", "field_field_slash", "field_sling_throw",
    "staged_sideview", "staged_portrait", "command_more_page", "weave_steps",
    "used_elemental_weave", "arts_learned", "slots_full", "slots_grown",
    "used_art_rending_gale", "used_art_dawn_edge", "used_art_iron_vow",
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
