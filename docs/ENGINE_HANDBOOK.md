# Asteria 引擎手冊（功能、範本、demo、規則、下一步）

**更新：** 2026-10-16（D32；D27–D32 的內容看 DECISION_LOG 與 [`audits/GAP_LIST.md`](audits/GAP_LIST.md)）。這份是「目前到底有什麼」的單一入口；細節和決策理由在
[`docs/audits/DECISION_LOG.md`](audits/DECISION_LOG.md)（D1 ～ D26），規格在
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
.venv/bin/python -m pytest -q                  # 全部測試（約 1 分鐘）
.venv/bin/python -m asteria.kernels.build_native   # 編譯 C++ kernel（每台機器一次）
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
- **kernel**（`docs/NATIVE_KERNELS.md`）：廣域碰撞、投射物、粒子、天氣、角色移動、場景 AI；`ASTERIA_KERNELS=
  native|numpy|python`，預設取最快可用的；沒編譯 C++ 也不會壞（退回 numpy／python）。
- 量測：300 隻敵人 + 500 顆投射物每幀 python 25.7 ms／numpy 14.5 ms／native 11.6 ms；全螢幕技能的大場面
  30 → 11.5 ms；640×640 的大地圖 < 0.5 秒載入（區塊懶惰繪製，只付鏡頭看得到的）；真實視窗 60 fps。

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

- **File > New from Template…（Ctrl+N）**：Party RPG（八方旅人式）、Action RPG（暗黑式）兩個範本，
  複製整個專案資料夾（含美術與授權文件）後改名開啟，Console 會顯示專案裡的 `START_HERE.md`（每個規則
  在編輯器哪裡改）。範本隨套件發布（`src/asteria/templates/`）；改了 demo 之後執行
  `scripts/sync_templates.py`，測試會檢查兩邊一致。
- Real-Time Combat 工作區（攻擊、投射物、稀有度、詞綴，即時預覽與判定框疊圖）；Enemy AI；技能與狀態
  可編輯 `display_name`、`icon_id`（圖示挑選）；Capture Rules 可設 `Joins As Actor`、`Becomes Pet Item`。
- 窄視窗：最小視窗 1000×640；預覽在窄頁自動收起；表格欄寬與下拉選單依內容。
- 稽核腳本 `scripts/editor_ui_audit.py` 逐工作區截圖並找：文字被截斷、溢出、過小控制項、停靠面板的分頁掉出
  分頁列；兩個專案在 1600×1000／1280×800／1100×700 皆 0 缺陷。
- Code 工作區：寫 Python 腳本直接操作專案，有自動完成。
- Multiplayer 工作區：本機 server、Guest ID、SQLite、專案規則模板及獨立 Diablo 多人副本。副本使用 project-backed adapter 同步原 ECS 戰鬥、技能、怪物、NPC、商店、製作、背包、裝備與角色存檔；四人 Cocoa 驗收通過。Boss 有正傷害者各得完整 100 XP，每項原掉落隨機保留給一位參與者。使用方式見 [遊戲模板](audits/MULTIPLAYER_GAMEPLAY_TEMPLATE.md)。
- Scene 視圖操作：**滑鼠滾輪以游標為中心縮放**（一格 ×1.15）；方向鍵平移視圖（有選取實體時改為移動實體，
  Shift 加大步距）；**觸控板**雙指捲動平移、捏合縮放（維持原樣）。

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

另有一個修正：**道具的 `battle_ability` 現在也會套用狀態、資源增益和世界指令**（原本被忽略，Storm Flask 的
降防禦從來沒生效）。

---

## 6. 測試與驗證

- 全套測試（`pytest -q`）。octopath 專案另有 `tests/test_octopath_demo.py`（每個機制）與
  `tests/test_octopath_style_battle.py`（機制本身的單元測試）；ARPG 在 `tests/test_arpg_demo.py`、
  `test_arpg_save_load.py`、`test_native_kernels.py`、`test_frame_limiter.py`；範本在
  `test_project_templates.py`。
- **實機驗證** `scripts/real_machine_validation.py OUT`：66 項真實視窗檢查（GPU、輸入、音訊、戰鬥、相機、
  選單、特效、匯入、打包 App、記憶體…）。有 4 項需要真人或手把，標示為未執行，不算通過。
- `scripts/arpg_demo_live_check.py <職業> OUT`：真實視窗，用腳本按鍵走完城鎮、轉職、技能樹、野外、Boss、
  礦坑，輸出截圖與 fps。
- `scripts/editor_ui_audit.py`：編輯器版面稽核（可 `--project`、`--also 1100x700`）。
- 量測：`scripts/arpg_stress.py`、`arpg_demo_measure.py`、`runtime_benchmark.py`。

---

## 7. 已知限制與還沒做的事

| 項目 | 狀態 |
| --- | --- |
| 圖示 | 暗黑 demo 的五個狀態圖示是程式畫的（`art.py` 的 `status_glyph`），技能圖示取自 CC0 資源包的相近圖；八方旅人的寵物沒有圖示（用縮寫）；沒有 AI 美術 |
| 原生 kernel 要每台機器編譯一次 | `python -m asteria.kernels.build_native`；沒編譯會退回 numpy |
| `CollisionWorld.from_scene` 沒有快取 | 2026-10-16 量測：100／500／2000 個碰撞器建一次 0.05／0.22／0.85 ms，每幀約一次，不是瓶頸；失效模型（啟用狀態、增刪、換場景、移動）的風險大於收益，**決定不做** |
| Enemy AI 的七欄規則表 | 窗口很窄時可橫向捲動（表格的正常行為） |
| 手把與實體鍵盤、音訊聽感與延遲 | 需要真人；沒有自動化 |
| 手感與平衡 | 數值是 demo 用的，需要有人實際玩過調整 |
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
| 畫面（D32–D33） | 地圖視窗（manifest `field.hud.gold`／`quest_tracker`）、低血量姿勢（`battle.weak_below`）、狀態染色（`StateDefinition.tint`） |
| 編輯器 | Game Start 分頁、新的 Game Systems 種類（Ability Slots、Pause Menu Entries）、種類下拉選單圖示、flag／paw／gauge 圖示 |

以上全部是資料驅動、沒設定就沒有影響；舊專案與存檔照常載入。

### 下一步的候選（沒有排序，要使用者決定）

1. 第三個範本（橫向平台動作、彈幕射擊）——使用者 2026-10-16 說先不用。
2. Web 匯出——使用者 2026-10-16 說先不用；要先做依賴盤點。
3. 專屬設計的技能圖示（不用 AI 生成）和八方旅人的寵物圖示。
4. 自動戰鬥、低血量姿勢門檻的編輯器表單（現在用 manifest 鍵）。

---

## 8. 工作方式（給之後接手的人）

- 直接在 `main` 上提交，不開分支；提交作者使用 Roger 的 GitHub 身分，且不得加入任何 `Co-Authored-By` trailer。
- 每行 Python ≤ 99 字元（skill：`.claude/skills/line-length`）。
- 新 clone 後執行 `git config core.hooksPath .githooks`；提交 hook 會阻擋共同作者 trailer，並確認 author 是 `rogerhao66666`。
- 每一批的結果寫進 `docs/audits/DECISION_LOG.md`（中文，六段式：做了什麼、證據、限制）。
- UI 和實機的東西一定在 Cocoa 真實視窗驗證，附截圖，放 `docs/audits/evidence/real_machine/`。
- 編輯器要好看：有顏色、有圖示、版面密但不擠；稽核腳本要乾淨。
