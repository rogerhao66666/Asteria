# FINAL_CLOSURE_AUDIT（D19，2026-10-11）

範圍：ASTERIA_SPEC、ASTERIA_ASSET_SPEC、ASTERIA_ASSET_PIPELINE、ASTERIA_ART_DIRECTION 的 97 項 active 需求（另有 2 項取消、3 項不在本期）。計數一律由 `SPEC_TRACEABILITY_MATRIX.md` 表格逐列計算，不手算。D18 的版本見 git 歷史（`9b93763`）。

## 1. 摘要

| | D18（`9b93763`） | D19（現在） |
|---|---|---|
| A 已實作並驗證 | 49 | **72** |
| B 已實作，缺部分驗證 | 45 | **22** |
| C 部分實作 | 1 | **1**（TPL-01，Eventual） |
| D 未實作 | 2 | **2**（EDT-17、EDT-18，Eventual） |
| E 取消 | 2 | 2 |
| 自動化測試 | 2165 passed | **2180 passed** |
| 實機檢查（`results.json`） | 29 PASS／3 NE／1 BLOCKED | **49 PASS／3 NOT EXECUTED／1 BLOCKED／0 FAIL** |

**結論：** 功能面已完成——所有 Core 需求都已實作，剩下的 C／D 全是 SPEC 原文的 Eventually／Potential 項目。自動化驗證已完成到目前能自動化的程度，但還有 13 項 B 可以再自動化（§4）。人工驗證尚未執行。**不宣告 FULL SPEC CLOSURE VERIFIED。**

## 2. 本期變更（詳見 DECISION_LOG D19）

- **Canonical 戰鬥呈現完整取代 legacy：** 沒有戰鬥美術的專案也能完整呈現；pygame 與 ModernGL 都通過實機驗證。CB15 A9 已退役。
- **整合問題：**
  - haste／slow 現在會改變速度，並影響排程器的下一個回合。根因是速度變化沒有進到 scheduler，加上內容本身沒有速度效果。
  - 編輯器重複的「Assets / Console」分頁已修正。根因是 Qt 6 在第二個 tab 群組留下舊的 tab bar。
- **編輯器 UI／UX：**
  - 視窗可放進筆電螢幕：最小尺寸 1721×1772 → 763×435。
  - 三套配色、55 個繪製圖示、按鈕依用途上色。
  - 資訊密度提升，各工作區有自己的面板配置。
  - 全部 GUI 文字已審查並精確化，record 欄位改為可讀名稱。
  - 版面會持久化。
- **B 項驗證：** session 測試在實機重跑（`b_items_replay`）、`Application.run` 實機主迴圈、戰鬥記憶體量測。23 項 B→A。
- **M10：** 自動化比較已完成；pygame 仍為 macOS 預設。

## 3. 剩下的功能缺口

| 需求 | 狀態 | 說明 |
|---|---|---|
| TPL-01 | C（Eventual） | 只有 Empty 範本與 Reference World |
| EDT-17 | D（Eventual） | Gameplay System Builder，SPEC §31「should eventually」 |
| EDT-18 | D（Eventual） | Plugin runtime，SPEC 未要求當前版本 |

另有一個待決定的語意問題，不算缺陷：BTL-02 的 DOT（狀態持續傷害）是否要套用屬性倍率，SPEC 沒有寫明。

## 4. 剩下的驗證缺口（22 項 B）

逐項見 `REMAINING_WORK_PLAN.md` §D19。
- **需要人或裝置（8 項）：** ENG-14（M1）、ENG-15（M2、M8）、ENG-18（M3、M4）、CAM-01（M5）、VFX-01／02／03（M10）、BTL-04（M1–M3）。
- **待你決定（1 項）：** BTL-02。
- **還能自動化（13 項）：** ENG-13 parallax、ENG-20 遷移後實機開啟、ANI-02 狀態機驅動戰鬥動畫、CAM-02 target group、CMP-03（沒有 runtime 消費者）、GP-02 cooldown／cast、RPG-01 容量、RPG-08 召喚／成長／收納、EVT-04 sequence 中的對話與音樂軌、EDT-16、AST-07、AST-08、AST-11。

