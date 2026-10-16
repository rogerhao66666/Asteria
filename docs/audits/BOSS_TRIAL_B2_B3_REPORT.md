# Boss Trial demo — B2（引擎缺口）與 B3（demo 資料）批次報告

日期：2026-10-16　狀態：**未 commit**；真實視窗（Cocoa）驗證尚未做（B4）。

## 1. Changed Files
引擎：`gameplay/abilities.py`（hit 的 `checks`／`kill`）、`runtime/game_session.py`（逐下檢查與即死、
`refine_equipment`、`socket_item`／`unsocket_item`、`points_per_level`、等級傳入 build、
`hit_check`／`kill` 戰鬥記錄）、`rpg/refine.py`（新）、`rpg/items.py`（精煉欄位、可鑲嵌道具欄位）、
`rpg/actors.py`（`ClassDefinition.level_growth`、`refine_rules`）、`rpg/resolved_build.py`、
`runtime/world_command_handlers.py`（`GRANT_EXPERIENCE`、`REFINE_EQUIPMENT`、`SOCKET_ITEM`、
`UNSOCKET_ITEM`、`UPGRADE_EQUIPMENT`）、編輯器（`game_systems_authoring.py` Weapon Refine 表單、
hit 範本、職業編輯保留 `level_growth`／`icon_id`）。
Demo：`reference_projects/boss_trial_demo/`（`build_project.py`、`trial_content.py`、`trial_art.py`、
`run_trial_smoke.py`、產生的專案與素材）。
測試：`test_hit_checks_and_kill`、`test_refine`、`test_socket_items`、`test_class_level_growth`、
`test_gear_world_commands`、`test_boss_trial_demo`，並擴充 `test_game_systems_d26`。

## 2. Requirement Coverage
| 要求 | 狀態 |
|---|---|
| 多段、爆擊、迴避 | 每下攻擊可掛 `checks`；爆擊與迴避由互動規則決定效果 |
| 即死 | hit 的 `kill`：機率、免疫標籤、免疫時改扣最大值比例（作者可選） |
| 吸血、護盾、增益、先制 | 既有（`lifesteal_stat`、ward 狀態、增益狀態、`preemptive_chance`），demo 已用 |
| 屬性、異常狀態 | 5 屬性、毒／燃燒／流血／睡眠／暈眩／冰凍／沉默等 |
| 技能樹（暗黑／流放／楓之谷／魔獸深度） | 3 職業樹共 37 節點＋屬性樹：多階層節點、前置、任一前置、互斥關鍵節點、JP／AP／屬性點花費 |
| 職業點 | `JobPointRules`（每場／每敵人，副職 50%） |
| 升級配點、職業每級成長 | `points_per_level`、`level_growth`（騎士 ATK 成長高於祕法師） |
| 多職業／多武器切換 | 3 職業（`SET_CLASSES`）、雙武器欄、6 種武器、獨特武器 |
| 卡片、寶珠、武器升級 | 3 個鑲嵌孔（寶珠返還、卡片消耗）、成長圖（覺醒、互斥路線、進化）、+N 精煉、耐久 |
| Boss 機制 | 3 階段（血量比例）、姿態（防禦／狂暴）、召喚、護盾破防、狀態、即死、吸血 |
| 武器攻擊時疊 icon | **取消**：NinjaGreen 的攻擊動畫自帶武器，不再疊 icon |
| 外部武器 icon | **未做**（B5） |

## 3. Tests Executed
全套 `pytest`：2812 項通過；`ruff check`、E501 全過；`editor_ui_audit` 0 缺陷（精煉表單截圖
`evidence/ui_audit/b2_refine_rules_form.png`）。

## 4. Integration Evidence
`run_trial_smoke.py`：經 `GameSessionRuntime` 用世界指令準備英雄（配點、升級、精煉、鑲嵌、成長、
轉職），再打 6 場。實際命中：爆擊 48、迴避 8、即死判定 3（皆被 Boss 免疫條款擋下）、Boss 三階段、
兩種姿態、破防、召喚、14 種狀態、吸血回復 5036、玩家技能 23 種、Boss 招式 11 種。
**這是腳本化的 session 驗證，不是真實視窗。**

