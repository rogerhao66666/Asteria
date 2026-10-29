# ARPG 設計與分批計畫（D22）

**日期：** 2026-10-13
**狀態：** **已核准**（2026-10-13），從 A1 開始實作。
**依據：** `ASTERIA_SPEC.md` §20 Real-Time ARPG Framework、§35 ARPG Stress Test、§36 Starter Projects；DECISION_LOG D21（計算核心層）。

---

## 1. 已確認的決定（2026-10-13）

| 問題 | 決定 |
|---|---|
| 解除 ARPG 延後 | 解除。原因是 D21-2 時功能 closure 和自動化驗證都已完成，只剩手動和實機項目 |
| 視角 | **俯視和橫向兩種都支援**，作者每個場景自己選。戰鬥核心只寫一次，兩種視角共用 |
| 形式 | 通用功能放進引擎，另外做一個 demo 專案 `reference_projects/arpg_demo`，跟 party_rpg_demo 一樣 |
| Demo | 一個專案裡有兩種區域：俯視的野外和橫向的地城。**玩法是經典的動作 RPG**：打怪掉寶、選職業、技能樹，這些系統也一起做進引擎（2026-10-13 追加） |
| 橫向素材 | 已下載 Kenney「Pixel Platformer」1.2（CC0，kenney.nl，260 KB）到 git-ignored 的 `local_reference/free_assets/kenney_pixel-platformer/`；複製進 repo 的檔案要記錄在 CREDITS |
| 範圍 | 完整核心：攻擊判定、無敵幀、擊退、硬直、投射物、敵人 AI、受傷與死亡；加一個壓力測試場景，先量測效能 |
| 流程 | 先寫這份設計文件，核准後再一批一批連續做 |

## 2. 現在已經有的東西

| 系統 | 位置 | ARPG 可以直接用的部分 | 不足 |
|---|---|---|---|
| 角色控制器 | `runtime/character_control.py` `CharacterController2DComponent` | `mode=topdown/side`；重力、跳躍、落地偵測、撞牆和撞天花板 | 沒有角色朝向；橫向少了離開平台後的起跳寬限（coyote time）、提早按跳的記憶（jump buffer）、放開就跳得比較低、斜坡和梯子；沒有衝刺和擊退速度 |
| 單向平台 | `runtime/collision.py` `Collider2D.one_way` | 可以從下面往上跳穿 | 不能按下鍵往下穿過 |
| 攻擊判定 | `HitboxSystem`、`Hitbox2D`、`Hurtbox2D` | 陣營判定、同一次攻擊對同一目標只打一次、無敵幀 | 判定框不會跟著角色朝向翻轉；每個攻擊框和每個受擊框逐一比對（O(n×m)），用的是 Python 物件；打中之後**沒有任何後續**（傷害、擊退都沒有） |
| 動作時間軸 | `runtime/entity_actions.py`、`gameplay/action_timeline.py` | 動畫、位移、判定框、無敵幀、取消窗口、連段窗口、VFX/音效/鏡頭 cue | 沒有輸入接上它；沒有「攻擊招式」這種資料把時間軸和傷害綁在一起 |
| 行為樹 | `runtime/behavior_tree.py`、編輯器 `behavior_tree_widget.py` | 選擇器、序列、冷卻、追擊、逃跑、巡邏、遊蕩、等待 | 沒有「攻擊」「保持距離」「射擊」節點；巡邏只有俯視版，橫向走到平台邊緣不會轉身 |
| 場景 AI、生怪區 | `runtime/field_ai.py` | 生怪區（波次、重生、稀有種） | 碰到敵人就進回合制戰鬥，沒有即時戰鬥模式 |
| 數值、公式、效果 | `gameplay/stats.py`、`formulas.py`、`effects.py`、`tags.py` | 通用數值、資源（HP/MP）、可編輯的公式、標籤 | 可以直接用 |
| 技能 | `gameplay/abilities.py` `AbilityDefinition` | 消耗、目標規則 | 冷卻只有回合制的 `cooldown_turns`，要加秒數版 |
| 掉落、合成、裝備 | `rpg/drop_tables.py`、`rpg/composition.py`、`rpg/items.py`、`rpg/equipment_growth.py`、`rpg/equipment_sets.py` | 掉落表（權重、保底、幸運）、合成配方、裝備欄位、鑲嵌孔、套裝、裝備成長、每件裝備有自己的 `instance_id` | 場景裡沒有可撿取的掉落物；**沒有隨機詞綴**（同一件裝備每次掉出來都一樣）；稀有度是寫死在程式裡的固定清單，作者不能自己加 |
| 職業、技能樹 | `rpg/actors.py` `ClassDefinition`、`rpg/progression_graph.py`、`rpg/progression.py`、`rpg/resolved_build.py` | 職業、等級成長；技能樹節點有等級上限、每級花費、前置條件、互斥群組，獎勵可以是數值、技能、被動；`resolve_actor_build` 把職業、裝備、技能樹合成最終數值 | 目前只有回合制在用；技能等級不會影響 ARPG 技能的傷害和冷卻；沒有 ARPG 的技能快捷列 |
| 鏡頭 | `runtime/camera.py` `CameraFollow2D`、`CameraDirector` | 死區、平滑、前瞻、震動 | 可以直接用；橫向區域只需要給一組預設值 |
| 計算核心 | `asteria.kernels` | `aabb_pairs`（同一組框兩兩比對）、粒子 | 沒有「兩組框互相比對」，也沒有投射物 |
| 美術 | `local_reference/free_assets/ninja_adventure`（CC0） | 俯視角色、怪物、Boss、斬擊和投射物特效 | **沒有授權清楚的橫向角色素材**（見 §8 決定 1） |

