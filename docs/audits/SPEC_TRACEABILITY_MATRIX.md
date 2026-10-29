# SPEC_TRACEABILITY_MATRIX

**來源：** `ASTERIA_SPEC.md`（S）、`ASTERIA_ASSET_SPEC.md`（AS）、`ASTERIA_ASSET_PIPELINE.md`（AP）、`ASTERIA_ART_DIRECTION.md`（AD）。範圍決策依 `SCOPE_DECISIONS.md`（見 DECISION_LOG D5）。
**證據日期：** 2026-10-09，`d69817c` + 工作樹；CB4–CB14 的狀態更新於 2026-10-10（`ac51b3a`，見 DECISION_LOG D10）。

## 狀態定義（依 CODEX_PROMPT）

| 代碼 | 意義 |
|---|---|
| **A** | 已實作並驗證，包含必要的整合與驗證 |
| **B** | 已實作，但必要驗證未完成（例如只有單元／headless 測試，或沒有接上 runtime／editor） |
| **C** | 部分實作 |
| **D** | 未實作 |
| **E** | 正式取消 |

Class、介面、stub、mock 不算實作證據。只有單元測試不算整合完成。

**優先級：**
- **Core**：SPEC 的核心列舉
- **Eventual**：SPEC 原文寫「Eventually／Potential／may」
- **Deferred**：`SCOPE_DECISIONS.md` 延後的項目
- **Cancelled**：已取消

**驗證層級：** CI＝程式碼檢視、UT＝單元／契約測試、HI＝headless 整合、GS＝GUI smoke（Cocoa 或 offscreen Qt）、RM＝實機視窗、NE＝未執行。

**Batch 欄位**對應 REMAINING_WORK_PLAN 的 CB 編號。

---

## 1. Engine Core（S §6–§8、§33）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試證據 | 整合／實機 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| ENG-01 | S§6 | Core | 組合式 Entity/Component，可序列化、可檢視、可腳本存取 | `core/entity.py` `Entity`、`core/component.py`、`core/metadata.py` `component_schema`、`core/registry.py` | UT 多檔 | HI + GS（Inspector） | **A** | — | — |
| ENG-02 | S§6 | Core | 典型 component（Collider、CharacterController、Health、Resource、AbilitySet、Inventory、PlayerInput/AIController） | `runtime/character_control.py`（CharacterController2D、PlayerInput2D、AIController2D）；`gameplay/components.py`；`rpg/*` runtime | UT + HI | RM（`mv_import_real_window`：CharacterController2D 依 tile 與實體 Collider2D 行走；`gameplay_systems_real_window`） | **A** | —（playable 參考遊戲的玩家仍由 `_field_input` 移動，屬該宿主的實作選擇，元件本身已在實機使用） | D17-6 |
| ENG-03 | S§7 | Core | 系統導向 runtime（Animation/Physics/AI/Ability/Render System） | `runtime/systems.py` `AnimationSystem`、`CameraFollowSystem`；`runtime/collision.py` `CollisionSystem`；`core/system.py` `fixed_update` | UT | HI + RM（D19 `engine_systems_real_window`：`Application.run` 實機主迴圈中的 Animation／Collision／Camera／Action systems；`replay_RPG-10`：playable 的 field AI 與 spawn systems） | **A** | —（Ability 由 battle runtime 處理是設計選擇，不是缺口） | CB4、D19 |
| ENG-04 | S§8 | Core | 應用生命週期、game loop、delta time | `core/application.py` `Application.run`、`core/time.py` | UT | RM（pygame 3 影格） | **A** | — | — |
| ENG-05 | S§8 | Core | Fixed update（需要時） | `core/application.py` `fixed_timestep`、`step_fixed` | UT（確定性步進） | HI + RM（D19 `engine_systems_real_window`：真實時鐘 8.00 s → 400 fixed steps @50 Hz） | **A** | — | CB4、D19 |
| ENG-06 | S§8 | Core | Scene 生命週期、load/unload、序列化 | `core/scene.py`、`core/serialization.py`、`project.py` | UT | GS 存檔→重開 | **A** | — | — |
| ENG-07 | S§8 | Core | Scene 轉場、persistent entities | `core/scene_transition.py` `SceneTransition`、`PersistentComponent`；`Application.change_scene`／`advance_transition` | UT | RM（W-18 場景轉移；D19 `engine_systems_real_window`：persistent entity 經淡入淡出帶到下一個場景） | **A** | — | CB4、D19 |
| ENG-08 | S§8 | Core | Transform 位置／旋轉／縮放 | `core/transform.py` | UT | HI | **A** | — | — |
| ENG-09 | S§8 | Core | Transform 父子關係／階層 | `core/transform.py` `parent_id`、`world_transform`、`set_parent`；`editor/editing.py` `ReparentTransformCommand`；Inspector parent 下拉選單 | UT | RM（`editor_workflows_gui`：拖放改父層並保持世界座標，undo 還原） | **A** | — | CB4 |
| ENG-10 | S§8 | Core | Event bus／resource lifetime | `core/events.py` `EventBus`、`core/services.py`、`assets/runtime_resources.py`；戰鬥範圍圖片釋放（`PlayableTestRuntime` `release_resource_scope`） | UT + HI | HI + RM（D19 `battle_memory_real_window`：12 場戰鬥，每場後戰鬥範圍圖片 0 殘留、共釋放 108 張，RSS 無增長） | **A** | — | CB13、D19 |
| ENG-11 | S§8 | Core | Rendering：sprite、tile、layer、transparency | `runtime/draw.py`、`runtime/tile_draw.py`、`platform/pygame_backend.py` | UT | RM（MV tile + 角色截圖） | **A** | — | — |
| ENG-12 | S§8 | Core | Rendering：batching、render groups | `platform/moderngl_backend.py`（`16a6ebd` 復原，sprite batching）；`preview --backend moderngl` | UT（pygame／GL 像素對照） | RM（`gpu_playable_runtime`：GPU 畫面與合成畫面逐像素相同，56 fps；`vfx_moderngl_field` 15 draw calls／frame；`mv_import_gpu_night`） | **A** | —；pygame 仍為預設後端（依提案，待你決定是否改預設）；不宣稱效能提升 | CB9 |
| ENG-13 | S§8 | Core | Parallax、screen-space UI | `runtime/camera.py`、`runtime/draw.py`、MV parallax 匯入；`presentation/battle_ui_renderer.py` | UT | RM（D20 `engine_systems_real_window`：parallax 層移動 0.500× 遊戲層）＋canonical 戰鬥 UI（D15） | **A** | — | CB2、D20 |
| ENG-14 | S§8 | Core | 輸入：鍵盤／滑鼠 | `runtime/input_map.py` `InputActionMap`；`platform/pygame_input.py` `PygameInputSource`；playable runtime 改走 action map | UT | HI；實機視窗以合成按鍵事件驅動（`game_menus_more_real_window`、`cutscene_real_window`、`migrated_project_plays`） | **B** | 實體鍵盤與滑鼠需要人操作（M1） | CB4 |
| ENG-15 | S§8 | Core | 輸入：Gamepad、input actions、rebinding、多組控制方案 | `runtime/input_map.py`（鍵盤／gamepad 按鈕／軸）；`runtime/input_rebinding.py` `ControlsMenu`、`effective_input_map`；GameSettings v2 `input_overrides`（玩家層，不寫入專案）；遊戲內 Settings → Controls；editor `input_map_widget.py`（Input Map 分頁） | UT + HI（playable Controls 畫面重綁後移動） | GS（Input Map 分頁） | **B** | 鍵盤重綁已 RM（`controls_rebinding_real_window`）；gamepad 重綁 BLOCKED（無手把，M2／M8） | CB4、D17-3（`2eaffaf`） |
| ENG-16 | S§8 | Core | Collision：collider、trigger、layers/masks、broad phase、角色碰撞 | `runtime/collision.py` AABB／圓形、layers/masks、`SpatialHash` broad phase、trigger、`CombinedQuery`（tile + collider） | UT + benchmark（1000 colliders：948 對、3.7 ms） | RM（W-18；D19 `engine_systems_real_window`：trigger enter／stay／exit、layer／mask 過濾） | **A** | — | CB5、D19 |
| ENG-17 | S§8 | Core | Hitbox/hurtbox、地面／平台偵測 | `runtime/character_control.py` Hitbox2D／Hurtbox2D／HitboxSystem、側視地面偵測、one-way platform（Collider2D v2） | UT + HI | RM（D19 `engine_systems_real_window` hitbox 命中；`replay_ANI-05`：controller／hitbox 在 session field update） | **A** | — | D17-6、D19 |
| ENG-18 | S§8 | Core | 音訊：BGM、ambient、SFX、mixer、fades、spatial | `runtime/audio_mixer.py` `AudioMixer`（music／ambient／sfx 匯流排、淡入淡出）；`platform/pygame_audio.py`；CC0 音效 6 個 | UT（RecordingAudioDevice） | RM（CoreAudio 裝置播放 PASS；D15） | **B** | 可聽確認與延遲 NOT EXECUTED（M3／M4）；沒有 spatial audio | CB6 |
| ENG-19 | S§33 | Core | 穩定 ID、參照、驗證、可讀格式 | `core/ids.py`、`assets/registry.py`、`assets/serialization.py` | UT | GS | **A** | — | — |
| ENG-20 | S§33 | Core | 版本化 + 遷移 | `core/migration.py` `component_migration` 遷移鏈；`deserialize_component` 逐版遷移；`asteria-upgrade` CLI | UT | RM（D20 `migrated_project_plays`：v8 專案經 asteria-upgrade CLI 升到 v11，實機走動、E 觸發 boss、F5 存讀檔） | **A** | — | CB12、D20 |
| ENG-21 | S§33 | Core | Runtime 存檔（隊伍、背包、任務、開關、NPC、場景） | `rpg/save_state.py`、`runtime/game_save.py`、`events/state.py`；`runtime/save_slots.py`（三個欄位 + autosave、摘要、覆寫／刪除二次確認）；暫停選單 Save／Load、標題 L | UT + HI（playable 存入欄位 → 讀回比對） | RM（`save_slots_real_window`、`runtime_recovery`） | **A** | — | CB7、CB12、D17-3（`8bbc86b`） |
| ENG-22 | S§9 | Core | 穩定專案 ID 優先於路徑 | `assets/canonical.py` `AssetRef`、`assets/store.py` | UT | GS | **A** | — | — |
| ENG-23 | S§10 | Core | Prefab／Template／Variant／Override／傳播 | `core/prefab.py`（definition、variant、override、`sync_instance` 傳播）；`editor/prefab_commands.py`；shell Prefab 選單 | UT | RM（`editor_workflows_gui`：建立、放置、修改後套用回 prefab 並傳播到其他實例、還原） | **A** | — | CB7 |

