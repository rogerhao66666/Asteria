# Asteria 使用手冊

**給遊戲作者的手冊。** 這本手冊說明怎麼用 Asteria 編輯器與引擎做一款遊戲：啟動編輯器、
做地圖與事件、填寫資料庫、設定戰鬥、選單、對話、操作與翻譯，然後試玩與匯出。最後一章列出
腳本可以使用的 Python API。

- 版本：2026-10-26 時的引擎與編輯器（決策紀錄 D85）。
- 英文版：[USER_MANUAL.en.md](USER_MANUAL.en.md)。
- 每張圖都是真實畫面：編輯器圖片取自 macOS（Cocoa）上開著 Full Verification 範例的編輯器
  視窗，介面語言為繁體中文；遊戲圖片是遊戲視窗的真實畫格。
- 引擎開發者請改讀 [`docs/ENGINE_HANDBOOK.md`](../ENGINE_HANDBOOK.md)。

## 目錄

1. [Asteria 是什麼](#1-asteria-是什麼)
2. [安裝與啟動編輯器](#2-安裝與啟動編輯器)
3. [專案的新增開啟與儲存](#3-專案的新增開啟與儲存)
4. [編輯器視窗](#4-編輯器視窗)
5. [地圖與場景](#5-地圖與場景)
6. [事件與事件程式](#6-事件與事件程式)
7. [資料庫](#7-資料庫)
8. [戰鬥](#8-戰鬥)
9. [選單與畫面](#9-選單與畫面)
10. [對話與選項](#10-對話與選項)
11. [輸入與操作](#11-輸入與操作)
12. [翻譯](#12-翻譯)
13. [試玩存檔與匯出](#13-試玩存檔與匯出)
14. [參考專案](#14-參考專案)
15. [給作者的 Python API](#15-給作者的-python-api)

---

## 1. Asteria 是什麼

Asteria 是用 Python（pygame-ce）寫的 2D RPG 引擎，編輯器用 PySide6 寫成。遊戲的一切都是
**專案檔裡的資料**，在編輯器裡編輯：地圖、角色、技能、道具、敵人、戰鬥規則、畫面版面與
翻譯。引擎本身沒有內建任何一款遊戲，範例只是示範資料。你可以做：

- 回合制隊伍戰鬥（側視、弱點、護盾與增幅），
- 生物戰鬥（捕捉、生物隊伍、寶可夢風格的畫面），
- 即時動作 RPG（俯視或橫向捲軸，含掉寶與技能樹），
- 以及介於兩者之間的任何玩法，因為規則是選項，不是程式碼。

編輯器沒有提供的功能，可以在 **程式碼** 工作區用 Python 腳本完成（第 15 章列出 API）。

全書會用到的三個詞：

| 詞 | 意思 |
| --- | --- |
| **專案** | 一個 `project.asteria.json` 及其資料夾（美術、音樂、`playable_test_manifest.json`、`saves/`）。 |
| **資料**（record） | 資料庫裡的一筆：一位角色、一個技能、一件道具、一個敵人、一場遭遇戰……每筆資料都有固定不變的內部 ID 和名稱。 |
| **事件程式** | 一串指令（對話、選項、開關、世界指令），在玩家與人交談、踏上某處或戰鬥到了某個時機時執行。 |

---

## 2. 安裝與啟動編輯器

> **不想裝 Python？** 改下載免安裝版 app：編輯器、試玩、匯出都在裡面，用它匯出的遊戲玩家也不用裝
> Python。見 [STANDALONE_APP.zh-TW.md](../STANDALONE_APP.zh-TW.md)。以下是原始碼安裝的步驟。

需要 Python 3.12 以上（3.13 可用）。在 Asteria 資料夾裡：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pygame,editor,mv,dev]"
```

啟動編輯器：

```bash
.venv/bin/asteria-editor
```

第一次啟動會開啟一份屬於你的 **Full Verification** 範例副本（一整款可以拿來學的小遊戲）。
副本放在你的使用者資料夾，所以參考專案本身永遠不會被改到。

其他常用指令：

```bash
.venv/bin/asteria-preview path/to/project.asteria.json
.venv/bin/asteria-export path/to/project.asteria.json OUTPUT_FOLDER --pyz
.venv/bin/asteria-export-web path/to/project.asteria.json OUTPUT_FOLDER --serve
```

`asteria-preview` 不開編輯器直接玩一個專案；兩個匯出指令見第 13 章。選用：
`.venv/bin/python -m asteria.kernels.build_native` 會編譯一次 C++ 加速模組（沒有它引擎也能跑）。

> 安靜執行：設定 `ASTERIA_MUTE=1` 可無聲遊玩（自動檢查用），網頁版則在網址加上 `?mute=1`。

**切換成中文介面**：編輯器預設是英文；選 **View ▸ Language ▸ 繁體中文**（中文介面下為
**檢視 ▸ 語言**）即可立即切換，見第 12 章。本手冊以下都用中文介面的名稱。

---

## 3. 專案的新增開啟與儲存

### 3.1 新專案

**檔案 ▸ 新專案…**（Ctrl+N）會把一個範本複製到新資料夾並開啟。對話框依序問範本、專案名稱、
資料夾。（這個對話框目前還沒有中文翻譯，會以英文顯示。）

![檔案選單](images/editor_zh_menu_file.png)

![新專案：選擇範本](images/editor_zh_dialog_new_project.png)

| 範本 | 內容 |
| --- | --- |
| Full Verification (Recommended) | 一整款可以拿來學的遊戲：四張地圖、有商店的城鎮、四人隊伍與職業和技能樹、屬性、護盾與破防、頭目、任務、製作，每一個編輯器頁面都有資料。 |
| Basic RPG (Small) | 一位英雄、兩種敵人、攻擊、火焰與治療；可玩的地圖與基本戰鬥。 |
| Party RPG (break and boost battles) | 弱點與護盾、增幅點數、職業、一隻寵物、調合、狀態與四種敵人。 |
| Action RPG (real-time loot and skill trees) | 即時戰鬥，含職業與技能樹、有稀有度和詞綴的掉寶、藥水、格子背包、有冷卻的技能列。 |
| Completely Empty | 沒有範例資料。 |

整個範本資料夾都會被複製，包括美術與授權檔。專案若有 `START_HERE.md`，**主控台** 面板會顯示
它（說明每條規則在編輯器的哪裡）。

### 3.2 開啟、儲存、匯入

| 選單項目 | 快捷鍵 | 作用 |
| --- | --- | --- |
| 檔案 ▸ 開啟專案… | Ctrl+O | 開啟一個 `*.asteria.json` 檔。 |
| 檔案 ▸ 儲存 | Ctrl+S | 儲存專案。 |
| 檔案 ▸ 另存新檔… | Ctrl+Shift+S | 以新檔名儲存。 |
| 檔案 ▸ 匯入 RPG Maker MV 專案… | | 把 RPG Maker MV 專案資料夾轉成新的 Asteria 專案。 |
| 檔案 ▸ 從素材庫匯入… | | 從內附的 CC0 `asset_library/` 複製美術到專案（會顯示每個素材包的授權；一個復原步驟）。 |
| 檔案 ▸ 匯出遊戲… | | 見第 13 章。 |

macOS 上快捷鍵用 ⌘ 取代 Ctrl。

### 3.3 專案資料夾裡有什麼

| 路徑 | 內容 |
| --- | --- |
| `project.asteria.json` | 專案本身：場景、資料庫、規則、版面、事件、翻譯。 |
| `playable_assets/`（或其他資料夾） | 專案用到的美術、音樂、字型。 |
| `playable_test_manifest.json` | 遊戲資料夾設定（標題、地圖與戰鬥的外觀）。請用 **執行 ▸ 遊戲資料夾設定…** 編輯，不要手改。 |
| `saves/` | 玩家的存檔（`slot1.asteria-save.json`……、`playtest_autosave.asteria-save.json`）。 |
| `scripts/` | 你在程式碼工作區寫的腳本。 |

---

## 4. 編輯器視窗

![編輯器的場景工作區](images/editor_zh_scene.png)

- **選單列**：檔案、編輯、檢視、預製物件、執行、說明。
- **工作區列**：場景、資料庫、戰鬥、演出、事件、程式碼、多人連線（Ctrl+1 … Ctrl+7，也在
  檢視 ▸ 工作區），接著是 **執行專案**、**停止** 與 **重設視圖**。
- **面板**（停駐視窗）：左邊是專案、圖塊、圖層；右邊是檢查器；下方是素材、主控台、除錯器、
  效能分析、問題。檢視 ▸ 面板 可重新打開關掉的面板，檢視 ▸ 重設版面 會把它們全部放回原位。

| 工作區 | 在這裡編輯 |
| --- | --- |
| 場景 | 地圖：圖塊、實體、預製物件（第 5 章）。 |
| 資料庫 | 遊戲資料、遊戲系統、敵人 AI、行為樹、即時戰鬥、遊戲開始（第 7 章）。 |
| 戰鬥 | 戰鬥規則：資源、狀態、行動順序、逃跑、勝利……（第 8 章）。 |
| 演出 | 戰鬥畫面、選單畫面、動畫、特效、操作（第 8、9、11 章）。 |
| 事件 | 實體事件、互動總覽、公用與戰鬥事件（第 6 章）。 |
| 程式碼 | 修改專案的 Python 腳本（6.6、第 15 章）。 |
| 多人連線 | 網路遊戲用的本機伺服器與訪客測試。 |

![檢視選單](images/editor_zh_menu_view.png)
![編輯選單](images/editor_zh_menu_edit.png)
![說明選單](images/editor_zh_menu_help.png)

**所有頁面共通的編輯方式**

- 每個變更都能復原：編輯 ▸ 復原（Ctrl+Z）與重做（Ctrl+Shift+Z），或每頁下方的 **復原** /
  **重做** 按鈕。
- 資料表單在你停止輸入片刻後（約三分之一秒）自動套用變更；引擎不接受的值會顯示為紅色且不套用。
- 說明文字放在提示框裡：把滑鼠停在欄位或區塊旁的 **ⓘ** 記號上。
- 檢視 ▸ 主題 切換配色；檢視 ▸ 語言 切換編輯器的語言（第 12 章）。
- 說明 ▸ 操作與快捷鍵 列出視埠與試玩的快捷鍵。

---

## 5. 地圖與場景

### 5.1 場景

每張地圖是一個 **場景**。**專案** 面板列出場景、預製物件與素材。對選取的場景可使用
編輯 ▸ 新增場景…、刪除場景、設為起始場景、重新命名…（F2）。新遊戲從 **資料庫 ▸ 遊戲開始**
指定的地方開始（7.5）；遊戲開始沒有指定場景時才使用起始場景。

### 5.2 繪製圖塊

打開 **圖塊** 面板。它顯示整張圖塊集；點一格或拖曳選一塊，然後在地圖上繪製。按住滑鼠時圖塊
就會出現在地圖上；放開算一個復原步驟。

| 工具 | 按鍵 |
| --- | --- |
| 選取 | S |
| 繪製 | B |
| 填滿 | G |
| 矩形 | R |
| 清除 | E |
| 從地圖吸取圖塊 | 右鍵 |
| 筆刷變小 / 變大 | `[` / `]` |

同一個面板裡的 **地形**、**區域**、**裝飾物** 分別繪製自動拼接地形、地圖區域與裝飾。**圖層**
面板決定繪製在哪一層（地面、牆、碰撞……）。

視埠：滑鼠滾輪以游標為中心縮放；方向鍵平移（或移動選取的實體，按住 Shift 移動更多）；
觸控板雙指平移、捏合縮放；Ctrl+0 重設視圖。檢視 ▸ 顯示攻擊與受擊判定框 會畫出即時戰鬥的判定框。

### 5.3 實體、元件與預製物件

放在地圖上的一切（玩家、人物、門、寶箱、鏡頭）都是由 **元件** 組成的 **實體**。在地圖或專案
面板中選取它；**檢查器** 把每個元件顯示成一個區塊（最上方可重新命名、開啟或關閉）。

| 編輯選單 | 作用 |
| --- | --- |
| 新增實體… | 新增一個空的實體。 |
| 從角色圖表放置角色… | 用角色圖表放置一個會走路的角色。 |
| 設定角色外觀… | 讓選取的實體使用某位角色的外觀。 |
| 新增元件… | 加入元件（碰撞、互動、遭遇、光源……）。 |
| 剪下實體 / 複製實體 / 貼上實體；複製實體（Ctrl+D，就地複製一份） | |
| 啟用 / 停用實體（Ctrl+E） | |
| 刪除選取項（Delete） | |

**預製物件** 選單把實體變成可重複使用的預製物件（從選取的實體建立預製物件…）、放置它
（放置預製物件…），以及把實例的變更推回預製物件或還原。

### 5.4 地圖區域

**資料庫 ▸ 遊戲系統 ▸ 地圖區域（區域、危險地帶）** 讓地圖的某些區域有自己的規則：音樂、
區域名稱看板、每步的隨機遇敵、地面傷害、濕滑地面、腳步聲、限制通行，以及玩家進入時的事件。

---

## 6. 事件與事件程式

### 6.1 實體事件

在場景工作區選取一個人物或物件，然後打開 **事件 ▸ 實體事件**。

![實體事件](images/editor_zh_events_entity.png)

- 最上方的清單是這個實體的事件；**+ 事件** 新增一個。
- **觸發**：何時執行。`Action`（玩家面向它並按下互動鍵）、`Autorun`（自動執行，期間玩家不能
  動）或 `Parallel`（與遊玩同時執行）。這三個值在中文介面也以英文顯示。碰觸與點擊觸發設定在
  實體的互動元件上。
- **程式**：要執行哪個事件程式。多個事件可以共用同一個程式。
- **條件**：事件何時可用（**+ 條件**：開關、變數、NPC 狀態、隊伍狀況……）。
  「條件：總是」表示沒有條件。
- **指令**：程式的指令。下方按鈕新增 **對話**、**選項**、**等待**、**如果**、**開關**、
  **變數**、**世界** 與 **序列…**；箭頭移動選取的指令，**刪除** 把它移除。雙擊指令可編輯。

### 6.2 指令的作用

| 指令 | 作用 |
| --- | --- |
| 對話 | 一段訊息，有說話者與可選的肖像（第 10 章）。 |
| 選項 | 一個帶選項的問題；答案存進一個變數（第 10 章）。 |
| 等待 | 等幾秒，或等到條件成立（開關、變數、戰鬥、聲音……）。 |
| 如果 | 條件成立時才執行接下來的指令。 |
| 開關 | 把一個開關（隨存檔保存的開／關旗標）打開或關閉。 |
| 變數 | 設定、增加或複製一個變數（隨存檔保存的數字或文字）。 |
| 世界 | 引擎的世界指令之一：開始戰鬥、給道具、移到另一張地圖、打開商店、播放音樂、移動鏡頭、加入隊伍、走到某處……完整清單與參數見 15.16。 |
| 序列… | 過場：移動、轉向、動畫、台詞與世界指令的平行軌道；可設為可跳過。 |

開關與變數由所有事件共用，並隨存檔保存。

### 6.3 互動總覽

**事件 ▸ 互動總覽** 逐張地圖列出玩家能互動的一切；選一項可看它的綁定、啟動的程式與互動設定
（距離、面向），讓你一次檢查整座城鎮。

![互動總覽](images/editor_zh_events_overview.png)

### 6.4 公用與戰鬥事件

**事件 ▸ 公用與戰鬥事件** 放不屬於某個實體的程式（**新增程式…** 新增一個）：

- **公用事件**：可重複使用、有觸發方式的程式：`call`（只在其他程式呼叫時執行）、`autorun`
  或 `parallel`（在它的開關開著時執行）。
- **戰鬥事件**：**時機**（戰鬥開始、新回合開始、戰鬥結束……）、**程式** 與 **只在** 條件
  （例如 `battle hp_ratio:<enemy> <= 0.5` 表示頭目受了重傷）。

![公用與戰鬥事件](images/editor_zh_events_common.png)

### 6.5 範例

Full Verification 範例中的公會會長（Hearthfold ▸ *Guildmaster Orla*）就是典型的程式：一個
**選項**（「Companions wait here until you hire them. Anything else?」）、每個答案一個 **如果**
分支、一個 **世界** `LEAVE_PARTY`、一個 **開關** 與一句 **對話**。

### 6.6 腳本（程式碼工作區）

![程式碼工作區](images/editor_zh_code.png)

**程式碼** 對開啟中的專案執行 Python。寫在 `scripts/main.py`（或 **新增腳本…**），然後按
**Run**（Ctrl+Enter；這個按鈕目前仍以英文顯示）。腳本可以使用 `project`、`selected`、`scene`
與 `entity`；右邊的 **編寫 API** 框是簡短的提示。一次執行的所有變更算一個復原步驟，執行失敗的
腳本會整個還原，錯誤顯示在 **錯誤追蹤**。

```python
town = project.scene("Hearthfold")
lina = town.create_entity("Lina", x=160, y=96)
lina.event("Greeting").dialogue("Lina", "Hello!").set_switch("met_lina").end()
```

---

## 7. 資料庫

**資料庫** 有六個分頁：遊戲資料、遊戲系統、敵人 AI、行為樹、即時戰鬥、遊戲開始。

### 7.1 資料頁

![遊戲資料：角色](images/editor_zh_gamedata_actors.png)

每個資料頁的用法都一樣：

- 右上角的下拉選單選擇類別（角色、技能、道具……）。
- 左邊清單顯示名稱與圖示；**篩選資料…** 搜尋名稱與 ID；排序框依 ID 或名稱排序。把滑鼠停在
  某列上可看到它的內部 ID。
- 右邊的表單：最上方是名稱與圖示，下面是內部 ID（固定不變；要新 ID 請用 **複製…** 做一份
  副本）。表單裡有數字、開關、選擇其他資料的下拉選單（附圖示）、標籤與清單卡片。空白的選用
  欄位收在「＋ 顯示其他 N 個欄位（空白）」底下；內部欄位在 **進階** 裡。
- 下方有 **複製…** 與 **刪除**；編輯會自動套用。

### 7.2 遊戲資料的類別

| 類別 | 內容 |
| --- | --- |
| 角色 | 可操控的角色：基礎屬性、標籤、技能、職業、裝備、外觀。 |
| 職業 | 職業：每級成長、技能、每級點數。 |
| 技能 | 技能：目標、花費、條件、命中、效果、狀態、冷卻、選單分組。 |
| 狀態 | 狀態（中毒、睡眠、增益……）：持續時間、疊加、每回合效果、圖示。 |
| 被動技能 | 永遠有效的效果。 |
| 成長路線、技能樹 | 等級與技能樹（附圖表檢視）。 |
| 道具、裝備、附件、裝備成長 | 消耗品、裝備、寶石／卡片、裝備成長路線。 |
| 製作 / 煉金 | 配方。 |
| 隊伍配置、陣形、隊伍選單規則 | 隊伍人數與前後排。 |
| 敵人 / 頭目、遭遇戰、敵人 AI / 頭目階段 | 敵人、你要打的敵群、它們如何行動。 |
| 場景動作時間軸、攻擊、投射物 | 即時戰鬥的招式。 |
| 戰利品稀有度、戰利品詞綴 | 隨機掉寶（動作 RPG）。 |

![職業](images/editor_zh_gamedata_classes.png)
![技能](images/editor_zh_gamedata_abilities.png)
![道具](images/editor_zh_gamedata_items.png)
![敵人 / 頭目](images/editor_zh_gamedata_enemies.png)
![遭遇戰](images/editor_zh_gamedata_encounters.png)

**遭遇戰** 就是一場戰鬥的內容：敵人成員、他們的排、獎勵與標籤（例如 `rules:<id>` 改用另一套
戰鬥規則）。地圖上的敵人、地圖區域或 `START_ENCOUNTER` 世界指令會指定要用哪一場遭遇戰。

**技能樹** 以圖表開啟：有圖示的卡片和箭頭。拖曳卡片後按 **儲存圖表版面**；**清單 / 資料檢視**
會顯示表單。

![技能樹圖表](images/editor_zh_gamedata_skilltree.png)

### 7.3 遊戲系統

**遊戲系統** 放全專案共用的規則，一次一種（左上角的下拉選單）：商店、任務、陣營、成就、套裝、
捕獲規則、寵物種類、寵物規則（生物隊伍）、世界互動、掉落表、物品欄規則、戰鬥附加（嘲諷、偷竊、
TP…）、敵人等級、地圖區域（區域、危險地帶）、裝備耐久度、武器精煉（+N）、分解、工作台（製作）、
任務告示板、招募事務所、抽獎卡池、職業點數、屬性公式（衍生屬性）、繼承新遊戲、翻譯、訊息設定、
音樂室、製作人員、戰鬥選項、技能欄位、暫停選單項目與裝飾物。

![遊戲系統：商店](images/editor_zh_systems_shops.png)

### 7.4 敵人 AI、行為樹、即時戰鬥

- **敵人 AI**：每個敵人的規則表（條件 → 行動 → 目標）與頭目階段。
- **行為樹**：地圖上與即時戰鬥敵人的 AI。
- **即時戰鬥**：攻擊、投射物、稀有度與詞綴，附即時預覽並疊畫判定框。

### 7.5 遊戲開始

**遊戲開始** 決定新遊戲的內容：起始場景、玩家的面向與位置、隊伍、初始道具、金錢與初始寵物。

![遊戲開始](images/editor_zh_game_start.png)

---

## 8. 戰鬥

### 8.1 傳統回合制戰鬥

**戰鬥** 工作區放戰鬥規則，一次一個類別：戰鬥資源、狀態效果、傷害互動、機率判定、目標選擇、
行動順序、詠唱與恢復時機、動作序列、破防量表、反擊與追擊、勝利與失敗條件、逃跑規則、動作花費
與一般戰鬥規則。

![戰鬥規則](images/editor_zh_battle_rules.png)

**一般戰鬥規則** 把它們串在一起：倒下判定的資源（HP）、增幅資源與每級花費、弱點破防用的護盾
資源、戰敗時的處理、行動時機與弱點標籤。**狀態效果** 設定每種狀態在戰鬥中的行為（回合數、
無法行動、機率、解除方式）。

![戰鬥中的狀態效果](images/editor_zh_battle_states.png)

遊玩中的戰鬥（Full Verification）：上方是行動順序，右邊是隊伍卡片，行動中的英雄旁是指令選單，
敵人下方是護盾與隱藏的弱點。

![回合制戰鬥](images/game_zh_battle.png)

隊伍 RPG 範例（破防／加速戰鬥），滿編隊伍、增幅點數與時間軸：

![隊伍 RPG（破防／加速戰鬥）](images/game_break_battle.png)

### 8.2 戰鬥畫面

**演出 ▸ 戰鬥畫面** 設定戰鬥的外觀：戰鬥角色圖、傷害數字與文字、戰鬥 HUD、戰鬥 UI 版面、
戰鬥 UI 間距、側視站位、肖像隊伍版面、動畫時機、鏡頭與編排、效果與音效聲道、行動選單、
指令選單頁、結算畫面、隊伍版面、戰鬥 UI 主題、動作序列與指令輸入步驟（同一頁也放 Menu Layout、
選單主題、Bitmap Font、Dialogue Window 與 Creature Screen 這幾類資料，見第 9 章；其中幾個
類別名稱目前仍以英文顯示）。

![戰鬥 UI 版面](images/editor_zh_battle_screen.png)

**戰鬥 UI 版面** 擺放隊伍 HUD、指令選單（**行動選單位置**）、頭上的名稱與 HP、肖像與舞台。
**指令選單頁** 為指令命名（戰鬥、技能、背包、逃跑……）。

### 8.3 生物戰鬥

生物遊戲（捕捉生物、用生物隊伍戰鬥）使用同一套規則，再加上：

- **遊戲系統 ▸ 寵物種類**（基礎屬性、成長、招式、進化）、**寵物規則（生物隊伍）**（隊伍人數、
  寄放、公式、基因、經驗）與 **捕獲規則**（捕獲率、球、搖晃次數）。
- 生物戰鬥畫面：用 **演出 ▸ 選單畫面 ▸ 版面 ▸ 生物畫面…** 開啟（`battle.creature_screen`
  資料；或在遊戲資料夾設定裡設 `battle.style: "creature"`）。畫面的圖片、字型、音效與位置都在
  同一個對話框裡編輯。

以下畫面取自 Full Verification 範例，生物暫用 Foozle 的圖：

![生物戰鬥：指令](images/game_creature_zh_30_commands.png)
![生物戰鬥：招式](images/game_creature_zh_31_moves.png)
![生物戰鬥：球在搖晃](images/game_creature_11_ball_shaking.png)
![生物戰鬥：隊伍畫面](images/game_creature_16_party_screen.png)

### 8.4 即時戰鬥

動作 RPG 直接在地圖上戰鬥。攻擊、投射物、戰利品稀有度與詞綴在 **資料庫 ▸ 即時戰鬥**；敵人行為
在 **行為樹**；下方的 HUD（血球、技能列、冷卻）是 **動作 RPG 介面** 這個選單畫面（第 9 章）。

![動作 RPG 的城鎮與動作 HUD](images/game_arpg_town.png)

---

## 9. 選單與畫面

### 9.1 版面畫布

**演出 ▸ 選單畫面 ▸ 版面** 讓你重新排列遊戲畫出的每一個畫面。

![選單畫面 ▸ 版面](images/editor_zh_menu_layout.png)

- **畫面清單**（左）：標題、暫停選單、設定、操作、存檔／讀檔、遊戲結束、狀態頁、裝備背包、
  裝備（紙娃娃）、強化（精煉、鑲嵌、卡片、成長）、技能樹、商店、製作（工作台）、任務告示板、
  招募事務所、抽獎卡池、任務紀錄、寵物、成就、怪物圖鑑、訊息紀錄、音樂室、製作人員、技能欄、
  要穿上新裝備嗎？、地圖提示列，以及遊玩中的畫面：對話視窗、對話選項、動作 RPG 介面與戰鬥畫面。
  圓點標出這個專案改過的畫面；工作台、告示板或卡池可以有自己的版面（縮排的列）。
- **畫布**（中）：用範例資料畫出的畫面。點外框選取元素，拖曳移動，拖曳右下角調整大小。
- **屬性**（右）：引擎預設位置（取消勾選即可自行擺放）、錨點、位置、大小、顯示、圖層、
  框（九宮格）、圖片等。
- **按鈕**：元素（選一個；**+** 加入你自己的圖片、面板、文字、量表或肖像）、移除元素、重設畫面、
  複製自…、背景…、選單主題…、點陣字型…、圖片對話視窗…、生物畫面…、遊戲資料夾設定…，以及
  **在遊戲中開啟**（執行專案並打開這個畫面）。**預覽語言** 用另一個語系畫出畫布。

沒有設定版面的畫面，會照引擎一貫的畫法畫出。

### 9.2 選單資料

**選單畫面 ▸ 選單資料** 編輯畫面背後的資料（角色畫面、裝備畫面、物品欄畫面、隊伍 / 陣形畫面……）。

![選單資料](images/editor_zh_menu_records.png)

### 9.3 遊戲的畫面

Full Verification 範例的畫面：

![標題](images/game_zh_title.png)
![暫停選單](images/game_zh_pause.png)
![狀態](images/game_zh_status.png)
![狀態：技能](images/game_zh_status_skills.png)
![裝備（紙娃娃）](images/game_zh_equipment.png)
![裝備背包](images/game_zh_bag.png)
![技能樹](images/game_zh_skill_tree.png)
![商店](images/game_zh_shop_buy.png)
![製作](images/game_zh_crafting.png)
![任務紀錄](images/game_zh_quests.png)
![寵物](images/game_zh_pets.png)
![存檔欄位](images/game_zh_save_slots.png)
![遊戲結束](images/game_zh_game_over.png)

暫停選單自己的項目來自 **遊戲系統 ▸ 暫停選單項目**；寵物、製作或強化等畫面只有在專案有相關
內容時才會出現。

---

## 10. 對話與選項

### 10.1 一句對話

在事件的 **指令** 中按 **對話**：

![對話指令](images/editor_zh_dialog_dialogue.png)

- **說話者** 與 **文字**；右邊的預覽顯示訊息框。
- **肖像**：一張圖片（瀏覽… 或從清單選），以及 **肖像位置**（左或右）。
- 文字代碼：`\V[name]` 變數、`\S[name]` 開關、`\N[id]` 角色名稱、`\P[n]` 隊伍第 n 位成員、
  `\G` 貨幣名稱、`\$` 金錢、`\M[name]` 訊息設定裡的巨集、`\T[key]` 翻譯文字、`\C[n]` 顏色、
  `\I[n]` 圖示、`\{` / `\}` 放大 / 縮小、`\.` 與 `\|` 停頓、`\!` 等待按鍵。

![遊玩中的一句對話](images/game_zh_dialogue.png)

### 10.2 選項

按 **選項**：一個提示與各個選項，每個選項附上要存進變數的值。游標停在選項上時（hover）可以
執行指令，取消鍵可以給一個值，選項也可以分欄排列。

![選項指令](images/editor_zh_dialog_choice.png)

![遊玩中的選項](images/game_zh_choice.png)

### 10.3 訊息設定與訊息視窗

- **遊戲系統 ▸ 訊息設定**：巨集（`\M[name]`）、`\G` 與 `\$` 顯示的貨幣、訊息紀錄的長度、
  **預設語系**、肖像樣式（臉在框內，或半身像站在框上）與肖像大小。
- **選單畫面 ▸ 版面 ▸ 圖片對話視窗…**：你自己的訊息視窗圖片、點陣字型、打字速度與翻頁箭頭；
  對話視窗與對話選項畫面也能像其他畫面一樣排版。
- 世界指令 `NAME_INPUT`（輸入名字）與 `PICTURE_CHOICE`（選一張圖）會打開它們自己的畫面。

![訊息設定](images/editor_zh_systems_message.png)

---

## 11. 輸入與操作

### 11.1 動作與綁定

**演出 ▸ 操作** 放專案的預設操作。一個 **動作**（Confirm、Cancel、Interact、Menu、Move Up……）
有多個 **綁定**：按鍵、手把按鈕、搖桿軸或十字鍵。

![操作](images/editor_zh_controls.png)

- 左邊是 **新增動作…** / **移除動作**；右邊是 **新增綁定** / **移除綁定**，以及 **裝置**、
  **程式碼**（按鍵名稱如 `a`、`left`、`space`，或手把按鈕／軸編號）與 **方向（搖桿 / 十字鍵）**。
- 玩家可以在遊戲中重新設定：設定 ▸ 按鍵設定…。

![在遊戲中重新設定按鍵](images/game_zh_controls.png)

新的輸入對應表的預設按鍵：

| 動作 | 鍵盤 | 手把 |
| --- | --- | --- |
| 移動 | 方向鍵、WASD | 左搖桿、十字鍵 |
| 互動（Interact） | E、Enter、Space | A（按鈕 0） |
| 確定（Confirm） | Enter、Space | A |
| 取消（Cancel） | Escape、Backspace | B（按鈕 1） |
| 選單（Menu） | C | Start（按鈕 7） |
| 奔跑（Run） | Shift | B |

### 11.2 滑鼠操作

**滑鼠操作** 開關（預設開啟）讓玩家在每個選單、對話與戰鬥中使用滑鼠：

- 指向一列或一個選項就會選取它，
- 左鍵確定，右鍵返回（取消），滾輪上下移動，
- 長選單會捲動，
- 用過滑鼠後右下角會出現提示（「點擊：選擇　右鍵：返回」）。

![用滑鼠選暫停選單](images/game_zh_mouse_02_pause_hover_settings.png)
![捲到底的長選單與滑鼠提示](images/game_zh_mouse_07_pause_scrolled_quit_hint.png)
![游標下的戰鬥指令](images/game_zh_mouse_04_battle_hover.png)

只用鍵盤的遊戲可以把它關掉；專案會存下 `"mouse": false`。

### 11.3 點擊移動

**點擊移動** 開關（預設關閉）：在地圖上按左鍵，玩家會沿著繞開障礙的路徑走過去；點一個人物會
走到他面前並交談。按任何鍵就會恢復鍵盤操作。適用於俯視地圖、俯視動作場景與網路遊戲，不適用於
橫向捲軸的平台場景。

![點擊移動](images/game_zh_mouse_09_click_to_move_walking.png)
![點一個人物走過去交談（動作 RPG）](images/game_en_mouse_12_arpg_click_figure_talks.png)

### 11.4 範例遊戲的按鍵

地圖上會顯示提示列，例如 Full Verification：移動 WASD／方向鍵、C 角色養成、Q 任務、E 互動、
F5 存檔、Esc 暫停。動作 RPG 範例：J 攻擊、K 閃避、1–6 技能、L 鎖定、F 撿取、B 背包、
C 技能樹、Esc 暫停。

---

## 12. 翻譯

### 12.1 編輯器的語言

**檢視 ▸ 語言**（英文介面為 View ▸ Language）讓編輯器在英文（預設）與繁體中文之間立即切換，
不必重新啟動；選擇會被記住。只有編輯器自己的文字會改變；你取的名稱、ID 與說明維持原樣。

![檢視 ▸ 語言](images/editor_zh_menu_view_language.png)

### 12.2 遊戲的語言

遊戲畫出的每個字都可以翻譯，也可以改名：

- **遊戲系統 ▸ 翻譯** 每個語系一張表（`en`、`zh-TW`、`fr`……）。頁面先列出每個內建文字與它旁邊
  的英文，接著是專案自訂的鍵與專案資料（角色、道具、地圖、說話者、對話……）。可以搜尋、只顯示
  未翻譯的列、**填入空白列**（用引擎自帶的繁體中文填入 zh-TW）、**新增鍵**、**移除鍵** 與
  **替對話產生鍵**（替每句對話與每個選項加上 `dlg.*` 鍵）。
- 留空表示維持英文；輸入一個空白可隱藏這個字。
- 在預設語系的表中填字就是改名：例如在 `en` 表把 `battle.command.attack` 填成 `Fight`。
- 這張表在它是 **預設語系**（訊息設定）或玩家在 **設定 ▸ 語言** 選了它時使用（有兩個以上語系
  時才會顯示這個設定）。

![翻譯](images/editor_zh_systems_translations.png)

常見的鍵：

| 鍵 | 文字 |
| --- | --- |
| `battle.command.attack`、`pause.save`… | 引擎的內建文字；完整清單見 [`docs/BUILT_IN_TEXT_KEYS.md`](../BUILT_IN_TEXT_KEYS.md)。 |
| `data.<kind>.<id>.name` / `.description` | 資料的名稱與說明（`data.actor.hero_01.name`）。 |
| `data.map.<scene id>.name`、`data.speaker.<name>.name`、`data.currency.<id>.name` | 地圖名稱、說話者、貨幣。 |
| `battle.layer.<command id>`、`pause.entry.<id>`、`controls.action.<action id>` | 你自己的指令頁、暫停選單項目與操作名稱。 |
| `dlg.*` | 對話與選項（它們的 `text_key`）。 |

在腳本與你自己的畫面中，用 `game.tr("key", "English")` 畫文字（15.5）。世界指令 `SET_LOCALE`
可以從事件切換語言。

同樣的畫面，繁體中文與英文：

![繁體中文的設定畫面](images/game_zh_settings.png)
![英文的地圖](images/game_en_field.png)
![英文的一句對話](images/game_en_dialogue.png)

---

## 13. 試玩存檔與匯出

### 13.1 試玩

![執行選單](images/editor_zh_menu_run.png)

| 執行選單 | 快捷鍵 | 作用 |
| --- | --- | --- |
| 執行專案 | F6 | 從遊戲開始遊玩（標題畫面、新遊戲）。 |
| 執行目前場景 | Ctrl+F6 | 遊玩編輯器中開著的場景。 |
| 從選取處播放 | Shift+F5 | 遊玩目前場景，玩家放在選取的實體位置。 |
| 重新開始播放 | Ctrl+Shift+F5 | 停止並用同樣方式重新開始。 |
| 停止 | Shift+F6 | 關閉遊戲視窗。 |
| 遊戲資料夾設定… | | 用設定樹編輯 `playable_test_manifest.json`（可復原）。 |

遊戲會在自己的視窗開啟。**除錯器**、**效能分析** 與 **問題** 面板顯示執行中遊戲的狀態、畫格時間
與專案錯誤。

不開編輯器：`.venv/bin/asteria-preview PROJECT.json`（選項 `--scene`、`--width`、`--height`、
`--save`、`--spawn X Y`、`--fps`）。

### 13.2 遊戲中的存檔

玩家用暫停選單（儲存進度 / 讀取進度）或在地圖上按 F5 存檔；存檔以編號欄位放在專案的 `saves/`
資料夾（`slot1.asteria-save.json`……）。編輯器永遠不會修改玩家的存檔；試玩存檔不會進到專案檔。

![存檔欄位](images/game_zh_save_slots.png)

### 13.3 匯出桌面版遊戲

**檔案 ▸ 匯出遊戲…** 會問遊戲名稱、是否另外建立單一檔案的遊戲（.pyz）與 macOS 應用程式
（.app），然後問資料夾。（這個對話框目前還沒有中文翻譯。）

![匯出遊戲](images/editor_zh_dialog_export.png)

遊戲資料夾一定會附上引擎（`run_game.py`）；玩家需要 Python 3.12 以上與 pygame-ce。在終端機
做同樣的事：

```bash
.venv/bin/asteria-export PROJECT.json OUTPUT --pyz --app --name "My Game"
```

### 13.4 匯出網頁版遊戲

```bash
.venv/bin/python -m pip install pygbag
.venv/bin/asteria-export-web PROJECT.json OUTPUT --serve
```

這會用 pygbag 建立 `OUTPUT/build/web/`（`index.html` 與遊戲套件），並在
`http://127.0.0.1:8000` 提供（請用 `127.0.0.1` 開啟，不要用 `localhost`）。選項：`--title`、
`--width`、`--height`、`--icon`、`--cjk-font`（預設 Noto Sans TC，`none` 表示不附字型）、
`--cdn`、`--no-build`、`--port`。把 `index.html` 與套件複製到任何靜態網站主機即可。

在瀏覽器中：存檔放在瀏覽器的本機儲存空間；音效必須是 ogg 或 wav；網頁版不含編輯器、多人連線、
GPU 繪圖與 C++ 加速；除非傳入 `--cdn`，頁面會從 pygame-web 的 CDN 載入 Python 執行環境。網址加上
`?mute=1` 可無聲執行。

---

## 14. 參考專案

用 檔案 ▸ 開啟專案… 開啟，或用 `asteria-preview` 遊玩。

| 專案 | 展示 |
| --- | --- |
| `reference_projects/full_verification_demo` | 建議使用的範本：一整款回合制遊戲。Hearthfold（城鎮）→ Whispering Woods → Catacombs → Ember Throne，主角 Roger 雇用 Mira、Vesper 與 Cael，職業與技能樹、STR / DEX / INT / LUK、屬性、弱點／護盾／破防、精煉與鑲嵌、製作、任務、寵物、地圖區域、繼承新遊戲、完整繁體中文、音樂室。每個編輯器頁面都有資料。 |
| `reference_projects/arpg_demo` | 即時動作 RPG：城鎮、野外、有平台和梯子的橫向捲軸礦坑、三個職業與技能樹、有稀有度／詞綴／套裝的掉寶、藥水、頭目。 |
| `reference_projects/party_rpg_demo` | 破防／加速的隊伍戰鬥：四位旅人各有兩個職業、弱點與護盾、增幅點數、神技、多武器攻擊、一隻寶可夢風格的寵物、調合、五場遭遇戰。 |
| `reference_projects/complex_reference_rpg` | 資料密集的通用 RPG：12 位角色、8 個職業、24 個技能、16 個被動、八棵技能樹、裝備成長、12 人名冊、有小兵的三階段頭目、自訂戰鬥資源。見它的 `PLAYTEST.md`。 |

想知道某個系統在資料裡怎麼描述，到 Full Verification 範例裡找：它的
[`README.md`](../../reference_projects/full_verification_demo/README.md) 有一張表，列出每個系統
與它在編輯器中的位置。

遊玩中的 Full Verification（英文）：

![標題](images/game_en_title.png)
![暫停選單](images/game_en_pause.png)
![戰鬥](images/game_en_battle.png)

---

## 15. 給作者的 Python API

本章由 `scripts/manual_api_list.py` 從引擎原始碼產生；簽名是真實的（省略型別註記）。引擎有變動
後請重新執行這個腳本，用 `--check` 可檢查本章是否仍是最新。

<!-- BEGIN API (generated by scripts/manual_api_list.py; do not edit by hand) -->

### 15.1 載入、儲存與執行專案

一個專案是一個 `project.asteria.json`，同一個資料夾放美術、`playable_test_manifest.json` 與 `saves/`。registry 告訴載入器有哪些元件：用 `EditorDocument().component_registry`（編輯器與參考腳本都這樣用）或 `build_preview_registry()`。

| 簽名 | 說明 |
| --- | --- |
| `Project.load_json(path, registry)` | 載入專案檔（classmethod）。 |
| `Project.save_json(path)` | 把專案寫進檔案。 |
| `Project.validate(*, validate_gameplay_refs=True)` | 檢查專案資料，遇到第一個問題就丟出錯誤。 |
| `Project.ability_reference_errors()` | 列出所有給了「技能庫裡沒有的技能」的紀錄。 |
| `Project.scenes()` | 依順序列出所有場景（地圖）。 |
| `Project.scene(scene_id)` | 用 id 取一個場景，沒有就是 `None`。 |
| `Project.add_scene(scene)` | 把場景加進專案。 |
| `Project.game_start` *(屬性)* | 資料庫 ▸ 遊戲開始 的設定。 |
| `GameStartDefinition.instantiate(project)` | 依遊戲開始設定建立新遊戲的存檔（`GameRuntimeSave`）。 |
| `GameRuntimeSave.load_json(path, project)` | 讀取某專案的存檔檔案（static method）。 |
| `GameRuntimeSave.save_json(path)` | 寫出存檔檔案。 |
| `asteria.runtime.save_slots.SaveSlots(folder, project, *, count=3, lookup=None)` | 某資料夾裡的編號存檔欄（遊戲使用 `<專案>/saves`）。 |
| `SaveSlots.save(slot, game)` | 把 `game` 存進一個存檔欄。 |
| `SaveSlots.load(slot)` | 讀出存檔欄裡的存檔。 |
| `SaveSlots.info(slot)` | 存檔欄的摘要（地圖、隊長、等級），給存檔畫面用。 |
| `SaveSlots.delete(slot)` | 刪除存檔欄裡的存檔。 |
| `asteria.runtime.preview.build_preview_registry()` | 遊戲播放器用的元件 registry。 |
| `asteria.runtime.preview.run_preview(project_path, scene_id=None, *, resource_root=None, backend=None, width=None, height=None, target_fps=60, save_path=None, playtest_profile=None, backend_kind='pygame', max_frames=None, profile_path=None, battle_presentation=None, debug_port=None, debug_token=None, spawn=None)` | 在視窗裡玩一個專案（`asteria-preview` 執行的就是它）。 |

### 15.2 PlayableTestRuntime（遊戲視窗）

在專案與存檔上開一個 pygame 視窗，畫出每個畫面，把鍵盤與滑鼠轉成遊戲動作。`rt.game` 就是下一節的 `GameSessionRuntime`。例：`rt = PlayableTestRuntime(project, project.game_start.instantiate(project), folder, width=1280, height=720); rt.open(); rt.run()`。

| 簽名 | 說明 |
| --- | --- |
| `asteria.runtime.playable_test_runtime.PlayableTestRuntime(project, runtime_save, resource_root, *, width=960, height=540, backend=None)` | 建立遊戲主程式（`open` 之前不顯示）。 |
| `rt.open()` | 開啟視窗、音訊與輸入。 |
| `rt.run(target_fps=60, max_frames=None, *, profile_path=None)` | 遊戲迴圈，直到玩家離開（或到 `max_frames`）。 |
| `rt.step(dt, events=None)` | 完整的一幀：事件、遊戲更新、繪製與翻頁（自己寫迴圈或 web 版用）。 |
| `rt.tick(target_fps=60)` | 等到穩定幀率的下一幀，回傳 dt。 |
| `rt.capture()` | 玩家看到的這一幀（pygame Surface）。 |
| `rt.close()` | 關閉視窗。 |
| `rt.save_playtest()` | 把試玩的自動存檔寫進 `saves/`。 |
| `rt.open_status_menu(back='field', page=None)` | 打開狀態選單。 |
| `rt.open_equipment_screen(back='field')` | 打開裝備（紙娃娃）畫面。 |
| `rt.open_enhance_screen(back='field')` | 打開強化畫面（精煉、鑲嵌…）。 |
| `rt.open_slots(mode, back='pause')` | 打開存檔／讀檔欄（`mode` 是 `save` 或 `load`）。 |
| `rt.menu_layout(screen_id)` | 某選單畫面的專案版面，沒有就是 `None`。 |
| `rt.text(value, x, y, *, size=20, color=(245, 245, 250), center=False, anchor=None, font=None)` | 在畫面上畫字（用 Python 寫的選單）。 |
| `rt.menu_row(label, x, y, *, selected, size=20, color=(245, 245, 250), pick=None, width=0)` | 畫一列選單與游標（含滑鼠可指區域）。 |
| `rt.hotspot(rect, pick=None, *, key='return')` | 標出這一幀滑鼠可指的位置；點擊會送出 `key`。 |
| `rt.enable_profiling(profiler=None, *, target_fps=60.0)` | 掛上幀時間分析器。 |
| `rt.enable_debugger(*, port=0, token=None)` | 開啟編輯器的除錯通道。 |
| `rt.game` *(屬性)* | `GameSessionRuntime`。 |
| `rt.settings` *(屬性)* | 玩家設定（語言、音量、按鍵覆寫）。 |

### 15.3 GameSessionRuntime：野外、地圖與移動

`game = rt.game`。不含繪製的遊戲規則：事件的世界指令能做的事，這裡都有對應方法。實體鍵可以是 `"player"`、實體名稱或 id。

| 簽名 | 說明 |
| --- | --- |
| `game.project` *(屬性)* | 載入的 `Project`。 |
| `game.save` *(屬性)* | 目前的 `GameRuntimeSave`。 |
| `game.player` *(屬性)* | 玩家實體。 |
| `game.transfer_player(scene_id, x=None, y=None, *, facing=None)` | 把玩家移到另一個場景或位置。 |
| `game.set_player_position(x, y)` | 把玩家放到 `(x, y)`。 |
| `game.set_player_facing(facing)` | 讓玩家轉向（`up`、`down`、`left`、`right`）。 |
| `game.find_path(start, goal, *, walker=None, cell_size=16.0, margin=0.0)` | 從 `start` 繞過牆壁到 `goal` 的路徑點，走不到是 `None`。 |
| `game.walk_to(entity_key, x, y, *, speed=60.0)` | 讓實體繞過障礙走到 `(x, y)`；抵達時開關 `walk.<id>.done` 變為開。 |
| `game.navigation_grid(*, cell_size=16.0, margin=0.0, walker=None)` | 目前野外的可行走格子。 |
| `game.move_route(entity_key, route, *, step=32.0, speed=60.0)` | 讓實體照路線行走，例如 `"up 3, left 2"`。 |
| `game.grid_route(entity_key, steps)` | 讓格子角色照步驟走（`GRID_ROUTE`）。 |
| `game.set_entity_position(entity_key, x, y, *, facing=None, permanent=False)` | 把實體放到 `(x, y)`；`permanent` 會記進存檔。 |
| `game.show_entity(entity_key, shown=True)` | 顯示或隱藏實體。 |
| `game.set_entity_movement(entity_key, behaviour='', facing='')` | 改變格子角色的移動方式與面向。 |
| `game.spawn_prefab(prefab_id, x, y, *, name=None)` | 在 `(x, y)` 用預製物件建立實體。 |
| `game.copy_entity(entity_key, x, y, *, name=None)` | 把場景實體複製到 `(x, y)`。 |
| `game.morph_entity(entity_key, prefab_id)` | 在原地把實體換成預製物件。 |
| `game.click_entity(world_x, world_y)` | 野外的滑鼠點擊：啟動被點實體的點擊觸發事件。 |
| `game.show_balloon(entity_key, balloon='exclamation', *, duration_ms=1000.0)` | 在實體頭上顯示對話泡泡（`exclamation`…）。 |
| `game.set_entity_icon(entity_key, icon_id='')` | 在實體頭上持續顯示圖示（任務標記…）。 |
| `game.play_action(entity_key, timeline_id)` | 在野外實體上播放動作時間軸。 |
| `game.set_tile(layer, x, y, tile, *, permanent=False)` | 改變某圖層的一格（例如門打開）；`permanent` 會存起來。 |
| `game.tile_changes(scene_id=None)` | 某場景被改過的圖塊。 |
| `game.set_light(radius=None, *, speed=0.0)` | 讓野外變暗，只留玩家周圍一圈（`None`：恢復）。 |
| `game.set_npc(npc_id, key, value)` | 改變 NPC 存檔裡的狀態（顯示、存活、心情…）。 |
| `game.move_npc(npc_id, scene_id, x, y)` | 移動 NPC，也可以移到別的場景。 |
| `game.notify(text, *, entity=None, duration_ms=1100.0, kind='info')` | 在實體上方顯示一則短暫的浮動訊息。 |
| `game.damage_party(resource_id, amount, *, can_kill=False)` | 對所有上場角色造成地板式傷害。 |

### 15.4 GameSessionRuntime：事件、對話與選項

`game.events` 是前景事件執行器：`game.events.start("程式 id")` 執行一個事件程式，之後主程式每幀呼叫 `update_events`。

| 簽名 | 說明 |
| --- | --- |
| `game.events` *(屬性)* | 前景的 `EventRunner`。 |
| `game.events.start(program_id, *, source_entity_id='', local_scope_id='', replace=False)` | 執行一個事件程式。 |
| `game.events.stop()` | 停止正在執行的事件。 |
| `game.update_events(dt=0.0)` | 讓執行中的事件程式前進 `dt` 秒。 |
| `game.pending_dialogue` *(屬性)* | 正在等玩家回應的台詞或選項。 |
| `game.acknowledge_dialogue()` | 關閉正在等待的台詞（確認鍵）。 |
| `game.choose(index)` | 選擇等待中選項的第 `index` 項。 |
| `game.hover_choice(index)` | 滑鼠停在第 `index` 項（執行它的 hover 指令）。 |
| `game.cancel_choice()` | 在等待中的選項按取消鍵。 |
| `game.held_dialogue` *(屬性)* | 不等待按鍵就顯示的台詞（`DIALOGUE wait: false`）。 |
| `game.event_busy` *(屬性)* | 事件鎖住玩家操作時為 True。 |
| `game.cutscene_active` *(屬性)* | 過場序列進行中為 True。 |
| `game.skip_cutscene()` | 快轉可跳過的過場。 |
| `game.expand_message(text, *, plain=False)` | 把訊息裡的控制碼（`\V[..]`、`\N[..]`、`\G`…）換成實際內容。 |
| `game.request_name_input(target, *, max_length=7, title='', default='', initial='')` | 打開輸入名字畫面（`NAME_INPUT`）。 |
| `game.finish_name_input(name)` | 送出輸入名字的結果。 |
| `game.request_picture_choice(layout, variable)` | 顯示圖片選項版面（`PICTURE_CHOICE`）。 |
| `game.finish_picture_choice(value)` | 送出圖片選項的結果。 |
| `game.actor_variable(actor_id, name, default=0)` | 角色專屬變數（會存檔）。 |
| `game.set_actor_variable(actor_id, name, value)` | 設定角色專屬變數。 |

### 15.5 GameSessionRuntime：翻譯

畫面畫的每個字都經過 `game.tr(鍵, 英文)`；鍵的清單在 `docs/BUILT_IN_TEXT_KEYS.md`。專案資料用 `data.<種類>.<id>.name`。

| 簽名 | 說明 |
| --- | --- |
| `game.tr(key, default=None, **params)` | 玩家語言的內建字（表裡沒有就用 `default`）。 |
| `game.set_locale(locale)` | 切換遊戲語言（要有那個語系的翻譯表，例如 `zh-TW`）。 |
| `game.localizer` *(屬性)* | 玩家目前語系的專案翻譯。 |
| `game.name_of(record, fallback=None)` | 紀錄名稱在玩家語言下的文字。 |
| `game.description_of(record, fallback='')` | 紀錄說明在玩家語言下的文字。 |
| `game.line_text(line)` | 台詞或選項翻譯後的文字。 |
| `game.speaker_of(line)` | 說話者翻譯後的名字。 |
| `game.map_name(scene_id, own)` | 地圖名稱翻譯後的文字。 |
| `game.stat_name(stat_id, *, short=False)` | 能力值或資源名稱翻譯後的文字。 |
| `game.slot_name(slot_id)` | 裝備部位名稱翻譯後的文字。 |
| `game.tag_name(tag)` | 標籤名稱翻譯後的文字。 |

### 15.6 GameSessionRuntime：隊伍、成長與技能

| 簽名 | 說明 |
| --- | --- |
| `game.join_party(actor_id, *, active=True)` | 角色加入名冊（有空位時也加入上場隊伍）。 |
| `game.leave_party(actor_id)` | 角色離開隊伍。 |
| `game.set_active_party(actor_ids, placements=None)` | 從名冊選出上場隊伍。 |
| `game.rest_party()` | 旅館：全員恢復全滿。 |
| `game.set_classes(actor_id, class_ids, *, unlock=True)` | 設定角色目前的職業。 |
| `game.set_secondary_class(actor_id, class_id)` | 設定角色的副職業。 |
| `game.learn_ability(actor_id, ability_id)` | 角色學會技能。 |
| `game.grant_actor_experience(actor_id, amount, *, level_threshold=1000.0, ap_per_level=2.0, ability_points_per_level=1.0, points_per_level=None, level_track='')` | 給經驗值（等級與點數隨之增加）。 |
| `game.allocate_progression(actor_id, graph_id, node_id, count=1)` | 在技能樹節點上花點數。 |
| `game.reset_progression(actor_id, graph_id=None, *, cost=None)` | 退回技能樹點數。 |
| `game.equip_passive(actor_id, passive_id, *, capacity=None)` | 裝備被動技能。 |
| `game.ability_slots(actor_id)` | 角色已裝上的技能與技能欄容量。 |
| `game.equip_ability(actor_id, ability_id)` | 把技能放進技能欄。 |
| `game.unequip_ability(actor_id, ability_id)` | 把技能從技能欄拿下。 |
| `game.party_gauge(gauge_id)` | 隊伍共用量表的數值。 |
| `game.change_party_gauge(gauge_id, amount)` | 增加或消耗隊伍共用量表。 |

### 15.7 GameSessionRuntime：道具、裝備、商店與製作

| 簽名 | 說明 |
| --- | --- |
| `game.use_item(actor_id, item_id)` | 在戰鬥外對成員使用消耗品。 |
| `game.equip_from_inventory(actor_id, equipment_id, slot_id=None)` | 從背包裝備物品。 |
| `game.unequip_to_inventory(actor_id, slot_id)` | 把部位上的物品卸下放回背包。 |
| `game.gain_equipment(equipment_id, quantity=1)` | 新裝備放進裝備背包（可能詢問是否穿上）。 |
| `game.wear_from_bag(actor_id, instance_id, slot_id, index=None)` | 把背包裡的裝備穿到部位上。 |
| `game.unequip_to_bag(actor_id, slot_id, index=0)` | 把穿著的裝備卸到背包。 |
| `game.refine_equipment(actor_id, instance_id, *, protect=False)` | 對已裝備物品精煉（+N）一次。 |
| `game.socket_item(actor_id, instance_id, socket_id, item_id)` | 把寶石或卡片鑲進孔位。 |
| `game.unsocket_item(actor_id, instance_id, socket_id)` | 把孔位裡的鑲嵌物取出。 |
| `game.disassemble(item_id)` | 依配方拆解物品。 |
| `game.open_shop(shop_id)` | 打開商店。 |
| `game.close_shop()` | 關閉商店。 |
| `game.buy(item_id, quantity=1, *, shop_id=None)` | 向開著的商店購買。 |
| `game.sell(item_id, quantity=1, *, shop_id=None)` | 賣給開著的商店。 |
| `game.craft(payload, *, station='', quality_bonus=0.0, rng=None)` | 用專案的配方製作。 |
| `game.learn_recipe(recipe_id)` | 學會配方。 |
| `game.known_recipes(station=None)` | 玩家看得到的配方。 |

### 15.8 GameSessionRuntime：任務與世界

| 簽名 | 說明 |
| --- | --- |
| `game.start_quest(quest_id)` | 開始任務。 |
| `game.advance_quest(quest_id, objective_id, amount=1)` | 推進任務目標。 |
| `game.complete_quest(quest_id)` | 完成任務。 |
| `game.fail_quest(quest_id)` | 任務失敗。 |
| `game.change_reputation(faction_id, amount)` | 改變陣營聲望。 |
| `game.change_relationship(subject_id, amount)` | 改變好感度。 |
| `game.add_counter(counter_id, amount=1)` | 增加世界計數器。 |
| `game.perform_interaction(interaction_id)` | 執行世界互動（判定、花費、結果）。 |
| `game.set_difficulty(difficulty_id)` | 選擇敵人等級規則的難度。 |
| `game.new_game_plus(rules_id=None)` | 從這一局繼承的新遊戲＋存檔。 |
| `game.request_new_game_plus(rules_id=None)` | 要求遊戲以新遊戲＋重新開始。 |

### 15.9 GameSessionRuntime：戰鬥

| 簽名 | 說明 |
| --- | --- |
| `game.start_encounter(encounter_id, *, opening=None)` | 開始回合制戰鬥；`opening` 可為 `preemptive`、`normal` 或 `surprise`。 |
| `game.current_turn_actor()` | 現在輪到誰。 |
| `game.ability_unavailable(actor_id, ability_id)` | 角色現在不能用某技能的原因（`''` 表示可以）。 |
| `game.default_targets(actor_id, ability_id)` | 選擇目標時的預設目標。 |
| `game.preview(actor_id, ability_id, target_ids)` | 預測行動的結果（不會改變任何東西）。 |
| `game.use_ability(actor_id, ability_id, target_ids=None, *, boost_level=0, form=None, choices=None)` | 依專案規則執行一次玩家行動。 |
| `game.use_battle_item(actor_id, item_id, target_ids=None)` | 在戰鬥中使用道具。 |
| `game.end_turn()` | 結束目前回合。 |
| `game.run_enemy_turns(*, limit=1000)` | 執行敵人回合，直到輪到我方。 |
| `game.plan_round(choices=None)` | 回合開始前所有人先選擇（生物式）。 |
| `game.escape_unavailable()` | 隊伍現在不能逃跑的原因（`''` 表示可以）。 |
| `game.attempt_escape(actor_id, *, rng=None)` | 嘗試逃跑。 |
| `game.capture_chance(target_id, item_id=None)` | 現在捕獲成功的機率（0–1）。 |
| `game.attempt_capture(actor_id, target_id, *, rng=None, item_id=None)` | 嘗試捕獲敵人。 |
| `game.summon(*, enemy_id=None, actor_id=None, count=1, owner_id=None, join_current_round=True)` | 讓戰鬥單位加入進行中的戰鬥。 |
| `game.steal(actor_id, target_id, *, chance_bonus=0.0)` | 嘗試偷取敵人的東西。 |
| `game.auto_battle_act(actor_id, **options)` | 讓角色自動行動一回合。 |
| `game.drain_battle_log()` | 取出並清空目前的戰鬥紀錄。 |
| `game.set_battle_weather(kind, intensity=0.6, wind=0.0)` | 之後戰鬥的天氣。 |

### 15.10 GameSessionRuntime：寵物與生物

| 簽名 | 說明 |
| --- | --- |
| `game.add_pet(species_id, *, level=1, nickname='', record=None, rng=None)` | 取得一隻某物種的新生物。 |
| `game.pets()` | 持有的寵物。 |
| `game.active_pet()` | 技能會派出的寵物。 |
| `game.set_active_pet(instance_id)` | 選擇出戰寵物。 |
| `game.rename_pet(instance_id, nickname)` | 替寵物取暱稱。 |
| `game.party_pets()` | 跟著玩家的寵物。 |
| `game.stored_pets()` | 放在倉庫的寵物。 |
| `game.move_pet_to_party(instance_id)` | 把寵物從倉庫移到隊伍。 |
| `game.move_pet_to_storage(instance_id)` | 把寵物移到倉庫。 |
| `game.heal_pets(*, party_only=False)` | 所有寵物恢復全滿。 |
| `game.use_item_on_pet(pet, item_id)` | 在戰鬥外對生物使用道具。 |
| `game.learn_pet_move(instance_id, ability_id, forget_ability_id='')` | 教寵物一個招式。 |
| `game.pet_evolution(instance_id, *, item_id='')` | 寵物現在符合的進化，沒有就是 `None`。 |
| `game.evolve_pet(instance_id, *, item_id='')` | 現在讓寵物進化。 |
| `game.pet_stats_at(pet, level=None)` | 寵物在某等級的能力值。 |
| `game.switch_pet(out_member_id, in_member_id)` | 把場上的生物換成候補的。 |

### 15.11 輸入與操作

`project.input_map` 是專案的 `InputActionMap`（演出 ▸ 操作）。`InputBinding` 是一個按鍵、手把按鈕或軸。

| 簽名 | 說明 |
| --- | --- |
| `asteria.runtime.input_map.InputActionMap(actions=None, *, mouse=True, click_move=False)` | 動作與綁定，以及兩個滑鼠開關。 |
| `InputActionMap.mouse` *(屬性)* | 選單、對話與戰鬥接受滑鼠（預設開）。 |
| `InputActionMap.click_move` *(屬性)* | 在地圖上按左鍵讓玩家走過去（預設關）。 |
| `InputActionMap.default()` | 鍵盤（方向鍵／WASD）加標準手把（classmethod）。 |
| `InputActionMap.actions()` | 所有動作 id。 |
| `InputActionMap.bindings(action_id)` | 某動作的綁定。 |
| `InputActionMap.set_bindings(action_id, bindings)` | 取代某動作的綁定。 |
| `InputActionMap.rebind(action_id, old, new, *, exclusive=False)` | 取代一個綁定（或新增）；`exclusive` 會從其他動作移除它。 |
| `InputActionMap.to_data()` | 轉成 JSON 資料。 |
| `InputActionMap.from_data(data)` | 從 JSON 資料讀入（classmethod）。 |
| `asteria.runtime.input_map.InputBinding(device, code, direction=1, threshold=0.5)` | 一個輸入：`device` 是 `key`、`button`、`axis` 或 `hat`。 |

### 15.12 程式碼工作區（編寫腳本）

程式碼工作區的腳本有全域變數 `project`（`AuthoringSession`）、`selected`、`scene`、`entity`，以及輔助函式 `track`、`move`、`face`、`animate`、`say`、`world`、`pause`、`battle_condition`。腳本做的所有修改算一步復原；腳本失敗會整個退回。

| 簽名 | 說明 |
| --- | --- |
| `AuthoringSession.scenes()` | 所有場景（包裝後）。 |
| `AuthoringSession.scene(name_or_id)` | 用名稱或 id 取場景。 |
| `AuthoringSession.new_event(program_id, name='')` | 建立空的事件程式。 |
| `AuthoringSession.event_program(program_id)` | 取得既有的事件程式。 |
| `AuthoringSession.common_event(program_id, trigger='call', switch='')` | 把程式設為公用事件（`call`、`autorun` 或 `parallel`）。 |
| `AuthoringSession.battle_event(hook, program_id, *, conditions=(), once=False)` | 在戰鬥的某個時刻執行程式。 |
| `AuthoringScene.entities()` | 場景裡的實體。 |
| `AuthoringScene.entity(name_or_id)` | 用名稱或 id 取實體。 |
| `AuthoringScene.create_entity(name, *, x=0.0, y=0.0)` | 在 `(x, y)` 新增實體。 |
| `AuthoringEntity.name` *(屬性)* | 實體名稱（可讀寫）。 |
| `AuthoringEntity.enabled` *(屬性)* | 實體是否啟用（可讀寫）。 |
| `AuthoringEntity.transform` *(屬性)* | 位置、旋轉與縮放。 |
| `AuthoringEntity.gameplay` *(屬性)* | 實體的能力值、資源與標籤。 |
| `AuthoringEntity.event(name='Event', *, trigger='action')` | 替實體新增事件（`trigger`：`action`、`autorun` 或 `parallel`）。 |
| `AuthoringEvent.dialogue(speaker, text=None, *, portrait='', side='left')` | 加一句台詞。 |
| `AuthoringEvent.set_switch(name, value=True)` | 加 SET_SWITCH。 |
| `AuthoringEvent.set_variable(name, value)` | 加 SET_VARIABLE。 |
| `AuthoringEvent.wait(seconds)` | 加 WAIT。 |
| `AuthoringEvent.world(command, **args)` | 加世界指令。 |
| `AuthoringEvent.transfer(destination, **args)` | 加移動到其他場景的 TRANSFER。 |
| `AuthoringEvent.sequence(*tracks, cutscene=False, skippable=False, wait='all')` | 加由平行軌道組成的 SEQUENCE。 |
| `AuthoringEvent.append(opcode, **args)` | 加任何 opcode 與參數。 |
| `AuthoringEvent.end()` | 結束串接（回傳實體或 session）。 |
| `AuthoringGameplayAttributes.set_stat(name, value)` | 設定基礎能力值。 |
| `AuthoringGameplayAttributes.define_resource(name, maximum, *, current=None, minimum=0.0, replace=False)` | 替實體加資源（HP、MP…）。 |
| `AuthoringGameplayAttributes.add_tag(tag)` | 加標籤。 |
| `asteria.authoring.api.track(name, *steps)` | 序列裡的一條平行軌道。 |
| `asteria.authoring.api.move(entity, x, y, duration=1.0, *, relative=False, wait=True)` | 軌道裡的移動步驟。 |
| `asteria.authoring.api.face(entity, facing)` | 轉向步驟。 |
| `asteria.authoring.api.animate(entity, clip)` | 播放動畫步驟。 |
| `asteria.authoring.api.say(speaker, text, *, portrait='', side='left')` | 對話步驟。 |
| `asteria.authoring.api.world(command, *, wait=0.0, **args)` | 世界指令步驟。 |
| `asteria.authoring.api.pause(seconds)` | 暫停步驟。 |
| `asteria.authoring.runner.run_authoring_script(source, project, *, execute=None, filename='<asteria-script>', selection_kind='none', selection_value=None)` | 在編輯器之外對專案執行腳本。 |

### 15.13 事件程式的資料

事件程式是一串指令。編輯器的事件工作區會寫出它們；`project.event_programs` 依 id 存放。

| 簽名 | 說明 |
| --- | --- |
| `asteria.events.program.EventProgram(instructions, *, name='')` | 一個程式：指令與名稱。 |
| `asteria.events.program.EventInstruction(opcode, args=None)` | 一條指令：opcode 與參數。 |
| `EventProgram.label_pc(name)` | LABEL 的位置。 |
| `EventProgram.to_data()` | 轉成 JSON 資料。 |
| `EventProgram.from_data(data)` | 從 JSON 資料讀入（classmethod）。 |

### 15.14 匯出

檔案 ▸ 匯出遊戲… 與指令 `asteria-export`、`asteria-export-web`（或 `python -m asteria.export_web`）背後都是這些函式。

| 簽名 | 說明 |
| --- | --- |
| `asteria.project_tools.export_game(project_path, output, *, allow_missing=False, bundle_engine=True)` | 遊戲資料夾：專案、它用到的檔案與引擎（`run_game.py`）。 |
| `asteria.project_tools.package_game(project_path, output, *, name=None, pyz=True, app=False, allow_missing=False, player=<bundled player>)` | 遊戲資料夾加上單一檔案 `.pyz`，在 macOS 還有 `.app`。 |
| `asteria.project_tools.build_pyz(game_folder, output, *, name)` | 把遊戲資料夾打包成單一 `.pyz` 檔。 |
| `asteria.project_tools.build_macos_app(pyz, output_dir, *, name, identifier=None)` | 把 `.pyz` 包成 macOS App。 |
| `asteria.project_tools.upgrade_project(path, *, backup=True)` | 把專案檔升級成目前的格式（保留備份）。 |
| `asteria.project_tools.export_main(argv=None)` | `asteria-export` 指令。 |
| `asteria.export_web.export_web(project_path, output, *, title=None, cjk_font='default', cdn=None, icon=None, width=1280, height=720, allow_missing=False, allow_unsupported_audio=False, build=True, serve=False, port=8000, run=run)` | 用 pygbag 建瀏覽器版（`build/web/index.html` 與 `.apk`）。 |
| `asteria.export_web.serve_web(web, port=8000, *, bind='127.0.0.1', ready=None)` | 在 `http://127.0.0.1:PORT` 提供 web 版。 |
| `asteria.export_web.main(argv=None)` | `asteria-export-web` 指令。 |

### 15.15 事件指令（opcode）

條件（`JUMP_IF`、`IF_FALSE_SKIP`、`WAIT until`、事件頁）寫成 `{source, name, operator, value}`；來源：`switch`、`variable`、`local`、`rpg`、`npc`、`battle`、`audio`；比較 `==`、`!=`、`<`、`<=`、`>`、`>=`。

| Opcode | 參數 | 作用 |
| --- | --- | --- |
| `DIALOGUE` | speaker, text, text_key, portrait_asset_id, portrait_side, wait | 顯示一句台詞；`wait: false` 讓字留著、事件繼續。 |
| `CHOICE` | prompt, prompt_key, choices [{text, value, text_key, hover}], variable_name, local_name, cursor, cancel, columns, box_at | 提問；選中選項的值存進變數。 |
| `WAIT` | seconds \| until {condition} (+ seconds) | 等幾秒，或等到條件成立。 |
| `SET_SWITCH` | name, value | 打開或關閉開關。 |
| `SET_VARIABLE` | name, value \| add \| from_variable | 設定、增加或複製變數。 |
| `SET_LOCAL` | name, value (scope_id) | 這個事件所屬實體自己的變數。 |
| `LABEL` | name | 可以跳到的位置。 |
| `JUMP` | label | 跳到標籤。 |
| `JUMP_IF` | condition, label | 條件成立時跳到標籤。 |
| `IF_FALSE_SKIP` | condition, count | 條件不成立時跳過接下來 `count` 條指令。 |
| `CALL` | program_id, scope | 執行另一個程式後回來。 |
| `RETURN` |  | 回到呼叫的程式。 |
| `EXIT` |  | 停止整個事件（含被呼叫的程式）。 |
| `END` |  | 結束這個程式。 |
| `WORLD` | command, args | 執行世界指令（見下表）。 |
| `SEQUENCE` | tracks, cutscene, skippable, wait | 由移動、台詞與指令組成的平行軌道（過場）。 |

### 15.16 世界指令

`WORLD` 指令可以執行的 83 個世界指令與各自讀取的參數名（`asteria.runtime.world_command_handlers.WORLD_COMMAND_ARGUMENTS`）。編輯器裡：事件 ▸ 世界。

| 指令 | 參數 |
| --- | --- |
| `ADD_COUNTER` | counter_id, amount |
| `ADVANCE_QUEST` | quest_id, objective_id, amount |
| `BATTLE_SEQUENCE` | sequence_id, actor_id, target_id |
| `CAMERA_FOCUS` | entity, x, y, zoom, blend, ease |
| `CAMERA_RELEASE` | blend, ease |
| `CAMERA_SHAKE` | intensity, duration |
| `CHANGE_CURRENCY` | currency_id, amount |
| `CHANGE_RELATIONSHIP` | subject_id, amount |
| `CHANGE_REPUTATION` | faction_id, amount |
| `COMPLETE_QUEST` | quest_id |
| `COPY_ENTITY` | entity, x, y, name |
| `DISASSEMBLE` | item_id |
| `EQUIP_ITEM` | actor_id, equipment_id, slot_id, index |
| `ERASE_PICTURE` | picture_id |
| `FAIL_QUEST` | quest_id |
| `GIVE_EQUIPMENT` | equipment_id, quantity |
| `GIVE_ITEM` | item_id, quantity |
| `GIVE_PET` | species_id, level, nickname, moves |
| `GRANT_EXPERIENCE` | actor_id, amount, threshold, points, level_track |
| `GRID_ROUTE` | entity, steps |
| `HEAL_PETS` | party_only |
| `INTERACT` | interaction_id |
| `JOIN_PARTY` | actor_id, active |
| `LEARN_ABILITY` | actor_id, ability_id |
| `LEARN_RECIPE` | recipe_id |
| `LEAVE_PARTY` | actor_id |
| `MORPH_ENTITY` | entity, prefab_id |
| `MOVE_NPC` | npc, scene_id, x, y |
| `MOVE_PICTURE` | picture_id, x, y, scale, opacity, tint, tint_color, duration, easing, delay |
| `MOVE_ROUTE` | entity, route, step, speed |
| `NAME_INPUT` | target, max_length, title, default, initial |
| `NEW_GAME_PLUS` | rules_id |
| `OPEN_CRAFTING` | station |
| `OPEN_GACHA` | banner_id |
| `OPEN_QUEST_BOARD` | board_id |
| `OPEN_RECRUIT` | office_id |
| `OPEN_SHOP` | shop_id |
| `PARTY_RESTORE` | — |
| `PARTY_STASH` | — |
| `PET_STORAGE` | — |
| `PICTURE_CHOICE` | layout, variable |
| `PLAY_ACTION` | entity, timeline_id |
| `PLAY_BGM` | asset_id, fade, volume, temporary |
| `PLAY_ME` | asset_id, volume |
| `PLAY_SE` | asset_id, volume |
| `PLAY_VFX` | asset_id, entity, x, y, scale, anchor |
| `REFINE_EQUIPMENT` | actor_id, instance_id, protect |
| `RESTORE_BGM` | — |
| `REST_PARTY` | — |
| `SCREEN_FADE` | to, duration, color |
| `SET_BATTLE_WEATHER` | kind, intensity, wind |
| `SET_CLASSES` | actor_id, class_ids, unlock |
| `SET_ENTITY_ICON` | entity, icon_id |
| `SET_LIGHT` | radius, speed, off |
| `SET_LOCALE` | locale |
| `SET_LOOK` | entity, sprite_sheet_asset_id, clip_set_id |
| `SET_MOVEMENT` | entity, behaviour, facing |
| `SET_NPC` | npc, key, value |
| `SET_PICTURE_FRAME` | picture_id, frame |
| `SET_POSITION` | entity, x, y, facing, permanent |
| `SET_RESPAWN` | scene_id, x, y, facing |
| `SET_TILE` | layer, x, y, tile, permanent |
| `SHOW_BALLOON` | entity, balloon, duration_ms |
| `SHOW_ENTITY` | entity, shown |
| `SHOW_PICTURE` | picture_id, asset_id, x, y, scale, opacity, frame, columns, rows, layer, click_event, tint, tint_color, frame_rate, frame_loop, scroll_x, scroll_y, wave_amplitude, wave_length, wave_speed, blend, text, font, text_color, shadow_color, text_align |
| `SHOW_POPUP` | text, entity, duration_ms, kind |
| `SOCKET_ITEM` | actor_id, instance_id, socket_id, item_id |
| `SPAWN_ENTITY` | prefab_id, x, y, name |
| `START_ENCOUNTER` | encounter_id |
| `START_QUEST` | quest_id |
| `STOP_BGM` | fade |
| `SUMMON` | enemy_id, actor_id, count, owner_id |
| `TAKE_ITEM` | item_id, quantity |
| `TIMER_ADD` | timer_id, seconds |
| `TIMER_PAUSE` | timer_id |
| `TIMER_RESUME` | timer_id |
| `TIMER_START` | timer_id, seconds, on_expire, count_up, show |
| `TIMER_STOP` | timer_id |
| `TITLE_COMMAND` | action, screen |
| `TRANSFER` | scene_id, x, y, facing |
| `UNSOCKET_ITEM` | actor_id, instance_id, socket_id |
| `UPGRADE_EQUIPMENT` | actor_id, instance_id, node_id |
| `WALK_TO` | entity, x, y, speed |

<!-- END API -->
