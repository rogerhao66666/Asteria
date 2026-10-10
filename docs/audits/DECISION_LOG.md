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
