# ASTERIA_PROGRESS.md

**Status:** Canonical implementation ledger\
**Canonical role:** Frozen baselines, implementation progress, test
status, known gaps and NEXT

> Progress records implementation state and never overrides the four
> specification documents.

# Asteria 編輯器 --- 進度紀錄

commit: `16a6ebd` --- 已 push 到 `origin/main`

## 這次工作階段修的東西(技能樹編輯器)

### 修好的 bug

1.  **新增節點(Add Node)會跑到很遠的地方** 原本新節點永遠往畫布絕對原點
    (0,0) 排,跟手動拖曳過的既有節點群完全對不上。
    改成往「既有節點群的左上角」附近找空格排(`authoring_hub_widget.py`
    的 `_free_position`)。

2.  **拖曳節點放開後跳回原位**
    真正原因:單一節點的技能樹裡,畫布範圍(scene rect)只包住那一個節點,
    `QGraphicsView`
    會把小於視窗的畫布置中顯示------所以不管節點拖去哪,畫布跟著它
    跑、又被置中,節點就一直「回到」畫面正中央。多節點的樹因為畫布範圍固定
    不變,才沒事。
    改成一個**固定尺寸的邏輯畫布**(2400×1600),不再跟著視窗或節點位置變動
    (`_update_scene_rect`)。

3.  **新建技能樹的 root 節點沒有置中**
    同一個根因的延伸:置中計算以前用「視窗當下的寬高」去算,而畫布是在還沒
    排版完成前就建好的,量到的尺寸是錯的。改成用固定畫布尺寸的正中心當作預
    設位置,不再需要「事後重新置中」這種依賴時機的補救邏輯。

4.  **拖曳一個節點,另一個節點看起來反方向移動**
    原因是每次拖曳的每個像素都會重算畫布範圍,而畫布範圍的原點一變,畫面捲
    動基準跟著偏移,造成沒被拖的節點視覺上跟著動。改成拖曳中只重畫連線,放
    開滑鼠才重算畫布範圍。

5.  **只有一個節點時完全不能拖曳** 原因是
    Connect(連線)模式沒有跟著切換的技能樹重置------在別的樹按過 Connect
    後切到新樹,連線模式還是開著,點節點被當成「選連線起點」而不是
    拖曳。改成切換到不同技能樹時自動關閉 Connect 模式。

6.  **Connect 關閉後滑鼠游標還是十字** `QGraphicsView` 的 viewport
    有自己一份游標設定,原本只設到 view 本身沒設 到 viewport。兩邊都設。

7.  **表格儲存格編輯時文字看不到、被裁切變形** `QTableWidget::item` 的
    CSS padding 會讓 Qt 用「縮進後的文字範圍」而不是
    整個儲存格去放編輯框,行高刻意留的呼吸空間因此被吃掉,編輯框被壓成只剩
    幾像素高。加了一個自訂 delegate 強制編輯框永遠填滿整個儲存格。

8.  **角色外觀(Appearance)面板 / 表單被裁到看不到左邊** 兩個疊加的原因:

    -   macOS 的 Qt 樣式預設把 `QFormLayout` 置中,改成明確靠左對齊。
    -   表單重建後 Qt 會把焦點交給子元件,`QScrollArea`
        因此自動把畫面往右捲
        去讓有焦點的東西露出來,把左邊擠出畫面。改成每次選定記錄後,排一個
        延後執行的「捲回最左邊」動作,確保發生在那次自動捲動之後。

### 新增的 UX

-   **智慧參考線吸附**:拖曳節點時,X/Y 座標跟其他節點很接近(6px 內)會自動
    對齊,並顯示黃色虛線提示對齊了哪一軸(類似 PowerPoint 的智慧參考線)。
-   **選取/連線來源節點會發亮**:邊框變亮金色,清楚知道正在點哪個節點。
-   **Connect 按鈕按下會亮起**(補上 `QPushButton:checked` 樣式)。
-   **分割線的醜圓點拿掉**,改成 1px 細線。
-   **左側清單欄變窄**(190px 起,可自己拖動調整),右邊編輯區拿到更多空間;
    標題文字改成跟著目前選的類別走(選 Items 就顯示「Items」,不再永遠寫
    「Character」)。
