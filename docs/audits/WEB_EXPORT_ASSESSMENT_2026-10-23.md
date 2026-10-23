# Web 匯出：依賴盤點與路線評估（2026-10-23）

**結果：** 使用者選了路線 A；實作、證據與限制在 DECISION_LOG **D59**（`python -m asteria.export_web`）。

**目的：** 讓 Asteria 專案能在瀏覽器裡玩。這份是動手前的盤點，供使用者選路線；選定後的實作、證據
與限制記在 DECISION_LOG。數字都是這台機器（Apple silicon、Python 3.13.15、pygame-ce 2.5.8）量的。

---

## 1. 結論（先講）

**建議路線 A：pygbag（pygame-ce 官方的 CPython→WebAssembly 路線）。** 理由：

- 可玩的 runtime（`PlayableTestRuntime` 與它 import 的 283 個 asteria 模組）在 import 時**沒有任何
  第三方套件**（實測 `sys.modules`：numpy、PIL、PySide6、moderngl 都沒進來）；pygame 是執行時經
  `self.pg` 用的，而且用到的子模組（draw、Surface、transform、font、image、mixer、event、key、
  mouse、joystick、mask、time、display）pygame-ce 的 wasm 版都有。
- kernels 本來就有純 Python 後援（`ASTERIA_KERNELS=python`，測試保證三組結果逐位元相同）；C++
  版載入失敗會丟 `ImportError` 被 `available()` 跳過。
- 需要改引擎的地方只有三處小守衛（見 §3），其餘都是「匯出工具」這一層的新程式。

另外三條路線（§4）都要重寫呈現層或不是真的「匯出」，不建議。

---

## 2. 依賴盤點

