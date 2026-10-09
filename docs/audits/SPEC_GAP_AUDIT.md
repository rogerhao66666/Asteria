# SPEC_GAP_AUDIT

**階段：** Stage A（Discovery）+ Stage B（Audit）→ Stage C（Report）。**沒有修改任何產品行為**（工作樹事件與撤回見 DECISION_LOG §0）。
**基準：** `main` @ `d69817c`；未提交工作樹包含 38 個修改檔和 36 個未追蹤路徑（與 Audit 開始時相同，只少了 3 個無法還原的測試函式）。
**環境：** macOS（Darwin 27）、Python 3.13.15（`.venv`）、pygame-ce 2.5.8、PySide6、moderngl 5.12.0（有安裝但沒有被引用）。

---

## 1. Source inventory 與權威性

| 類別 | 檔案 | 權威性 |
|---|---|---|
| Canonical SPEC | `ASTERIA_SPEC.md`（§1–§44 + Character Generator）、`ASTERIA_ASSET_SPEC.md`、`ASTERIA_ASSET_PIPELINE.md`、`ASTERIA_ART_DIRECTION.md` | 功能需求最高依據（`audit/FIVE_DOC_CONSISTENCY_AUDIT.md`） |
| Canonical ledger | `ASTERIA_PROGRESS.md` | 只記錄狀態，不覆蓋 SPEC |
| Scope decisions | `SCOPE_DECISIONS.md`（`~/Downloads/Asteria_Codex_SPEC_Audit_Handoff.zip`，**不在 repo**） | 只覆蓋它列出的取消／延後項目 |
| 流程／模板 | `CODEX_PROMPT.md`、`REPORT_INDEX.md`（同一個 zip） | 定義流程和報告格式 |
| Handoff | `CODEX_HANDOFF.md`、`PROJECT_HANDOFF.md`、`ASTERIA_FINAL_ALIGNMENT_AUDIT.md`、`START_HERE_MAC.md` | 操作指引；`CODEX_HANDOFF.md` 第 4 點規定 MV 邊界 |
| 歷史／證據 | `docs/BATCH*.md`（17–158）、`docs/PHASE_*`、`audit/*.md`、`review/*` | 只作為來歷，不重開凍結邊界 |
| 舊版 SPEC | `docs/CANONICAL_SPEC.md`（2026-09-13）、`docs/ARCHITECTURE.md`、`docs/NEXT_PHASE_PLAN.md` | 已被 5 份 `ASTERIA_*.md` 取代 |
| 設計／計畫（未追蹤） | `docs/superpowers/specs|plans/2026-10-0*` | 工作紀錄；其中 starter art／boss sprites 依 SCOPE_DECISIONS 已停止 |
| Build／CI | `pyproject.toml`（`0.158.0a158`；extras：pygame、editor、mv、dev） | **沒有 CI 設定**；沒有 packaging／launcher 設定 |

### 權威衝突

| # | 衝突 | 影響 | 處理 |
|---|---|---|---|
| C-1 | `README.md` 寫 v0.158／Batch 98／554 passed，並連到 `docs/CANONICAL_SPEC.md` | 新人會讀到過時的權威 | CB0 文件同步 |
| C-2 | `ASTERIA_PROGRESS.md` 第 84 行把 ModernGL 後端和外觀面板列為已 commit，但 `bf4a993` 已刪除 | ledger 不正確 | D1／D2；CB0 |
| C-3 | `ASTERIA_PROGRESS.md` 最後一筆停在 2026-09-26；後面 14 個 commit（MV 地圖／專案／角色產生器）和未提交工作都沒有記錄 | ledger 不完整 | CB0 |
| C-4 | `audit/REAL_ENVIRONMENT_VALIDATION.md` 寫 MV fixture「not available」，但 `audit/REAL_VALIDATION_ACCEPTANCE_REPORT_2026-09-26.md` 寫 15 個 MV 實機測試 PASS | 證據互相矛盾 | 以較新的 acceptance report 為準；CB0 標註 |
| C-5 | `pyproject` 版本 `0.158.0a158`，PROGRESS 基準是 v0.159 | 版本不一致 | CB0 |
| C-6 | `ASTERIA_SPEC.md` 的 Character Generator 小節 vs `SCOPE_DECISIONS.md` 取消 | 已解決：E | D2 |
| C-7 | `CODEX_HANDOFF.md` 第 4 點（MV 不得進入 Presentation／Runtime）vs 實際程式碼 | 違反（見 G-6） | CB0 |

---

## 2. 測試執行紀錄

