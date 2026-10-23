# Asteria

Python 寫的 2D RPG 引擎加編輯器。資料驅動、系統通用：回合制（八方旅人式）和即時動作（暗黑式）
都做得出來，兩者只是範例專案，引擎裡沒有任何一款遊戲的規則寫死。

A Python-first 2D RPG engine and editor. Data-driven and generic: turn-based (Octopath-style)
and real-time (Diablo-style) games are both just sample projects; no game's rules live in the
engine. English summary at the end of this file.

---

## 特色

- **三條原則**：不限制作者（有歧義的規則做成編輯器可改的選項）、系統通用（Diablo、八方旅人只是範例資料）、
  沒有證據不說完成（每個功能有測試，畫面在真實視窗驗證，證據放在 `docs/audits/evidence/`）。
- **編輯器**（PySide6）：Scene、Database、Battle、Presentation、Events、Code、Multiplayer 七個工作區；
  紀錄是表單（下拉挑參照、chips、卡片），改了就套用、Ctrl+Z 復原；畫地圖、技能樹圖、素材庫匯入、
  從範本開新專案；介面有英文與繁體中文，即時切換。
- **回合制戰鬥**：排程與加速點、弱點／護盾／破防、多段攻擊、多武器、主副職業、技能樹、狀態、反射與吸收、
  多階段 Boss、召喚、寵物與收服、調合、逃跑、戰鬥結果與獎勵；側視站位、HUD 肖像、鏡頭、特效、全部可調。
- **即時戰鬥**：俯視與橫向視角共用一套核心；攻擊判定（無敵幀、擊退、硬直）、連段、閃避、鎖定、冷卻、
  投射物、行為樹 AI、平台手感（郊狼時間、跳躍緩衝、斜坡、梯子）；底部 HUD、背包、技能樹畫面。
- **RPG 資料**：職業、技能樹、裝備（欄位、鑲嵌、套裝、成長、隨機詞綴、稀有度、精煉）、掉落、任務、
  商店、聲望、成就、圖鑑、寵物（物種、升級、進化）、存檔槽、新遊戲＋。
- **世界**：分層地圖、四向角色、對話與事件程式（VM）、NPC 狀態、天氣與光照、視差背景、可翻譯的內建字詞。
- **效能**：ECS 用欄位陣列存放；熱迴圈有 Python／numpy／C++ 三組 kernel，結果逐位元相同，沒編譯 C++
  也能跑；真實視窗 1280×720 每格約 5 ms（預算 16.7 ms）。
- **多人原型**：TCP session／lobby、即時輸入同步、合作 Boss 範例、SQLite 玩家狀態（本機或可信 LAN）。
- **素材**：`asset_library/` 只放可再散布的 CC0／CC-BY 素材（Foozle Lucifer 與 Critters、KayKit 3D 角色），
  來源與授權記在 [`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md)；RPG Maker MV 專案可匯入。

## 安裝

需要 Python 3.12 或更新（macOS、Linux、Windows 都可；真實視窗的驗證腳本在 macOS 上做）。

```bash
git clone https://github.com/rogerhao66666/Asteria.git
cd Asteria
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[pygame,editor,mv,dev]"
```

可選的 extras：`pygame`（遊戲執行）、`editor`（PySide6 編輯器）、`mv`（RPG Maker MV 匯入，需要 Pillow）、
`moderngl`（GPU 後端）、`fast`（numpy kernel）、`dev`（pytest、ruff）。只做遊戲、不開編輯器的機器
裝 `".[pygame]"` 就夠。

C++ kernel 不是必要的；要用的話在開發機編譯一次：

```bash
python -m asteria.kernels.build_native
```

## 怎麼用

```bash
asteria-editor                                   # 開編輯器
asteria-preview reference_projects/full_verification_demo/project.asteria.json   # 直接玩一個專案
asteria-upgrade PROJECT.json                     # 把舊版專案升到目前格式
asteria-export PROJECT.json OUT_DIR              # 匯出可發布的遊戲資料夾
asteria-export PROJECT.json OUT_DIR --pyz --app  # 另外做單檔遊戲（Name.pyz）與 macOS app（Name.app）
asteria-import-mv MV_PROJECT_DIR OUT.json        # 匯入 RPG Maker MV 專案
```

第一次開編輯器：**File > New from Template…**（Ctrl+N），選 Full Verification（完整的遊戲，推薦）、
Basic RPG、Party RPG（八方旅人式）、Action RPG（暗黑式）或 Completely Empty。範本會整個複製到你選的
資料夾，Console 會顯示該專案的 `START_HERE.md`，寫明每條規則在編輯器哪裡改。**Play Current Scene**（F6）
直接試玩。

遊戲操作（預設鍵位，可在設定裡改）：WASD／方向鍵移動、E 互動、Q 任務、Esc 暫停、F5 存檔。

## 範例專案（`reference_projects/`）

| 專案 | 內容 |
| --- | --- |
| `full_verification_demo` | 回合制 JRPG，**所有系統都用上**：四張地圖、三個 Boss、四位隊員、技能樹、職業、多武器、裝備精煉與鑲嵌、寵物收服與進化、召喚、調合、商店、任務、存讀檔、新遊戲＋。`run_campaign.py` 能無頭跑完整段劇情並核對每個系統真的被用到 |
| `octopath_demo` | 八方旅人式：弱點／護盾／破防、加速、奧義、多武器、多段攻擊、寵物、調合 |
| `diablo_demo` | 暗黑式即時動作：城鎮、野外（俯視）、礦坑（橫向）、技能樹 build、詞綴裝備 |
| `diablo_multiplayer_demo` | 上一個的多人版本 |

重建範例專案（美術從 `asset_library/` 讀；音樂需要 git 忽略的本機下載）：

```bash
python reference_projects/full_verification_demo/build_project.py
```

## 開發

```bash
python -m pytest -q                              # 全部測試（約 3,200 項，約 3 分鐘）
ruff check src scripts tests reference_projects  # 每行 ≤ 99 字元，import 排序，bugbear
ruff format --check src scripts tests reference_projects
```

真實視窗的驗證（macOS；會開視窗並截圖到 `docs/audits/evidence/`）：

```bash
python scripts/full_verification_campaign_live_check.py OUT_DIR   # 整段劇情
python scripts/battle_art_gallery_live_check.py OUT_DIR           # 每個角色每個動作、每種特效
python scripts/runtime_benchmark.py OUT.json --real-window        # 效能基準
python scripts/editor_ui_audit.py OUT_DIR                         # 編輯器每一頁的排版稽核
```

GitHub Actions（`.github/workflows/tests.yml`）在每次 push 與 PR 跑 ruff 與全部測試（無頭）。

專案規則：直接在 `main` 上做；每個改動有測試與實機證據，記進
[`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md)；每個 Python 檔每行 ≤ 99 字元；
刪功能要逐項核准。