| 項目 | 現況（證據） | 在 web 上 | 要做的事 |
| --- | --- | --- | --- |
| Python 版本 | `requires-python >= 3.12`；本機 3.13 | pygbag 0.9.3 預設 CPython **3.12** wasm（`app.py: DEFAULT_PYBUILD = "3.12"`） | 無。CI 已在 3.12 跑全部測試 |
| pygame-ce | 2.5.8；runtime 用 `pg.draw`×151、`Surface`×41、`transform`×39、`font`×17、`image`×12、`mixer`×7、`joystick`×4、`mask`×1、`surfarray`×2（只在 numpy kernel 裡） | pygame-ce wasm 版都支援；`surfarray` 不會用到（numpy kernel 不裝） | 無 |
| PySide6 | 只有 `editor/` 與 `presentation/workspace.py` import；runtime 不碰（實測） | 絕不打包 | 匯出時排除 `asteria/editor`（4.4 MB）；`presentation/workspace.py` 不會被 import |
| moderngl | `platform/gpu_*`、`moderngl_backend.py`，只在 `backend_kind="moderngl"` 時 import | 不可用 | web 入口固定 pygame 後端 |
| numpy | 只有 `kernels/_numpy.py`（與 `surfarray`） | pygbag 有 numpy 輪子但要多下載 | 不裝；`ASTERIA_KERNELS=python`。實測 Full Verification 野外一幀 1.25 ms（純 Python kernel、無頭），回合制 demo 幾乎不吃 kernel |
| C++ kernels（ctypes） | `kernels/_native.py` 找不到或載入不了 `.dylib` 時丟 `ImportError` | wasm 沒有 dylib | 匯出時不帶 `kernels/native/`；行為已正確 |
| 執行緒 | `runtime/image_preloader.py` 用 `ThreadPoolExecutor`（D48 的戰鬥圖預先解碼），只在 display driver 不是 dummy／offscreen 時啟用 | wasm **沒有執行緒**；emscripten driver 不是 dummy，會被誤啟用 | 加守衛：`sys.platform == "emscripten"` 時不開（或改同步一張一張解） |
| socket／subprocess | `runtime/debug_server.py`（只在 `--debug-port` 時 import）、`multiplayer_preview.py`（threading）、`kernels/build_native.py`（subprocess，只在編譯時） | 不可用 | web 入口不開 debug port；多人連線（F3）在 web 上關閉並寫進限制 |
| 主迴圈 | `PlayableTestRuntime.run()` 用 `time.sleep` + 自旋等下一幀 | 瀏覽器必須是 `async def main()`、每幀 `await asyncio.sleep(0)`，不能 `time.sleep` | web 入口自己寫 async 迴圈：每幀 `runtime._frame(pg.event.get(), dt)` + `present()`；`run()` 桌面照舊 |
| 檔案讀取 | 專案 JSON（3.8 MB）、`playable_test_manifest.json`、1,218 張 PNG、`pg.image.load(path)`、`Path(__file__)` 找 `rpg/built_in_text/*.json` | pygbag 把整個資料夾打成 `.apk`（zip）掛進記憶體檔案系統，`open()`／`Path` 都照常 | 無。匯出時重用 `project_tools.referenced_files()` 只帶用到的檔 |
| 存檔與設定 | 寫在 `<專案>/saves/`：`slot1..3`、`autosave`、`settings.json`（4 個寫入點：`game_save.py`、`save_slots.py`、`game_menus.py`、autosave）；起始存檔 8 KB，大型存檔約 55 KB | 記憶體檔案系統**重新整理就沒了**；pygbag 沒有自動持久化 | 新增 `runtime/web_persistence.py`：開場把 `localStorage` 裡的 `saves/*` 還原到資料夾，之後每 N 幀檢查 mtime 有變就寫回 `localStorage`（經 pygbag 的 `platform.window`）。4 個 slot + 設定 < 300 KB，遠低於 5 MB 上限。遊戲程式碼不用改 |
| 音樂與音效 | demo：6 個 `.ogg`（音樂）、4 個 `.wav`（音效）；`pygame.mixer.music` 串流、`mixer.Sound` | SDL_mixer wasm 支援 ogg vorbis 與 wav；**mp3 不行**；瀏覽器要使用者點一下才准出聲（pygbag 的開場遮罩處理） | 匯出時檢查副檔名，mp3 報錯並說要轉 ogg；wav 可用（pygbag 會提醒改 ogg，大檔再轉） |
| 字型 | Latin 用 `pg.font.Font(None, size)`（pygame 內建字型）與專案的 `font.ttf`；**中文用系統字型**（`cjk_font_path` 找 STHeiti／Noto 等） | 瀏覽器沙盒**沒有系統字型**：中文會畫成方框 | 匯出選項 `--cjk-font`；建議把 Noto Sans TC（OFL，可再散布）放進 `asset_library/` 並在 web 入口註冊為 CJK 字型（見 §6 問題 2） |
| 視窗 | `set_mode((1280, 720))`、`display.flip()` | 畫在固定大小的 canvas，pygbag 依視窗縮放 | 無 |
| 執行期載入來源 | — | pygbag 產生的 `index.html` 在**玩家開頁面時**從 `https://pygame-web.github.io/archives/0.9/` 下載 Python wasm runtime（約 20 MB，瀏覽器會快取） | 預設接受；要離線／內網時用 `--cdn` 指向自己放的一份（見 §6 問題 3） |
| 打包大小 | demo 18 MB（圖 13 MB、專案 3.8 MB）；引擎去掉 editor／multiplayer／validation／templates 後 **3.4 MB** 原始碼 | 一個 `.apk` zip 約 15–20 MB（PNG 已壓縮） | 可接受；之後可再砍沒用到的模組 |
| 效能 | 本機原生：野外 5 ms、戰鬥 4.6 ms（真實視窗 60 fps）；純 Python kernel 無頭野外 1.25 ms | CPython wasm 約慢 3–5 倍、沒有 JIT；預估一幀 10–25 ms | 實匯出後量；若不夠再做「web 省略後製／粒子」的選項（不改規則，只是畫面） |

**不會進 web 的部分（寫進限制）：** 編輯器、多人連線、ModernGL 後端、C++ kernel、debug server、
真實視窗才有的預先解碼、手把（瀏覽器的 Gamepad API 要先按一下才會出現，可用但不保證）。

---

## 3. 引擎要改的三處（都很小、桌面行為不變）

1. `runtime/image_preloader.py`／`playtest/resources.py`：`sys.platform == "emscripten"` 時不開執行緒
   （同一介面改成同步一張一張解，或直接關）。
2. `platform/pygame_battle_ui.py` 的 `cjk_font_path`：先看一個可設定的字型路徑（環境變數或 manifest
   `fonts.cjk`），找不到才找系統字型。這也順便修了 D52 記的「匯出不附中文字型」。