-   **編輯器視窗開啟位置**:不再交給 OS
    預設置中(在某些多螢幕/寬螢幕設定下
    會兩邊都被裁出畫面外),改成明確定位到主螢幕左上角附近。

## 這次工作階段之外、repo 裡本來就有的改動(這次一併 commit)

使用者確認一併 commit 進去的、非本次對話產生的既有未提交工作:

-   角色外觀 /
    素材產生相關:`actor_appearance.py`、`asset_thumbnails.py`、
    `character_generator.py`、`unit_authoring.py`、`class_design_panel.py`
-   ModernGL 渲染後端:`moderngl_backend.py`、`moderngl_shaders.py`
-   Runtime 角色連結:`actor_link.py`
-   對應的測試檔(`test_actor_appearance.py`、`test_moderngl_backend.py`
    等)
-   專案存檔/測試產生的資料檔:`test.asteria.json`、`actor_appearances.json`、
    `characters/`、`tiles/`(這些是本機測試/存檔資料,不是原始碼,commit 前
    已跟你確認過要不要一起收)

## 驗證方式

所有修改都在無畫面環境(`QT_QPA_PLATFORM=offscreen`)用真實的
`AsteriaEditorWindow` 走完整流程驗證過(不是猜測),包含: - 模擬滑鼠
press/move/release 拖曳節點,比對「拖曳後場景座標位移」是否等於
「螢幕上實際位移」 - 量測 root 節點中心點相對視窗中心的像素誤差 -
直接讀取表格編輯器的 geometry/字型,而不是只看畫面截圖 -
重跑完整測試套件:**1244 個測試全數通過**

## 已知待處理 / 尚待你確認

-   角色外觀面板的「開啟自動捲到最左邊」邏輯已改好且驗證過會生效,但實際畫
    面截圖回饋這輪還沒收到你最終確認。
-   `saber` 技能樹如果是舊專案裡已經存過位置的樹,root
    不會自動置中(這是刻
    意設計------尊重你手動排過的版面);要置中的話按「Reset Layout」。

------------------------------------------------------------------------

# Documentation consolidation state --- 2026-09-17

Canonical top-level documentation is fixed to:

1.  `ASTERIA_SPEC.md`
2.  `ASTERIA_ASSET_SPEC.md`
3.  `ASTERIA_ASSET_PIPELINE.md`
4.  `ASTERIA_ART_DIRECTION.md`
5.  `ASTERIA_PROGRESS.md`

Keep the old seven-file source set until migration audit closure.

------------------------------------------------------------------------

# Composable Presentation gap audit --- 2026-09-20

Decision: finish the system architecture/implementation before producing the final test/Starter asset pack.

Documentation audit found that the previous canonical documents already covered generic composition, equipment references, layers, VFX separation, projectiles, damage numbers, and presentation/gameplay separation, but did **not** define the complete generic attachment/socket contract strongly enough.

Canonical specs now explicitly require:

- Baked / Layered / Attached / Procedural / Hybrid presentation as concurrent first-class modes.
- Generic visual attachments, not a weapon-only subsystem.
- Stable named sockets/anchors with optional per-frame/keyed transforms.
- position/rotation/scale/flip/visibility/z-order and transform inheritance.
- attach/detach/swap, lifetime/ownership, serialization and save-load identity.
- reusable actor motion + equipment + VFX composition without variant explosion.
- generic animated world/screen text; damage numbers are presets, not Engine Core semantics.
- Editor/Python parity for attachment authoring and preview.
- fidelity rule: composition must never force lower-quality art; baked/hybrid remains first-class.

Implementation status at this audit:

- Generic Presentation sequence/composition/runtime: implemented in prior batches and targeted-tested.
- Layered high-fidelity presentation and independent VFX: implemented in prior batches and targeted-tested.
- VFX local/world/socket anchor concepts: present in prior asset/runtime work.
- Asset stable IDs, AssetStore, Scene binding, runtime materialization: implemented in prior batches and targeted-tested.
- **Generic Visual Attachment runtime with per-frame socket binding: NOT YET CLOSED.**
- **Attachment serialization/lifecycle/runtime ownership end-to-end: NOT YET CLOSED.**
- **Attachment Editor authoring/preview: NOT YET CLOSED.**
- **Generic animated text/popup runtime + editor preset authoring: NOT YET CLOSED.**
- **Full repository ModernGL/Qt E2E integration: NOT YET VERIFIED.**