## 3. 架構原則

0. **引擎是通用的，demo 只是其中一種用法（2026-10-13 使用者指示）。** 動作 RPG 玩法只是因為它是有名的 ARPG 才拿來做 demo；引擎不能只支援這一種玩法。所有系統（掉寶、詞綴、職業、技能樹、戰鬥、AI、介面）都不寫死任何一款遊戲的規則、名稱、數值或美術風格。作者的程式、想法、美術、玩法都不受限制；能支援的就支援，做不到的寫成擴充點（資料選項、事件、腳本 hook），不寫成限制。demo 專有的東西只放在 `reference_projects/arpg_demo` 的資料裡。
1. **戰鬥核心和視角無關。** 判定、傷害、擊退、投射物、AI 節點都不認識「俯視」或「橫向」。和視角有關的只有控制器、朝向翻轉和 AI 的移動方式。
2. **所有規則都是作者可以改的資料，編輯器裡也改得到**（D20-1「引擎不限制作者」）。凡是兩種做法都說得通的，例如擊退方向、打擊停頓、受傷後的無敵，一律做成選項，預設值維持現有行為。
3. **熱點要能用陣列一次算完。** 每幀的攻擊框和受擊框蒐集一次，交給 kernel 一次比對。投射物**不是** entity，而是存在 `ProjectileStore` 的欄位陣列裡，跟粒子一樣，這樣 500 顆才跑得動。python 參考實作永遠存在；numpy 版的結果必須完全相同。
4. **先量測，再決定要不要寫 native。** 壓力場景放在第 2 批就做，之後每一批都量一次。C++ 只在量到瓶頸、而且 numpy 解決不了時才提。
5. **不新增「雙模式」切換。** ARPG 是場景層級的選項 `combat_mode`：`encounter` 是現在的碰到就進回合制，`action` 是即時戰鬥。同一個專案可以有兩種場景，但**不做**隊伍在兩種戰鬥之間轉換這種 Dual-Mode 功能。

### 3.1 核心存放方式：欄位陣列（D22-C1、C2，2026-10-13 使用者決定先做）

- 每個 entity 在它所在的場景有一個 slot。標上 `@column_storage` 的元件，數字欄位（float、int、bool，加上它列出的執行期欄位）存在場景的欄位陣列裡（`array.array`，以 slot 為索引）。
- 遊戲程式、腳本、Inspector、存檔照舊用屬性讀寫（`transform.x = 3`），屬性會直接讀寫欄位。系統則可以一次讀寫整個欄位：python kernel 直接用陣列，numpy 用 `frombuffer` 共用同一塊記憶體，不複製。
- 元件不在場景裡時（建立中、復原用的暫時移除、等待加入），數值留在元件自己身上；加入場景時搬進欄位，移出時搬回來。專案檔格式不變，numpy 仍然是選用。
- 文字欄位和 `enabled` 維持一般屬性；`facing` 對外仍是文字，實際存成整數欄位 `facing_code`。
- 場景有各元件型別的索引：`query` 不再掃描所有 entity，順序仍然是場景順序。
- 現在用欄位存放的元件：Transform、Collider2D、CharacterController2D、Hitbox2D、Hurtbox2D。之後的新系統（例如 A4 的敵人 AI）也照這個方式做。

## 4. 戰鬥流程