3. `PlayableTestRuntime`：把 `run()` 迴圈裡「一幀」的部分抽成 `step(events, dt)`（`_frame` +
   present + 計數），web 入口與桌面共用；`run()` 的等待與 profiler 照舊。

---

## 4. 路線比較

| 路線 | 做法 | 要改多少 | 風險 | 建議 |
| --- | --- | --- | --- | --- |
| **A. pygbag** | CPython + pygame-ce 編成 wasm，我們的 Python 原樣跑 | 匯出工具一個模組 + §3 三處 | 效能（要實測）、runtime 從 CDN 載入、無系統字型 | **選這個** |
| B. Pyodide + 自寫 canvas 後端 | Python 跑在 Pyodide，繪製改呼叫 JS canvas | runtime 是直接拿 `self.pg` 畫（`pg.draw` 151 處、Surface 41 處、font、mixer），等於重寫整個呈現層與音訊 | 數週工作、兩套後端要一直對齊 | 不建議 |
| C. 轉成 JS／TS | 重寫引擎 | 全部 | — | 不可行 |
| D. 串流（伺服器跑 Python，瀏覽器收畫面） | WebRTC／MJPEG 把視窗送到瀏覽器 | 中 | 需要一台一直開著的伺服器，不是「匯出」 | 不建議；多人連線以後若要走 WAN 再談 |

---

## 5. 建議的批次（核准後做）

**W1 匯出指令與 web 入口（一個 commit）**

- `python -m asteria.export_web PROJECT.json OUT_DIR [--title] [--cjk-font PATH] [--cdn URL]
  [--serve [PORT]] [--allow-missing]`，也掛成 `asteria-export-web`。
  步驟：重用 `project_tools.referenced_files` 複製專案與授權檔 → 複製精簡的引擎（排除 editor、
  multiplayer、validation、templates、kernels/native、`__pycache__`）→ 檢查音訊副檔名 → 寫 `main.py`
  （async 迴圈、`ASTERIA_KERNELS=python`、存檔鏡像、CJK 字型）→ 呼叫 `pygbag --build`（沒裝 pygbag
  時說明怎麼裝；`--serve` 用 pygbag 的本機伺服器）。輸出 `OUT_DIR/build/web/`（`index.html` +
  `.apk`），可直接丟到任何靜態主機或 itch.io。
- `runtime/web_persistence.py`（localStorage 鏡像，桌面上可用 dict 假的 storage 測）。
- §3 的三處守衛。
- 測試：匯出產物的檔案清單與排除；`main.py` 的迴圈在桌面以 dummy driver 跑 120 幀不出錯（和 web
  共用同一段程式）；存檔鏡像往返；mp3 被擋；pygbag 不在時的訊息；ruff。

**W2 Full Verification 真的在瀏覽器裡跑（文件 commit）**

- 匯出 demo、`--serve`，用內建瀏覽器開 `http://localhost:8000`：截標題、野外、對話、戰鬥指令、
  技能說明、勝利、存檔→重新整理→讀回、設定切 zh-TW（有字型才看得到中文）。
- 量每幀時間（web 入口記 `performance.now()` 差值印到 console）。
- 六段式報告（D58）、手冊 §1 指令與 §7 限制表、`THIRD_PARTY_ASSETS.md`（若加字型）、
  `docs/audits/evidence/web_export/`。

---

## 6. 請使用者決定

1. **路線**：A（pygbag）？
2. **中文字型**：要不要把 Noto Sans TC（SIL OFL 1.1，可再散布、可打包）放進 `asset_library/fonts/`，
   web 匯出預設帶上（約 7 MB；用 fonttools 子集化常用字可到 2–3 MB，但 fonttools 不在 dev 依賴裡）？
   不帶的話 web 版的中文是方框，英文正常。
3. **runtime 來源**：接受玩家開頁面時從 pygame-web 的 CDN 載入 Python（約 20 MB、瀏覽器快取）；
   `--cdn` 留給要自架的人。還是預設就把 runtime 複製進輸出資料夾（輸出多 20 MB，完全離線可玩）？
4. **存檔**：用 `localStorage`（同一個瀏覽器、同一個網址才看得到；清站台資料就沒了）；要不要另外給
   「匯出存檔成檔案下載／匯入」？建議先不做，記在限制。