## 2. Animation／Camera／VFX（S §11–§12、§44）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| ANI-01 | S§11 | Core | Sprite-sheet 匯入、影格切割、clip、循環 | `graphics/sprites.py`、`runtime/animation.py` `AnimatorState`、`assets/rpg_maker_mv.py` | UT | RM（MV 行走 12 影格） | **A** | — | — |
| ANI-02 | S§11 | Core | State machine、transition 參數 | `runtime/animation_state_machine.py`；machine 存在 sprite sheet metadata，由 `BattleVisualResolver` 帶進 clip set；editor `animation_state_machine_authoring.py`、`animation_state_machine_widget.py`（Animation States 分頁：節點、拖曳、transition、參數、預覽） | UT + HI | RM（`editor_d17_gui` 編輯器；D20 `replay_ANI-02`：作者狀態機決定戰鬥 clip） | **A** | — | CB8、D17-3（`584644b`）、D20 |
| ANI-03 | S§11、AP§25 | Core | Frame events | `SpriteKeyframe.events`；`AnimatorState.drain_events`；`AnimationSystem.listeners` | UT | RM（D19 `engine_systems_real_window`：AnimationSystem frame events 在實機主迴圈發出） | **A** | — | CB8、D19 |
| ANI-04 | S§11 | Core | 預覽 | `editor/animation_authoring.py`、`animation_editor_widget.py`（預覽用 runtime `AnimatorState`） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| ANI-05 | S§11 | Core | Action timeline（動畫、移動、hitbox、i-frame、cancel、VFX、SFX、camera、事件） | `gameplay/action_timeline.py`（movement、hitbox、iframe、cancel／combo window、gameplay_event cue）、`runtime/entity_actions.py`、PLAY_ACTION | UT + HI | RM（D19 `engine_systems_real_window` 的 movement／hitbox／vfx cue；`replay_ANI-05`） | **A** | —（ARPG 戰鬥本身依 SPEC §20 維持 Deferred） | D17-6、D19 |
| CAM-01 | S§12 | Core | Follow、smooth、dead zone、zoom、shake | `runtime/camera.py` `CameraFollow2D`、`presentation/battle_camera_feedback.py` | UT | HI + RM（canonical 戰鬥 camera shake 依 motion beat；D15） | **B** | 缺人眼確認（M5） | CB2 |
| CAM-02 | S§12 | Core | Look-ahead、bounds、target groups、boss／cutscene camera、transitions | `runtime/camera.py`（look-ahead、bounds、`CameraTargetGroup`、`CameraDirector`、shake）、`systems.py` `CameraFollowSystem`、`field_camera.py`（manifest `field.camera.follow` 跟隨鏡頭）、WORLD `CAMERA_FOCUS／RELEASE／SHAKE`；戰鬥 boss 開場鏡頭（encounter tag `boss`） | UT + HI | RM（跟隨、boss 開場、事件 focus；D20 `engine_systems_real_window` look-ahead 48–58 px、target group 中心誤差 0.5 px） | **A** | — | CB10、D17-3（`ca6cff1`）、D20 |
| VFX-01 | S§12 | Core | 粒子、hit flash、damage numbers、screen effects | `runtime/battle_presentation_adapters.py` VFX sprite sheet 播放、hit flash（screen_fx）、damage numbers（`presentation/battle_feedback.py`）；天氣粒子（`runtime/weather.py`）；粒子特效 `presentation/particles.py`（`particle_effect` 資產、`ParticleEmitter2D` 元件、PLAY_VFX、戰鬥時間軸 beat）、`runtime/particle_draw.py`、編輯器 Particle Effects（即時預覽） | UT | HI + RM（實機視窗 VFX 截圖；D15）＋D20 `particles_field_pygame`／`particles_field_moderngl`（約 59 fps）、`particles_battle_beat`、`editor_particles_gui` | **B** | 粒子功能已完成並有實機證據；外觀需要人眼確認（M10） | CB2 |
| VFX-02 | S§12、AD§12 | Core | 2D lights、normal maps、shadows、bloom、color grading、screen shaders | `render/lighting.py`、`render/postprocess.py`（headless 指令模型）；ModernGL 後端已復原 | UT | RM（`vfx_moderngl_field`、`vfx_pygame_field`、`vfx_gpu_battle_afterimage`、`mv_import_gpu_night`） | **B** | 光照、陰影、bloom、grading、vignette 已 RM；normal map 與 screen shader（內建／專案）只有 GL 測試；人工目視 M10 | CB9 |
| VFX-03 | S§12 | Core | Trails、afterimages、fog/weather/water | 部分（`render/environment.py`） | UT | RM（battle afterimage、雨 2000 粒子、水面） | **B** | afterimage、weather、water 已 RM；field trail 與 fog 只有 HI／GL 測試；人工目視 M10 | CB9 |
| CMP-01 | S§44 | Core | Baked/Layered/Attached/Procedural/Hybrid 並存 | `presentation/canonical.py`、`composition.py`、`actor_visual_layers.py`；`presentation/character_composition.py`（body sheet metadata 的 layer／attachment 解析成繪製部件）；`BattlePresentationRuntime` 在 body 前後繪製 | UT + HI（真實 canonical 戰鬥：layer 在後、attachment 在前、隨朝向鏡像） | RM（戰鬥；D19 replay `replay_CMP-01`：field 玩家的 layer／attachment 與戰鬥分層在實機 playable 視窗繪製） | **A** | — | CB2、D17-3（`c499639`）、D19 |
| CMP-02 | S§44.1 | Core | 通用 attachment／socket 契約 | `presentation/attachments.py`、`attachment_runtime.py`；socket 依 sheet 影格 key；`TextureDraw.rotation_deg`（pygame 與 ModernGL 都支援） | UT + HI（socket 逐格 key 帶動 attachment） | RM（`battle_layered_characters`，截圖已檢視） | **A** | — | CB0、CB2、D17-3（`c499639`） |
| CMP-03 | S§44.3 | Core | 通用 animated text／popup | `presentation/animated_text.py`、`text_render_integration.py` | UT | RM（D20 `replay_CMP-03`：field popup 使用通用 animated text，在角色上方上升淡出；SHOW_POPUP 指令） | **A** | — | CB2、D20 |
| CMP-04 | S§44.4 | Core | Editor／Python parity（attachment 撰寫） | `editor/character_composition_authoring.py`（undo、與 runtime 相同的 `parts()`）、`character_composition_widget.py`（Character Composition 分頁與影格預覽） | UT + GS | RM（Cocoa `editor_d17_gui`） | **A** | —（人工操作 M7 另列為人工驗證，不影響功能驗證） | CB2、D17-3（`c499639`） |

