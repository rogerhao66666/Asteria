# 缺口清單（對照 YEP 258 個插件與 Godot）

**日期：** 2026-10-16　**方法：** 取得 `[YEP] Full Collection.zip`（518 個 `.js`，含 Free 目錄的重複項，
去重後約 150 個系統）與 Godot master（淺層 clone），逐項對照 Asteria 的 `src/asteria`。

**證據強度（請先讀）：** 這份清單以「關鍵字搜尋 `src/asteria` ＋ 讀相關檔案」得出。
搜尋不到只代表「命名上找不到」，不代表功能一定不存在；標「待查證」的項目，實作前要先讀碼確認。
沒有逐一執行 YEP 插件，也沒有逐行比對 Godot 原始碼，只比對功能類別。

## A. 確認缺失（`src/asteria` 內找不到對應實作）

| # | 項目（來源） | 說明 | 打算 |
|---|---|---|---|
| A1 | 寵物進化、學技能、親密度 | `rpg/pets.py` 沒有；D25 限制段也寫沒做 | 做 |
| A2 | 寵物成為戰鬥單位 | 目前只提供數值給技能 | 做成可選項（`battle_unit`） |
| A3 | Game Start 編輯表單 | 只有資料模型與驗證 | 做 |
| A4 | 隊伍共用量表（PartyLimitGauge） | 無 party 層級共用資源 | 做 |
| A5 | 商店條件價格／條件顯示（CondShopPrices、HideShowShopItems） | `ShopEntry` 只有固定 `buy_prices`、`stock` | 做 |
| A6 | 依 Region 設定戰鬥背景（RegionBattlebacks） | 只有範本 manifest 的背景 | 做 |
| A7 | 技能類型／多類型（MultiTypeSkills、SkillCore 的 skill type） | 沒有 skill type 概念 | 待查證後做 |
| A8 | 狀態分類與依分類解除（StateCategories） | 只有 debugger 的 `remove_state` | 做 |
| A9 | 命中／迴避參數（HitAccuracy，含 xparam/sparam 公式控制） | 只有通用機率檢查與暴擊 | 待查證後做 |
| A10 | 自動戰鬥 AI（ActorAutoBattleAI） | 無 | 做 |
| A11 | 裝備技能槽與層級（EquipBattleSkills、EquipSkillTiers） | 無 | 待查證後做 |
| A12 | 道具升級槽／附魔（ItemUpgradeSlots、AttachAugments） | 只有 `unlocked_sockets` 成長 | 待查證後做 |
| A13 | 技能學習系統（SkillLearnSystem：用 JP 學技能） | 有職業點，沒有學習面板 | 做（可與 A1 共用） |
| A14 | 技能獎勵（Z_SkillRewards）、演員變數（ActorVariables） | 無 | 待查證後做 |
| A15 | 事件系統：移動路徑指令、事件複製／變形、事件生成、事件點擊觸發、事件圖示／氣球 | 世界指令中只有 `MOVE`、`MOVE_NPC`、`WALK_TO`；沒有 MoveRoute | 做 |
| A16 | 地圖上的畫面：金錢視窗、狀態視窗、任務追蹤視窗（MapQuestWindow）、Gab 視窗 | 無或僅部分 | 待查證後做 |
| A17 | 戰鬥視覺：血條樣式、弱點姿勢、狀態特效、目標游標、戰鬥狀態視窗 | 無 | 待查證後做 |
| A18 | 載具（VehicleRestrict） | 無 | 不做（見 D） |
| A19 | 公共事件選單／按鈕觸發公共事件、可自訂主選單項目（MainMenuManager） | 無 | 做 |

## B. 已有，但範圍可能比 YEP 小（待查證）

戰鬥 BGM 控制、受傷音效、經驗升級成長效果、防具縮放（ArmorScaling）、
範圍效果（AreaOfEffect）、STB（只在 `battle_scheduler` 出現一次，是否完整未確認）、
訊息速度選項、存檔事件位置、自動存檔（`autosave` 僅 2 檔命中）。

## C. 已確認具備（D26–D30 與先前批次）

嘲諷、吸血、過度擊殺、次數限制、熟練度、先制／偷襲、偷竊、敵人等級與難度、ATB／CTB、勝利結算、
地板傷害／滑冰／腳步聲／限制通行、事件計時器、裝備耐久與暱稱、拆解、職業點、新遊戲＋、
訊息控制碼與翻譯、訊息記錄／音樂室／名單、地形鋪磚、尋路與 `WALK_TO`、2D 骨骼動畫
（含 DragonBones／Spine 匯入）、Picture 系統、裝飾物、戰鬥天氣、TP 模式、區域規則、
任務、合成、貨幣、副職業、技能冷卻、反射／吸收、敵人 AI 行為樹、寵物基礎（D25）。

## D. 對照 Godot

| 面向 | 狀態 |
|---|---|
| Tween／緩動、粒子、光照／遮擋、Camera2D、輸入映射、手把、UI 主題、計時器、訊號、復原、Profiler、Debugger | 有 |
| 場景／ECS、TileMap、導航（格狀 A*，非 navmesh） | 有（導航較簡） |
| AnimationTree／AnimationPlayer 概念 | 無同名物件；骨骼動畫與動作時間軸涵蓋部分用途，混合樹未做（待查證） |
| 音訊匯流排（Audio Bus） | 僅 1 檔命中，待查證 |
| 熱重載、遠端除錯 | 找不到 |
| 剛體物理 | **刻意不做**（只做 AABB 與圓形） |
| 3D | 不在範圍 |
| Web 匯出 | 有 7 檔提到 web，但 NEXT_STEPS 與路線圖尚未承諾；需先做依賴盤點 |

## 實作順序

1. 寵物：進化、學技能、親密度、可選戰鬥單位，加編輯器表單與測試。
2. Game Start 表單（含起始寵物）。
3. A4–A6、A8、A10、A19：每項先寫失敗測試。
4. A15 事件系統補強。
5. 待查證項目：讀碼確認後才開工，不確認不補造。

## 進度（2026-10-16，D31）

| 項目 | 狀態 |
|---|---|
| A1 寵物進化、學技能、親密度 | 完成：`PetEvolution`、`PetMove`、`affinity`；測試 `tests/test_pets_advanced.py` |
| A2 寵物戰鬥單位 | 完成，可選項（species `battle_unit`），預設關閉 |
| A3 Game Start 表單 | 完成：Database 工作區最後一個分頁；`tests/test_game_start_authoring.py` |
| A4 隊伍共用量表 | 完成：`shared_gauges`、`ResourceGain(shared=True)`、`change_party_gauge` |
| A5 商店條件價格與顯示 | 完成：`ShopEntry.visible_when`、`price_rules` |
| A6 依區域戰鬥背景 | 完成：`AreaRule.battle_background` |
| A8 狀態分類 | 完成：`category.<名稱>` 貢獻標籤、`remove_category`、`dispel` |
| A10 自動戰鬥 | 完成（啟發式）：`auto_battle_choice`／`auto_battle_act`；沒有編輯器設定介面 |
| A19 自訂暫停選單項目 | 完成：`MenuEntry`，Game Systems > Pause Menu Entries |
| A15 事件系統 | 部分：新增 `MOVE_ROUTE`、`SHOW_BALLOON`。**未做**：事件複製／變形／生成、事件點擊觸發、事件圖示 |
| A7、A9、A11–A14、A16、A17 | **未做**（待查證項目仍待讀碼確認） |
