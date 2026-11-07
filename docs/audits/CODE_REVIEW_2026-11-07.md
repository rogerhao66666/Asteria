# 程式碼與檔案分類（2026-11-07，D104）

接續 [`CODE_REVIEW_2026-11-06.md`](CODE_REVIEW_2026-11-06.md)（D103）。D103 只修效能與寫法，沒有動檔案結構；
這次把結構整理完：模組依主題分子套件、大類別拆成 mixin、長函式拆開、重複的程式合併、確認沒人用的刪掉、
文件分成現行與歷史。

**原則（使用者決定）：**
- 確認沒有任何地方用的程式才刪；預留的介面（ABC、Protocol、adapter 基底、可覆寫的 hook）一律保留。
- 套件層級的名字（`asteria.rpg.X` 等）與手冊寫的模組路徑照舊；內部模組直接搬，repo 內所有 import
  （`src`、`tests`、`scripts`、`reference_projects`、`demos`、私人專案的工具）都改成新路徑，不留轉接檔。
- 存檔與專案檔裡的 schema id（例如 `asteria.rpg.gauge_composition`）看起來像模組路徑，但它們是資料格式，
  一律不動。元件的型別名稱是寫死的字串（`asteria.SpriteRenderer2D`），搬模組不影響存好的專案。

## 1. 量到的變化

| 項目 | 之前（`cebe3105`） | 之後 |
|---|---:|---:|
| 模組數 | 628 | 684 |
| 套件數（有 `__init__.py` 的資料夾） | 18 | 54 |
| 平放超過 15 個模組的套件 | 11 個（`editor` 159、`runtime` 96、`rpg` 65、`presentation` 61、`assets` 54…） | 7 個（都在 24 個以下） |
| 超過 1000 行的類別 | 10 | 2 |
| 超過 1500 行的檔案 | 10 | 4 |
| 總行數 | 186,393 | 約 184,600 |

模組變多是因為大檔案拆開了；總行數變少，是因為重複的程式合併、確認沒人用的刪掉了。

## 2. 子套件

完整表在 [`ARCHITECTURE.md`](../ARCHITECTURE.md) §2.1。每個子套件的 `__init__.py` 第一段寫它管什麼。

| 套件 | 子套件 |
|---|---|
| `rpg` | `battle`、`characters`、`data`、`enemies`、`items`、`menus`、`text`、`world` |
| `runtime` | `action`、`battle`、`creature`、`field`、`menus`、`scene`、`session`、`playtest`、`tools` |
| `presentation` | `battle`、`screens`、`text`、`visuals` |
| `assets` | `kinds`、`codecs`、`packages`、`loading`、`rpg_maker_mv` |
| `editor` | `window`、`project`、`records`、`rpg`、`combat`、`events`、`menus`、`animation`、`scene`、`assets`、`tools`、`ui` |

`assets/rpg_maker_mv` 把 MV 相關的八個模組收在一起，`test_architecture_boundaries.py` 的 MV 邊界規則照舊成立。

## 3. 大類別與長函式

| 拆了什麼 | 之前 | 之後 |
|---|---|---|
| `AsteriaEditorWindow` | `editor/shell.py` 3326 行 | `shell.py` 約 600 行（建構與啟動）＋ `editor/window/` 9 個 mixin；`__init__` 從 363 行變 78 行（五個建構函式） |
| 紀錄表單 | `editor/records/form.py` 3684 行 | `form`、`form_shapes`（Qt 無關的資料判斷）、`form_controls`、`form_chips`、`form_tables`、`form_parts` |
| `CreatureBattleScreen` | 2370 行 | `battle_story`、`battle_round`、`battle_menus`、`battle_draw`、`battle_party`；尺寸與顏色在 `battle_style` |
| `CanonicalBattleAdapter` | 1462 行 | `timeline`、`generated_art`、`frame`；共用的在 `presentation_parts` |
| `BattleUiComposer` | 1736 行 | `ui_hud`、`ui_menu`、`ui_feedback`；繪製紀錄類別在 `ui_parts` |
| `CreatureMenuScreen` | 1298 行 | `menu_party`、`menu_bag`、`menu_pages`、`menu_draw`；共用的在 `menu_style` |
| `FieldUiMixin`、`FieldPlayMixin` | 1390、1170 行 | 再拆出 `dialogue_ui`、`field_input`、`field_entities`、`field_sight` |
| `PlayableTestRuntime._frame` | 425 行的 if/elif | 約 110 行；每個畫面一個方法，`frame_modes.SCREEN_FRAMES` 對照 |
| `register_standard_world_commands` | 656 行 | 五個主題函式；註冊結果與 HEAD 逐一比對：84 個指令完全相同 |
| `RpgDatabase` | 每種紀錄各寫一次讀、寫、加入 | `RECORD_KINDS` 表驅動；28 個參考專案的資料庫讀寫來回比對完全相同 |