```
輸入 / AI ─▶ 技能（AbilityDefinition + 秒數冷卻 + 消耗）
         ─▶ 攻擊招式 AttackDefinition ─▶ 動作時間軸（起手 → 判定 → 收招，取消窗口和連段窗口）
                                      └▶ 投射物 cue ─▶ ProjectileStore（kernel）
每幀：控制器移動 ─▶ 蒐集攻擊框、受擊框、投射物框 ─▶ kernel 兩組框互相比對
      ─▶ HitEvent（排序固定）─▶ 傷害結算 HitResolution
           傷害公式（ValueFormula + 標籤，例如 Element.Fire）
           韌性 → 硬直、擊退、打擊停頓、受傷後無敵
           HP ≤ 0 → 死亡 → 掉落表 → 場景掉落物 → gameplay_event 給事件程式
      ─▶ 呈現：受傷閃爍、傷害數字、頭上的敵人 HP、鏡頭震動、VFX/音效
```

### 新增的資料（都會進編輯器）

| 紀錄 | 主要欄位 |
|---|---|
| `AttackDefinition` | 使用的動作時間軸、判定框大小和位置（會隨朝向翻轉）、傷害公式、標籤、韌性傷害、擊退（力道、方向模式：依攻擊者朝向／依命中方向／固定方向）、打擊停頓（秒數，作用範圍：全畫面／只有雙方）、命中後給目標的無敵秒數、每次攻擊可以打中幾個目標 |
| `ProjectileDefinition` | 速度、壽命、重力、穿透次數、碰牆行為（消失／反彈／停住）、追蹤強度、判定框、命中時使用哪個 `AttackDefinition`、外觀（沿用現有 `projectile` 精靈類型） |
| `CombatantComponent` | 陣營、HP 和其他資源、韌性上限與回復、硬直時間、受傷後無敵、死亡行為（移除／播動畫／觸發事件）、掉落表 |
| `ActionCombatComponent`（玩家） | 輸入動作對應的技能（攻擊、閃避、技能 1–4）、連段表、鎖定目標（關閉／最近的敵人／手動切換） |
| `AbilityDefinition` | 新增 `cooldown_seconds`（預設 0，舊資料不受影響） |
| `CharacterController2D` v2 | `facing`；橫向的起跳寬限、跳躍記憶、短跳、按下鍵穿過單向平台；衝刺；外力速度（擊退用）。新欄位的預設值都和現在的行為相同 |
| 場景設定 | `combat_mode`：`encounter`（預設）／`action` |

## 5. 分批計畫

每一批都會照固定格式回報，在 DECISION_LOG 記錄為 D22-n。單元測試通過**不代表**功能完成；每批都要有 runtime 整合證據，有畫面的批次要有實機紀錄。

