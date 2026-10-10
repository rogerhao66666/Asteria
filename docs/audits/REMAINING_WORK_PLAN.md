# REMAINING_WORK_PLAN

**狀態：** 提案。每個 Batch 都要在 Stage E **經你明確批准**後才能開始。
**排序原則（CODEX_PROMPT）：** 維持 SPEC 優先級；同一優先級內依序是 資料完整性／正確性 → 斷掉的整合 → 缺少的核心行為 → 必要的 Editor 功能 → runtime／presentation 缺陷 → 驗證 → 打包。
**本期不做：** C++、ARPG Engine、Dual-Mode Demo、JRPG Demo、恢復 Character Generator、AI 美術、替換 renderer、放寬既有驗證標準。

**規模：** S ≤ 1 天、M 2–4 天、L ≥ 1 週。需求 ID 對應 SPEC_TRACEABILITY_MATRIX。

---

## 相依關係

```
CB0 ──► CB13a(CI) ──► 其他所有 Batch 都在 CI 上驗證
CB0 ──► CB3 ──► CB1 ──► CB2 ──► (G-BATTLE gate) ──► Legacy 退役提案
CB0 ──► CB14 ──► CB15
CB4 ──► CB5、CB8 ；CB6、CB7、CB9、CB12 可以並行
CB10、CB11 在 CB1–CB3 之後
```

---

## CB0 — 基準整理與邊界修正（S）

| 項目 | 內容 |
|---|---|
| 需求 | AST-13、C-1–C-5（SPEC_GAP_AUDIT §1） |
| 範圍 | (1) 把工作樹裡的通用引擎工作分批 commit：角色產生器的通用合成修正、click-to-place、MV 側視 motion 索引修正（`assets/rpg_maker_mv.py:180`）、walking sheet 重建；(2) 套用 P0-3 提案 patch（MV 武器 → `assets/rpg_maker_mv_weapon.py` + 通用 `CombatantOverlay`），並把 `runtime/rpg_maker_mv_map_render.py` 搬到 `assets/`；(3) MV 衍生美術加進 `.gitignore`（需要批准）；(4) 同步 README／`ASTERIA_PROGRESS.md`／pyproject 版本，並記錄 `bf4a993` 刪除了哪些東西 |
| 不做 | `ready_user_hero` 的刪除（D3，等 CB15）；任何美術 |
| 測試 | 全套測試（B 類美術失敗維持原樣列出）；新增邊界測試：`grep -rE "rpg_maker\|mv_weapon" src/asteria/{presentation,runtime,graphics,rpg,gameplay,core}` 必須為空 |
| 驗收 | 邊界測試 PASS；A 類測試全部 PASS；ledger 和 README 一致 |
| 風險 | patch 是 2026-10-09 工作樹的快照；套用前要確認工作樹沒有再變動 |

## CB1 — Event VM 進入 Runtime（M）

| 項目 | 內容 |
|---|---|
| 需求 | EVT-01–04、EDT-04、RPG-07、W-04、W-11 |
| 前置 | CB3（遭遇／戰鬥開始要走資料定義） |
| 範圍 | `GameSessionRuntime` 改用 `events/runner.py`／`scheduler.py`（autorun、parallel、trigger、wait/resume）；建立標準 `WorldCommandRouter` handler：TRANSFER、SHOW_TEXT／CHOICE、GIVE/TAKE_ITEM、CHANGE_CURRENCY、START_ENCOUNTER、PLAY_BGM/SE（cue）、SCREEN_FADE、WAIT_FOR_INPUT；`playable_test_runtime` 只負責顯示對話和選項（legacy adapter） |
| 測試 | 每個 handler 都有 UT；E2E：用 Editor API 撰寫「對話 → 選項 → 設開關 → 條件分支 → 開始遭遇戰」，headless 執行，斷言 save 狀態；事件執行到一半存檔 → 讀檔 → 繼續 |
| 驗收 | W-04 變成 HI PASS + RM PASS |
| 風險 | 現有的 `START_ENCOUNTER` 特例要改成 handler，並保留向後相容 |

## CB2 — Battle Presentation 漸進整合（L，依 D6）

