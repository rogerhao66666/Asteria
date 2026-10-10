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
| ENG-02 | S§6 | Core | 典型 component（Collider、CharacterController、Health、Resource、AbilitySet、Inventory、PlayerInput/AIController） | `runtime/collision.py` `Collider2DComponent`；`core/scene_transition.py` `PersistentComponent`；`runtime/input_map.py`（PlayerInput 資料） | UT | HI | **C** | 沒有 CharacterController、AIController component（AI 屬 CB11） | CB4、CB5 |
| ENG-03 | S§7 | Core | 系統導向 runtime（Animation/Physics/AI/Ability/Render System） | `runtime/systems.py` `AnimationSystem`、`CameraFollowSystem`；`runtime/collision.py` `CollisionSystem`；`core/system.py` `fixed_update` | UT | HI | **B** | playable runtime 只部分走 Scene systems；缺 AI／Ability System（CB11） | CB4 |
| ENG-04 | S§8 | Core | 應用生命週期、game loop、delta time | `core/application.py` `Application.run`、`core/time.py` | UT | RM（pygame 3 影格） | **A** | — | — |
| ENG-05 | S§8 | Core | Fixed update（需要時） | `core/application.py` `fixed_timestep`、`step_fixed` | UT（確定性步進） | HI | **B** | 缺 RM | CB4 |
| ENG-06 | S§8 | Core | Scene 生命週期、load/unload、序列化 | `core/scene.py`、`core/serialization.py`、`project.py` | UT | GS 存檔→重開 | **A** | — | — |
| ENG-07 | S§8 | Core | Scene 轉場、persistent entities | `core/scene_transition.py` `SceneTransition`、`PersistentComponent`；`Application.change_scene`／`advance_transition` | UT | HI | **B** | 缺 RM | CB4 |
| ENG-08 | S§8 | Core | Transform 位置／旋轉／縮放 | `core/transform.py` | UT | HI | **A** | — | — |
| ENG-09 | S§8 | Core | Transform 父子關係／階層 | `core/transform.py` `parent_id`、`world_transform`、`set_parent`；`editor/editing.py` `ReparentTransformCommand`；Inspector parent 下拉選單 | UT | GS | **B** | 缺 RM | CB4 |
| ENG-10 | S§8 | Core | Event bus／resource lifetime | `core/events.py` `EventBus`、`core/services.py`、`assets/runtime_resources.py`、`presentation/render_resources.py`；戰鬥範圍圖片釋放（`PlayableTestRuntime` `release_resource_scope`） | UT + HI | HI + RM（實機戰鬥 pacing 正常） | **B** | 沒有實機的記憶體回收量測 | CB13 |
| ENG-11 | S§8 | Core | Rendering：sprite、tile、layer、transparency | `runtime/draw.py`、`runtime/tile_draw.py`、`platform/pygame_backend.py` | UT | RM（MV tile + 角色截圖） | **A** | — | — |
| ENG-12 | S§8 | Core | Rendering：batching、render groups | `platform/moderngl_backend.py`（`16a6ebd` 復原，sprite batching）；`preview --backend moderngl` | UT（pygame／GL 像素對照） | RM（Apple M5 GPU 視窗 400 sprites/frame 61.9 fps；D15） | **B** | playable runtime 仍用 pygame；ModernGL 只在 scene preview | CB9 |
| ENG-13 | S§8 | Core | Parallax、screen-space UI | `runtime/camera.py`、`runtime/draw.py`、MV parallax 匯入；`presentation/battle_ui_renderer.py` | UT | 部分 RM | **B** | battle UI 沒有實機接線 | CB2 |
| ENG-14 | S§8 | Core | 輸入：鍵盤／滑鼠 | `runtime/input_map.py` `InputActionMap`；`platform/pygame_input.py` `PygameInputSource`；playable runtime 改走 action map | UT | HI | **B** | 缺 RM | CB4 |
| ENG-15 | S§8 | Core | 輸入：Gamepad、input actions、rebinding、多組控制方案 | `runtime/input_map.py` `InputBinding`（鍵盤／gamepad 按鈕／軸）、rebinding、序列化（Project v10 `input_map`） | UT（rebinding 存讀） | HI | **B** | gamepad 實機驗證是 EXTERNAL；沒有 rebinding UI | CB4 |
| ENG-16 | S§8 | Core | Collision：collider、trigger、layers/masks、broad phase、角色碰撞 | `runtime/collision.py` AABB／圓形、layers/masks、`SpatialHash` broad phase、trigger、`CombinedQuery`（tile + collider） | UT + benchmark（1000 colliders：948 對、3.7 ms） | HI（playable runtime 使用） | **B** | 沒有 CharacterController component；缺 RM | CB5 |
| ENG-17 | S§8 | Core | Hitbox/hurtbox、地面／平台偵測 | — | — | — | **D** | ARPG 相關 → 見 ARPG-* | CB5／Deferred |
| ENG-18 | S§8 | Core | 音訊：BGM、ambient、SFX、mixer、fades、spatial | `runtime/audio_mixer.py` `AudioMixer`（music／ambient／sfx 匯流排、淡入淡出）；`platform/pygame_audio.py`；CC0 音效 6 個 | UT（RecordingAudioDevice） | RM（CoreAudio 裝置播放 PASS；D15） | **B** | 可聽確認與延遲 NOT EXECUTED（M3／M4）；沒有 spatial audio | CB6 |
| ENG-19 | S§33 | Core | 穩定 ID、參照、驗證、可讀格式 | `core/ids.py`、`assets/registry.py`、`assets/serialization.py` | UT | GS | **A** | — | — |
| ENG-20 | S§33 | Core | 版本化 + 遷移 | `core/migration.py` `component_migration` 遷移鏈；`deserialize_component` 逐版遷移；`asteria-upgrade` CLI | UT | HI | **B** | — | CB12 |
| ENG-21 | S§33 | Core | Runtime 存檔（隊伍、背包、任務、開關、NPC、場景） | `rpg/save_state.py`、`runtime/game_save.py`、`events/state.py` | UT + 完整 playable 存讀比對 | HI | **B** | 沒有任務模型；沒有存檔欄位 UI；沒有實機存讀流程 | CB7、CB12 |
| ENG-22 | S§9 | Core | 穩定專案 ID 優先於路徑 | `assets/canonical.py` `AssetRef`、`assets/store.py` | UT | GS | **A** | — | — |
| ENG-23 | S§10 | Core | Prefab／Template／Variant／Override／傳播 | `core/prefab.py`（definition、variant、override、`sync_instance` 傳播）；`editor/prefab_commands.py`；shell Prefab 選單 | UT | GS | **B** | 缺 Editor 實機流程驗證 | CB7 |

