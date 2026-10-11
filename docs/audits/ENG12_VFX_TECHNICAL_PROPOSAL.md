# ENG-12／VFX-02／VFX-03 技術提案（D17 Phase 4）

**狀態：** 待審查。核准前不實作。
**日期：** 2026-10-11
**原則（依 D17 指示）：** 沿用既有 ModernGL 後端；不移植 C++；不替換 renderer；pygame 路徑保留為預設與後備。

---

## 1. Current Implementation（現況）

| 需求 | SPEC | 現有程式 | 狀態 | 缺口 |
|---|---|---|---|---|
| ENG-12 batching、render groups | S§8 | `platform/moderngl_backend.py`：GL 3.3 core、單一 sprite program、依 texture 切換 flush 的 quad batcher；D17-3 加入 `rotation_deg`。`preview --backend moderngl` | B | 只有 scene preview 使用；**playable runtime（field、戰鬥、選單）全部畫在 pygame Surface 上**；沒有 render group 概念（只有 `TextureDraw.layer／depth` 排序） |
| VFX-02 lights、normal maps、shadows、bloom、color grading、screen shaders | S§12、AD§12 | `graphics/light.py` `Light2D`、`graphics/material.py` `Material2D`（albedo／normal／emissive、blend）、`render/lighting.py` `ShadowCaster2D`、`render/postprocess.py` `PostEffect2D／PostProcessStack`、`render/pipeline.py` `FrameRenderPlan`、`render/executor.py` `execute_frame`、`render/headless.py`（只記錄指令） | C | 全部是 headless 指令模型；**沒有任何後端執行**；沒有 shader；沒有 scene 資料（component）承載燈光或後製；editor 無法撰寫 |
| VFX-03 trails、afterimages、fog／weather／water | S§12 | `graphics/environment.py` `AmbientLight2D`、`Fog2D`、`ParticleEmitter2D`；`render/environment.py` `EnvironmentCommand` | C | 只有資料類別；沒有模擬、沒有繪製、沒有 trail／afterimage／water |

相關已存在的能力（可直接沿用）：
- 戰鬥世界層已是 backend-neutral 的 `TextureDraw` 清單（`BattlePresentationRuntime.build_frame`），經 `PygameTextureDrawer` 繪製；UI 經 `PygameBattleUiBackend`。
- VFX sprite sheet 播放、hit flash（`draw_screen_fx`）、加法混合（D16 EDT-08）已在 pygame 路徑。
- `RuntimeProfiler`：已有 render／present／vfx 分段；`draw_calls`、`gpu_time` 標 Unsupported。
- 實機證據（D15，Apple M5）：ModernGL 視窗 400 sprites／frame 60.7 fps；canonical 戰鬥 pygame 路徑平均 frame 6.5 ms（render 4.1 ms、present 0.7 ms）、58.9 fps。

## 2. Existing Renderer Architecture（現有架構）

目前有三條互不相連的繪製路徑：

```
A. Playable runtime（實際遊戲）
   PlayableTestRuntime._frame → _draw_field / _draw_battle / 選單
     ├─ field：pygame blit（背景、tile、實體、FieldEffects VFX、對話）
     ├─ battle：CanonicalBattleAdapter.draw
     │     ├─ BattlePresentationRuntime.build_frame → TextureDraw[] → PygameTextureDrawer
     │     └─ BattleUiRenderer → PygameBattleUiBackend（面板、量表、文字、VFX、screen fx）
     └─ pg.display.flip()

B. Scene preview（asteria-preview 非 playable 專案）
   RuntimeBackend／TextureBackend 介面
     ├─ PygameRuntimeBackend
     └─ ModernglRuntimeBackend（GL 3.3 core、batched quads）

C. render/ 指令模型（headless）
   FrameRenderPlan → execute_frame → HeadlessRenderBackend（只記錄 ops）
```

