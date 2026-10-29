# Asteria

[English](README.md) | **繁體中文**

**用 Python 做 2D RPG 的引擎與編輯器。** 回合制隊伍戰鬥與即時動作戰鬥共用一套資料驅動的核心；
有歧義的規則都是編輯器裡的選項，範例遊戲只是資料，不是寫死在引擎裡的規則。編輯器有繁體中文與英文介面。

> **狀態：Alpha（開發者預覽）。** 功能完整、測試齊全，但資料格式與 API 仍可能變動，也還沒有在很多人的
> 機器上跑過。這是個人興趣專案：歡迎回報問題，但不保證回應時間。

![編輯器：場景工作區](docs/manual/images/editor_zh_scene.png)

![遊戲：回合制戰鬥](docs/manual/images/game_zh_battle.png)

---

## 特色

- **編輯器**（PySide6）：場景、資料庫、戰鬥、演出、事件、程式碼、多人連線七個工作區；紀錄是表單，
  改了就套用、Ctrl+Z 復原；畫地圖、技能樹圖、素材庫匯入、從範本開新專案；英文與繁體中文介面即時切換。
- **回合制戰鬥**：排程與加速點、弱點／護盾／破防、多段攻擊、多武器、主副職業、技能樹、狀態、反射與吸收、
  多階段 Boss、召喚、寵物與收服、調合、逃跑、戰鬥獎勵；側視站位、HUD 肖像、鏡頭、特效，全部可調。
- **即時戰鬥**：俯視與橫向視角共用一套核心；攻擊判定（無敵幀、擊退、硬直）、連段、閃避、鎖定、冷卻、
  投射物、行為樹 AI、平台手感（郊狼時間、跳躍緩衝、斜坡、梯子）。
- **RPG 資料**：職業、技能樹、裝備（欄位、鑲嵌、套裝、成長、隨機詞綴、稀有度、精煉）、掉落、任務、
  商店、聲望、成就、圖鑑、寵物（物種、升級、進化）、存檔槽、新遊戲＋。
- **世界**：分層地圖、四向角色、對話與事件程式、NPC 狀態、天氣與光照、視差背景、可翻譯的內建字詞。
- **效能**：ECS 欄位陣列；熱迴圈有 Python／numpy／C++ 三組 kernel，結果相同，不編譯 C++ 也能跑。
- **匯出**：可發布的遊戲資料夾、單檔遊戲（`.pyz`）、macOS app，以及不需要 Python 的免安裝版。
- **多人原型**：TCP session／lobby、即時輸入同步、合作 Boss 範例、SQLite 玩家資料（本機或可信任的區域網路）。
- **RPG Maker MV 匯入**：地圖、資料庫、事件可以帶過來（素材請見下方說明）。

## 安裝

需要 Python 3.12 以上（macOS、Linux、Windows）。

```bash
git clone https://github.com/rogerhao66666/Asteria.git
cd Asteria
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[pygame,editor,mv,dev]"
```

可選的 extras：`pygame`（遊戲執行）、`editor`（PySide6 編輯器）、`mv`（RPG Maker MV 匯入，需要 Pillow）、
`moderngl`（GPU 後端）、`fast`（numpy kernel）、`dev`（pytest、ruff）、`package`（免安裝版 app）。
只玩遊戲、不開編輯器的話，裝 `".[pygame]"` 就夠。C++ kernel 可選：`python -m asteria.kernels.build_native`。

## 開始使用

```bash
asteria-editor                                   # 開編輯器
asteria-preview reference_projects/full_verification_demo/project.asteria.json   # 直接玩範例
asteria-export PROJECT.json OUT_DIR              # 匯出可發布的遊戲資料夾
asteria-export PROJECT.json OUT_DIR --pyz --app  # 另外做單檔遊戲與 macOS app
asteria-import-mv MV_PROJECT_DIR OUT.json        # 匯入 RPG Maker MV 專案
asteria-upgrade PROJECT.json                     # 把舊版專案升到目前格式
```