## 2. Animation／Camera／VFX（S §11–§12、§44）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| ANI-01 | S§11 | Core | Sprite-sheet 匯入、影格切割、clip、循環 | `graphics/sprites.py`、`runtime/animation.py` `AnimatorState`、`assets/rpg_maker_mv.py` | UT | RM（MV 行走 12 影格） | **A** | — | — |
| ANI-02 | S§11 | Core | State machine、transition 參數 | `runtime/animation_state_machine.py`（參數、trigger、any-state、wait-for-finish、priority）；`reference_data` 載入 | UT | HI（AnimationSystem） | **B** | 沒有 state machine 圖形編輯器（CB10a） | CB8 |
| ANI-03 | S§11、AP§25 | Core | Frame events | `SpriteKeyframe.events`；`AnimatorState.drain_events`；`AnimationSystem.listeners` | UT | HI | **B** | 缺 RM | CB8 |
| ANI-04 | S§11 | Core | 預覽 | `editor/animation_authoring.py`、`animation_editor_widget.py`（預覽用 runtime `AnimatorState`） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| ANI-05 | S§11 | Core | Action timeline（動畫、移動、hitbox、i-frame、cancel、VFX、SFX、camera、事件） | `gameplay/action_timeline.py` `ActionTimeline`、`ActionCueKind` | UT | NE | **C** | 沒有 hitbox/i-frame/cancel cue；沒有接上 runtime | CB8／Deferred |
| CAM-01 | S§12 | Core | Follow、smooth、dead zone、zoom、shake | `runtime/camera.py` `CameraFollow2D`、`presentation/camera_runtime.py` | UT | HI + RM（canonical 戰鬥 camera shake 依 motion beat；D15） | **B** | 缺人眼確認（M5） | CB2 |
| CAM-02 | S§12 | Core | Look-ahead、bounds、target groups、boss／cutscene camera、transitions | `runtime/camera.py`（look-ahead、`clamp_center_to_bounds`、`CameraTargetGroup`、`CameraDirector` 與 easing、shake）、`runtime/systems.py` `CameraFollowSystem`、`runtime/field_camera.py`、Camera2D component v2、WORLD 指令 `CAMERA_FOCUS／RELEASE／SHAKE` | UT + HI | RM（`field_camera_boss_focus`：boss 事件鏡頭 zoom 1.6、畫面不露邊；截圖已檢視） | **B** | look-ahead、target group 只有 UT／HI；playable field 是單畫面地圖，沒有跟隨鏡頭；戰鬥開場的 boss 鏡頭沒有做 | CB10 |
| VFX-01 | S§12 | Core | 粒子、hit flash、damage numbers、screen effects | `runtime/battle_presentation_adapters.py` VFX sprite sheet 播放、hit flash（screen_fx）、damage numbers；`presentation/vfx_runtime.py` | UT | HI + RM（實機視窗 VFX 截圖；D15） | **B** | 沒有粒子發射器資料（VFX 為序列圖）；缺人眼確認 | CB2 |
| VFX-02 | S§12、AD§12 | Core | 2D lights、normal maps、shadows、bloom、color grading、screen shaders | `render/lighting.py`、`render/postprocess.py`（headless 指令模型）；ModernGL 後端已復原 | UT | NE | **C** | lighting／bloom shader 尚未實作（需另提案） | CB9 |
| VFX-03 | S§12 | Core | Trails、afterimages、fog/weather/water | 部分（`render/environment.py`） | UT | NE | **C** | — | CB9 |
| CMP-01 | S§44 | Core | Baked/Layered/Attached/Procedural/Hybrid 並存 | `presentation/canonical.py`、`composition.py`、`actor_visual_layers.py` | UT（Batch 94–106） | NE | **B** | 遊玩中沒有消費者 | CB2 |
| CMP-02 | S§44.1 | Core | 通用 attachment／socket 契約 | `presentation/attachments.py`、`attachment_runtime.py`、`attachment_commands.py` | UT | GS 預覽 | **B** | runtime 沒有繪製；工作樹中的 MV 武器路徑繞過了通用模型（見 RISK-03） | CB0、CB2 |
| CMP-03 | S§44.3 | Core | 通用 animated text／popup | `presentation/animated_text.py`、`text_render_integration.py` | UT | NE | **B** | — | CB2 |
| CMP-04 | S§44.4 | Core | Editor／Python parity（attachment 撰寫） | `editor/attachment_authoring.py`、`attachment_preview.py` | UT + GS | GS | **B** | 行為 parity 不成立（runtime 不消費） | CB2 |