NEXT implementation priority:

1. Generic Socket/Anchor canonical model.
2. Generic Visual Attachment model and serialization.
3. Runtime socket sampling + attachment transform resolution.
4. Attachment lifecycle/ownership and scene save/load.
5. Presentation commands for attach/detach/swap/property animation.
6. Generic animated text/popup primitive and reusable presets.
7. Editor socket/attachment authoring and live preview using the same canonical model.
8. Backend integration and stress tests.
9. Repository-level closure audit against all five canonical documents.
10. Only after system closure, produce/validate the final Starter/Reference assets and vertical-slice test content.


------------------------------------------------------------------------

# Art / Presentation closure and pre-asset-validation state --- 2026-09-25

The 2026-09-20 composable-presentation gap list above is historical. Subsequent Chat batches closed the specified Chat-side implementation seams through Batch 106, including generic sockets/anchors, attachments, lifecycle and save/load integration, animated text, editor/live-preview bridges, rendering/backend contracts, VFX, material/lighting, camera choreography, audio synchronization, fidelity import, project integration, resource lifetime/order-safe batching, layered attachment compositing, action/equipment/presentation binding, equipment presentation presets, frame-aware character layers, facing-aware attachment compositing, and high-fidelity animation acceptance.

Current Chat-side consolidated verification: `PYTHONPATH=src python -m pytest -q` → **596 passed** on 2026-09-25; `python -m compileall -q src` → PASS. Historical canonical-repository verification remains **1244 passed** at commit `16a6ebd`; that is historical evidence and is not claimed as a fresh full-repository run.

Formal asset production now uses the project skill `.agents/skills/asteria-asset-production/SKILL.md`. Animation delivery is one complete animation at a time; internal frame-by-frame production is allowed/preferred when needed. Source Integrity precedes canonicalization, and Technical PASS alone is not final.

Remaining external/final gates: merge this Chat-side implementation onto the canonical repository; run the complete repository suite; exercise actual PySide6 widgets, actual ModernGL/Pygame GPU/shader/material/lighting paths, real audio-device timing, and hardware profiling with final assets. Starter assets then undergo the formal asset-production gates and vertical-slice validation.


------------------------------------------------------------------------

# Full canonical integration closure — 2026-09-25

The previously separate canonical engine/editor/RPG/runtime line and the later asset/composable-presentation line have now been integrated into one source tree.

Integration baseline:

- Engine/Editor/RPG/Runtime: `Asteria_v0.159.0_COMPLEX_REFERENCE_RPG_ACCEPTANCE_CURRENT_FULL.zip`.
- Asset/Presentation: cumulative implementation through Asset/Presentation Batch 106.
- Canonical documentation: the five-document set in this repository.
- Asset production procedure: `.agents/skills/asteria-asset-production/SKILL.md`.

Fresh merged-tree verification on 2026-09-25:

- `PYTHONPATH=src pytest -q` -> **1734 passed, 8 skipped**.
- `python -m compileall -q src tests` -> **PASS**.
- Source modules: **334 Python files** under `src/`.
- Test modules: **233 test files** under `tests/`.

The earlier `596 passed` Chat-side result and historical `1244 passed` result remain provenance/history only; the 1734/8 result above is the fresh verification of the integrated tree.

The old statement that the Chat-side implementation still needed to be merged onto the canonical repository is superseded by this closure. Remaining external gates are real PySide6 UI interaction, real ModernGL/Pygame GPU/shader/material/lighting execution, real audio-device timing, hardware profiling with final assets, and final Starter asset art review/vertical-slice validation.

## Asset Production Protocol v2 closure