## 3. Gameplay 框架（S §13–§18）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| GP-01 | S§13–14 | Core | Stats（base/derived/modified）、Resources（任意） | `gameplay/stats.py`、`rpg/battle_resources.py` | UT | HI + playable | **A** | — | — |
| GP-02 | S§14 | Core | Ability：cost、cooldown、targeting、cast/recovery、tags、AI metadata | `gameplay/abilities.py`、`rpg/battle_timing.py`、`rpg/targeting.py` | UT | RM（D20 `replay_GP-02`：cost、targeting、cooldown、timeline 模式的 cast／recovery） | **A** | — | CB3、D20 |
| GP-03 | S§15 | Core | Effects、Triggers、Conditions（AND/OR/NOT）、Modifiers | `gameplay/effects.py`、`triggers.py`、`conditions.py` `ConditionGroup`、`modifiers.py` | UT | HI | **A** | — | — |
| GP-04 | S§16 | Core | 階層 tags、免 Python 公式 | `gameplay/tags.py`、`gameplay/formulas.py` `FormulaBuilder` | UT | HI + Editor 表單 | **A** | — | — |
| GP-05 | S§17 | Core | 行動解析 pipeline | `rpg/battle.py`、`battle_transactions.py`、`reactions.py` | UT（Batch 82–93） | RM（`gameplay_systems_real_window`：成本、目標、互動倍率、gauge、狀態在實機視窗的戰鬥中解析） | **A** | — | CB3 |
| GP-06 | S§18 | Core | State/status（duration、stacks、refresh、periodic、removal） | `gameplay/states.py`、`rpg/battle_states.py` | UT | HI | **A** | — | — |