## 3. Gameplay 框架（S §13–§18）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| GP-01 | S§13–14 | Core | Stats（base/derived/modified）、Resources（任意） | `gameplay/stats.py`、`rpg/battle_resources.py` | UT | HI + playable | **A** | — | — |
| GP-02 | S§14 | Core | Ability：cost、cooldown、targeting、cast/recovery、tags、AI metadata | `gameplay/abilities.py`、`rpg/battle_timing.py`、`rpg/targeting.py` | UT | HI；playable 依 ability targeting 定義選目標（CB3） | **B** | 缺 RM | CB3 |
| GP-03 | S§15 | Core | Effects、Triggers、Conditions（AND/OR/NOT）、Modifiers | `gameplay/effects.py`、`triggers.py`、`conditions.py` `ConditionGroup`、`modifiers.py` | UT | HI | **A** | — | — |
| GP-04 | S§16 | Core | 階層 tags、免 Python 公式 | `gameplay/tags.py`、`gameplay/formulas.py` `FormulaBuilder` | UT | HI + Editor 表單 | **A** | — | — |
| GP-05 | S§17 | Core | 行動解析 pipeline | `rpg/battle.py`、`battle_transactions.py`、`reactions.py` | UT（Batch 82–93） | HI；playable 走 `BattleSessionRules`（CB3） | **B** | 缺 RM | CB3 |
| GP-06 | S§18 | Core | State/status（duration、stacks、refresh、periodic、removal） | `gameplay/states.py`、`rpg/battle_states.py` | UT | HI | **A** | — | — |

