# ARCHITECTURE_PERFORMANCE_RISKS

本文件只做**有證據的風險評估**，不做實作：不加 C++、不替換 renderer。
每項風險都會標明證據是：
- **Measured**（本次實測）
- **Prior-measured**（舊報告）
- **Code-inspection**（程式碼檢視）
- **Hypothetical**（推測）

## 1. 架構風險

| ID | 風險 | 證據類型 | 證據 | 影響 | 建議（對應 Batch） |
|---|---|---|---|---|---|
| RISK-01 | **兩條平行的 runtime 路徑**：canonical presentation／events 只有測試在跑，實際遊玩走手刻腳本 | Code-inspection | `runtime/preview.py:88-95` → `playable_test_runtime.py`；`src/` 中 presentation 只有 editor 預覽在 import | Editor 改的東西在遊玩中無效；有長期維護兩套系統的風險（D6 明確禁止） | CB1、CB2、CB3 incremental；以 G-BATTLE gate 判斷舊路徑何時退役 |
| RISK-02 | **規則洩漏到演出層**：playable runtime 自己決定目標、boost、量表和回合順序 | Code-inspection | `playable_test_runtime.py:503,506-510,515`；`game_session.py:290` | 形成第二套 battle rules（D6 禁止）；資料驅動原則（S§2）失效 | CB3 先把規則搬回資料，再接 presentation |
| RISK-03 | **MV 語意越界** | Code-inspection | `runtime/rpg_maker_mv_map_render.py`；工作樹的 `graphics/mv_weapon_visual.py`、`presentation/battle_screen.py:178-189`、`battle_runtime.py` `_weapon_visuals` | 違反 `CODEX_HANDOFF.md` 第 4 點和 S§44.1；之後換成免費素材時，會被 MV 格式綁住 | CB0：提案 patch（`docs/audits/proposed/`） |
| RISK-04 | **大量 commit 中靜默刪除功能** | Code-inspection（git） | `bf4a993` 一次動了 298 個檔案（+22010／−19698），刪掉 ModernGL 和外觀模組，ledger 沒有記錄 | 回歸沒被察覺；ledger 失真 | CB0：ledger 修正；CB13：CI + 刪除檔案要經過審查 |
| RISK-05 | **Editor／Runtime 分離**：`assets/character_content_pack.py`（未追蹤）在 assets 層 import `editor.create_character_command`；assets 層也 import presentation（`complex_codecs.py`、`monster.py`、`vfx.py`）和 runtime（`rpg_maker_mv_map.py`） | Code-inspection | 上述 import | 打包 runtime 時會被迫帶入 editor（PySide6）依賴 | CB15 移除 content pack；CB12 打包時做 import-boundary 測試 |
| RISK-06 | **沒有具體 System**：`SystemScheduler` 存在但 0 個子類別；行為散落在 `GameSessionRuntime`／`PlayerRuntime` 的手動呼叫 | Code-inspection | `core/system.py`、`core/scene.py:117` | §7 的 system-oriented 架構沒有被驗證；ARPG 階段會被迫重構 | CB4 |
| RISK-07 | **大型平坦模組**：`presentation/` 有 82 個檔案、約 1.24 萬行，多數只有測試在用 | Code-inspection | `find src/asteria/presentation -name '*.py'` | 維護成本高、死碼風險 | CB2 完成後，依實際使用度再評估（不先重構） |
| RISK-08 | **Thread safety** | Code-inspection | `src/` 中沒有任何 threading；runtime 透過子程序和 editor 分離 | 目前低風險；如果之後做背景資產載入，需要所有權規則 | 不需要行動 |
| RISK-09 | **沒有 CI，環境相依的測試** | Code-inspection | 沒有 `.github/`；部分 MV 測試沒有 `skipif` | 回歸只能靠本機發現 | CB13 |
| RISK-10 | **存檔／專案沒有遷移** | Code-inspection | `core/serialization.py` 版本不符直接 raise | 引擎一變動，舊專案就打不開（違反 S§39） | CB12 |

## 2. 效能發現

