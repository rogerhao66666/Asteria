from __future__ import annotations

import random

from asteria.core import Transform
from asteria.events import EventRunner, EventScheduler, WorldCommandRouter
from asteria.events.timers import EventTimers
from asteria.runtime.backlog import MessageBacklog
from asteria.runtime.interaction import InteractionController
from asteria.runtime.pictures import PictureManager
from asteria.runtime.session.ability_use import AbilityUseMixin
from asteria.runtime.session.action_play import ActionPlayMixin
from asteria.runtime.session.battle_events import BattleEventsMixin
from asteria.runtime.session.builds import BuildsMixin
from asteria.runtime.session.economy import EconomyMixin
from asteria.runtime.session.encounters import EncountersMixin
from asteria.runtime.session.field_play import FieldPlayMixin
from asteria.runtime.session.gear import GearMixin
from asteria.runtime.session.interactions import InteractionsMixin
from asteria.runtime.session.inventory_use import InventoryUseMixin
from asteria.runtime.session.map_tiles import MapTilesMixin
from asteria.runtime.session.messages import MessagesMixin
from asteria.runtime.session.npc_state import NpcStateMixin
from asteria.runtime.session.party import PartyMixin
from asteria.runtime.session.pets import PetsMixin
from asteria.runtime.session.rewards import RewardsMixin
from asteria.runtime.session.scene_events import SceneEventsMixin
from asteria.runtime.session.strikes import StrikesMixin
from asteria.runtime.session.support import (  # noqa: F401 - re-exported
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)
from asteria.runtime.session.turns import TurnsMixin
from asteria.runtime.world_command_handlers import (
    move_entity_to_scene,
    register_standard_world_commands,
)