## 4. RPG／Battle（S §19、§21–§25、§28）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| BTL-01 | S§19 | Eventual | 隊伍／敵群、回合排程、速度順序 | `rpg/battle.py`、`battle_scheduler.py` | UT | HI；playable 回合順序由 scheduler 決定（CB3） | **B** | 缺 RM | CB3 |
| BTL-02 | S§19 | Eventual | 多段攻擊、反擊／追擊／反應、弱點／抗性、break | `rpg/action_sequences.py`、`reactions.py`、`interactions.py`、`gauge_composition.py` | UT | HI | **B** | F-3 已修（CB-BR1：互動倍率進入實際傷害，Preview 一致）；DOT 不套用；缺 RM | CB3、CB-BR1 |
| BTL-03 | S§19 | Eventual | 自訂資源、回合操作、boss 階段、戰鬥事件、戰鬥 AI | `rpg/battle_resources.py`、`enemy_ai.py` `BossPhaseDefinition` | UT | HI；boost／死亡資源由資料設定（CB3） | **B** | 缺 RM | CB3 |
| BTL-04 | S§19、§29 | Core | 戰鬥 UI／演出（HUD、時間軸、結果、選單、動畫、VFX、camera、audio、hit-stop、多段、結果轉場） | `runtime/battle_presentation_adapters.py` Canonical（動畫 sprite、motion sequence：動畫／VFX／audio／camera／flash、KO 同步、捕捉指令、側視 staging）；`runtime/battle_visuals.py` | UT（`test_canonical_battle_presentation.py`） | HI + RM（animation_smoothness、frame_pacing PASS；D15） | **B** | 可聽音訊、實體按鍵、手把未驗證（M1–M3）；hit-stop 未接 | CB2 |
| RPG-01 | S§21 | Core | 背包：可堆疊／唯一、分類、容量、關鍵道具、消耗品、貨幣 | `rpg/items.py` `Inventory` | UT | playable 選單 | **B** | 沒有容量規則的實機驗證 | CB11 |
| RPG-02 | S§21 | Core | 裝備：欄位、需求、modifier、tags、passives、set bonus、熟練度、升級 | `rpg/items.py`、`equipment_growth.py`、`resolved_build.py`；`rpg/equipment_sets.py`（件數門檻的 modifier／tag／能力） | UT | HI（build 解析） | **B** | 套裝編輯器已有（D13）；缺 RM | CB11 |
| RPG-03 | S§21–22 | Core | 成長、職業／副職業、技能樹、多種解鎖貨幣、熟練度 | `rpg/progression*.py`、`actors.py`、`ability_build.py` | UT | GS（技能樹編輯器）+ playable | **A** | — | — |
| RPG-04 | S§23 | Core | 掉落（權重／保底／稀有、數量範圍、條件、難度／幸運） | `rpg/enemies.py`（`chance`、min/max、`required_switch`、`luck_bonus`）；`loot.luck` 事件變數 | UT | HI（勝利結算） | **B** | 沒有權重／保底表；缺 RM | CB11 |
| RPG-05 | S§23 | Core | 經濟（買賣、多貨幣、庫存、定價） | `rpg/economy.py` `ShopDefinition`／`ShopRuntime`（多貨幣、買賣、庫存）；`OPEN_SHOP`；`runtime/game_menus.py` 商店畫面 | UT | HI（按鍵驅動的 playable 畫面） | **B** | 商店編輯器已有（D13）；缺 RM | CB11 |
| RPG-06 | S§23 | Core | 製作（配方、材料、需求、工作台、成功率、品質、經驗、發現、失敗） | `rpg/composition.py`（工作台、成功率、失敗產出、品質等級、經驗）；`GameSessionRuntime.craft` | UT | HI | **B** | 沒有 RM；配方發現已有（D13） | CB11 |
| RPG-07 | S§24 | Core | 世界互動框架（talk…custom、需求、check、結果、獎勵） | `runtime/interaction.py`、`rpg/interactions.py` | UT | 只有 playable 的 talk → 遭遇戰 | **C** | 只執行 `START_ENCOUNTER`（見 EVT-02） | CB1、CB11 |
| RPG-08 | S§25 | Core | 生物／夥伴（捕捉、收集、召喚、成長、收納） | `rpg/battle_lifecycle.py`（召喚）；`rpg/capture.py` `CaptureRule`；`attempt_capture`；bestiary captured 計數 | UT | HI | **B** | 捕捉選單已接進 playable 戰鬥（D13）；缺 RM | CB11 |
| RPG-09 | S§28 | Core | 基本 AI（idle/patrol/chase/attack/flee）、進階（狀態機、權重、門檻、階段） | `rpg/enemy_ai.py`（回合制）；`runtime/field_ai.py` `FieldAISystem`（idle/patrol/wander/chase/flee、回家） | UT | HI（Scene systems） | **B** | field AI 已在 playable runtime 執行（D13）；沒有 behavior tree／utility；缺 RM | CB11 |
| RPG-10 | S§28 | Core | 遭遇（隨機／可見、生成區、wave、重生、稀有、boss、條件） | `rpg/enemies.py` `EncounterDefinition`；`runtime/field_ai.py` `SpawnSystem`（radius、max alive、respawn、waves、稀有、條件）、`VisibleEncounterComponent` | UT | HI（觸碰可見遭遇會開戰） | **B** | spawn 沒有在 playable runtime 執行；缺 RM | CB11 |

