# AUDIT_EXECUTIVE_SUMMARY

**日期：** 2026-10-09 | **階段：** Stage D（Review，已停止） | **基準：** `d69817c` + 工作樹
**總判定：原始 SPEC closure = FAIL**（預期中的基準，見 CLOSURE_EXIT_CRITERIA）

## 數字

| 指標 | 值 |
|---|---|
| Active 需求 | 97 |
| A（已實作且已驗證） | 17（18%） |
| B（已實作，驗證或接線不足） | 20 |
| C（部分實作） | 44 |
| D（未實作） | 16 |
| E（取消）／不在本期 | 2 ／ 3 |
| 測試 | 1922 passed、3 failed（全部是 B 類 boss 美術，D4）；共 1925 個 |

「測試全綠不等於 closure」：大多數測試在單元層，整合層和實機層才是主要缺口。

## 五個關鍵缺口

1. **Runtime 不消費 Battle Presentation**（G-1）：約 1.24 萬行 presentation 只有測試在跑；Run Project 走的是手刻的 pygame 腳本。
2. **Runtime 不執行 Event VM**（G-2）：只認得 `START_ENCOUNTER`，對話、開關、轉移都不會發生。
3. **規則寫死在 runtime**（G-3）：技能目標、`"momentum"`、`"stagger_system"`、`"vitality"`、回合順序；有形成第二套 battle rules 的風險。
4. **Engine 平台能力缺口**（G-4）：input、碰撞、音訊播放、fixed step、Transform 階層、Prefab、動畫 state machine。
5. **靜默回歸**（G-5）：`bf4a993` 刪掉了 ModernGL GPU 後端，以及通用的 Actor 外觀、Entity↔Actor 連結和 asset 縮圖。

## 整合風險

- MV 語意越界（已 commit 的 1 處，加上工作樹的 3 處）→ 提案 patch 已備妥，未套用。
- 沒有 CI；打包啟動沒有驗證過；實機層有 6 條流程「路徑不存在」。
- 量測到的熱點：`text()` 每次都建立 font，約 0.64 ms／次，戰鬥影格可能超出預算。

## 建議的 closure 順序

**CB0**（基準／邊界／文件）→ **CB13a**（CI）→ **CB3**（規則回歸資料）→ **CB1**（Event VM）→ **CB2**（Battle Presentation 漸進整合）→ **CB14**（通用 Inspector）→ **CB15**（取消範圍的退役）→ CB4–CB9、CB12 → CB10、CB11。

詳見 REMAINING_WORK_PLAN。

## 需要你批准的事項

| # | 事項 | 我的建議 |
|---|---|---|
| 1 | 是否批准 CB0（含套用 P0-3 提案 patch、MV 衍生美術加 `.gitignore`） | 批准 |
| 2 | CB9：恢復 ModernGL 作為並列後端（不是替換 renderer） | 批准，排在 CB2 之後 |
| 3 | CB14 → CB15 的順序，以及 CB15 的逐項退役清單 | 先 CB14 |
| 4 | `ready_user_hero`：依證據（AI 生成、來源寫 DLC、已搬到 `asteria_hero`、沒有 runtime／editor／demo 依賴）建議在 CB15 正式移除 | 批准移除；這之前不 commit |
| 5 | B 類美術測試改成 Retired（保留失敗紀錄） | 批准 |
| 6 | 「Eventual」需求（System Builder、Plugins、Profiler、部分 Battle）要不要留在 closure 分母裡 | 你決定 |
| 7 | 3 個無法逐字還原的測試函式（DECISION_LOG §0）：要從 Codex log 重建，還是放棄 | 放棄（屬於已取消的範圍） |

## 文件

`SPEC_GAP_AUDIT.md`、`SPEC_TRACEABILITY_MATRIX.md`、`INTEGRATION_VALIDATION_MATRIX.md`、`ARCHITECTURE_PERFORMANCE_RISKS.md`、`REMAINING_WORK_PLAN.md`、`CLOSURE_EXIT_CRITERIA.md`、`DECISION_LOG.md`、`proposed/P0-3_mv_semantics_to_asset_boundary.patch`
