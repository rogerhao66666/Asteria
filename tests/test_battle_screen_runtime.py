from copy import deepcopy
from types import SimpleNamespace

from asteria.assets import AssetRef
from asteria.assets.rpg_maker_mv_weapon import apply_weapon_overlays, weapon_overlay_for_loadout
from asteria.gameplay import (
    ActionCue,
    GameplaySubject,
    PresentationCue,
    ResourcePool,
    StatBlock,
    TagSet,
)
from asteria.graphics import SpriteClip, SpriteFrame, SpriteKeyframe, SpriteSheet
from asteria.presentation import (
    BattleAnimationRole,
    BattleCombatantVisual,
    BattlePresentationScene,
    BattleScreenRuntime,
    BattleUiRenderer,
    BattleVisualAnchor,
    CombatantOverlay,
    HeadlessBattleUiBackend,
)
from asteria.rpg import (
    BattleResourceDefinition,
    BattleResourceRuntime,
    BattleScheduler,
    BattleSchedulerDefinition,
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    PartyMember,
)
from asteria.runtime import AnimationClipSet, Camera2D


def _clip(name, frames, *, loop=False):
    return SpriteClip(name, [SpriteKeyframe(i, 0.1) for i in frames], loop)


def _assets():
    hero_sheet = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a1", "texture"),
        [SpriteFrame(i * 16, 0, 16, 24) for i in range(4)],
    )
    mimic_sheet = SpriteSheet(
        AssetRef("10000000-0000-4000-8000-0000000000a2", "texture"),
        [SpriteFrame(i * 24, 0, 24, 24) for i in range(4)],
    )
    clips = {
        "clips.hero": AnimationClipSet(
            {
                "idle": _clip("idle", [0], loop=True),
                "attack": _clip("attack", [1, 2]),
                "hit": _clip("hit", [2]),
                "ko": _clip("ko", [3]),
            }
        ),
        "clips.mimic": AnimationClipSet(
            {
                "idle": _clip("idle", [0], loop=True),
                "attack": _clip("attack", [1]),
                "hit": _clip("hit", [2]),
                "ko": _clip("ko", [3]),
            }
        ),
    }
    return {"sheet.hero": hero_sheet, "sheet.mimic": mimic_sheet}, clips


def _scene():
    return BattlePresentationScene(
        "batch103.reference",
        "battle.bg.reference",
        (
            BattleCombatantVisual("hero", "sheet.hero", "clips.hero", BattleVisualAnchor(72, 104)),
            BattleCombatantVisual(
                "mimic", "sheet.mimic", "clips.mimic", BattleVisualAnchor(232, 104, "left")
            ),
        ),
    )


def _screen():
    sheets, clips = _assets()
    return BattleScreenRuntime(_scene(), clips.get, sheets.get)


def _subject(hp):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def _battle_mirror():
    hero = PartyMember("hero", "heroes", _subject(75), initiative=100)
    mimic = PartyMember("mimic", "enemies", _subject(45), initiative=30)
    members = [hero, mimic]
    scheduler = BattleScheduler(
        members,
        BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100),
    )
    battle_resources = BattleResourceRuntime([BattleResourceDefinition("hp")], members)
    return SimpleNamespace(
        scheduler=scheduler,
        action_timing=None,
        battle_resources=battle_resources,
    )


def test_screen_runtime_fans_out_one_event_stream_to_animation_camera_and_feedback():
    screen = _screen()
    screen.coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "hero.attack",
                ActionCue("attack", 0, "animation", {"member_id": "hero", "role": "attack"}),
            ),
            PresentationCue(
                "hit.audio",
                ActionCue("hit", 0, "audio", {"member_id": "mimic", "sound_id": "sfx.hit"}),
            ),
        )
    )
    screen.coordinator.push_target_selection(("mimic",), primary_target_id="mimic")
    events = screen.consume_events()
    assert len(events) == 3
    assert screen.animation.combatant("hero").role == BattleAnimationRole.ATTACK
    assert screen.camera_feedback.target_ids == ("mimic",)


def test_equipped_weapon_overlay_changes_with_type_only_during_attack():
    system = {
        "weaponTypes": ["", "Sword", "Bow"],
        "attackMotions": [
            {"type": 0, "weaponImageId": 0},
            {"type": 1, "weaponImageId": 2},
            {"type": 2, "weaponImageId": 13},
        ],
    }
    screen = _screen()
    loadout = EquipmentLoadout((EquipmentSlotDefinition("weapon"),))
    loadout.equip(
        "weapon",
        EquippedItem(EquipmentDefinition("sword", slot="weapon", tags=("mv-weapon-type:sword",))),
    )
    sword = weapon_overlay_for_loadout(loadout, system, lambda name: "weapon.sword")
    screen.animation.set_overlay("hero", sword)
    assert all(
        draw.texture_asset_id != "weapon.sword"
        for draw in screen.animation.build_frame(Camera2D()).combatant_draws
    )

    screen.animation.combatant("hero").set_role("attack")
    attack = screen.animation.build_frame(Camera2D()).combatant_draws
    assert screen.animation.combatant("hero").role == "attack"
    assert any(
        draw.texture_asset_id == "weapon.sword" and draw.source == sword.frames[0]
        for draw in attack
    )

    bow = CombatantOverlay("weapon.bow", ((0, 0, 96, 64),))
    screen.animation.set_overlay("hero", bow)
    swapped = screen.animation.build_frame(Camera2D()).combatant_draws
    assert any(
        draw.texture_asset_id == "weapon.bow" and draw.source == bow.frames[0] for draw in swapped
    )
    assert all(draw.texture_asset_id != "weapon.sword" for draw in swapped)

    screen.animation.set_overlay("hero", None)
    cleared = screen.animation.build_frame(Camera2D()).combatant_draws
    assert all(draw.texture_asset_id != "weapon.bow" for draw in cleared)