## 5. 世界、事件、UI（S §26–§27、§29）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| EVT-01 | S§27 | Core | 可恢復的 Event VM（wait/resume、parallel、autorun、switch、variable、local、branch、call stack） | `events/vm.py`、`runner.py`、`scheduler.py`、`call_stack.py`、`state.py` | UT（Batch 36–44） | HI；遊玩中執行前景 runner + 場景 autorun/parallel（CB1） | **B** | 缺 RM | CB1 |
| EVT-02 | S§27 | Core | 對話／選項、場景轉移、動畫／音訊／畫面效果、背包／隊伍／世界狀態動作 | `events/dialogue.py`；`runtime/world_command_handlers.py` 標準 WORLD handler；Event Editor 可輸入 WORLD 參數 | UT | HI | **B** | 缺 RM | CB1 |
| EVT-03 | S§27 | Core | Common events、battle events、cutscenes、存讀檔恢復 | 部分（VM 狀態可序列化） | UT | HI（存檔 v2 保存進行中的事件） | **C** | 沒有 common event 和 cutscene | CB1 |
| EVT-04 | S§27 | Core | Sequencer（平行軌道：移動、動畫、對話、camera、音樂、VFX、轉場） | `presentation/choreography.py`（演出用） | UT | NE | **C** | 沒有事件層的 sequencer | CB1 |
| WLD-01 | S§26 | Core | 任務／目標／相依／獎勵／串聯 | `rpg/quests.py`（counter／item／defeat_enemy／switch 目標、前置、獎勵、串聯）；存檔 v6；`*_QUEST` WORLD 命令；任務日誌畫面 | UT | HI | **B** | 任務編輯器已有（D13）；缺 RM | CB11 |
| WLD-02 | S§26 | Core | NPC 狀態、聲望、關係、陣營、旗標、成就、圖鑑 | event switches；`rpg/world_record.py`（陣營聲望／階級、關係、計數、成就、圖鑑）；存檔 v7；WORLD 命令 | UT | HI | **B** | 陣營／成就編輯器與成就、圖鑑畫面已有（D13）；沒有 NPC 狀態模型；缺 RM | CB11 |
| UI-01 | S§29 | Core | 標題、HUD、對話、背包／裝備／狀態、技能 | `presentation/rpg_*_screen.py`（LIBRARY）；`playable_test_runtime._draw_title/_draw_build_menu`（寫死） | UT | RM 寫死版本 | **C** | 畫面模型未接線 | CB2 |
| UI-02 | S§29 | Core | 商店、任務、暫停／設定、存讀檔、game over | `runtime/game_menus.py`；playable 的 pause／任務／商店／存讀檔／game over 畫面 | UT | HI（按鍵驅動 + headless 截圖檢視） | **B** | 沒有設定畫面；缺 RM | CB11 |