## 4. RPG／Battle（S §19、§21–§25、§28）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| BTL-01 | S§19 | Eventual | 隊伍／敵群、回合排程、速度順序 | `rpg/battle.py`、`battle_scheduler.py` | UT | RM（`gameplay_systems_real_window`：四人隊伍 vs boss＋2 隨從，排程器決定回合，break 推遲回合） | **A** | — | CB3 |
| BTL-02 | S§19 | Eventual | 多段攻擊、反擊／追擊／反應、弱點／抗性、break | `rpg/action_sequences.py`、`reactions.py`、`interactions.py`、`gauge_composition.py` | UT | RM（D20 `replay_BTL-02`：DOT 固定／套倍率、雙武器弱點與抗性、破盾 ×2、Boost 連擊／增幅、副職業、逐回合加重的劇毒）；D20-6 `party_rpg_demo_real_window`（可遊玩的隊伍 RPG 式 demo，以按鍵操作） | **A** | — | CB3、CB-BR1、D20 |
| BTL-03 | S§19 | Eventual | 自訂資源、回合操作、boss 階段、戰鬥事件、戰鬥 AI | `rpg/battle_resources.py`、`enemy_ai.py` `BossPhaseDefinition` | UT | RM（`gameplay_systems_real_window`：stagger／rage／boost 資源、break 延後回合、boss 多階段；`replay_EVT-03` battle events；`battle_frame_pacing` 敵方 AI 回合）；D20-6 `party_rpg_demo_real_window`（可遊玩的隊伍 RPG 式 demo，以按鍵操作） | **A** | — | CB3、D19 |
| BTL-04 | S§19、§29 | Core | 戰鬥 UI／演出（HUD、時間軸、結果、選單、動畫、VFX、camera、audio、hit-stop、多段、結果轉場） | `runtime/battle_presentation_adapters.py` Canonical（動畫 sprite、motion sequence：動畫／VFX／audio／camera／flash、KO 同步、捕捉指令、側視 staging）；`runtime/battle_visuals.py` | UT（`test_canonical_battle_presentation.py`） | HI + RM（animation_smoothness、frame_pacing PASS；D15） | **B** | hit-stop 已接（D17）；可聽音訊、實體按鍵、手把未驗證（M1–M3） | D17-6 |
| RPG-01 | S§21 | Core | 背包：可堆疊／唯一、分類、容量、關鍵道具、消耗品、貨幣 | `rpg/items.py` `Inventory` | UT | RM（D20 `replay_RPG-01`：專案容量規則套用到事件與商店） | **A** | — | CB11、D20 |
| RPG-02 | S§21 | Core | 裝備：欄位、需求、modifier、tags、passives、set bonus、熟練度、升級 | `rpg/items.py`、`equipment_growth.py`、`resolved_build.py`；`rpg/equipment_sets.py`（件數門檻的 modifier／tag／能力） | UT | RM（D19 replay `replay_RPG-02`）＋`gameplay_systems_real_window`（裝備授予技能） | **A** | — | CB11、D19 |
| RPG-03 | S§21–22 | Core | 成長、職業／副職業、技能樹、多種解鎖貨幣、熟練度 | `rpg/progression*.py`、`actors.py`、`ability_build.py` | UT | GS（技能樹編輯器）+ playable | **A** | — | — |
| RPG-04 | S§23 | Core | 掉落（權重／保底／稀有、數量範圍、條件、難度／幸運） | `rpg/enemies.py`（chance、數量、條件、luck）；`rpg/drop_tables.py`（權重、保底計數存於 `world.counters`）；`RewardDefinition.drop_table_id`；Drop Tables 表單（RPG DB v27） | UT + HI（勝利結算抽表、保底觸發） | RM（D19 replay `replay_RPG-04`） | **A** | — | CB11、D17-3（`72ebb0c`）、D19 |
| RPG-05 | S§23 | Core | 經濟（買賣、多貨幣、庫存、定價） | `rpg/economy.py` `ShopDefinition`／`ShopRuntime`（多貨幣、買賣、庫存）；`OPEN_SHOP`；`runtime/game_menus.py` 商店畫面 | UT | RM（D19 replay `replay_RPG-05`）：買、賣、多貨幣、限量庫存 | **A** | — | CB11、D19 |
| RPG-06 | S§23 | Core | 製作（配方、材料、需求、工作台、成功率、品質、經驗、發現、失敗） | `rpg/composition.py`（工作台、成功率、失敗產出、品質等級、經驗）；`GameSessionRuntime.craft` | UT | RM（D19 replay `replay_RPG-06`）：事件開啟製作畫面並製作、配方發現 | **A** | — | CB11、D19 |
| RPG-07 | S§24 | Core | 世界互動框架（talk…custom、需求、check、結果、獎勵） | `rpg/world_interactions.py`（SPEC §24 全部欄位）、`GameSessionRuntime.perform_interaction`、INTERACT、Game Systems 表單 | UT + HI | RM（D19 replay `replay_RPG-07`） | **A** | — | D17-6、D19 |
| RPG-08 | S§25 | Core | 生物／夥伴（捕捉、收集、召喚、成長、收納） | `rpg/battle_lifecycle.py`（召喚）；`rpg/capture.py` `CaptureRule`；`attempt_capture`；bestiary captured 計數 | UT | RM（`gameplay_systems_real_window` 捕捉；D20 `replay_RPG-08`：召喚、預備隊上場、成長、收納、召喚物出現在戰鬥畫面） | **A** | — | CB11、D20 |
| RPG-09 | S§28 | Core | 基本 AI（idle/patrol/chase/attack/flee）、進階（狀態機、權重、門檻、階段） | `rpg/enemy_ai.py`（回合制）；`runtime/field_ai.py`；`rpg/behavior_tree.py` + `runtime/behavior_tree.py`（reactive selector、sequence、條件、chase／flee）；editor `behavior_tree_widget.py`（RPG DB v28） | UT + HI（playable field 實體依樹追擊／放棄） | 編輯器 RM（Cocoa）；RM（D19 replay `replay_RPG-09`）：行為樹在 session 中觸發遭遇 | **A** | — | CB11、D17-3（`7eb2372`）、D19 |
| RPG-10 | S§28 | Core | 遭遇（隨機／可見、生成區、wave、重生、稀有、boss、條件） | `rpg/enemies.py` `EncounterDefinition`；`runtime/field_ai.py` `SpawnSystem`（radius、max alive、respawn、waves、稀有、條件）、`VisibleEncounterComponent` | UT | RM（D19 replay `replay_RPG-10`）：生成、追擊、重生、可見遭遇開戰 | **A** | — | CB11、D19 |

