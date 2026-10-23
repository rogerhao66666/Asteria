# ARCHITECTURE_PERFORMANCE_RISKS

**2026-10-23 重新核對**（原稿 2026-10-12；D56）。每項都標明證據：
- **Measured**（實測，寫明日期）
- **Code-inspection**（程式碼檢視，2026-10-23）
- **Hypothetical**（推測）

狀態欄：**已處理**（有證據）、**降級**（風險變小但還在）、**未處理**、**新**。

## 1. 架構風險

| ID | 風險 | 狀態（2026-10-23） | 證據 |
|---|---|---|---|
| RISK-01 | 兩條平行的 runtime 路徑：canonical presentation 只有測試在跑，實際遊玩走手刻腳本 | **已處理**（戰鬥） | 可玩 runtime 的戰鬥走 canonical 的 `BattleScreenRuntime`（`runtime/battle_presentation_adapters.py`，由 `playtest/battle_flow.py` 呼叫）；地圖走 `runtime/tile_scene_view.py`。D26–D53 的戰鬥功能都是在這條路上做的 |
| RISK-02 | 規則洩漏到演出層：可玩 runtime 自己決定目標、boost、回合順序 | **降級** | 規則在 `GameSessionRuntime`（`runtime/session/ability_use.py`、`turns.py`）和 `runtime/battle_commands.py`；演出層剩選單狀態（`playtest/battle_flow.py` 的 `_boost_level`、`_skills_for_actor`），不含判定 |
| RISK-03 | MV 語意越界 | **降級** | MV 只剩匯入層（`assets/rpg_maker_mv_*.py`、`runtime/rpg_maker_mv_*.py`）；所有 demo 與範本用免費素材（Lucifer、Critters，D43 起）。`assets/` 仍 import `presentation`／`runtime`（`complex_codecs.py`、`monster.py`、`vfx.py`、`sprite_kinds.py`、`rpg_maker_mv_*.py`），見 RISK-05 |
| RISK-04 | 大量 commit 中靜默刪除功能 | **已處理** | 每個 commit 都有 DECISION_LOG 條目與證據（D26 起）；CI 從 2026-10-23 起每次 push 跑全部測試（RISK-09） |
| RISK-05 | Editor／Runtime 分離 | **降級** | `assets/` 不再 import `editor`（`character_content_pack.py` 已移除）；`runtime/` 只有 `preview.py` import editor（編輯器預覽本來就屬於編輯器）。`assets/` 仍 import `presentation`／`runtime`（8 個檔案）：打包 runtime 不會因此帶入 PySide6，但層次仍不乾淨 |
| RISK-06 | 沒有具體 System | **已處理** | `System` 子類別：`AnimationSystem`、`CameraFollowSystem`（`runtime/systems.py`）、`FieldAISystem`、`SpawnSystem`（`runtime/field_ai.py`）、`EntityActionSystem`（`runtime/entity_actions.py`） |
| RISK-07 | 大型平坦模組 | **未處理** | `presentation/` 58 個檔案、約 15,700 行（原 82 個、12,400 行：檔案少了、總行數多了，因為戰鬥 UI 長大）。沒有死碼證據；不先重構 |
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

**Benchmark 仍缺：** 大型 tilemap、存讀檔時間、編輯器開大專案的時間、多 NPC（100 個以上）的地圖。都還是 **NE**。

## 3. 未來 native（C++）邊界候選

依 `SCOPE_DECISIONS.md` 只做評估。D21 已把粒子更新與碰撞 broad phase 抽成 `asteria.kernels`（純 Python 參考實作、numpy 實作、D48 的 C++ kernel 不需 numpy），native 實作從這一層加。

| 候選 | 潛在效益 | 判斷（2026-10-23） |
|---|---|---|
| Sprite 批次渲染 | 高（大量 sprite／粒子時） | PERF-07 顯示 render 每格 2.7–2.8 ms，沒有必要；要再快先恢復 ModernGL 的 GPU 批次（D1） |
| 碰撞 broad phase | 中到高 | 已在 `asteria.kernels`；50 個實體時 0.2 ms |
| 動畫取樣／粒子更新 | 中 | 粒子已在 `asteria.kernels`；動畫 0.8 ms |
| Event VM、Battle 規則 | 低 | 不建議：不是 CPU 熱點，且要保持確定性與 Python 擴充性 |

**結論（2026-10-23）：** 沒有任何「Measured 且必須用 native 才能解決」的瓶頸；原稿量到的兩個熱點（PERF-01、PERF-02）都已在 Python 層解決。架構風險裡還開著的是 RISK-07（presentation 模組大）與 RISK-05 的後半（`assets/` 依賴上層）。