## 6. Editor（S §5、§30、§32、§34）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| EDT-01 | S§5 | Core | Project/hierarchy、Scene/map workspace、Inspector | `editor/shell.py`、`widgets.py` `ProjectTreeWidget`/`InspectorWidget`、`viewport_widget.py`、`tile_edit.py` | UT + GS | GS Cocoa（9 張截圖已檢視） | **A** | — | — |
| EDT-02 | S§5 | Core | Asset browser + asset 預覽 | `editor/asset_thumbnails.py`（已復原）；Inspector asset 下拉選單 | UT | GS | **B** | 缺 RM | CB14 |
| EDT-03 | S§5、§30 | Core | 結構化資料庫（搜尋、複製一份、參照、驗證） | `editor/integrated_authoring.py`、`authoring_hub_widget.py`、`record_operations.py`（批次編輯、MIXED 值）、9 個 authoring controller | UT + GS | GS + RM（多選與批次欄位） | **B** | 批次套用沒有在 Cocoa 實機執行 | CB10 |
| EDT-04 | S§5 | Core | Event editor | `editor/event_editor_widget.py`、`event_editing.py` | UT + GS | 輸出不會在 runtime 執行 | **B** | 依 EVT-01 | CB1 |
| EDT-05 | S§5 | Core | Animation editor | `editor/animation_authoring.py`、`animation_editor_widget.py`（格線、clip、影格事件、pivot、undo） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| EDT-06 | S§5 | Core | Action timeline editor | `editor/action_timeline_authoring.py`、`action_timeline_widget.py`（通道軌、拖曳 beat、預覽）；runtime 播放同一份 motion_sequences | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）；runtime 戰鬥播放 RM | **A** | — | — |
| EDT-07 | S§5 | Core | AI editor | `editor/enemy_ai_authoring.py`、`enemy_ai_widget.py`（規則、條件、boss phase、綁定敵人、決策預覽用 `EnemyAIRuntime.explain`） | UT + GS + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16） | **A** | — | — |
| EDT-08 | S§5 | Core | VFX tools | `editor/vfx_authoring.py`、`vfx_widget.py`；runtime `battle_visuals.vfx_placement／vfx_rect／vfx_keyframe` | UT + GS + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）；戰鬥 renderer 依 placement 繪製（HI） | **A** | — | — |
| EDT-09 | S§5、§32 | Core | Script editor（語法高亮、自動完成、API 補全、錯誤導覽、traceback、reload） | `editor/code_workspace.py`、`script_tools.py`（語法高亮、Authoring API 補全、traceback 跳行、腳本檔、reload）、`authoring/runner.py` | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（補全清單量測；popup 是獨立視窗，截圖抓不到） | **A** | — | — |
| EDT-10 | S§5、§34 | Core | Debugger／runtime 檢視／debug actions | `runtime/debugger.py`、`runtime/debug_server.py`（只限 loopback、token）、`editor/debugger_widget.py` | UT + HI | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（附加到另外啟動的遊戲 process，give_item 成功） | **A** | — | — |
| EDT-11 | S§5、§34 | Core | Play-test：執行專案／目前場景／從選定點出生／快速重啟／log | `editor/runtime_launcher.py`（debug、spawn、log）、`playmode.py`、`shell.py`（Play from Selection、Restart Play）、`runtime/preview.py --spawn` | UT + HI | RM（Run Project／Stop、debugger 附加） | **B** | Play from Selection 與 Restart 沒有在實機視窗執行 | CB10 |
| EDT-12 | S§5 | Core | Undo/redo | `editor/commands.py`（共用 command stack） | UT + GS | GS | **A** | — | — |
| EDT-13 | S§5 | Core | 複製／貼上／剪下、複製一份／刪除 | 實體 cut／copy／paste／duplicate；紀錄 `record_operations.py` cut／copy／paste（新 id、單一 undo）；快捷鍵依焦點分派 | UT + GS | GS（offscreen，含焦點分派） | **B** | 缺 RM | CB10 |
| EDT-14 | S§5 | Core | 多選、拖放、搜尋／篩選／排序、右鍵選單、快捷鍵、批次編輯 | 多選（實體與紀錄）、紀錄篩選、右鍵選單、Ctrl+C／X／V／Del、批次編輯 | UT + GS | GS + RM（多選） | **C** | 紀錄沒有拖放與排序 | CB10 |
| EDT-15 | S§5 | Core | 驗證 + 錯誤導覽 | `editor/problems.py`（收集全部問題並附位置）、`problems_widget.py`（Problems dock、篩選、跳轉） | UT + GS | RM（Cocoa `editor_tools_gui`，截圖已檢視；D16）（含跳轉） | **A** | — | — |
| EDT-16 | D2 | Core | 通用 Character/Entity Inspector（sprite 選擇、Actor 外觀、Entity↔Actor 連結、縮圖） | `runtime/actor_link.py`、`editor/actor_appearance.py`、`assets/character_visual.py`；shell「Place Character from Sprite Sheet…」「Set Actor Appearance…」 | UT | GS + HI E2E（匯入 sprite sheet → Actor → 放置 → 遊玩） | **B** | 缺 RM | CB14 |
| EDT-17 | S§31 | Eventual | Gameplay System Builder | — | — | — | **D** | SPEC 原文寫「eventually」 | 後續 |
| EDT-18 | S§32 | Eventual | Plugins（components、systems、panels、importers…） | — | — | — | **D** | — | 後續 |
| EDT-19 | S§34 | Eventual | Profiling（frame/AI/collision/entity/particles/draw calls/memory） | `runtime/profiler.py` `RuntimeProfiler`（frame/update/render/ai/collision/animation/asset_loading、pacing、entity/particles/asset 計數、記憶體；draw_calls 與 gpu_time 標 Unsupported）；`asteria-preview --profile` | UT | HI + RM（實機 profile；D15） | **B** | draw calls 在 pygame 標 Unsupported；沒有 Editor 內 profiler 面板 | CB13 |