## 5. 世界、事件、UI（S §26–§27、§29）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| EVT-01 | S§27 | Core | 可恢復的 Event VM（wait/resume、parallel、autorun、switch、variable、local、branch、call stack） | `events/vm.py`、`runner.py`、`scheduler.py`、`call_stack.py`、`state.py` | UT（Batch 36–44） | RM（D19 replay `replay_EVT-01`） | **A** | — | CB1、D19 |
| EVT-02 | S§27 | Core | 對話／選項、場景轉移、動畫／音訊／畫面效果、背包／隊伍／世界狀態動作 | `events/dialogue.py`；`runtime/world_command_handlers.py` 標準 WORLD handler；Event Editor 可輸入 WORLD 參數 | UT | RM（W-18、cutscene）＋RM（D19 replay `replay_EVT-02`）：選項分支、物品／貨幣指令、轉移 | **A** | — | CB1、D19 |
| EVT-03 | S§27 | Core | Common events、battle events、cutscenes、存讀檔恢復 | `events/common.py`（common events：call／autorun／parallel）、`events/lifecycle_bridge.py`（battle events：條件、once）、`runtime/game_session.py`（common scheduler、per-battle hook bus、cutscene API）、`editor/event_flow_*` | UT + HI | RM（`cutscene_real_window`）＋RM（D19 replay `replay_EVT-03`）：common events、battle events | **A** | — | D17-6、D19 |
| EVT-04 | S§27 | Core | Sequencer（平行軌道：移動、動畫、對話、camera、音樂、VFX、轉場） | `events/sequencer.py`（SEQUENCE 平行軌道、cutscene、skip、cancel、存讀）、`runtime/field_presentation.py`（SCREEN_FADE、PLAY_VFX）、`editor/event_flow_widget.py` SequenceEditorDialog、Authoring API track／move／say… | UT + HI | RM（movement／camera／VFX／letterbox／skip；D20 `replay_EVT-04`：dialogue 與 music track 平行） | **A** | — | D17-6、D20 |
| WLD-01 | S§26 | Core | 任務／目標／相依／獎勵／串聯 | `rpg/quests.py`（counter／item／defeat_enemy／switch 目標、前置、獎勵、串聯）；存檔 v6；`*_QUEST` WORLD 命令；任務日誌畫面 | UT | RM（D19 replay `replay_WLD-01`）：擊敗目標推進、事件驅動、串聯、任務畫面 | **A** | — | CB11、D19 |
| WLD-02 | S§26 | Core | NPC 狀態、聲望、關係、陣營、旗標、成就、圖鑑 | `rpg/world_record.py`（WorldRecord v2 `npcs`）；`runtime/npc_state.py`（`NpcIdentity2D`、`apply_npc_states`）；WORLD 指令 SET_NPC／MOVE_NPC；session `set_npc`／`move_npc` | UT + HI（NPC 狀態存讀、停用不繪製） | RM（W-18）＋RM（D19 replay `replay_WLD-02`）：聲望、關係、計數、成就與圖鑑畫面 | **A** | — | CB11、D17-3（`cd7894f`）、D19 |
| UI-01 | S§29 | Core | 標題、HUD、對話、背包／裝備／狀態、技能 | playable：標題、對話、HUD、Build；`runtime/status_menu.py`（Status／Items／Equipment／Skills，透過 `presentation/rpg_*_screen` runtime 投影） | UT + HI | RM（標題、HUD、對話、status 畫面使用道具與換裝、技能分頁：`game_menus_more_real_window`、`status_menu_real_window`） | **A** | — | D17-6 |
| UI-02 | S§29 | Core | 商店、任務、暫停／設定、存讀檔、game over | `runtime/game_menus.py`；playable 的 pause／任務／商店／存讀檔／game over 畫面 | UT | RM（任務、商店、暫停／設定、存讀檔、game over：`game_menus_more_real_window`、`save_slots_real_window`） | **A** | — | CB11 |