def test_mv_weapon_overlays_follow_real_loadout_but_ignore_armor():
    system = {
        "weaponTypes": ["", "Sword", "Bow"],
        "attackMotions": [
            {"type": 0, "weaponImageId": 0},
            {"type": 1, "weaponImageId": 2},
            {"type": 2, "weaponImageId": 13},
        ],
    }
    loadout = EquipmentLoadout(
        (EquipmentSlotDefinition("weapon"), EquipmentSlotDefinition("armor"))
    )
    sword = EquippedItem(
        EquipmentDefinition("sword", slot="weapon", tags=("mv-weapon-type:sword",))
    )
    armor = EquippedItem(EquipmentDefinition("armor", slot="armor"))
    loadout.equip("weapon", sword)
    loadout.equip("armor", armor)
    screen = _screen()
    screen.animation.combatant("hero").set_role("attack")
    members = screen.animation._member_order

    apply_weapon_overlays(
        screen.animation, members, {"hero": loadout}, system, lambda name: f"mv.system.{name}"
    )
    first = screen.animation.build_frame(Camera2D()).combatant_draws
    assert any(draw.texture_asset_id == "mv.system.Weapons1" for draw in first)

    loadout.unequip("weapon", 0)
    loadout.equip(
        "weapon",
        EquippedItem(EquipmentDefinition("bow", slot="weapon", tags=("mv-weapon-type:bow",))),
    )
    apply_weapon_overlays(
        screen.animation, members, {"hero": loadout}, system, lambda name: f"mv.system.{name}"
    )
    second = screen.animation.build_frame(Camera2D()).combatant_draws
    assert any(draw.texture_asset_id == "mv.system.Weapons2" for draw in second)
    assert all(draw.texture_asset_id != "mv.system.Weapons1" for draw in second)


def test_sync_battle_is_read_only_and_builds_hud_timeline_side_view():
    battle = _battle_mirror()
    before_scheduler = deepcopy(battle.scheduler.to_data())
    before_resources = deepcopy(battle.battle_resources.to_data())
    screen = _screen()
    screen.sync_battle(battle, current_member_id="hero")
    assert battle.scheduler.to_data() == before_scheduler
    assert battle.battle_resources.to_data() == before_resources
    assert {x.member_id for x in screen.hud.members} == {"hero", "mimic"}
    assert screen.timeline.view.turns[0].member_id == "hero"
    assert screen.timeline.view.turns[0].is_current
    assert screen.side_by_member == {"hero": "heroes", "mimic": "enemies"}


def test_build_frame_applies_camera_feedback_without_mutating_base_camera():
    screen = _screen()
    screen.coordinator.push_target_selection(("mimic",), primary_target_id="mimic")
    screen.consume_events()
    camera = Camera2D(0, 0, 320, 180, 1)
    before = (camera.x, camera.y, camera.width, camera.height, camera.zoom)
    frame = screen.build_frame(camera)
    assert (camera.x, camera.y, camera.width, camera.height, camera.zoom) == before
    assert [x.member_id for x in frame.markers] == ["mimic"]
    assert len(frame.combatant_draws) == 2


class _TextureRecorder:
    def __init__(self):
        self.draws = ()

    def render(self, draws):
        self.draws = tuple(draws)


def test_render_runs_world_then_ui_path_and_drains_audio_once():
    screen = _screen()
    screen.coordinator.consume_timeline_cues(
        (
            PresentationCue(
                "hit.audio",
                ActionCue("hit", 0, "audio", {"member_id": "mimic", "sound_id": "sfx.hit"}),
            ),
        )
    )
    screen.consume_events()
    screen.sync_battle(_battle_mirror(), current_member_id="hero")

    ui_backend = HeadlessBattleUiBackend()
    ui_renderer = BattleUiRenderer(ui_backend)
    textures = _TextureRecorder()
    result = screen.render(Camera2D(), ui_renderer=ui_renderer, texture_renderer=textures)
    assert len(textures.draws) == 2
    assert ui_backend.ops[0] == ("begin", "batch103.reference")
    assert ui_backend.ops[-1] == ("end",)
    assert len(result.audio_cues) == 1
    assert screen.render(Camera2D(), ui_renderer=ui_renderer).audio_cues == ()


def test_screen_snapshot_restore_is_deterministic():
    screen = _screen()
    screen.sync_battle(_battle_mirror(), current_member_id="hero")
    screen.coordinator.push_target_selection(("mimic",), primary_target_id="mimic")
    screen.consume_events()
    screen.update(0.1)
    snapshot = screen.snapshot()

    restored = _screen()
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