| 項目 | 內容 |
|---|---|
| 需求 | BTL-04、CMP-01–04、VFX-01、CAM-01、UI-01、AST-05、W-05、W-12–W-14 |
| 前置 | CB3 |
| 步驟 | **2a** 定義 `BattlePresentationAdapter` 介面，輸入只有 canonical Battle Events、`BattleSnapshot`、Action Results。**2b** 把 `_draw_battle` 包成 `LegacyPygameBattleAdapter`，不改變行為。**2c** 新增 `CanonicalBattleAdapter` = `BattleScreenRuntime` + `PygameBattleUiBackend`，消費 Editor 的 presentation profile；用設定選擇 adapter，預設維持 legacy。**2d** 行為對照測試：同一個戰鬥腳本 → 兩個 adapter → 比對事件消費順序、目標、數值、結果，視覺不比對。**2e** 分別驗證 animation、VFX、camera、audio cue、hit-stop、多段攻擊、結果轉場。**2f** 實機截圖 + Cocoa smoke |
| 不做 | 刪除 legacy；新增任何 battle 規則 |
| 驗收 | CLOSURE_EXIT_CRITERIA 的 G-BATTLE；通過後**另外**提出 legacy 退役提案 |
| 風險 | `PygameBattleUiBackend` 目前 0 測試，要先補契約測試 |

## CB3 — 把寫死的規則搬回 canonical 資料（M）

| 項目 | 內容 |
|---|---|
| 需求 | GP-02、GP-05、BTL-01–03、RISK-02 |
| 範圍 | 目標判斷改用 ability targeting 定義；boost、量表 ID、死亡資源由專案的 battle rules 資料設定（`editor/rpg_battle_rules_*` 已經有撰寫介面）；回合順序改由 `rpg/battle_scheduler.py` 決定 |
| 測試 | `grep -E '"heal"\|"momentum"\|"vitality"\|"stagger_system"' src/asteria/runtime` 必須為空；對照測試：Reference RPG 在改動前後的戰鬥結果（同一個 seed）一致，或差異都有記錄 |
| 驗收 | BTL-01–03 → A（加上實機驗證） |

## CB4 — Engine Core 平台：Loop／Input／Transform／Scene／Systems（M–L）

| 需求 | ENG-02、03、05、07、09、14、15 |
|---|---|
| 範圍 | fixed-step；具體的 System（Animation／Player／Camera）；Transform 父子關係 + Editor 階層；場景轉場和 persistent entity；input action map 資料、鍵盤＋gamepad、rebinding、序列化 |
| 驗收 | 確定性步進測試；rebinding 存讀；gamepad 實機（EXTERNAL） |

## CB5 — Collision（L）
| 需求 | ENG-16、17（hitbox/hurtbox 只做資料結構；gameplay 屬於延後的 ARPG） |
|---|---|
| 範圍 | Collider component（AABB／圓形）、layers/masks、spatial-hash broad phase、trigger、角色控制器 |
| 驗收 | UT + 1000 個 entity 的 benchmark（記錄數據） |

## CB6 — Audio 播放後端（M）
| 需求 | ENG-18、AST-08（Audio）、W-15 |
|---|---|
| 範圍 | 用 `pygame.mixer` 實作 `AudioBackend`；BGM／ambient／SFX 匯流排；淡入淡出 |
| 驗收 | UT（mock）+ 實機播放紀錄（延遲屬於 EXTERNAL） |

## CB7 — Prefab／Variant（L）
| 需求 | ENG-23、AST-08（Prefab） |
|---|---|
| 驗收 | Editor：建立 prefab → 放置 → 修改 base → 實例更新 → 存讀 |

## CB8 — Animation State Machine + Frame Events（M）
| 需求 | ANI-02、03、05（非 ARPG 的 cue）、AST-04 |
|---|---|
| 驗收 | 參數驅動 idle/walk/attack 切換；frame event 會觸發 runtime 事件 |

## CB9 — GPU Renderer 復原：ModernGL（M，依 D1）