| ID | 熱點 | 證據類型 | 數據 | 判斷 |
|---|---|---|---|---|
| PERF-01 | `PlayableTestRuntime.text()` **每次呼叫都 new 一個 `pygame.font.Font`**（`runtime/playable_test_runtime.py:102-104`） | **Measured**（本次，`SDL_VIDEODRIVER=dummy`，300 次平均） | 每次建立 font 約 **0.640 ms**，快取 font 約 **0.009 ms**（約 70 倍）。`_draw_battle` 有 15 個 `self.text(` 呼叫點（部分在英雄／敵人／技能迴圈內），`_draw_build_menu` 有 14 個 | **推算**（Derived，不是端到端量測）：每個戰鬥影格約 20–40 次 → **約 13–26 ms**，光 font 建立就可能超過 60 fps 的 16.7 ms 預算。修法很簡單（快取 font），但檔案屬於 legacy adapter，依 D6 只做最小修正 |
| PERF-02 | `PygameRuntimeBackend.draw_texture` 每次 draw 都做 `subsurface` + `transform.scale` + `flip` + `copy` + `set_alpha` | **Measured** | 最壞路徑（48→64 縮放 + flip + alpha）每次約 **0.021 ms**；1000 個 draw 約 21 ms | 大量 sprite／粒子時會成為瓶頸。正確方向是快取縮放／翻轉結果或用 GPU 批次（D1、CB9），不是 C++ |
| PERF-03 | 合成 presentation 壓力負載 | **Prior-measured**（`audit/PERFORMANCE_FINDINGS.md`） | 1494 draws、11 batches、平均 13.43 ms、2 個掉幀 | headless 的合成數據，**不是**實際 GPU 或 pygame 的量測 |
| PERF-04 | `BattlePresentationRuntime.build_frame` 每影格建立新的 draw list 並排序（`battle_runtime.py:471`） | Code-inspection | 只有 O(n log n)，戰鬥場景 n 很小 | 低風險（Hypothetical） |
| PERF-05 | Tile 繪製有 viewport culling（`runtime/tile_draw.py:41`） | Code-inspection | — | 已處理 |
| PERF-06 | 沒有 runtime profiler（S§34） | Code-inspection | 只有合成負載工具 | 無法建立實機基準 → CB13 |

**Benchmark 缺口：**
- 實機 frame time（pygame field 和 battle）
- 資產解碼／上傳時間
- 大型 tilemap
- 大量 entity 的碰撞（目前還沒有碰撞系統可以量）
- 存讀檔時間
- Editor 大專案開啟時間

以上都是 **NE**。

## 3. 未來 native（C++）邊界候選

依 `SCOPE_DECISIONS.md`，**只做評估，不納入目前範圍**。

| 候選 | 潛在效益 | 遷移複雜度 | 耦合／binding 邊界 | 所有權 | 相容性 | 證據 |
|---|---|---|---|---|---|---|
| Sprite 批次渲染 | 高 | 中 | `TextureBackend` Protocol（`platform/backend.py`）已經是乾淨的邊界 | 後端持有 GPU 資源；Python 端持有 `TextureDraw` 值物件 | 可以和 pygame 並存 | PERF-02（Measured）。**但應該先恢復 ModernGL（Python + GPU），它可能已經足夠**（D1） |
| 碰撞 broad phase | 中到高（大量 entity） | 低（新模組） | 純函式：AABB 陣列進、配對出 | 呼叫端持有資料 | 新功能，沒有相容負擔 | Hypothetical：碰撞系統還不存在（CB5），應該先用 Python + spatial hash 量測 |
| 動畫取樣／粒子更新 | 中 | 中 | `presentation/vfx_runtime.py`、`property_animation.py` | runtime 持有 | 需要保持 deterministic | Hypothetical |
| Event VM | 低 | 高 | `events/vm.py` | — | 可恢復性和序列化難以跨語言 | 不建議 |
| Battle 規則 | 低 | 高 | `rpg/battle*` | — | 確定性 snapshot 與 Python 擴充性 | 不建議：回合制不是 CPU 熱點 |

**D21 更新：** 粒子更新和碰撞 broad phase 已經抽成 `asteria.kernels`（純 Python 參考實作 + numpy 實作）。之後要加 native 實作時，從這一層加，數據見 DECISION_LOG D21。

**結論：** 目前沒有任何「Measured 且必須用 native 才能解決」的瓶頸。已量到的兩個熱點（PERF-01、PERF-02）都可以在 Python 層解決（快取、GPU 批次）。
