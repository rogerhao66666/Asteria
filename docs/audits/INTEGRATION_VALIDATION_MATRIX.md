# INTEGRATION_VALIDATION_MATRIX

追蹤跨系統工作流程，並把每條流程拆成不同的驗證層級。

**層級代碼：**
- **CI**：程式碼檢視
- **UT**：單元／契約測試
- **HI**：headless 整合
- **GS**：GUI smoke（offscreen Qt 或 Cocoa）
- **RM**：實機視窗
- **PK**：打包後啟動
- **PF**：效能 benchmark

**結果代碼：** PASS、PARTIAL、FAIL、**NE（未執行）**、**N/A（路徑不存在）**

**證據來源：**
- 本次執行（2026-10-09）
- `audit/REAL_VALIDATION_ACCEPTANCE_REPORT_2026-09-26.md`，以下標記為〔AR〕；那是當時的 Codex 實機紀錄，本次沒有重跑

| # | 工作流程 | 預期 | CI | UT | HI | GS | RM | PK | PF | 證據／指令 | 阻擋點 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W-01 | 建立 → 編輯 → 存檔 → 重開專案 | canonical 資料相等 | PASS | PASS | PASS | PASS〔AR：Cocoa、9 張截圖〕 | N/A | NE | N/A | `tests/test_editor_*`、`test_complex_reference_rpg_project.py` | 滑鼠／鍵盤自動化 PARTIAL〔AR〕 |
| W-02 | 匯入 asset → 設定動畫 → runtime 播放 | 在 field 播放 | PASS | PASS | PASS | PARTIAL | PASS〔AR：MV `Actor1.png` 四方向 12 影格〕 | NE | NE | `tests/test_rpg_maker_mv_adapter.py`、`scripts/validate_mv_character_creator.py` | battle／側視動畫沒有 runtime 路徑（G-1） |
| W-03 | Entity + components + behavior | 移動、碰撞、動畫 | PASS | PASS | PASS | PASS | PARTIAL（tile 碰撞） | NE | NE | `runtime/player.py` `PlayerRuntime` | 沒有 collider／AI behavior（G-4） |
| W-04 | Event → 狀態更新（Editor 撰寫 → Run） | 對話、開關、轉移生效 | **FAIL** | PASS（只到 VM 層） | **N/A** | PASS（編輯器） | **N/A** | NE | N/A | `runtime/game_session.py:55-66` 只處理 `START_ENCOUNTER` | G-2 |
| W-05 | 戰鬥執行 → 演出 → 結果 | 遊玩中使用 canonical 規則和 presentation | PARTIAL | PASS（rpg + presentation 各自） | PASS（`validation/playable_battle*.py`） | N/A | PARTIAL（手刻 `_draw_battle`） | NE | PARTIAL（合成負載） | `runtime/playable_test_runtime.py:381-563` | G-1、G-3 |
| W-06 | 動畫 編輯 → 存檔 → 讀檔 → 播放 | 編輯器可以改 clip | PARTIAL | PASS | PASS | PARTIAL（只有預覽） | PARTIAL | NE | NE | `editor/animation_widget.py` | 沒有動畫編輯器（EDT-05） |
| W-07 | GUI → canonical data | 單一 model | PASS | PASS | PASS | PASS〔AR〕 | N/A | N/A | N/A | `editor/integrated_authoring.py`（共用 `EditorDocument` command stack） | — |
| W-08 | Python API → GUI parity | API 改動在 GUI 可見 | PASS | PASS | PASS | PARTIAL | N/A | N/A | N/A | `authoring/api.py`、`editor/code_workspace.py` | 沒有實機互動驗證 |
| W-09 | Editor playtest → 返回 Editor | 子程序啟動、結束、回到 Editor | PASS | PASS | N/A | PARTIAL | PASS〔AR：3 影格後結束〕 | N/A | N/A | `editor/runtime_launcher.py`、`playmode.py` | 沒有從選定點出生和快速重啟 |
| W-10 | 獨立打包啟動 | 不靠 repo 也能執行 | PASS | PASS | PASS（`python -I`、暫時 HOME、在 repo 外啟動 folder／.pyz／.app；確認載入內附引擎） | PASS（editor Export Game） | NE | PASS（.pyz、.app 啟動 5 影格） | NE | `tests/test_migration_and_export.py` | 實機雙擊 .app 未執行；不產生免直譯器執行檔 |
| W-11 | 遊玩存檔 → 讀檔 → 繼續 | 狀態完全相同 | PASS | PASS | PASS（完整 playable 存讀比對〔AR〕） | N/A | PARTIAL | NE | N/A | `runtime/game_save.py`、`validation/playable_runtime_loop.py` | 事件中斷點無法恢復（因為 VM 不跑） |
| W-12 | Attachment 撰寫 → 預覽 → runtime | 裝備可見 | PASS | PASS | PASS | PASS（預覽） | **N/A** | NE | NE | `editor/attachment_preview.py` | G-1 |
| W-13 | Battle presentation 設定（Editor）→ 遊玩 | 設定生效 | PASS | PASS | PASS | PASS（編輯） | **N/A** | NE | NE | `editor/battle_presentation_authoring.py` | G-1 |
| W-14 | Runtime RPG UI 設定 → 遊玩選單 | 設定生效 | PASS | PASS | PASS | PASS（編輯） | **N/A** | NE | NE | `editor/runtime_rpg_ui_authoring.py` vs 手刻 `_draw_build_menu` | G-1 |
| W-15 | 音訊 cue → 裝置播放 | 正確時序 | PASS | PASS（cue 排程） | PASS | N/A | **N/A**（沒有後端） | NE | NE | `presentation/audio_runtime.py` | G-4 |
| W-16 | GPU 渲染路徑（shader、lighting、批次） | 與 pygame 等價或更好 | PARTIAL | PASS（headless 指令） | PASS | N/A | **N/A**（後端已移除） | NE | NE | `render/*`；`git show 16a6ebd:src/asteria/platform/moderngl_backend.py` | D1、G-5 |
| W-17 | 遺失／錯誤 asset 處理 | 結構化診斷 | PASS | PASS | PASS | PARTIAL | PASS〔AR〕 | NE | N/A | `assets/quality_gate.py`、`editor/resource_resolver.py` `EditorResourceError` | — |
| W-18 | MV 專案 → Asteria 專案 → Run | 地圖和角色可遊玩 | PASS | PASS | PASS（`test_mv_import_playable.py`：匯入→存檔→重載→遊玩，碰撞、對話、轉移、存讀檔） | PASS（editor File → Import RPG Maker MV Project…） | **PASS**（`mv_import_real_window`、`mv_import_gpu_night`：實機視窗、真實按鍵，NPC 對話、門轉移到 (8, 23)，遊玩時不載入 MV 模組） | NE | NE | `assets/rpg_maker_mv_map_bake.py`、`runtime/tilemap_field.py` | 依本機 MV reference（git-ignored）；未轉換的 MV 指令列為匯入問題 |
| W-19 | 輸入 → 移動 → 攝影機跟隨（實機） | 即時操作 | PASS | PASS | PASS | N/A | **PARTIAL**〔AR：沒有驗證即時鍵盤操作和攝影機跟隨〕 | NE | NE | `runtime/player.py` | 沒有 gamepad 和 rebinding |
| W-20 | 回歸套件 | 全綠 | — | **1922 PASS / 3 FAIL**（B 類美術） | — | — | — | — | — | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -p no:cacheprovider` | 沒有 CI |

## 摘要

| 層級 | PASS | PARTIAL | FAIL | NE | N/A |
|---|---|---|---|---|---|
| RM（實機），W-01–W-19 | 4 | 5 | 0 | 1 | 9 |
| PK（打包），W-01–W-19 | 0 | 0 | 0 | 16 | 3 |

- RM 的 9 個 N/A 中，有 6 個（W-04、W-12、W-13、W-14、W-15、W-16）是「**路徑不存在**」：不是「還沒測」，而是「沒有可以測的整合」。另外 3 個（W-01、W-07、W-08）本來就沒有 runtime 段落。
- **打包啟動完全沒有被驗證過。**
- 結論：單元層非常紮實；**整合層和實機層是 closure 的主要阻擋**。

## D19 現況（2026-10-11，依目前證據逐列重評）

上方各表保留原始稽核時的結果作為歷史，這張表是目前的狀態。RM 證據見 `REAL_MACHINE_VALIDATION.md` 的項目編號。

| ID | 流程 | 目前結果 | 依據 |
|---|---|---|---|
| W-01 | 建立 → 編輯 → 存檔 → 重開 | PASS | 原表 AR（Cocoa） |
| W-02 | 匯入 asset → 動畫 → runtime 播放 | PASS | W-18 實機（MV 角色 sheet 在 field 播放，RM #20） |
| W-03 | Entity + components + behavior | PASS | RM #31：`Application.run` 中的 collision、controller、animation、camera |
| W-04 | Event → 狀態更新（Editor → Run） | PASS | RM #11 cutscene、#28 editor event 在 live game、#30 EVT-01／02／03 replay |
| W-05 | 戰鬥 → 演出 → 結果 | PASS | canonical 是唯一戰鬥畫面（A9 已退役）；RM #6、#26、#29（無美術專案也能完整呈現） |
| W-06 | 動畫 編輯 → 存檔 → 播放 | PASS | RM #10（animation editor）、#13（戰鬥中的分層動畫） |
| W-07 | GUI → canonical data | PASS | 原表 |
| W-08 | Python API → GUI parity | PASS（offscreen GS） | 原表；沒有 RM 段落 |
| W-09 | Editor playtest → 返回 | PASS | RM #7 |
| W-10 | 獨立打包啟動 | PASS | RM #18（.app 在 repo 外執行）；在 Finder 雙擊開啟仍為人工 M6 |
| W-11 | 遊玩存檔 → 讀檔 → 繼續 | PASS | RM #8b（SIGKILL 後讀回）、#15（存檔欄位） |
| W-12 | Attachment 撰寫 → runtime | PASS | RM #13、#30 CMP-01（field 與戰鬥） |
| W-13 | Battle presentation 設定 → 遊玩 | PASS | RM #19（Character Composition 編輯器）＋#13 |
| W-14 | Runtime RPG UI 設定 → 遊玩選單 | PASS | RM #14、#27（狀態、任務、商店、裝備、設定畫面） |
| W-15 | 音訊 cue → 裝置播放 | PASS（裝置） | RM #3a；可聽確認與延遲仍為人工 M3、M4 |
| W-16 | GPU 渲染路徑 | PASS | RM #22（GPU 畫面與合成畫面逐像素相同）、#23、#33（與 pygame 的量化比較）；目視為人工 M10 |
| W-17 | 遺失／錯誤 asset | PASS | 原表 AR；#29（沒有任何圖片時改用剪影與產生的背景） |
| W-18 | MV 專案 → Run | PASS | RM #20、#21 |
| W-19 | 輸入 → 移動 → 鏡頭跟隨 | PASS（OS 事件佇列） | RM #2a、#16、#17；實體按鍵為人工 M1 |
| W-20 | 回歸套件 | PASS | 2180 passed（`9576dda`） |

19 個流程全部有整合證據（W-08 只有 GS）。剩下的人工項目只有實體按鍵（M1）、可聽音訊與延遲（M3、M4）、Finder 開啟 .app（M6）與 GPU 目視（M10）。