視窗、事件與輸入一律由 pygame-ce（SDL2）負責；ModernGL 在 pygame 建立的 GL context 上繪製（Architecture Decision 5），所以輸入、事件迴圈與關閉偵測在兩個後端相同。

## 3. Missing Functionality（缺少的功能）

1. **Playable runtime 的 GPU 呈現：** 遊戲本體沒有 GL 路徑，因此 batching 與所有 shader 效果在實際遊玩中都不存在（ENG-12）。
2. **Render groups：** 沒有「世界（受光）／世界（不受光）／特效／UI」分組，後製與光照無法只作用在世界層。
3. **後製堆疊執行：** bloom、color grading、screen shaders（vignette、flash、wave、grayscale…）沒有 shader 也沒有參數資料流（VFX-02）。
4. **2D 光照：** `Light2D` 沒有 scene component、沒有 light map、沒有 ambient 套用（VFX-02）。
5. **Normal maps 與 shadows：** `Material2D.normal_texture_id`、`ShadowCaster2D` 沒有任何消費者（VFX-02）。
6. **Trails／afterimages：** 沒有資料、沒有模擬（VFX-03）。
7. **Fog／weather／water：** `Fog2D`、`ParticleEmitter2D` 沒有執行；water 沒有任何模型（VFX-03）。
8. **撰寫：** editor 沒有燈光、材質、環境、後製的撰寫或預覽；Python API 也沒有。
9. **量測：** profiler 無 GPU 時間與 draw call 數。

## 4. Proposed Integration（整合方案）

### 4.1 核心決策：GPU Presenter + 漸進式 render groups（建議）

不改寫 playable runtime 的 pygame 繪製碼（約 1,600 行、已有大量測試與實機證據）。改為：

1. **GpuPresenter（R1）：** 選用 `moderngl` 後端時，視窗以 `OPENGL` 開啟；`runtime.screen` 變成同尺寸的離屏 pygame Surface（現有繪製碼完全不變）。每幀把 Surface 上傳為 GL texture，經後製鏈畫到 default framebuffer，再 `flip`。
   - 恆等後製時，輸出必須與 pygame 路徑逐像素相同（回歸基準）。
2. **Render groups（R2）：** 已是 `TextureDraw` 的世界層（戰鬥 combatant／attachment／VFX，以及 field 的 tile 與實體——field 先改為產生 `TextureDraw`）改送 GL batcher，分到 `world_lit`、`world_unlit`、`effects`；UI 與文字仍畫在 pygame Surface，作為 `ui` group 以 alpha 疊在最上層。
   - 這樣光照與後製只影響世界層，UI 保持清晰。
3. **效果 pass（R3–R6）** 掛在 render group 之間：`world_lit` → light map 相乘 → fog → `effects`（加法）→ bloom → color grading／screen shaders → `ui`。

```
world_lit ──► [lighting: ambient + Σ lights (+normal) − shadows] ─┐
world_unlit ──────────────────────────────────────────────────────┤
                                                                   ├─► fog ─► effects(add) ─► bloom ─► grade/screen ─► ui ─► present
```

不採用的替代方案：
- **整個 playable runtime 改寫成 GL 指令：** 回歸風險過高，且與「不替換 renderer」衝突。
- **只用 pygame 做所有效果：** bloom、normal map、shadow 在 CPU 上成本不可接受；但部分效果保留 pygame 近似版作為後備（見 §7）。

### 4.2 Canonical 資料（不建平行格式）