## 6. Editor（S §5、§30、§32、§34）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| EDT-01 | S§5 | Core | Project/hierarchy、Scene/map workspace、Inspector | `editor/shell.py`、`widgets.py` `ProjectTreeWidget`/`InspectorWidget`、`viewport_widget.py`、`tile_edit.py` | UT + GS | GS Cocoa（9 張截圖已檢視） | **A** | — | — |
| EDT-02 | S§5 | Core | Asset browser + asset 預覽 | `editor/asset_thumbnails.py`（已復原）；Inspector asset 下拉選單 | UT | RM（`editor_workflows_gui`：asset browser 縮圖） | **A** | — | CB14 |
| EDT-03 | S§5、§30 | Core | 結構化資料庫（搜尋、複製一份、參照、驗證） | `editor/integrated_authoring.py`、`authoring_hub_widget.py`、`record_operations.py`（批次編輯、MIXED 值）、9 個 authoring controller | UT + GS | RM（`editor_workflows_gui`：搜尋、複製一份、批次修改與 undo；`editor_tools_gui` Problems 面板參照驗證） | **A** | — | CB10 |
| EDT-04 | S§5 | Core | Event editor | `editor/event_editor_widget.py`、`event_editing.py` | UT + GS | RM（`editor_workflows_gui`：編輯器撰寫的事件在執行中的遊戲經 debugger 觸發並生效） | **A** | — | CB1 |
| EDT-05 | S§5 | Core | Animation editor | `editor/animation_authoring.py`、`animation_editor_widget.py`（格線、clip、影格事件、pivot、undo） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| EDT-06 | S§5 | Core | Action timeline editor | `editor/action_timeline_authoring.py`、`action_timeline_widget.py`（通道軌、拖曳 beat、預覽）；runtime 播放同一份 motion_sequences | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）；runtime 戰鬥播放 RM | **A** | — | — |
| EDT-07 | S§5 | Core | AI editor | `editor/enemy_ai_authoring.py`、`enemy_ai_widget.py`（規則、條件、boss phase、綁定敵人、決策預覽用 `EnemyAIRuntime.explain`） | UT + GS + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| EDT-08 | S§5 | Core | VFX tools | `editor/vfx_authoring.py`、`vfx_widget.py`；runtime `battle_visuals.vfx_placement／vfx_rect／vfx_keyframe` | UT + GS + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）；戰鬥 renderer 依 placement 繪製（HI） | **A** | — | — |
| EDT-09 | S§5、§32 | Core | Script editor（語法高亮、自動完成、API 補全、錯誤導覽、traceback、reload） | `editor/code_workspace.py`、`script_tools.py`（語法高亮、Authoring API 補全、traceback 跳行、腳本檔、reload）、`authoring/runner.py` | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（補全清單量測；popup 是獨立視窗，截圖抓不到） | **A** | — | — |
| EDT-10 | S§5、§34 | Core | Debugger／runtime 檢視／debug actions | `runtime/debugger.py`、`runtime/debug_server.py`（只限 loopback、token）、`editor/debugger_widget.py` | UT + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（附加到另外啟動的遊戲 process，give_item 成功） | **A** | — | — |
| EDT-11 | S§5、§34 | Core | Play-test：執行專案／目前場景／從選定點出生／快速重啟／log | `editor/runtime_launcher.py`（debug、spawn、log）、`playmode.py`、`shell.py`（Play from Selection、Restart Play）、`runtime/preview.py --spawn` | UT + HI | RM（`editor_workflows_gui`：Play from Selection、Restart；`editor_to_runtime_playtest`） | **A** | — | CB10 |
| EDT-12 | S§5 | Core | Undo/redo | `editor/commands.py`（共用 command stack） | UT + GS | GS | **A** | — | — |
| EDT-13 | S§5 | Core | 複製／貼上／剪下、複製一份／刪除 | 實體 cut／copy／paste／duplicate；紀錄 `record_operations.py` cut／copy／paste（新 id、單一 undo）；快捷鍵依焦點分派 | UT + GS | RM（`editor_workflows_gui`：視窗快捷鍵複製／貼上／剪下） | **A** | — | CB10 |
| EDT-14 | S§5 | Core | 多選、拖放、搜尋／篩選／排序、右鍵選單、快捷鍵、批次編輯 | 多選、紀錄篩選與排序、右鍵選單、快捷鍵、批次編輯；hierarchy 拖放（`hierarchy.drop_entities`，以 model 套用） | UT + GS | RM（`editor_workflows_gui`：搜尋、多選、拖放＋undo、快捷鍵、批次編輯） | **A** | — | D17-6 |
| EDT-15 | S§5 | Core | 驗證 + 錯誤導覽 | `editor/problems.py`（收集全部問題並附位置）、`problems_widget.py`（Problems dock、篩選、跳轉） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（含跳轉） | **A** | — | — |
| EDT-16 | D2 | Core | 通用 Character/Entity Inspector（sprite 選擇、Actor 外觀、Entity↔Actor 連結、縮圖） | `runtime/actor_link.py`、`editor/actor_appearance.py`、`assets/character_visual.py`；shell「Place Character from Sprite Sheet…」「Set Actor Appearance…」 | UT | RM（D20 `editor_characters_gui`：Cocoa 編輯器匯入 sprite sheet → Actor → 放置 → 在 live game 找到角色；Actor 外觀；縮圖） | **A** | — | CB14、D20 |
| EDT-17 | S§31 | Eventual | Gameplay System Builder | — | — | — | **D** | SPEC §31『should eventually』— Eventually，不是 release blocker | 後續 |
| EDT-18 | S§32 | Eventual | Plugins（components、systems、panels、importers…） | — | — | — | **D** | SPEC §32 未要求當前版本的 plugin runtime — Eventually；保留既有擴充介面 | 後續 |
| EDT-19 | S§34 | Eventual | Profiling（frame/AI/collision/entity/particles/draw calls/memory） | `runtime/profiler.py`；`asteria-preview --profile`；debugger `profile_start／profile／profile_reset`；editor `profiler_widget.py`（Profiler dock，讀取執行中遊戲） | UT + HI | RM（D15 profile；`editor_d17_gui` profiler_dock 讀取執行中遊戲，截圖已檢視） | **A** | pygame 的 draw calls／GPU time 如實標 Unsupported（見 ENG-12 提案） | CB13、D17-3（`42f4db3`） |

## 7. Asset Pipeline（AS、AP、AD）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| AST-01 | AP§46 #1–6 | Core | Canonical 動畫／角色 schema、sprite 匯入、任意影格尺寸、grid slicing、方向對應 | `assets/canonical.py`、`importers.py`、`codecs.py`、`rpg_maker_mv.py` | UT | RM（MV 48×48 與 96×96） | **A** | — | — |
| AST-02 | AP§46 #7 | Core | Pivot 編輯 | anchor 中繼資料；Animation Editor pivot 欄位（`animation_authoring.set_pivot`） | UT + GS | RM（`editor_workflows_gui`：pivot 修改與 undo） | **A** | — | CB10 |
| AST-03 | AP§46 #9–12 | Core | FPS／時序、驗證、canonical 存讀 | `assets/quality_gate.py`、`usability_gate.py`、`serialization.py`、`store.py` | UT | GS | **A** | — | — |
| AST-04 | AP§46 #10、§48 | Core | 動畫事件會觸發 | 見 ANI-03 | UT | RM（同 ANI-03：D19 `engine_systems_real_window` frame events） | **A** | — | CB8、D19 |
| AST-05 | AP§46 #13、§48 | Core | Runtime 播放整合 | field 行走（`playable_test_runtime`）；canonical 戰鬥 sprite 動畫（`runtime/battle_visuals.py`、`battle_presentation_adapters.py`） | UT + HI | RM（field 行走；戰鬥 animation_smoothness 量測 88–89 格／10 s） | **A** | — | — |
| AST-06 | AP§48 | Core | 專案 build 可以打包 | `project_tools.export_game`（資源、CREDITS／LICENSE、`engine/asteria`、`run_game.py`）；`build_pyz`（單檔，解壓到使用者 cache、存檔在使用者資料夾）；`build_macos_app`；`package_game`；`asteria-export --pyz --app`；editor File → Export Game… | UT + HI（`python -I` 在 repo 外啟動 folder／.pyz／.app，確認載入的是內附引擎） | RM（`packaged_app_real_window`、editor `export_game`） | **A** | Finder 雙擊（Gatekeeper）屬人工 M6，不是本需求的驗收條件；免直譯器執行檔已由 D100 補上（macOS；Windows／Linux 未建置、未簽 Developer ID） | CB12、D17-3（`9ea2d01`）、D100 |
| AST-07 | AS§35 Phase A | Core | 類別：Character、NPC、Monster、Tileset、Prop、Portrait、Icon、VFX、Skill、Item、Equipment、Animation、Scene | `assets/*`（character_bundle、monster、tileset、prop、portrait、icon、vfx）；Item／Equipment 的 `icon_id`（`runtime/menu_icons.py`，商店與狀態選單繪製；編輯器下拉選圖示；MV 匯入保留 IconSet 圖示） | UT | RM（`asset_categories_real_window` 11 類；D20 `menu_icons_real_window`：商店、Items、Equipment 以真實按鍵開啟並繪出物品／裝備圖示）；立繪已 RM | **A** | — | CB13、D20 |
| AST-08 | AS§35 Phase A | Core | 類別：Projectile、UI asset、Prefab、Audio（播放） | Prefab：`core/prefab.py`；Audio：`runtime/audio_mixer.py`；Projectile、UI asset：`assets/sprite_kinds.py`（golden 涵蓋） | UT | RM（D20 `asset_categories_real_window`：projectile、UI；`editor_workflows_gui` prefab；`audio_playback_device` 實機播放，可聽性為人工 M3） | **A** | — | CB13、D20 |
| AST-09 | AS§34 | Core | Golden 測試套件（11 類） | `validation/golden.py`（8 項檢查）、`tests/golden/`（11 個 golden asset、baseline、README 的更新規則）、`scripts/update_golden_baselines.py` | UT + HI | 每次 commit 都執行（測試基礎設施） | **A** | — | — |
| AST-10 | AS§33、AD | Core（內容） | 正式 Starter Pack 美術 | — | — | — | **D（Deferred content）** | 依 SCOPE_DECISIONS，改用授權明確的免費素材；屬於 JRPG Demo 階段 | Deferred |
| AST-11 | AP§17、§21 | Core | Atlas packing、auto-fix | `graphics/atlas.py`、`assets/autofix.py`、`assets/asset_package.py` | UT | RM（D20 `editor_characters_gui`：Asset 清單 Auto-fix Image 預覽／備份／破壞性確認，Pack into Atlas 產出 PNG＋regions JSON） | **A** | — | CB13、D20 |
| AST-12 | AP Part A §33–36 | Eventual | Prompt／AI provider／video-to-sprite | — | — | — | **E** | 依 SCOPE_DECISIONS 停止 AI 生成 | — |
| AST-13 | CODEX_HANDOFF | Core | MV 只在 asset 邊界（不進 Runtime/Battle/Scene/Presentation） | `assets/rpg_maker_mv*.py`；`asteria.assets` 對 MV 模組改為延遲載入；`runtime/component_registry.py`（project tools 不再經由 editor 載入） | UT（文字規則涵蓋核心層、authoring、validation、頂層模組）+ HI（子行程跑 field、canonical 戰鬥、存檔，確認沒有任何 MV 模組被載入）；39 個 `mv_reference` 測試 PASS | RM（`mv_import_real_window`、`mv_import_gpu_night`：匯入的專案遊玩時不載入任何 MV 模組）；W-18 PASS | **A** | — | CB0、D17-3（`8e22457`） |

