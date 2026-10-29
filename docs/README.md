# Asteria 文件索引

這個資料夾同時放著**現行文件**（描述目前的引擎）和**歷史紀錄**（開發過程中每一批的稽核與計畫）。
歷史紀錄保留原貌，裡面的版本號、測試數字和「目前狀態」只代表寫下當時，不代表現在。

*English: the documents under "現行文件" describe Asteria as it is now; everything listed under
"歷史紀錄" is kept as it was written and may describe older versions.*

## 現行文件

| 文件 | 給誰 | 內容 |
| --- | --- | --- |
| [`manual/USER_MANUAL.zh-TW.md`](manual/USER_MANUAL.zh-TW.md)／[`manual/USER_MANUAL.en.md`](manual/USER_MANUAL.en.md) | 遊戲作者 | 從安裝到匯出的操作手冊，附真實截圖；最後一章是 Python API |
| [`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md) | 引擎開發者 | 安裝、目錄、每個系統怎麼運作、範本、資料格式、測試、已知限制（**從這裡開始**） |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 引擎開發者 | 套件分層、資料從專案檔到畫面的流程、執行環境的組成 |
| [`NATIVE_KERNELS.md`](NATIVE_KERNELS.md) | 引擎開發者 | python／numpy／C++ 三組計算核心與 ABI |
| [`STANDALONE_APP.zh-TW.md`](STANDALONE_APP.zh-TW.md)／[`STANDALONE_APP.md`](STANDALONE_APP.md) | 使用者、維護者 | 不需要 Python 的免安裝版 app：使用與打包 |
| [`BUILT_IN_TEXT_KEYS.md`](BUILT_IN_TEXT_KEYS.md) | 遊戲作者、翻譯 | 遊戲畫面上每一個內建字詞的 key（由 `scripts/built_in_text_keys.py` 產生） |
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | 維護者 | 在本機接續工作的步驟、還沒做的事、已經決定的事 |
| [`templates/`](templates/) | 遊戲作者 | 兩個套件內範本的 `START_HERE.md` 原稿（`scripts/sync_templates.py` 會複製進套件） |
| [`spec/ASTERIA_SPEC.md`](spec/ASTERIA_SPEC.md) | 引擎開發者 | 產品與功能規格：設計目標與原則 |
| [`spec/ASTERIA_ASSET_SPEC.md`](spec/ASTERIA_ASSET_SPEC.md)、[`spec/ASTERIA_ASSET_PIPELINE.md`](spec/ASTERIA_ASSET_PIPELINE.md) | 引擎開發者 | 素材格式與匯入管線的規格 |
| [`spec/ASTERIA_ART_DIRECTION.md`](spec/ASTERIA_ART_DIRECTION.md) | 美術、引擎開發者 | 美術方向與素材規範 |
| [`audits/DECISION_LOG.md`](audits/DECISION_LOG.md) | 所有人 | 每個設計決策（D1 起）的要求、原因、做法、驗證與狀態 |
| [`audits/GAP_LIST.md`](audits/GAP_LIST.md) | 維護者 | 規格對照實作的缺口清單 |
| [`audits/MULTIPLAYER_DESIGN.md`](audits/MULTIPLAYER_DESIGN.md) | 引擎開發者 | 多人連線的設計與限制 |

`spec/` 寫的是設計目標；某個功能現在做到哪裡，以手冊、引擎手冊和 DECISION_LOG 為準。

## 歷史紀錄（保留原貌，不再更新）

| 位置 | 內容 |
| --- | --- |
| `docs/` 根目錄的 `BATCH*`、`PHASE_*`、`*_CLOSURE_AUDIT*`、`*_v0.1xx.md` | v0.93～v0.159 各批次的設計與結案稽核 |
| [`CANONICAL_SPEC.md`](CANONICAL_SPEC.md)、[`CONSISTENCY_AUDIT.md`](CONSISTENCY_AUDIT.md)、[`NEXT_PHASE_PLAN.md`](NEXT_PHASE_PLAN.md)、[`MAC_FIRST_RUN_TEST.md`](MAC_FIRST_RUN_TEST.md) | v0.94～v0.112 時期的「目前狀態」文件 |
| [`history/`](history/) | 進度筆記、交接文件、舊版的稽核與審查、`ARCHITECTURE_BATCH94-119.md`（舊的架構筆記） |
| [`audits/`](audits/) 裡其餘的檔案 | 2026-10 的缺口稽核、素材搜尋、UI 計畫與實機證據（`evidence/`） |
| [`superpowers/`](superpowers/) | 個別功能當時的設計稿與執行計畫（其中角色產生器已取消） |
