# FINAL_CLOSURE_AUDIT（D18，2026-10-11）

範圍：ASTERIA_SPEC、ASTERIA_ASSET_SPEC、ASTERIA_ASSET_PIPELINE、ASTERIA_ART_DIRECTION 的 97 項 active 需求（另 2 項取消）。計數一律由 `SPEC_TRACEABILITY_MATRIX.md` 表格逐列計算，不手算。

## 1. Final Executive Summary

| | 起點（`f6b116b`） | 現在 |
|---|---|---|
| A 已實作並驗證 | 31 | **49** |
| B 已實作，缺部分驗證 | 60 | **45** |
| C 部分實作 | 4 | **1**（TPL-01，Eventual） |
| D 未實作 | 2 | **2**（EDT-17、EDT-18，Eventual） |
| E 取消 | 2 | 2 |
| 自動化測試 | 2176 passed | **2165 passed**（退役 Character Generator 移除 41 個只測該功能的測試；本期新增約 30 個） |
| 實機檢查 | — | **29 PASS、3 NOT EXECUTED、1 BLOCKED** |

**結論：不宣告無條件完成。** 所有 Core 需求的功能都已實作（剩下的 C／D 全是 SPEC 原文標示 Eventually／Potential 的項目）；45 項 B 的功能完成，但還缺部分實機或人工證據（見 §4、§10）。

## 2. Updated SPEC Traceability Matrix

見 `SPEC_TRACEABILITY_MATRIX.md`（D18 註記列出每一項變更）。本期升為 A：ENG-02、ENG-09、ENG-12、ENG-23、CMP-04、GP-05、BTL-01、UI-01、UI-02、EDT-02、EDT-03、EDT-04、EDT-11、EDT-13、EDT-14、AST-02、AST-13、STR-01。VFX-02、VFX-03 由 C 升為 B。TPL-01 依 SPEC §36 原文「Potential templates」改列 Eventual。

## 3. Remaining Functional Gaps

| 需求 | 狀態 | 說明 |
|---|---|---|
| TPL-01 | C（Eventual） | 只有 Empty 範本與 Reference World |
| EDT-17 | D（Eventual） | Gameplay System Builder，SPEC §31「should eventually」 |
| EDT-18 | D（Eventual） | Plugin runtime，SPEC §32 未要求當前版本；既有擴充點保留 |

其他功能面注意事項（不影響狀態）：MV 事件只轉換第一頁與「對話後消失」慣用法，其餘列為匯入問題；參考內容的 `haste_song` 沒有機制效果；A9 legacy 戰鬥呈現仍是部分專案的後備。

## 4. Remaining Validation Gaps

45 項 B 的缺少證據逐項列在 `REMAINING_WORK_PLAN.md` §D18。主要類型：

- **需要人或裝置**：實體鍵盤（M1）、手把與重綁（M2、M8）、可聽音訊與延遲（M3、M4）、流暢度與鏡頭手感（M5）、Finder 開啟 .app（M6）、編輯器人工操作（M7）、VFX 目視（M10）、使用者自己的 MV 專案（M11）。
- **只有 UT／HI 的子功能**：例如 trigger／layer mask、hitbox／hurtbox、frame events、反擊／追擊、製作、遭遇生成、behavior tree 的 field 行為、parallax、persistent entities、normal map 與 screen shader 的實機畫面。

## 5. Integration Validation Results

`INTEGRATION_VALIDATION_MATRIX.md`：W-18（MV 專案 → Asteria → Run）由 FAIL 改為 **PASS**（HI＋實機，兩個後端）；W-10（獨立打包啟動）HI／PK PASS 且 .app 實機 PASS。

## 6. GPU / VFX Implementation Summary

- **ENG-12**：`GpuPresenter`（ModernGL，pygame 擁有視窗）呈現 playable runtime 的合成畫面；恆等畫面逐像素相同（32／24-bit）；GL 失敗自動回到 pygame 並記錄原因；vsync 預設關閉（macOS 實機曾卡住）。tile-map 專案走 `ModernglRuntimeBackend` 的 batched quads。**pygame 仍為預設後端**。
- **VFX-02**：場景元件 Environment2D、LightSource2D、ShadowCaster2D；GPU：半解析度光照圖、Lambert（normal 層）、陰影遮罩、bloom、grading、vignette、內建與專案 shader（編譯失敗會記錄並略過）。
- **VFX-03**：WaterRegion2D、天氣粒子（雨／雪／落葉／塵）、霧、afterimage／trail（battle timeline `motion_fx`、field `MotionTrail2D`）。
- **後備**：pygame 提供近似光照、霧、水、天氣、afterimage；bloom、grading、vignette、shader、陰影列為不支援，不影響遊玩。
- 資料：場景設定在 scene component、shader 與 normal map 在 asset registry、全域預設在 manifest `render`。

## 7. W-18 Closure Report

