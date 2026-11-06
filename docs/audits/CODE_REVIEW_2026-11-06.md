# 程式碼審查與整理（2026-11-06）

範圍：`src/asteria` 全部（約 18.5 萬行、634 個模組），七個子系統各自審查（runtime 畫面與 playtest、
runtime session、editor a–l、editor m–z、rpg + gameplay、presentation + graphics + kernels、
core 與周邊 + repo 結構）。效能數字都是實際量的，不是估的。

**原則：** 不刪功能、不改行為（CONTRIBUTING）。所以「只有測試在用的模組」「看起來是死碼的類別」
只列在第 4 節，沒有刪；要不要刪請另開 issue 決定。每個修正都有測試。

## 1. 量到的效能變化

選單畫面（`full_verification_demo`，`trial_ui_tour` 的 95 個畫面，各 60 格，無頭、同一台機器）：

| 畫面 | 之前 | 之後 |
|---|---:|---:|
| 裝備清單 | 70.3 ms | 17.7 ms |
| 裝備 | 41.3 ms | 12.7 ms |
| 狀態 | 40.0 ms | 18.5 ms |
| 狀態頁（專案頁） | 35.3 ms | 20.3 ms |
| 道具 | 24.7 ms | 13.8 ms |
| 任務板（翻面） | 28.1 ms | 9.0 ms |
| **95 個畫面平均幀時間加總** | **1166 ms** | **749 ms（−36%）** |
| p95 超過 16.7 ms（60 fps）的畫面 | 18 個 | 7 個 |

匯入時間（`python -X importtime`，冷啟動）：

| 匯入 | 之前 | 之後 |
|---|---:|---:|
| `asteria.assets` | 518 ms | < 1 ms |
| `asteria.platform` | 551 ms | 40 ms |
| `asteria.runtime.collision` | 632 ms | 28 ms |
| `asteria.project` | 580 ms | 273 ms |
| `from asteria.editor import EditorDocument` | 609 ms，載入整個 Qt | 不載入 Qt |

## 2. 做了什麼

### 效能

- **選單一幀只解析一次角色組成。** `menu_fit()` 在 `GameSessionRuntime.reading_builds()` 裡畫：畫畫面
  只讀存檔，所以同一幀裡每個角色的 build、`stat_breakdown`、狀態頁的 `view()`/`rows()` 各算一次
  （之前狀態頁一幀解析 8 次 build，`stat_breakdown` 每次又解析 3 次）。離開範圍就忘掉，裝備、配點後
  下一幀就看得到。
- **`resolve_actor_build` 本身：** 成長軌與配點的貢獻只算一次（`RpgActorRuntime.build_layers`），
  之前同一次解析裡算 5 次；有效標籤也只算一次。`progression_graph.contribution` 只走已點的等級，
  能力與被動技用有序 dict（之前是 list 線性搜尋）。`normalize_tag` 用 `str.split()` 判斷空白（對全部
  110 萬個 Unicode 碼位驗證過結果相同）。
- **文字：** `contains_cjk` 改成 ASCII 快速路徑加一個預先編譯的字元類別（之前每個字元一個 generator
  掃 15 個範圍）；系統中文字型以「檔案 + 大小」快取；`text_size` 有快取，而且用 `text()` 實際畫的字型
  量（之前忽略字型資產，量出來的寬度可能和畫出來的不同）；主題的中文字型路徑每個主題查一次，不是
  每行字查一次磁碟。
- **面板與遮罩：** 皮膚圖片跟圖示一起快取（之前每次都 new 一個 subsurface，讓九宮格面板的快取永遠
  打不中）。八處每幀 new 一張全螢幕半透明 Surface 的地方改成共用的 `shade()` / `dim_screen()`。
- **匯入：** `presentation`、`runtime`、`rpg`、`assets`、`editor` 的 `__init__` 改成用到才匯入
  （PEP 562 `__getattr__`），對外的名字和以前完全相同（產生時逐一驗證是同一個物件）。這也拆掉了
  `assets → presentation → runtime → reference_data → assets` 的匯入循環：以前第一個匯入
  `asteria.reference_data` 會直接失敗。`assets` 的 MV 介面改成精確的名字對應：以前問任何不存在的
  名字（連 `hasattr`）都會把三個 MV 模組全載進來，違反 AST-13。