## 7. Asset Pipeline（AS、AP、AD）

| ID | 來源 | 優先 | 需求 | 程式碼證據 | 測試 | 整合 | 狀態 | 缺口 | Batch |
|---|---|---|---|---|---|---|---|---|---|
| AST-01 | AP§46 #1–6 | Core | Canonical 動畫／角色 schema、sprite 匯入、任意影格尺寸、grid slicing、方向對應 | `assets/canonical.py`、`importers.py`、`codecs.py`、`rpg_maker_mv.py` | UT | RM（MV 48×48 與 96×96） | **A** | — | — |
| AST-02 | AP§46 #7 | Core | Pivot 編輯 | anchor 中繼資料；Animation Editor pivot 欄位（`animation_authoring.set_pivot`） | UT + GS | RM（截圖可見欄位） | **B** | pivot 修改沒有在實機執行 | CB10 |
| AST-03 | AP§46 #9–12 | Core | FPS／時序、驗證、canonical 存讀 | `assets/quality_gate.py`、`usability_gate.py`、`serialization.py`、`store.py` | UT | GS | **A** | — | — |
| AST-04 | AP§46 #10、§48 | Core | 動畫事件會觸發 | 見 ANI-03 | UT | HI | **B** | — | CB8 |
| AST-05 | AP§46 #13、§48 | Core | Runtime 播放整合 | field 行走 RM；battle／側視沒有 | UT | 部分 RM | **C** | — | CB2 |
| AST-06 | AP§48 | Core | 專案 build 可以打包 | `project_tools.export_game`（資源 + CREDITS/LICENSE + `run_game.py`）；`asteria-export` CLI | UT | HI（匯出後在獨立 process 啟動） | **B** | 沒有打包成單一執行檔；缺 RM | CB12 |
| AST-07 | AS§35 Phase A | Core | 類別：Character、NPC、Monster、Tileset、Prop、Portrait、Icon、VFX、Skill、Item、Equipment、Animation、Scene | `assets/*`（character_bundle、monster、tileset、prop、portrait、icon、vfx） | UT | 部分 RM | **B** | — | CB13 |
| AST-08 | AS§35 Phase A | Core | 類別：Projectile、UI asset、Prefab、Audio（播放） | Prefab：`core/prefab.py`；Audio：`runtime/audio_mixer.py`；Projectile、UI asset：`assets/sprite_kinds.py`（golden 涵蓋） | UT | HI | **B** | 缺 RM | CB13 |
| AST-09 | AS§34 | Core | Golden 測試套件（11 類） | `validation/golden.py`（8 項檢查）、`tests/golden/`（11 個 golden asset、baseline、README 的更新規則）、`scripts/update_golden_baselines.py` | UT + HI | 每次 commit 都執行（測試基礎設施） | **A** | — | — |
| AST-10 | AS§33、AD | Core（內容） | 正式 Starter Pack 美術 | — | — | — | **D（Deferred content）** | 依 SCOPE_DECISIONS，改用授權明確的免費素材；屬於 JRPG Demo 階段 | Deferred |
| AST-11 | AP§17、§21 | Core | Atlas packing、auto-fix | `graphics/atlas.py`、`assets/autofix.py`、`assets/asset_package.py` | UT | HI | **B** | 缺 RM | CB13 |
| AST-12 | AP Part A §33–36 | Eventual | Prompt／AI provider／video-to-sprite | — | — | — | **E** | 依 SCOPE_DECISIONS 停止 AI 生成 | — |
| AST-13 | CODEX_HANDOFF | Core | MV 只在 asset 邊界（不進 Runtime/Battle/Scene/Presentation） | `assets/rpg_maker_mv*.py`；違反處：`runtime/rpg_maker_mv_map_render.py`（已 commit）、`graphics/mv_weapon_visual.py` + `presentation/battle_screen.py`／`battle_runtime.py`（工作樹） | UT（邊界由測試強制） | — | **B** | 尚未實機重驗 W-18 | CB0 |

## 8. 壓力測試、範本、取消項目（S §35–§36、CG）

