# Asteria 免安裝版 app

[English](STANDALONE_APP.md)

免安裝版把整個引擎包成一個下載檔：編輯器、試玩、匯出遊戲都在裡面。不用安裝 Python、PySide6、
pygame，也不用編譯任何東西。用它匯出的遊戲，玩家那邊同樣不需要 Python。

## 給遊戲作者：下載與執行

### macOS（Apple silicon，macOS 11 以上）

1. 下載 `Asteria-<版本>-macos-arm64.dmg`（或 `.zip`）。
2. 打開 `.dmg`，把 **Asteria** 拖到 **應用程式（Applications）**。
3. 只有第一次：這個 app 沒有 Apple 開發者簽章，macOS 會擋下雙擊。請 **按右鍵（或 Control＋點按）
   Asteria ▸ 打開**，再按對話框裡的 **打開**。macOS 15 以後若沒有 **打開** 按鈕：到 **系統設定 ▸
   隱私權與安全性**，往下找到「已阻擋 "Asteria"」，按 **強制打開**。
4. 之後就能正常雙擊開啟。

第一次啟動會開啟一份屬於你的 **Full Verification** 範例副本（和原始碼安裝一樣）。
**File ▸ New from Template…** 開新專案；素材庫已經內建在 app 裡。

### 和原始碼安裝的差別

| | 免安裝版 |
| --- | --- |
| 編輯器全部頁面 | 可以 |
| 試玩（▶）與除錯器 | 可以：app 會以遊戲模式再啟動自己 |
| 本機多人連線伺服器 | 可以 |
| C++ 加速（native kernels） | 可以，已預先編好（不需要編譯器） |
| 專案自己的 Python 程式碼 | 可以：內含完整 Python 標準函式庫；另外用 pip 裝的套件不行 |
| **File ▸ Export Game…** | 可以，見下方 |
| 網頁版匯出（`asteria-export-web`） | 不行：需要 `pygbag`，請用原始碼安裝 |

### 匯出玩家免裝 Python 的遊戲

**File ▸ Export Game…** 勾選 **macOS app (.app)** 會產生 `你的遊戲.app`。裡面是一個小型播放器
（沒有編輯器、沒有 Qt）加上你的遊戲，玩家直接雙擊即可（第一次同樣要按右鍵 ▸ 打開）。存檔放在
`~/Library/Application Support/Asteria Games/<遊戲名稱>/saves`，換成新版的 app 後存檔仍在。
`.pyz` 與遊戲資料夾仍可勾選產生，但這兩種需要 Python 3.12 以上加 pygame-ce。

### 命令列

app 裡的程式接受和原始碼安裝相同的指令：

```bash
/Applications/Asteria.app/Contents/MacOS/Asteria                       # 編輯器
/Applications/Asteria.app/Contents/MacOS/Asteria preview path/to/project.asteria.json
/Applications/Asteria.app/Contents/MacOS/Asteria export path/to/project.asteria.json OUT --app
```

## 給維護者：如何建置

要在目標平台上建置（PyInstaller 不能跨平台編譯）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pygame,moderngl,editor,mv,fast,package]"
.venv/bin/python scripts/build_app.py
```

產出 `dist/Asteria.app`（Windows／Linux 是 `dist/Asteria/`）、`dist/Asteria-<版本>-<平台>.zip`，
macOS 另有 `.dmg`。`build/`、`dist/` 已加入 .gitignore，不要提交。選項：
`--sign "Developer ID Application: …"` 用你的開發者身分簽章（預設 ad-hoc）；`--skip-player`、
`--no-archive` 在修改腳本時可以加快建置。

組成方式（`scripts/build_app.py`、`src/asteria/frozen.py`）：

- PyInstaller 凍結直譯器、標準函式庫、PySide6、pygame-ce、numpy、ModernGL。引擎本身**不**凍結：
  以原始碼（已預先編譯 .pyc）複製到 `Contents/Resources/engine/src/asteria`，旁邊是
  `engine/asset_library` 與 `engine/reference_projects/full_verification_demo`。所以引擎用
  `__file__` 找的路徑都和原始碼目錄一樣有效，匯出時也能把引擎複製進遊戲。
- 編輯器用 `sys.executable -m <模組>` 啟動試玩與多人伺服器。app 裡的 `sys.executable` 是 app
  本身，由 `asteria.frozen.editor_main` 照 Python 的方式執行這些 `-m`／`-c` 命令列。
- `AsteriaPlayer.app`（沒有 Qt）放在 `Contents/Resources/player/`。匯出時複製它、改成遊戲名稱、
  把遊戲放進 `Contents/Resources/game`，再重新封印（ad-hoc 簽章）。
- 複製前先編譯 C++ kernel 程式庫（arm64＋x86_64 通用）；沒有編譯器時 app 仍可用 numpy kernel 執行。

發布前請在真實視窗手動檢查凍結版：開啟 Full Verification 範例、試玩、匯出遊戲、啟動匯出的遊戲。

尚未完成：Developer ID 簽章與公證（需要 Apple Developer 帳號）、在 CI 建置 Windows／Linux
（腳本在這兩個平台會產生資料夾版本，但還沒有在那些系統上跑過）。