| 資料 | 位置 | 說明 |
|---|---|---|
| `LightSource2D` component | scene entity | 包裝既有 `Light2D` 欄位（kind、radius、intensity、color、casts_shadow、layer_mask） |
| `ShadowCaster2D` component | scene entity | polygon（沿用 `render/lighting.py` 模型） |
| `Environment2D` component | scene（camera 或 scene settings entity） | ambient（`AmbientLight2D`）、fog（`Fog2D`）、weather preset、post stack（`PostEffect2D` 清單） |
| 材質 | sprite sheet asset metadata `material` | normal／emissive sheet id（影格對齊 body sheet，同 CMP layer 的規則）、blend、receives_light |
| Trail／afterimage | entity component `MotionTrail2D`；戰鬥 timeline cue `afterimage` | 長度、間隔、淡出、顏色 |
| Water | `WaterRegion2D` component | 區域、波長、速度、tint |
| 戰鬥用 | battle manifest／encounter：環境與 post stack 覆寫 | 例：boss 戰 bloom + grading |

全部經 component registry 自動進 Inspector、存檔與 Python API；`default_component_registry()`（D17-3）新增這些型別即可讓 editor、preview、project tools 一致。

### 4.3 撰寫

- Inspector 直接編輯上述 component（既有 schema 機制）。
- Editor 新增 **Environment** 分頁：post stack 排序、參數、啟停；材質指定（在 Character Composition／Animation 分頁旁加 Material 欄）。
- 預覽：editor 用 ModernGL standalone context 把同一條 pass 鏈畫到離屏 FBO，讀回 QImage 顯示（與遊戲同 shader，非近似）。無 GL 時顯示 pygame 後備結果並標示。

## 5. Performance Considerations（效能）

- **預算：** 60 fps → 16.7 ms。現況 frame 6.5 ms，餘 ~10 ms。目標：GL 路徑在 1080p、全後製時 Apple M5 增加 ≤ 3 ms，維持 ≥ 60 fps。
- **上傳成本：** 960×540 RGBA ≈ 2 MB／幀，1920×1080 ≈ 8 MB／幀。使用 `Surface.get_view("2")`／`get_buffer` 避免 Python 端複製；BGRA→RGBA 在 shader swizzle；只在 Surface 有變更時上傳（UI 層可加 dirty flag）。R2 後世界層不再經 Surface，上傳量只剩 UI。
- **Batching：** 現有 batcher 遇 texture 切換就 flush；R2 加入 tileset／sprite atlas 與 group 內依 texture 穩定排序（只在不改變混合結果時），降低 draw call。persistent dynamic VBO（`buffer.orphan()`）取代每次 flush 新建 buffer。
- **光照：** light map 用半解析度 FBO，每盞點光一個加法 quad（無上限問題）；normal map 走 forward lit shader，每 draw 最多 8 盞影響光（依距離挑選）。陰影只對 `casts_shadow` 的光計算，上限 4 盞（設定可調）。
- **Bloom：** bright pass + 半／四分之一解析度可分離高斯（2×2 pass）+ 合成；RGBA16F FBO。
- **粒子／天氣：** CPU 模擬（numpy 非必要，純 Python 上限約 2k 粒子／幀，以 profiler 驗證），GL instanced quads 繪製；macOS 無 compute shader（見 §6）。
- **量測：** profiler 新增 `gpu_upload`、`gpu_post`、`gpu_lights` 分段；GL timer query（`ctx.query(time=True)`）填入目前標 Unsupported 的 `gpu_time` 與 `draw_calls`。

## 6. macOS Compatibility（macOS 相容性）

- macOS 的 OpenGL 已標示 deprecated 但仍可用：Apple Silicon 透過 Metal 轉譯支援到 **4.1 core**。現有後端要求 3.3 core，已在 M5 實機 PASS。
- **限制與對策：**
  - 不使用 compute shader（需 4.3，macOS 沒有）→ 粒子 CPU 模擬。
  - 不依賴 geometry shader（4.1 有，但效能差）→ 陰影 volume 在 CPU 產生 quad。
  - GLSL 一律 `#version 330`；core profile + forward-compatible；不用已移除的固定管線。
  - **Retina／HiDPI：** drawable 尺寸與視窗尺寸不同。viewport 用 `ctx.fbo.size`（實際像素），邏輯座標維持 virtual layout；以 `PixelScalePolicy` 決定 nearest 放大，避免像素藝術模糊。
  - **vsync：** `set_mode(..., vsync=1)`，與現有 frame pacing 量測比對。
  - RGBA16F render target 在 Apple GPU 可用；建立失敗時退回 RGBA8（bloom 品質降低但可運作）。
