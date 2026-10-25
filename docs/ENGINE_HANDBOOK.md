# Asteria 引擎手冊（功能、範本、demo、規則、下一步）

**更新：** 2026-10-22（D51；D42–D51 的內容看 DECISION_LOG，缺口對照表見 [`audits/GAP_LIST.md`](audits/GAP_LIST.md)）。這份是「目前到底有什麼」的單一入口；細節和決策理由在
[`docs/audits/DECISION_LOG.md`](audits/DECISION_LOG.md)（D1 ～ D51），規格在
[`ASTERIA_SPEC.md`](../ASTERIA_SPEC.md)。舊的 `README.md`、`START_HERE_MAC.md`、各 BATCH 文件是歷史紀錄，
不代表現狀。

---

## 0. 一句話

Python 寫的 2D RPG 引擎加編輯器：**資料驅動、系統通用**（回合制和即時動作都能做，Octopath 和 Diablo 只是
兩個範例專案），**使用者用資料或 Python 程式碼都能擴充**，熱迴圈用 C++ kernel 加速。

三條原則（使用者定的，之後的工作都要遵守）：

1. **不限制作者**：不寫死遊戲規則。有歧義的規則做成編輯器能改的選項；demo 的設定只是範例。
2. **系統通用**：Diablo、八方旅人是範例資料，引擎裡沒有它們的程式碼。
3. **沒有證據不說完成**：功能要有測試；畫面和視窗要在真實 Cocoa 視窗驗證。

---

## 1. 安裝與常用指令

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[pygame,editor,mv,dev]"