## 5. Remaining Gaps
- 真實視窗（Cocoa）未驗證：戰鬥畫面、KnightGold 動作觀感、場景 NPC 互動。
- 即死「成功擊殺」只在單元測試證明；demo 的試玩中只出現被免疫。
- 反擊（`ReactionDefinition`）已傳進戰鬥，但可玩路徑沒有觸發它：Boss 與英雄的反擊目前沒有。
- 鑲嵌／精煉只有世界指令與 session API，沒有專用畫面。
- 經驗曲線仍是線性（`level_threshold` 固定）。
- 數值未經真人試玩調整；參考專案的 `broken` 狀態原本用不存在的 `round.end` 觸發，已在本 demo 改掉，
  但 octopath 範本仍有同樣設定，需另行決定。
- 外部武器／裝備 icon 與攻擊疊 icon 尚未做。

## 6. Closure Status
B2：實作與單元／整合測試完成，未達 A（缺真實視窗）。B3：資料與腳本化整合完成，未達 A。

---
## B4 追加（真實視窗，2026-10-16）
`scripts/boss_trial_live_check.py`：Cocoa 真實視窗、真實按鍵，1280×720。結果 `PASS`
（`evidence/boss_trial/results.json`，截圖 `trial_*.png`、`contact_sheet.png`）。實測：指令選單、
普通攻擊、多段技 flurry、神技 sunburst、Boss 三階段
（opening／ascent／last_stand）、破防標示、勝利畫面。
使用者回饋與處理：畫面「有點怪」→ Boss 名稱改 Vaelor（原名被縮寫成
VCWarlord）、武器 icon 放大；怪血量太高 → 45000 降為 24000、防禦 90→70（腳本 6 場仍打到三階段）。
**美術改為 NinjaGreen（使用者決定）：** 真動畫（idle／attack／hit／dead／item／roll 逐格）、攻擊幀畫入套件的 Katana 層；
英雄與 Boss 用同一像素比例，不再刻意放大。換武器時動畫仍是 Katana，對應武器由頭上 icon 表示。
**仍待人看：** 數值手感與觀感；外部武器 icon
（B5，等你決定下載，見下）。

### 技能特效（使用者要求「技能用對應的特效」）
每個技能各自的動作序列指定特效：火／冰／雷／光／暗屬性用對應的元素特效，劍／斧／匕首／矛用不同斬擊，
多段技每一下一個特效，防禦／增益用護盾與光環，召喚用魔法陣，毒用煙。19 種特效取自 CC0 的 Ninja Adventure
`FX/`。`scripts/boss_trial_fx_check.py` 在真實視窗逐一施放 15 個技能並截圖（`evidence/boss_trial/fx_*.png`、
`fx_contact_sheet.png`）。其中 cleave、assassinate、attack_sword 截圖時特效恰好在兩幀之間，沒拍到；
其餘都看得到各自的特效。

### 版面與動作（使用者回饋後的最終版）
- 版面與八方旅人 demo 相同：回合條在上、右側只列角色的狀態、指令選單貼在行動角色左邊（每回合位置一致）。
  敵人不顯示名稱、血條與面板（新增版面選項 `hidden_zones`，只留腳下的護盾／弱點格）。
- 攻擊會衝到實際目標前（打 Boss 就到 Boss 面前，打小怪就到小怪面前）、揮砍、退回（新增 `move` 動作通道；
  停在目標體型邊緣）。
- 精靈表可用 `body_height` 告訴引擎角色本體高度，選單依本體擺放；忍者畫布已裁到刚好包住動作。
- 以上都在 Cocoa 真實視窗截圖確認（`evidence/boss_trial/`）。

### 真實視窗穩定度
`boss_trial_live_check.py` 先前偶發失敗，原因是驗證腳本用逐步扣血硬凑三階段、結果看運氣；已改成確定性流程
（每看到一個階段就把 Boss 血量設到下一階段門檻）。改後連跑 6 次全 PASS。這只證明腳本穩定，不代表手感。