| 項目 | 內容 |
|---|---|
| 需求 | ENG-12、VFX-02（基礎）、W-16 |
| 範圍 | 從 `16a6ebd` 取回 `platform/moderngl_backend.py`、`moderngl_shaders.py`、`tests/test_moderngl_backend.py`；恢復 pyproject 的 `moderngl` extra 和 `preview._BACKEND_FACTORIES["moderngl"]`；對現行 `TextureDraw`（`layer`、`depth`、`opacity`、`flip_x`）補齊行為 |
| 限制 | pygame 維持預設；**不替換** renderer；lighting／bloom 等 §12 shader 需求另外提案 |
| 驗收 | 兩個後端在同一組 `TextureDraw` 契約測試下輸出一致（像素容差）；實機截圖（EXTERNAL GPU） |

## CB-BR1 — Battle Rules Correction（S，D12 批准）
| 需求 | BTL-02（F-3） |
|---|---|
| 範圍 | 互動規則（弱點／抗性倍率、NULLIFY／ABSORB／REFLECT）接入既有 `BattleRuntime.execute` → `AbilityRuntime` → `apply_effect` 傷害路徑；`BattleRuntime.preview_action` 用同一路徑預測 |
| 限制 | 不建立第二套傷害計算；倍率只來自專案的 InteractionRule 資料；不改 SPEC 未要求的其他規則 |
| 驗收 | 普通攻擊、技能、反擊（reaction）、敵人 AI 路徑；Preview 與 Runtime 一致；UT + 整合 + 回歸測試 |

## CB10 — Editor 工具（L，可拆）

**D12 追加（優先）：** 10h 視覺化資料編輯器：Shop、Quest、Faction、Achievement、Equipment Set、Capture Rules（GUI 與 Python API 共用 canonical data model；不能只給 JSON 編輯器）
| 需求 | ANI-04、CAM-02、EDT-03、05–11、13–15、AST-02 |
|---|---|
| 子項 | 10a 動畫編輯器（切割、時序、pivot、事件、state machine 圖）；10b action timeline 編輯器；10c debugger（檢視／修改 stats、states、開關、傳送、生成）；10d 右鍵選單、批次編輯、紀錄 copy/cut/paste、全域問題面板；10e script editor 語法高亮、自動完成；10f play-test 從選定點出生、快速重啟、log；10g VFX 面板掛進 shell |

## CB11 — 遊戲系統（L，依 JRPG 需要挑選）

**D12 追加 — Runtime Integration（11-RI）：** Field Enemy AI、Spawn Zones 在 playable runtime 實際執行；戰鬥 Capture 選單；配方發現（Recipe Discovery）；Game Settings 畫面；Achievement 畫面；Bestiary／Encyclopedia 畫面。必須經過實際 runtime 整合，不能只靠單元測試。
| 需求 | RPG-01、02、04–10、WLD-01、02、UI-02 |
|---|---|
| 子項 | 商店／經濟、任務、製作的成功率／品質／工作台、條件掉落、set bonus、field AI（idle/patrol/chase/flee）、spawn zone／wave／respawn、捕捉／收納、pause／存讀檔／game over 畫面 |

## CB12 — 遷移與打包（M）
| 需求 | ENG-20、21、AST-06、W-10、RISK-05、RISK-10 |
|---|---|
| 範圍 | schema 遷移鏈；存檔欄位；匯出可執行遊戲 + 獨立啟動；import-boundary 測試（runtime 不 import editor／PySide6） |

## CB13 — 驗證基礎設施（S–M）
| 需求 | AST-07、09、11、ENG-10、EDT-19、RISK-04、09 |
|---|---|
| 子項 | **13a** CI（Linux offscreen 全套 + compileall + ruff 正確性規則）；13b MV／平台相依測試加 skip；13c AS§34 golden suite（使用授權明確的免費素材或程式產生的 fixture）；13d runtime profiler／實機 benchmark 基準（PERF-01、PERF-02）；13e 修 F601、PLE0605 |

## CB14 — 通用 Character／Entity Inspector 復原與整合（M，依 D2）