mixin 之間不互相 import：共用的常數與小函式放在同一個 `*_style`／`*_parts` 模組，類別與 mixin 都從那裡拿。

## 4. 重複與死碼

- 合併：三份相同的 `_spin` → `menus/layout_widget.spin_box`；`_free_id` → 公開的 `free_id`（十個模組在用）；
  跨模組使用的私有函式改成公開名字（例如 `_help_tip` → `help_tip`、`_small` → `hint_label`）。
- 刪除（全 repo 確認沒有使用）：`AuthoringHubWidget`、紀錄表單裡第二份 `FlowLayout`（編輯器用的是
  `ui/flow_layout.py`），以及前幾批找到的只剩定義的函式。
- 保留：所有 ABC、Protocol、adapter 基底與 hook，即使目前只有一個實作。

## 5. 看過但刻意不改的

- **`getattr(self, "x", 預設)`（約 170 處）：** 試過全部換成宣告的屬性，完整測試出現 46 個失敗。原因是存檔還原
  （`BattleRuntime.from_data` 用 `cls.__new__`）與很多測試會在沒跑 `__init__` 的物件上呼叫這些方法，
  預設值是這些路徑要的行為。已經整批還原，保留原寫法。
- **`except …: pass`（66 處）：** 逐一看過，大多有明確的例外型別與註解。範圍最廣的六處（`except Exception`）
  是出錯後盡量回復（rollback）時用的，改成 `contextlib.suppress(Exception)` 並註明「回報第一個錯誤」。
- **還超過 1000 行的類別：** `SceneViewportWidget`（1051 行，編輯器的地圖畫布；一個 Qt 事件處理器，
  拆開要跨 mixin 共用很多狀態）與 `BattleRuntime`（1080 行，回合制核心；存檔還原不跑 `__init__`）。
- **很長但是資料的函式：** `build_skills`（範本的技能表，715 行）、`rpg_categories`、`affixes`
  這類函式本身就是資料表，拆開不會比較好讀。

## 6. 文件

- `docs/` 根目錄的 221 份批次文件（`BATCH*`、`PHASE_*`、`*_CLOSURE_AUDIT*`、`*_v0.1xx.md` 等）搬到
  `docs/history/batches/`，`docs/superpowers/` 搬到 `docs/history/superpowers/`。檔案之間的相對連結一起修正。
- `docs/` 根目錄現在只有現行文件：`README`、`ENGINE_HANDBOOK`、`ARCHITECTURE`、`NATIVE_KERNELS`、
  `STANDALONE_APP`（中英）、`BUILT_IN_TEXT_KEYS`、`NEXT_STEPS`。
- 手冊、引擎手冊、架構文件裡的模組路徑都改成新位置；`DECISION_LOG` 過去的條目維持寫下當時的路徑。

## 7. 驗證

- `ruff check .` 與 `ruff format --check` 通過（每行 ≤ 99 字）。
- 全部 684 個模組在獨立直譯器裡逐一匯入。唯一失敗的是 `templates/action_rpg/lucifer_art.py`：
  它是腳本式模組，要先把自己的資料夾放進 `sys.path`，HEAD 也一樣失敗。
- `scripts/manual_api_list.py --check`（API 章節與程式一致）、`scripts/sync_templates.py --check`、
  `scripts/built_in_text_keys.py`。
- ARPG 範例：HEAD 與現在的 `build_project.py` 產生的 `project.asteria.json` 完全相同。
- 完整測試：3913 passed、1 skipped（依環境略過的那一個，例如沒建原生 kernel 或沒有 GL），12 分 37 秒。

## 8. 順手發現

- `reference_projects/arpg_demo/project.asteria.json` 比它的產生器舊：缺少較新的元件欄位（`stride`、`fit`、
  `walls_cover_characters`）與 `run` 動作。不是這次造成的（HEAD 的產生器輸出一樣），讀檔時會升級；
  要不要重新產生由使用者決定。
- 引擎程式裡還有第三方遊戲的名字：內建字詞的英文預設值（`creature.menu.teach_ask` 的「POKéMON」）、
  manifest 的鍵 `pokenav`、註解裡的 `pokeemerald`。鍵是存好的資料格式，預設字是玩家看得到的字，
  要不要改由使用者決定。
