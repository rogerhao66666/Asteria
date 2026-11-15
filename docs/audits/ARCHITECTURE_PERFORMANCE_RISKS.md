# ARCHITECTURE_PERFORMANCE_RISKS

**2026-11-15 重新核對**（原稿 2026-10-12；D56）。每項都標明證據：
- **Measured**（實測，寫明日期）
- **Code-inspection**（程式碼檢視，2026-10-23）
- **Hypothetical**（推測）

狀態欄：**已處理**（有證據）、**降級**（風險變小但還在）、**未處理**、**新**。

## 1. 架構風險

| ID | 風險 | 狀態（2026-10-23） | 證據 |
|---|---|---|---|
| RISK-01 | 兩條平行的 runtime 路徑：canonical presentation 只有測試在跑，實際遊玩走手刻腳本 | **已處理**（戰鬥） | 可玩 runtime 的戰鬥走 canonical 的 `BattleScreenRuntime`（`runtime/battle_presentation_adapters.py`，由 `playtest/battle_flow.py` 呼叫）；地圖走 `runtime/tile_scene_view.py`。D26–D53 的戰鬥功能都是在這條路上做的 |
| RISK-02 | 規則洩漏到演出層：可玩 runtime 自己決定目標、boost、回合順序 | **降級** | 規則在 `GameSessionRuntime`（`runtime/session/ability_use.py`、`turns.py`）和 `runtime/battle_commands.py`；演出層剩選單狀態（`playtest/battle_flow.py` 的 `_boost_level`、`_skills_for_actor`），不含判定 |
| RISK-03 | MV 語意越界 | **降級** | MV 只剩匯入層（`assets/rpg_maker_mv_*.py`、`runtime/rpg_maker_mv_*.py`）；所有 demo 與範本用免費素材（Lucifer、Critters，D43 起）。純視覺資料型別已移到 `core.visual_types`、`graphics.animation`、`graphics.draw`、`graphics.combat`；剩下的 runtime 依賴是匯入器將 MV 地圖轉成執行場景元件，見 RISK-05 |
| RISK-04 | 大量 commit 中靜默刪除功能 | **已處理** | 每個 commit 都有 DECISION_LOG 條目與證據（D26 起）；CI 從 2026-10-23 起每次 push 跑全部測試（RISK-09） |
| RISK-05 | Editor／Runtime 分離 | **降級** | `assets/` 不再 import `editor`（`character_content_pack.py` 已移除）；`runtime/` 只有 `preview.py` import editor（編輯器預覽本來就屬於編輯器）。`assets/` 不再依賴 `presentation`；目前只剩 `rpg_maker_mv/map.py`、`rpg_maker_mv/project.py` 兩個匯入流程會用到 runtime，其中地圖轉場器建立場景元件，專案匯入器延遲建立 `GameStartDefinition`。純資料型別已下放，剩餘依賴範圍縮到匯入邊界 |
| RISK-06 | 沒有具體 System | **已處理** | `System` 子類別：`AnimationSystem`、`CameraFollowSystem`（`runtime/systems.py`）、`FieldAISystem`、`SpawnSystem`（`runtime/field_ai.py`）、`EntityActionSystem`（`runtime/entity_actions.py`） |
| RISK-07 | 大型平坦模組 | **降級**（已盤點） | `presentation/` 58 個檔案、約 15,700 行（原 82 個、12,400 行：檔案少了、總行數多了，因為戰鬥 UI 長大）。2026-10-23 逐模組查公開名稱在 `src/`、`tests/`、`scripts/`、`reference_projects/` 的引用：55 個模組有人用；**只有 `preview.py`（130 行）與 `workspace_controller.py`（104 行）除了互相引用外沒有任何引用**，`performance.py` 的 `FrameDiagnostics`、`IndexedEvents`、`BoundedDispatcher`、`ReuseBuffer`、`DegradationPolicy` 也沒有引用（8 個名稱只用到 2 個）。使用者核准後已刪（D57，2026-10-23）：兩個模組和 `performance.py` 的四個類別與一個常數；`FrameDiagnostics` 是 `diagnose` 的回傳型別，留下 |
| RISK-08 | Thread safety | **不需要行動** | `src/` 仍沒有 threading；音樂切換用子程序（D48） |
| RISK-09 | 沒有 CI | **已處理** | `.github/workflows/tests.yml`（2026-10-23）：ruff check／format 加全部測試，Ubuntu、Python 3.12 與 3.13、SDL dummy、Qt offscreen。本機用同樣環境變數跑過 3200 個測試全過；GitHub 上的第一次執行結果要看 Actions 頁 |
| RISK-10 | 存檔／專案沒有遷移 | **已處理** | `core/migration.py`（元件版本遷移，S§33）；D44 起每個新欄位「沒設定就不寫入」，舊專案照常讀（D54、D55 都有相容測試） |
| RISK-11 | **兩個 4,000 行以上的檔案**：`runtime/game_session.py`（4,825 行、290 個方法）與 `runtime/playable_test_runtime.py`（4,476 行、170 個方法）；改一處容易影響別處，加一個功能要在同一個檔案裡散改多處（D55 的縮放就改了三處） | **已處理**（2026-10-23） | 拆成 mixin：`runtime/session/`（18 個模組）與 `runtime/playtest/`（14 個模組），每個方法原樣搬過去、名字不變，`GameSessionRuntime`／`PlayableTestRuntime` 還在原來的模組裡組合。拆完後 3205 個測試、劇情（無頭與真實視窗）、戰鬥圖庫、效能基準都和拆之前一樣 |