- **函式內的 import：** 554 個提到檔案頂端（PySide6 會換掉 `builtins.__import__`，之後每個函式內
  import 要多走四層 Python 呼叫：87 ns 變 890 ns，畫面每幀都在付）。只提升證明安全的：標準庫；
  asteria 模組要在匯入圖上不形成循環；editor 裡還要求本來就已經載入（啟動不變慢）。可選依賴
  （pygame、Qt、numpy、PIL）、web 匯出不帶的套件（multiplayer、editor）和 `sys.path` 設好之後才能
  匯入的都留在原地。
- **編輯器：** 圖塊盤的圖檔只在檔案改了才重新解碼（每次 `refresh_all` 都重讀並逐格掃透明）；
  貼圖每次重畫每張只找一次，找不到的不會每格都再找一次；`translate()` 記住結果（包含沒翻到的字，
  之前每次都跑 103 條 regex），換語言或換專案時清掉；事件實體清單和選單元素清單從 O(n²) 改成一次
  `Counter`。

### 寫法

- 30 個 mixin 的 `from .support import (...)  # noqa: F401` 共 194 個沒用到的 import 刪掉。
- `self.__dict__.setdefault(...)` / `__dict__.get(...)` 造出來的屬性（runtime 約 40 處）改成在
  `PlayableTestRuntime._init_caches()`、各類別的 `__init__` 或類別預設值裡宣告，每個都有註解寫它
  存什麼。測試裡用 `__new__` 建 runtime 的地方改呼叫 `_init_caches()`。
- 重複的驗證函式：`_id`（43 份）、`_finite`（9 份）、`_text`（13 份）合併成
  `asteria/core/values.py` 的 `required_id`、`finite`、`clean_text`。
- `_EitherBlocks`（和 `CombinedQuery` 一樣）、`_ability_state_of`（和 `_ability_state` 一樣）刪掉重複。
- `runtime/session/messages.py` 的方法和匯入的函式同名（`def name_of(...): return name_of(...)`），
  改成 `data_text.name_of(...)`。
- 一般名字匯入到模組層時取清楚的別名（`key` → `data_key`）。
- 執行階段和驗證程式不再為了元件登錄建一個 `EditorDocument()`（會把 Qt 整個載入）：
  `EditorDocument().component_registry` 全部改成 `default_component_registry()`（使用手冊同步更新）。
- 編輯器開專案的四條路（設定、開檔、範本、MV 匯入）合成 `_show_new_project()`，「有未儲存的變更」
  的對話框合成 `_confirm_discard()`。

## 3. 順手修掉的錯誤

