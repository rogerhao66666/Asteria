# CLOSURE_EXIT_CRITERIA

原始 SPEC closure 的可量測 gate。**Stage F 最終判定**只能是 PASS／FAIL／BLOCKED。任何一項驗證缺漏，都不得宣稱完成。

## 0. 計分規則

- **分母** = SPEC_TRACEABILITY_MATRIX 中的 active 需求（目前是 97 項）。E（取消）和「不在本期」（Deferred）不計入。
- **Closure 條件**：active 中 **C = 0** 且 **D = 0**。B 只有在缺的驗證屬於明確列管的 EXTERNAL gate 時才可以保留（見 G-EXT）。
- 「Eventual」需求（EDT-17、EDT-18、EDT-19、BTL-01–03）目前**計入**分母。若你決定延後，必須寫進 DECISION_LOG 並更新分母，不能靜默剔除。
- **目前基準（2026-10-09）**：A 17／B 20／C 44／D 16，共 97 → **FAIL**。

## 1. Gates

| Gate | 條件（全部必須成立） | 驗證方式 | 目前 |
|---|---|---|---|
| **G-REG** 回歸 | Active 測試套件 0 失敗、0 未說明的 skip；Retired（B 類美術）測試明確排除，失敗紀錄保留 | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，在 CI（Linux）和 macOS 都跑 | FAIL（3 個 B 類失敗還沒被歸類；沒有 CI） |
| **G-BOUND** 邊界 | MV／來源格式語意只出現在 `src/asteria/assets/`；runtime 不 import `editor`／PySide6 | grep 測試 + import-boundary 測試 | FAIL（RISK-03、RISK-05） |
| **G-EVENT** 事件 | Editor 撰寫的事件在 Run Project 中執行；標準 world command 都有 handler；中途存檔 → 讀檔 → 繼續 | CB1 的 E2E（HI）+ 實機 1 次 | FAIL（W-04 不存在） |
| **G-BATTLE** 戰鬥 | 只有一套 battle rules；runtime 沒有寫死的規則 ID；回合由 scheduler 決定；`CanonicalBattleAdapter` 消費 canonical events；新舊 adapter 對照測試 PASS；animation／VFX／camera／audio／hit-stop／多段／結果轉場都有驗證；Editor 的 presentation profile 改動在遊玩中可見 | CB2、CB3 的測試 + 實機截圖 | FAIL |
| **G-ENGINE** 平台 | ENG-02、03、05、07、09、14–18、20、23 都到 A 或 B-EXTERNAL | 各 Batch 驗收 | FAIL |
| **G-EDITOR** 編輯器 | §5 列出的 13 個面板都存在而且可以操作；生產力需求都有實作；Cocoa GUI smoke PASS | GS + 實機截圖 | FAIL |
| **G-ASSET** 資產 | AP§48 的 DoD 9 項全部 PASS；AS§35 Phase A 的類別齊全；AS§34 golden suite PASS | UT + HI + RM | FAIL |
| **G-INSPECT** 通用 Inspector（D2） | 不靠 Generator 就能完成「匯入 sprite sheet → 指派給 Actor → 放上地圖 → 遊玩」 | CB14 的 E2E | FAIL |
| **G-PKG** 打包 | 匯出的遊戲在乾淨環境可以獨立啟動 | PK 層實測 | NE |
| **G-PERF** 效能 | 實機 benchmark 基準已建立；field 和 battle 在參考專案上 60 fps（frame time p95 ≤ 16.7 ms，在參考機上量測）；PERF-01 已處理 | CB13d | NE |
| **G-DOC** 文件 | README、`ASTERIA_PROGRESS.md`、pyproject 一致；traceability 矩陣已更新到最終狀態 | 人工審查 | FAIL（C-1–C-5） |
| **G-SCOPE** 取消範圍 | 沒有 AI／MV 衍生美術被追蹤；Generator 專屬程式已封存（CB15，經過批准）；共用功能都保留 | `git ls-files` 檢查 + G-INSPECT | FAIL |
| **G-EXT** 外部 gate | 以下項目要有紀錄（PASS 或明確的 BLOCKED 加原因）：真實 GPU、音訊裝置延遲、gamepad、滑鼠／鍵盤 Editor 自動化、硬體 profiling | 實機紀錄 | NE |

## 2. 判定

- **PASS**：所有 gate 都 PASS，G-EXT 每項都有紀錄。
- **BLOCKED**：功能 gate 都 PASS，只剩 G-EXT 因為環境無法執行。
- **FAIL**：任何功能 gate 沒過。

**目前判定：FAIL**（這是預期中的，Stage D 只是基準）。

## 3. 證據要求

每個 gate 都必須附上：
- commit hash
- 完整指令
- 環境（OS、Python、GPU／音訊裝置）
- 預期結果與實際結果
- 截圖或 JSON 結果檔的路徑

「NE」不得寫成 PASS；只有單元測試不得算作整合 PASS。