| 步驟 | 結果 | 證據 |
|---|---|---|
| 1 匯入 MV 專案 | PASS | `import_mv_project`、CLI、editor 選單 |
| 2 產生 canonical asset | PASS | atlas PNG、sprite sheet、Tileset、TileMap、Walkability 圖層、角色 sheet／動畫 |
| 3–5 存檔、關閉、重載 | PASS | 新行程讀回，所有參照可解析 |
| 6–7 啟動 runtime、繪製地圖 | PASS | `mv_import_real_window` 截圖 |
| 8 玩家移動 | PASS | 真實按鍵 |
| 9 碰撞 | PASS | 牆與 NPC 擋住玩家 |
| 10 場景轉移 | PASS | 門轉移到地圖 2 (8, 23) |
| 11 asset 參照 | PASS | `AssetResources` 全部解析 |
| 12 不依賴 MV 模組 | PASS | 遊玩時 `sys.modules` 沒有 `rpg_maker*` |

順帶修正：轉移後存檔無法讀回（引擎）、NPC 可被穿過、腳底基準不一致。

## 8. CB15 Retirement Summary

退役 Character Generator（A1–A5、A7、A8）；保留 CreateCharacterCommand（移除 bundle 分支）、legacy 戰鬥呈現（A9 BLOCKED）、runtime host（A10）。備份 `../Asteria_backup_2026-10-11_cb15_generator.zip`；回復 `git revert 71e76c1`。詳見 `CB15_RETIREMENT_REVIEW.md` Part D。

## 9. Performance and Regression Report

硬體：Apple M5（OpenGL 4.1 Metal），macOS 27.0.1 arm64，Python 3.13.15，pygame-ce 2.5.8（SDL 2.32.10）。方法：`RuntimeProfiler`，真實視窗，`clock.tick(60)`。

| 工作負載 | 後端 | 樣本 | fps | p99 間隔 | 其他 |
|---|---|---|---|---|---|
| canonical 戰鬥 10 s、7 個技能 | pygame | 559 幀 | 55.99 | 18.8 ms | jitter 0.72 ms，0 幀超出 1.5× |
| 同上 | ModernGL presenter | 562 幀 | 56.09 | 18.8 ms | 上傳 0.41 ms，GPU 0.58 ms，1 draw call |
| field＋光照、陰影、水、雨、bloom、grading 5 s | ModernGL | ~280 幀 | 55.97 | 19.1 ms | 15 draw calls／幀 |
| 同上 | pygame 後備 | ~280 幀 | 55.95 | 19.0 ms | GPU-only 效果列為不支援 |
| 雨 2000 粒子＋完整效果 4 s | ModernGL | ~240 幀 | 59.5–60.1 | 17.7–19.9 ms | 天氣 4.3 ms／幀 |
| 400 sprites 240 幀 | ModernGL（preview 後端） | 240 幀 | 61.4 | — | — |

不宣稱 GPU 帶來效能提升（R1 的目的是 GPU 呈現與效果，不是加速）；不宣稱零卡頓。

回歸：全套 2165 passed；golden baseline 只有 rpg_database hash 因 STR-01 內容調整而更新（有說明）；行為與時序 baseline 不變。

## 10. Manual Validation Checklist

步驟見 `REAL_MACHINE_VALIDATION.md`「Manual procedures」。

| # | 項目 | 需要 | 狀態 |
|---|---|---|---|
| M1 | 實體鍵盤 | 人 | NOT EXECUTED |
| M2 | 手把 | 手把 | BLOCKED |
| M3 | 可聽音訊 | 人 | NOT EXECUTED |
| M4 | 音訊延遲 | 錄音或 loopback | NOT EXECUTED |
| M5 | 流暢度、鏡頭手感 | 人 | NOT EXECUTED |
| M6 | Finder 開啟 .app | 人 | NOT EXECUTED |
| M7 | 編輯器人工操作 | 人 | NOT EXECUTED |
| M8 | 手把重綁 | 手把 | BLOCKED |
| M9 | D17 目視 | 人 | NOT EXECUTED |
| M10 | VFX 目視（GPU 與 pygame） | 人 | NOT EXECUTED |
| M11 | 使用者自己的 MV 專案 | 人＋MV 專案 | NOT EXECUTED |

## 11. Final Closure Audit

- **完整驗證（A）**：49 項。
- **已實作、等待人工或部分實機證據（B）**：45 項。
- **未完成功能**：0 項 Core；3 項 Eventual（TPL-01、EDT-17、EDT-18）。
- **Deferred**：STR-02、ARPG-01、AST-10（依 SCOPE_DECISIONS，不在分母）。
- **Cancelled**：2 項 E（Character Generator、AI 生成）。

**剩餘 closure blockers**：§10 的人工與裝置項目；§4 的 B 證據缺口；兩個待你決定的事項——macOS 預設後端是否改為 ModernGL、是否另開批次讓 canonical 戰鬥呈現取代 legacy（A9）。
