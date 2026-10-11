# DECISION_LOG

**日期：** 2026-10-09
**階段：** Stage D（Review）——只有 Audit／Planning，沒有授權任何實作
**基準：** `main` @ `d69817c` + 未提交工作樹（未改變，見 §0）

每條決策記錄：決策內容、原因、證據、受影響模組、SPEC 依據、後續執行條件。

---

## §0 工作樹事件紀錄（透明揭露）

在收到本決策文件之前，依照前一個指示「做 P0、美術部分不要 commit」，我在工作樹做了以下動作。收到 Decision 3 和「仍處於 Audit 階段」的指示後，已經**全部撤回**：

| 動作 | 撤回狀態 |
|---|---|
| 在新 branch `p0-baseline-cleanup` 做了 1 個本機 commit（刪除 `ready_user_hero`），沒有 push | 已撤回：`git reset --soft` 後刪除 branch，HEAD 回到 `d69817c`；`ready_user_hero` 的刪除回到「工作樹中未提交」的原狀 |
| 把未追蹤的美術檔、starter 程式、相關測試移到 repo 外的封存資料夾 | 已全部移回原位，封存資料夾已清空並刪除 |
| 修改 `assets/__init__.py`、`editor/shell.py`、`editor/resource_resolver.py`、`gameplay/abilities.py` | 已還原成原本的工作樹內容 |
| P0-3 重構：把 MV 武器語意移到 asset adapter，新增通用 `CombatantOverlay` | 已還原；成果保存成**提案 patch** `docs/audits/proposed/P0-3_mv_semantics_to_asset_boundary.patch`（未套用。若要套用，`assets/__init__.py` 還需要加一行 `from .rpg_maker_mv_weapon import *`） |
| 刪除 `tests/test_editor_mv_character_creator.py` 中 Ready Characters 相關的 4 個測試與 2 行斷言 | **部分無法還原（見下）** |

**無法逐字還原的部分：** `tests/test_editor_mv_character_creator.py` 的這 3 個測試函式只存在於未提交的工作樹中（git 裡沒有任何版本）：
- `test_starter_hero_button_places_a_real_playable_character_at_the_clicked_cell`
- `test_user_defined_hero_library_places_the_complete_preset_on_the_map`
- `test_ready_character_picker_is_separate_from_modular_character_generator`

共約 108 行，我沒辦法逐字復原。另一個被刪的測試和 2 行斷言已經逐字還原。Codex session log 裡有它們較早的版本（例如 `~/.codex/sessions/2026/10/05/rollout-2026-10-05T12-28-34-*.jsonl`、`2026/10/06/rollout-2026-10-06T13-13-51-*.jsonl`、`2026/10/06/rollout-2026-10-06T13-43-15-*.jsonl`），但和最後的版本不同（例如 `pack_combo.count()` 是 7 不是 8、斷言路徑是 `ready_user_hero/walking.png`）。為了避免捏造測試內容，**我沒有自己重寫**。
影響：完整測試套件從 1928 個降到 1925 個。這三個測試都只服務 Ready Characters／starter pack（已取消的 Character Generator 範圍，見 D2）。是否要從 log 重建，由你決定。