| 指令 | 環境 | 結果 |
|---|---|---|
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -p no:cacheprovider`（Audit 初次執行） | offscreen Qt | 1924 passed, 4 failed / 1928 |
| `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mv_character_creator_e2e.py` | 原生 Cocoa | 1 passed（offscreen 失敗只是 `editor_platform == "cocoa"` 斷言造成） |
| 同第一行（撤回工作樹變更後） | offscreen Qt | **1922 passed, 3 failed / 1925** |
| `.venv/bin/python -m compileall -q src tests` | — | PASS |
| `.venv/bin/ruff check src` | pyproject 設定 | 444 個問題（305 個可自動修）；正確性類只有 `F601`（`assets/rpg_maker_mv_generator.py:28`）、`PLE0605`（`presentation/__init__.py:458`），還有 2 個 `B023` |

3 個失敗都在 `tests/test_asteria_boss_pack.py`（屬於 B 類美術驗收，見 DECISION_LOG D4，原始錯誤紀錄有保留）。
**沒有執行（NE）：** 打包後獨立啟動、真實 GPU、音訊裝置、硬體 profiling、滑鼠／鍵盤自動化（Editor）、CI。

---

## 3. 子系統缺口與證據

### G-1 Runtime 沒有消費 Battle Presentation（BTL-04、CMP-*、VFX-01、UI-01）— **Critical**
- 實際的 Run Project 路徑是：`editor/runtime_launcher.py` → `runtime/preview.py:88-95` → `runtime/playable_test_runtime.py` `PlayableTestRuntime`（619 行，手刻 pygame）
- `src/` 中除了 `presentation/` 本身和 3 個 editor attachment 預覽模組，**沒有任何模組 import `asteria.presentation`**
- `platform/pygame_battle_ui.py` `PygameBattleUiBackend`：0 個呼叫者、0 個測試
- 影響：約 1.24 萬行、Batch 94–139 的 presentation 成果在遊玩中不可見；Editor 的 Battle Presentation／Runtime RPG UI 設定沒有效果
- 處理：CB2，**Incremental**（D6）

### G-2 Runtime 不執行 Event VM（EVT-01–04、EDT-04、RPG-07）— **Critical**
- `runtime/game_session.py:55-66` `field_step` 會線性掃描 program，只處理 `WORLD` + `command == "START_ENCOUNTER"`
- `EventRunner`／`EventScheduler`／`SceneEventRuntime` 在 `events/` 以外 0 個使用者
- `WorldCommandRouter`：`src/` 中 0 個已註冊 handler；`authoring/api.py:355` 和 `editor/shell.py:811` 會產生 `TRANSFER`，但沒有任何東西處理
- 處理：CB1

### G-3 Playable runtime 裡寫死了規則和 ID（GP-02、GP-05、BTL-01–03）— **High**
- `playable_test_runtime.py:503`：以自己為目標的技能 ID 集合
- `:506-510`：`"momentum"` boost
- `:515`：`"stagger_system"`
- `:428,556`：`"momentum"` UI
- `game_session.py:290-291`：`"vitality"`
- 回合順序寫死，沒有使用 `rpg/battle_scheduler.py`
- 處理：CB3（把規則搬回 canonical 資料，避免出現第二套 battle rules，見 D6）

### G-4 Engine 平台能力（ENG-05/07/09/15–18、ENG-23、ANI-02）— **High**
- Input：`pygame_backend.poll_actions` 寫死 4 個動作；沒有 gamepad、rebinding 或 action map
- Collision：只有 tile 碰撞
- Audio：`AudioBackend` 只是 Protocol，`src/` 中沒有 `pygame.mixer`
- 沒有 fixed step、Transform 階層、場景轉場、Prefab、動畫 state machine
- `SystemScheduler` 存在，但 0 個具體 System
- 處理：CB4–CB8

### G-5 被移除的功能（ENG-12、VFX-02、EDT-02、EDT-16）— **High（Regression）**
- `bf4a993` 刪除：
  - `platform/moderngl_backend.py` + `moderngl_shaders.py` + `tests/test_moderngl_backend.py`（491 行）
  - `editor/actor_appearance.py`、`asset_thumbnails.py`、`unit_authoring.py`、`class_design_panel.py`、`runtime/actor_link.py` 和它們的測試
- 這些都沒有 Generator 依賴（D1／D2）
- 處理：CB9、CB14

### G-6 MV 語意越過 asset 邊界（AST-13、CMP-02）— **High**
- 已 commit：`runtime/rpg_maker_mv_map_render.py`（在 Runtime 層 import `assets.rpg_maker_mv_*`）
- 工作樹：`graphics/mv_weapon_visual.py`；`presentation/battle_screen.py` `sync_weapon_loadouts` 讀 MV `System.json` 的 `weaponTypes` 和 `mv-weapon-type:` tag；`presentation/battle_runtime.py` `set_weapon_visual`／`_weapon_visuals`（武器專用路徑，違反 S§44.1）
- 處理：CB0。提案 patch 已備妥：`docs/audits/proposed/P0-3_mv_semantics_to_asset_boundary.patch`（未套用）

### G-7 Editor 工具缺口（EDT-05–11、13–15）— **Medium**
沒有 action timeline 編輯器、debugger、VFX 工具、右鍵選單、批次編輯、語法高亮／自動完成；動畫編輯器只有預覽。處理：CB10

### G-8 遊戲系統缺口（RPG-04–10、WLD-01–02、UI-02）— **Medium**
沒有商店／經濟、任務、關係／成就／圖鑑、捕捉／收納、field AI、spawn/wave；UI 缺 pause／存讀檔／game over。處理：CB11

### G-9 驗證基礎設施（AST-06、AST-09、ENG-20）— **Medium**
沒有 CI；沒有 golden 測試套件；沒有遷移框架；沒有打包啟動。部分 MV 測試沒有 skip 機制，依賴本機 Steam 安裝。處理：CB12、CB13

### G-10 已取消範圍的殘留物（CG-01、AST-12）— **Low（衛生）**
Character Generator 相關程式、AI 美術（`assets/starter/characters/*`，約 28 MB，未追蹤）、MV 衍生原型（`mv_generator_prototype`、`mv_combat_prototypes`）放在可散布的 `assets/starter/` 路徑；`ready_user_hero` 的刪除還沒 commit（D3）。處理：CB15，先完成 CB14

---

## 4. 已確認完整的部分（A）

ENG-01、04、06、08、11、19、22；ANI-01；GP-01、03、04、06；RPG-03；EDT-01、12；AST-01、03。
它們的共同點是：資料模型與規則層完整、測試密集，並且有 GUI 或實機證據。Battle Core（`rpg/battle*`，Batch 93 凍結）能力也完整，只是整合度不足，所以列為 B。