## 2. 效能發現

| ID | 熱點 | 狀態 | 證據 |
|---|---|---|---|
| PERF-01 | `text()` 每次呼叫都 new 一個 `pygame.font.Font` | **已處理** | `playtest/text_draw.py` 的 `_menu_font` 依大小快取（`self._fonts`） |
| PERF-02 | 每次 draw 都 `subsurface` + `scale` + `flip` + `copy` + `set_alpha` | **已處理**（戰鬥、地圖） | 戰鬥：`PygameTextureDrawer` 依（圖、來源格、大小、翻轉）快取縮好的圖，只畫可見部分（D48）；地圖：`TileSceneView._sprite` 依格與倍率快取；玩家行走圖與 NPC 圖依大小快取（`graphics/scaling.py` 的 `ScaledImageCache`，2026-10-23）。所有縮放都走同一個 `graphics.scaling.resized`（最近鄰或平滑）。剩下 `platform/pygame_backend.py` 的通用 `draw_texture` 每次仍縮放一次（沒有量到它是熱點） |
| PERF-03 | 合成 presentation 壓力負載 | **已被實測取代** | 見 PERF-07 |
| PERF-04 | `build_frame` 每影格建新的 draw list 並排序 | **低風險** | 戰鬥 n 很小；D48 之後 HUD 與指令列只在變化時重排 |
| PERF-05 | Tile 繪製有 viewport culling | **已處理** | `runtime/tile_draw.py` |
| PERF-06 | 沒有 runtime profiler | **已處理** | `runtime/profiler.py`（`RuntimeProfiler`：逐段計時、計數器、frame pacing）；`scripts/runtime_benchmark.py` |
| PERF-07 | **實機基準**（Measured 2026-10-23，Apple silicon，真實視窗 1280×720，54 個實體，各 600 格） | — | 地圖（50 隻 AI 敵人）：平均 5.1 ms、p95 7.4 ms、p99 10.6 ms；戰鬥：平均 4.3 ms、p95 6.4 ms。每格預算 16.7 ms，用不到三分之一；FPS 56–59 被螢幕更新率卡住。分段：地圖 render 2.8、update 0.9、present 0.9、AI 0.6、collision 0.2 ms；戰鬥 render 2.7、animation 0.8、present 0.8 ms。地圖偶發單格 24 ms 尖峰在 present（合成器），不是引擎 |
| PERF-08 | 專案載入 | **Measured 2026-10-23** | Full Verification 的 `project.asteria.json`（3.8 MB）載入 0.08 s；`import asteria.editor` 0.34 s |
| PERF-09 | **Headless 100 NPC 基準** | **Measured 2026-11-15** | 本機 `.venv`、Python 3.13.15、pygame-ce 2.5.8，`--enemies 100 --frames 300`。104 個實體的 wander field 平均 0.9830 ms／p95 1.2427 ms；patrol 平均 0.9075 ms／p95 1.2144 ms；battle 平均 1.1586 ms／p95 2.9415 ms。巡邏階段用來覆蓋路徑解析快取；這是單次 headless 引擎工作時間，不代表真實視窗 FPS，也不能單獨作為快取前後的效能比較，資料見 `evidence/benchmark_2026-11-15_headless_100npcs.json` |

**Benchmark 仍缺：** 大型 tilemap、存讀檔時間、編輯器開大專案的時間。都還是 **NE**。100 NPC headless 負載已補；仍需 real-window 基準才能量呈現與 frame pacing。

## 3. 未來 native（C++）邊界候選

依 `SCOPE_DECISIONS.md` 只做評估。D21 已把粒子更新與碰撞 broad phase 抽成 `asteria.kernels`（純 Python 參考實作、numpy 實作、D48 的 C++ kernel 不需 numpy），native 實作從這一層加。

| 候選 | 潛在效益 | 判斷（2026-10-23） |
|---|---|---|
| Sprite 批次渲染 | 高（大量 sprite／粒子時） | PERF-07 顯示 render 每格 2.7–2.8 ms，沒有必要；要再快先恢復 ModernGL 的 GPU 批次（D1） |
| 碰撞 broad phase | 中到高 | 已在 `asteria.kernels`；50 個實體時 0.2 ms |
| 動畫取樣／粒子更新 | 中 | 粒子已在 `asteria.kernels`；動畫 0.8 ms |
| Event VM、Battle 規則 | 低 | 不建議：不是 CPU 熱點，且要保持確定性與 Python 擴充性 |

**結論（2026-11-15）：** 沒有任何「Measured 且必須用 native 才能解決」的瓶頸；原稿量到的兩個熱點（PERF-01、PERF-02）都已在 Python 層解決。新增 100 NPC headless 基準未顯示單格 CPU 工作接近 16.7 ms 預算；巡邏路徑解析已在 `FieldAI` 內用有上限的快取。RISK-05 的純資料型別依賴已下放；MV 地圖轉場器仍建立 runtime 場景元件，這是目前保留的匯入邊界耦合。RISK-07（presentation 模組大；盤點出的三處沒人用的程式已刪，D57）仍屬維護性整理，沒有實測效能急迫性。