| ID | 來源 | 優先 | 需求 | 狀態 | 備註 |
|---|---|---|---|---|---|
| STR-01 | S§35 | Core | JRPG stress test（四人隊伍、職業、弱點、break、boost、passive、回合操作、NPC 互動、捕捉／夥伴、多階段 boss） | **C** | 引擎層除了捕捉／夥伴都有；但遊玩路徑只行使一部分；`validation/*` 是 headless |
| STR-02 | S§35 | Deferred | ARPG stress test | **D（Deferred）** | 依 SCOPE_DECISIONS 延後 |
| ARPG-01 | S§20 | Deferred | 即時 ARPG（jump、dash、i-frame、combo、cancel、hitbox、knockback、projectile、lock-on、hitstop、即時 AI） | **D（Deferred）** | `presentation/arpg_reference_workload.py` 只是合成演出負載 |
| TPL-01 | S§36 | Core | Starter 範本（Empty／Classic JRPG／Advanced JRPG／ARPG） | **C** | 只有 Empty（New Project + starter tileset）和 Reference World；JRPG 範本屬於 Demo 之後 |
| CG-01 | S「Character Generator」 | Cancelled | Editor 端可選的分層角色產生器 | **E** | `SCOPE_DECISIONS.md`；通用能力的處理見 D2 |

---

## A–E 統計（含分母說明）

**分母規則：**
- E 不計入分母。
- Deferred（依 SCOPE_DECISIONS 延後：STR-02、ARPG-01）和 Deferred content（AST-10）列在「不在本期」欄位，也不計入 active 分母。
- Eventual（EDT-17、EDT-18、EDT-19、BTL-01–03）照 SPEC 原文是「eventually」，**仍然計入** active 分母，因為原始 SPEC 有列出、而且沒有被延後。

| 子系統 | A | B | C | D | E | 不在本期 | Active 分母（A+B+C+D） | A 比例 | A+B 比例 |
|---|---|---|---|---|---|---|---|---|---|
| Engine Core（ENG） | 7 | 14 | 1 | 1 | 0 | 0 | 23 | 30% | 91% |
| Animation／Camera／VFX／Composition | 2 | 9 | 3 | 0 | 0 | 0 | 14 | 14% | 79% |
| Gameplay（GP） | 4 | 2 | 0 | 0 | 0 | 0 | 6 | 67% | 100% |
| RPG／Battle（BTL、RPG） | 1 | 12 | 1 | 0 | 0 | 0 | 14 | 7% | 93% |
| 世界／事件／UI（EVT、WLD、UI） | 0 | 5 | 3 | 0 | 0 | 0 | 8 | 0% | 63% |
| Editor（EDT） | 9 | 7 | 1 | 2 | 0 | 0 | 19 | 47% | 84% |
| Asset Pipeline（AST） | 3 | 7 | 1 | 0 | 1 | 1 | 11 | 27% | 91% |
| 壓力測試／範本／Generator | 0 | 0 | 2 | 0 | 1 | 2 | 2 | 0% | 0% |
| **合計** | **26** | **56** | **12** | **3** | **2** | **3** | **97** | **27%** | **85%** |

**2026-10-10 更新（CB3–CB14 及 CB11 之後）：** 2026-10-09 原始稽核時是 A 17／B 20／C 44／D 16；CB4–CB14 之後是 A17／B38／C33／D9。A 沒有增加，因為 A 需要實機（RM）驗證，而這一輪全部只有 UT／HI／offscreen GS。新的 B 項目都缺 RM，請見各列「缺口」欄。

**2026-10-11 更新（D16：CB13、CB10、CAM-02）：** A17／B50／C24／D6 → **A26／B56／C12／D3**。9 項升為 A（ANI-04、EDT-05、EDT-06、EDT-07、EDT-08、EDT-09、EDT-10、EDT-15、AST-09）：Editor 工具依 EDT-01 同樣的標準——在實機 Cocoa 視窗執行、量測並由工程師檢視截圖（`evidence/real_machine/editor_*.png`）；AST-09 是每次 commit 都執行的測試基礎設施。這些 A 不包含「有人實際上手使用」，那仍是人工項目。

（共 102 列 = 97 active + 2 E + 3 不在本期。統計由腳本從本表計算。）

**解讀：**
- A 比例低的主因不是缺少程式碼，而是 **B（已實作但沒接線或沒驗證）和 C（部分實作）合計 64 項**。其中最大的一群（BTL-04、CMP-*、VFX-01、EVT-01、UI-01）屬於同一個整合缺口：Runtime 沒有消費 Presentation 和 Event VM。
- **測試全綠不等於 closure**（`SCOPE_DECISIONS.md`）：1922 個通過的測試，大多落在 UT 層。