The formal Asteria asset-production workflow now separates animation authorship from image generation. Animation semantics are defined by an explicit production plan; generation is constrained to realizing per-frame specifications under the Master Reference. Source Integrity precedes canonicalization, failed frames return to the smallest affected production unit, and final acceptance requires technical plus visual/temporal gates. The repository-local `asteria-asset-production` Skill implements the same protocol. This closes the prior process gap where a generator could invent a plausible-looking sheet that passed structural checks without satisfying authored motion or identity requirements.

## Character Generator Phase 1
Implemented the first canonical Character Generator core: layered part catalog, RPG-like 48x48 starter preset, four-direction/three-frame topology, deterministic RGBA compositing, recipe metadata, Qt-neutral Editor workspace model, and regression tests. Built-in generation and custom/imported artwork remain equal workflows. Starter visual parts are a separate art-production deliverable and must meet the project's RPG-Maker-like test-asset quality target before replacing engineering fixtures.

## Character Generator Phase 2
- Added a first-class Qt Character Generator editor surface with layered part selectors, live 4-direction frame preview, playback, and canonical asset generation.
- Preview uses the same CharacterGeneratorWorkspace/canonical recipe as Python authoring; no GUI-only character model was introduced.
- Built-in generated characters and custom/imported artwork remain equal canonical-asset paths.
- Starter visual target is clean RPG-Maker-like test quality; engineering fixtures are not user-facing defaults.

### Character Generator Phase 3 — modular authoring contract
Implemented the first production-facing modular-part topology contract: explicit shared 48x48 Starter walk topology, interchangeable part manifests, topology/frame/dimension validation, optional palette-mask contract, and authoring-template export. This establishes the deterministic seam required before formal Starter body/hair/outfit art is admitted. Art quality target for Starter generator parts is clean RPG-Maker-like test/reference quality; engineering fixtures are not accepted as default Starter art.

## Character Generator Phase 3 Integration Vertical Slice
- Added `starter_assets/character_generator/rpg_like_48_v1` with canonical 48x48 RGBA / 4-direction x 3-frame topology.
- Canonicalized the accepted Body Base source into 12 real transparent frames and retained Body/Face/Hair/Outfit visual-master sources separately.
- Added a real Starter Library manifest, deterministic compositor previews, and validation report.
- Added integration regression tests for real RGBA dimensions, 12-frame topology, deterministic composition, and explicit Art-vs-Engineering status.
- Current closure: **ENGINEERING PASS / ART PENDING**. Hair/outfit layers in this vertical slice are engineering-derived to validate compositing and are intentionally not claimed as final RPG-Maker-quality Starter art. Visual-master source sheets remain references until their independent layers pass the Art gate.

---

## Final clean handoff update (2026-09-26)

A second Chat-side consolidation is prepared as an **engine-only** handoff. Rejected/generated Starter art and reference art have been removed rather than promoted. Character Generator code remains supported; its production modular art library is deferred. During integration, the user's RPG Maker MV assets may be used externally as private development fixtures through the generic Asset Pipeline. They are not Asteria distribution assets.

See `ASTERIA_FINAL_ALIGNMENT_AUDIT.md` for the current implementation/external-validation/deferred-content boundary.

------------------------------------------------------------------------

# SPEC gap audit, scope decisions and CB0 baseline --- 2026-10-09

**Scope decisions** (`SCOPE_DECISIONS.md`, delivered outside the repo in
`Asteria_Codex_SPEC_Audit_Handoff.zip`; recorded in
`docs/audits/DECISION_LOG.md`):

- Character Generator is formally cancelled. AI art generation stopped.
  Generic Asset Pipeline, Animation, Attachment and Presentation are kept.
- ARPG Engine, Dual-Mode Demo and JRPG Demo are deferred until original SPEC
  closure; the JRPG Demo will use licensed free assets.
- C++ migration and renderer replacement are deferred.

**Work recorded since the 2026-09-26 handoff** (previously missing from this
ledger): real RPG Maker MV asset/database/map import and project conversion,
the MV-backed character creator and click-to-place character creation
(2026-09-26 → 2026-10-09). MV data stays in `asteria.assets.rpg_maker_mv*`;
`tests/test_architecture_boundaries.py` now enforces that.