- **長期風險：** Apple 未來若移除 OpenGL，pygame 路徑仍完整可玩（§7）。改用 Metal（例如 wgpu）屬 renderer 替換，不在本提案範圍。

## 7. Fallback Strategy（後備策略）

| 等級 | 後端 | 提供的效果 |
|---|---|---|
| **L0** | pygame（預設，現況） | 全部現有畫面；ambient 與點光以 pygame `BLEND_RGB_MULT` 的近似 light map（radial gradient 快取）；fog 以均勻疊色；天氣粒子、trail、afterimage（皆 backend-neutral）；bloom、normal map、shadow、water 扭曲、color grading LUT **停用** |
| **L1** | ModernGL presenter | L0 全部 + 後製堆疊（bloom、color grading、screen shaders）+ GPU light map + fog pass + water |
| **L2** | ModernGL + render groups | L1 全部 + normal map 光照 + shadows + batched 世界層 |

- **選擇：** `--backend`、manifest `render.backend`、editor Play 設定。預設維持 pygame，直到 R7 實機驗證通過、由你決定是否改預設。
- **自動降級：** context 建立失敗、shader 編譯／連結失敗、必要擴充缺失 → 記錄原因（profiler／debugger 可見），整個 session 回到 L0，遊戲照常進行；不在遊玩中途切換。
- **效果宣告：** 後端回報 capability（`lights`、`normal_maps`、`shadows`、`bloom`、`color_grading`、`water`）；資料中要求但後端不支援的效果靜默略過並在 Problems 面板列出一次。遊戲規則不受影響（效果純屬呈現）。

## 8. Regression Risks（回歸風險）

| 風險 | 影響 | 對策 |
|---|---|---|
| GL 輸出與 pygame 不一致（alpha 預乘、gamma、取樣） | 畫面偏色、邊緣暈 | 恆等 pipeline 逐像素等於 pygame Surface 的測試；不使用 sRGB framebuffer（與 pygame 一致）；texture 一律 nearest |
| 既有 golden baseline 只涵蓋 pygame | GL 路徑沒有基準 | GL 另建基準（standalone context）；pygame 基準不變 |
| HiDPI 尺寸錯誤 | 畫面只佔 1/4 或模糊 | viewport 取實際 drawable 尺寸；實機檢查 |
| 實機腳本截圖取 `runtime.screen` | 截到的是後製前畫面 | GL 路徑截圖改為 framebuffer 讀回（已有 `fbo.read()` 慣例） |
| 每幀上傳成本 | 高解析度掉幀 | 分段量測；R2 後只上傳 UI；dirty flag |
| field 改產生 `TextureDraw`（R2） | field 畫面順序／位置改變 | R2 前先建 field 畫面 golden；pygame 路徑也改用同一份 draw list（單一來源），逐像素比對 |
| CI 無 GL | GL 測試無法執行 | GL 測試用 `moderngl.create_standalone_context()`，失敗則 skip 並標示；不把 skip 當 PASS |
| editor 預覽與遊戲不一致 | 撰寫結果失真 | editor 用同一條 pass 鏈（同 shader 原始碼） |
| 新 component 改變存檔／專案格式 | 舊專案載入 | 新 component 皆有預設值；Project 版本 +1 並附 migration 測試 |

## 9. Test Plan（測試計畫）