## 8. 壓力測試、範本、取消項目（S §35–§36、CG）

| ID | 來源 | 優先 | 需求 | 狀態 | 備註 |
|---|---|---|---|---|---|
| STR-01 | S§35 | Core | JRPG stress test（四人隊伍、職業、弱點、break、boost、passive、回合操作、NPC 互動、捕捉／夥伴、多階段 boss） | **A** | `validation/jrpg_stress.py` 在參考專案的真實 session 一次展示 13 項；RM `gameplay_systems_real_window`（實機視窗、canonical 戰鬥畫面）。找到並修正：戰鬥主體缺 StateRuntime、break 不可達、`broken` 未定義（D18）。haste_song／slow_hex 改變速度並影響排程器的下一個回合（D19 `aa25d27`，根因：速度變化沒進到 scheduler） |
| STR-02 | S§35 | Deferred | ARPG stress test | **D（Deferred）** | 依 SCOPE_DECISIONS 延後 |
| ARPG-01 | S§20 | Deferred | 即時 ARPG（jump、dash、i-frame、combo、cancel、hitbox、knockback、projectile、lock-on、hitstop、即時 AI） | **D（Deferred）** | 沒有 ARPG 實作（D19 退役了沒人使用的合成演出負載 `arpg_reference_workload.py`）；character controller、hitbox、action timeline 等通用元件已存在 |
| TPL-01 | S§36 | Eventual | Starter 範本（Empty／Classic JRPG／Advanced JRPG／ARPG） | **C** | 只有 Empty（New Project + starter tileset）和 Reference World。D18 重新分類：SPEC §36 原文為「Potential templates」，依本表圖例屬 Eventual，不列 blocker |
| CG-01 | S「Character Generator」 | Cancelled | Editor 端可選的分層角色產生器 | **E** | `SCOPE_DECISIONS.md`；通用能力的處理見 D2 |

---

## A–E 統計（含分母說明）

**分母規則：**
- E 不計入分母。
- Deferred（依 SCOPE_DECISIONS 延後：STR-02、ARPG-01）和 Deferred content（AST-10）列在「不在本期」欄位，也不計入 active 分母。
- Eventual（EDT-17、EDT-18、EDT-19、BTL-01–03）照 SPEC 原文是「eventually」，**仍然計入** active 分母，因為原始 SPEC 有列出、而且沒有被延後。

| 子系統 | A | B | C | D | E | 不在本期 | Active 分母（A+B+C+D） | A 比例 | A+B 比例 |
|---|---|---|---|---|---|---|---|---|---|
| Engine Core（ENG） | 20 | 3 | 0 | 0 | 0 | 0 | 23 | 87% | 100% |
| Animation／Camera／VFX／Composition | 10 | 4 | 0 | 0 | 0 | 0 | 14 | 71% | 100% |
| Gameplay（GP） | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 100% | 100% |
| RPG／Battle（BTL、RPG） | 13 | 1 | 0 | 0 | 0 | 0 | 14 | 93% | 100% |
| 世界／事件／UI（EVT、WLD、UI） | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 100% | 100% |
| Editor（EDT） | 17 | 0 | 0 | 2 | 0 | 0 | 19 | 89% | 89% |
| Asset Pipeline（AST） | 11 | 0 | 0 | 0 | 1 | 1 | 11 | 100% | 100% |
| 壓力測試／範本／Generator | 1 | 0 | 1 | 0 | 1 | 2 | 2 | 50% | 50% |
| **合計** | **86** | **8** | **1** | **2** | **2** | **3** | **97** | **89%** | **97%** |

（D20 由腳本從本表逐列重算（第 8 節的 6 欄表格一併計入）；上方表格取代先前各期的統計。以下各期註記保留原文作為歷史。）

**2026-10-12 D20（續）：** AST-07 由 B 升為 A（物品／裝備圖示，`menu_icons_real_window`）。VFX-01 的功能缺口（粒子發射器資料）已補上並有實機證據（`particles_field_*`、`particles_battle_beat`、`editor_particles_gui`），剩下人工目視 M10，維持 B。→ **A86／B8／C1／D2**。