| 錯誤 | 修正 |
|---|---|
| 選單文字裡的 `{map.name}` 永遠是空的（讀了 runtime 沒有的 `scene`） | 讀 `game.scene` |
| 狀態頁背後的地圖被縮小畫在左上角（自己複製了一份背景，沒用 `window_drawing()`） | 用共用的 `_draw_backdrop` |
| 多人連線時 `resolve_actor_build` 的包裝丟掉 `apply_slots`，技能欄位候選會 `TypeError` | 包裝保留原本的參數 |
| 遊戲系統的復原紀錄用 `label[:-1]` 當單數：「Add Music Roo」「Delete Pet Rules (creature party」 | `_Kind.noun` |
| 先 `translate()` 再 `setText()`：切回英文時那些字還是中文（實測重現） | 48 處改成直接給英文；加測試防止再出現 |
| `DialogueWindowDialog` 覆寫了 Qt 的 `style()`、`window`、`font`，對它呼叫 `style().polish()` 會壞 | 改名 `chosen_style()`、`window_field`、`font_box` |
| 開檔、從範本建立、MV 匯入時，舊專案的試玩程式不會被停掉（變成孤兒），程式頁還留著舊專案的腳本 | 統一走 `_show_new_project()` |

## 4. 審查發現、這次沒有動的（建議另開 issue）

這些要嘛會改行為，要嘛會刪功能、搬大量檔案，照 CONTRIBUTING 應該先討論。

**可能是死碼（只有測試在用或完全沒人用）：**
- `render/`：只有 `ShadowCaster2D`、`PostEffect2D` 有人用（`runtime/environment2d.py`），其餘只有
  `tests/test_render_foundation.py` 用。建議把這兩個移到 `graphics/`、刪掉其他。
- `presentation/` 的通用框架：`bridge`、`workspace`、`visual_authoring`、`visual_editing` 沒有測試以外的使用者。
- `assets/` 16 個模組（約 1300 行）只有 `tests/test_batch5x/6x.py` 用；`importers.py` 連測試都沒用。
- editor：`AuthoringHubWidget`（沒人用）、`StructuredRecordEditor`、五個 `rpg_*_workspace.py` 模型、
  `scene_entity_authoring.py`、`runtime_state_integration.py`、`ProjectWorkspaceController`（建了沒用）、
  `record_form.FlowLayout`（和 `flow_layout.py` 重複）。
- session：`attach_equipment`、`restore_pet_uses`、`change_pet_affinity`。

**架構（大工程，建議分批）：**
- `GameSessionRuntime` 由 19 個 mixin 組成、`PlayableTestRuntime` 16 個，實際上是共用 `self` 的單一
  大類別（`encounters`、`field_play` 各自呼叫其他 10 個 mixin）。建議依序拆出 `BuildService`、
  `TextRenderer`、`MenuBackdrop`、畫面模式表（取代 `_frame` 430 行的 if/elif）、`NetworkSession`。
- 文字繪製有 4 套以上（`pygame_battle_ui`、`text_draw`、`pygame_backend`、`moderngl_backend`、
  `creature_battle`），面板繪製 4 套，各有各的快取；建議合成一個 `platform/text_renderer.py`。
- 編輯器每次小編輯都 `refresh_all()`（`shell.py` 呼叫 40 次），重建專案樹、資產清單、檢視器；建議
  改成依變更種類發訊號。專案樹每次重建也會讓展開的節點收起來。
- 表單引擎有三套（`record_form.RecordForm`、`game_systems_widget.RecordForm`（同名！）、
  `combat_workspace._build_form`）；數字框、顏色按鈕、自動套用計時器各複製了 3–5 份。
- `shell.py`（3.4k 行）、`record_form.py`（3.7k 行）、`game_systems_authoring.py`（2.7k 行，多半是資料）
  建議拆檔；審查報告裡有逐檔的拆法。
- `rpg/actors.py` 同時是角色定義、角色執行期和整個資料庫（`RpgDatabase` 約 1450 行、70 個手寫的
  `add_*`）。`rpg/`、`runtime/`（135 個檔案）、`editor/`（159 個檔案）都是平的，建議分子套件
  （留舊路徑的轉接模組一個版本）。
- presentation 反過來依賴 runtime（`battle_runtime` 匯入 `asteria.runtime`），12 個 runtime 模組又匯入
  presentation；建議把 `Camera2D`、`AnimatorState`、`TextureDraw` 移到 `graphics/`。

**會改變畫面的：**
- 選單背後的地圖每幀重畫（約 3–4 ms）。地圖在選單下其實是凍結的，可以做成快照；但動態圖塊、彈出字
  會停在開選單那一刻，所以沒有做。

**倉庫：**
- `validation/`（5.2k 行）只給測試和腳本用，卻跟著套件安裝；桌面匯出 `_copy_engine` 把整個
  `src/asteria`（含 editor 2.8 MB、templates 6.9 MB）複製進每個遊戲，web 匯出則有排除。
- `reference_projects/arpg_multiplayer_demo` 是 `arpg_demo` 的手動副本（5 個一樣的 .py、2.9 MB 圖），
  只有一個測試在確認兩邊一樣。
- `docs/` 頂層 200 個 `BATCH*.md`、`docs/audits` 141 MB 的截圖、`tests/` 493 個平放的檔案（30 個叫
  `test_batchNN.py`）。

## 5. 驗證

- 全部測試：之前 3893 passed、53 skipped；之後見提交訊息（新增 14 個測試）。
- `ruff check`、`ruff format --check` 通過；`scripts/sync_templates.py --check` 通過。
- 每個模組各自在新的直譯器裡匯入一次（找匯入循環）：624 個全部成功（之前 `asteria.reference_data`
  失敗）。
- 為了確保提升 import 沒有改變語意，另外比對了：函式裡同名區域變數造成的 `UnboundLocalError`
  （找到並修了 2 處）、web 匯出不帶的套件、`sys.path` 設定之後才能匯入的情況。
