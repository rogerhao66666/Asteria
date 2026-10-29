# Asteria 架構

**更新：** 2026-10-29。這份說明程式怎麼分層、一個專案從檔案到畫面經過哪些地方。每個系統的功能看
[`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md)，設計決策看 [`audits/DECISION_LOG.md`](audits/DECISION_LOG.md)。
Batch 94～119 時期的架構筆記保留在 [`history/ARCHITECTURE_BATCH94-119.md`](history/ARCHITECTURE_BATCH94-119.md)。

## 1. 三條規則

1. **規則是資料。** 角色、技能、戰鬥規則、選單、版面都存在專案檔裡；引擎裡沒有任何一款範例遊戲的名字或數值。
2. **一份規則，兩個介面。** 遊戲規則只在 `GameSessionRuntime`（不碰像素）；視窗、輸入、繪製在
   `PlayableTestRuntime`。編輯器與自動測試直接呼叫前者，不需要開視窗。
3. **熱迴圈往下沉。** 碰撞、投射物、粒子、天氣、移動、野外 AI 這些每幀大量計算的部分，放在可替換的
   kernel（python／numpy／C++），上層保持作者看得懂的 Python。

## 2. 套件分層

由下往上；下層不 import 上層。

| 層 | 套件 | 負責 |
| --- | --- | --- |
| 核心 | `core` | ECS：`Entity`、`Component`、`Scene`、`System`、`SystemScheduler`、事件匯流排；熱資料的欄位陣列（`core/columns.py`，每個場景一組 `array.array`）；prefab、序列化、版本遷移 |
| 計算 | `kernels` | 三組結果逐位元相同的計算核心（見 [`NATIVE_KERNELS.md`](NATIVE_KERNELS.md)） |
| 玩法積木 | `gameplay` | 數值、資源、公式（`expressions`）、標籤、效果、狀態、技能（Ability）、攻擊、投射物、動作時間軸 |
| RPG 資料 | `rpg` | `RpgDatabase`（`rpg/actors.py`）與所有紀錄：職業、技能樹、裝備、掉落、任務、商店、寵物、選單規則與選單頁、標籤與屬性定義；回合制戰鬥的生命週期（`battle_lifecycle`）；內建字詞（`built_in_text`） |
| 事件 | `events` | 事件程式的 VM、排程、對話、選項、世界指令的綁定 |
| 圖像 | `graphics`、`render`、`platform` | 精靈、圖塊地圖、骨骼、光照、點陣字；繪製指令與管線；pygame、ModernGL、headless 三種後端與輸入、音訊 |
| 戰鬥呈現 | `presentation` | 回合制戰鬥畫面：版面、HUD、指令選單、鏡頭、特效排程、角色與隊伍畫面 |
| 素材 | `assets` | 素材庫、匯入、圖集、品質檢查、RPG Maker MV 匯入 |
| 執行環境 | `runtime` | 場景系統、角色控制、碰撞、即時戰鬥（`action_*`）、存檔，以及下面兩個大類別 |
| 專案 | `project.py`、`project_tools.py` | `Project`（專案檔的讀寫與版本）；升級與匯出 |
| 工具 | `editor`、`multiplayer`、`authoring`、`export_web.py`、`frozen.py`、`validation` | 編輯器、多人連線、作者腳本 API、網頁匯出、免安裝版 app、壓力測試 |

## 3. 一個專案從檔案到畫面

```
project.asteria.json ──Project.load_json──▶ Project ─┬─ scenes（ECS 場景）
                                                    ├─ rpg_database（RpgDatabase）
                                                    ├─ battle_presentation_library、input_map …
                                                    └─ game_start ──instantiate──▶ GameRuntimeSave
                                                                                      │
                          GameSessionRuntime(project, runtime_save) ◀─────────────────┘
                          （規則：移動、事件、戰鬥、背包、翻譯…；不碰像素）
                                         │
                          PlayableTestRuntime（視窗、輸入、繪製、選單、音訊）
                                         │
                                    pygame 視窗／ModernGL
```

- **讀檔**：`Project.load_json(path, registry)` 檢查 `schema` 與版本（目前接受 2～11），舊格式在
  `core/migration.py` 與各紀錄的讀取函式裡升級；`asteria-upgrade` 把檔案寫回最新格式。
- **新遊戲**：`project.game_start.instantiate(project)` 產生 `GameRuntimeSave`（`runtime/game_save.py`）：
  場景、玩家位置、隊伍、背包、裝備、技能樹分配、任務、世界狀態。存檔就是這個物件的 JSON。
- **規則**：`GameSessionRuntime`（`runtime/game_session.py`）由 `runtime/session/` 的 mixin 組成，一個模組
  管一塊規則：`field_play`、`action_play`、`gear`、`scene_events`、`battle_events`、`messages`
  （翻譯 `tr()`、資料名稱）、`party`、`inventory_use`、`builds`、`encounters`、`ability_use`、`pets`、
  `strikes`、`turns`、`economy`、`interactions`、`map_tiles`、`rewards`。
- **畫面**：`PlayableTestRuntime`（`runtime/playable_test_runtime.py`）由 `runtime/playtest/` 的 mixin 組成：
  `resources`、`environment`、`text_draw`、`field_view`、`multiplayer`、`field_ui`、`action_scenes`、
  `title_build`、`workshop`、`battle_flow`、`menus_input`、`save_slots`、`menus_draw`、`menu_fit`、
  `menu_pages`、`capture`。它只處理輸入、像素、選單導覽與特效播放；規則一律呼叫 session。
- **進入點**：`asteria-preview`（`runtime/preview.py`）讀專案、建立或讀取存檔；專案資料夾有
  `playable_test_manifest.json` 時交給 `run_playable_test_runtime`，否則跑一般的場景預覽。

## 4. 場景與每一幀

- `Scene` 持有實體（依加入順序）、每種元件的索引（`scene.query` 不掃描全部實體）、欄位陣列的 slot，以及
  `SystemScheduler`。`Scene.update(dt)` 依 `order` 執行系統；更新途中加入或移除的實體延到這一幀結束才生效。
- 野外的系統（`runtime/systems.py`、`character_control`、`collision`、`field_ai`、`projectiles`…）從場景索引
  讀元件，每幀共用同一個碰撞世界，數量多的部分交給 kernel。
- 即時戰鬥：場景裡有 `CombatSceneComponent` 時，敵人在野外即時戰鬥，不切到回合制畫面（`runtime/action_play.py`、
  `action_combat.py`）。
- 回合制戰鬥：遭遇開始後，`rpg/battle_lifecycle.py` 管回合與結果，`presentation/` 把狀態轉成繪製指令，
  `platform/pygame_battle_ui.py` 畫出來。

## 5. 編輯器

- `AsteriaEditorWindow`（`editor/shell.py`）持有一份 `EditorDocument`（`editor/model.py`）：目前的 `Project`、
  是否有未存的修改，以及 `CommandStack`（`editor/commands.py`）。**每個修改都是一個可復原的指令**；表單停止
  輸入約 0.35 秒後自動套用。
- 七個工作區（Scene、Database、Battle、Presentation、Events、Code、Multiplayer）各自由 `*_widget.py`
  （畫面）和 `*_authoring.py`（讀寫專案資料的 controller）組成；畫面不直接改資料。
- 介面文字一律是英文原文，經 `editor/i18n.py` 依 `translations/zh_TW.json` 即時換成繁中。
- **試玩**：`editor/runtime_launcher.py` 用 `sys.executable -m asteria.runtime.preview` 開一個子程序，加上
  `--debug-port`；Debugger 與 Profiler 面板透過 `runtime/debug_server.py` 的本機通道讀遊戲狀態。在免安裝版
  app 裡，`sys.executable` 就是 app 本身（`frozen.py`）。

## 6. 匯出與發布

| 成品 | 程式 | 內容 |
| --- | --- | --- |
| 遊戲資料夾 | `project_tools.package_game`（`asteria-export`） | 專案、它用到的每個檔案、引擎原始碼（`engine/asteria`）、`run_game.py`；需要 Python 與 pygame-ce |
| 單檔 `.pyz`、macOS `.app` | 同上，`--pyz`、`--app` | 從原始碼版匯出的 `.app` 需要 Python；從免安裝版 app 匯出的內附播放器，不需要 Python |
| 網頁版 | `export_web.py`（`asteria-export-web`） | pygbag 把 CPython 與 pygame-ce 編成 WebAssembly |
| 免安裝版編輯器 | `scripts/build_app.py` | PyInstaller 凍結直譯器與函式庫；引擎以原始碼放在 app 裡（見 [`STANDALONE_APP.zh-TW.md`](STANDALONE_APP.zh-TW.md)） |

匯出前會檢查 C++ kernel，必要時重新編譯並帶進成品；沒有 kernel 的平台退回 numpy 或純 Python。

## 7. 多人連線

`multiplayer/` 是和遊戲無關的積木：TCP session 與 lobby、client API、命令／狀態／事件、即時輸入同步、
SQLite 玩家資料。遊戲透過 adapter 接上（`multiplayer/project_demo.py` 用專案本身的 ECS 戰鬥與背包）。
伺服器以 `python -m asteria.multiplayer.server` 啟動；只適合本機或可信任的區域網路，設計與限制見
[`audits/MULTIPLAYER_DESIGN.md`](audits/MULTIPLAYER_DESIGN.md)。

## 8. 測試

- `tests/` 全部在無頭環境跑（SDL dummy、Qt offscreen），約 3,600 項、5 分鐘；CI 在 Linux 與 macOS 跑。
- 範例專案本身就是測試資料：`test_full_verification_campaign.py` 打完整段劇情，`test_party_rpg_demo.py`、
  `test_arpg_demo.py` 逐一檢查機制。
- 畫面與視窗的行為另外用 `scripts/*_live_check.py` 在真實 Cocoa 視窗驗證，截圖放 `docs/audits/evidence/`。