| 批次 | 內容 | 整合證據 |
|---|---|---|
| **A1 戰鬥核心** | `CombatantComponent`、`AttackDefinition`、傷害結算（公式、標籤、韌性、硬直、擊退、打擊停頓、受傷後無敵、死亡、掉落）；判定框隨朝向翻轉；控制器 v2 的 `facing` 和外力速度 | 在 `GameSession` 場景中，用時間軸攻擊一個敵人：扣血、被擊退、硬直、死亡、掉落 |
| **A2 投射物和壓力場景** | `ProjectileStore`（python 和 numpy 兩套，結果相同）；kernel `aabb_cross_pairs`（兩組框互相比對）；`HitboxSystem` 改用 kernel，但 `HitEvent` 和順序不變；**壓力場景 300 隻敵人 + 500 顆投射物**，加進 `scripts/runtime_benchmark.py` | 量測表（python／numpy、每個區段的毫秒數）；結果用來決定 A4 要不要把敵人移動也改成陣列 |
| **A3 玩家動作** | 輸入接上攻擊、連段、取消、閃避（加無敵幀）、衝刺、技能（秒數冷卻、消耗 MP 或其他資源）、鎖定目標 | 在 PlayableTestRuntime 中用模擬輸入打出三段連擊、閃避穿過攻擊 |
| **A4 敵人和 Boss AI** | 行為樹新節點：範圍內攻擊、保持距離、射擊、繞圈、橫向巡邏（到邊緣轉身）、跳躍、Boss 分階段（依 HP 切換子樹）；接觸傷害；生怪區在 `action` 場景生出即時戰鬥的敵人 | 近戰、遠程、Boss 三種敵人各打一場，有重播紀錄 |
| **A5 橫向手感** | 起跳寬限、跳躍記憶、短跳、按下鍵穿過平台、斜坡、梯子；橫向鏡頭預設值 | 橫向測試場景跑一段固定輸入，位置逐幀比對 |
| **A6 掉寶** | 稀有度改成作者定義的資料（名稱、顏色、詞綴數量、掉落權重），預設就是現在的清單；**隨機詞綴**（`AffixDefinition`：前綴／後綴、可出現的裝備類型、物品等級範圍、數值範圍、權重、互斥群組）；掉出來的裝備有物品等級、稀有度、擲出的詞綴，存檔保存；唯一裝備（固定詞綴）；金幣；藥水；場景掉落物（依稀有度上色的名稱標籤、撿取範圍、自動撿取的篩選選項）；背包預設是清單，格子背包是選項 | 殺 1000 隻怪的固定亂數種子掉落統計（稀有度分布符合權重）；裝備詞綴後 `resolve_actor_build` 的數值正確；存讀檔後詞綴不變 |
| **A7 職業和技能樹** | 開場選職業；殺怪得經驗、升級、技能點；ARPG 技能接上技能樹節點，技能等級可以影響傷害、冷卻、消耗、投射物數量（每項都由公式決定，作者可以改）；技能快捷列；重置技能點（選項，可設定花費） | 兩個職業各從 1 級升到 10 級，點不同的技能樹分支，同一個敵人的擊殺時間不同 |
| **A8 遊戲整合和介面** | 場景 `combat_mode`；玩家 HP/MP 條、經驗條、技能快捷列和冷卻、頭上的敵人 HP、傷害數字、死亡與重生、背包和裝備畫面、技能樹畫面；存檔 | 實機（Cocoa 視窗）一輪：進場、戰鬥、升級、點技能、撿裝備、換裝備、死亡、重生、存讀檔 |
| **A9 編輯器** | 攻擊招式、投射物、戰鬥角色、稀有度、詞綴的工作區；行為樹新節點加進節點清單；場景 `combat_mode`；判定框在場景中的預覽；Problems 檢查（例如時間軸缺判定框 cue、投射物沒有對應攻擊招式） | 在編輯器中建立一個新的敵人和攻擊並在 playtest 打到它；Cocoa 截圖 |
| **A10 Demo 專案** | `reference_projects/arpg_demo`，動作 RPG 玩法：城鎮（商人、合成）、俯視野外（近戰和遠程小怪、精英怪、一個 Boss），加上橫向地城（平台、梯子、遠程敵人、Boss）；三個職業（戰士、遊俠、法師）各有自己的技能樹；打怪掉寶、隨機詞綴、套裝、唯一裝備；README 說明每條規則在哪筆資料 | 實機：三個職業都進過兩個區域，打倒兩個 Boss，換上掉落的裝備 |
| **A11 收尾量測** | 實機跑壓力場景，用 python／numpy 各跑一次；依結果寫出下一步（不需要／numpy 擴大範圍／提出 C++ 提案） | 量測表寫進 DECISION_LOG |

A1–A2 不需要美術。A3 起開始用素材：俯視用 Ninja Adventure（CC0），橫向用 Kenney Pixel Platformer（CC0）。

## 6. 效能目標

- 60 fps 一幀是 16.7 ms。壓力場景（300 隻敵人 + 500 顆投射物）的**戰鬥模擬**（AI、控制器、投射物、判定、結算）目標在 numpy 下 ≤ 6 ms，剩下的留給繪製。
- python 參考實作不設目標，只記錄數字。
- 達不到目標時，先看量測結果是哪一段慢：如果是逐個 entity 讀寫位置，就把那一段改成陣列；不先動 C++。

## 7. 不在這次範圍

- 隊伍在回合制和即時戰鬥之間轉換（Dual-Mode）
- 尋路（A* 或 navmesh）。敵人用現有的直線靠近加碰撞滑動；需要時另外提案
- 大型 MMO 服務（帳號、公開配對、持久世界）；通用多人連線能力另見 `MULTIPLAYER_DESIGN.md`，ARPG 遊戲端的多人 Boss 戰整合仍未完成
- 物理引擎、旋轉的判定框（只用 AABB 和圓）
- C++ kernel（只在 A11 量到瓶頸後才提案）

## 8. 決定紀錄

- 2026-10-13：核准計畫；下載 Kenney Pixel Platformer；demo 改成動作 RPG，掉寶、職業、技能樹一起做（新增 A6、A7，原本的 A6–A9 順延成 A8–A11）。
- 「不在範圍」不變：沒有尋路。動作 RPG 小怪用直線靠近加碰撞滑動就夠了；地形複雜到會卡住時再提案。
- 2026-10-14：使用者明確多人連線能力應供各類 Asteria 遊戲導入；D22 原範圍仍指 ARPG 計畫批次。通用網路原型已開始實作；ARPG Demo 的多人 Boss 戰仍是待完成的遊戲端整合案例，見 `MULTIPLAYER_DESIGN.md`。