## 5. 實機與效能（Apple M5，macOS 27.0.1，Python 3.13.15，pygame-ce 2.5.8）

| 工作負載 | 後端 | fps | p99 間隔 | 其他 |
|---|---|---|---|---|
| canonical 戰鬥 10 s | pygame | 55.8 | 18.9 ms | 1 幀超出 1.5 倍預算 |
| canonical 戰鬥 | ModernGL presenter | 56.8 | 18.9 ms | GPU 畫面與合成畫面逐像素相同 |
| 無美術專案的戰鬥 | pygame／ModernGL | 55.5／56.5 | 22.7／24.6 ms | 以真實按鍵打到勝利 |
| field＋全部效果 5 s | ModernGL／pygame | 56.3／55.7 | 24.0／19.1 ms | ModernGL 每幀 15 個 draw call |
| 雨 800 粒子 soak 30 s | ModernGL／pygame | 57.5／55.8 | 23.4／19.1 ms | 0 錯誤；RSS 持平 |
| 雨 2000 粒子＋全部效果 | ModernGL | 59.3 | 21.7 ms | VFX 區段 4.4 ms |
| 12 場戰鬥 | pygame | — | — | 戰鬥圖片 0 殘留；RSS 約 173 MB 持平 |
| `Application.run` 8 s | pygame | — | — | fixed step 400／400 |

不宣稱 GPU 帶來效能提升，也不宣稱零卡頓。

## 6. M10（ModernGL）

- **自動化部分已完成（實機 #33）：**
  - 無效果時兩個後端畫面相同。
  - 有效果時 10.1% 的像素不同；pygame 不支援 bloom、grade、shadows、vignette，其餘效果以近似方式呈現。
  - 30 秒 soak 兩個後端都是 0 錯誤；ModernGL 的 RSS 在暖機後持平（另外跑 90 秒驗證）。
- **人工目視：** NOT EXECUTED。
- **決定：** pygame 維持 macOS 預設，ModernGL 為選用。

## 7. CB15

- **已退役：** A1–A5、A7、A8（D18）與 A9（D19）。
- **保留：** A6、A10。沒有 BLOCKED 項目。
- **候選清單：** D19 掃描出 23 個沒有產品程式引用的模組，依「不確定就保留」原則全部保留，待你決定是否另開批次逐項審查（CB15 Part E）。

## 8. 人工驗證清單

步驟見 `REAL_MACHINE_VALIDATION.md`「Manual procedures」。

| # | 項目 | 需要 | 狀態 |
|---|---|---|---|
| M1 | 實體鍵盤 | 人 | NOT EXECUTED |
| M2 | 手把 | 手把 | BLOCKED |
| M3 | 可聽音訊 | 人 | NOT EXECUTED |
| M4 | 音訊延遲 | 錄音或 loopback | NOT EXECUTED |
| M5 | 流暢度、鏡頭手感 | 人 | NOT EXECUTED |
| M6 | Finder 開啟 .app | 人 | NOT EXECUTED |
| M7 | 編輯器人工操作（含新配色與文字） | 人 | NOT EXECUTED |
| M8 | 手把重綁 | 手把 | BLOCKED |
| M9 | D17 目視 | 人 | NOT EXECUTED |
| M10 | VFX 目視（GPU 與 pygame） | 人 | NOT EXECUTED（自動化部分已完成） |
| M11 | 使用者自己的 MV 專案 | 人＋MV 專案 | NOT EXECUTED |

## 9. 狀態判定

| 狀態 | 是否達成 |
|---|---|
| FUNCTIONAL CLOSURE COMPLETE | **達成**：所有 Core 需求都已實作；剩下的 C／D 全為 Eventual |
| AUTOMATED VALIDATION COMPLETE | **未達成**：還有 13 項 B 可以再自動化 |
| MANUAL VALIDATION PENDING | **是**：M1–M11 尚未執行（M2、M8 因沒有手把而 BLOCKED） |
| FULL SPEC CLOSURE VERIFIED | **未達成** |