- **UT（headless）：** component 驗證與序列化；post stack 排序與參數；light 選取（每 draw 最多 8 盞）；陰影 polygon 投射幾何；trail／afterimage／天氣粒子以固定種子決定性模擬；fallback 選擇邏輯（模擬 context／shader 失敗）；capability 宣告。
- **GL（standalone context，無法建立則 skip）：** 恆等 presenter 逐像素等於 pygame；light map 取樣點數值（中心、半徑外 = ambient）；normal map Lambert 已知法線；陰影遮蔽點測試；bloom 能量（亮點外擴、全暗不變）；LUT 恆等；water 扭曲位移上限；旋轉 quad（D17-3 已有）。
- **HI：** playable runtime 以隱藏 GL 視窗跑 field、canonical 戰鬥各 120 幀，帶完整效果，無錯誤且 profiler 有 GPU 分段；強制 shader 失敗時自動退回 L0 並可繼續遊玩。
- **GS：** editor Environment 分頁、材質欄、預覽影像與遊戲 framebuffer 比對。
- **RM（`scripts/real_machine_validation.py` 新增）：** `gpu_presenter`（恆等、fps、截圖）、`gpu_lighting`（燈光場景截圖、fps）、`gpu_post_stack`（bloom＋grading 1080p fps）、`gpu_fallback`（強制失敗後仍可遊玩）。
- **PF：** 400 sprites + 全後製 1080p 在 M5 ≥ 60 fps；frame 增量 ≤ 3 ms。
- **人工：** 新增 M6「效果目視檢查」程序（光照方向、陰影、bloom 是否過曝、像素是否保持銳利）。結果只記 PASS／FAIL／BLOCKED／NOT EXECUTED。

## 10. Implementation Batches（實作批次）

| Batch | 內容 | 規模 | 主要需求 | 完成條件 |
|---|---|---|---|---|
| **R1** | GpuPresenter：playable runtime 可選 ModernGL；Surface 上傳；恆等 pass；HiDPI；自動降級；profiler GPU 分段與 timer query | M | ENG-12 | 恆等逐像素測試、HI、RM `gpu_presenter` |
| **R2** | Render groups：field 改產生 `TextureDraw`（pygame 也用同一份）；世界層送 GL batcher；UI 疊層；atlas；persistent VBO | L | ENG-12 | field／戰鬥 golden 不變、draw call 下降有量測 |
| **R3** | 後製堆疊：`Environment2D`（post stack）、bloom、color grading（LUT／lift-gamma-gain）、vignette／flash／wave／grayscale；Environment 分頁；L0 子集 | M | VFX-02 | GL 測試、editor 預覽、RM `gpu_post_stack` |
| **R4** | 2D 光照：`LightSource2D`、ambient、light map；pygame 近似版；editor 光源 gizmo | M | VFX-02 | light map 測試、RM `gpu_lighting` |
| **R5** | Normal maps（材質 metadata）、`ShadowCaster2D` 陰影 | M | VFX-02 | Lambert／遮蔽測試、RM 截圖 |
| **R6** | VFX-03：`MotionTrail2D`、戰鬥 `afterimage` cue、天氣（粒子 preset：雨、雪、落葉）、fog pass、`WaterRegion2D` | M–L | VFX-03 | 決定性模擬測試、HI、RM 截圖 |
| **R7** | 驗證收尾：RM 全部、PF、M6 人工程序、文件與矩陣 | S | 全部 | 不以單元測試宣稱完成 |

建議順序：R1 → R3 → R4 → R6 → R2 → R5 → R7。R2 回歸風險最高，放在已有效果可以檢驗之後；R5 依賴 R2 的 lit group。

**需要你決定的事項：**
1. 是否採用 §4.1 的 Presenter + 漸進式 render groups（建議採用）。
2. L0（pygame）是否提供近似光照與 fog，或在 pygame 下直接停用光照（建議提供近似版，避免同一專案在兩個後端差異過大）。
3. R7 完成後，macOS 預設後端是否改為 ModernGL（建議在 R7 實機結果出來後再決定）。
4. 環境資料放在 scene component（建議）或 playable manifest。