| 項目 | 內容 |
|---|---|
| 需求 | EDT-02、EDT-16 |
| 範圍 | 從 `16a6ebd` 復原並調整：`runtime/actor_link.py` `ActorLinkComponent`（Entity↔Actor）、`editor/actor_appearance.py`（Actor → 任意 sprite sheet）、`editor/asset_thumbnails.py`（Asset 預覽）；評估 `unit_authoring.py`、`class_design_panel.py` 是否和目前的 authoring hub 重疊；從 `create_character_command.py` 抽出不依賴 `GeneratedCharacterBundle` 的「canonical 視覺 → Entity + Actor」命令；把 sprite 選擇、動畫設定、attachment points、scale／position／layer、動畫預覽集中到 Inspector |
| 驗收 | 不靠 Generator 也能完成「匯入免費素材 sprite sheet → 指派給 Actor → 放上地圖 → 遊玩」的 E2E |

## CB15 — 已取消範圍的退役（S–M，需要逐項批准，依 D2／D3／D4）

**D12：尚未批准。** 先提交 `docs/audits/CB15_RETIREMENT_REVIEW.md` 逐項審核，等明確批准後才能執行任何刪除。

| 項目 | 內容 |
|---|---|
| 前置 | **CB14 完成**（確認沒有通用能力只存在於 Generator） |
| 範圍 | 封存或移除 Generator 專屬程式、UI 和腳本（清單見 DECISION_LOG D2）；`ready_user_hero`、`asteria_hero`、`template_*`、`asteria_boss`、MV 衍生原型等 AI／衍生美術；B 類測試改成 `retired_art` marker 或移到 `tests/retired/`，並保留 D4 的失敗紀錄 |
| 限制 | 不刪除共用的 asset／animation／presentation 功能；A 類驗證門檻不變 |
| 驗收 | 全套測試（排除 retired 之後）全綠；`git ls-files` 中沒有 AI 或 MV 衍生美術 |

---

## 延後項目（本期不做，SPEC 依據保留）

| 項目 | 依據 | 重新啟動的條件 |
|---|---|---|
| ARPG Engine（ARPG-01、STR-02） | SCOPE_DECISIONS | 原始 SPEC closure 之後 |
| JRPG Demo + 免費素材 Starter（AST-10、TPL-01） | SCOPE_DECISIONS | closure 之後；素材要有 license 紀錄 |
| Gameplay System Builder、Plugins（EDT-17、18） | SPEC 原文「eventually」 | 由你決定是否納入 closure 分母 |
| C++ native、renderer 替換、3D | SCOPE_DECISIONS | 需要先有 Measured 瓶頸（見 ARCHITECTURE_PERFORMANCE_RISKS §3） |

## D17 — Reconciliation 後的剩餘工作（2026-10-11）

每個非 A 的 active 需求分成 **Functional**（功能缺口，要寫程式）、**Validation**（功能已在，缺驗證證據）、**Proposal**（先提技術方案，等待 Review）、**Eventually**（SPEC 原文為 eventually，不是 release blocker）。M1–M6 見 `REAL_MACHINE_VALIDATION.md`。

**Scope Classification（D17 #5、#6）：** ENG-17 依 SPEC §8（Engine Core：Character collision、Hitbox/hurtbox、Ground/platform detection，未標 eventually）列為當前範圍；ANI-05 依 SPEC §11（Action timelines may contain hitbox、i-frame、cancel、combo window）列為當前範圍的通用 cue 資料與派送，ARPG 戰鬥本身（§20『Eventually』）維持 Deferred；EDT-17（§31『should eventually』）、EDT-18（§32 未要求當前版本）列為 Eventually，保留既有擴充介面（component registry、WORLD command router、AI condition／target resolver、asset codec）。另依 Phase 1 結果，RPG-07、UI-01、BTL-04（hit-stop）是 SPEC Core 的功能缺口，併入 D17-2。

