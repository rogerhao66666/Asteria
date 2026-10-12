# FINAL_CLOSURE_AUDIT（D19，2026-10-11）

範圍：ASTERIA_SPEC、ASTERIA_ASSET_SPEC、ASTERIA_ASSET_PIPELINE、ASTERIA_ART_DIRECTION 的 97 項 active 需求（另有 2 項取消、3 項不在本期）。計數一律由 `SPEC_TRACEABILITY_MATRIX.md` 表格逐列計算，不手算。D18 的版本見 git 歷史（`9b93763`）。

## 1. 摘要

| | D19（`06a5577`，逐列重算） | D20（現在） |
|---|---|---|
| A 已實作並驗證 | 71（註記寫 72，多算 1 項） | **86** |
| B 已實作，缺部分驗證 | 22 | **8** |
| C 部分實作 | 1 | **1**（TPL-01，Eventual） |
| D 未實作 | 2 | **2**（EDT-17、EDT-18，Eventual） |
| E 取消 | 2 | 2 |
| 自動化測試 | 2180 passed | **1999 passed**（D20-2 退役 35 個模組時移除只測退役程式碼的測試） |
| 實機檢查（`results.json`） | 49 PASS／3 NE／1 BLOCKED／0 FAIL | **65 PASS／3 NOT EXECUTED／1 BLOCKED／1 FAIL** |

**結論：** 功能面已完成，所有 Core 需求都已實作，剩下的 C／D 全是 SPEC 原文的 Eventually／Potential 項目。

**唯一的 FAIL：** weather load（最新一次 35.5 fps，門檻 55）。執行時 macOS 低耗電模式開著，舊 commit 在相同條件下也只有 34.7 fps，所以不是程式回歸，但在重跑前仍記為 FAIL。

**剩下的 8 項 B：** 全部需要人或裝置。AST-07（物品圖示）和 VFX-01 的粒子功能已依你的決定完成（D20-5）；VFX-01 只剩人工目視。

**不宣告 FULL SPEC CLOSURE VERIFIED。**

## 2. 本期變更（詳見 DECISION_LOG D20）

- **作者彈性：**
  - DOT 預設固定，作者可以選擇套用倍率；也可以設定逐回合加重。
  - 倍率規則任意設定，可以做出八方旅人式的弱點、破盾、Boost、雙武器和副職業。
  - 背包規則、召喚與夥伴、技能冷卻、行動時序都成為專案選項。
- **CB15：** 退役 35 個從產品進入點無法觸及的模組（`78dd3fb`，有備份與回滾說明）。
- **編輯器：**
  - 表單標籤改在欄位上方，並依寬度排出最多欄數。
  - Asset 清單新增 Auto-fix Image 和 Pack into Atlas。
- **B 項實機證據：** 13 項 B→A（實機項目 36–40）。過程中修正 2 個在實機截圖才看得到的缺陷。
- **八方旅人式戰鬥 demo（D20-6）：** `reference_projects/octopath_demo` 可直接遊玩。新增完整的戰鬥指令選單，畫面上會顯示護盾、弱點和 BP；奧義、多段多屬性攻擊、Donate BP、召喚寵物、調和、狀態效果都由資料設定。D20-7 再加入 6 種打法各不相同的敵人（吸收、反射、免疫、抗性、分裂、高速），分成 4 場戰鬥，由場景中遊蕩的敵人觸發。實機項目 44。
- **物品／裝備圖示（AST-07，B→A）與粒子特效（VFX-01）：** 實機項目 41–43；戰鬥粒子每幀重啟的缺陷由實機截圖發現並修正。

### D19 變更（保留）

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

BTL-02 的 DOT 問題已經依「不限制作者」的決定結案：預設固定，作者可以選擇套用倍率。

## 4. 剩下的驗證缺口（8 項 B）

逐項見 `REMAINING_WORK_PLAN.md` §D20。
- **需要人或裝置（8 項）：** ENG-14（M1）、ENG-15（M2、M8）、ENG-18（M3、M4）、CAM-01（M5）、VFX-01／02／03（M10）、BTL-04（M1–M3）。

## 5. 實機與效能（Apple M5，macOS 27.0.1，Python 3.13.15，pygame-ce 2.5.8）

| 工作負載 | 後端 | fps | p99 間隔 | 其他 |
|---|---|---|---|---|
| canonical 戰鬥 10 s | pygame | 55.8 | 18.9 ms | 1 幀超出 1.5 倍預算 |
| canonical 戰鬥 | ModernGL presenter | 56.8 | 18.9 ms | GPU 畫面與合成畫面逐像素相同 |
| 無美術專案的戰鬥 | pygame／ModernGL | 55.5／56.5 | 22.7／24.6 ms | 以真實按鍵打到勝利 |
| field＋全部效果 5 s | ModernGL／pygame | 56.3／55.7 | 24.0／19.1 ms | ModernGL 每幀 15 個 draw call |
| 雨 800 粒子 soak 30 s | ModernGL／pygame | 57.5／55.8 | 23.4／19.1 ms | 0 錯誤；RSS 持平 |
| 雨 2000 粒子＋全部效果 | ModernGL | 59.3（D19）；31.8（D20，低耗電模式，FAIL） | 21.7 ms；35.9 ms | VFX 區段 4.4 → 8.9 ms；舊 commit 同條件 34.7 fps |
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
- **未被引用模組：** D20 用可達性分析審查後退役 35 個、保留 7 個（CB15 Part F，`git revert 78dd3fb` 可回滾）。

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
| AUTOMATED VALIDATION COMPLETE | **未達成**：只差 weather load（低耗電模式下 FAIL）；使用者決定先不重跑。其他可自動化的項目都已有實機證據 |
| MANUAL VALIDATION PENDING | **是**：M1–M11 尚未執行（M2、M8 因沒有手把而 BLOCKED） |
| FULL SPEC CLOSURE VERIFIED | **未達成** |