## 文件

- [`docs/ENGINE_HANDBOOK.md`](docs/ENGINE_HANDBOOK.md) — **從這裡開始**：安裝、目錄、每個系統怎麼運作、範本專案、
  資料格式的變更、已知限制、下一步。
- [`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md) — 每個決策：要求、原因、做了什麼、測試、實機證據、限制。
- [`docs/audits/ARCHITECTURE_PERFORMANCE_RISKS.md`](docs/audits/ARCHITECTURE_PERFORMANCE_RISKS.md) — 架構風險與效能基準。
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、[`ASTERIA_SPEC.md`](ASTERIA_SPEC.md) 與 `ASTERIA_ASSET_*.md` — 規格（部分為歷史文件，手冊會說明哪些還有效）。
- [`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md) — 第三方素材的來源與授權。

## 授權

程式碼的授權尚未決定（repo 目前沒有 `LICENSE`）。`asset_library/` 內的素材各自為 CC0 或 CC-BY，見
`THIRD_PARTY_ASSETS.md` 與各資料夾的 readme。

---

## English summary

**Asteria** is a Python 2D RPG engine with a PySide6 editor. Turn-based (Octopath-style) and
real-time (Diablo-style) play share one data-driven core; every rule with more than one sensible
answer is an editor option, and the sample games are data, not engine code.

- Install: Python 3.12+, `pip install -e ".[pygame,editor,mv,dev]"`; the C++ kernels are optional
  (`python -m asteria.kernels.build_native`), numpy and pure-Python fallbacks give the same results.
- Use: `asteria-editor` (File > New from Template…, F6 to play), `asteria-preview PROJECT.json`,
  `asteria-upgrade`, `asteria-export` (a playable folder; `--pyz` a single-file game, `--app` a
  macOS bundle), `asteria-import-mv`.
- Samples in `reference_projects/`: `full_verification_demo` (a whole JRPG exercising every system,
  with a headless campaign that checks each one was used), `octopath_demo`, `diablo_demo`,
  `diablo_multiplayer_demo`.
- Develop: `python -m pytest -q` (~3,200 tests), `ruff check` / `ruff format --check`; real-window
  checks under `scripts/*_live_check.py` write evidence to `docs/audits/evidence/`; CI runs the
  suite headless on every push.
- Docs: start with `docs/ENGINE_HANDBOOK.md` (Traditional Chinese); decisions and evidence in
  `docs/audits/DECISION_LOG.md`. Bundled art is CC0 / CC-BY (see `THIRD_PARTY_ASSETS.md`); the
  code licence is not decided yet.