**2026-10-12 D20：** 13 項由 B 升為 A，依據是新的實機證據（`REAL_MACHINE_VALIDATION.md` 項目 36–40）：
- `b_items_replay` 新增 7 項：EVT-04、RPG-01、RPG-08、GP-02、BTL-02、ANI-02、CMP-03（CMP-03 另有新的 runtime 使用者：field popup）。
- `engine_systems_real_window` 新增 parallax 與 target group：升級 ENG-13、CAM-02。
- `migrated_project_plays`：升級 ENG-20。
- `editor_characters_gui`（Cocoa 編輯器）：升級 EDT-16、AST-11。
- `asset_categories_real_window`＋既有 prefab／音訊實機項：升級 AST-08。

AST-07 仍為 B（Item、Equipment 沒有實機畫面）。ENG-14 仍為 B（實機只有合成按鍵事件，實體鍵盤／滑鼠為人工 M1）。→ **A85／B9／C1／D2**（D19 表格逐列重算為 A71／B22：D19 註記的 A72 多算 1 項，本次以腳本重算更正）。

**2026-10-11 D19：** 23 項由 B 升為 A，依據是新的實機證據（`REAL_MACHINE_VALIDATION.md` 項目 29–31）：
- `engine_systems_real_window`：`Application.run` 實機主迴圈。升級 ENG-03、ENG-05、ENG-07、ENG-16、ENG-17、ANI-03、ANI-05，以及 AST-04（即 ANI-03 的動畫事件）。
- `battle_memory_real_window`：升級 ENG-10。
- `b_items_replay`：session 層整合測試在實機 playable 視窗重跑，斷言不變。升級 RPG-02、RPG-04、RPG-05、RPG-06、RPG-07、RPG-09、RPG-10、EVT-01、EVT-02、EVT-03、WLD-01、WLD-02、CMP-01，並為 ANI-05 補證。
- 既有的 `gameplay_systems_real_window`：升級 BTL-03。

CAM-02 補上 look-ahead 實機證據，target group 仍缺，維持 B。→ **A72／B22／C1／D2**（D18 為 A49／B45／C1／D2）。

**D19 CB15 掃描：** 退役 35 個無法從產品進入點觸及的模組（見 CB15_RETIREMENT_REVIEW Part F）。原本引用其中模組的 ENG-10、CAM-01、VFX-01、ARPG-01 已改為引用產品實際使用的模組；狀態不變。

**2026-10-10 更新（CB3–CB14 及 CB11 之後）：** 2026-10-09 原始稽核時是 A 17／B 20／C 44／D 16；CB4–CB14 之後是 A17／B38／C33／D9。A 沒有增加，因為 A 需要實機（RM）驗證，而這一輪全部只有 UT／HI／offscreen GS。新的 B 項目都缺 RM，請見各列「缺口」欄。

**2026-10-11 更新（D16：CB13、CB10、CAM-02）：** A17／B50／C24／D6 → **A26／B56／C12／D3**。9 項升為 A（ANI-04、EDT-05、EDT-06、EDT-07、EDT-08、EDT-09、EDT-10、EDT-15、AST-09）：Editor 工具依 EDT-01 同樣的標準——在實機 Cocoa 視窗執行、量測並由工程師檢視截圖（`evidence/real_machine/editor_*.png`）；AST-09 是每次 commit 都執行的測試基礎設施。這些 A 不包含「有人實際上手使用」，那仍是人工項目。

**2026-10-11 D17 Traceability Reconciliation：** 依程式碼、測試與整合證據重新檢查過期註記（RPG-07、UI-01、AST-05、RPG-10、UI-02、ENG-03、ENG-13、ENG-21、EDT-04）。只有 AST-05 改變狀態（C → A，依實機 field 行走與戰鬥動畫量測）；其餘只修正缺口描述。RPG-07、UI-01 維持 C。→ **A27／B56／C11／D3**。

**2026-10-11 D17 Phase 2：** EVT-03、EVT-04、ENG-02、ENG-17、ANI-05、RPG-07、UI-01、EDT-14 由 C／D 完成實作並經 HI（playable runtime／game session）或 GS 驗證，列為 **B**（缺實機）。→ **A27／B64／C4／D2**。

**2026-10-11 D17 Phase 3：** ENG-15、ENG-21、ANI-02、CMP-01／02／04、RPG-04、RPG-09、WLD-02、CAM-02、EDT-19、AST-06、AST-13 的功能缺口已實作並經 HI／GS 驗證；全部仍缺實機，維持 **B**。AST-13 重驗時發現 W-18 的功能缺口（MV 地圖匯入後無法遊玩），記為新的 Functional gap。→ **A27／B64／C4／D2**（不變）。

（共 102 列 = 97 active + 2 E + 3 不在本期。統計由腳本從本表計算。）

**解讀：**
- A 比例低的主因不是缺少程式碼，而是 **B（已實作但沒接線或沒驗證）和 C（部分實作）合計 64 項**。其中最大的一群（BTL-04、CMP-*、VFX-01、EVT-01、UI-01）屬於同一個整合缺口：Runtime 沒有消費 Presentation 和 Event VM。
- **測試全綠不等於 closure**（`SCOPE_DECISIONS.md`）：1922 個通過的測試，大多落在 UT 層。

**2026-10-11 D17 Phase 6：** 實機（Apple M5、Cocoa、真實 SDL 按鍵事件）新增 9 項檢查，截圖逐張檢視，修正 2 個缺陷（boss 開場鏡頭殘影、缺字形）。ENG-21、CMP-02、AST-06、EDT-19 所有面向都有實機證據 → **A**；其餘 B 的缺少證據已逐項寫在缺口欄。→ **A31／B60／C4／D2**。

**2026-10-11 D18（Consolidated Closure）：** W-18 修復（MV 匯入可遊玩）、ENG-12 GPU 呈現、VFX-02／VFX-03 實作、STR-01 展示、CB15 退役、新增實機檢查（gameplay、menus、editor workflows、GPU、VFX、MV）。逐列依證據重評：ENG-02、ENG-09、ENG-12、ENG-23、CMP-04、GP-05、BTL-01、UI-01、UI-02、EDT-02、EDT-03、EDT-04、EDT-11、EDT-13、EDT-14、AST-02、AST-13、STR-01 → **A**；VFX-02、VFX-03 C → **B**；TPL-01 優先級依 SPEC 原文改為 Eventual（仍為 C）。→ **A49／B45／C1／D2**（另 2 項 E；C、D 全為 Eventual）。
