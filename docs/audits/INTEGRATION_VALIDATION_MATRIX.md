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
| W-10 | 獨立打包啟動 | 不靠 repo 也能執行 | PARTIAL | PASS（package 模型） | NE | N/A | NE | **NE** | NE | `assets/package.py`、`package_installer.py` | 沒有 launcher／匯出流程（AST-06） |
| W-11 | 遊玩存檔 → 讀檔 → 繼續 | 狀態完全相同 | PASS | PASS | PASS（完整 playable 存讀比對〔AR〕） | N/A | PARTIAL | NE | N/A | `runtime/game_save.py`、`validation/playable_runtime_loop.py` | 事件中斷點無法恢復（因為 VM 不跑） |
| W-12 | Attachment 撰寫 → 預覽 → runtime | 裝備可見 | PASS | PASS | PASS | PASS（預覽） | **N/A** | NE | NE | `editor/attachment_preview.py` | G-1 |
| W-13 | Battle presentation 設定（Editor）→ 遊玩 | 設定生效 | PASS | PASS | PASS | PASS（編輯） | **N/A** | NE | NE | `editor/battle_presentation_authoring.py` | G-1 |
| W-14 | Runtime RPG UI 設定 → 遊玩選單 | 設定生效 | PASS | PASS | PASS | PASS（編輯） | **N/A** | NE | NE | `editor/runtime_rpg_ui_authoring.py` vs 手刻 `_draw_build_menu` | G-1 |
| W-15 | 音訊 cue → 裝置播放 | 正確時序 | PASS | PASS（cue 排程） | PASS | N/A | **N/A**（沒有後端） | NE | NE | `presentation/audio_runtime.py` | G-4 |
| W-16 | GPU 渲染路徑（shader、lighting、批次） | 與 pygame 等價或更好 | PARTIAL | PASS（headless 指令） | PASS | N/A | **N/A**（後端已移除） | NE | NE | `render/*`；`git show 16a6ebd:src/asteria/platform/moderngl_backend.py` | D1、G-5 |
| W-17 | 遺失／錯誤 asset 處理 | 結構化診斷 | PASS | PASS | PASS | PARTIAL | PASS〔AR〕 | NE | N/A | `assets/quality_gate.py`、`editor/resource_resolver.py` `EditorResourceError` | — |
| W-18 | MV 專案 → Asteria 專案 → Run | 地圖和角色可遊玩 | PASS | PASS | PASS | PASS（原生 Cocoa，本次） | PASS〔AR：3 影格〕 | NE | NE | `tests/test_mv_character_creator_e2e.py`、`test_rpg_maker_mv_project.py` | 需要本機 MV 安裝；違反 MV 邊界（G-6） |
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