第一次開編輯器會打開一份 Full Verification 範例的副本（放在你的使用者資料夾，不會改到 repo 裡的範例）。
要開新專案：**File > New Project…**（Ctrl+N），選 Full Verification（完整的遊戲，推薦）、Basic RPG、
Party RPG、Action RPG 或 Completely Empty。**Run Project**（F6）從遊戲開始處試玩，
**Run Current Scene**（Ctrl+F6）從目前的地圖試玩。

遊戲預設鍵位：WASD／方向鍵移動、E 互動、Q 任務、Esc 暫停、F5 存檔（可在設定裡改）。

完整的使用手冊：[繁體中文](docs/manual/USER_MANUAL.zh-TW.md)／[English](docs/manual/USER_MANUAL.en.md)。

## 範例專案（`reference_projects/`）

| 專案 | 內容 |
| --- | --- |
| `full_verification_demo` | 回合制 JRPG，**所有系統都用上**：四張地圖、三個 Boss、四位隊員、技能樹、職業、多武器、裝備精煉與鑲嵌、寵物收服與進化、召喚、調合、商店、任務、存讀檔、新遊戲＋ |
| `party_rpg_demo` | 隊伍 RPG：弱點／護盾／破防、加速、奧義、多武器、多段攻擊、寵物、調合 |
| `arpg_demo` | 動作 RPG：城鎮、野外（俯視）、礦坑（橫向）、技能樹 build、詞綴裝備 |
| `arpg_multiplayer_demo` | 上一個的多人版本 |

範例的美術和音樂都已在 repo 裡（`playable_assets/`），可以直接玩。要重建範例：

```bash
python reference_projects/full_verification_demo/build_project.py
```

美術從 `asset_library/` 讀。音樂原本來自較大的 Foozle 音樂包（不放進 repo）；沒有設定
`ASTERIA_MUSIC_ASSETS` 時，重建會沿用 repo 裡已有的音樂檔，所以從 repo 重建不需要另外下載。

## 素材與授權

- **程式碼**：[MIT License](LICENSE)。用 Asteria 做的遊戲可以自由發布、販售，不需要開源。
- **附帶的素材**（`asset_library/`、範例的 `playable_assets/`）：CC0 為主，字型為 SIL OFL；每一項的來源與
  授權見 [`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md)，函式庫見 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
- **你自己的遊戲素材**：任何授權允許你使用的素材都可以。注意 RPG Maker 內建的素材（RTP）與多數官方 DLC，
  授權通常只限用在 RPG Maker 製作的遊戲；匯入 MV 專案後，請換成你有權使用的素材再發布。

Asteria 與 RPG Maker 及其權利人沒有任何關聯。

## 開發

```bash
python -m pytest -q                              # 全部測試（約 3,600 項，約 5 分鐘）
ruff check src scripts tests reference_projects  # 每行 ≤ 99 字元
ruff format --check src scripts tests reference_projects
```

GitHub Actions 在每次 push 與 PR 跑 lint、格式檢查，以及 Linux（Python 3.12、3.13）與 macOS 的全套測試；
在自己的電腦上，`scripts/docker_tests.sh` 會用 Docker 在乾淨的 Linux 跑全套。
想參與：請看 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 文件

- [`docs/ENGINE_HANDBOOK.md`](docs/ENGINE_HANDBOOK.md)：**從這裡開始**，安裝、目錄、每個系統怎麼運作、已知限制。
- [`docs/manual/`](docs/manual/)：給遊戲作者的使用手冊（中英文，附截圖）。
- [`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md)：每個設計決策的原因、測試與證據。
- [`docs/spec/`](docs/spec/)：產品與素材規格（設計目標；目前實作到哪裡以手冊為準）。
- [`docs/README.md`](docs/README.md)：所有文件的索引，標明哪些是現行文件、哪些是歷史紀錄。
- [`docs/history/`](docs/history/)：開發過程的紀錄與稽核。