**Corrections to earlier entries.** Commit `bf4a993` (2026-09-26, "integrate
canonical engine baseline") removed, without a ledger note:
`platform/moderngl_backend.py`, `platform/moderngl_shaders.py`,
`editor/actor_appearance.py`, `editor/class_design_panel.py`,
`editor/unit_authoring.py`, `editor/asset_thumbnails.py`,
`runtime/actor_link.py` and their tests. The first section of this ledger
(commit `16a6ebd`) therefore no longer describes the current tree. Restoring
the ModernGL backend (as a parallel backend, not a renderer replacement) and
the generic actor-appearance/actor-link/thumbnail features is planned as
CB9 and CB14 in `docs/audits/REMAINING_WORK_PLAN.md`.

**Removed:** all of `assets/` (AI-generated and MV-derived starter
characters), the starter character-pack code, the Ready Characters editor tab
and art-only scripts/tests. A backup exists outside the repository.

**Audit result:** 97 active requirements → A 17 / B 20 / C 44 / D 16
(`docs/audits/SPEC_TRACEABILITY_MATRIX.md`). Closure verdict: **FAIL**. The
main gaps are integration: the playable runtime does not consume Battle
Presentation or execute the Event VM, and battle rules are partly hard-coded
in `runtime/playable_test_runtime.py`.

**Verification (2026-10-09):**
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → **1854 passed**;
in a clean clone without the git-ignored MV reference → **1799 passed,
55 skipped, 0 failed**; `compileall` PASS. CI workflow added
(`.github/workflows/ci.yml`).

**NEXT:** CB3 (battle rules back into canonical data) → CB1 (Event VM in the
runtime) → CB2 (incremental Battle Presentation integration).

## Runtime integration batches CB3 / CB1 / CB2 (first increment) --- 2026-10-09

- **CB3:** `rpg.BattleSessionRules` (RPG database schema v24) names the
  knockout resource, the gauge hit trigger and boost resource/cost/limit.
  `GameSessionRuntime` uses battle targeting data, the battle scheduler and
  these rules; `runtime/` holds no project-specific battle ids (enforced by
  `tests/test_battle_session_rules.py`).
- **CB1:** authored event programs run during play: a foreground
  `EventRunner` for interactions, the scene's autorun/parallel scheduler,
  standard WORLD commands (`runtime/world_command_handlers.py`), dialogue and
  choices, and game save version 2 keeps an event that is mid-dialogue.
- **CB2 (first increment):** the session records an ordered battle log;
  `LegacyPygameBattleAdapter` (default) and `CanonicalBattleAdapter`
  (`BattleScreenRuntime` + `PygameBattleUiBackend`) both consume it, and a
  parity test proves they agree. The canonical UI renders but has open layout
  defects; canonical combatant sprites, VFX/audio playback and legacy
  retirement remain.
- Found: the reference project's `playable_assets/` images were removed in
  `bf4a993`, so Run Project on it cannot load its images until licensed art or
  test-only placeholders are added.

Verification: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` →
**1884 passed**. Real-window runs were not executed (headless SDL only).

## Engine core, editor and packaging batches CB4–CB9, CB12, CB14 --- 2026-10-10

- **Assets:** free-licensed playable test art and audio for the reference
  project (CC0 Kenney / Ninja Adventure, CC-BY-SA 3.0 LPC soldier) with
  `THIRD_PARTY_ASSETS.md` and `playable_assets/CREDITS.md` (closes F-1). The
  Free Pixel Art Asset Pack stays local-only (no redistribution right).
- **CB2 / F-2:** the canonical battle UI layout defects are fixed (`ebc5bf3`);
  legacy remains the default.
- **CB14:** `ActorLinkComponent`, actor appearance and asset thumbnails are
  restored without the Generator; "Place Character from Sprite Sheet…" and
  "Set Actor Appearance…" in the shell; Inspector dropdowns for actors,
  assets and parents.
- **CB4:** input action map (keyboard + gamepad, rebinding, Project v10),
  fixed-step simulation, concrete Animation/Camera systems, transform
  parent/child hierarchy, scene transitions with persistent entities.
- **CB5:** colliders (box/circle), layers/masks, spatial-hash broad phase,
  triggers; 1000 colliders → 948 candidate pairs in 3.7 ms.
- **CB6:** `AudioMixer` with music/ambient/effect buses and fades on
  `pygame.mixer`.
- **CB7:** prefabs, variants, overrides and propagation, with editor commands.
- **CB8:** animation state machines (parameters, triggers, any-state,
  wait-for-finish) and runtime frame events.
- **CB9:** ModernGL sprite-batching backend restored from `16a6ebd`;
  `asteria-preview --backend moderngl`; pygame stays the default.
- **CB12:** component migration chain, `asteria-upgrade` and `asteria-export`
  (the exported folder launches in its own process).

Verification: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` →
**1954 passed**; correctness lint passes. Real-window runs (gamepad, audio
latency, GPU window) were not executed.

**NEXT:** CB10 (editor tools), CB11 (game systems), CB13 (golden suite,
profiler), then CB15 retirement after item-by-item approval.

## Game systems batch CB11 --- 2026-10-10

Shops and quests (RPG DB v25, save v6), conditional/luck loot, equipment set
bonuses, crafting stations/chance/quality/experience, field AI and spawn
zones with visible encounters, pause / quest log / shop / save-load / game
over screens in the playable runtime, and faction reputation,
relationships, achievements, bestiary and enemy capture (save v7). See
`docs/audits/DECISION_LOG.md` D11 for commits and remaining gaps (no editor
UIs for these definitions yet; field AI/spawns not yet run by the playable
runtime). Verification: **1975 passed** offscreen; no real-window run.

## D12 closure decisions executed --- 2026-10-10

F-3 fixed (interaction multipliers reach actual damage through the existing
pipeline; preview matches runtime). CB15 retirement review submitted for
approval (nothing removed). Form-based Game Systems editors (shops, quests,
factions, achievements, equipment sets, capture rules) share one undoable
API with scripts. Field enemy AI and spawn zones run in the playable game;
battle capture menu; recipe discovery and crafting screen; achievement,
bestiary and settings screens. Details and per-batch reports: DECISION_LOG
D12/D13. Verification: **1998 passed** offscreen; no real-window run.

## Code style unification --- 2026-10-10

`ruff` is now the single style tool (configuration in `pyproject.toml`):
line length 120, double quotes, rules E/W (pycodestyle), F (pyflakes), I
(imports, except package `__init__.py` whose order is load-bearing), B
(bugbear) and UP (pyupgrade), with four documented ignores. The whole code
base was reformatted in one mechanical commit (`.git-blame-ignore-revs`
lists it), star imports in tests/codecs were replaced by explicit imports,
unused imports/variables and lambda assignments were fixed, and the shared
playable-runtime fixtures moved to `tests/conftest.py`. CI runs
`ruff check` and `ruff format --check`. Run both locally before committing:

    .venv/bin/ruff check src tests scripts
    .venv/bin/ruff format src tests scripts

## CB13 validation and CB10 editors, CAM-02 camera --- 2026-10-11

Golden asset suite (11 assets × 8 checks) with regression/timing baselines
and update rules, runtime benchmark, asset auto-fix and atlas, battle-scoped
resource release. Editors: animation, action timeline, runtime debugger (live
game over a loopback channel), play from selection / restart / log, script
editor (highlighting, API completion, traceback navigation, reload), record
cut/copy/paste, multi-select, filter, context menu and batch edit, a global
Problems panel with navigation, an enemy AI / boss phase editor whose preview
uses the battle's own selection logic, and a VFX tool whose placement the
battle renderer reads. Camera: look-ahead, bounds, target groups, eased
cutscene/boss shots and shake, driven by event commands. Fixed on the way:
the reference boss crashed on its final phase (unregistered AI condition).

Verification: **2097 passed**; real-machine run on macOS/Apple M5 with two new
checks (boss camera, editor tools in a Cocoa window, screenshots reviewed —
three UI defects found and fixed). Matrix: A26/B56/C12/D3 (DECISION_LOG D16).
Not done: hands-on use by a person (M1–M5), record drag-and-drop/sort, field
follow camera in the playable map, battle-intro boss camera. The engine is
not complete.