.venv/bin/asteria-editor                       # 編輯器（File > New from Template… 從範本開新專案）
.venv/bin/asteria-preview PROJECT.json         # 直接玩專案
.venv/bin/python -m pytest -q                  # 全部測試（約 3,100 項，約 5 分鐘）
.venv/bin/python -m asteria.kernels.build_native   # 編譯 C++ kernel（開發機一次；ABI 改了要重編）
.venv/bin/python -m asteria.export_web PROJECT.json OUT --serve   # 瀏覽器版（D59；需要 pip install pygbag）
```

提交前（專案規則）：

```bash
.venv/bin/ruff format .
.venv/bin/ruff check --select E501 .                       # 每行 ≤ 99 字元
.venv/bin/ruff check src tests scripts demos reference_projects
```

重新產生兩個 demo 專案（需要 git-ignored 的 `local_reference/` 美術來源）：

```bash
.venv/bin/python reference_projects/octopath_demo/build_project.py
.venv/bin/python reference_projects/diablo_demo/build_project.py
```

---

## 2. 目錄

| 路徑 | 內容 |
| --- | --- |
| `src/asteria/core` | ECS：Entity／Component／Scene／System、欄位陣列存放（`array.array` 欄位）、prefab、序列化、遷移 |
| `src/asteria/kernels` | 計算核心：`python`（基準）／`numpy`／`native`（C++ via ctypes）三組，結果逐位元相同 |
| `src/asteria/events` | 事件程式（VM、排程、對話、世界指令、綁定） |
| `src/asteria/gameplay` | 數值、資源、公式、標籤、效果、狀態、技能（Ability）、攻擊、投射物、動作時間軸 |
| `src/asteria/rpg` | 角色、職業、技能樹、裝備與詞綴與套裝、掉落、任務、經濟、回合制戰鬥核心、捕獲、調合 |
| `src/asteria/runtime` | 可玩的執行環境：場景、地圖、角色控制、碰撞、即時戰鬥（`action_*`）、遊戲選單、存檔、HUD |
| `src/asteria/multiplayer` | 通用多人連線原型：TCP session/lobby、client API、遊戲 adapter、命令／狀態／事件、即時輸入同步與合作 Boss 範例 |
| `src/asteria/presentation` | 回合制戰鬥呈現：動畫、特效、HUD、選單、鏡頭、角色／隊伍／裝備／技能畫面 |
| `src/asteria/graphics`、`render`、`platform` | 精靈、地圖、光照、後製；pygame 與 ModernGL 兩種後端 |
| `src/asteria/assets` | 素材管線：匯入、圖集、自動修正、品質門檻、RPG Maker MV 匯入 |
| `src/asteria/editor` | PySide6 編輯器（約 100 個模組） |
| `src/asteria/validation` | 壓力測試與實驗場景 |
| `reference_projects/` | `octopath_demo`、`diablo_demo` 以及其他參考專案 |
| `tests/` | 全部測試 |
| `scripts/` | 實機驗證、編輯器稽核、量測腳本 |
| `docs/audits/` | 決策紀錄、稽核、實機證據（`evidence/`） |

---

## 3. 引擎功能

### 3.1 核心與效能

- ECS，欄位用 `array.array` 欄位存放（`'d'`／`'q'`／`'b'`），系統直接讀寫欄位。
- **kernel**（`docs/NATIVE_KERNELS.md`）：廣域碰撞、牆擋移動（`blocked_boxes`）、投射物、粒子、天氣、角色移動、
  場景 AI（沒有角色控制器的怪一次走完：`fieldai_free_step`、`points_blocked`）；`ASTERIA_KERNELS=
  native|numpy|python`，預設取最快可用的；沒編譯 C++ 也不會壞（退回 numpy／python）。C++ 版不需要 numpy
  （緩衝區用 `array.array`），macOS 編成 arm64＋x86_64、最低 macOS 11；ABI 5；匯出一定帶著通過檢查的程式庫。
- 量測（2026-10-20 起不開 tracemalloc；之前的數字被 heap 追蹤放大）：300 隻敵人 + 500 顆投射物每幀約
  native 1.8／numpy 2.4／python 3.1 ms；640×640 的大地圖 < 0.5 秒載入（區塊懶惰繪製，只付鏡頭看得到的）；
  真實視窗 60 fps。
- 同樣的東西只做一次（D48）：九宮格面板、HUD 文字、戰場背景的縮放、戰鬥角色每一格的縮放與可見範圍、
  戰鬥 UI 面板都有快取；HUD 與指令列只在內容變了才重排；場上的碰撞世界跟著場景就地更新
  （`CollisionWorld.follow`，做不到完全一致就重建）。
- 下一場戰鬥的圖在場上就先解碼（只在真實視窗；manifest `battle.preload_mb`，預設 64，0 關閉），開戰那一幀
  10–18 ms；換音樂不會因為淡出而凍住。

### 3.2 玩法資料（`gameplay`）

- 數值、資源、標籤、公式（可編輯）、效果、**狀態**（持續時間、疊層、週期效果、`display_name`、`icon_id`）。
- **技能** `AbilityDefinition`：目標規則、消耗（`costs`）、條件（`conditions`，例如要裝備某武器）、效果；
  回合制擴充：`cooldown_turns`、`battle_costs`（加速點）、`hits`（多段，每段自帶武器／屬性標籤和倍率）、
  `battle_resource_gains`、`commands`（世界指令，例如召喚）、`concoct_station`（調合）、`apply_states`；
  即時：`timeline_id`、`cooldown_seconds`、`move_while_acting`、`interrupts_actions`；顯示：`display_name`、
  `icon_id`；**`requires_items`**（需要持有的道具，不消耗）、**`requires_pet`**（需要持有並派出寵物，
  公式讀 `pet_<stat>`、`pet_level`）。
- 動作時間軸（cue：動畫、位移、判定框、無敵、取消窗口、連段、VFX、音效、鏡頭、`apply_state`）。

### 3.3 RPG 系統（`rpg`）

職業與副職、技能樹（等級上限、花費、前置、互斥）、裝備（欄位、鑲嵌、套裝、成長、隨機詞綴、可自訂稀有度）、
掉落表、任務、商店、聲望、成就、**寵物**（`rpg/pets.py`：物種＝基礎數值與每級成長、經驗曲線；持有的寵物＝
物種、暱稱、等級、經驗，存在存檔；派出參戰後贏得戰鬥會得到經驗並升級；暫停選單的 Pets 畫面可選擇出戰
寵物與改名）、**捕獲**（`CaptureRule`：加入隊伍、變成寵物道具，或成為持有的寵物並指定起始等級）、**調合**
（配方＋站點）、
回合制戰鬥核心（排程、弱點與護盾與破防、加速點、狀態政策、反射與吸收、多階段 Boss、召喚）。

### 3.4 即時戰鬥（`runtime/action_*`）

- 俯視和橫向兩種視角，戰鬥核心共用；攻擊判定（無敵幀、擊退、硬直）、連段、閃避、鎖定、冷卻與消耗
  （含 `item:<id>` 消耗）、投射物（含穿透、精靈）、敵人 AI（行為樹）、橫向手感（郊狼時間、跳躍緩衝、斜坡、
  梯子、單向平台）。
- 綁定可寫替代 `a|b|c`（取第一個學會的），`SET_CLASSES` 世界指令轉職，`defeat_switch` 讓被擊敗的 Boss
  存檔後仍倒下。
- 場景：`TileSceneView`（分層、方向動畫、鏡頭跟隨與前瞻、視差背景 `ParallaxBackground2D`、職業外觀
  `ClassAppearance`、區塊懶惰繪製）。

### 3.5 即時戰鬥的畫面（HUD）

- **底部 HUD**（`runtime/hud_bottom.py`）：左紅右藍的資源球（依資源名稱選色；護盾是淺藍條）、快捷列
  （鍵帽從專案輸入表讀、技能圖示、**冷卻時鐘：變暗後亮扇形順時針轉一圈，轉滿閃一下**、魔力不足變暗、
  道具數量方塊徽章在右下、資源消耗在左下用資源色小圓珠加數字）、狀態列（圖示或縮寫、增益綠框／減益紅框、
  剩餘時間遮罩與秒數、疊層徽章）、經驗條、淡出的操作提示。
- 敵人頭上：血條（受傷或被鎖定才顯示）上方一排狀態小方格；鎖定（L）時畫面上方有目標框：名稱、血條、
  每個狀態的名稱與剩餘秒數。
- 背包畫面（格子、裝備比較提示、套裝加成）、技能樹畫面。

### 3.6 編輯器（`asteria-editor`）

工作區：**Scene、Database（RPG）、Battle、Presentation（UI）、Events、Code、Multiplayer**；面板：Project／Tiles／Layers、
Inspector、Assets／Console／Debugger／Profiler／Problems。重點：

- **File > New from Template…（Ctrl+N）**：Full Verification（推薦：完整的遊戲，也是編輯器預設開的起始專案）、
  Basic RPG（小）、Party RPG（八方旅人式）、Action RPG（暗黑式）、Completely Empty；複製整個專案資料夾
  （含美術與授權文件）後改名開啟，Console 會顯示專案裡的 `START_HERE.md`（每個規則在編輯器哪裡改）。
  Party 與 Action 範本隨套件發布（`src/asteria/templates/`），改了 demo 之後執行 `scripts/sync_templates.py`，
  測試會檢查兩邊一致；Full Verification 與 Basic RPG 從原始碼裡的 `reference_projects/` 複製。
- **紀錄表單（`editor/record_form.py`，2026-10-19）**：Game Data、Battle Rules、Battle Screen、Runtime UI
  的每一筆紀錄不再是 Field／Value 樹，而是表單：名稱與圖示在上方，ID 固定顯示；數字框（機率以 %
  顯示）、開關、**下拉選單挑參照**（技能、狀態、職業、物品、資源、能力值…附圖示，從專案讀出，
  `record_vocabulary.py`）、標籤用 chips（附專案內所有標籤的建議）、能力值表（兩欄、能力值從清單選）、
  多筆資料用卡片（新增／複製／上下移／刪除，新卡片的內部 id 自動編號）、巢狀部分各成區塊；固定值欄位
  （stacking、selection_mode…）從引擎的檢查自動讀出選項（`engine_enums()`）；空的選填欄位收在
  「Show N more fields」／「More fields」；內部欄位收在 Advanced。每個欄位有說明（ⓘ 與灰字）。
  **改了就套用**（停止輸入 0.35 秒後經可復原指令套用，Ctrl+Z 復原），錯誤以紅字顯示且不套用；
  左側清單顯示名稱與圖示，篩選也找名稱。Game Systems 與 Game Start 也改為自動套用、鍵值從清單選。
- **介面語言**（D50）：English（預設）／繁體中文，View ▸ Language 即時切換，記在 QSettings `editor/language`
  （`editor/i18n.py`、`editor/translations/zh_TW.json`）；只翻介面文字，名稱、id、描述等作者的資料不翻。
- **畫地圖**（D42）：Tiles 面板顯示整張圖塊集，點一格或拖曳選一塊來畫（整塊無縫重複）；筆刷大小 `[`／`]`、
  右鍵從地圖吸取、B／G／R／E／S 切換工具；按住時就畫在地圖上，放開算一步復原。
- **素材庫**（D44）：File > Import from Asset Library… 從 `asset_library/`（CC0 的 Foozle 包與弓）挑圖匯入
  專案，顯示授權，一步復原。
- **技能樹**：Game Data > Skill Trees 先顯示圖（圖示卡片加箭頭，可存版面），表單到切到資料檢視才建（D46）。
- 場景視圖的攻擊／受擊框預設不畫，View > Show Hit & Hurt Boxes 才畫（D43）。
- **Inspector**：選取實體即顯示全部元件，每個元件一個區塊（數字兩兩並排、下拉、開關），可直接改名與開關。
- Real-Time Combat 工作區（攻擊、投射物、稀有度、詞綴，即時預覽與判定框疊圖）；Enemy AI；技能與狀態
  可編輯 `display_name`、`icon_id`（圖示挑選）；Capture Rules 可設 `Joins As Actor`、`Becomes Pet Item`。
- 窄視窗：最小視窗 1000×640；預覽在窄頁自動收起；表格欄寬與下拉選單依內容。
- 稽核腳本 `scripts/editor_ui_audit.py` 逐工作區截圖並找：文字被截斷、溢出、過小控制項、停靠面板的分頁掉出
  分頁列。2026-10-22 在 Full Verification 專案（56 頁，英文與中文，1600×1000 與 1100×700）：每次被截的文字
  0–1 處（Map Rule Sets 的圖片路徑、窄視窗 Battle 頁的一個選項；見 DECISION_LOG D51）。
- Code 工作區：寫 Python 腳本直接操作專案，有自動完成。
- Multiplayer 工作區：本機 server、Guest ID、SQLite、專案規則模板及獨立 Diablo 多人副本。副本使用 project-backed adapter 同步原 ECS 戰鬥、技能、怪物、NPC、商店、製作、背包、裝備與角色存檔；四人 Cocoa 驗收通過。Boss 有正傷害者各得完整 100 XP，每項原掉落隨機保留給一位參與者。使用方式見 [遊戲模板](audits/MULTIPLAYER_GAMEPLAY_TEMPLATE.md)。
- Scene 視圖操作：**滑鼠滾輪以游標為中心縮放**（一格 ×1.15）；方向鍵平移視圖（有選取實體時改為移動實體，
  Shift 加大步距）；**觸控板**雙指捲動平移、捏合縮放（維持原樣）。

### 3.7 遊戲內建字的翻譯（D52）

- **遊戲自己畫的字都能翻、也能改名**：標題、野外提示、對話提示、暫停／設定／按鍵設定／存檔／狀態／
  任務／商店／製作／成就／圖鑑／訊息紀錄／音樂室／製作人員／技能欄／寵物選單、背包與技能樹（動作遊戲）、
  動作 HUD、戰鬥指令與提示、指令不能用的原因、破防與捕獲、勝利結算與標題、遊戲結束、連線合作的訊息。
  畫的時候都經過 `GameSessionRuntime.tr(鍵, 英文)`。
- **鍵的清單**：`src/asteria/rpg/built_in_text.py`（`GROUPS`：337 個鍵、依畫面分 27 組，每個鍵附畫出的英文），
  逐條列在 [`BUILT_IN_TEXT_KEYS.md`](BUILT_IN_TEXT_KEYS.md)（`scripts/built_in_text_keys.py` 產生）。
  `tests/test_built_in_text.py` 掃描原始碼：畫面用到的每個鍵都在清單裡、英文一致，清單裡的鍵都有畫面在用。
- **翻譯表**：Database ▸ Game Systems ▸ Translations。每個 locale 一張表，頁面列出全部內建字（英文在旁邊），
  可搜尋、只看未翻譯；文字留空就用英文（輸入一個空白可隱藏那個字）。表在它是 Message Settings 的
  Default Locale、或玩家在 設定 ▸ 語言 選了它時使用（有兩個以上 locale 才出現語言選項）。
  在預設語系的表裡寫英文就是改名，例如 en 表 `battle.command.attack` = `Fight`。
- **沒有翻譯表的專案畫面完全不變**：新舊引擎各畫 12 個畫面（標題、野外、暫停、設定、任務、成就、圖鑑、
  遊戲結束、存檔、狀態、戰鬥指令、技能清單），Octopath、Complex Reference（沒有表）與英文的 Full
  Verification 共 36 張逐像素相同。
- **引擎附的繁體中文**：`rpg/built_in_text/zh-TW.json`（每個鍵都有，`{...}` 與英文一致）。Translations 頁的
  「填入空白列」把它填進 zh-TW 表（專案名稱剛好是內建字的，例如指令頁的「Skills」，也一起填）。
- **專案自己的名稱也能翻**（頁面依專案列出，沒寫就照專案寫的顯示）：`battle.layer.<指令 id>`（Command
  Menu Pages 的名稱，例如 Fight）、`battle.group.<分組>`（技能的 `menu_category`）、`pause.entry.<id>`
  （暫停選單自訂項目）、`controls.action.<動作 id>`（按鍵設定畫面的動作名稱）。
- **規則拒絕的訊息**（買不起、庫存不夠、背包放不下）用 `Words` 帶著鍵丟出：`str(錯誤)` 還是英文，商店畫面用
  `translated(錯誤, game.tr)` 顯示譯文。
- **中文排版**：戰鬥版面用 `presentation/text_cells.py` 算寬度：中日韓全形字算 2 格，ASCII 長度不變
  （所以英文版面和以前一樣）；技能說明在字與字之間換行、句讀不放行首。中文用系統的 CJK 字型畫
  （macOS 的 STHeiti）：戰鬥畫面的字級等於 UI 字型實際的 em（`point_size`，含 skin 的 `font_scale`），
  選單等主畫面是英文字型行高的 1.25 倍（以前同字級時中文大了約 45%）；並且垂直置中在英文大寫字母的
  中線（`glyph_shift`），選單游標和中文標籤同高；置中的標題與提示不超出英文那一行的上緣。skin 字型本身有
  中文字時直接用它。
- **專案資料也能翻（D60）**：同一張表裡寫 `data.<種類>.<id>.name`／`.description`（種類由紀錄類別決定，見 `rpg/data_text.py` 的 `KINDS`）、`data.map.<場景 id>.name`、`data.speaker.<名字>.name`、`data.currency.<id>.name`；對話與選項用選填的 `text_key`（選項提示 `prompt_key`）。畫面一律經 `game.name_of(record)`／`description_of`／`line_text`，沒寫就照紀錄自己的字。
- **Full Verification（D60 T3）**：資料的繁中由 `trial_zh_data.py`（詞彙表 `trial_zh_words.py` 加句型）在建置時產生，1,923 列全有；真實視窗證據 `audits/evidence/data_translation/`（`scripts/data_translation_live_check.py`）。
- **編輯器（D60 T2）**：Translations 頁在引擎字詞之後列出專案資料（每種紀錄一組，加上地圖、貨幣、說話者、台詞；預設收合、搜尋時展開；「顯示 ▸ 專案資料」）；「替對話產生鍵」一次替所有沒有鍵的台詞、選項與提示加上 `dlg.*` 鍵（可復原）。
- **還不能翻的**：（D60 之前）專案資料的名稱和說明照作者寫的顯示；
  開發用的錯誤訊息（`unknown …`、資料設定錯誤）維持英文。細節見 DECISION_LOG D52。

---

## 4. 範本專案

### 4.1 Octopath 式回合制（`reference_projects/octopath_demo`）

四位旅人：Garrick（Warrior／Merchant，劍＋矛）、Sera（Hunter／Thief，弓＋短劍）、Bram（Apothecary／Cleric，
斧＋杖）、Ione（Scholar／Dancer，杖＋短劍）。

| 功能 | 怎麼運作（資料位置） |
| --- | --- |
| 弱點、護盾、破防 | 每種敵人自己的護盾數和弱點；弱點命中扣 1 護盾，歸零破防（失去回合、承受 2 倍傷害）；弱點打中前顯示 `?` |
| 加速（Boost） | 左右鍵調加速等級，每回合 +1 點；攻擊多打幾下，法術變強（`boost.repeat`／`boost.power` 標籤） |
| 奧義（Divine） | 花 3 加速點（`battle_costs`）：Brand of Valor、Arrowstorm、Last Stand、Elemental Storm；不夠時選單顯示「Needs 3 bp」 |
| 多武器 | 裝備的每把武器各給一個普通攻擊（拿下劍就沒有 Attack (Sword)）；Twin Fang 要同時裝備劍和矛 |
| 多段技能 | `hits`：每段各自帶武器或屬性；Brand of Valor（劍矛劍矛雷）、Arrowstorm（五箭＋冰）、Grand Inferno（一發火球打三下）、Elemental Barrage（火冰雷）、Thousand Spears（四下矛）、Amputation（兩下斧） |
| 主副職業 | 每人兩個職業，副職技能戰鬥中可用 |
| **寵物（寶可夢式，不是單位）** | Sera 一開始有 Frosty（Frost Lynx，Lv3）；`send_frost_lynx` 的 `requires_pet` 需要對應的寵物，傷害讀 `pet_power`（等級越高越痛），沒有就灰掉並顯示「Needs Frost Lynx」；參戰後贏得戰鬥得經驗升級；捕獲 Ember Hound 得到持有的 Lv2 寵物並解鎖 `send_ember_hound`；暫停選單 Pets 畫面可選出戰寵物與改名 |
| 調合 | Bram 的 Concoct：從背包選底材和觸媒，四種配方（Fire Bomb／Frost Bomb 打全體、Healing Salve 補一人、Storm Flask 打一人並降防禦），產物立即生效 |
| 給予加速點 | Garrick 的 Donate BP |
| 狀態 | 毒（每回合更痛）、睡眠（跳過回合）、沉默（封魔法）、攻擊提升、防禦下降；Cleanse 解除 |
| 五種遭遇 | Grimgarde 首領（召喚、沉默吼、毒隕石）、Gel Slime（火會治療它、會分裂）、Bone Wraith（不死、免疫毒）、Mirror Gazer（反射法術、免疫睡眠）、Iron Samurai（抗劍斧弓、8 護盾） |
| 野外 | 敵人在地圖上遊蕩，碰到就開戰 |

### 4.2 Diablo 式即時動作（`reference_projects/diablo_demo`）

| 區域 | 內容 |
| --- | --- |
| Hollowbrook（城鎮，俯視） | 商人、鐵匠（調藥水）、三個職業訓練師、長老 |
| Greenvale Fields（野外，俯視） | 史萊姆、會射擊的 Watcher、精英隊、獨眼巨人 Boss |
| Rustdeep Mine（礦坑，橫向） | 平台、單向平台、梯子、爬行者、蝙蝠、無人機、Rust Golem Boss；視差背景 |

- 三職業（Warrior／Ranger／Mage）各有技能樹加共用屬性樹，每級 2 點技能點。
- 同一組按鍵：J 攻擊（綁定 `w_slash|r_shot|m_bolt|punch`）、K 閃避、1–4 技能（4 是藥水）、Space 跳、
  E 對話、F 撿取、L 鎖定、B 背包、C 技能樹、Esc 暫停。
- 掉寶：Common／Magic／Rare／Legendary、隨機詞綴、三件套裝、唯一裝備；藥水是技能消耗的道具；
  鍛造與商店。
- 存檔往返、被擊敗的 Boss 保持倒下。

### 4.3 Full Verification（`reference_projects/full_verification_demo`，回合制壓力測試）

驗證引擎回合制部分的專案，也是推薦範本：主角 Aldric（勇者／大魔導師）一人出發，在 Hearthfold 的公會雇用
Mira、Vesper、Cael；四張地圖、三個 Boss 加三種小怪；職業與四種風格的技能樹、STR／DEX／INT／LUK 與能力值
公式、元素、弱點／護盾／破防、精煉與鑲嵌、製作、任務、寵物、地圖區域、新遊戲＋、翻譯、音樂室，編輯器每一頁
都有資料。每個系統用在哪裡：[`audits/FULL_VERIFICATION_COVERAGE.md`](audits/FULL_VERIFICATION_COVERAGE.md)。
驗證：`tests/test_full_verification_campaign.py`（整段劇情）與 `scripts/full_verification_campaign_live_check.py`
（Cocoa 視窗；圖在 `audits/evidence/full_verification_campaign/`）。

---

## 5. 資料格式的變更（都向下相容：沒設定就不寫入）

| 變更 | 位置 |
| --- | --- |
| `StateDefinition.display_name`、`icon_id` | `gameplay/states.py` |
| `AbilityDefinition.display_name`、`icon_id`、`requires_items` | `gameplay/abilities.py` |
| `CaptureRule.actor_id` 可為空，新增 `pet_item_id`、`pet_species_id`、`pet_level`（至少要有 actor、寵物道具或寵物物種其中一個） | `rpg/capture.py` |
| `AbilityDefinition.requires_pet` | `gameplay/abilities.py` |
| 資料庫新增 `pet_species`；存檔的 RPG 狀態新增選填的 `pets`、`active_pet_id`（沒有寵物就不寫入，不改版本） | `rpg/pets.py`、`rpg/actors.py`、`rpg/save_state.py` |
| `ActionCombat` 綁定替代、`item:<id>` 消耗；`CombatantComponent.defeat_switch`；`ClassAppearance`；`ParallaxBackground2D` | `runtime/` |
| `ActionCombat` 綁定 `slot:N`（技能欄第 N 格）、`vfx` 提示（世界裡的圖片特效：`effect` 精靈表 id、位移、縮放、`rotate`、`follow`）；技能欄規則 `AbilityLoadoutRules.limited_sources` 可含 `allocation`（技能樹給的技能），技能樹學到新技能會自動放進空格 | `runtime/action_combat.py`、`runtime/action_play.py`、`runtime/session/action_play.py` |
| 技能樹節點選填 `icon_id`（沒設就用它給的第一個技能的圖示；空的不寫入） | `rpg/progression_graph.py` |
| 專案資料翻譯（D60）：`DialogueLine.text_key`、`DialogueChoice.text_key`、`ChoiceRequest.prompt_key`（只在有設定時寫入）；翻譯放在既有的語系表 `data.*` 鍵，紀錄本身不變 | `rpg/data_text.py`、`events/dialogue.py`、`events/runner.py`、`runtime/session/messages.py` |
| 對話肖像（D41）：`DialogueLine.portrait_side`（`left`／`right`）；`MessageSettings.portrait_style`（`face` 訊息框內／`bust` 站在訊息框上）、`portrait_size`（0 = 自動）；DIALOGUE 指令的 `portrait_asset_id`、`portrait_side` 都只在有設定時寫入 | `events/dialogue.py`、`rpg/localization.py`、`runtime/playtest/field_ui.py`、`editor/dialogue_command_dialog.py` |
| 戰鬥版面選填 `menu_over_stage`、`row_buttons`、`column_size`、`front_large_zones`、`overhead_below`（預設 True：敵人名稱與血條放腳下）、`stage_front_right`；`BattleUiTheme` 的 `panel_skins`、`font_asset_id`、`font_scale`（九宮格面板、字型）；編輯器的版面表單永遠列出全部欄位 | `presentation/battle_ui.py`、`presentation/library.py`、`editor/integrated_authoring.py` |
| 戰鬥版面 `command_counts`（頂層指令旁的數量，預設關，D42）；戰鬥 HUD 資源樣式 `color`（空白＝主題色，D47） | `presentation/battle_ui.py`、`presentation/battle_hud.py` |
| 戰鬥 HUD 隊伍肖像（D53）：戰鬥版面 `hud_portraits`（`left` 預設／`right`／`above`／`off`）、`hud_portrait_size`（0 = 和卡片的列一樣高），只在有設定時寫入；肖像取自戰鬥角色圖的 `portrait_asset_id`（32 單位以上）／`small_portrait_asset_id`；繪製指令 `BattleUiPortrait`、`BattleUiFrame.portraits`（預設空）；後端選填 `draw_portrait` | `presentation/battle_ui.py`、`presentation/library.py`、`presentation/battle_ui_renderer.py`、`platform/pygame_battle_ui.py`、`runtime/battle_presentation_adapters.py` |
| 戰鬥站位（D54）：戰鬥版面 `column_spacing`（同一方相鄰兩欄的中心距離，0 = 自動：整張圖不重疊；有 Boss 的那一欄一律自動）、`column_spacing_right`（右側那一方另設，空白 = 跟著 `column_spacing`）、`feet_on_ground`（預設開：側視站位與肖像隊伍版面給的位置也夾在地面帶 `stage_top`～舞台底之內，角色圖的偏移 Y 照樣能讓飛行單位離地），只在不是預設值時寫入；`stage_front_right` = 0 讓整方貼著自己的邊緣 | `presentation/battle_ui.py`、`presentation/library.py`、`runtime/battle_visuals.py` |
| `InventoryRules.equip_offer`（never／empty_slot／always）與世界指令 `GIVE_EQUIPMENT`（D44） | `rpg/items.py`、`runtime/session/gear.py` |
| `ClassDefinition.resource_growth`（每級加資源）；`EquipmentDefinition.rarity`（選填，背包依它上色與命名） | `rpg/actors.py`、`rpg/items.py` |
| `DerivedStatRule`（Game Systems > Stat Formulas：stat += base + Σ 係數×stat，順序、下限、上限、對象）；`CharacterScreenProfile.stat_order`、`resource_order`（沒設時倒地資源 HP 排第一，D51） | `rpg/derived_stats.py`、`presentation/rpg_character_screen.py` |
| `InteractionRule.multiplier_source_terms`／`multiplier_target_terms`；`OutcomeCheckDefinition.blocked_source_tags`／`blocked_target_tags` | `rpg/interactions.py` |
| `AbilityDefinition.description`（戰鬥選單上方的說明）；技能進化 `AbilityEvolutionRule.required_tags` | `gameplay/abilities.py`、`rpg/ability_build.py` |
| `RefineRules.materials`、`protect_item`；裝備相關世界指令可寫 `slot:<部位>` | `rpg/refine.py`、`runtime/world_command_handlers.py` |
| 世界指令 `LEARN_ABILITY`、`NEW_GAME_PLUS`、`SET_LOCALE`；技能可用 `BATTLE_SEQUENCE` 叫出序列 | `runtime/world_command_handlers.py`、`runtime/session/party.py`（LEARN_ABILITY）、`session/battle_events.py`（NEW_GAME_PLUS）、`session/messages.py`（SET_LOCALE） |
| manifest `battle.preload_mb`（預先解碼戰鬥圖的記憶體上限，預設 64，0 關閉） | `runtime/playtest/resources.py`、`runtime/image_preloader.py` |

另有一個修正：**道具的 `battle_ability` 現在也會套用狀態、資源增益和世界指令**（原本被忽略，Storm Flask 的
降防禦從來沒生效）。

---

## 6. 測試與驗證

- 全套測試（`pytest -q`）。octopath 專案另有 `tests/test_octopath_demo.py`（每個機制）與
  `tests/test_octopath_style_battle.py`（機制本身的單元測試）；ARPG 在 `tests/test_arpg_demo.py`、
  `test_arpg_save_load.py`、`test_native_kernels.py`、`test_frame_limiter.py`；範本在
  `test_project_templates.py`。
- Full Verification：`tests/test_full_verification_campaign.py` 打完整段劇情；
  `scripts/full_verification_campaign_live_check.py OUT` 在 Cocoa 視窗先用真的按鍵走路與對話，再跑完劇情，
  每個里程碑存一張圖，另存 `results.json`。
- **實機驗證** `scripts/real_machine_validation.py OUT`：66 項真實視窗檢查（GPU、輸入、音訊、戰鬥、相機、
  選單、特效、匯入、打包 App、記憶體…）。有 4 項需要真人或手把，標示為未執行，不算通過。
- `scripts/arpg_demo_live_check.py <職業> OUT`：真實視窗，用腳本按鍵走完城鎮、轉職、技能樹、野外、Boss、
  礦坑，輸出截圖與 fps。
- `scripts/editor_ui_audit.py`：編輯器版面稽核（可 `--project`、`--also 1100x700`）。
- `scripts/built_in_text_live_check.py OUT`：Cocoa 視窗把 Full Verification 切成 zh-TW，用真的按鍵走過標題、
  野外、暫停、設定、存檔、狀態、戰鬥指令、勝利與遊戲結束，存圖並記下每個畫面畫出的字（D52）。
- 量測：`scripts/arpg_stress.py`、`arpg_demo_measure.py`、`runtime_benchmark.py`。ARPG 壓力與執行期基準
  不開 heap 追蹤（tracemalloc 會讓每次 Python 配置慢約 40 倍，熱點也會看錯）。

---

- **不出聲**：`ASTERIA_MUTE=1` 讓任何執行（pytest、真實視窗 live check、`asteria-preview`）用無聲的音訊裝置；
  web 版網址加 `?mute=1`。自動化檢查一律帶著它（D59）。

## 7. 已知限制與還沒做的事

| 項目 | 狀態 |
| --- | --- |
| 圖示與美術 | 所有 demo（Full Verification、Octopath、reference、Diablo 兩個、party／basic／action 範本）的人物、怪物、地圖、UI、裝備與技能圖示都是 Foozle Lucifer（CC0）；例外：Diablo 的箭與投射物、弓和魔杖圖示來自 Ninja Adventure（Lucifer 沒有）。程式畫的原創圖示（`graphics/forged_icons.py`，D35）仍在引擎裡可選。沒有 AI 美術 |
| 原生 kernel 要在開發機編譯一次 | `python -m asteria.kernels.build_native`（macOS 編成 arm64 + x86_64 通用檔，ABI 5）；匯出會先檢查、必要時重編並帶著它，玩家的 Python 沒有 numpy 也能用；沒編譯會退回 numpy／python |
| 輕量電腦 | 效能只在本機（Apple silicon、沒開低耗電模式）量過；真的輕量電腦或低耗電模式要有人實際跑 |
| 頭上名字的縮寫 | 名字超過 14 字會縮成縮寫（「Goblin Slinger 2」→「GS2」），要怎麼顯示待使用者決定。2026-10-22 發現的其他戰鬥畫面問題（拉近時的狀態文字、技能列名稱黏花費、狀態畫面 HP／MP 順序）已修（DECISION_LOG D51 補充） |
| 編輯器 | 中文模式下，顯示的字就是存檔值的固定選項（Enemy AI 的條件／動作／目標、事件觸發、VFX 錨點）還是英文；稽核（英文與中文、1600×1000 與 1100×700）被截的文字 0 處（D51 補充） |
| 遊戲內的文字翻譯 | 引擎自己的字都能用專案的翻譯表翻（D52，見 3.7）；專案資料的名稱、說明、對話也能翻（D60；Full Verification 全部有繁中）；開發用的錯誤訊息維持英文；中文用系統字型，桌面匯出不附中文字型（web 匯出附 Noto Sans TC，`ASTERIA_CJK_FONT` 可指定）；寵物改名不支援中文輸入法組字 |
| Web 匯出（D59） | `python -m asteria.export_web`（pygbag）：沒有編輯器、多人連線、ModernGL、C++ kernel、預載執行緒；玩家開頁面要連得到 pygame-web 的 CDN（`--cdn` 自架）；存檔在瀏覽器的 localStorage；音訊只有 ogg／wav；本機測試用 `127.0.0.1` 開，不用 `localhost`；證據 `audits/evidence/web_export/` |
| Enemy AI 的七欄規則表 | 窗口很窄時可橫向捲動（表格的正常行為） |
| 手把與實體鍵盤、音訊聽感與延遲 | 需要真人；沒有自動化 |
| 手感與平衡 | 數值是 demo 用的，需要有人實際玩過調整。Diablo 的九個流派用 `scripts/arpg_balance.py` 對齊（同等級、同技能點下的輸出加存活的綜合分數，差距在 ±20% 內）；沒有裝備、沒有真人操作，只能比流派之間 |
| 寵物 | 預設不是戰鬥單位（物種可選 `battle_unit`）；已有進化、學技能、親密度（D31） |
| 寵物的存檔與選單 | Pets 畫面只在專案有寵物物種時出現在暫停選單；起始寵物在 Database > Game Start 分頁設定 |
| 多人連線 | 通用 TCP session／adapter、SQLite 原子掉落領取及完整角色存檔、可修改規則模板、獨立 Diablo 多人副本已完成四人原生驗收。Guest ID 為開發身分；伺服器重開保留角色並重建場次世界。公開網路部署、TLS、登入驗證與 WAN 品質驗收另行處理。見 [設計文件](audits/MULTIPLAYER_DESIGN.md)。 |

接續工作與本機設定：[`NEXT_STEPS.md`](NEXT_STEPS.md)。

### D26 新增的系統（資料驅動，沒設定就沒有影響；細節見 DECISION_LOG D26）

戰鬥規則擴充（嘲諷、吸血、過度擊殺、次數限制、熟練度、先制、偷竊）、敵人等級與難度、ATB／CTB 量表與預測順序、勝利結算畫面、區域與地板規則（地板傷害、滑冰、腳步聲、限制通行、潛行）、事件計時器、裝備耐久與暱稱、拆解、職業點、新遊戲＋、訊息控制碼與翻譯、訊息記錄／音樂室／製作人員名單、地形自動鋪磚、格狀尋路與 `WALK_TO`、2D 骨骼動畫，以及多人連線的 TLS／token／網路模擬／度量。

### D27–D33 新增的系統（細節見 DECISION_LOG；缺口對照表見 [`audits/GAP_LIST.md`](audits/GAP_LIST.md)）

| 類別 | 內容 |
|---|---|
| 寵物（D31） | 進化（等級／親密度／道具，可自動或手動）、學技能（出現在 learnset 的技能必須學會才能用）、親密度、可選的戰鬥單位（`battle_unit`，以暱稱顯示、不決定勝負） |
| 作者流程（D31） | Database > Game Start 表單（場景、隊伍、背包、貨幣、起始寵物）、暫停選單自訂項目（`MenuEntry`）、技能槽規則（`AbilityLoadoutRules`）與暫停選單「Skill Slots」畫面 |
| 規則（D31–D32） | 商店條件顯示與價格規則、依區域的戰鬥背景、隊伍共用量表、狀態分類與 `dispel`、技能選單分類（`menu_category`）、自動戰鬥（manifest `battle.auto_key`）、演員變數 |
| 事件（D31–D33） | `MOVE_ROUTE`、`SHOW_BALLOON`、`SPAWN_ENTITY`、`COPY_ENTITY`、`MORPH_ENTITY`、`SET_ENTITY_ICON`、點擊觸發（`Interaction2D.trigger = click`） |
| 畫面（D32–D35） | 地圖視窗（manifest `field.hud.gold`／`quest_tracker`）、低血量姿勢與 T 鍵自動戰鬥（Game Systems > Battle Options）、狀態染色（`StateDefinition.tint`）、原創技能／狀態／寵物圖示 |
| 編輯器 | Game Start 分頁、新的 Game Systems 種類（Ability Slots、Pause Menu Entries）、種類下拉選單圖示、flag／paw／gauge 圖示 |

以上全部是資料驅動、沒設定就沒有影響；舊專案與存檔照常載入。

### D36 新增（Full Verification demo 帶出來的系統；報告 [`audits/BOSS_TRIAL_B2_B3_REPORT.md`](audits/BOSS_TRIAL_B2_B3_REPORT.md)）

| 類別 | 內容 |
|---|---|
| 技能每一下（`hits`） | `checks`（逐下擲爆擊／迴避等檢查，效果由互動規則決定）、`kill`（即死：機率、免疫標籤、免疫時改扣最大值比例） |
| 裝備 | `RefineRules`（+N 精煉：費用、各級成功率、失敗後果 keep／drop／break／destroy、安全級數）、可鑲嵌道具（`ItemDefinition.attachment_id`、`destroyed_on_removal`） |
| 角色 | `ClassDefinition.level_growth`（職業每級成長）、`points_per_level`（升級給任意名稱的點數） |
| 世界指令 | `GRANT_EXPERIENCE`、`REFINE_EQUIPMENT`、`SOCKET_ITEM`、`UNSOCKET_ITEM`、`UPGRADE_EQUIPMENT` |
| 戰鬥表現 | 版面 `hidden_zones`（該區域成員完全不畫 HUD，像八方旅人的敵人）、`move` 動作通道（`advance` 衝向目標、`return` 退回，停在目標體型邊緣）、精靈表中繼資料 `body_height`（血條與選單依本體高度擺） |
| 反擊與戰鬥表現 | `ReactionDefinition.reactor_tags`（要求反應者自己帶標籤，如反擊姿態）；可玩戰鬥現在會觸發專案的反應並記入戰鬥記錄；敵人技能也走逐下流程（爆擊／即死／反應）；`EQUIP_ITEM`（戰鬥中換武器，技能跟著變）、`DISASSEMBLE`；失去開場（先制／偷襲）的一方在時間軸排程下只讓出第一輪 |
| Demo | `reference_projects/full_verification_demo/`：單一主角打 Boss，`run_trial_smoke.py` 腳本化驗證、`scripts/full_verification_live_check.py` 真實視窗驗證 |

### D42–D51 新增（2026-10-18～22；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 編輯器 | 紀錄表單與邊改邊套用（D45）、RPG Maker 式畫地圖（D42）、素材庫匯入（D44）、技能樹圖（D43）、繁體中文介面（D50）、逐頁排版與偶發當機修正（D47） |
| 戰鬥與角色 | 能力值公式、元素攻擊與抗性、弱點與爆擊倍率、新裝備先問、裝備稀有度、精煉材料與保級（D43–D44）；HP 在 MP 上面、BP 金色圓點、HUD 資源顏色（D47）；選單游標自動對齊、頭上名字不蓋人（D49） |
| 效能 | 碰撞世界就地更新、C++ kernel 不需 numpy、繪製快取、戰鬥圖預先解碼、HUD 與指令列只在變化時重排、場上 AI 批次、換音樂不凍住（D48） |
| Demo | Full Verification（原 Boss Trial）補滿所有系統，成為推薦範本（D43） |

### D55 新增（2026-10-23；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 精靈表 | 中繼資料 `scaling`：`pixel`（預設）／`smooth`，戰鬥與地圖照它用最近鄰或平滑縮放；編輯器 Sprite Animation ▸ Sheet ▸ 縮放方式；playtest manifest `field.player_scaling` |
| 素材 | `asset_library/kaykit/`（KayKit Adventurers 2.0、Character Animations 1.1，CC0）與渲染成品；`scripts/build_kaykit_art.py`（`--render` 用 Blender 拍，否則只組圖）、`scripts/kaykit_render_blender.py` |
| Demo | Full Verification 隊伍仍是 Lucifer 像素風；建置時 `ASTERIA_FV_PARTY=kaykit` 可換成 KayKit（`trial_kaykit.py`）；`build_kaykit_art.py --style toon` 產生卡通著色＋外框的像素版 |

### D56 新增（2026-10-23；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 工具 | GitHub Actions（`.github/workflows/tests.yml`）：每次 push／PR 跑 ruff 與全部測試（無頭）；`scripts/battle_art_gallery_live_check.py`（D55）、`scripts/runtime_benchmark.py` 仍是本機跑 |
| 繪製 | `graphics/scaling.py`：所有 pygame 繪製的縮放走 `resized`（最近鄰／平滑），`ScaledImageCache` 保留縮好的圖 |
| 程式結構 | `runtime/game_session.py` 的 `GameSessionRuntime` 由 `runtime/session/` 的 18 個 mixin 組成；`runtime/playable_test_runtime.py` 的 `PlayableTestRuntime` 由 `runtime/playtest/` 的 14 個 mixin 組成。本手冊其他列寫的 `runtime/game_session.py`／`runtime/playable_test_runtime.py`，方法現在在這兩個資料夾的對應模組裡 |
| 文件 | `docs/audits/ARCHITECTURE_PERFORMANCE_RISKS.md` 重核為 2026-10-23 現況，含實機基準 |

### D59 新增（2026-10-23；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 匯出 | `asteria.export_web`：專案＋精簡引擎＋Noto Sans TC＋async `main.py` → pygbag 打包成 `build/web/`；`--serve` 用自己的靜態伺服器；`runtime/web_persistence.py` 把 `saves/` 鏡像到 localStorage；引擎在瀏覽器裡不開執行緒、不碰 `resource`／`tracemalloc`／`statistics`；`PlayableTestRuntime.step()` |
| 素材 | `asset_library/fonts/noto_sans_tc/`（OFL）；素材庫列圖包時略過沒有圖片的資料夾 |

### D61 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 素材 | `asset_library/opengameart/7Soul_496_RPG_Icons/`（CC0，496 張 34×34） |
| Demo | Full Verification 九種武器類型（含新的書、拳、投擲與它們的普通攻擊）各 ≥5 把、五個稀有度；`trial_arsenal.py`；證據 `audits/evidence/arsenal/` |
| Demo | 防具 18、飾品 19、道具 94（藥水、狀態藥、投擲、材料、屬性寶珠、卡片）；`trial_supplies.py`；會解除狀態的技能說明寫 removes |
| 引擎 | 商店可以賣裝備：`ShopRuntime(receive_equipment=, equipment=)`，買下進裝備背包；商店清單跟著游標捲動；工坊精煉結果 `workshop.outcome.*` 有翻譯 |
| 編輯器 | 商店商品欄「道具或裝備」（來源 `goods`：道具＋裝備，都顯示名稱與圖示） |
| Demo | 爐心鎮三間新商店（武器、防具、藥鋪）；`trial_shops.py`；run_campaign 新增 7 個必要事實；`scripts/shops_live_check.py` |

### D62 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 生物 | Pet Rules（隊伍、上場數、倉庫、能力公式、基因、經驗曲線、招式上限、掙扎）；捕獲 rate 模式；遭遇的物種成員與預備；換人 |
| 戰鬥畫面 | `runtime/creature_battle.py`（`battle.style: "creature"`，圖與座標都在 manifest 的 `battle.creature_screen`）；`graphics/bitmap_font.py` 點陣字型 |
| 地圖 | `runtime/grid_walk.py` 格子行走與跳台階（`ledge_<方向>` 標籤、`field.jump_shadow`）；`runtime/grid_actors.py` 的 `GridMover2D` 格子角色；tile 的 `animation`／`frame_ms` 動畫；`cover` 標籤的遮蓋格（高草遮腳） |
| 地圖區域 | `AreaRule` 的 `music`、`title`（`field.area_name` 地名牌）、`encounters`／`encounter_chance`／`encounter_first_step`（每走一格的隨機遇敵） |
| 對話 | `dialogue.window`：遊戲自己的訊息窗圖、點陣字型、打字速度、翻頁箭頭 |

### D63 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 算式 | `gameplay/expressions.py`：安全算式；`ValueFormula.expression`、`OutcomeCheckDefinition.chance_expression`、`BattleEscapeRule.chance_expression`（`attempts`）、`BattleSessionRules.initiative_expression`／`final_damage_expression` |
| 戰鬥規則 | `BattleSessionRules.battle_counters`（能力段數等，換人歸零）、`vary_seed`（每場不同亂數） |
| 狀態 | `BattleStatePolicy` 的 `prevent_chance`、`remove_chance`、`duration_range`、`exclusive_group`；`apply_states` 的 `chance`、`unless_outcome`；狀態每回合傷害、到期、解除寫進對戰紀錄 |
| 捕捉 | `CaptureRule.shake_checks`：晃動判定與晃幾下 |
| 戰鬥畫面 | 開場滑入、丟球、生物從球出來、資訊框滑入；依血量的換人台詞；訓練家換人前詢問、野生戰倒下後詢問；戰鬥中的隊伍順序；沒打中、能力段數、異常狀態台詞（`state_messages`）、異常圖示（`status_icons`） |

### D64 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 地圖 | `SightTrigger2D`（視線、驚嘆號 `field.emotes`、走過來、開始事件、`done_switch`）；`GridMover2D.look_facings`；`PLAY_BGM` 的 `temporary` |
| 招式 | `priority`、`drain`、`recoil`、`hit_counts`、每擊的 `first_checks`；`plan_round()`（敵方先選招、照先制度再照速度）；排程器 `set_priorities()` |
| 狀態 | `BattleStatePolicy.battle_only`（戰後不保留）；戰鬥計數器不寫回存檔 |
| 戰鬥畫面 | 吸取、反作用、打幾下的台詞；`outcome_lines`、`fail_tag`；訓練家的 `defeat_text` |

### D65 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| Demo | Full Verification 主角改名 Roger（中文羅傑），家是 Roger's House；id 仍是 `hero_01` |

### D66 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 事件 | `WAIT until`、`EXIT`、`SET_VARIABLE.from_variable`、`CHOICE.box_at`；可讀 `player.facing`（事件開始時）與 `battle.running` |
| 世界指令 | `GRID_ROUTE`、`SET_POSITION`（`permanent`）、`SHOW_ENTITY`、`SET_MOVEMENT`、`GIVE_PET`、`SET_LOOK`、`SET_RESPAWN`、`RESTORE_BGM`；`entity` 可寫 `self`、`var:<變數>` |
| 元件 | `SwitchVisibility2D`（開關控制出現）、`LookByVariable2D`（外觀跟著變數） |
| 區域規則 | `AreaRule.autorun`（`always` 或 `enter`）；忙碌時 `on_enter` 排隊 |
| 輸掉戰鬥 | `BattleSessionRules.defeat`（`respawn`）、`defeat_currency`、`defeat_currency_loss`、`defeat_event`；遭遇標籤 `defeat_continues` |
| 畫面 | 選項的方向鍵游標；`dialogue.choice_frame` 等遊戲自己的選項框、`cancel_picks_last`；`field.notices: false`；戰鬥設定可用 `\V[...]`、`encounters.<id>.no_running_text` |

### D67 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 翻譯 | `stat_name`、`slot_name`、`game.tag_name`（`data.tag.<標籤>.name`）；`SocketDefinition.label`；任務目標顯示名稱；`test_full_verification_ui_words.py` 檢查中文畫面沒有 id 與英文 |
| 選單版面 | `presentation/menu_layout.py`（`MenuLayout`／`MenuElement`／`MenuSlotPlace`／`MenuTheme`，演出庫類別 `menu_layout`、`menu_theme`）；`runtime/menu_canvas.py` 依版面畫；沒有版面時逐像素和以前一樣 |
| 預覽 | `runtime/menu_preview.py`：`MenuPreview` 在畫面外畫任一個畫面；`open_menu_screen`；`ASTERIA_OPEN_MENU` 讓試玩一開始就打開某個畫面 |
| 編輯器 | 演出 ▸ 選單畫面 ▸ 版面（`editor/menu_layout_widget.py`）：畫布拖曳與縮放、屬性欄、紙娃娃部位表、主題、在遊戲中開啟；選單資料移到同一頁的第二個子頁 |
| 設定 | `GameSettings.developer_menu`：C 鍵的養成驗收選單只在開啟時出現 |

### D68 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 畫面 | `runtime/equipment_screen.py` 紙娃娃（只列能穿的、比較、穿上後的數值）；`runtime/enhance_screen.py` 精煉、鑲嵌、卡片、成長四頁；工坊移除 |
| 遊戲 | `game.wear_from_bag(actor, instance, slot, index)`；暫停選單的「裝備」「強化」依專案內容出現 |
| Demo | `trial_doll.py`：頭、腿、腳部位，14 件 Lucifer 圖示裝備，Lucifer 紙娃娃版面與石頭面板；證據 `audits/evidence/ui_u3/` |

### D69 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 畫面 | `runtime/creature_menu.py`：生物遊戲自己的開始選單（`field.creature_menu`），暫停鍵打開；圖鑑（清單、項目）、隊伍（能力三頁、替換）、背包（依標籤分袋、使用／丟掉）、訓練家卡片、設定、記錄 |
| 設定 | 各列可用開關隱藏、標籤可用 `\V[...]`；設定存在 `option.<id>`；`dialogue.speeds` 依 `option.text_speed` 改文字速度 |
| 遊戲 | 世界計數器 `play.seconds`（遊玩時間）；記錄寫到存檔欄 `save_slot` |

### D70 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 資料 | `rpg/workstations.py`：工作台（分頁依配方標籤、未發現顯示 ???、一次上限、分解頁、音效、成功圖、音樂、版面），`rpg_database.workstations` |
| 畫面 | `runtime/crafting_screen.py`：分頁、成品圖示、材料持有／需要、成功率、品質、數量、分解；每個工作台可有自己的版面 `crafting.<id>` |
| 翻譯 | `data.workstation.*`、`data.workstation_category.*`、`data.quality.<名稱>.name`；20 個 `crafting.*` 鍵 |
| Demo | `trial_crafting.py`：爐心鎮的煉金台與鍛造爐、12 條新配方；證據 `audits/evidence/ui_u4/` |

### D71 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 資料 | `rpg/boards.py`：任務告示板、招募事務所；`rpg/gacha.py`：抽獎卡池（稀有度、獎品、主打、硬／軟保底、多連抽保證）；任務的卡片欄位 `card_image`／`rank`／`category`／`repeatable`／`time_limit` |
| 事件 | `OPEN_QUEST_BOARD`、`OPEN_RECRUIT`、`OPEN_GACHA` |
| 規則與畫面 | `runtime/boards_play.py`（狀態存在 `world.systems`）、`runtime/service_screens.py`（卡片翻面、肖像、寶箱出現／搖晃／打開）；版面 `quest_board`／`recruit`／`gacha` 與 `<畫面>.<id>` |
| 編輯器 | 遊戲系統三頁；抽獎卡池「模擬 10,000 抽」 |
| 翻譯 | 75 個 `board.*`／`recruit.*`／`gacha.*` 鍵；資料鍵 `data.quest_board.*`、`data.recruit_office.*`、`data.gacha_banner.*`、`data.gacha_rarity.*`、`data.quest_category.*`、招募備註 |
| Demo | `trial_boards.py`：星石、懸賞告示板、公會職員、星落寶箱；證據 `audits/evidence/ui_u5/` |

### D72 新增（2026-10-24；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 驗收 | 導覽 43 個畫面中英文（`scripts/ui_tour_live_check.py`）；`run_campaign.py` 用畫面操作告示板、招募、十連抽、煉金、紙娃娃、強化鑲嵌與精煉 |
| 效能 | `scripts/menu_frame_time_check.py`：每個選單畫面 60 幀，95 百分位上限 16.7 ms；目前最慢 4.55 ms |
| 證據 | `audits/evidence/ui_u6/` |

### D73 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 道具 | `game.use_item_on_pet(pet, item)`；道具標籤 `cures:<狀態>`（`*` 全部）、`revives`；戰鬥與田野的道具效果有自己的公式環境 |
| 隊伍 | 世界指令 `PARTY_STASH`／`PARTY_RESTORE`（借別人的隊伍打一場） |
| 戰鬥畫面 | `encounters.<id>` 的 `player_name`、`player_back`、`auto_choices`、`auto_delay`；遭遇標籤 `sure_capture` |
| 事件 | `SET_VARIABLE` 的 `add`；`rpg` 條件的 `pets`（隊伍隻數） |
| 田野 | 預設按鍵 `run`（Shift、手把 B）；`field.run_switch` |
| 規則 | Pet Rules `exp_whole`（經驗值取整數） |
| 開始選單 | 背包「使用」選生物；訓練家卡片的 `badges` |

### D74 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 聲音 | 世界指令 `PLAY_ME`（短曲：音樂暫停、播完接著放）；條件來源 `audio`（`me`、`se`）讓事件等短曲／音效放完 |
| 圖塊 | 世界指令 `SET_TILE`（`layer`、`x`、`y`、`tile`、`permanent`）；這次造訪或永久（存檔 `world.systems` 的 `tiles.<場景>`）；碰撞圖層會開路／擋路 |
| 選項 | `CHOICE` 的 `cursor`、`cancel`（取消鍵的值）、`columns`（格狀）；`game.cancel_choice()` |
| 編輯器 | 事件的「選項」與「等待」對話框（等待可選秒數或條件：switch、variable、rpg、npc、battle、audio） |

### D75 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 對話 | `DIALOGUE` 的 `wait: false`（字留著、事件繼續；`game.held_dialogue`）；沒提示的 `CHOICE` 用這句當提示 |
| 取名字 | 世界指令 `NAME_INPUT`（`target` `variable:<x>` / `pet:last`、`max_length`、`title`、`default`）；畫面 `runtime/name_input.py`、`field.name_input`；條件 `rpg` `name_input` |
| 圖片選擇 | 世界指令 `PICTURE_CHOICE`（`layout`、`variable`）；畫面 `runtime/picture_choice.py`、`field.picture_choices.<layout>`；條件 `rpg` `picture_choice` |
| 道具 | 標籤 `teaches:<能力>`、`reusable`；種族 `teachable`；`game.teaching_check`；`ItemDefinition.description` |
| 商店 | `field.creature_shop`：`runtime/creature_shop.py`（BUY／SELL／QUIT、購買畫面、數量、YES／NO、`buy_sound`、`bonus`、`map_front_at`）；條件 `rpg` `shop` |

### D76 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 版面基礎 | `ScreenSpec.size`（畫面自己的解析度）與 `group`（`menu`／`game`，編輯器清單的「遊戲進行中」標題）；`MenuElement.frames`／`frame_axis`／`fps`（動畫條）、`bitmap_font`；`MenuCanvas(size=, target=)`、`picture()`、`strip_frame()`、`font_of()` |
| 點陣字 | `MenuBitmapFont`（演出庫類別 `bitmap_font`）：字圖、格子大小、每列的字（`⬚` 空格）、字距、空白寬、行高、等寬、個別字寬、顏色（`tint`／`keep`／`two_tone`）、像素倍率；`graphics/bitmap_font.SheetFont`；`rt.text(font="bitmap:<id>")`，主題 `MenuTheme.bitmap_font`；字圖沒有的字改用一般字型 |
| 對話框 | 畫面 `dialogue`（視窗、名字、名字框、頭像、台詞、繼續提示、箭頭）與 `dialogue_choice`（框、提問、選項）；`runtime/dialogue_screen.py`；圖片視窗 `presentation/dialogue_window.DialogueWindowStyle`（演出庫類別 `dialogue_window`，`default`），`rt.dialogue_settings()` 先讀專案再讀 manifest；編輯器一鍵從 manifest 轉入（逐像素相同） |
| 動作 RPG HUD | 畫面 `hud_action`（30 個元件：兩顆球的外框／液體／空球／名稱／數值、改成條、底板、技能格、按鍵帽、冷卻動畫條、徽章、消耗、經驗、等級、狀態格、其他資源條、提示、鎖定框、橫幅、倒下）；`MenuTheme.resource_colors` 取代依名稱猜的顏色 |
| 戰鬥畫面 | 畫面 `battle`：`presentation/battle_layout.BattleScreenLayout` 把排好的指令依組（`party_hud`、`overhead`、`menu`、`help`、`workflow`、`timeline`、`numbers`、`result`、`target`）整組移動、縮放（0＝引擎大小）、換外觀、改字色字級、隱藏，加作者自己的元件；單位是戰鬥虛擬座標，編輯器依 `MenuPreview.unit` 換算；沒有版面時不跑 |
| 技能樹 | `node_locked`／`node_available`／`node_learned`／`node_maxed`／`node_selected` 的圖、`link_met`／`link_unmet` 的顏色與線寬、`points_icon` |
| 圖片欄位 | `editor/image_tools.picture_field(key)`：所有通用表單的圖片欄位（`icon_id`、`image`、`portrait`、`*_image`、`*_icon`、`*_background`…）都有預覽與「選擇…」 |
| 編輯器 | 版面頁新按鈕「點陣字型…」「圖片對話視窗…」；主題的「點陣字型」與「資源顏色」；屬性欄的動畫格數、方向、每秒格數；數字框的上下箭頭不再吃掉文字區（主題 `QAbstractSpinBox` 右側 padding 0） |

### D77 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 生物畫面 | 演出庫類別 `creature_screen`（記錄 id＝manifest 路徑：`battle.creature_screen`、`field.creature_menu`、`field.creature_shop`、`field.name_input`、`field.picture_choices`）；`presentation/creature_screens.CreatureScreenSettings`；`creature_settings(runtime, 畫面)` 先讀專案再讀 manifest；`creature_battle_on(runtime)` |
| 編輯器 | 版面頁「生物畫面…」（`editor/creature_screens_dialog.py`）：設定樹（圖片、音效、字型、顏色、位置、數字、是／否、文字、表格、清單；右鍵新增／複製／移除）、240 × 160 位置預覽可拖曳、一鍵從 manifest 轉入；控制器 `set_creature_screen`、`read_creature_manifest`、`import_creature_manifest` |

### D78 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 選項框 | 沒有被作者放置的 `dialogue_choice.box` 會長到包住提問與每一列（`dialogue_screen._grown`） |
| 戰鬥版面 | `party_hud.<n>`、`overhead.<n>`：單張卡片在整組之後單獨移動、縮放、換外觀、隱藏（`battle_layout.PER_MEMBER`）；`layout_boxes` 有每張卡的外框 |
| 生物畫面頁 | `MenuPreview.render_creature(畫面, 設定)`（借設定畫一次再還原）；`creature_screens_dialog.help_for`（說明取自畫面模組的 docstring）；開始選單、商店、輸入名字的 `engine_defaults`；`[x, y, w, h]` 位置 |
| 遊戲資料夾設定 | `editor/game_folder_settings_dialog.py`：`playable_test_manifest.json` 的每個分區用設定樹編輯，確定才寫回（格式不變，不會建立新檔）；執行 ▸ 遊戲資料夾設定…、版面頁按鈕 |

### D79 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 照明 | 世界指令 `SET_LIGHT`（`radius`、`speed`、`off`）；屬於它的場景；條件 `rpg` `light` |
| 位置 | `SET_POSITION` 沒給的 `x`／`y` 留在原地（只給 `permanent`＝記住現在的位置） |

### D80 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 生物畫面頁 | `help_for` 經過編輯器翻譯（說明句子都在 `zh_TW.json`，測試逐句檢查）；戰鬥預覽只推進 `CreatureBattleScreen.update`，最後畫一次；開始選單、商店的預覽疊在野外上（`MenuPreview._over_field`） |
| 遊戲資料夾設定 | 分區名稱 `TITLES`／`title_of`；寫回是 `WriteGameFolderSettingsCommand`（可復原）；版面頁的預覽在檔案內容變了時重開（`_folder_settings`） |

### D81 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 資料表單 | 欄位與分區的說明只在 ⓘ 的滑鼠提示裡（`Section` 的 `FormSectionHelp`），不再印在表單上 |

### D82 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 圖片 | `tint`／`tint_color`、`MOVE_PICTURE` 的 `delay`、`frame_rate`／`frame_loop`、`scroll_x`／`scroll_y`、`wave_*`、`blend`（`add`）、文字圖片 `text`／`font`／`text_color`／`shadow_color`／`text_align`（`runtime/pictures.py`，畫在 `field_ui._draw_pictures`、`_picture_motion`、`_text_picture`） |
| 選項 | `CHOICE` 選項的 `hover`（`DialogueChoice.hover`、`runner.hover_choice`）；選項框等提問打完（`dialogue.choice_after_text`、`field_ui._choice_ready`）；超過兩行往上捲；同一句不重打 |
| 標題畫面 | 遊戲資料夾的 `title_screen.program`（`playtest/title_build.py` 的 `_title_program_frame`）；`TITLE_COMMAND`（`session.request_title`）；`CreatureMenuScreen.open_alone` |
| 條件／等待 | `rpg` `pressed:`／`held:`（`a|b`）、`rpg` `saves`；`WAIT` 的 `until`＋`seconds`（`events/vm.py`） |
| 訊息 | `\V[play.time]`、`\V[creatures.owned]`（`session.messages._message_word`） |

### D83 新增（2026-10-25；細節見 DECISION_LOG）

| 類別 | 內容 |
|---|---|
| 編輯器 | 滑鼠提示 120 ms 出現（`theme.TOOLTIP_DELAY_MS`，`_quick_tooltips` 的 `QProxyStyle`） |

### 下一步的候選（沒有排序，要使用者決定）

1. 頭上名字太長時怎麼顯示（現在縮成「GS2」）。
2. 編輯器剩下的英文：顯示＝存檔值的固定選項，要把顯示和值分開。
3. 專案資料的翻譯——做了（D60）；剩下戰鬥序列裡的對話、曲名與製作人員名單的資料鍵。
4. 第三個範本（橫向平台動作、彈幕射擊）——使用者 2026-10-16 說先不用。
5. Web 匯出——做了（D59）；還可做：存檔匯出／匯入成檔案、自架 runtime 的一鍵複製、標題畫面每幀 14 ms 的背景縮放快取。
6. 技能圖示換成美術師手繪（現在是程式畫的 32 px 原創圖示，D35）。

---

## 8. 工作方式（給之後接手的人）

- 直接在 `main` 上提交，不開分支；提交作者使用 Roger 的 GitHub 身分，且不得加入任何 `Co-Authored-By` trailer。
- 每行 Python ≤ 99 字元（skill：`.claude/skills/line-length`）。
- 新 clone 後執行 `git config core.hooksPath .githooks`；提交 hook 會阻擋共同作者 trailer，並確認 author 是 `rogerhao66666`。
- 每一批的結果寫進 `docs/audits/DECISION_LOG.md`（中文，六段式：做了什麼、證據、限制）。
- UI 和實機的東西一定在 Cocoa 真實視窗驗證，附截圖，放 `docs/audits/evidence/real_machine/`。
- 編輯器要好看：有顏色、有圖示、版面密但不擠；稽核腳本要乾淨。
- 編輯器的新介面文字要在 `src/asteria/editor/translations/zh_TW.json` 加翻譯（或樣板）；依標題挑圖示、樣式或
  面板的程式碼比對 `i18n.english(text)`，不要比對畫面上的字。
- 遊戲畫面的新文字要寫成 `game.tr("<鍵>", "<英文>")`，並在 `rpg/built_in_text.py` 的 `GROUPS` 與
  `rpg/built_in_text/zh-TW.json` 各加一條，再跑 `scripts/built_in_text_keys.py`（測試會抓漏）；版面量字寬用
  `presentation/text_cells.cells`（全形字算 2 格），不要用 `len()`。
- 效能量測不開 tracemalloc（`RuntimeProfiler(track_python_heap=False)`）；真實視窗的時間會被合成器的 vsync
  吃掉，比較新舊要在同一個程序裡交替跑。
- 同一個資料夾有其他 session 在改時，實機截圖從 HEAD 的乾淨副本拍（`git archive HEAD`，再把編好的
  `libasteria_kernels.dylib` 複製進去），才不會拍到別人沒提交的改動。