撤回後驗證：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -p no:cacheprovider` 結果是 **1922 passed, 3 failed**。3 個失敗就是原本的 boss 美術測試（D4），跟 Audit 當時一致。

---

## D1 — ModernGL Backend

**決策：** 不退役。列入 Closure Plan 的 **CB9（GPU Renderer 復原，規劃中）**。Audit 階段不復原也不刪除。

**證據：**
| 問題 | 發現 |
|---|---|
| Canonical SPEC 有要求 ModernGL 嗎？ | 沒有指名 ModernGL。但 `ASTERIA_SPEC.md` §8 Rendering 要求 batching、transparency、render groups；§12 要求 2D lights、normal maps、bloom、color grading、screen shaders；`ASTERIA_ART_DIRECTION.md` §12 要求 dynamic lighting、post-processing，§22 要求 shader/material hooks、pixel-perfect sampling；`ASTERIA_ASSET_PIPELINE.md` §41 要求 GPU-friendly texture layout、batched rendering。`CODEX_HANDOFF.md` 第 6 點和 `ASTERIA_FINAL_ALIGNMENT_AUDIT.md` 都把「Pygame/ModernGL rendering paths」列為要驗證的路徑 |
| Git 歷史中原本的實作 | `16a6ebd`（2026-09-16）新增 `platform/moderngl_backend.py`（257 行，`ModernglRuntimeBackend(RuntimeBackend, TextureBackend)`：GL 3.3 context、textured-quad 批次、`load_texture` 透過 PIL）、`platform/moderngl_shaders.py`（56 行 GLSL sprite VS/FS）、`tests/test_moderngl_backend.py`（178 行）；`runtime/preview.py` 的 `_BACKEND_FACTORIES` 有 `"moderngl"`；`pyproject` 有 extra `moderngl=["moderngl>=5.8", …]`。它只是 **Phase 1：批次 sprite quad**，沒有 lighting／bloom／post |
| 何時被移除 | `bf4a993`「chore: integrate canonical engine baseline」（2026-09-26）。commit message 和 canonical 文件都沒有說明原因；`ASTERIA_PROGRESS.md` 第 84 行仍然列為已 commit 的工作 |
| 現有 Backend 有等效能力嗎？ | **沒有。** `platform/pygame_backend.py` `PygameRuntimeBackend.draw_texture` 是逐一 CPU blit，每次 draw 還做 `transform.scale`／`flip`／`copy`，沒有 shader、批次或 GPU 路徑。`render/*`（lighting、postprocess、environment）和 `presentation/render_backend.py` 只有 headless 指令模型和 Protocol（docstring 寫「ModernGL/Pygame/etc.」），沒有 GPU 執行器 |
| 是否造成 Regression | **是。** 批次 GPU sprite 路徑和它的 178 行測試消失；§12 shader 類需求從「有基礎可延伸」退回「沒有任何 GPU 後端」 |
| 復原所需工作與依賴 | `git show 16a6ebd:<path>` 可以取回 3 個檔案（共 491 行）；`.venv` 已經有 `moderngl 5.12.0`，但 `pyproject.toml` 已經沒有這個 extra；要重新接上 `preview._BACKEND_FACTORIES` 和 `platform/__init__`，並對現行 `TextureBackend`／`TextureDraw`（含 `layer`／`depth`／`opacity`／`flip_x`）重新驗證。估計 **M（2–4 天）**，其中真實 GPU 驗證屬於 EXTERNAL gate。§12 的 lighting／bloom 等不在復原範圍內，需要另外規劃 |

**與 Scope Decision 的關係：** `SCOPE_DECISIONS.md` 寫「Defer … renderer replacement」，`CODEX_PROMPT.md` 寫「Do not … replace renderer」。復原 ModernGL 是**恢復一個被移除的既有並列後端**，不是取代 pygame，所以不衝突；但 CB9 開工前仍需要你明確批准。
**受影響模組：** `platform/`、`runtime/preview.py`、`presentation/render_backend.py`、`render/*`、`pyproject.toml`
**後續執行條件：** (1) 你批准 CB9；(2) pygame 仍然是預設後端；(3) 兩個後端用同一組 `TextureDraw` 契約測試對照輸出。

---

## D2 — Character Appearance Panel／Character Generator

**決策：** Character Generator 是 **E（Formally cancelled）**。Generator 專屬 UI／工作流程規劃退役（CB15）。被 `bf4a993` 刪掉的外觀相關模組，經檢查**大部分是通用功能而不是 Generator 專屬**，列入 CB14 復原／整合。

**證據：被刪的模組（`16a6ebd` 版本）**
| 模組 | 實際用途 | 分類 |
|---|---|---|
| `editor/actor_appearance.py`（198 行）`ActorAppearanceLibrary.set(actor_id, sprite_sheet_asset_id, frame_index, flip_x)` | 任意 Actor → 任意 sprite sheet 的外觀指派 | **通用**（Sprite Selection） |
| `runtime/actor_link.py`（23 行）`ActorLinkComponent` + 246 行測試 | 場景 Entity ↔ RPG Actor 的連結 component | **通用**（Character/Entity Presentation） |
| `editor/asset_thumbnails.py`（85 行）`asset_thumbnail` | Assets 面板的影格縮圖 | **通用**（Asset 預覽） |
| `editor/unit_authoring.py`（159 行） | Actor／Enemy 合併成單一「Unit」撰寫介面 | 通用（資料庫 UX） |
| `editor/class_design_panel.py`（402 行） | 職業裝備相容、等級表、點數分配 | 通用（RPG 資料庫） |

這些都不依賴 Character Generator。

**證據：目前的 Generator 專屬程式（退役候選，CB15）**
`assets/character_generator.py`、`character_generator_topology.py`、`rpg_maker_mv_generator.py`、`character_bundle.py` 的 `CharacterBundleGenerator`、`editor/character_generator_widget.py`、`character_generator_workspace.py`、`ready_character_library_widget.py`（未追蹤）、`assets/starter_character.py`、`starter_character_packs.py`、`starter_sprite.py`、`character_content_pack.py`（未追蹤）、`scripts/build_starter_template_art.py`、`rebuild_asteria_boss_aura.py`、`rebuild_starter_side_views.py`、`validate_mv_character_creator.py`，以及相關測試。

**必須保留／整合的通用能力（對照目前狀態）**
| 能力 | 目前所在 | 狀態 |
|---|---|---|
| Sprite Selection | Inspector 的 `SpriteRenderer2D.sprite_sheet_asset_id` 欄位 | C（沒有 picker／縮圖；Actor 外觀指派已被刪除） |
| Animation Configuration | `Animator2DComponent`、`runtime/animation_binding.py` | C（沒有 state machine；編輯器只有預覽） |
| Attachment Points | `presentation/attachments*.py`、`editor/attachment_authoring.py`、`attachment_preview.py` | B |
| Character/Entity Presentation | `editor/create_character_command.py`（**與 Generator 耦合**：吃的是 `GeneratedCharacterBundle`） | C：要抽出一個「從 canonical 視覺資產建立 Entity + Actor」的通用命令 |
| Sprite Scale／Position／Layer | `Transform`、`SpriteRenderer2D`、Inspector | B |
| Animation Preview | `editor/animation_widget.py`（59 行）、Generator 內建預覽 | C：Generator 退役後，預覽要轉到通用動畫編輯器 |
| Generic Asset Integration | `assets/*`、`editor/resource_resolver.py`（walking sheet 重建） | B |

**SPEC 依據：** `ASTERIA_SPEC.md` 最後一節「Character Generator」（optional）→ 由 `SCOPE_DECISIONS.md` 取消；§5（Inspector、Asset preview）、§6、§44.4 仍然有效。
**後續執行條件：** CB14（通用 inspector／外觀）要**先於** CB15（Generator 退役）完成，確保沒有任何通用能力只存在於 Generator UI 裡。退役一律走「封存／移除提案 → 你批准 → 執行」。

---

## D3 — `ready_user_hero`

**決策：** **不 commit 刪除**（工作樹維持原狀）。依證據，它只服務已取消的範圍，建議**正式移除**，但要等你批准，並以 CB15 的一部分執行。

**證據：**
| 檢查項 | 結果 |
|---|---|
| Git History | 只有 `d69817c`（2026-10-06）新增 8 個檔案 + `character.bundle.json`；之前的 `4bbaa19` 修過 hero aura 對齊 |
| Asset Metadata | `origin: "asteria-generated-user-defined-hero"`；`art_adjustment.all_visuals`: 「re-illustrated with **image generation**」；`source.pack: "ParallelWorldsHero_GFX"`（RPG Maker DLC 素材當作版面／動作參考）→ **AI 生成**，而且有 **DLC 授權疑慮** |
| Runtime References | 無（`src/asteria/runtime`、`platform` 中 0 處） |
| Editor References | 沒有直接引用這個目錄。`ready_character_library_widget.py`（未追蹤）透過 pack id `ready.user_hero` 使用，但這個 pack 現在指向 `assets/starter/characters/asteria_hero/`（未追蹤） |
| Starter Pack References | `starter_character_packs.py:22` 的 `ready.user_hero` → `asteria_hero` 目錄；`asteria_hero/character.bundle.json` 的 `preset_id: "ready.user_hero"`。也就是內容已經**搬到** `asteria_hero` |
| Demo References | `demos/`、`reference_data/`、`reference_projects/` 中 0 處 |
| Test Dependencies | `tests/test_character_content_packs.py:171` **斷言** `ready_user_hero` 目錄**不存在**（代表刪除是有意的搬遷）；`tests/test_starter_character_art.py:183/226` 只用暫存目錄名稱來測試「保護使用者 pack」 |
| 屬於正式 Asset Pipeline 或 Starter Pack 嗎？ | 不屬於。`ASTERIA_ASSET_SPEC.md` §33 Starter Pack 清單（Default_Hero、Villager、Slime、Goblin…）沒有它；`ASTERIA_FINAL_ALIGNMENT_AUDIT.md` 寫明正式 Starter 美術是 DEFERRED，而且「rejected/generated Starter art」不得恢復 |

**後續執行條件：** 你批准後，在 CB15 中和 `asteria_hero`（同屬 AI 生成）一起處理。如果沒有批准，維持工作樹現狀，不 commit、不還原。

---

## D4 — Boss Art Tests

**決策：** 停止 AI 美術與 boss 修圖。通用驗證（A 類）全部保留、標準不變。Boss 專屬驗收（B 類）規劃標記為 **Retired / Out of Active Scope**（Audit 階段**沒有修改**任何測試）。失敗紀錄保留在下方，不偽裝成 PASS。

**A. Generic Asset Pipeline Validation（保留，Active）**
`tests/test_asset_pipeline.py`、`test_quality_gate.py`、`test_gate.py`、`test_project_assets.py`、`tests/asset_production/test_production_protocol_contract.py`、`test_batch106_high_fidelity_animation_acceptance.py`、`test_sprite_authoring.py`、`test_rpg_maker_mv_adapter.py`／`_catalog`／`_database`／`_map`／`_map_render`／`_project`／`_reference_inventory`，以及 `test_battle_presentation_runtime.py` 中的通用影格版面／比例／aura 版面驗證。

**B. Specific Boss / Starter Art Acceptance（規劃退役，需要批准）**
| 檔案 | 測試數 | 目前結果 |
|---|---|---|
| `tests/test_asteria_boss_pack.py`（未追蹤） | 29 | **26 PASS／3 FAIL** |
| `tests/test_starter_character_art.py`（未追蹤） | 24（8 個函式，含參數化） | PASS |
| `tests/test_starter_sprite.py`（未追蹤） | 10 | PASS |
| `tests/test_character_content_packs.py`（未追蹤） | 8 | PASS |
| `tests/test_starter_character_native_pipeline.py`（未追蹤） | 1 | PASS |

**原始失敗紀錄（保留，2026-10-09 執行）：**
1. `test_asteria_boss_profile_walk_outer_frames_switch_leading_leg`：`AssertionError: ('profile walk outer frames must alternate which leg leads', 1, (447, 270), (429, 305))`；`assert ((447 - 270) * (429 - 305)) < 0`
2. `test_asteria_boss_walk_rows_keep_head_bob_small_and_consistent`：`('walk frames in each direction must keep head height stable', 2, [10, 4, 4])`；`assert (10 - 4) <= 2`
3. `test_asteria_boss_front_and_back_torso_anchors_do_not_sway_between_frames`：row 3 的 y 錨點 `44.53 → 46.11`；`assert 1.58 <= 1.0`

**Boss 是正式 SPEC 的必要資產嗎？** 不是。`ASTERIA_ASSET_SPEC.md` 只定義 boss 的尺寸級別（§5 `128×128+`、Part B §15），§33 Starter Pack 沒有 boss；`asteria_boss` 是未追蹤的 AI 美術工作（`docs/superpowers/plans/2026-10-08-high-resolution-asteria-boss-sprites.md`）。所以 B 類可以退役，不屬於 BLOCKED。
**退役方式（提案，CB15）：** 移到 `tests/retired/` 或加上 `@pytest.mark.retired_art`，並在 `pytest.ini_options` 預設排除；保留檔案與本紀錄。**不放寬** A 類的任何門檻。
**替代方案：** 正式美術改用授權明確的免費素材（CC0／CC-BY，記錄 license 和出處），並讓它們通過 A 類 gate + `ASTERIA_ART_DIRECTION.md` 的四道 gate。

---

## D5 — Instruction Documents

**決策：** 找到了。本次報告依照它們的模板重新整理，並保留所有證據類欄位。

| 文件 | 位置 | 權威性 |
|---|---|---|
| `CODEX_PROMPT.md`、`SCOPE_DECISIONS.md`、`REPORT_INDEX.md`、`README.md` | `~/Downloads/Asteria_Codex_SPEC_Audit_Handoff.zip` → `asteria_audit_package/`（2026-10-09 18:04，共 5 個 entry）。**不在 Repository 中**（repo 全文搜尋 0 處；git 歷史 0 處） | `SCOPE_DECISIONS.md` **只**覆蓋它列出的決策（取消 Character Generator；延後 ARPG／Dual-Mode／JRPG Demo；延後 C++ 和 renderer replacement）。其他功能需求以 repo 中的 canonical SPEC 為準。`CODEX_PROMPT.md`／`REPORT_INDEX.md` 定義的是流程和報告格式，不定義功能需求 |
| Canonical SPEC | `ASTERIA_SPEC.md`、`ASTERIA_ASSET_SPEC.md`、`ASTERIA_ASSET_PIPELINE.md`、`ASTERIA_ART_DIRECTION.md`、`ASTERIA_PROGRESS.md`（`audit/FIVE_DOC_CONSISTENCY_AUDIT.md` 認定） | 功能需求最高依據；PROGRESS 只記錄狀態，不覆蓋其他四份 |

**權威衝突（未解決，需要你確認）：**
- `README.md` 指向 `docs/CANONICAL_SPEC.md`（2026-09-13），但它已經被 5 份 `ASTERIA_*.md`（2026-09-17 起）取代。
- 本次 Audit 一開始找不到這些檔案，第一版報告是我推定的格式，現已依模板重整。

---

## D6 — Battle Presentation Integration

**決策：** 採用 **Incremental Integration**（CB2）。不直接取代 `runtime/playable_test_runtime.py`。

**現況證據：**
- 戰鬥規則只有一套：`rpg/battle*.py`，透過 `runtime/game_session.py` 的 `GameSessionRuntime.execute`／`enemy_turn`／`finish_victory` 使用。
- `playable_test_runtime.py` 的 `_draw_battle`、`_use_skill`、`_enemy_response` 混合了「演出」和「部分規則決策」：寫死以自己為目標的技能清單（第 503 行）、`"momentum"` boost（第 506–510 行）、`"stagger_system"`（第 515 行）、固定「玩家→全體敵人」回合順序（沒有使用 `battle_scheduler`）。`game_session.py:290` 寫死 `"vitality"`。
- `presentation/battle_screen.py` `BattleScreenRuntime`、`platform/pygame_battle_ui.py` `PygameBattleUiBackend`：`src/` 中 0 個 runtime 消費者；後者也沒有測試。

**執行原則（CB2 的 DoD 細節見 REMAINING_WORK_PLAN）：**
1. Battle Logic 只保留一套（`rpg/battle*` + `GameSessionRuntime`）。把 `playable_test_runtime` 裡的規則決策**往下搬**到 canonical battle／battle-rules 資料，不能在 presentation 新增規則。
2. 把 `_draw_battle` 包成 **Legacy Presentation Adapter**，和新的 `BattleScreenRuntime` 實作同一個介面，並用設定切換。
3. 兩者都只消費 canonical Battle Events／`BattleSnapshot`／Action Results。
4. 建立行為對照測試：同一個戰鬥腳本 → 兩個 adapter 消費同一串事件 → 斷言順序、目標、數值、結果畫面一致（視覺差異不比對）。
5. Animation／VFX／Camera／Audio／Runtime 整合各自有驗證。
6. 新路徑通過 CLOSURE_EXIT_CRITERIA 的 G-BATTLE 之後，才另外提出 Legacy 退役提案。

**受影響模組：** `runtime/playable_test_runtime.py`、`runtime/game_session.py`、`presentation/battle_screen.py`、`battle_runtime.py`、`platform/pygame_battle_ui.py`、`rpg/battle_scheduler.py`
**SPEC 依據：** `ASTERIA_SPEC.md` §5（GUI/runtime 單一 canonical model）、§17、§19、§44.4、§44.5

---

## 其他待決事項

| # | 事項 | 建議 |
|---|---|---|
| Q1 | 是否從 Codex log 重建 3 個無法還原的測試（§0） | 不重建（只服務已取消的範圍） |
| Q2 | 是否套用 P0-3 提案 patch | 在 CB0 審核後套用 |
| Q3 | 未追蹤的 MV 衍生美術（`mv_generator_prototype`、`mv_combat_prototypes`）放在可散布路徑 | 在 CB0 加 `.gitignore` 或搬到 `local_reference/`（需要批准） |

---

## D7 — 移除 `assets/` 全部內容（2026-10-09，使用者授權執行）

**決策：** 使用者決定 `assets/` 底下的內容全部不要了，並授權「先備份後處理」。這覆蓋 D3／D4 原本「等待批准」的狀態。

**已執行：**
- 備份：`/Users/roger/Documents/Vscode/Asteria_backup_2026-10-09_generated_art.zip`（repo 外，30 MB，180 個項目，`unzip -t` 通過）。內容包括整個 `assets/`（含從 git 取出的 `ready_user_hero`）、下列被移除的程式／腳本／測試／設計文件，以及修改前的 `shell.py`、`assets/__init__.py`、`test_editor_mv_character_creator.py`
- 刪除：`assets/`（目錄已不存在）；`assets/starter_character.py`、`starter_character_packs.py`、`starter_sprite.py`、`character_content_pack.py`；`editor/ready_character_library_widget.py`；`scripts/build_starter_template_art.py`、`rebuild_asteria_boss_aura.py`、`rebuild_starter_side_views.py`；測試 `test_asteria_boss_pack.py`、`test_character_content_packs.py`、`test_starter_character_art.py`、`test_starter_sprite.py`、`test_starter_character_native_pipeline.py`；starter art／boss sprites／content packs 的 6 份設計與計畫文件
- 移除相依：Editor 的「Ready Characters」分頁；`assets/__init__.py` 的 3 個 import；`shell.py` 的 content-pack `instantiate` 分支；`test_editor_mv_character_creator.py` 的 Ready Characters 測試與斷言
- Commit：只 commit 了 `ready_user_hero` 的刪除（`773d072`，branch `cleanup/remove-generated-art`，未 push）。其他變更跟你原本未提交的工作交織在一起，維持未提交
- **保留**：Character Generator 的通用合成程式、click-to-place、MV 匯入、所有通用 asset／animation／attachment／presentation 功能（D2；Generator 專屬部分的退役仍屬 CB15）

**驗證：** offscreen 全套結果是 1851 passed、1 failed（`test_mv_character_creator_e2e` 的 `cocoa` 平台斷言，原生 Qt 下通過）；原生 Qt 下 `test_mv_character_creator_e2e.py` + `test_editor_mv_character_creator.py` 12 passed；`compileall` PASS。D4 的 3 個 boss 失敗已經隨測試檔移除，原始失敗紀錄保留在 D4。

---

## D8 — CB0 執行紀錄（2026-10-09，使用者批准「開始做」）

| Commit | 內容 |
|---|---|
| `7f229f3` | MV 側視 motion 索引修正 |
| `542979e` | Generator WIP 快照（已取消，退役由 CB15 處理） |
| `aee05c3` | 點地圖格子放置角色（同時移除 Ready Characters 分頁） |
| `959c20d` | field 行走循環 0-1-2-1、保持比例 |
| `98a68e0` | Battle Presentation：aura、source pixel ratio、武器攻擊疊圖（原 WIP） |
| `c2dc576` | 套用 P0-3：MV 語意移回 `assets/`；通用 `CombatantOverlay`；`tests/test_architecture_boundaries.py`；e2e 測試的 platform 斷言改成依實際環境 |
| `779e9df` | `mv_reference` marker：39 個依賴本機 MV reference 的測試，在沒有 fixture 時改成 skip |
| `cafa337` | CI（`.github/workflows/ci.yml`）；修 F601、PLE0605 |

**驗證：** 本機 offscreen **1854 passed, 0 failed**；乾淨 clone（沒有 MV reference）**1799 passed, 55 skipped, 0 failed**。
**狀態變更：** AST-13 由 C → B（邊界已由測試強制；尚未實機重驗 W-18）。SPEC_GAP_AUDIT 中的 C-1、C-2、C-3 已處理（README、PROGRESS 已同步）；C-5（pyproject 版本）**未改**，版本號需要由你決定。
**CI：** 只有 commit，沒有 push，所以還沒在 GitHub 上跑過。

---

## D9 — CB3／CB1／CB2（第一階段）執行紀錄（2026-10-09）

| Commit | Batch | 內容 |
|---|---|---|
| `84a1d9b` | CB3 | 新增 `BattleSessionRules`（RPG DB schema v24）；`GameSessionRuntime` 依資料決定目標、boost、量表、KO、排程器回合；runtime 中沒有任何寫死的專案 ID（有測試強制）；字型快取（PERF-01） |
| `4cd1daf` | CB1 | Event VM 在遊玩中執行（前景 runner + 場景 autorun/parallel）；標準 WORLD handler；存檔 v2 保存進行中的事件；Event Editor 可以輸入 WORLD 參數 |
| `826d82c` | CB2-a～d | session 戰鬥紀錄 → Legacy／Canonical 兩個 presentation adapter；行為對照測試；預設仍是 legacy |
| `bb69837` | CB2 | Canonical UI 依 virtual resolution 縮放；陣營左右配置 |

**行為變更（已寫在 commit 中）：** 回合順序改由排程器決定；多目標技能依 `maximum_targets` 命中；boss 先說台詞，確認後才開始戰鬥。

**驗證：** 本機 offscreen **1884 passed, 0 failed**；compileall／正確性 lint PASS。實機視窗（RM）**沒有執行**，只有 SDL dummy driver 的 headless 執行與截圖檢視。

**狀態更新（SPEC_TRACEABILITY_MATRIX）：**
| ID | 之前 | 現在 | 說明 |
|---|---|---|---|
| GP-02、GP-05、BTL-01、BTL-02、BTL-03 | B | B（已在遊玩中使用，HI 驗證） | 缺 RM |
| EVT-01 | B | B（已在遊玩中執行，HI 驗證） | 缺 RM |
| EVT-02 | C | B | 有標準 handler；Editor 可以撰寫參數 |
| EVT-03 | C | C | 仍沒有 common event 和 cutscene |
| BTL-04、UI-01 | B／C | C | Canonical adapter 已接上，但實際渲染有版面缺陷（見下）；不是預設 |
| AST-13 | C | B | 邊界由測試強制 |
| RISK-02、RISK-03、PERF-01 | 開放 | 已處理 | |

**新發現：**
- **F-1（高）：** `reference_projects/complex_reference_rpg/playable_assets/` 在 `bf4a993` 被刪除（屬於引擎專用的交接整理）。`playable_test_manifest.json` 仍然引用這些圖片，所以**對 reference project 執行 Run Project 時圖片會載入失敗**。測試改用程式產生的佔位圖。要等授權明確的免費素材（或 test-only 佔位素材）補上。
- **F-2（中，CB2 後續）：** Canonical battle UI 第一次實際渲染時發現的版面缺陷：
  - HUD 面板在 6 人隊伍時和 action menu 重疊
  - 回合時間軸標籤互相重疊，而且顯示原始排程時間值
  - 預設字型缺少選單游標字元
  - 戰鬥者顯示 member id，不是顯示名稱
  這些缺陷修好之前，legacy 維持預設。
- **F-3（中）：** 互動結果（弱點倍率）只用在量表和演出，**沒有套用到實際傷害**。這是 Battle Core 呼叫方式的語意問題，沿用自原本的 playable runtime。需要你決定是否列入 Battle 規則修正。

**CB2 剩餘：** canonical 戰鬥者 sprite／動畫（需要 combatant visual profile + 素材）、VFX/音訊 cue 播放（需要 CB6）、F-2 版面修正、實機驗證，最後才是 legacy 退役提案。

---

## D10 — CB14／CB4–CB9／CB12 執行紀錄（2026-10-10）

| Commit | Batch | 內容 |
|---|---|---|
| `73e3701`、`2799978` | F-1 | Reference project 的 playable 測試素材改用授權明確的免費素材（CC0 Kenney／Ninja Adventure、CC-BY-SA 3.0 LPC）；`THIRD_PARTY_ASSETS.md`。Free Pixel Art Asset Pack 只留在本機，**不 commit** |
| `ebc5bf3` | CB2（F-2） | Canonical battle UI 版面修正（面板重疊、時間軸標籤、游標字元、顯示名稱） |
| `90145ab` | CB14 | 不依賴 Generator 的 actor link、actor appearance、asset 縮圖；Inspector 下拉選單；shell 放置角色命令 |
| `ca3a454`、`ded74c3`、`7e1bc6d`、`0026683` | CB4 | Input action map（鍵盤／gamepad／rebinding，Project v10）；fixed-step；具體 System；Transform 父子關係；場景轉場 + persistent entity |
| `b8fb5f8` | CB5 | Collider、layers/masks、spatial hash、trigger；1000 colliders → 948 候選對、3.7 ms |
| `cd28b63` | CB6 | `AudioMixer`（music／ambient／sfx 匯流排、淡入淡出）+ pygame.mixer 後端；6 個 CC0 音效 |
| `8c98ae9` | CB7 | Prefab、variant、override、傳播；Editor 命令 |
| `e2ab55a` | CB8 | Animation state machine、frame events |
| `08f519d` | CB9 | 依 D1 從 `16a6ebd` 復原 ModernGL 後端；pygame 仍是預設 |
| `2d11c9d`、`ac51b3a` | CB12 | Component 遷移鏈、`asteria-upgrade`、`asteria-export` |

**流程失誤（已修正）：** `2d11c9d` 在全套測試有 1 個失敗（`test_runtime_preview` 的 stub 沒有接受新的 `max_frames` 參數）時被 push。`ac51b3a` 已修正。之後 commit 前一律先確認全綠。

**驗證：** 本機 offscreen **1954 passed, 0 failed**；正確性 lint PASS。ModernGL 只有 offscreen GPU context 和像素對照。**沒有實機視窗驗證**（gamepad、音訊延遲、GPU 視窗都是 EXTERNAL）。

**狀態更新：** SPEC_TRACEABILITY_MATRIX 已同步 D9 和 D10 的狀態。合計從 A17／B20／C44／D16 變成 **A17／B38／C33／D9**。A 沒有增加，因為 A 需要 RM。

**仍未解決：** F-3（互動倍率沒有套用到實際傷害），需要你決定是否列入 Battle 規則修正。ENG-02 沒有 CharacterController component。AST-08 缺 Projectile 和 UI asset 類別。

---

## D11 — CB11 遊戲系統執行紀錄（2026-10-10）

| Commit | 需求 | 內容 |
|---|---|---|
| `78b1681` | RPG-05、WLD-01 | 商店（多貨幣買賣、限量庫存）和任務（counter／item／defeat_enemy／switch 目標、前置、獎勵、串聯）；RPG DB v25、存檔 v6；`OPEN_SHOP`、`*_QUEST` WORLD 命令 |
| `6393983` | RPG-04 | 條件掉落（`required_switch`）和幸運加成（`luck_bonus`，`loot.luck` 事件變數） |
| `47e1f00` | RPG-02 | 裝備套裝加成（依件數的 modifier／tag／能力） |
| `eb65c31` | RPG-06 | 製作：工作台、成功率、失敗產出、品質等級、經驗 |
| `6baf488` | RPG-09、RPG-10 | Field AI（idle／patrol／wander／chase／flee）、spawn zone（respawn、waves、稀有、條件）、可見遭遇 |
| `fd276b2` | UI-02 | Pause／任務日誌／商店／存讀檔／game over 畫面（依 input action map，可用手把） |
| `c8f583a` | WLD-02、RPG-08 | 陣營聲望、關係、計數、成就、圖鑑；敵人捕捉加入 roster；存檔 v7 |

**行為變更：** 遊玩中按 Esc 改為開啟 Pause 選單（原本直接結束程式）；戰敗會進入 Game Over 畫面（原本卡在戰鬥畫面）。

**驗證：** 本機 offscreen **1975 passed, 0 failed**；正確性 lint PASS。新畫面用按鍵事件驅動測試，並檢視 headless 截圖（發現並修正預設字型缺字：▶ ∞ 箭頭 ✓，包含原有 build 選單）。**沒有實機視窗驗證。**

**狀態更新：** RPG-02、04、05、10、WLD-01、02、UI-02 → B；RPG-06、08、09 → C。合計 **A17／B45／C29／D6**。

**仍未完成（誠實列出）：**
- 商店、任務、陣營、成就、套裝、捕捉規則都**沒有 Editor 編輯 UI**，目前只能用程式或 JSON 撰寫（屬 CB10 範圍）。
- Field AI 和 spawn system 尚未在 playable runtime 的場景中執行（只有 Scene systems 與 session 測試）。
- 捕捉沒有接進 playable 戰鬥 UI；沒有配方發現；沒有設定畫面、成就／圖鑑畫面。
- Reference project 沒有加入示範商店或任務資料（避免擴大成 JRPG Demo）。

---

## D12 — Closure Decisions（2026-10-10，使用者正式決策）

| # | 決策 | 內容 |
|---|---|---|
| 1 | **F-3：APPROVED — MUST FIX** | 屬性倍率接入實際傷害。使用既有 canonical damage pipeline、不建第二套計算器、倍率由專案資料定義、不寫死範例倍率；涵蓋普通攻擊、技能和其他適用的傷害來源；Battle Preview 與 Runtime 一致；補齊 UT／整合／回歸測試；不改 SPEC 未要求的其他規則。納入 Battle Rules Correction Batch（CB-BR1）。 |
| 2 | **CB10 Editor Completion：APPROVED（既有 SPEC closure）** | 依序：Shop、Quest、Faction、Achievement、Equipment Set、Capture Rules Editor。GUI 與 Python API 用同一個 canonical data model；只有 JSON 編輯器不算完成。 |
| 3 | **Runtime Integration** | Field Enemy AI、Spawn Zones、Battle Capture Menu、Recipe Discovery、Game Settings Screen、Achievement Screen、Bestiary Screen。必須實際 runtime 整合，不能只靠單元測試。 |
| 4 | **Reference Project** | 維持最小化測試用途；不加完整範例商店、任務劇情或 JRPG Demo 內容；允許必要的最小測試 fixture。 |
| 5 | **CB15：NOT APPROVED YET** | 不得刪除未逐項審核的功能。先提交 `CB15_RETIREMENT_REVIEW.md`（Feature、Source Paths、Original Purpose、Dependencies、SPEC Requirement、Replacement、Removal Impact、Recommendation、Migration／Rollback），等明確批准。 |
| 6 | **Closure Policy** | Canonical SPEC First；No Scope Expansion；No Character Generator；No ARPG Engine；No Dual-Mode Demo；No C++ Migration Yet；No JRPG Demo Until SPEC Closure；No Premature Feature Retirement；No False Completion Claims。 |

**每批回報格式：** Changed Files／Requirement Coverage／Tests Executed／Integration Evidence／Remaining Gaps／Closure Status。

### CB-BR1（F-3）執行紀錄

- **方法：** `apply_effect` 和 `AbilityRuntime.execute` 新增可選的 `value_transform`。`BattleRuntime.execute` 用它把**對選定目標的負向 RESOURCE_DELTA（傷害）**送進既有的 `InteractionResolver.resolve_value`（以技能 tags 為 action tags）。NULLIFY → 0、ABSORB → 回復、REFLECT → 傷害轉給行動者。正向 delta（回復）、SELF 效果、成本不受影響。沒有任何 InteractionRule 時行為與修正前完全相同。
- **涵蓋路徑：** 所有戰鬥傷害都經過 `BattleRuntime.execute`：玩家指令、`GameSessionRuntime.execute`、`submit_action`／延遲施放、`execute_with_reactions`（反擊、追擊）、敵人 AI（`execute_decision` → `execute_with_reactions`）、action sequence（多段）。
- **不在範圍：** 狀態持續傷害（DOT，`StateRuntime` 週期效果）不經過技能管線，仍不套用屬性倍率；SPEC 是否要求需要你確認。
- **Preview：** `BattleRuntime.preview_action`／`GameSessionRuntime.preview` 在複製的 subject 上執行同一條管線，不修改戰鬥。測試逐項比對 Preview 與實際結果。
- **行為變更（回歸）：** `test_multihit_sequence_uses_same_canonical_ability_twice` 原本斷言 2 段火焰攻擊對火弱點敵人造成 40，這是缺陷行為；修正後為 60（2 × 20 × 1.5）。Reference project 的 Boss 對 fire／ice／lightning 弱點，屬性技能現在實際造成 1.5 倍傷害。

---

## D13 — D12 執行回報（2026-10-10）

依 D12 要求的格式回報。驗證層級沿用 SPEC_TRACEABILITY_MATRIX：UT＝單元、HI＝headless 整合（實際驅動 `PlayableTestRuntime._frame` 與按鍵事件、或實際建立 `AsteriaEditorWindow`）、RM＝實機視窗。**本輪全部沒有 RM。**

### Batch CB-BR1 — F-3 屬性倍率（`2f14a7e`）
| 項目 | 內容 |
|---|---|
| Changed Files | `gameplay/effects.py`、`gameplay/abilities.py`、`rpg/battle.py`、`runtime/game_session.py`、`tests/test_battle_interaction_damage.py`（新）、`tests/test_playable_battle_status_resources_interactions.py`、audit 文件 |
| Requirement Coverage | BTL-02（F-3）：普通攻擊、技能、反擊、敵人 AI、多段；NULLIFY／ABSORB／REFLECT；倍率只來自 InteractionRule 資料 |
| Tests Executed | 新增 9 個（參數化 5 種倍率／disposition，資料驅動倍率，回復不受影響，反擊路徑，reference session 技能 vs 普攻）；全套 1984 passed |
| Integration Evidence | Reference session：`fire_arc` 對 fire 弱點 Boss 命中 `weak_fire` 規則，Preview（`GameSessionRuntime.preview`）與實際扣血逐項一致；`strike` 不匹配規則 |
| Remaining Gaps | DOT（狀態週期效果）不經過技能管線，不套用倍率（待你確認 SPEC 是否要求）；沒有 RM |
| Closure Status | BTL-02 維持 **B**（缺 RM） |

### CB15 審核文件（`abc04b6`）
`docs/audits/CB15_RETIREMENT_REVIEW.md`：A1–A8 逐項（7 項建議 RETIRE、`CreateCharacterCommand` 建議 KEEP），Part B 記錄 D7 已移除項目，Part C 列出明確不退役的項目。**沒有刪除任何東西，等待逐項批准。**

### Batch CB10h — Game Systems Editors（`5ba6470`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/game_systems_authoring.py`（新，Python API + FORMS 規格）、`editor/game_systems_widget.py`（新，Qt 表單）、`editor/shell.py`（RPG 工作區「Game Systems」分頁）、`tests/test_game_systems_editors.py`（新）、`tests/test_editor_mv_character_creator.py`（分頁清單加一項） |
| Requirement Coverage | Shop、Quest、Faction、Achievement、Equipment Set、Capture Rules Editor；GUI 與 API 共用 `GameSystemsAuthoringController` 與 canonical `*Definition`；undo／redo；整個 RPG DB 驗證；被引用時禁止刪除並顯示 Used by |
| Tests Executed | 7 個（API CRUD + undo、六類 New 範本、驗證與引用保護、在真實 `AsteriaEditorWindow` 中操作 Shop／Quest／Faction／Achievement／Set／Capture 表單、六類無變更 Apply round-trip）；全套 1991 passed |
| Integration Evidence | 測試直接操作表單元件（新增 stock 列、objective、loot、set bonus 的巢狀 modifier、勾選參照清單）後 Apply，再讀回 RPG DB；驗證錯誤顯示在 UI 狀態列；offscreen 截圖檢視版面 |
| Remaining Gaps | 不是 JSON 文字框，但也沒有拖放排序；quest objective 的 target 是文字欄位（由 canonical 驗證把關），沒有依 kind 切換的下拉選單；沒有 RM |
| Closure Status | 對照表沒有獨立的列；補上 RPG-02／05／08、WLD-01／02 列在 D11 記錄的「沒有 Editor UI」缺口。這些列維持 **B**（缺 RM） |

### Batch 11-RI — Runtime Integration（`e6d3274`、`d12111b`、`2025f6f`）
| 項目 | 內容 |
|---|---|
| Changed Files | `runtime/field_ai.py`、`runtime/game_session.py`、`runtime/playable_test_runtime.py`、`runtime/game_menus.py`、`runtime/world_command_handlers.py`、`rpg/composition.py`、`rpg/world_record.py`、`rpg/save_state.py`；測試 `test_runtime_field_enemies.py`（新）、`test_runtime_menus_d12.py`（新）、`test_game_menus.py` |
| Requirement Coverage | Field Enemy AI、Spawn Zones（`GameSessionRuntime.field_update`，每個 field frame 執行，選單開啟時暫停）；Battle Capture Menu（X 鍵，顯示成功率與消耗道具，消耗回合）；Recipe Discovery（`requires_discovery`、`LEARN_RECIPE`、以正確材料製作即發現、`OPEN_CRAFTING`、製作畫面）；Game Settings（音樂／音效音量套用到 AudioMixer、戰鬥訊息開關，存 `saves/settings.json`）；Achievement Screen；Bestiary Screen |
| Tests Executed | Runtime 整合 9 個 + 更新 1 個；全套 **1998 passed**；lint PASS |
| Integration Evidence | 全部透過 `PlayableTestRuntime._frame` 與 pygame 按鍵事件驅動：生怪 → 畫面上可見（像素檢查）→ 追擊玩家 → 觸碰開戰並移除；選單中凍結、移除後依 respawn 時間重生；X → 捕捉選單 → Esc 取消 → 削弱後按 1 捕捉成功、角色加入 roster、圖鑑 captured+1；事件開啟製作台 → Enter 製作 → 物品增加；暫停選單進入成就／圖鑑／設定；設定調整後混音器音量改變並寫檔。新畫面都有 headless 截圖檢視 |
| Remaining Gaps | 捕捉與 field 敵人只在 legacy battle HUD 標示操作說明（canonical adapter 畫面沒有加控制提示）；playable runtime 的 field 敵人沒有專屬 sprite（以標記圓形顯示，未在 manifest 對應名稱時）；設定沒有按鍵重設 UI；沒有 RM |
| Closure Status | RPG-08、RPG-09 由 C → **B**；RPG-06 由 C → **B**；RPG-10、UI-02、WLD-02 維持 **B**（新增 runtime 證據，仍缺 RM） |

**整體 Closure Status：** 沒有任何項目因為這輪而成為 A；**Engine 尚未完成**。A 仍需實機視窗驗證（W-* 系列）與 D12 未涵蓋的 CB10 其他子項（10a–10g）、CB13（golden suite、profiler）、CB2 剩餘、CB15（待批准）。

---

## D14 — Remaining Closure Decisions（2026-10-10，使用者正式決策）

| # | 決策 |
|---|---|
| 1 | **CB2 Battle Presentation 必須完成 runtime 整合：** 角色 sprite、動畫播放、戰鬥 VFX、camera 協調、音訊同步、捕捉指令提示、戰鬥狀態與演出同步。新版必須實際顯示角色動畫與技能特效；不能只靠資料事件／mock／headless 宣稱完成。保留既有 Battle Logic，不建立第二套規則。舊 pygame presentation 在新版實機驗證前不得刪除。 |
| 2 | **CB10 Editor Completion：** Animation Editor、Action Timeline Editor、Debugger、Script Editor 和其他未完成的 CB10 項目。GUI 與 Python API 共用 canonical data model；Save／Load／Undo／Redo；Preview 與 Runtime 整合；Script Editor 必須能實際編輯、儲存、執行；Debugger 具備 SPEC 要求的能力；不做 placeholder；遵守 Editor 設計要求（專業、清楚、漸進揭露）。 |
| 3 | **CB13 Validation Infrastructure：** Golden Test Suite（可重現資料、明確 baseline 更新規則）、Performance Profiler（Frame Time、Update、Rendering、Animation、VFX、Asset Loading；無法提供的指標標 Unsupported，不偽造）、Regression Validation、Runtime Benchmark、Presentation Timing Validation。 |
| 4 | **Real-Machine Validation：** GPU window、Input／Controller、Audio Playback、Audio Latency、Animation Smoothness、Frame Pacing、Editor → Runtime Playtest、Runtime Exit／Recovery。狀態只能是 PASS／FAIL／BLOCKED／NOT EXECUTED；無法執行的不得標 PASS；無法使用的裝置要提供 macOS 驗證程序並保留 NOT EXECUTED。 |
| 5 | **DoT：** 預設不套用屬性倍率；技能或狀態可以透過 canonical Battle Rules 明確啟用；不重複套用初始攻擊倍率；不建第二套計算器；使用既有 damage pipeline；向後相容；補齊測試；若 SPEC 有不同規定先提出衝突。 |
| 6 | **CB15：** 不批准整批退役；逐項清單欄位：Module／Feature、Source Paths、Current Dependencies、Original SPEC Requirement、Replacement Availability、Regression Risk、Proposed Action、Rollback Plan。新版完全整合並通過實機驗證前保留舊 Runtime／Presentation。 |
| 7 | **每批回報：** Changed Files、Requirement IDs、Test Results、Integration Evidence、Real-Machine Validation Evidence、Remaining Gaps、Updated Traceability Matrix。禁止事項同 D12 #6，並禁止未驗證就宣稱 Engine 完成。 |

### Batch D14-5 — DoT（`6224d8e`）
| 項目 | 內容 |
|---|---|
| Changed Files | `gameplay/states.py`（`StateRuntime.advance(value_transform=)`）、`rpg/battle_states.py`（`BattleStatePolicy.interaction_tags`、`periodic_transform`）、`rpg/battle.py`（`_periodic_interaction_transform`、`periodic_interactions`）、`tests/test_battle_interaction_damage.py` |
| Requirement IDs | BTL-02、S§16（Damage-over-time、Periodic effects） |
| Test Results | 新增 4 個（預設不套用、opt-in 只解析一次且不匹配時不變、攻擊倍率不重複套用到 DoT（×1.5 而非 ×2.25）、序列化向後相容）；全套 2002 passed |
| Integration Evidence | 使用既有 `PlayableBattleMechanicsHarness`（flame_fragility ×1.5、scorch）透過 `BattleStateRuntime.apply_trigger` 的實際 tick 路徑 |
| Real-Machine Validation Evidence | 不適用（純規則；無畫面） |
| SPEC 衝突檢查 | `ASTERIA_SPEC.md` §16 只列出 Damage-over-time／Periodic effects，沒有倍率規則 → 無衝突 |
| Remaining Gaps | 狀態的 opt-in 在 Battle Rules Editor 目前只能經由通用樹狀編輯器設定 |
| Updated Traceability Matrix | BTL-02 維持 B（缺 RM） |

### CB15 審核文件（D14 #6 格式更新）
欄位改為 D14 #6 指定的 8 欄；新增 A9（Legacy battle presentation）與 A10（playable runtime host），兩者 Proposed Action 皆為 **KEEP**。仍然沒有刪除任何東西。

---

## D15 — D14 執行回報（2026-10-10）

依 D14 #7 格式。驗證層級：UT＝單元、HI＝headless 整合（實際驅動 runtime／editor）、RM＝實機視窗（`docs/audits/REAL_MACHINE_VALIDATION.md`）。

### Batch CB13-a — Runtime Profiler（`47cf5bb`）
| 項目 | 內容 |
|---|---|
| Changed Files | `runtime/profiler.py`（新）、`runtime/playable_test_runtime.py`（分段計時）、`runtime/game_session.py`（ai／spawn／collision 分段）、`runtime/preview.py`（`--profile`、`--fps`）、`tests/test_runtime_profiler.py`（新） |
| Requirement IDs | EDT-19（S§34 Profiling）、D14 #3 |
| Test Results | 3 個新測試；全套 2005 passed |
| Integration Evidence | Playable runtime `run(profile_path=)` 寫出 frame／pacing／sections／counters／memory；無法量測的 `draw_calls`、`gpu_time` 標 Unsupported，未記錄的 SPEC 指標列在 `not_recorded`，不偽造 |
| Real-Machine Validation Evidence | 實機 Cocoa 視窗 profile（`evidence/real_machine/battle_profile.json`） |
| Remaining Gaps | 沒有 Editor 內的 profiler 面板；draw calls 只在 ModernGL 後端可量測 |
| Updated Traceability Matrix | EDT-19 C → **B** |

### Batch CB2 — Canonical Battle Presentation（`60c2c6d`、`6439abd`、`dfd0a27`）
| 項目 | 內容 |
|---|---|
| Changed Files | `runtime/battle_visuals.py`（新）、`runtime/battle_presentation_adapters.py`、`platform/pygame_battle_ui.py`、`presentation/battle.py`（`reemit`）、`presentation/battle_ui.py`（staging 選項）、`presentation/battle_hud.py`（HUD 顯示 HP／SP）、`presentation/battle_screen.py`、`runtime/playable_test_runtime.py`、`runtime/preview.py`（`--battle-presentation`）、`scripts/build_reference_battle_presentation.py`（新）、reference project 資料與 `playable_assets/battle/`（CC0）、`CREDITS.md`、`THIRD_PARTY_ASSETS.md`；測試 `test_canonical_battle_presentation.py`（新，10 個）及既有測試更新 |
| Requirement IDs | BTL-04、VFX-01、CAM-01、UI-01（戰鬥部分）、RPG-08（捕捉提示）、D14 #1 |
| Test Results | 全套 **2012 passed**；lint PASS |
| Integration Evidence | 角色 sprite 動畫（idle 實際換影格）；技能 motion sequence 依序：揮擊 → VFX → 命中（受擊姿勢、傷害數字、音效、camera shake 同一拍）；KO 姿勢等致命一擊後才出現（由 `BattleRuntime.is_active` 同步）；指令只在英雄等待輸入時出現且不遮擋隊伍；捕捉出現在指令選單；缺 visual profile 時明確 fallback。沒有新增任何戰鬥規則 |
| Real-Machine Validation Evidence | 實機 Cocoa 視窗：animation_smoothness PASS（boss 動畫 88 格／10 s）、frame_pacing PASS（58.9 fps、jitter 1.2 ms、p99 18.0 ms），截圖 `evidence/real_machine/battle_window_0.png` |
| 實機發現並修正 | (1) 舊 `_play_fx` 每個技能阻塞約 430 ms（第一次實機量測 43.7 fps、p99 441 ms → FAIL）；(2) canonical 下同一命中音效播兩次；(3) 勝利音樂在最後一擊音效前播放。三者都已修正並有回歸測試 |
| 使用者 demo 回饋（同日） | 角色右、怪物左（預設）；角色與怪物站在地面、不擋背景；怪物 HP 顯示在頭上；指令只在輪到角色時顯示（八方旅人式）。以 `BattleUiLayoutProfile` 的 opt-in 欄位（`party_hud`、`overhead_zones`、`action_menu_placement`、`stage_top`）實作，預設值維持原行為；reference project 採用 |
| Remaining Gaps | 可聽音訊、實體按鍵、手把、主觀流暢度需要人工（M1–M5）；hit-stop 未接進 canonical；時間軸列右端與最上方隊伍格在舊欄式版面仍會重疊（新版 bottom row 不受影響）；legacy 畫面的阻塞式特效仍存在（D14 #6 保留，不修改） |
| Updated Traceability Matrix | BTL-04 C → **B**；VFX-01、CAM-01、ENG-12、ENG-18 補上 RM 證據，維持 **B** |

### Batch D14-4 — Real-Machine Validation（`6439abd`、`dfd0a27`）
| 項目 | 結果 |
|---|---|
| GPU window | PASS |
| Input：OS 事件佇列（合成按鍵） | PASS |
| Input：實體鍵盤 | NOT EXECUTED（M1） |
| Controller | BLOCKED（未連接手把；M2） |
| Audio playback（裝置） | PASS |
| Audio playback（可聽） | NOT EXECUTED（M3） |
| Audio latency | NOT EXECUTED（M4，不提供假數字） |
| Animation smoothness | PASS（量測）；主觀 NOT EXECUTED（M5） |
| Frame pacing | PASS |
| Editor → Runtime playtest | PASS |
| Runtime exit／recovery | PASS／PASS |

### 仍未開始（D14 範圍內）
- **CB13：** Golden Test Suite（AS§34 的 11 類 golden asset）、Regression Validation 基準、Presentation Timing Validation 的獨立套件（目前由 CB2 測試涵蓋時序）。
- **CB10：** Animation Editor、Action Timeline Editor、Debugger、Script Editor 與其他 CB10 項目。

**整體 Closure Status：** A17／B50／C24／D6。沒有任何項目升為 A：A 需要 M1–M5 的人工實機項目。**Engine 尚未完成。**

## D16 — CB13 與 CB10 執行回報（2026-10-11）

依 D14 #7 格式。驗證層級同 D15；本輪新增兩項實機檢查：`field_camera_boss_focus` 與 `editor_tools_gui`。`editor_tools_gui` 在 Cocoa 實機視窗操作每一個新工具並量測結果，截圖都由工程師檢視過，見 `REAL_MACHINE_VALIDATION.md` #9、#10。

### Batch CB13 — Golden／Regression／Timing／Benchmark／Auto-fix／Resource lifetime（`c521f96`）
| 項目 | 內容 |
|---|---|
| Changed Files | `validation/golden.py`、`regression.py`、`presentation_timing.py`、`benchmark.py`（新）；`assets/sprite_kinds.py`、`asset_package.py`、`autofix.py`（新）；`scripts/build_golden_assets.py`、`update_golden_baselines.py`、`runtime_benchmark.py`（新）；`tests/golden/`（11 個 golden asset、baseline、README）；`runtime/playable_test_runtime.py`（戰鬥範圍資源釋放）；`runtime/game_session.py`（碰撞世界每幀只建一次） |
| Requirement IDs | AST-09、AST-11、AST-08（Projectile、UI asset 類別）、ENG-10、D14 #3 |
| Test Results | golden 11 個 asset × 8 項檢查，含負向測試；regression 與 timing baseline；auto-fix 測試；當時全套通過 |
| Integration Evidence | baseline 只能由 `update_golden_baselines.py` 更新，任一檢查失敗時拒絕寫入，規則寫在 README。本輪 baseline 確實攔下一次資料變更：boss AI 條件修正改變了 `rpg_database` hash，已依規則更新，並在 commit 說明原因 |
| Real-Machine Validation Evidence | 實機 benchmark：field 58.2 fps、battle 59.1 fps（`evidence/real_machine/benchmark_real_window.json`）；benchmark 找到碰撞 O(n²)（30 ms／幀 → 5.7 ms）並已修正 |
| Remaining Gaps | 沒有實機的記憶體回收量測（ENG-10） |
| Updated Traceability Matrix | AST-09 D → **A**（每次 commit 都執行的測試基礎設施）；AST-11 C → **B**；AST-08 C → **B**；ENG-10 維持 **B** |

### Batch CB10-a／b — Animation Editor、Action Timeline Editor（`481b635`、`ce87b69`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/animation_authoring.py`、`animation_editor_widget.py`、`action_timeline_authoring.py`、`action_timeline_widget.py`、`shell.py`；測試 2 檔 |
| Requirement IDs | EDT-05、EDT-06、ANI-04、AST-02 |
| Test Results | API 與 GUI 測試；全套通過 |
| Integration Evidence | 編輯的是 runtime 戰鬥直接讀取的 sprite_sheet 中繼資料與 motion_sequences。預覽使用 runtime `AnimatorState`。所有修改都可 undo |
| Real-Machine Validation Evidence | `editor_tools_gui`：animation_editor=ok、action_timeline=ok，截圖已檢視 |
| Remaining Gaps | pivot 修改沒有在實機執行（AST-02） |
| Updated Traceability Matrix | EDT-05 C → **A**；EDT-06 D → **A**；ANI-04 C → **A**；AST-02 C → **B** |

### Batch CB10-c／f — Debugger、Play-test（`9d383b1`）
| 項目 | 內容 |
|---|---|
| Changed Files | `runtime/debugger.py`、`debug_server.py`（新，只聽 loopback、需要 token）、`editor/debugger_widget.py`（新）、`runtime_launcher.py`、`shell.py`、`playable_test_runtime.py`、`preview.py`；`tests/test_runtime_debugger.py` |
| Requirement IDs | EDT-10、EDT-11 |
| Test Results | 8 個測試，包含另一個 process 的 spawn 與 debug 通道 |
| Integration Evidence | 可檢視 stats／resources／位置／states／abilities／animation／AI／quest／world／switch／inventory。debug actions 都走 session 的正式 API，不另加規則 |
| Real-Machine Validation Evidence | `editor_tools_gui`：debugger_live_game=ok，附加到另外啟動的遊戲 process，give_item 成功（截圖 `editor_debugger.png`） |
| Remaining Gaps | Play from Selection 與 Restart Play 沒有在實機視窗執行 |
| Updated Traceability Matrix | EDT-10 D → **A**；EDT-11 C → **B** |

### Batch CB10 EDT-09 — Script Editor（`1d116a8`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/script_tools.py`（新）、`code_workspace.py`、`shell.py`、`authoring/runner.py`（`script_namespace`）、`authoring/api.py`（回傳型別標註）；`tests/test_script_editor.py` |
| Requirement IDs | EDT-09 |
| Test Results | 6 個測試 |
| Integration Evidence | 語法高亮；Authoring API 自動完成，可跟隨腳本內的賦值與呼叫鏈的回傳標註，只做靜態解析、不執行任何程式碼；traceback 列出腳本內的 frame，點選即跳到該行；腳本檔新增／開啟／reload；執行結果整體是一個 undo 步驟 |
| Real-Machine Validation Evidence | `editor_tools_gui`：script_completion=ok（補全 popup 是獨立視窗，截圖抓不到，以量測為準） |
| Remaining Gaps | — |
| Updated Traceability Matrix | EDT-09 C → **A** |

### Batch CB10 EDT-03／13／14 — 紀錄剪下／複製／貼上、多選、篩選、右鍵選單、批次編輯（`d21d0be`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/record_operations.py`（新）、`model.py`（`EditorDocument.group`）、`clipboard.py`、`integrated_authoring.py`（每個分類都有 `create`）、`authoring_hub_widget.py`、`shell.py`；測試 2 檔 |
| Requirement IDs | EDT-03、EDT-13、EDT-14 |
| Test Results | 9 個測試，含 Cocoa 以外的焦點分派測試 |
| Integration Evidence | 所有操作都走 controller 的 create／edit／delete，驗證照常套用，且整批是一個 undo 步驟。被參照的紀錄無法剪下，已刪的部分會一併回復。id 與 schema／version 不能批次編輯 |
| Real-Machine Validation Evidence | `editor_tools_gui`：multi_select_batch_fields=ok。審查截圖時發現欄位名稱被截斷，已修正（`e715774`） |
| Remaining Gaps | 紀錄沒有拖放與排序（EDT-14 仍是 C）；批次套用與剪貼簿沒有在實機執行 |
| Updated Traceability Matrix | EDT-13 C → **B**；EDT-14 維持 **C**；EDT-03 維持 **B** |

### Batch CB10 EDT-15 — Problems 面板（`7c1d6e4`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/problems.py`、`problems_widget.py`（新）、`shell.py`、`rpg/actors.py`（`reference_errors`）、`project.py`（`ability_reference_errors`）；`tests/test_problems_panel.py` |
| Requirement IDs | EDT-15 |
| Test Results | 6 個測試 |
| Integration Evidence | 一次列出所有問題（`Project.validate` 只回報第一個），每個問題都可以跳到對應的紀錄、場景實體、sprite、時間軸、遊戲系統或腳本行 |
| Real-Machine Validation Evidence | `editor_tools_gui`：problems_panel=ok（含跳轉）。審查截圖時發現同一錯誤重複顯示，已修正（`b01eb17`） |
| Remaining Gaps | 底部 dock 升起 Debugger／Problems 時，內部會多畫出一條「Assets／Console」分頁列，看起來是 Qt 的 dock 繪製問題，需要人工確認 |
| Updated Traceability Matrix | EDT-15 C → **A** |

### Batch CB10 EDT-07 — Enemy AI／Boss Phase 編輯器（`3fa4b43`、`b01eb17`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/enemy_ai_authoring.py`、`enemy_ai_widget.py`（新）、`rpg/enemy_ai.py`（`explain`、內建 `resource` 條件、詞彙常數）、`shell.py`、reference project boss AI 資料、`tests/golden/baselines/regression.json`；`tests/test_enemy_ai_editor.py` |
| Requirement IDs | EDT-07 |
| Test Results | 8 個測試，包含真實戰鬥中的回歸測試 |
| Integration Evidence | 預覽使用 `EnemyAIRuntime.explain`，`decide()` 也共用這段邏輯，所以預覽結果與戰鬥實際選擇一致。**發現並修正一個既有缺陷：** reference boss 的 nova 規則使用未註冊的條件 `resource_at_least`，boss 血量降到 30% 以下（phase 3）時 `enemy_turn` 會丟出 KeyError。已改用內建的 `resource` 條件（rage 等戰鬥資源從戰鬥層讀取） |
| Real-Machine Validation Evidence | `editor_tools_gui`：enemy_ai_preview=ok（phase_3、nova 100%）。審查截圖時發現規則表只露出約一列，已修正 |
| Remaining Gaps | — |
| Updated Traceability Matrix | EDT-07 C → **A** |

### Batch CB10 EDT-08 — VFX 工具（`f5511cb`）
| 項目 | 內容 |
|---|---|
| Changed Files | `editor/vfx_authoring.py`、`vfx_widget.py`（新）、`runtime/battle_visuals.py`（`vfx_placement`、`vfx_rect`、`vfx_keyframe`）、`battle_presentation_adapters.py`（讀取 placement、additive blend）、`shell.py`；`tests/test_vfx_tool.py` |
| Requirement IDs | EDT-08（VFX-01 的 runtime 端） |
| Test Results | 8 個測試，其中一個在真實 canonical 戰鬥中驗證火焰 VFX 依編輯的 scale、opacity、blend 繪製 |
| Integration Evidence | 預設值重現原本的畫面（身體中央、0.6 倍），既有戰鬥畫面不變。匯入時先驗證 frame grid，再把圖片複製進專案 |
| Real-Machine Validation Evidence | `editor_tools_gui`：vfx_tool=ok、vfx_preview=ok；實機戰鬥的 frame pacing 仍 PASS |
| Remaining Gaps | — |
| Updated Traceability Matrix | EDT-08 C → **A** |

### Batch CAM-02 — Camera（`7901fa1`、`e6f0092`）
| 項目 | 內容 |
|---|---|
| Changed Files | `runtime/camera.py`、`systems.py`、`camera_factory.py`、`player_slice.py`、`reference_runtime.py`、`components2d.py`（Camera2D v2 與 migration）、`field_camera.py`（新）、`world_command_handlers.py`、`playable_test_runtime.py`；reference boss 事件；`tests/test_camera_cam02.py` |
| Requirement IDs | CAM-02 |
| Test Results | 10 個測試 |
| Integration Evidence | 新增：look-ahead、bounds、target group、shot director（eased transition、跟隨移動中的實體）、shake。事件指令 `CAMERA_FOCUS`／`CAMERA_RELEASE`／`CAMERA_SHAKE` 在 event editor 可編輯。Playable field 預設是恆等視角（畫面與之前完全相同），也不會露出地圖邊緣。reference boss 說話時鏡頭推近，開戰時切回 |
| Real-Machine Validation Evidence | `field_camera_boss_focus` PASS：zoom 1.60、地圖覆蓋整個畫面、boss 移到畫面中央；前後截圖已檢視 |
| Remaining Gaps | look-ahead 與 target group 只有 UT／HI；playable field 是單畫面地圖，沒有跟隨鏡頭；沒有戰鬥開場的 boss 鏡頭 |
| Updated Traceability Matrix | CAM-02 C → **B** |

### Real-Machine Validation（D16 重跑）
| 項目 | 結果 |
|---|---|
| GPU、Input 事件佇列、Audio 裝置、Animation、Frame pacing（58.9 fps）、Editor playtest、Exit、Recovery | PASS |
| Boss camera（新） | PASS |
| Editor tools GUI（新） | PASS |
| Controller | BLOCKED（未連接手把） |
| 實體鍵盤、可聽音訊、音訊延遲 | NOT EXECUTED（M1、M3、M4） |

**整體 Closure Status：** A17／B50／C24／D6 → **A26／B56／C12／D3**（97 項 active）。仍為 D：ENG-17（hitbox／hurtbox、地面偵測）、EDT-17、EDT-18（後兩項是 Eventual）。新的 A 都依 EDT-01 同樣的標準：實機視窗執行、量測、截圖已檢視。這不等於「有人實際上手使用過」，那仍是人工項目（M1–M5）。**Engine 尚未完成。** CB15 仍在等待使用者逐項批准，沒有刪除任何東西。

## D17 — Final Remaining SPEC Closure Decisions（2026-10-11，使用者正式決策）

1. **Traceability Reconciliation 先做：** 依實際程式碼、測試、整合證據更新過期註記（至少 RPG-07、UI-01、AST-05、RPG-10、UI-02）；不得只因程式碼存在就把 B 升為 A。
2. **Immediate Functional Closure：** EVT-03、EVT-04（必須是平行演出，不是依序阻塞）、ENG-02、EDT-14。
3. **Remaining Functional Gaps：** ENG-15 按鍵重設 UI、ENG-21 存檔欄位 UI、ANI-02 圖形化動畫狀態機編輯器、CMP-01／02／04 分層角色／attachment runtime、RPG-04 權重／保底掉落表、RPG-09 behavior tree runtime、WLD-02 NPC 狀態模型、CAM-02 跟隨鏡頭／boss 開場鏡頭、EDT-19 Editor profiler 面板、AST-06 獨立執行檔打包、AST-13 MV 邊界規則重驗。一律使用既有 canonical 資料模型，不另建平行的 runtime 或資料格式。
4. **ENG-12／VFX-02／VFX-03：** 先提交 Technical Proposal（優先評估既有 ModernGL 後端；不做 C++ migration；不直接替換 renderer），等待 Review。
5. **ENG-17／ANI-05：** 保留通用 hitbox／hurtbox、i-frame、animation cancel 的資料模型與擴充能力；canonical SPEC 若定義為本階段必要的通用 Engine 功能就列入 Closure，若屬 ARPG-only 則維持 Deferred；不自行擴大 ARPG 範圍。
6. **EDT-17／EDT-18：** 標記為 Future／Eventually；保留既有擴充介面；若 SPEC 明確要求當前版本的 plugin runtime／API，仍須完成那一部分。
7. **Manual Validation：** 準備 M1–M5 程序（實體鍵盤、手把、音訊播放／延遲、GPU 視窗、戰鬥演出、Editor 操作、Runtime 遊玩流程）；能自動驗證的先做；需要真人的不得假裝 PASS。
8. **CB15：** 不批准任何未逐項審核的刪除；保留 legacy，直到替代功能通過驗證。
9. **限制：** 不開始 C++ migration、ARPG engine、Dual-Mode demo、完整 JRPG demo、Character Generator、AI 美術生成；不降低 SPEC acceptance criteria；不把 Eventually／Deferred 算進 release blocker；不因 unit test 通過就宣稱 Engine 完成。
10. **執行順序：** Reconciliation → 依 SPEC 優先順序完成已批准的 Functional Closure → ENG-12／VFX-02／VFX-03 提案 → Final Closure Audit。每批回報 Requirement Status、Changed Files、Test Evidence、Integration Evidence、Remaining Gaps。

### Batch D17-1 — Traceability Reconciliation
| 項目 | 內容 |
|---|---|
| Requirement Status | AST-05 C → **A**（實機 field 行走 + 戰鬥動畫量測）。RPG-07 維持 **C**：talk／inspect／open／buy／craft／challenge／capture 由事件與 22 個 WORLD 指令組成，但沒有 SPEC §24 的通用互動定義（capability、target type、cost、check 成敗、consequence、follow-up）；`rpg/interactions.py` 是戰鬥元素互動，不是世界互動。UI-01 維持 **C**：標題、對話、HUD 已在 runtime；背包／裝備／狀態／技能畫面沒有接上。RPG-10、UI-02、ENG-03、ENG-13、ENG-21、EDT-04：只修正缺口描述（spawn、設定畫面、場景 AI 系統、戰鬥 UI 實機接線、存檔中的任務、事件執行都已存在），維持 **B** |
| Changed Files | `docs/audits/SPEC_TRACEABILITY_MATRIX.md`、`docs/audits/DECISION_LOG.md` |
| Test Evidence | 沒有新增測試；依據既有測試（`test_canonical_battle_presentation.py`、`test_session_events.py`、field AI／spawn 測試）與實機結果 |
| Integration Evidence | `REAL_MACHINE_VALIDATION.md` #5、#9（實機 field／戰鬥）；程式碼位置寫在各列 |
| Remaining Gaps | **RPG-07 與 UI-01 是 Core 缺口，但不在 D17 #2／#3 的批准清單上**，需要使用者決定是否列入 Closure |

**Closure Status：** A26／B56／C12／D3 → **A27／B56／C11／D3**。

### Batch D17-2 — Core Functional Closure
| 項目 | 內容 |
|---|---|
| Completed Requirements | EVT-03（`cc6671d`）、EVT-04（`cc6671d`）、ENG-02／ENG-16／ENG-17／ANI-05（`e4418b0`）、EDT-14（`fa86806`）、BTL-04 hit-stop（`678caa8`）、RPG-07（`299ca5e`）、UI-01（`e82fff3`） |
| Changed Files | events：`sequencer.py`、`common.py`、`runner.py`、`scheduler.py`、`lifecycle_bridge.py`、`conditions.py`、`context.py`；runtime：`character_control.py`、`entity_actions.py`、`field_presentation.py`、`status_menu.py`、`game_session.py`、`playable_test_runtime.py`、`collision.py`（Collider2D v2）、`battle_presentation_adapters.py`、`world_command_handlers.py`；rpg：`world_interactions.py`、`actors.py`（DB v26）；project v11；editor：`event_flow_authoring.py`、`event_flow_widget.py`、`hierarchy.py`、`widgets.py`、`authoring_hub_widget.py`、`game_systems_authoring.py`、`action_timeline_authoring.py`；authoring API |
| Tests Executed | 新增 `test_event_sequencer.py`（6）、`test_event_flow_integration.py`（6）、`test_character_control.py`（9）、`test_drag_drop_and_sort.py`（6）、`test_world_interactions.py`（5）、`test_status_menu.py`（4）、hit-stop（1）；全套 **2134 passed**；lint PASS |
| Integration Evidence | 真實 playable runtime：cutscene 中玩家輸入被鎖、角色由 tween 移動、鏡頭／VFX／淡出平行播放、Esc 跳過後終態相同；common event 依 switch 自動／平行執行；battle event 依 HP 條件只觸發一次且在戰鬥中顯示對話、阻擋指令；AI 敵人透過 CharacterController 追擊並以 hitbox 命中玩家 hurtbox；PLAY_ACTION／INTERACT 從事件呼叫；Status 選單透過 canonical screen runtime 投影並使用道具、換裝；真實 canonical 戰鬥量測 hit-stop 延後 0.2 s |
| 發現並修正的既有缺陷 | EventScheduler 在程式以對話結尾時於對話仍顯示時就丟掉 runner；SCREEN_FADE 被排入佇列但從未繪製；project tree 拖放只移動 Qt item（下次 refresh 就還原）；FieldAI 在 AI driver 為 none 時仍直接移動實體；背包畫面沒有 profile 時顯示 item id |
| Remaining Functional Gaps | playable 玩家本身仍由 `_field_input` 直接移動（未改為 PlayerInput2D，避免改變既有手感與已驗證流程） |
| Remaining Validation Gaps | 以上全部缺實機（RM）；人工 M1–M5 |
| Updated Traceability Status | EVT-03、EVT-04、ENG-02、ENG-17、ANI-05、RPG-07、UI-01、EDT-14 → **B**；BTL-04 維持 B（hit-stop 缺口關閉）。**A27／B64／C4／D2** |

### Batch D17-3 — Remaining Functional Gaps（Phase 3）
| 項目 | 內容 |
|---|---|
| Completed Requirements | ENG-15（`2eaffaf`）、ENG-21（`8bbc86b`）、CAM-02 跟隨／boss 開場（`ca6cff1`）、EDT-19（`42f4db3`）、ANI-02（`584644b`）、RPG-04（`72ebb0c`）、WLD-02（`cd7894f`）、RPG-09（`7eb2372`）、CMP-01／02／04（`c499639`）、AST-06（`9ea2d01`）、AST-13（`8e22457`） |
| Changed Files | runtime：`input_rebinding.py`、`save_slots.py`、`npc_state.py`、`behavior_tree.py`、`component_registry.py`、`battle_presentation_adapters.py`（boss 開場、composition、旋轉）、`field_camera.py`、`draw.py`（`rotation_deg`）、`preview.py`、`playable_test_runtime.py`、`game_session.py`、`debugger`；presentation：`character_composition.py`、`battle_runtime.py`；platform：`moderngl_backend.py`（旋轉 quad）；rpg：`drop_tables.py`、`behavior_tree.py`、`world_record.py`（v2）；assets：`__init__.py`（MV 延遲載入）；`project_tools.py`；editor：`input_map_widget.py`、`profiler_widget.py`、`animation_state_machine_authoring.py`／`_widget.py`、`behavior_tree_authoring.py`／`_widget.py`、`character_composition_authoring.py`／`_widget.py`、`model.py`、`shell.py`（分頁、File → Export Game…） |
| Tests Executed | 新增 `test_character_composition.py`（7）、`test_migration_and_export.py` 打包（4）、`test_architecture_boundaries.py`（2），以及 ENG-15／ENG-21／CAM-02／EDT-19／ANI-02／RPG-04／WLD-02／RPG-09 各自的測試；全套 **2175 passed**；lint PASS；`mv_reference` 39 passed |
| Integration Evidence | 真實 canonical 戰鬥：layer 畫在 body 後、attachment 在前並隨朝向鏡像，pygame 與 ModernGL 都以中心旋轉；打包產物以 `python -I`、暫時 HOME 在 repo 外啟動（folder、.pyz、.app），並確認載入的是內附引擎；子行程跑 field、canonical 戰鬥、存檔，沒有任何 MV 模組被載入；其餘項目見各 commit（playable runtime 重綁、欄位存讀、跟隨鏡頭、behavior tree 追擊、NPC 狀態存讀、Profiler 讀取執行中遊戲） |
| 發現並修正的既有缺陷 | `asteria.assets` 一 import 就載入 MV adapter 與 Character Generator 的 `character_bundle`；`project_tools.load_project` 經 `editor.model` 載入整個 editor shell；editor 與 preview 各有一份相同的 component 清單 |
| 新發現的 Functional gap | **W-18：MV 專案匯入後無法遊玩。** `to_asteria_scene` 只把 MV 地圖掛在未序列化的 Python 屬性上，`TileMap2DComponent` 指向不存在的 `mv.tileset.N`；重載後地圖資料消失，`run_preview` 只畫 marker（3 影格 0 個 texture）。先前 W-18 的 PASS 來自已取消的 Character Generator 驗證腳本。修正方向（未實作，待你決定）：匯入時在 asset 邊界把 MV 地圖（含 autotile）烘成 canonical TileMap／Tileset／atlas，runtime 增加一般 TileMap scene 的繪製與行走路徑，不帶任何 MV 語意 |
| Remaining Functional Gaps | W-18（上列）；CMP-01 field 角色尚未消費分層角色（戰鬥已消費）；AST-06 不產生免直譯器執行檔（需 PyInstaller，非專案依賴）；playable 玩家仍由 `_field_input` 直接移動 |
| Remaining Validation Gaps | Phase 3 全部項目缺 RM；人工 M1–M5 |
| Updated Traceability Status | 各項維持 **B**（功能完成、缺實機），缺口描述已更新；W-18 由 PASS 改為 **FAIL**；W-10 改為 HI／PK PASS。**A27／B64／C4／D2**（不變） |

### D17 Phase 4 — ENG-12／VFX-02／VFX-03 技術提案（待審查）
提案見 `ENG12_VFX_TECHNICAL_PROPOSAL.md`（10 節）。建議：沿用 ModernGL，以 GpuPresenter 讓 playable runtime 可選 GL 呈現（現有 pygame 繪製碼不變），再逐步加入 render groups、後製、光照、normal map／shadow、VFX-03；pygame 維持預設與後備（L0）。**核准前不實作。** 需要你決定的四件事列在提案 §10 末。

### D17 Phase 5 — Scope Classification（定案）
| 需求 | 分類 | 依據 | 狀態 |
|---|---|---|---|
| ENG-17 | Core（通用） | S§8 Engine Core 列舉 hitbox／hurtbox、地面／平台偵測；與 ARPG 戰鬥規則無關 | 已實作（D17-2），**B**，缺 RM |
| ANI-05 | Core（通用） | S§11 action timeline；hitbox／i-frame／cancel cue 是通用動畫資料 | 已實作（D17-2），**B**，缺 RM |
| ARPG 戰鬥規則（ARPG-*） | Deferred | S§20「Eventually」；SCOPE_DECISIONS 延後 | 不列 blocker |
| EDT-17 | Eventually | S§31「should eventually」 | **D**，不列 blocker |
| EDT-18 | Eventually | S§32 未要求當前版本的 plugin runtime；既有擴充點（component registry、importer、codec、WORLD 指令 handler）保留 | **D**，不列 blocker |

計數不變：**A27／B64／C4／D2**。

### Batch D17-6 — Validation Closure（Phase 6）
| 項目 | 內容 |
|---|---|
| Completed Requirements | ENG-21、CMP-02、AST-06、EDT-19 → **A**（所有面向皆有實機證據） |
| Changed Files | `scripts/real_machine_validation.py`（新增 cutscene、battle_features、menus、follow_camera、packaged_app、editor_d17；`--only` 合併結果）；`runtime/battle_presentation_adapters.py`（戰鬥鏡頭限制在戰場內）；`platform/pygame_battle_ui.py`（共用 `renderable_text`）；`runtime/playable_test_runtime.py`；`REAL_MACHINE_VALIDATION.md`（項目 11–19、M6–M9） |
| Tests Executed | 實機 Apple M5、Cocoa、真實 SDL 按鍵事件：新增 9 項全部 **PASS**；回歸測試 2 項；全套 **2176 passed** |
| Integration Evidence | 截圖逐張檢視（cutscene、boss 開場、分層角色、status、存檔欄位、Controls、跟隨鏡頭、6 個 editor 畫面）；editor 檢查前後比對專案檔未被寫入 |
| 發現並修正的缺陷 | boss 開場鏡頭拉近時戰場邊緣露出殘影（`c8b7616`）；預設字型缺箭頭字形，顯示為方框或「??」（`c8b7616`） |
| Remaining Functional Gaps | W-18（MV 地圖匯入後無法遊玩，待決定）；CMP-01 field 消費；ENG-12／VFX-02／VFX-03（提案待審） |
| Remaining Validation Gaps | 人工 M1–M9 全部 NOT EXECUTED（需要人）；手把 BLOCKED；其餘 B 項目的缺少證據逐項列在 REMAINING_WORK_PLAN |
| Updated Traceability Status | **A31／B60／C4／D2**（由表格逐列計算；另有 2 項 E） |

## D18 — Consolidated SPEC Closure（2026-10-11）

依「Consolidated Spec Closure Execution」指示執行 WS1–WS8。起點 `f6b116b`（A31／B60／C4／D2）。

### Batch D18-1 — W-18 MV 匯入可遊玩（`a432282`、`594639d`）
| 項目 | 內容 |
|---|---|
| Completed Requirements | W-18；AST-13（A） |
| Changed Files | `assets/rpg_maker_mv_map_bake.py`（新）、`rpg_maker_mv_map.py`、`rpg_maker_mv_project.py`、`local_reference.py`；`runtime/tilemap_field.py`（新）、`interaction.py`（touch trigger）、`components2d.py`（Interaction2D v2）、`game_session.py`、`game_save.py`、`collision.py`、`preview.py`；`platform/pygame_backend.py`；editor File → Import RPG Maker MV Project…；`asteria-import-mv` |
| Tests Executed | `test_mv_import_playable.py`（7）；全套 2183 |
| Integration Evidence | 匯入→存檔→重載→遊玩（新行程，不載入 MV 模組）；碰撞、NPC 對話、門轉移、存讀檔；實機 `mv_import_real_window` PASS |
| 發現並修正 | 轉移後的存檔無法讀回（玩家實體在另一個場景）；玩家可穿過 NPC；事件與玩家腳底基準不一致 |
| Remaining | MV 事件只轉換第一頁＋「對話後消失」慣用法；其他指令列為匯入問題 |

### Batch D18-2 — ENG-12 GPU 呈現（`65a3104`）
GpuPresenter：playable runtime 可選 ModernGL，畫面逐像素等於合成畫面；GL 失敗自動回到 pygame；vsync 預設關閉（macOS Cocoa swap 會卡住，實機發現）。實機 56.1 fps、上傳 0.41 ms、GPU 0.58 ms。pygame 仍為預設。

### Batch D18-3 — VFX-02／VFX-03（`a225258`、`d639e73`、`2eaabc3`）
場景元件 Environment2D／LightSource2D／ShadowCaster2D／WaterRegion2D／MotionTrail2D；world／UI 分層；GPU EffectChain（光照、陰影、normal map、霧、水、bloom、grading、vignette、內建與專案 shader）；pygame 後備（近似光照、霧、水；其餘列為不支援）；天氣粒子；afterimage／trail（motion_fx timeline 頻道）；tile-map 專案在兩個後端都套用環境。測試 `test_vfx_environment.py`（16）；實機 vfx 四項 PASS。

### Batch D18-4 — CMP-01 field、STR-01（`875a58e`、`3c6dd57`）
field 繪製分層角色與 attachment。`validation/jrpg_stress.py` 在參考遊戲一次展示 §35 全部 13 項。發現並修正：**引擎**——戰鬥主體沒有 StateRuntime，break 套用 `broken` 會丟例外；**內容**——break 不可達（8 次弱點傷害 ≥ 11,760 > 9,000 HP）、`broken` 未定義：stagger 8 → 5、break timeline_shift 1.5、新增 StateDefinition。golden 只有 rpg_database hash 變動。記錄未改：haste_song 的 `buff.haste` 在此內容沒有效果。

### Batch D18-5 — CB15 退役（`71e76c1`、`f06a88b`）
退役 Character Generator（A1–A5、A7、A8），保留 CreateCharacterCommand（移除 bundle 分支，先移植通用測試）；A9 legacy 戰鬥呈現 **BLOCKED**（canonical 仍以 legacy world layer 作後備）；另審查 4 個候選並保留。備份 zip、回復參考見 CB15_RETIREMENT_REVIEW Part D。測試 2206 → 2165。

### Batch D18-6 — 驗證收尾（`37b0013` 與本批文件）
新增實機檢查：gameplay_systems、game_menus_more、editor_workflows（加上 D18-1～3 的 mv_import、gpu、vfx）。全套重跑：**29 PASS、3 NOT EXECUTED、1 BLOCKED**（`37b0013` 的 commit message 寫成 34 PASS，為誤算，以 results.json 為準）。修正：status 畫面讀取 `event.mod` 時未防禦；`--only` 合併殘留舊的 crash 項目。

### Traceability
逐列依證據重評（見矩陣 D18 註記），**A31／B60／C4／D2 → A49／B45／C1／D2**（另 2 項 E）。C、D 三項（TPL-01、EDT-17、EDT-18）皆為 Eventual。TPL-01 依 SPEC §36「Potential templates」改列 Eventual。

### 需要你決定
1. macOS 預設後端是否改為 ModernGL（實機已驗證畫面相同、效能相當；建議先完成人工 M10 目視）。
2. A9 legacy 戰鬥呈現：要退役需先讓 canonical 在沒有 combatant visuals 的專案也能完整呈現（另一個功能批次）。

## D19 — Final Closure Execution（2026-10-11）

依「Asteria — D19 Final Closure Execution」執行。起點 `9b93763`（A49／B45／C1／D2）。期間使用者追加三項要求：GUI 配色與圖示、資訊密度、GUI 文字精確化，全部納入本期。

### D19-1 — Canonical 戰鬥呈現完整取代 legacy（`94a71b2`、`ae087c2`）
| 項目 | 內容 |
|---|---|
| 問題 | 沒有 combatant visuals 的專案仍走 legacy world layer；預設 adapter 是 legacy |
| 做法 | 沒有戰鬥美術的成員改用 canonical 產生的 sprite sheet：idle、攻擊前衝、受擊閃光、KO 四格，來源是 manifest 的立繪或敵人圖，沒有圖就用剪影。預設編排會把技能 fx 當 canonical VFX 播放，sfx 當音訊 cue。boost 移到行動選單，缺背景時用產生的背景。預設 adapter 改為 canonical |
| 驗證 | `test_battle_without_art.py`（3）；實機 `battle_without_art_pygame`、`battle_without_art_moderngl` PASS（真實按鍵打到勝利、回到 field、F5 存檔） |
| CB15 | A9 退役。備份 `../Asteria_backup_2026-10-11_cb15_legacy_battle.zip`，回復 `git revert 94a71b2`。詳見 CB15_RETIREMENT_REVIEW Part E |

### D19-2 — 已知整合問題（`aa25d27`、`c9e704d`）
- **haste_song 沒有效果：** 根因有兩個。第一，`speed_timeline` 是 CONTINUOUS 排程，下一個回合由成員自己的速度決定，但 `PartyMember.initiative` 是靜態值，狀態改變的速度到不了 scheduler。第二，內容本身沒有速度效果。修正：`PartyMember.current_initiative` 讀取 subject 的 speed；haste_song 加上 speed +20，slow_hex 加上 debuff.slow 與 speed −20。沒有新增 SPEC 未定義的規則。
- **編輯器重複的「Assets / Console」分頁：** 根因是 Qt 6 的 `QMainWindowLayout` 在第二個 dock 群組做 tabify 時，留下一條仍然可見的舊 tab bar；`restoreState` 之後還會更多。最小重現：任何兩個 tab 群組都會發生。修正：建立面板後、還原版面後、移動 dock 後，隱藏全部 dock tab bar 並重新 layout，Qt 只會重新顯示仍在使用的那幾條。測試 `test_editor_dock_tabs.py` 在修正前失敗、修正後通過（offscreen 與 Cocoa）。

### D19-3 — 編輯器 UI／UX（`ac63eb4`、`e5a2dac`、`21a30bd`、`6be5ffc`、`e56b748`、`53ec4a6`）
真實 Cocoa 稽核工具 `scripts/editor_ui_audit.py`：逐一切到 19 個工作區頁面截圖，並列出被截斷的文字、超出父元件、過小的控制項。
- **視窗比螢幕大：** 最小尺寸原本是 1721×1772，這台 MacBook 可用範圍只有 1470×840。頁面改為可捲動，tab 列可捲動，面板預設寬度改小。改善後最小尺寸 763×435，1280×800 與 1440×900 的缺陷數都是 0。
- **配色與圖示：** 55 個程式繪製的向量圖示，沒有第三方美術。每個工作區有自己的顏色，按鈕依用途上色，面板標題列有圖示，Inspector 有空狀態畫面。使用者覺得配色不好看後，主題改為三套 palette（Graphite 為預設、Twilight、Daylight），可在 View ▸ Theme 即時切換並記住選擇。
- **資訊密度：** 下拉選單、表單、按鈕列在空間不足時會收合或換行。各頁面最小寬度：Enemy AI 1260→911、Character Composition 867→614、VFX 1100→806、Behavior Trees 1058→506。各工作區記住自己的面板配置，資料庫類工作區預設使用整個視窗。
- **文字：** 檢查全部 443 個 GUI 字串與分類名稱。工作區改名 RPG→Database、UI→Presentation，各分頁、戰鬥規則與呈現分類也一併改名。record 編輯器顯示可讀的欄位名稱，資料鍵與檔案格式不變。
- **版面持久化：** 每個 dock 都有 objectName，版面會還原；新增 View ▸ Panels、Reset Layout、Ctrl+1…6。

### D19-4 — B 項自動化驗證（`d335c72`、`9e1ba31`、`9576dda`）
- **`b_items_replay`：** session 層整合測試在實機 playable 視窗重跑，斷言不變。每次 session 呼叫後只繪製目前狀態，不推進時間、不送輸入，也不載入遊戲本身沒有載入的圖片。沒有實際驅動視窗的測試不計入。79 個測試、13 個檔，cocoa。
- **`engine_systems_real_window`：** `Application.run` 實機主迴圈，涵蓋 fixed step、trigger、layer／mask、hitbox、frame events、action timeline、look-ahead、persistent entity。
- **`battle_memory_real_window`：** 12 場戰鬥，每場後戰鬥圖片 0 殘留，RSS 沒有增長。
- **矩陣：** 23 項 B→A，**A72／B22／C1／D2**。

### D19-5 — M10 自動化部分（`2d06beb`）
同一個 field 畫面在兩個後端比較：
- **無環境效果：** 兩者完全相同。
- **有效果：** 10.1% 的像素不同（pygame 不支援 bloom、grade、shadows、vignette）。
- **30 秒 soak：** 兩個後端都是 0 錯誤；ModernGL 59.7 fps、pygame 58.9 fps。ModernGL 前 10 秒的 RSS 增長是驅動暖機，另外跑 90 秒持平。

**決定：** pygame 仍是 macOS 預設，ModernGL 為選用。人工目視 M10 仍為 NOT EXECUTED。

### 驗證結果
- **自動化測試：** 2180 passed。
- **實機全套重跑（2026-10-11 23:24）：** 49 PASS、3 NOT EXECUTED（M1、M3、M4）、1 BLOCKED（M2）、0 FAIL。
- **編輯器 GUI：** dock 測試在 Cocoa 下通過；UI 稽核 0 缺陷。

### 需要你決定
1. BTL-02：狀態的持續傷害（DOT）是否要套用屬性倍率（SPEC 沒有寫明）。
2. CB15：D19 掃描到 23 個沒有產品程式引用的模組，要不要另開批次逐項審查是否退役（見 CB15 Part E）。
