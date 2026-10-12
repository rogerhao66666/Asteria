# ARPG 設計與分批計畫（D22）

**日期：** 2026-10-13
**狀態：** 設計提案，**等待核准**。核准前不寫實作程式。
**依據：** `ASTERIA_SPEC.md` §20 Real-Time ARPG Framework、§35 ARPG Stress Test、§36 Starter Projects；DECISION_LOG D21（計算核心層）。

---

## 1. 已確認的決定（2026-10-13）

| 問題 | 決定 |
|---|---|
| 解除 ARPG 延後 | 解除。原因是 D21-2 時功能 closure 和自動化驗證都已完成，只剩手動和實機項目 |
| 視角 | **俯視和橫向兩種都支援**，作者每個場景自己選。戰鬥核心只寫一次，兩種視角共用 |
| 形式 | 通用功能放進引擎，另外做一個 demo 專案 `reference_projects/arpg_demo`，跟 octopath_demo 一樣 |
| Demo | 一個專案裡有兩種區域：俯視的野外和橫向的地城 |
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
| 掉落、合成、裝備 | `rpg/drop_tables.py`、`rpg/composition.py`、`rpg/equipment_growth.py` | 掉落表、合成配方、裝備成長 | 場景裡沒有可撿取的掉落物 |
| 鏡頭 | `runtime/camera.py` `CameraFollow2D`、`CameraDirector` | 死區、平滑、前瞻、震動 | 可以直接用；橫向區域只需要給一組預設值 |
| 計算核心 | `asteria.kernels` | `aabb_pairs`（同一組框兩兩比對）、粒子 | 沒有「兩組框互相比對」，也沒有投射物 |
| 美術 | `local_reference/free_assets/ninja_adventure`（CC0） | 俯視角色、怪物、Boss、斬擊和投射物特效 | **沒有授權清楚的橫向角色素材**（見 §8 決定 1） |

## 3. 架構原則

1. **戰鬥核心和視角無關。** 判定、傷害、擊退、投射物、AI 節點都不認識「俯視」或「橫向」。和視角有關的只有控制器、朝向翻轉和 AI 的移動方式。
2. **所有規則都是作者可以改的資料，編輯器裡也改得到**（D20-1「引擎不限制作者」）。凡是兩種做法都說得通的，例如擊退方向、打擊停頓、受傷後的無敵，一律做成選項，預設值維持現有行為。
3. **熱點要能用陣列一次算完。** 每幀的攻擊框和受擊框蒐集一次，交給 kernel 一次比對。投射物**不是** entity，而是存在 `ProjectileStore` 的欄位陣列裡，跟粒子一樣，這樣 500 顆才跑得動。python 參考實作永遠存在；numpy 版的結果必須完全相同。
4. **先量測，再決定要不要寫 native。** 壓力場景放在第 2 批就做，之後每一批都量一次。C++ 只在量到瓶頸、而且 numpy 解決不了時才提。
5. **不新增「雙模式」切換。** ARPG 是場景層級的選項 `combat_mode`：`encounter` 是現在的碰到就進回合制，`action` 是即時戰鬥。同一個專案可以有兩種場景，但**不做**隊伍在兩種戰鬥之間轉換這種 Dual-Mode 功能。

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
| **A6 遊戲整合和介面** | 場景 `combat_mode`；玩家 HP/MP 條、技能冷卻圖示、頭上的敵人 HP、傷害數字、死亡與重生、撿取掉落物；存檔 | 實機（Cocoa 視窗）一輪：進場、戰鬥、死亡、重生、撿取、存讀檔 |
| **A7 編輯器** | 攻擊招式、投射物、戰鬥角色的工作區；行為樹新節點加進節點清單；場景 `combat_mode`；判定框在場景中的預覽；Problems 檢查（例如時間軸缺判定框 cue、投射物沒有對應攻擊招式） | 在編輯器中建立一個新的敵人和攻擊並在 playtest 打到它；Cocoa 截圖 |
| **A8 Demo 專案** | `reference_projects/arpg_demo`：俯視野外（遠近戰小怪、一個 Boss），加上橫向地城（平台、梯子、遠程敵人、Boss）；可以合成、可以換裝備；README 說明每條規則在哪筆資料 | 兩個區域都在實機打完，Boss 也打倒 |
| **A9 收尾量測** | 實機跑壓力場景，用 python／numpy 各跑一次；依結果寫出下一步（不需要／numpy 擴大範圍／提出 C++ 提案） | 量測表寫進 DECISION_LOG |

A1–A2 不需要美術。A3 起開始用素材；橫向素材的來源見 §8 決定 1。

## 6. 效能目標

- 60 fps 一幀是 16.7 ms。壓力場景（300 隻敵人 + 500 顆投射物）的**戰鬥模擬**（AI、控制器、投射物、判定、結算）目標在 numpy 下 ≤ 6 ms，剩下的留給繪製。
- python 參考實作不設目標，只記錄數字。
- 達不到目標時，先看量測結果是哪一段慢：如果是逐個 entity 讀寫位置，就把那一段改成陣列；不先動 C++。

## 7. 不在這次範圍

- 隊伍在回合制和即時戰鬥之間轉換（Dual-Mode）
- 尋路（A* 或 navmesh）。敵人用現有的直線靠近加碰撞滑動；需要時另外提案
- 多人連線、物理引擎、旋轉的判定框（只用 AABB 和圓）
- C++ kernel（只在 A9 量到瓶頸後才提案）

## 8. 需要你決定

1. **橫向素材。** 本機的素材裡沒有授權清楚的橫向角色。`free_pixel_art_xiaosuzaoshui` 有橫向的蘑菇和史萊姆，但找不到授權檔，所以不用。建議下載 **Kenney「Pixel Platformer」**（CC0，和現有 Kenney 素材同一來源）放進 git-ignored 的 `local_reference/free_assets/`，下載前會再跟你確認檔名和大小。另一個選項是橫向地城先用俯視素材的側面幀。
2. **核准這份計畫**，然後從 A1 開始一批接一批連續做，只有遇到大的架構變更、和 SPEC 衝突或需要刪除功能時才停下來問你。