class GameSessionRuntime(
    FieldPlayMixin,
    ActionPlayMixin,
    GearMixin,
    SceneEventsMixin,
    NpcStateMixin,
    BattleEventsMixin,
    MessagesMixin,
    PartyMixin,
    InventoryUseMixin,
    BuildsMixin,
    EncountersMixin,
    AbilityUseMixin,
    PetsMixin,
    StrikesMixin,
    TurnsMixin,
    EconomyMixin,
    InteractionsMixin,
    MapTilesMixin,
    RewardsMixin,
):
    """Generic Project + GameRuntimeSave integration runtime.

    This is the engine-level seam used by reference/full-play validation. It does
    not know project-specific actor, boss, job, resource, weakness or party-size
    names. Project definitions provide those rules; GameRuntimeSave provides the
    mutable player state.
    """

    def __init__(self, project, runtime_save):
        runtime_save.validate(project)
        runtime_save.rpg_state.bind_database(project.rpg_database)
        self.project = project
        self.save = runtime_save
        self._configure_inventory()
        # short messages for the field (CMP-03 popups): {"text", "entity", "duration_ms"}
        self.notices = []
        self.scene = project.scene(runtime_save.scene_id)
        self.player = self.scene.get_entity(runtime_save.player_entity_id)
        if self.player is None and runtime_save.player_entity_id:
            # saved after a transfer: bring the player from the scene the project file puts it in
            for other in project.scenes():
                entity = other.get_entity(runtime_save.player_entity_id)
                if entity is not None:
                    move_entity_to_scene(entity, other, self.scene)
                    self.player = entity
                    break
        if self.player is None:
            raise GameSessionError("saved player entity does not exist")
        self.facing = runtime_save.player_facing
        self._turn_player_controller()  # a loaded save faces the way it was saved
        if runtime_save.player_position is not None:
            transform = self.player.get(Transform)
            transform.x, transform.y = runtime_save.player_position
        self.interaction = InteractionController(action="interact")
        from .interaction import TouchTriggerController

        self.touch = TouchTriggerController()
        self.struck_encounters = 0  # fights a field attack started (they open preemptive)
        self.pending_new_game = None  # a New Game Plus save the host starts next frame
        self.equip_offers = []  # EquipOffer: new gear the player is asked to wear
        self.sight_scale = 1.0  # how far field foes see the player (map areas set it)
        self.touch.arm(self.scene, self.player)
        self.mode = "field"
        self.battle = None
        self.encounter_id = None
        self.encounter_background = ""  # battle background asset of the area the fight began in
        self._enemy_ids = ()
        self._captured = set()
        self._pets_sent = set()
        self.enemy_levels = {}  # enemy member id -> level, when the project has level rules
        self._last_defeated = ()
        self.map_rules = None  # FieldMapRules, set when a tile field binds area rules
        self.field_tiles = None  # the tile field's blocking query, for pathfinding
        self.field_bounds = None  # (x0, y0, x1, y1) of the field map
        self.walkers = {}  # entity id -> PathFollower (WALK_TO)
        self.timers = EventTimers(runtime_save.event_context)
        self.pictures = PictureManager(runtime_save.event_context)
        self._localizer = None
        self._last_logged_line = None
        self.backlog = MessageBacklog(self._backlog_limit())
        self.battle_log = []
        self._forced_cast = False  # a state picked this action's targets
        self._log_sequence = 0
        self._logged_turn = None
        # Event programs run here: one foreground runner for interactions plus
        # the current scene's autorun/parallel scheduler.
        self.presentation_requests = []
        self.event_errors = []
        self.world_commands = register_standard_world_commands(WorldCommandRouter(), self)
        self.events = EventRunner(
            project.event_programs,
            context=runtime_save.event_context,
            world_commands=self.world_commands,
        )
        self.events.sequence_host = self
        if runtime_save.active_event is not None:
            self.events.restore(runtime_save.active_event)
        # Project-wide common events (EVT-03): autorun / parallel ones run while their switch is
        # on.
        self.common_events = EventScheduler(
            project.event_programs,
            context=runtime_save.event_context,
            world_commands=self.world_commands,
            sequence_host=self,
        )
        self.battle_events = None
        self.pending_followups = []  # event programs queued by world interactions (RPG-07)
        self.entity_facing = {}
        self.entity_animation = {}
        self.scene_events = None
        self.open_shop_id = None
        self.name_input_request = None  # NAME_INPUT: the name screen's request while open
        self.picture_choice_request = None  # PICTURE_CHOICE: the layout and the variable
        self.pet_storage_requested = False  # PET_STORAGE asked for the party / box screen
        self._pending_pet_moves = []  # (pet instance id, ability id) learned past max_moves
        self._species_foes = {}  # enemy member id -> the creature record of a species foe
        self.open_crafting_station = None
        self._field_simulation = {}
        self._grid_movers = {}  # scene id -> GridMoverSystem (grid characters)
        self.grid_reserved = ()  # cells the player's grid walk holds (column, row)
        self.player_lift = 0.0  # how high the player is off the ground (a ledge hop)
        self.area_music = ""  # the music of the map area the player is in ('' = none)
        self.area_title_shown = ""  # the last area name shown (reset by a scene change)
        self.area_title_requests = []  # area names to show (the field draws and clears them)
        self.sighting = None  # a character that noticed the player: walking up (SightTrigger2D)
        from asteria.runtime.grid_actors import RouteRunner

        self.routes = RouteRunner()  # scripted grid routes (GRID_ROUTE)
        self.route_hidden = set()  # entities a route hid (until shown or the scene changes)
        self.pending_area_programs = []  # area entry programs queued while an event runs
        self._route_names = {}  # entity id -> the names its route switches use
        self.player_story_moves = 0  # counts events moving the player (grid walk resets)
        self._story_hidden = set()  # entities a route / SHOW_ENTITY disabled
        self.emotes = {}  # entity id -> (emote key, seconds left): a mark over a character
        self._step_rng = random.Random(f"{self.project.id}:steps")
        self._tile_blocking = {}  # scene id -> tile map walls (set_tile_blocking)
        self._frame_collision_world = None
        from asteria.runtime.profiler import NullProfiler

        self.profiler = NullProfiler()
        self.field_input = None  # InputSnapshot for real-time control this frame (set_field_input)
        # real-time play with RPG actors (D22 A7): experience from defeated foes, level-ups this
        # field update
        self.action_progression = {
            "level_threshold": 1000.0,
            "ap_per_level": 2.0,
            "ability_points_per_level": 1.0,
        }
        self.progression_events = []
        self.player_down = 0.0  # seconds until the fallen player respawns (action scenes)
        self._action_spawn = {}  # scene id -> where the player respawns
        self._build_scene_events()
        # WLD-02: saved NPC state (visibility, position, flags...) and the "npc" condition source
        runtime_save.event_context.providers["npc"] = self._npc_value
        runtime_save.event_context.providers["rpg"] = self._rpg_value
        # the "audio" condition source: ``me`` / ``se`` while a fanfare / sound plays (a host
        # that plays sound sets ``plays_audio`` and clears them; headless they never wait)
        self.plays_audio = False
        self.audio_status = {"me": False, "se": False}
        runtime_save.event_context.providers["audio"] = self._audio_value
        self._tile_changes = {}  # scene id -> {"layer|x|y": tile} (SET_TILE, this visit)
        self.light = {}  # SET_LIGHT: the lit circle of a dark place (and its scene)
        self.tile_changes_version = 0
        from asteria.runtime.npc_state import apply_npc_states

        apply_npc_states(self.scene, self.world, self.entity_facing)