| ID | 狀態 | 缺口類型 | 目前缺口 | 下一步 |
|---|---|---|---|---|
| ENG-02 | C | Functional | 沒有 CharacterController、AIController component（AI 屬 CB11） | D17-2：CharacterController／AIController component |
| ENG-03 | B | Validation | playable 的 field AI 與 spawn 走 Scene systems（D13）；Ability 由 battle runtime 處理，不是 Scene system；缺 RM | 實機 field 流程（M6） |
| ENG-05 | B | Validation | 缺 RM | 實機 fixed-step 量測 |
| ENG-07 | B | Validation | 缺 RM | 實機場景轉場（M6） |
| ENG-09 | B | Validation | 缺 RM | 實機階層移動 |
| ENG-10 | B | Validation | 沒有實機的記憶體回收量測 | 實機記憶體量測 |
| ENG-12 | B | Proposal | playable runtime 仍用 pygame；ModernGL 只在 scene preview | D17-P 技術提案（等待 Review） |
| ENG-13 | B | Validation | canonical 戰鬥 UI 已在實機接線（D15）；parallax 缺 RM | parallax 實機 |
| ENG-14 | B | Validation | 缺 RM | M1 實體鍵盤／滑鼠 |
| ENG-15 | B | Functional | gamepad 實機驗證是 EXTERNAL；沒有 rebinding UI | D17-3：按鍵重設 UI；M2 手把 |
| ENG-16 | B | Functional | 沒有 CharacterController component；缺 RM | D17-2：CharacterController（與 ENG-02） |
| ENG-17 | D | Functional | ARPG 相關 → 見 ARPG-* | D17-2：通用 hitbox／hurtbox、地面／平台偵測（SPEC §8 為 Core） |
| ENG-18 | B | Validation | 可聽確認與延遲 NOT EXECUTED（M3／M4）；沒有 spatial audio | M3／M4；spatial 依 SPEC『where useful』，不列 blocker |
| ENG-20 | B | Validation | — | 遷移 CLI 實機流程 |
| ENG-21 | B | Functional | 任務已在存檔（runtime state v7）；沒有存檔欄位 UI；實機 recovery 只驗證玩家位置 | D17-3：存檔欄位 UI |
| ENG-23 | B | Validation | 缺 Editor 實機流程驗證 | Editor prefab 實機流程 |
| ANI-02 | B | Functional | 沒有 state machine 圖形編輯器（CB10a） | D17-3：圖形化狀態機編輯器 |
| ANI-03 | B | Validation | 缺 RM | 實機 frame event |
| ANI-05 | C | Functional | 沒有 hitbox/i-frame/cancel cue；沒有接上 runtime | D17-2：通用 hitbox／i-frame／cancel／combo cue（SPEC §11 為 Core）；ARPG 戰鬥本身仍 Deferred |
| CAM-01 | B | Validation | 缺人眼確認（M5） | M5 |
| CAM-02 | B | Functional | look-ahead、target group 只有 UT／HI；playable field 是單畫面地圖，沒有跟隨鏡頭；戰鬥開場的 boss 鏡頭沒有做 | D17-3：跟隨鏡頭、戰鬥 boss 開場鏡頭 |
| VFX-01 | B | Validation | 沒有粒子發射器資料（VFX 為序列圖）；缺人眼確認 | M5；粒子發射器併入 D17-P 提案 |
| VFX-02 | C | Proposal | lighting／bloom shader 尚未實作（需另提案） | D17-P 技術提案 |
| VFX-03 | C | Proposal | — | D17-P 技術提案 |
| CMP-01 | B | Functional | 遊玩中沒有消費者 | D17-3：分層角色 runtime |
| CMP-02 | B | Functional | runtime 沒有繪製；工作樹中的 MV 武器路徑繞過了通用模型（見 RISK-03） | D17-3：attachment runtime 繪製 |
| CMP-03 | B | Validation | — | 戰鬥 damage number 實機 |
| CMP-04 | B | Functional | 行為 parity 不成立（runtime 不消費） | D17-3：editor／python parity 隨 CMP-01/02 |
| GP-02 | B | Validation | 缺 RM | 實機戰鬥 |
| GP-05 | B | Validation | 缺 RM | 實機戰鬥 |
| BTL-01 | B | Validation | 缺 RM | 實機戰鬥（M6） |
| BTL-02 | B | Validation | F-3 已修（CB-BR1：互動倍率進入實際傷害，Preview 一致）；DOT 不套用；缺 RM | 實機戰鬥（M6） |
| BTL-03 | B | Validation | 缺 RM | 實機戰鬥（M6） |
| BTL-04 | B | Functional | 可聽音訊、實體按鍵、手把未驗證（M1–M3）；hit-stop 未接 | D17-2：hit-stop 接進 canonical；M1–M3 |
| RPG-01 | B | Validation | 沒有容量規則的實機驗證 | 實機背包流程 |
| RPG-02 | B | Validation | 套裝編輯器已有（D13）；缺 RM | 實機裝備流程 |
| RPG-04 | B | Functional | 沒有權重／保底表；缺 RM | D17-3：權重／保底掉落表 |
| RPG-05 | B | Validation | 商店編輯器已有（D13）；缺 RM | 實機商店 |
| RPG-06 | B | Validation | 沒有 RM；配方發現已有（D13） | 實機製作 |
| RPG-07 | C | Functional | talk／inspect／open／buy／craft／challenge／capture 由事件 + WORLD 指令組成；沒有 SPEC §24 的通用互動定義（actor capability、target type、cost、check 成敗、consequence、follow-up） | D17-2：SPEC §24 通用互動定義 |
| RPG-08 | B | Validation | 捕捉選單已接進 playable 戰鬥（D13）；缺 RM | 實機捕捉 |
| RPG-09 | B | Functional | field AI 已在 playable runtime 執行（D13）；沒有 behavior tree／utility；缺 RM | D17-3：behavior tree runtime |
| RPG-10 | B | Validation | spawn 已在 playable runtime 執行（`GameSessionRuntime.field_update` 的 `SpawnSystem`，D13）；缺 RM | 實機 spawn |
| EVT-01 | B | Validation | 缺 RM | 實機事件流程 |
| EVT-02 | B | Validation | 缺 RM | 實機事件流程 |
| EVT-03 | C | Functional | 沒有 common event 和 cutscene | D17-2：common／battle events、cutscene |
| EVT-04 | C | Functional | 沒有事件層的 sequencer | D17-2：平行 sequencer |
| WLD-01 | B | Validation | 任務編輯器已有（D13）；缺 RM | 實機任務 |
| WLD-02 | B | Functional | 陣營／成就編輯器與成就、圖鑑畫面已有（D13）；沒有 NPC 狀態模型；缺 RM | D17-3：NPC 狀態模型 |
| UI-01 | C | Functional | 背包／裝備／狀態／技能畫面沒有接進 runtime；`presentation/rpg_*_screen` 模型仍未被消費 | D17-2：背包／裝備／狀態／技能畫面接進 runtime |
| UI-02 | B | Validation | 設定畫面已有（`game_menus.GameSettings`，D13）；缺 RM | 實機選單流程 |
| EDT-02 | B | Validation | 缺 RM | 實機 asset browser |
| EDT-03 | B | Validation | 批次套用沒有在 Cocoa 實機執行 | 實機批次套用 |
| EDT-04 | B | Validation | Event VM 會執行編輯器產出的程式；缺「編輯器撰寫 → 實機遊玩」的流程驗證 | 編輯器 → 實機遊玩 |
| EDT-11 | B | Validation | Play from Selection 與 Restart 沒有在實機視窗執行 | 實機 Play from Selection／Restart |
| EDT-13 | B | Validation | 缺 RM | 實機剪貼簿 |
| EDT-14 | C | Functional | 紀錄沒有拖放與排序 | D17-2：拖放、排序 |
| EDT-16 | B | Validation | 缺 RM | 實機 inspector |
| EDT-17 | D | Eventually | SPEC 原文寫「eventually」 | SPEC §31『should eventually』；不列 blocker |
| EDT-18 | D | Eventually | — | SPEC §32 plugins 未要求當前版本；保留既有擴充介面 |
| EDT-19 | B | Functional | draw calls 在 pygame 標 Unsupported；沒有 Editor 內 profiler 面板 | D17-3：Editor profiler 面板 |
| AST-02 | B | Validation | pivot 修改沒有在實機執行 | 實機 pivot 修改 |
| AST-04 | B | Validation | — | 見 ANI-03 |
| AST-06 | B | Functional | 沒有打包成單一執行檔；缺 RM | D17-3：獨立執行檔打包 |
| AST-07 | B | Validation | — | 實機類別播放 |
| AST-08 | B | Validation | 缺 RM | 實機 |
| AST-11 | B | Validation | 缺 RM | 實機 |
| AST-13 | B | Validation | 尚未實機重驗 W-18 | D17-3：MV 邊界規則重驗 |
