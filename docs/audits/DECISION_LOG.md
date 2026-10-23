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

## D20 — 作者彈性、模組審查、剩餘 B 項實機證據（2026-10-12）

### D20-1 — 引擎不限制作者（`a864a05`、`776bcb9`、`d40ea2e`、`553a60d`、`6810b5b`）
使用者決定：「我們的引擎不要有任何限制使用者的行為」。SPEC 沒寫死的規則都改成作者可選的資料，並且可以在編輯器裡設定：
- **DOT：** 預設是固定傷害。在 Status Effects 填 Interaction Tags，就會經過互動規則套用倍率。D19 的待決事項 1 由此結案。
- **逐回合加重的 DOT：** PeriodicEffect 的 `growth`、`growth_mode`（add／multiply）、`growth_cap`，例如 10、20、30……。Game Data 新增「Status Definitions」分類可以編輯。
- **倍率規則：** 任意倍率、克制、屬性、武器類型都可以設定，弱點也可以是「劍」。攻擊在能力上標武器類型（`weapon.sword`），物品只標攜帶的裝備（`equip.sword`）。破盾倍率、Boost 的連擊（repeat）或增幅（power，`boost_mode`）、雙武器、副職業都可以只靠資料組出八方旅人式的系統。
- **背包規則：** 堆疊上限、唯一物品、種類上限（關鍵物品可豁免）、滿了時的處理（fill／reject）。
- **召喚與夥伴：** 召喚（敵方小兵、預備隊夥伴、事件 SUMMON）、捕捉後成長、收納。
- **技能：** 冷卻回合，以及行動時序 `action_timing`（immediate／timeline，預設 immediate，參考專案不受影響）。

### D20-2 — CB15 未被引用模組審查（`78dd3fb`）
使用者核准：沒用到的就移除。用可達性分析（從產品進入點出發）檢查，退役 35 個模組，保留 7 個（autofix、usability_gate、rpg_maker_mv_weapon、reference_world、presentation_timing、animated_text、text_render_integration）。
- **備份：** `../Asteria_backup_2026-10-11_cb15_unused_modules.zip`
- **回滾：** `git revert 78dd3fb`
- **詳細記錄：** CB15 Part F

autofix 原本沒有產品入口，已在 D20-4 接上編輯器。animated_text 已由 field popup 使用（`a619aeb`）。

### D20-3 — 編輯器排版（`4226917`、`3cc0228`）
- 表單改成標籤在欄位上方，依寬度排成最多欄數，減少左右捲動。
- 清單和明細在寬度足夠時並排。
- 右側加上內距，捲軸前留空隙。

### D20-4 — 剩餘 B 項實機證據（`ecbad0b`、`82bf170`、`a619aeb`、`27521d2`）
- 補功能：
  - EVT-04：sequence 會等它的對話軌道把句子讀完。
  - ANI-02：作者的狀態機驅動戰鬥動畫。
  - CMP-03：field popup 使用通用 animated text，並新增 SHOW_POPUP 指令。
  - AST-11：Asset 清單新增 Auto-fix Image（預覽、`.bak.png` 備份、破壞性修正需確認）和 Pack into Atlas。
- 新的實機檢查：
  - `editor_characters`、`migrated_project`、`asset_categories`；
  - `engine_systems` 加 parallax 和 target group；
  - replay 新增 7 項。
- 實機截圖檢視時找到並修正 2 個缺陷：
  - 新放置角色的 sprite sheet 顯示為「Missing」，Scene 也不畫出來；
  - Inspector 的 combo／checkbox 底下透出值的文字。
- **矩陣：** 13 項 B→A，逐列重算為 **A85／B9／C1／D2**。D19 註記寫 A72，但逐列重算 D19 表格是 A71，多算了 1 項，本次更正。

### 驗證結果
- **自動化測試：** 1954 passed。
- **實機全套重跑（2026-10-12）：** 58 PASS、3 NOT EXECUTED（M1、M3、M4）、1 BLOCKED（M2）、1 FAIL。
  - FAIL 是 weather load：31.8 fps，門檻 55。執行時 macOS 低耗電模式開著；舊 commit `06a5577` 在相同條件下也只有 34.7 fps，所以不是程式回歸。關閉低耗電模式後要重跑。
  - `editor_workflows_gui` 在全套中因鍵盤焦點失敗一次，單獨重跑通過；結果檔記錄重跑，並附註說明。

### 剩下的 B（9 項）
- 需要人或裝置（M1–M5、M8、M10）：ENG-14、ENG-15、ENG-18、CAM-01、VFX-02、VFX-03、BTL-04。
- 還缺功能：
  - VFX-01：沒有粒子發射器資料，另外還要人眼確認。
  - AST-07：Item、Equipment 沒有 runtime 畫面，選單不顯示物品圖示。

### D20-5 — 使用者決定：AST-07、VFX-01 兩個都做（`15157ac`、`5fcfa57`）
- **AST-07 物品／裝備圖示：**
  - 選填的 `icon_id`，沒設定時不寫入，舊資料不變。
  - 可指向任何 icon 資產（用 region 取 atlas 的一格）、舊式資產或 PNG 路徑。
  - 商店、Items、Equipment 畫面會繪出圖示。
  - 編輯器提供附縮圖的下拉選單，也可以直接輸入 id 或路徑。
  - MV 匯入會保留 IconSet 圖示。
  - 參考專案的 36 個 CC0 圖示打包成一張 atlas。
  - golden 的 rpg_database hash 有更新：已確認除了 `icon_id` 之外完全相同。
- **VFX-01 粒子特效：**
  - 所有參數都由作者決定：發射量、burst、持續時間（或循環）、生命、速度、方向、散布、重力、阻力、發射形狀、大小與顏色隨時間變化、粒子形狀（圓、方、火花、圖片）、混合模式、旋轉、局部座標。
  - 三種用法：場景實體上的 `ParticleEmitter2D`、事件的 `PLAY_VFX`、戰鬥時間軸的 VFX beat。
  - 編輯器的 Particle Effects 頁有即時預覽、7 個預設，Apply 是一次復原步驟。
  - Problems 會警告發射器指到不存在的特效。
- **實機檢查時找到並修正的缺陷：** 戰鬥 VFX cue 每一幀都會被替換，導致粒子每幀重新開始、看起來只有一個點。已改用穩定的 key，並加上回歸測試。
- **矩陣：** AST-07 B→A。VFX-01 的功能缺口已補上，剩人工目視 M10，維持 B。→ **A86／B8／C1／D2**。
- **驗證：** 自動化測試 1970 passed；實機 63 PASS、3 NOT EXECUTED、1 BLOCKED、1 FAIL（weather load，低耗電模式仍開著）。

### 需要你決定
1. ~~關閉低耗電模式後重跑 weather load~~：**使用者決定（2026-10-12）先不測。** 項目 25 仍記為 FAIL（低耗電模式；程式未回歸），等之後再重跑 `--only vfx`。
2. ~~AST-07、VFX-01~~：已依使用者決定完成（D20-5）。

### D20-6 — 八方旅人式戰鬥 demo（`6fb8d9c`、`524b8cd`）
使用者問 demo 是否完成。檢查後的結論是：引擎能力大致都有，但缺幾項功能，也沒有可遊玩的專案。這次全部補齊，並做成可遊玩的 demo。

**引擎（全部是選填資料，不設定就不寫入）：**
- 技能：
  - `battle_costs`：奧義消耗 3 BP；
  - `hits`：多段攻擊，每段可以有不同的傷害類型和倍率；
  - `battle_resource_gains`：分 BP 給隊友；
  - `commands`：使用後執行世界指令，例如叫出寵物；
  - `concoct_station`：在戰鬥中調和；
  - `apply_states`：施加或解除狀態。
- 物品：`battle_ability`，在戰鬥中使用時發動對應的技能。
- 敵人用技能時也會套用上述效果。
- 戰鬥時登錄專案的全部技能，物品和召喚物都能出手。
- 狀態的能力值修正（攻擊提升、防禦下降）現在會進入傷害公式。這原本是引擎缺口：修正值一直沒有被使用。
- 戰鬥資源 `subject_maximum`：每個敵人有自己的護盾數。破盾門檻 `reset_to_maximum`：破盾後護盾回到該敵人自己的上限。
- `ability_unavailable` 會說明技能不能用的原因。被跳過的回合會記錄到戰鬥紀錄。

**戰鬥 UI（`runtime/battle_commands.py`）：**
- 列出全部技能，可切換 Skills／Items。
- 左右鍵調 Boost，選擇目標，選擇調和材料，Esc 返回。
- 不能用的技能會反灰，並顯示原因。
- 敵人下方顯示護盾數和弱點（未揭露時顯示 ?），也會顯示 BROKEN／SLEEP；角色下方顯示 BP 點數和狀態。
- 選單寬度依內容調整。

**編輯器：** 資料樹右鍵可以「Add Entry／Remove Entry／Add Field」，hits、commands、狀態、BP 消耗等欄位都能在編輯器裡編輯。

**Demo（`reference_projects/octopath_demo`）：**
- 以參考專案的 CC0 素材建置。
- 4 位旅人，各有主職和副職，各帶兩種武器；另有一隻寵物。
- 3 個敵人，各有不同的護盾數和弱點。
- 4 個奧義、需要兩種武器的 Twin Fang、多段攻擊和多屬性技能、Donate BP、調和配方 4 種，以及中毒、睡眠、沉默、攻擊提升、防禦下降、解除異常。
- 自動化測試 9 項，其中一項是全程用鍵盤打贏戰鬥。
- 實機項目 44 為 PASS；demo 測試也在 replay 中跑過。

**驗證結果：** 自動化測試 1987 passed；實機 65 PASS、3 NOT EXECUTED、1 BLOCKED、1 FAIL（weather load，使用者決定先不重跑）。

**矩陣：** 計數不變（BTL-02／BTL-03／GP-02 原本就是 A，這次補上 demo 的證據）。

### D20-7 — demo 加入多種敵人（`0966f2f`）
使用者要求加入更多不同類型的敵人。新增 6 種敵人，並重新設計 Skeleton Knight。每種的打法都不同，全部只用資料設定，素材是 CC0 的 Ninja Adventure：

| 敵人 | 特性 |
|---|---|
| Gel Slime | 吸收火（火屬性會幫它補血），會分裂 |
| Web Spinner | 降低防禦，三連咬 |
| Bone Wraith | 不死系，免疫中毒，會吸血、冰凍、沉默 |
| Skeleton Knight | 抗短劍和弓 |
| Pit Viper | 速度極快，會施毒、降防 |
| Mirror Gazer | 反射魔法，免疫睡眠，會讓全隊睡著 |
| Iron Samurai | 8 層護盾，抗劍、斧、弓，會戰吼、旋風斬 |

- 新增 4 場戰鬥，由場景中遊蕩的敵人觸發（碰到就開打）。
- 新增選填版面欄位 `stage_front`（預設 0.30 不寫入）。demo 把兩邊的站位往外推，讓指令選單不會蓋住敵人。

**自動對戰時發現並修正的引擎缺陷：** 敵人 AI 會選到已倒下的我方角色當目標，導致行動失敗。現在只會選還站著的角色，並已加上回歸測試。

**驗證：**
- 自動化測試：1999 passed（demo 測試 21 項，包含每場新戰鬥都用鍵盤打贏，且每個敵人招式都有用到）。
- 實機：項目 44 PASS，加上 4 場新戰鬥的截圖；replay 全部 PASS。

### D21 — 計算核心層（kernels）與 numpy（`4d2a365`）

使用者想引入 C++ 提升效能。討論後的決定：
- 現在**不寫 C++**。原因是目前沒有量到必須用 native 才能解決的瓶頸，回合制也不吃 CPU。
- 為之後的 ARPG 先把熱點迴圈抽成獨立的計算核心層 `asteria.kernels`，介面只收陣列。以後要加 C++，只需要多寫一套實作。
- 現在就用 numpy 當第一套加速實作。numpy 是選用相依（`pip install .[fast]`），沒裝時自動退回純 Python。

**內容：**
- `kernels/_python.py`：參考實作，永遠可用。
- `kernels/_numpy.py`：同樣的運算、同樣的順序，結果必須完全相同。
- 由 `ASTERIA_KERNELS`（`auto`／`python`／`numpy`，預設 `auto`）或 `kernels.use()` 選擇。
- 目前有兩個 kernel：
  - `ParticleStore`：粒子的更新、位移和繪製資料。`ParticleSystem` 改用它；`ParticleView` 改成 NamedTuple，屬性不變。
  - `aabb_pairs`：碰撞 broad phase。`CollisionWorld.contacts()` 改用它；`grid` 改成第一次查詢時才建立。配對順序改為固定排序。
- 尋路、ARPG AI、投射物等還不存在的系統**不先加介面**，等第一版做出來再抽。

**量測（Low Power Mode 開著，`time.perf_counter`，每項 20–200 次平均，單位 ms）：**

| 項目 | python | numpy |
|---|---|---|
| 粒子 1933 顆：update | 0.734 | 0.134（約 5.5 倍） |
| 粒子 1933 顆：views | 1.847 | 0.689（約 2.7 倍） |
| 粒子 29 顆：update + views | 0.038 | 0.029 |
| 碰撞 3000 個：配對 | 2.89 | 1.65 |
| 碰撞 3000 個：建立 + contacts | 11.37 | 9.50 |

**誠實說明：**
- 碰撞整體只快約 15%，因為大部分時間花在逐個 entity 讀取位置、建立 shape（Python 物件）。要再快，資料本身要以陣列存放，這是 ARPG 設計時要處理的事。
- 天氣負載（項目 25）的瓶頸是 pygame 逐條畫線，不是更新（2000 顆雨的更新只要 0.375 ms），numpy 幫不上，所以這次沒有改天氣。
- 一般場景的粒子只有幾十顆，fps 本來就被垂直同步限制在約 60，所以實際遊玩看不出差別。

**驗證：**
- 自動化測試：新增 `tests/test_kernels.py` 15 項。7 種 preset 逐影格比對兩套實作的結果完全相同；碰撞配對和暴力法逐對比對；碰撞 contacts 相同。
- 實機（scratchpad，不寫入 evidence）：`icons_and_particles` 分別用 `ASTERIA_KERNELS=numpy` 和 `python` 在 Cocoa 視窗跑，兩者都 PASS（58.9／59.0 fps，p99 23.1／22.7 ms）。

### D21-2 — 天氣也改用計算核心層

使用者要求天氣也一起改。天氣的儲存、移動和繪製改成 kernel 的 `WeatherStore`：
- `python`：原本的迴圈和 pygame 逐顆繪製。
- `numpy`：移動以陣列計算。繪製方面，pygame 會把座標截斷成整數，所以每顆粒子的形狀（雨線、葉片橢圓、雪點）只取決於幾個整數。每種形狀先讓 pygame 畫一次記下來，再一次貼到所有同形狀的粒子上。
- **畫出來的像素和 pygame 逐像素相同**。測試涵蓋 4 種天氣 × 3 種風速（含畫面邊緣、強逆風），共 12 項。

**量測（單獨跑，1280×720，單位 ms）：**

| 項目 | python | numpy |
|---|---|---|
| 雨 2000 顆：更新 | 0.17 | 0.02 |
| 雨 2000 顆：繪製（不透明畫面） | 0.93 | 0.84 |
| 雪 2000 顆：繪製（不透明畫面） | 0.87 | 0.69 |

繪製大部分時間花在整張畫面的清除和貼圖（約 0.5 ms），兩套實作都要付，所以繪製只快一點。

**實機（Cocoa，低耗電模式已關閉）：** 同一個天氣負載檢查（2000 顆雨 + 完整 GPU 效果）：

| kernel | fps | 天氣區段平均 |
|---|---|---|
| python | 59.5 | 3.05 ms |
| numpy（預設） | 59.2 | 1.56 ms |

- 項目 25 由 FAIL 轉為 **PASS**。原因是低耗電模式關閉了，**不是** numpy；numpy 讓天氣的耗時減半，多出餘裕給 ARPG。
- `--only vfx` 已寫回正式 evidence：70 項中 66 PASS、3 NOT EXECUTED、1 BLOCKED、**0 FAIL**。AUTOMATED VALIDATION COMPLETE 改為達成。
- 自動化測試：2026 passed。


## D22 — 開始 ARPG（2026-10-13）

**決定（使用者）：**
- 解除 ARPG 的延後（SCOPE_DECISIONS／Closure Policy）。原因是 D21-2 時功能 closure 和自動化驗證都已完成，只剩手動和實機項目。
- 俯視和橫向兩種視角都支援，由作者在每個場景選擇。戰鬥核心只寫一次，兩種視角共用。
- 形式：通用功能放進引擎，另外做一個 demo 專案 `reference_projects/diablo_demo`，專案裡有俯視野外和橫向地城兩種區域。
- 第一階段做完整核心：判定、無敵幀、擊退、投射物、敵人 AI、受傷和死亡，加上壓力場景（300 隻敵人 + 500 顆投射物），先量測效能。
- 先寫設計文件，核准後再實作。

**設計：** [ARPG_DESIGN.md](ARPG_DESIGN.md)：現有系統盤點、架構原則、戰鬥流程、新資料、A1–A9 分批計畫、效能目標、不在範圍內的項目。

**狀態：** 已核准，實作中。

**需要你決定：** 橫向素材的來源（建議下載 CC0 的 Kenney Pixel Platformer）；核准計畫後從 A1 開始。

**核准（2026-10-13）：** 使用者核准計畫並同意下載 Kenney Pixel Platformer 1.2（CC0，kenney.nl，`kenney_pixel-platformer.zip`，260 KB，存到 git-ignored 的 `local_reference/free_assets/kenney_pixel-platformer/`，已下載，授權檔確認是 CC0）。Demo 改成暗黑破壞神式：打怪掉寶、職業、技能樹也一起做進引擎。計畫改成 A1–A11（新增 A6 掉寶、A7 職業和技能樹），見 [ARPG_DESIGN.md](ARPG_DESIGN.md)。

**使用者追加（2026-10-13）：**
- 系統一律做成通用的。暗黑式玩法只是 demo，引擎不能只支援暗黑；不限制作者的程式、想法、美術和玩法。已寫進 ARPG_DESIGN §3 原則 0。
- A1 也要做霸體和倒地。

### D22-A1 — 戰鬥核心

**改動的檔案：**
- `gameplay/attacks.py`（新）：`AttackDefinition` 欄位包括傷害公式（內嵌或引用共用公式）、扣哪個資源（負數就是回復）、標籤、韌性傷害、硬直、擊退（方向模式 away／attacker_facing／fixed、角度、橫向上挑）、打擊停頓（雙方／全畫面）、命中後無敵、最多打中幾個目標、爆擊、命中事件、`armor_break`、倒地。
- `gameplay/library.py`：gameplay library v2 新增 `attacks`，v1 檔案照樣能讀。
- `gameplay/action_timeline.py`、`runtime/entity_actions.py`：新 cue `armor`（霸體等級 + 秒數），動作結束時霸體也跟著結束；`paused` 讓打擊停頓時時間軸暫停。
- `runtime/character_control.py`：控制器 v2 新增 `facing`（跟著移動方向，橫向只分左右）、外力推動 `apply_impulse`（依 `knockback_decay` 衰減，撞牆就停）、`lock_control`（硬直、倒地時不吃輸入）、`paused`。俯視的快速移動（例如擊退）會停在牆邊，不再差一整步。Hitbox2D／Hurtbox2D v2 新增 `follow_facing`：判定框照「面向右」編輯，面向左時鏡像，面向上下時轉 90 度。三個元件都有 v1→v2 migration。
- `runtime/combat.py`（新）：`CombatantComponent` 欄位包括陣營、資源、生命資源、數值、標籤、韌性、韌性回復、硬直時間、破韌結果（硬直或倒地）、霸體等級、霸體時的受傷倍率、倒地和起身時間、倒地無敵、起身無敵、擊退抗性、受傷後無敵、死亡行為（移除、停用、保留）、掉落表、死亡事件。`CombatSystem` 把 `HitEvent` 結算成上面這些效果，並發出 `CombatEvent`：damage、staggered、knocked_down、got_up、death、drop、hit_event。數值可以內嵌，也可以由 `stats_provider` 提供（A7 會接上職業和裝備）。
- `runtime/game_session.py`：場景系統加入 `combat`，接上時間軸、控制器和判定；掉落表的保底次數存在 world counters；profiler 有 `combat` 區段。
- `runtime/component_registry.py`：註冊 Combatant。
- `editor/integrated_authoring.py`：新增「Attacks (Real-Time Combat)」紀錄分類，可以新增、編輯、復原、貼上。Combatant 元件由 schema 自動出現在 Inspector。
- `tests/test_combat.py`（新，17 項）。

**需求涵蓋（SPEC §20）：** Hitbox/hurtbox（隨朝向）、Knockback、Stagger/poise、Hitstop、I-frames、霸體、倒地。

**執行的測試：** `tests/test_combat.py` 17 passed；完整套件 **2043 passed**。

**整合證據：** 在 PlayableTestRuntime 的參考專案上跑真的 `GameSession.field_update`：玩家播放動作時間軸，打中場景裡的敵人，依序觸發扣血、擊退、倒地、起身，第二擊打死，實體被移除，掉落表擲出物品。編輯器裡改攻擊紀錄後，執行中的場景讀到同一份資料，復原也有效。

**修掉的問題（測試抓到的）：** 擊退原本丟掉了垂直分量，俯視角色只會被往左右推。

**還沒做：**
- 實機視窗驗證：A1 沒有畫面上的變化，畫面上的表現在 A8 介面那批一起做實機驗證。
- 編輯器 Cocoa 截圖：專用工作區和判定框預覽在 A9。
- 持續性的狀態效果（中毒、燃燒）在即時戰鬥中的計時：還沒接，A3 技能那批一起處理。
- 接觸傷害（碰到敵人就受傷）在 A4。

**狀態：** A1 完成，接著做 A2。

### D22-A2 — 投射物和壓力場景

**改動的檔案：**
- `kernels/_python.py`、`kernels/_numpy.py`：新增 `aabb_cross_pairs`（兩組框互相比對；numpy 用網格 join，全部向量化）和 `ProjectileStore`（追蹤、重力、移動、計時；判定框、到期、保留、改值）。追蹤只用向量運算和 `sqrt`；每種轉向速率的 cos/sin 由 `math` 算一次，兩套共用，所以兩套結果**逐位元相同**。
- `gameplay/projectiles.py`（新）：`ProjectileDefinition` 欄位包括命中時用的攻擊、速度、壽命、重力、判定框、穿透（-1 = 不限）、碰牆行為（消失／反彈／停住／穿過）、牆的圖層、反彈次數、追蹤轉速和範圍、外觀、結束事件。gameplay library v3 新增 `projectiles`，v1、v2 照樣能讀。
- `runtime/projectiles.py`（新）：`ProjectileSystem`。投射物**不是** entity，數值都在 kernel 的陣列裡。發射時可以設數量、扇形角度和偏移，偏移和角度會隨朝向轉；每幀做追蹤、重力、碰牆、批次判定，命中交給 combat 結算（擊退會從投射物的位置推開）；發出 fired、hit、ended 事件，提供 `views()` 給畫面。
- `gameplay/action_timeline.py`、`runtime/entity_actions.py`：新 cue `projectile`。
- `runtime/character_control.py`：`HitboxSystem` 改用 kernel 一次比對所有判定框和受擊框（事件和順序不變）；`HitEvent` 新增選填的 `origin`、`direction`。
- `runtime/combat.py`：擊退方向會用命中的來源點和飛行方向；投射物的命中不算進近戰的 `max_targets`。
- `runtime/game_session.py`：場景系統加入 `projectiles`，有 profiler 區段。
- `editor/integrated_authoring.py`：新增「Projectiles (Real-Time Combat)」紀錄分類。
- `validation/arpg_stress.py`、`scripts/arpg_stress.py`（新）：壓力場景。
- 測試：`tests/test_projectiles.py`（新，17 項，python／numpy 都跑）、`tests/test_kernels.py`（+8）。

**執行的測試：** 完整套件 **2068 passed**。

**整合證據：** `GameSession` 中，玩家的時間軸 `projectile` cue 射出箭，打中敵人並扣血；同一個齊射場景用 python 和 numpy 跑，傷害、結束原因、每個事件的座標全部相同。

**量測：壓力場景**（`scripts/arpg_stress.py`，低耗電模式關閉，headless，只有引擎運算、沒有繪製）。設定是 300 隻追擊敵人（控制器、碰撞框、受擊框、戰鬥數值）、500 顆在飛的穿透投射物、每 0.5 秒一次近戰；跑 120 幀，單位 ms：

| kernel | 每幀平均 | p95 | ai | collision | projectiles | combat |
|---|---|---|---|---|---|---|
| python | 45.2 | 47.5 | 6.7 | 28.8 | 12.2 | 1.3 |
| numpy | 42.8 | 44.3 | 6.9 | 29.3 | 9.1 | 1.3 |

兩套 kernel 命中數相同（3889）。**離目標（numpy ≤ 6 ms）很遠。**

**cProfile 找到的瓶頸：**
1. 控制器逐個角色、逐個角點查詢碰撞：60 幀裡 `query_point` 被呼叫約 16 萬次，約佔一半時間。
2. 碰撞世界每幀重建約 3 次（AI、控制器、投射物各一次），每次逐個 entity 產生 Python 物件：每幀約 15 ms。
3. 場景 AI 逐個 entity 跑 Python 邏輯：每幀約 6 ms。

**決定（依量測）：** 這正是設計文件預留的情況，所以移動也要改成陣列運算。接著做 **A2-2**：控制器整批比對碰撞、同一幀共用碰撞世界；改完再量一次。

**狀態：** A2 完成，基準數字已記錄。

### D22-A2-2 — 移動和碰撞改成整批運算（依 A2 量測）

**改動的檔案：**
- `kernels`：`aabb_cross_pairs` 新增 `touching` 選項（邊緣相接也算），python 和 numpy 兩套都有，測試和暴力法比對。
- `runtime/character_control.py`：俯視控制器改成整批處理，先一次比對所有角色的 x 移動，再一次比對 y 移動。判定改成「角色的框和牆的框重疊」，原本是檢查四個角點，所以**比角色窄的牆也擋得住了**（原本會穿過去，這是修正）。圓形碰撞框用最近點精確判定。橫向控制器暫時維持逐個處理（A5 再改）。控制器可以使用外部提供的碰撞世界，移動後用 `move_shapes` 保持它是最新的，再留給後面的系統用。
- `runtime/collision.py`：`CollisionWorld.solid_columns()`（快取的陣列）、`move_shapes()`（如果有子物件掛在移動的父物件下，就標記 `stale` 要求重建）；`blocking_query` 不再每次都定義一個新的 class。
- `runtime/field_ai.py`：有控制器的角色不需要 blocking query，所以不再為它們建立碰撞世界。
- `runtime/projectiles.py`：碰牆判定改成整批。
- `runtime/game_session.py`：每幀只有控制器建一次碰撞世界，投射物沿用同一個。
- 測試：+2（比角色窄的牆擋得住；整批判定和逐個判定一致，共用的世界和重建的世界位置相同）、kernel `touching` 比對。

**執行的測試：** 完整套件 **2070 passed**。

**量測**（同一台機器，低耗電模式關閉，headless，120 幀，單位 ms；命中數都和 A2 相同）：

| 場景 | kernel | 每幀平均 | ai | collision | projectiles | combat |
|---|---|---|---|---|---|---|
| 300 敵 + 500 投射物（A2 前） | numpy | 42.8 | 6.9 | 29.3 | 9.1 | 1.3 |
| 300 敵 + 500 投射物（A2-2） | python | 27.0 | 2.6 | 15.3 | 9.4 | 1.2 |
| 300 敵 + 500 投射物（A2-2） | numpy | **18.2** | 2.7 | 11.8 | 3.9 | 1.2 |
| 200 敵 + 300 投射物 | numpy | 12.2 | 1.8 | 8.3 | 2.5 | 0.7 |
| 100 敵 + 150 投射物 | numpy | **5.9** | 0.9 | 3.8 | 1.3 | 0.3 |

**誠實說明：**
- 300 + 500 從 42.8 降到 18.2 ms，但**還沒達到 6 ms 的目標**。100 + 150 有達到。
- 剩下的時間不是算術，而是逐個 entity 的 Python 處理：每個系統各自掃描所有 entity（`scene.query`）、讀元件屬性、一個一個組陣列、每幀把碰撞框重建成 Python 物件。這些 numpy 和 C++ 都幫不上，因為資料本身是以 Python 物件逐個存放的。
- 要再大幅降低，需要改 ECS 核心的存放方式（熱門元件改成欄位陣列），這是大的架構變更，**需要你決定**。

**狀態：** A2-2 完成。

**使用者決定（2026-10-13）：** 照建議，先繼續 A3 之後的批次；ECS 核心改成欄位陣列存放的決定延到 A11，到時用 demo 的真實場景數字決定。期間不需要大改的優化可以順手做。

**使用者改變決定（2026-10-13）：** 核心存放方式先改，避免之後的系統要重做。A3 暫停，先做 C1、C2。

### D22-C1 — 核心改成欄位陣列存放

**改動的檔案：**
- `core/columns.py`（新）：`@column_storage`、欄位 descriptor、`ColumnTable`（以 slot 為索引的 `array.array` 欄位，記錄成員的 slots，成員變動時版本號遞增）。
- `core/component.py`：元件不在場景時，數值存在元件自己的 `_clocal`。
- `core/entity.py`：在場景中新增或移除元件時通知場景。
- `core/scene.py`：entity slot（移除後重複使用）、欄位表、各元件型別的索引（`query` 不再掃描所有 entity，順序仍是場景順序；`move_entity` 重排後重新編號）、`columns()`、`slot_of()`。
- 改用欄位存放的元件：Transform、Collider2D、CharacterController2D（含執行期欄位 intent、push、control_lock、facing_code 等）、Hitbox2D、Hurtbox2D。`facing` 對外仍是文字，存成 `facing_code`。

**相容性：** 專案檔、存檔、元件的屬性 API、Inspector、復原、prefab、跨場景攜帶的 entity 都不變，原有 2070 個測試未修改就全部通過。有一處行為更嚴格：數字欄位被設成文字時，會在設定當下就報錯；以前要到存檔時才報錯。

### D22-C2 — 系統直接讀寫欄位

**改動的檔案：**
- `kernels`（python、numpy 兩套，結果相同）：`collider_columns`、`box_columns`（判定框隨朝向轉）、`topdown_prepare`、`moved_boxes`、`add_to_column`、`decay_push`、`facing_codes`、`blocked_rows`（把候選配對向量化過濾：自己、單向平台、圖層、圓形）。
- `runtime/collision.py`：`CollisionWorld` 改成用欄位存放形狀，`ColliderShape` 物件要用時才產生；`from_scene` 直接從欄位建立；`move_shapes` 只更新數字。
- `runtime/character_control.py`：俯視控制器整段在欄位上跑，Python 只處理被擋住的少數角色；`box_rows()` 從欄位一次算出判定框；`HitboxSystem` 改用它，並把這一幀的受擊框留給投射物使用。
- `runtime/projectiles.py`：沿用 `HitboxSystem` 這一幀的受擊框。
- 圓形碰撞的判定在批次和逐個兩條路徑都改用 `sqrt`，兩邊完全一致。
- `validation/arpg_stress.py`：報告加入 `state_digest`（所有敵人和投射物的最終狀態）。
- 測試：`tests/test_column_storage.py`（新，11 項）涵蓋欄位讀寫、移出再加入、跨場景、序列化、slot 重複使用、查詢順序、更新中新增和移除、碰撞世界和逐個建立的結果相同、每個新 kernel python 等於 numpy，以及**整個壓力場景用 python 和 numpy 跑完，狀態完全相同**。

**執行的測試：** 完整套件 **2081 passed**。

**量測**（同一台機器，低耗電模式關閉，headless，120 幀，單位 ms）：

| 場景 | kernel | A2 前 | A2-2 | C2 | 
|---|---|---|---|---|
| 300 敵 + 500 投射物 | numpy | 42.8 | 18.2 | **15.0** |
| 300 敵 + 500 投射物 | python | 45.2 | 27.0 | 25.1 |
| 200 敵 + 300 投射物 | numpy | — | 12.2 | **10.0** |
| 100 敵 + 150 投射物 | numpy | — | 5.9 | **5.5** |

C2 之後 300 + 500 場景的拆解（numpy，每幀 ms）：場景 AI 5.1、俯視控制器 4.1、投射物 3.1、戰鬥結算 1.6、碰撞世界 1.3、判定框 1.2、行為樹 0.8。

**誠實說明：**
- 300 + 500 仍然沒有達到 6 ms。剩下的時間主要是：每個 numpy 呼叫都有固定的開銷（每次約 5–20 µs，一幀幾十次），加上還沒改的系統，最大的是場景 AI 的逐個 entity 判斷，約 5 ms。
- 場景 AI 在 A4 重寫敵人 AI 時，會直接用欄位方式做。
- 如果之後還要再大幅降低，下一步是把整個系統合成一次呼叫（C++ 或同等做法），這要等 A11 用量測決定。

**狀態：** C1、C2 完成。接著繼續 A3。

### D22-A3 — 玩家動作：技能、連段、閃避、冷卻和消耗、鎖定、即時狀態

**改動的檔案：**
- `gameplay/abilities.py`：`AbilityDefinition` 新增選填欄位 `timeline_id`、`cooldown_seconds`、`move_while_acting`（0 原地不動、1 照常移動、中間值放慢）、`interrupts_actions`（例如閃避，隨時可以打斷自己的動作）。回合制原本的欄位不變，舊資料照樣能讀。
- `gameplay/attacks.py`：`apply_states`（狀態、機率、持續秒數）。
- `gameplay/states.py`：`StateRuntime.has_active`（每幀檢查用，成本低）。
- `runtime/action_combat.py`（新）：
  - `ActionCombatComponent` 欄位：輸入綁定（`"attack=slash; dodge=roll"`）、輸入緩衝秒數、鎖定模式（off／manual／nearest）、鎖定範圍、鎖定和切換目標的輸入動作、瞄準方式（目標 → 搖桿 → 朝向）、開始時是否轉向。
  - `ActionCombatSystem.use()` 是玩家、行為樹、腳本共用的入口：在連段窗口內按同一個技能，接時間軸指定的下一段；在取消窗口內，或技能有 `interrupts_actions`，可以打斷目前的動作；其他時候先緩衝。冷卻以秒計算；消耗用公式算，從戰鬥資源扣；動作中的移動依 `move_while_acting` 縮放。每個結果都會發出事件（used、combo、buffered、denied 加原因、lock_on、lock_lost）。
- `runtime/entity_actions.py`：`play(..., aim, source)`；`movement` cue 新增 `relative`（world／facing／aim）和 `speed`（衝刺）；`projectile` cue 加上 `aim: true` 會沿瞄準方向射出。
- `runtime/character_control.py`：控制器新增欄位 `speed_override`（動作中的衝刺速度），python 和 numpy 兩套 kernel 都支援；`turn_with_facing`、`turn_with_aim`。
- `runtime/projectiles.py`：`fire_from` 接受世界方向 `direction`。
- `runtime/combat.py`：Combatant 新增 `regen`（每秒恢復，負值就是持續消耗）；狀態會即時計時（`StateRuntime`，週期效果可以致死）；攻擊命中時套用狀態；公式讀取的是套用狀態修正後的數值；新事件 state_applied、state_ended、state_unknown。
- `runtime/game_session.py`：場景系統加入 `action_combat`；新增 `set_field_input()`（A8 會把實際按鍵接上）；combat 改用專案的狀態表。
- `runtime/component_registry.py`：註冊 ActionCombat。
- 測試：`tests/test_action_combat.py`（新，11 項）。

**需求涵蓋（SPEC §20）：** Dash/dodge、I-frames、Combo chains、Cancel windows、Cooldowns/resources、Targeting/lock-on、Action timelines；加上即時狀態效果。

**執行的測試：** 完整套件 **2092 passed**。

**整合證據：**
- 測試場景和 `GameSession` 用的是同一組系統。
- 三連擊：第三下太早按，會被緩衝，等窗口打開才出。
- 閃避：往搖桿方向衝刺約 60 單位，期間站在敵人的判定框裡也不受傷；無敵結束後被打中；冷卻中再按會被拒絕。
- 消耗：MP 不夠時被拒絕，恢復後又能用。
- 取消窗口內可以換技能；原地不動的技能真的不會移動，可移動的技能會照常走。
- 鎖定背後的敵人後，箭會轉向射中它；切換到下一個目標；目標死亡時自動解除；再按一次就放開。
- 毒：每 0.5 秒扣血，最後致死；狂暴讓公式讀到加倍的攻擊力。
- `GameSession` 中，`set_field_input({"attack": 1})` 讓玩家用技能打中敵人。

**量測（numpy，300 + 500 壓力場景）：** 15.7 ms（C2 是 15.0 ms；兩次執行之間會有約 ±0.5 ms 的差異）。狀態檢查改成 `has_active` 之後，combat 回到 1.8 ms。

**還沒做：**
- 實際按鍵接上 PlayableTestRuntime、技能列和冷卻圖示：A8。
- 編輯器的技能和動作專用介面：A9。ActionCombat 元件已經會出現在 Inspector；技能的新欄位走技能紀錄原本的選填欄位機制。
- AI 使用技能（行為樹節點）：A4。

**狀態：** A3 完成。

**使用者決定（2026-10-13）：** A4 到 A8 一口氣做完（A4 敵人 AI、A5 橫向手感、A6 掉寶、A7 職業和技能樹、A8 遊戲整合和介面），做完再一起實機驗證戰鬥畫面。

### D22-A4 — 敵人和 Boss AI

**改動的檔案：**
- `kernels`（python、numpy 兩套結果相同）：`fieldai_step`，一次算出場景 AI 的偵測、放棄追擊、追擊、逃跑和回家。
- `runtime/field_ai.py`：FieldAI 改用欄位存放（`mode_code`、`home_x/y`、`started`）。有控制器的實體整批跑 kernel；巡邏、遊蕩和沒有控制器的實體照舊逐個處理。`state()` 對外的格式不變。目標不見時改成回家（以前會出錯）。
- `rpg/behavior_tree.py`、`runtime/behavior_tree.py`、`editor/behavior_tree_authoring.py`：
  - 新條件節點：`hp_below`、`hp_above`（Boss 分階段）、`ability_ready`、`has_state`、`acting`。
  - 新動作節點：`use_ability`（和玩家走同一個 `ActionCombatSystem.use`，瞄準玩家，可設定等動作結束）、`keep_distance`、`strafe`、`side_patrol`（橫向，遇到牆或平台邊緣就轉身）、`jump`、`summon`（召喚 prefab）、`apply_state`。
  - 編輯器的節點清單和參數表單都加上了。
- `runtime/character_control.py`：Hitbox2D v3 新增 `rehit_interval`，保持啟動時每隔幾秒可以再打中同一目標，用於接觸傷害或光束；0 維持原本「每次啟動只打一次」。
- `runtime/action_combat.py`：事件改成一發生就派送給 listeners。原本行為樹在 AI 階段呼叫 `use()` 發出的事件會被清掉，測試抓到這個 bug。
- `kernels/__init__.py`：第一次呼叫 `use()` 時也會回傳原本的 kernel 名稱（以前回傳 `None`）。
- `runtime/game_session.py`：行為樹接上 action_combat、combat、碰撞世界和召喚。
- 測試：`tests/test_enemy_ai.py`（新，12 項）。

**整合證據：**
- Boss 在 HP 50% 以上只用斬擊；HP 降到一半以下後改用帶霸體的重擊（傷害 20）。
- 弓手保持在 80 到 120 之間的距離，邊退邊射，玩家被射中。
- 繞圈移動，兩個方向都測過。
- 橫向巡邏：走到平台邊緣和牆就轉身，不會掉下去，也不會穿牆。
- 跳躍節點會讓角色離地。
- 召喚出 3 隻小怪；替自己加上狂暴狀態後，`has_state` 判斷成立。
- 接觸傷害：在第 0、0.5、1.0 秒各打中一次。
- 編輯器：新增 `use_ability` 節點並設定參數。
- 場景 AI 的混合場景用 python 和 numpy 跑完，結果完全相同。
- `GameSession` 中，行為樹控制的敵人追上玩家後咬到玩家。

**執行的測試：** 完整套件 **2104 passed**。

**量測（300 + 500 壓力場景，numpy）：** 13.8 ms（A3 是 15.7 ms）；ai 3.6 → 1.7 ms。

**狀態：** A4 完成。

### D22-A5 — 橫向手感

**改動的檔案：**
- `runtime/character_control.py`：控制器 v3 新增 `coyote_time`（走出平台後仍可起跳的時間）、`jump_buffer`（落地前先按跳會記住）、`jump_cut`（上升中放開跳，保留多少比例的上升速度，也就是短跳）、`drop_through`（下 + 跳穿過單向平台）、`climb_speed`（梯子）。執行期欄位：`jump_held`、`air_time`、`buffer_left`、`cut_armed`、`climbing`、`drop_left`。`PlayerInputSystem` 會設定 `jump_held`。橫向這一步重寫成：梯子、水平移動（遇到斜坡會往上踏）、跳躍判斷、重力、落地；走下坡時會貼著地面。**每個新選項的預設值都和原本行為相同**（0、0、1、False）。
- `runtime/collision.py`：Collider2D v3 新增形狀 `slope_right`、`slope_left`（框內一條斜線以下是實心），以及 `ladder`（可攀爬，永遠不擋路）。`ColliderShape.surface_y()`、`contains_point()`、`CollisionWorld.ladder_at()`；點查詢、地面偵測、落地接觸都考慮斜坡。
- 測試：`tests/test_side_view.py`（新，9 項）。

**整合證據：**
- 起跳寬限：寬限 0 時走出平台後按跳不會跳，寬限 0.15 秒時會跳。
- 跳躍記憶：落地前按跳，有記憶時會在落地後跳起來，沒有就不會。
- 短跳：按住 0.05 秒的高度不到按住 0.6 秒的 60%；`jump_cut` 等於 1 時兩者一樣高。
- 穿過單向平台：開啟時按下 + 跳會掉下去，關閉時則是正常起跳。
- 斜坡：走上 40 單位高的斜坡，再走回來，90 幀中有超過 80 幀貼地。測試抓到一個問題：原本下坡時每隔幾幀會飄起來，已改成用上一幀是否著地來判斷要不要貼地。
- 梯子：走過去不會被擋；按上可以爬，停住時不會掉；按跳會離開梯子。
- 舊版的控制器和碰撞框資料載入後行為不變。

**執行的測試：** 完整套件 **2113 passed**。

**還沒做：** 橫向的鏡頭預設（垂直死區、前瞻），會和 A8 的實機畫面一起做。橫向角色仍然是逐個處理，敵人多的橫向關卡如果量到瓶頸再改成欄位運算。

**狀態：** A5 完成。

### D22-A6 — 掉寶

**改動的檔案：**
- `rpg/loot.py`（新）：
  - `RarityDefinition` 欄位：名稱、顏色、詞綴數量範圍、擲骰權重、排序、前綴和後綴各自的上限。權重 0 的稀有度只能由掉落表指定，可用來做唯一裝備。專案沒有自訂時，用 `DEFAULT_RARITIES`。
  - `AffixDefinition` 欄位：位置（前綴、後綴，或作者自訂）、可出現的裝備標籤或欄位、物品等級範圍、權重、互斥群組、限定的稀有度，以及數值範圍（可設為整數、可隨物品等級成長）。
  - `RolledAffix` 會把擲出的數值存在自己身上，之後作者修改詞綴時，已經掉落的裝備不會跟著變。
  - `roll_rarity`、`roll_affixes`、`roll_equipment`、`item_display_name`。
- `rpg/items.py`：`EquippedItem` 新增 `item_level`、`rarity`、`rolled_affixes`。詞綴的數值經由原本的 `modifiers()` 計入角色數值；只在有設定時才寫入存檔，普通裝備的存檔內容和以前一樣。
- `rpg/resolved_build.py`：角色數值明細中，詞綴的來源標為 `affix`。
- `rpg/actors.py`：RPG 資料庫 v30 新增 `rarities`、`affixes`（v29 照樣能讀），加上 `loot_rarities()`。掉落表現在可以引用裝備。
- `rpg/drop_tables.py`：掉落項目的稀有度改成任何作者定義的 id，不再限定寫死的五種。
- `rpg/save_state.py`：存檔 v8 新增 `equipment_bag`（未裝備的裝備），v1 到 v7 照樣能讀。
- `runtime/loot.py`（新）：`LootComponent`（地上的物品、裝備、貨幣）、`LooterComponent`（撿取範圍；自動撿取規則：none、currency、items、all、rarity_at_least）、`LootSystem`（`drop` 灑出掉落物，裝備在掉落時就擲好；`pick_up_nearest`；拒絕撿取時東西留在地上；`labels()` 提供依稀有度上色的名稱）。
- `runtime/combat.py`：Combatant 新增 `currency_drop`（例如 `gold=5-12`）、`loot_level`（掉落裝備的物品等級）、`loot_luck`；死亡時的 drop 事件會帶上這些資料。
- `runtime/game_session.py`：combat 的 drop 事件會產生地上掉落物；撿到的東西放進存檔（貨幣、背包，背包滿了就留在地上，裝備放進 equipment_bag）。
- `editor/integrated_authoring.py`：新增「Loot Rarities」「Loot Affixes」紀錄分類。
- 既有測試：更新「最新版本號」的斷言（資料庫 29 → 30、存檔 7 → 8），舊版存檔測試多移除 `equipment_bag`，和過去每次升版的做法相同。
- 黃金基準：用 `scripts/update_golden_baselines.py` 更新。**只有** 4 個參考存檔和 RPG 資料庫的摘要改變，原因是存檔格式升到 v8（多了空的 `equipment_bag`）、資料庫升到 v30（多了空的 `rarities` 和 `affixes`）。Boss 戰的結果和黃金素材摘要都沒有改變。
- 測試：`tests/test_loot.py`（新，9 項）。

**整合證據：**
- 稀有度分布：擲 4000 次，平凡 70%、魔法 25%，誤差都在 3% 以內；幸運值 2 時遺物的數量變成兩倍以上；權重 0 的唯一裝備不會被擲出。
- 詞綴：遵守標籤、欄位、物品等級（第 10 級才會出現強化版）、互斥群組、前綴和後綴各 1 個的上限；數值有隨等級成長。
- 「Sharp Sword of the Bear」：攻擊 10 + 5（基礎）+ 7（詞綴）= 22、HP 115，存讀檔後相同。
- `GameSession` 中：敵人死亡 → 地上出現斧頭和 5 金幣 → 金幣自動撿起 → 按撿取拿到斧頭 → 斧頭進入 equipment_bag，物品等級 7 → 存檔 JSON 存讀後相同。
- 編輯器：新增稀有度和詞綴，修改後可以復原。

**執行的測試：** 完整套件 **2122 passed**。

**還沒做：** 格子背包（物品佔格子）。目前背包是清單，A8 的背包畫面也先用清單。

**狀態：** A6 完成。

### D22-A7 — 職業、等級和技能樹接上即時戰鬥

**做法：** 職業、等級、技能樹、裝備原本就有，而且回合制已經在用。A7 不另做一套，而是把它們接上即時戰鬥。

**改動的檔案：**
- `runtime/game_session.py`：
  - 掛有 ActorLink 的 entity，戰鬥數值、資源、標籤直接取自角色的 `resolve_actor_build`（職業、等級、技能樹、裝備、隨機詞綴都算在內）。
  - `refresh_combatant` 在重新計算數值時，保留目前的 HP 等資源和進行中的狀態；配點、換職業、裝備或卸下裝備、重置技能點、升級後都會自動重算。
  - 擊敗敵人時，由攻擊者對應的角色獲得經驗（`grant_actor_experience`，門檻和每級點數可在 `action_progression` 設定），升級紀錄在 `progression_events`。
  - `equip_from_bag` 從裝備袋裝上（會檢查裝備需求；被換下的放回袋子）、`unequip_to_bag`。
  - `reset_progression`：可以指定費用，退回全部或某棵技能樹的點數；按照依賴順序從末端開始退。
- `runtime/combat.py`：Combatant 新增 `experience`；死亡事件帶上經驗值。
- `runtime/action_combat.py`：`require_known`，只能使用角色已經學會的技能（`not_known` 會被拒絕）；冷卻可以用公式計算。
- `gameplay/abilities.py`：`cooldown_formula`（選填，依使用者的數值計算冷卻，例如技能等級越高冷卻越短）。
- `runtime/projectiles.py`：`projectile` cue 新增 `count_stat`，用某個數值增加投射物數量（例如技能等級）。
- **技能等級不另外做系統**：技能樹節點本來就能給數值（例如 `bolt_rank` +1），傷害、冷卻、消耗、數量的公式直接讀這個數值。作者可以自由決定每個技能怎麼隨等級成長。
- 測試：`tests/test_action_progression.py`（新，5 項，都在 `GameSession` 中，用參考專案的 hero_01 和 vanguard_tree）。

**整合證據：**
- 玩家的戰鬥數值等於角色的 build；配一點技能樹後，數值增加的量正好等於節點獎勵，且目前 HP 保持不變；重置後點數退回、數值回落；付不起費用時被拒絕。
- 擊敗 3 個敵人，經驗剛好在第三個跨過門檻而升一級、拿到 3 點技能點、數值重算；沒有連結角色的攻擊者不會給經驗。
- 從袋子裝上帶「power +25」詞綴的劍，戰鬥數值 +25；卸下後恢復，劍回到袋子。
- 技能等級 2：射出 1 + 2 = 3 發，每發傷害 10 × 2 = 20，冷卻 2 − 0.5 × 2 = 1 秒。
- 開啟 `require_known` 後，沒學過的技能被拒絕；關閉後就能用。

**執行的測試：** 完整套件 **2127 passed**。

**還沒做：** 開場選職業、技能樹、背包、技能列這些畫面在 A8。目前可以透過 `set_active_classes` 和 `allocate_progression` 這些 API 操作。

**狀態：** A7 完成。

### D22-A8 — 遊戲整合和畫面上的介面

**改動的檔案：**
- `runtime/action_play.py`（新）：
  - `CombatSceneComponent` 是場景設定，和環境設定一樣放在場景裡的任一 entity 上。欄位包括 `combat_mode`（`encounter` 是預設，維持碰到就進回合制；`action` 是即時戰鬥）、`view`（俯視／橫向）、`on_player_death`（重生或 game over）、重生延遲、重生時是否補滿、`draw_colliders`（畫出碰撞框，用於 block-out 關卡）、`camera_look_ahead`、`player_life_resource`、`background_color`。
  - `ARPG_ACTIONS` 是預設的動作按鍵，**只補專案輸入表裡沒有的**，不寫入專案。
  - `ActionHud` 畫出：頭上的敵人 HP、傷害數字、硬直和倒地文字、狀態名稱、受擊閃白、投射物、依稀有度上色的掉落物名稱（靠得近時會堆疊）、鎖定標記；畫面下方有生命和資源條（生命資源排第一）、等級和經驗條、技能列和冷卻遮罩、按鍵說明、升級提示、倒下後的重生倒數。
- `runtime/game_session.py`：`combat_scene`、`action_scene`；即時戰鬥場景會加入 `PlayerInputSystem`（輸入驅動玩家的控制器），碰到敵人不會進回合制；`prepare_action_player()` 會替玩家補上缺少的元件（控制器依場景視角、輸入、攻擊和受擊判定框、戰鬥數值、技能使用、撿取、連結第一位隊員），作者已經設定的不會被覆蓋；玩家倒下後鎖住操作、延遲後在起點重生並給短暫無敵，也可以設定成 game over。
- `runtime/combat.py`：`protected`，玩家死亡時永遠不會被移除或停用，只會倒下等待重生。
- `gameplay/attacks.py`：`damage_resource` 預設改成空字串，代表扣目標自己的生命資源。這是實機測試抓到的問題：參考專案的角色用的是 vitality 而不是 hp，原本敵人完全打不痛玩家。明確寫 hp 的舊資料行為不變。
- `runtime/playable_test_runtime.py`：即時戰鬥場景改走新的輸入路徑（移動、攻擊、閃避、技能、鎖定、撿取 F、背包 B、建構 C、暫停 Esc）、加上 HUD、背包畫面（依稀有度上色、物品等級、選中裝備的數值、Enter 裝備；不符需求時會說明原因）、game over；設有 `background_color` 時用單色背景。
- `validation/arpg_playground.py`、`scripts/arpg_playground.py`（新）：把參考專案的場景改成即時戰鬥場景，有三段連擊、閃避、追蹤火球、追擊的小怪、弓手、HP 一半以下會用霸體重擊的 Boss、掉落（金幣和隨機詞綴的劍）。`--side` 是橫向 block-out 關卡（地面、單向平台、斜坡、高台、梯子）。內容全部是一般專案資料，不是引擎程式。
- `scripts/arpg_live_check.py`（新）：在真實視窗跑上面的關卡，按鍵放進 pygame 的事件佇列（和實際按鍵走同一條路），在固定幀存截圖，並輸出 JSON 摘要。
- 測試：`tests/test_action_play.py`（新，5 項，透過 PlayableTestRuntime 送出按鍵事件）。

**實機驗證（Cocoa 真實視窗，1280×720，參考專案的真實素材）：** 截圖和摘要在 `docs/audits/evidence/real_machine/arpg_*`。
- **俯視**：660 幀，平均 55.4 fps；玩家使用技能 20 次（連擊、閃避、火球、鎖定），擊殺 3 隻（含 Boss），命中 5 次、被打 10 次，等級 12 → 13，金幣 +69（走過自動撿取）；地上有白色的「Blade」和藍色魔法等級的「Sharp Blade of the Bear」。
- **橫向**：320 幀，平均 55.2 fps；跳躍、短跳、攻擊；擊殺 1 隻；斜坡、梯子、單向平台、高台都正常顯示。
- 另外 78 個 A1–A8 的整合測試，用真實視窗模式在 Cocoa 重跑一次（709 幀）全部通過；那個模式使用 conftest 的單色替代圖。

**實機測試時發現並修正的問題：**
1. 參考專案的角色沒有 hp 資源，敵人打不痛玩家 → 攻擊預設扣目標的生命資源。
2. 敵人的圓點大小沒有乘上場景的世界縮放 → 改用每個世界單位實際的像素數。
3. 敵人每一下小攻擊都會打斷玩家的連擊 → playground 設定 `hitstun_rule = never`（暗黑式手感）和自動瞄準最近的敵人。兩者都是引擎原本就有的選項。
4. 參考專案原本回合制的 Boss 精靈站在競技場裡擋住玩家 → playground 停用場景裡的回合制遭遇。

**執行的測試：** 完整套件 **2132 passed**。

**量測（300 + 500 壓力場景，numpy）：** 13.4 ms。

**還沒做：**
- 橫向的玩家精靈目前沿用參考專案俯視角色的走路圖，比例偏大；A10 的 demo 會換成 Pixel Platformer 的橫向素材。
- 開場選職業畫面、技能樹專用畫面：目前用建構選單（C）配點和換職業；暗黑式技能樹畫面放在 A10 的 demo。
- 鏡頭的 `camera_look_ahead` 欄位已經有了，但還沒接到 field camera。
- 真實視窗約 55 fps，沒有到 60；瓶頸在既有的繪製（每幀縮放整張場景背景），留給 A11 量測。
- 格子背包。

**狀態：** A8 完成。A4 到 A8 都做完，需要使用者實際遊玩驗證。

**使用者指示（2026-10-13）：** 編輯器要做得更有質感、排版要更好；另外新增 lint 規則「每行少於 100 字元」，寫進 skill，整個專案都要遵守（在 A9 之後用獨立的 commit 處理）。

### D22-A9 — 編輯器：即時戰鬥工作區

**改動的檔案：**
- `editor/combat_authoring.py`（新，不依賴 Qt）：攻擊、投射物、掉寶稀有度、詞綴的新增、複製、刪除、套用，每次操作都是一個可復原的步驟。`KINDS` 描述每一類的區塊和欄位（標籤、元件種類、選項、說明），表單、預覽和測試共用同一份描述。`usage()` 列出紀錄被哪些地方使用。
- `editor/combat_workspace.py`（新）：Database 之下新增「Real-Time Combat」分頁。
  - **左側**：四個分類切換按鈕，有圖示、顏色和數量；搜尋框；紀錄清單（稀有度用它自己的顏色當圖示）；新增、複製、刪除按鈕。
  - **中間**：記錄名稱和 id，下面是有標題和說明的卡片（例如攻擊有：傷害、反應、霸體和倒地、狀態和事件），每張卡片依寬度排成多欄。專用的編輯元件：傷害公式（數值來源、屬性、係數，加上「屬性標籤倍率」表格處理弱點和抗性，可設上下限，並用文字顯示公式內容）、狀態表、詞綴數值表、顏色選擇器、圖層遮罩（十六進位）。
  - **右側即時預覽**（表單一改就重畫，還不必套用）：
    - 攻擊：攻擊者、目標和擊退箭頭（含角度、上挑），特性標籤（倒地、破霸體、韌性、元素），以及打擊停頓、硬直、倒地、無敵的時間條。
    - 投射物：用引擎的投射物 kernel 實際模擬飛行軌跡（重力、追蹤、追蹤範圍圈），附射程、碰牆、穿透、使用的攻擊。
    - 稀有度：名稱分別在深色和淺色背景上的顏色（淺色背景加描邊）、詞綴數量、在所有稀有度中被擲到的比例條。
    - 詞綴：裝備名稱示範，以及每條數值在最低和最高物品等級的範圍條。
  - **空狀態**：沒有任何紀錄時，顯示說明和一個大的「New …」按鈕，不顯示空表單。
  - 不合法的值會在下方即時說明原因（例如「詞綴下限大於上限」），套用按鈕用綠色、刪除用紅色。
- `editor/theme.py`：新增卡片、紀錄標題、分類按鈕、預覽框、標籤的樣式；三種配色都適用。
- `editor/collision_overlay.py`、`editor/viewport_widget.py`：場景檢視會畫出碰撞框（實心、單向平台虛線、斜坡三角形、梯子、觸發區）、受擊框（綠）、攻擊框（紅色虛線，會跟著朝向）。
- `editor/problems.py`、`editor/shell.py`：Problems 新增「Real-Time Combat」檢查。錯誤包括：攻擊引用不存在的共用公式或狀態、投射物引用不存在的攻擊、時間軸的投射物或連段目標不存在、技能的時間軸不存在、行為樹的技能、狀態或 prefab 不存在、輸入綁定到不存在的技能、掉落表不存在。警告包括：判定框的 hit tag 不是任何攻擊（打中但不會造成傷害）、生命資源不在資源清單裡（永遠不會死）。點兩下可以跳到即時戰鬥工作區的那一筆紀錄、行為樹或場景 entity。
- `editor/decor.py`：分頁圖示規則。
- `scripts/editor_ui_audit.py`：每個即時戰鬥分類都是一個檢查畫面；新增 `--project`，可以用指定的專案檢查。
- 測試：`tests/test_editor_combat_workspace.py`（新，4 項）；`test_editor_shell_integration_154a` 的分頁清單加上新分頁。

**Cocoa 實機 UI 檢查（`scripts/editor_ui_audit.py`，1600×1000，dpr 2）：**
- 參考專案沒有任何即時戰鬥紀錄（只會看到空狀態）：4 個畫面都是 **0 個問題**。
- 用加入 playground 內容的專案（6 個攻擊、2 個投射物、5 個稀有度、2 個詞綴）檢查：一開始有被裁切的表頭、被擠扁的欄位、整頁捲動，修正後 **clipped、overflow、tiny 都是 0**。剩下的只有攻擊和投射物這兩類的卡片區塊會在自己的範圍內捲動（攻擊有 4 張卡片），這是刻意的，整個頁面本身不會捲動。截圖在 `docs/audits/evidence/ui_audit/a9_combat_*.png`。

**執行的測試：** 完整套件 **2136 passed**。

**狀態：** A9 完成。

### D22-L1 — Lint 規則：每行少於 100 字元（使用者指示）

**規則：** repo 裡所有 Python 檔案（src、tests、scripts、reference_projects、demos；第三方的 local_reference 除外），每行最多 99 個字元。寫在 `.claude/skills/line-length/SKILL.md`，內容包括規則、提交前的三個檢查指令、各種寫法的處理方式，以及不在範圍內的部分（Markdown 文件和 JSON 資料不會被 ruff 檢查）。

**做法：**
- `pyproject.toml`：`line-length` 從 120 改成 99。
- `ruff format` 重新排版程式碼（540 個檔案）。
- 剩下 formatter 不會處理的 992 行，用一次性的 token 層級腳本改寫：註解換行（行尾註解移到上一行）；字串字面值拆成相鄰的字面值，值完全不變（f-string 只在 `{…}` 外面拆）；多行字串和 docstring 在空白處換行；太長的單行 docstring 拆成兩行文字。
- 最後 4 行手動改：拆成區域變數、改用 `any()`、測試函式名稱縮短。
- 改寫後有 9 個測試失敗：GLSL shader 字串中一行 `//` 註解被拆開，後半段變成程式碼，GPU 效果因此編譯失敗。已改成註解獨立一行，並在 skill 中寫明「是程式碼或資料的字串不能在中間換行」。
- 這次只有格式變動，沒有改任何行為。

**結果：**
- `ruff check --select E501 .`：整個 repo **0 個問題**。
- `ruff check src tests scripts`：全部規則都通過。
- 完整套件 **2136 passed**，黃金基準沒有改變。
- `demos/` 和 `reference_projects/` 原本就有其他規則的問題（例如 lambda 指派、import 位置），在這次之前就存在、以前也不在 lint 範圍內；這次沒有處理，數量從 115 個降到 47 個。

### D22-A10 — ARPG demo 專案（暗黑式範例，系統全部通用）

**Demo 專案 `reference_projects/diablo_demo/`**（`build_project.py` 產生，可重跑；`art.py` 切素材、`maps.py` 用程式排地圖；README 說明每條規則在資料的哪裡）：
- **城鎮 Hollowbrook**（俯視）：商人（收購怪物素材、賣藥水）、鐵匠（用素材合成藥水）、戰士／遊俠／法師三位導師（對話後用 `SET_CLASSES` 換職業）、長老（給藥水）、村民；往東的道路傳送到野外。
- **野外 Greenvale Fields**（俯視）：史萊姆（近戰）、會射擊的眼怪、骷髏精英小隊（霸體、倒地、掉寶加成）、獨眼巨人 Boss（HP 一半以下改用霸體重擊、會丟石頭）。
- **礦坑 Rustdeep Mine**（橫向，Kenney Pixel Platformer）：起伏地形、單向平台、木橋、梯子通往高處走道、爬行怪、蝙蝠（無重力）、無人機（遠程）、岩石魔像 Boss。
- **職業與技能樹**：初始是「冒險者」（只會揮拳）；戰士、遊俠、法師各有一棵技能樹（7 個節點，含技能和數值），另有共用的「屬性」樹；每升一級得 2 點。
- **同一套按鍵適用所有職業**：`attack=w_slash|r_shot|m_bolt|punch`，用第一個已學會的技能。
- **掉寶**：Common／Magic／Rare／Legendary 隨機詞綴（前後綴數量依稀有度限制）、三件套「Wanderer's Path」、三件傳奇（Unique）、金幣、合成素材。
- **藥水**是背包道具，由技能消耗（`item:potion`）。
- 美術全部 CC0（Ninja Adventure、Kenney），`playable_assets/CREDITS.md`；沒有 AI 生成的圖。

**為了 demo 加入的通用引擎功能（任何遊戲都能用）：**
- `runtime/tile_scene_view.py`（新）：PlayableTestRuntime 可以直接玩 TileMap 場景。
  - 角色下方和上方的圖層各預先畫一次，每幀只縮放畫面看得到的部分（最近鄰縮放）。
  - 有 SpriteRenderer2D 的 entity 依深度排序、畫在自己的位置；有 Animator2D 而且動畫組有四方向 `idle_*`／`walk_*` 的，依移動和朝向播放，執行動作時間軸時播 `attack_*`。
  - 鏡頭跟隨玩家，不超出地圖邊界；投射物有 sprite 時依飛行方向旋轉畫出。
- `GameSession.set_tile_blocking()`：地圖的碰撞圖層和地圖邊界會擋住角色控制器、場上 AI、投射物（`ProjectileSystem.tiles`）。
- 按鍵綁定的替代寫法 `a|b|c`：`ActionCombatSystem.bound_ability()` 選第一個已學會的；HUD 技能列和 Problems 檢查都支援。
- 世界指令 `SET_CLASSES`（`actor_id`、`class_ids`、`unlock`）和 `GameSession.set_classes()`。
- `runtime/skill_tree_screen.py`（新）：即時戰鬥場景按 C 開啟技能樹畫面。顯示目前職業的樹（標記 `class:<id>` 或名稱為 `<id>_tree`）和共用樹（`shared`）；方向鍵選節點、Enter 學習、O 切換樹；右側顯示等級、下一級的花費和獎勵、已得到的獎勵、前置條件；不能學時說明原因。
- 技能消耗 `item:<道具id>`：由隊伍背包支付（藥水、箭矢、炸彈），技能列顯示剩餘數量。
- hitbox cue 可以帶 `width`／`height`／`offset_x`／`offset_y`，在 cue 期間改變攻擊範圍（旋風斬、新星），結束、取消或被換掉時還原。
- gameplay_event cue 可以帶 `apply_state`（和 `duration`），把狀態加在使用者身上（戰吼、喝藥水回血）。
- 裝備標記 `rarity:<id>` 會固定稀有度（傳奇、套裝、任務獎勵）。
- `item_display_name(..., brief=True)`：地上和清單只顯示第一個前綴和第一個後綴，詳細數值在背包右側。
- HUD：玩家的生命條從一開始就顯示；技能列不再蓋到左側的生命面板；三個字以內的資源名稱顯示成大寫（HP、MP）；在 tile 場景中，有自己 sprite 的 entity 不再畫圓點替代。
- `CombatScene.background_color` 也套用在 tile 場景（礦坑的黑暗）。
- 標題畫面的副標題改用 manifest 的 `subtitle`（沒有設定時維持原本的文字）。
- `scripts/editor_ui_audit.py`：和「開啟專案」一樣先載入素材，tile map 才會畫在場景檢視裡（原本的稽核漏了這一步）。
- `scripts/arpg_demo_live_check.py`（新）：真實視窗的腳本化遊玩（導師→技能樹→野外→Boss→礦坑→背包）。
- 測試：`tests/test_arpg_demo.py`（新，12 項）。

**實機驗證（Cocoa 真實視窗，1280×720）：** 證據在 `docs/audits/evidence/real_machine/arpg_demo_*`。
| 職業 | 幀數 | 平均 fps | p95 | 使用的技能 | 擊殺 | 等級 | 撿到裝備 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 戰士 | 1478 | 55.5 | 18.0 ms | 連擊 85、旋風斬、跳斬、翻滾、藥水 | 3 | 4 | 1 |
| 遊俠 | 1486 | 55.5 | 18.0 ms | 射擊 69、齊射、穿透箭、翻滾、藥水 | 3 | 4 | 2 |
| 法師 | 1478 | 55.5 | 18.0 ms | 火球 46、隕石、翻滾、藥水 | 6 | 4 | 1 |

腳本會直接把玩家移到導師、Boss、地上的裝備旁邊（不是走過去），並直接給經驗值來測技能樹；這些只是測試捷徑，不是遊戲內容。

**編輯器（Cocoa，1600×1000，dpr 2）：** 用 demo 專案跑 `editor_ui_audit` 的全部畫面：只有 1 個問題，Enemy AI 的「Add Rule…」按鈕被裁切 7 px，用參考專案也會出現，不是這次造成的；其餘都是頁面內捲動的提示。場景檢視會畫出城鎮的 tile map 和碰撞格（`docs/audits/evidence/ui_audit/a10_editor_*.png`）。

**實機測試時發現並修正的問題：**
1. 一開始 HUD 沒有生命條（狀態要等第一次被打才建立）→ HUD 會先建立狀態。
2. Kenney 地形選錯格：「單獨方塊」和「左邊緣」被當成中間格，地面出現接縫 → 改用左／中／右三欄，填充改用沒有外框的格子。
3. 傳奇裝備的名稱串了五個後綴 → 稀有度限制前後綴數量，名稱只顯示一個前綴和一個後綴。
4. 技能樹先顯示共用的「屬性」樹 → 職業的樹排在前面；不能學的原因改用節點名稱，不顯示 id。
5. HUD 的圓點畫在有 sprite 的敵人身上 → tile 場景中不再畫。
6. 編輯器的 Map、Camera、Combat Scene 三個 entity 都在原點，標籤疊在一起 → 放在地圖外分開。

**執行的測試：** 完整套件 **2147 passed、1 skipped**。被略過的是 `test_record_operations_gui.py:76`，在視窗沒有鍵盤焦點時會略過（當時有 Cocoa 視窗開著），和 A10 無關。ruff E501 和全部規則都是 0 個問題。

**還沒做：**
- 背包仍是 A8 的清單畫面，不是暗黑式的格子背包；也還沒有裝備比較的提示框。
- 玩家的外觀不會隨職業改變（ClassDefinition 沒有外觀欄位），三種職業共用同一張角色圖。
- `camera_look_ahead` 還沒接到 tile 場景的鏡頭。
- 礦坑的背景只有單色，沒有視差背景圖層。
- 數值平衡只做了大概：例如法師的 MP 消耗得很快。
- 真實視窗約 55.5 fps（`clock.tick(60)` 加上垂直同步）；A11 會量測並決定下一步。

**狀態：** A10 完成，需要使用者實際遊玩驗證手感和平衡。

### D22-A11 — 收尾量測和下一步的決定

**量測一：引擎壓力場景（無畫面，`scripts/arpg_stress.py`，300 幀）**
| 場景 | kernel | 每幀平均 | p95 | AI | 碰撞 | 投射物 | 戰鬥 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 100 敵 + 150 投射物 | python | 7.5 ms | 8.1 ms | 0.85 | 4.24 | 2.33 | 0.47 |
| 100 敵 + 150 投射物 | numpy | 5.1 ms | 5.6 ms | 0.67 | 3.16 | 1.13 | 0.48 |
| 300 敵 + 500 投射物 | python | 25.3 ms | 27.7 ms | 2.79 | 13.25 | 8.52 | 1.97 |
| 300 敵 + 500 投射物 | numpy | 14.9 ms | 17.7 ms | 1.80 | 8.88 | 3.46 | 2.05 |

**量測二：ARPG demo 真實視窗（Cocoa，1280×720，不限幀，`scripts/arpg_demo_measure.py`）**，玩家站在野外中央持續射擊；證據在 `docs/audits/evidence/real_machine/a11_measure_*.json`。
| 敵人數 | kernel | 整幀平均 | p95 | 模擬 | 繪製 | 送出畫面 | 不限幀 fps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | python | 8.33 ms | 8.66 ms | 0.33 | 3.82 | 4.06 | 120.0 |
| 170 | python | 8.47 ms | 9.46 ms | 1.81 | 5.34 | 1.13 | 118.1 |
| 20 | numpy | 8.35 ms | 8.69 ms | 0.42 | 3.84 | 3.97 | 119.8 |
| 170 | numpy | 8.51 ms | 9.53 ms | 1.84 | 5.35 | 1.11 | 117.6 |

不限幀時一幀是 8.3 ms，剛好是這台 Mac 120 Hz 螢幕的垂直同步；「送出畫面」那一段大部分是在等垂直同步。真正的工作量是模擬加繪製，170 隻敵人時約 7 ms，60 fps 的預算是 16.7 ms。

**發現的問題：A8 到 A10 看到的「約 55 fps」不是負載造成的。** `pygame.Clock.tick(60)` 以整毫秒等待，等完之後 `present()` 又要等下一次 120 Hz 的垂直同步，所以每幀落在約 18 ms。
- 修正：`PlayableTestRuntime.tick()` 依固定的截止時間排程（先 sleep，最後一點時間用短暫空轉），每次只往後推一個週期；落後超過一個週期時重新開始排程，不會為了追進度連跑好幾幀。`run()` 和兩個實機檢查腳本都改用它。
- 結果：真實視窗 ARPG demo（遊俠，1486 幀）**60.0 fps，p95 16.8 ms**（原本 55.5 fps、18.0 ms）。證據：`a11_live_ranger_limiter_summary.json`。
- 測試：`tests/test_frame_limiter.py`（新）。

**決定：**
1. **不提 C++ 提案。** demo 規模（數十到一兩百隻敵人）在 python kernel 下模擬也只要 0.3–1.8 ms；最吃時間的是繪製，不是 ECS 或運算。
2. **numpy 維持現在的範圍，不擴大。** 在 demo 規模下 numpy 和 python 幾乎一樣（陣列轉換的成本抵消了好處）；只有幾百個敵人加幾百個投射物時才有明顯差距（25.3 → 14.9 ms）。預設仍然由 `ASTERIA_KERNELS` 選擇。
3. **ECS 核心（欄位存放）不需要再改。**
4. 如果之後的遊戲要同時有 300 個以上活動中的敵人，依量測結果優先處理：
   - (a) 碰撞：角色移動時逐個 entity 檢查，numpy 下仍要 8.9 ms。
   - (b) 繪製：tile 圖層每幀重新縮放。可以依縮放倍率快取放大後的圖層，或交給已有的 ModernGL 後端。
   - 到那時再重新量測，才考慮把這兩段寫成 C++。

**執行的測試：** 完整套件 **2148 passed、1 skipped**（略過的和 A10 相同）。

**狀態：** A11 完成，D22 的 A1–A11 全部完成。需要使用者實際遊玩 demo，確認手感和平衡。

### D23-1 — 原生（C++）kernel：架構和第一個切片（使用者指示：核心用 C++ 一次做完）

**架構：**
- `kernels/native/asteria_kernels.cpp`：純 C 介面，吃原始欄位緩衝區；`kernels/_native.py` 用 `ctypes` 載入，不需要 pybind11 或 cmake。`native` 這組 kernel 以 numpy 組為底，只覆蓋已移植的函式，所以介面永遠完整，可以逐個移植。
- `python -m asteria.kernels.build_native` 用系統的 clang++／g++ 編譯；旗標 `-ffp-contract=off -fno-fast-math`，與 python 參考版逐位元一致。沒編譯或載入失敗時，`kernels.available()` 自動略過，引擎維持用 numpy。`ASTERIA_KERNELS=native` 可指定。
- 輸出大小不定的函式用「呼叫端提供緩衝區、回傳需要的數量、不夠就重試」。

**第一個切片：`aabb_cross_pairs`。** 400 組隨機箱子（含邊緣相接、零寬度、負座標、全部互相重疊）與 python 參考版 **0 個不一致**；500 × 2000 個箱子 0.62 ms（numpy）→ 0.28 ms（native）。測試：`tests/test_native_kernels.py`。

**量到的問題：這個切片對壓力場景沒有任何效果**（300 敵 + 500 投射物：numpy 15.3 ms，native 15.4 ms）。cProfile（120 幀，numpy）：
- 時間花在 Python 物件迴圈，不在 kernel：`list.append` 85.9 萬次 0.83 s、`CollisionWorld.from_scene` 與 `_add` 合計約 1.3 s、`field_ai.update` 約 1.2 s、`Scene.query` 7.3 萬次。
- `aabb_cross_pairs` 整體只有 0.26 s（約 5%）。
- 結論：把現有 kernel 一個一個換成 C++ 的上限很低。要有效益，C++ 必須接手「每幀逐個 entity 的迴圈」：由欄位直接建出碰撞世界、AI 步進、命中收集，而不是只加速被呼叫的陣列函式。

### D23-2 — 所有現有 kernel 移到 C++（使用者決定：kernel 用 C++，其餘維持 Python，使用者照樣用程式碼寫玩法）

**做法：** `kernels/native/asteria_kernels.cpp` 包含全部 kernel；`kernels/_native.py` 用 `ctypes` 載入。已移植：`aabb_pairs`、`aabb_cross_pairs`、`ParticleStore.step`、`WeatherStore.step`、`ProjectileStore.step`、`collider_columns`、`topdown_prepare`、`moved_boxes`、`add_to_column`、`decay_push`、`box_columns`、`blocked_rows`、`facing_codes`、`fieldai_step`。天氣的 `draw`、粒子的 `views`、`ProjectileStore` 的存取方法仍是 numpy／Python（不是熱迴圈，或依賴 pygame）。
- 欄位是 `array.array`，C++ 直接讀寫同一塊記憶體（和 numpy 版一樣零拷貝）；每個函式先檢查欄位型別，不符就退回 numpy 版。
- 運算順序和 python 參考版完全相同，編譯旗標 `-ffp-contract=off -fno-fast-math`。轉向用的 cos／sin 仍由 Python 先算好傳入。
- `auto` 的順序變成 native → numpy → python；沒編譯就略過 native。`ASTERIA_KERNELS=native|numpy|python` 可指定。
- 編譯：`python -m asteria.kernels.build_native`（只需要系統的 clang++／g++）。編譯出的 `.dylib/.so/.dll` 不進版控。

**驗證：**
- `tests/test_native_kernels.py`（9 項）：每個函式用隨機資料和 python 參考版比對，包含原地被改寫的欄位（鎖定倒數、跳躍旗標、推力衰減、AI 模式和意圖、NaN 目標、被取消的追蹤等），要求完全相等。
- 完整套件在 native 下 **2164 passed、1 skipped**（黃金基準沒有改變）。
- 三組 kernel 在壓力場景的命中數完全一致。
- 寫的時候抓到兩個 bug：暫存陣列在 C 呼叫前就被回收（指標懸空）、兩個函式的 `argtypes` 少算一個指標。兩者都靠新測試發現並修正。

**量測（無畫面壓力場景，每幀平均）：**
| 場景 | python | numpy | native | native 對 numpy |
| --- | --- | --- | --- | --- |
| 100 敵 + 150 投射物 | 7.6 ms | 5.1 ms | 4.0 ms | −23% |
| 300 敵 + 500 投射物 | 25.7 ms | 14.5 ms | 11.6 ms | −20% |
| 1000 敵 + 800 投射物 | 87.2 ms | 56.7 ms | 46.6 ms | −18% |

**這是預期內的結果，不是 C++ 的上限：** 剩下的時間在 Python 逐物件的迴圈（碰撞世界每幀重建、AI 的 Python 部分、戰鬥結算）。碰撞在 1000 敵時 numpy 38.1 → native 28.1 ms，其中 `CollisionWorld.from_scene` 仍是 Python。再要提升，下一步是把這個迴圈接到欄位，這會碰到系統層，不屬於這次「只換 kernel」的範圍。

**狀態：** D23 完成。

### D23-3 — 大場面量測：全螢幕技能、很多怪和很多角色同時施放（使用者提問）

**場面（Cocoa 真實視窗，1280×720，demo 的野外）：** 玩家每 0.3 秒放一次「全螢幕」的新星（攻擊框 1400 × 800，打到畫面上每一隻）；另有 N 隻會射擊的怪（代表其他玩家或怪物同時施放技能）；每次施放再播 M 個特效、射出 K 支箭。傷害數字、狀態文字、掉落標籤、血條都照常顯示。腳本：`/tmp` 的一次性腳本，場面數字記在下表，截圖 `d23_fullscreen_skill_load.png`。

**第一次量測發現的問題（都是我自己加的）：**
1. 傷害數字、掉落標籤、HUD 文字每幀重新渲染（17 萬次 `font.render`，剖析中佔 3 秒）。→ 文字渲染加上快取（`PlayableTestRuntime.text` 和 `ActionHud._label`）。
2. `tile_view` 每次被呼叫都掃描整個場景的 entity（被每個 entity 的座標轉換呼叫，3200 萬次迭代）。→ 每個場景只查一次。
3. 場上特效（`PLAY_VFX` 的精靈和粒子）用的是舊鏡頭，在 tile 場景會畫在錯的位置，粒子大小也差 3 倍。→ 改用目前場景的座標轉換和比例。測試：`test_particle_effects_and_text_use_the_tile_scenes_camera_and_are_cached`。

**修正前後（每幀平均 / p95）：**
| 怪 | 施放者 | 特效／次 | 箭／次 | 浮動文字 | 粒子 | 修正前 | 修正後 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | 2 | 0 | 14.1 / 16.1 ms | 8.4 / 9.0 ms |
| 40 | 10 | 6 | 20 | 115 | 462 | 17.1 / 18.5 ms | 8.3 / 9.3 ms |
| 80 | 20 | 10 | 40 | 224 | 731 | 21.2 / 22.9 ms | 8.5 / 9.3 ms |
| 150 | 40 | 20 | 80 | 459 | 1557 | 30.3 / 32.8 ms | 11.5 / 12.7 ms |

8.3 ms 是這台螢幕 120 Hz 垂直同步的底線。即使 150 隻怪、40 個施放者、每次 20 個特效、80 支箭、459 個浮動文字，也在 60 fps 的預算（16.7 ms）內。

**還沒量到的：** 每個角色用大張的多格動畫序列（不是我們現在每個角色只換一格）、全螢幕的光暈疊加（GPU 後端的填充率問題）、真正的多人連線（網路和同步不在引擎範圍內）。

**執行的測試：** 完整套件 **2166 passed**。

### D23-4 — 編輯器：即時戰鬥工作區左下角按鈕被擠壓、自動完成清單漂浮（使用者回報）

- **按鈕被截斷**（「ew Affix」「uplicate」）：左欄變窄時，三個並排按鈕放不下加了圖示的長標籤。→ 改成兩列：「New」整列寬、「Duplicate」和「Delete」各佔一半；標籤縮短（完整名稱放在提示文字）；左欄最小寬度 240。用 1000／1280／1600 寬度驗證，標籤都完整顯示。
- **漂浮的 `entities / entity / entity_named` 清單**：Code 工作區的自動完成清單在切換到別的工作區時沒有收起來。→ 工作區被隱藏時關閉清單（`hideEvent`）。實際重現後確認：修正前清單仍然可見，修正後隱藏。
- 這兩個問題之前的 UI 稽核沒抓到：稽核用 1600 寬，窗口夠寬；清單只在輸入程式碼後出現。稽核腳本之後可加入較窄的視窗尺寸。
- 測試：`tests/test_editor_combat_workspace.py` 新增 1 項。

### D23-5 — 存檔往返、擊敗記憶、大地圖區塊繪製（「全部處理」第一批）

**1. 存檔和讀檔完整往返**（`tests/test_arpg_save_load.py`，3 項）：玩一段（換職業、經驗和升級、技能樹配點、背包和穿戴的隨機裝備、藥水、金幣、換場景和朝向）→ 存檔 → 關閉 → 載入 → 全部比對。職業、技能等級、點數、裝備的稀有度和詞綴、背包、穿戴、金幣、場景、座標都一致。抓到並修正 1 個 bug：
- 傳送門指定的朝向在即時戰鬥場景被忽略（玩家控制器有自己的朝向，`set_player_facing` 沒有同步），存檔的朝向因此也是錯的。→ `set_player_facing` 同步控制器，載入存檔時也同步。
- 橫向場景的存檔載入後仍在該場景、站在地上、位置一致。

**2. 擊敗後不會復活**：`CombatantComponent.defeat_switch`（通用欄位）。被擊敗時寫入存檔的開關；之後進入場景時，開關為開的 entity 不會出現。demo 的 Bone Champion、Gorgoth、Rust Golem 使用它。測試：擊敗 Boss → 存檔 → 載入，Boss 不在，其他怪都在。

**3. 大地圖**：`TileSceneView` 不再把整張地圖預先畫成兩張大圖，改成一個區塊一個區塊畫，第一次看到時才渲染，放在上限 192 個區塊的快取裡（約 50 MB）。
- 一張 640 × 640 格（10240 px 見方，預先畫的話約 400 MB）的地圖：載入加三幀不到 0.5 秒；沿著地圖走 40 步，快取大小維持在上限內；邊界牆和可走區域正確。
- 地圖範圍改成依區塊計算，不再逐格掃描。
- 牆壁查詢（`MapBlocking`）載入時只挑出一次碰撞圖層，每次查詢是幾次字典存取。
- 測試：`test_a_huge_map_costs_only_what_the_camera_sees`。

**4. 試過但沒有效果、已還原：** 把 `CollisionWorld.from_scene` 的逐個 `_add` 改成整批建列。壓力場景（300 敵 + 500 投射物，native）12.4 ms，和之前相同。剖析顯示時間在逐個 collider 的場景走訪（檢查啟用狀態、排序），不在 `append`。要真的改善，需要場景層級的快取和失效機制，這會碰到「entity 啟用狀態改變不通知場景」的既有設計，風險大於收益，沒有做。

**執行的測試：** 完整套件 **2171 passed**。

### D23-6 — demo 缺口：格子背包、職業外觀、鏡頭前瞻、視差背景、法師平衡（「全部處理」第二批）

**1. 格子背包（`runtime/bag_screen.py`，新）：** 取代 A8 的清單。上方是穿戴格（依裝備欄位），下方 8 欄的格子；稀有度顏色的外框和底色、裝備圖示（`icon_id`）。方向鍵移動、Enter 穿上或脫下、B／Esc 關閉；從背包第一列往上進穿戴格。右側提示框：名稱（稀有度顏色）、稀有度、物品等級、欄位；每項數值，和**同欄位目前穿的那件比較**（括號內為差值，綠色較好、紅色較差）；詞綴名稱；所屬套裝、已穿件數和各件數的加成（達到的用綠色）。需求不符時說明原因。新增 `EquipmentLoadout.slot_ids()`。測試：`test_the_bag_grid_compares_stats_equips_unequips_and_shows_the_set`。截圖 `d23_bag_grid.png`。
- 圖示是 Kenney Tiny Dungeon（CC0）和 Ninja Adventure 的物品圖，切成 16 px 存在 `playable_assets/icons/`，`CREDITS.md` 已補上。

**2. 職業外觀：** 通用元件 `asteria.ClassAppearance`（`looks`：`class_id=sprite_sheet|animation_set; ...`）。連結的角色顯示目前職業的外觀（最後一個有設定的職業勝出），換職業時立刻換。TileSceneView 在動畫狀態上也跟著換動畫組。demo 的三個職業各有自己的角色圖。測試：`test_class_looks_swap_with_the_class_and_the_camera_looks_ahead`。

**3. 鏡頭前瞻：** `CombatScene.camera_look_ahead`（世界單位）現在接到 tile 場景的鏡頭：鏡頭緩緩偏向玩家面對的方向，橫向場景只往左右。demo 俯視 36、橫向 48。測試同上（面向右時鏡頭中心在玩家右側 20 以上，面向左則在左側）。

**4. 視差背景：** 通用元件 `asteria.ParallaxBackground2D`（貼圖、`factor_x`／`factor_y`、縮放、錨點、可重複、透明度）。在 tile 圖層之下，依 factor 由遠到近畫。礦坑有兩層洞穴剪影（0.12 和 0.3）。測試真的量位移：每一層單獨畫兩次，內容左移的像素數正好是 `factor × 鏡頭移動 × 縮放`（36 和 90 px）。截圖 `d23_mine_parallax_mage.png`。

**5. 法師平衡：** 火球消耗 2 → 1 並加 0.35 秒冷卻，英雄 MP 回復 3 → 4／秒。原本連續施放約 30 秒就耗盡 110 MP（實機量到 MP 1/110）。

**執行的測試：** 見下一批的完整套件。

### D23-7 — 編輯器窄視窗、地圖編輯、lint、說明文件、補量測（「全部處理」第三批）

**1. 編輯器在窄視窗（稽核新增 `--also` 可一次跑多種大小）：** 1100×700 用 demo 專案一開始有 8 個裁切或橫向捲動，修正後 1600×1000、1280×800、1100×700 三種大小，demo 專案和參考專案都是 **0 個裁切／溢出／過小**。
- 即時戰鬥工作區：左欄動作改成「New」整列、「Duplicate」「Delete」各半（你回報的問題）；視窗窄於 1000 時右側預覽自動收起（標題列的「Preview」開關可手動打開，手動選擇會保留）；預覽最小寬度 300 → 190；頁面最小寬度原本寫死 940，改成三個面板的真實最小值 816。
- Enemy AI：規則詳細面板窄時上下堆疊（放在可捲動區），按鈕依文字寬度保底，表格欄寬上限 140、被省略的字在提示文字裡；下拉選單依最長項目寬度顯示（新增 `editor/ui_fit.py`）。
- 事件流程：「+ Condition」「− Condition」移到自己的一行。
- 角色組合：長 id 的下拉選單不再被截斷。VFX 編輯器：預覽最小寬度 320 → 220。
- Code 工作區的自動完成清單切換工作區時會收起（上一批）。
- 還在的：Enemy AI 的七欄規則表在窄窗內可橫向捲動（資料表的正常行為，稽核歸在「捲動」不是缺陷）。

**2. 在編輯器裡編輯 demo 的地圖：** 測試用編輯器指令在碰撞圖層畫一格牆 → 復原 → 重做 → 儲存 → 重新開啟專案；可玩的執行環境在那一格確實會擋人，旁邊一格不會（`test_the_demo_map_can_be_edited_undone_saved_and_the_walls_change_in_play`）。

**3. lint：** `demos/` 和 `reference_projects/` 的 43 個問題全部清掉（匯入排序、`lambda` 賦值、星號匯入改明確匯入、未使用的匯入等），12 個 demo 驗證腳本和戰鬥測試腳本修改後重新執行確認正常。skill 的提交前檢查現在包含這兩個資料夾。

**4. 說明文件：** `docs/NATIVE_KERNELS.md`（怎麼編譯、三組 kernel、退回機制、怎麼新增一個、效益）；demo 的 README 補上新功能和圖示出處。

**5. 補量測（無畫面，1280×720，pygame 軟體混合）：**
| 負載 | 每幀 |
| --- | --- |
| 60 個角色，64 px 幀 ×3 倍 | 0.7 ms |
| 60 個角色，128 px 幀 ×3 倍 | 2.4 ms |
| 150 個角色，128 px 幀 ×3 倍 | 6.0 ms |
| 40 個角色，256 px 幀 ×3 倍 | 3.7 ms |
| 全螢幕半透明疊加 | 0.3 ms |
| 三層全螢幕疊加 | 0.9 ms |
| 放大一張螢幕大小的畫布（tile 檢視每幀的成本） | 0.3 ms |

**6. 真實視窗（Cocoa，1280×720）三個職業重跑（背包格子、外觀、視差、前瞻都在）：** 全部 **60.0 fps，p95 16.7 ms**；戰士 3 擊殺、遊俠 3、法師 7；各撿到 1–2 件裝備。

**執行的測試：** 完整套件 **2174 passed、1 skipped**；ruff 全部通過（含 E501）。

### D23-8 — HUD 底部重做：圓球、快捷列、狀態列（使用者回報）

**使用者回報：** 下方文字疊在一起；血量的圖示和數字沒在同一條水平線；Potion 的「x3」很醜；希望快捷鍵像暗黑破壞神、魔獸世界的鍵盤式快捷列；血量改成左紅右藍的圓球；增益、護盾、減益、異常狀態都要顯示。

**做法（`runtime/hud_bottom.py`，新；`action_play.draw_overlay` 改用它）：**
- **圓球**：生命資源在左邊紅色圓球，第一個其他資源在右邊（名稱像魔力的用藍色，怒氣橘色，體力黃色），依比例填充（逐列畫弦、頂端較亮、液面線、高光、外框），數字在球內。其他資源是快捷列右上方的細條；名稱含 shield／barrier／ward／guard 的資源自己有淺藍色的條（護盾）。
- **快捷列**：攻擊和閃避兩個較大的格子在左，後面是編號技能；每格左上角有鍵帽（鍵名從專案的輸入表讀，不是寫死；Shift、Space 等縮寫；手把顯示 PAD 號碼）；技能名稱；冷卻用由上往下的遮罩加上秒數；魔力不足時變暗；消耗道具的技能在**右下角有小方塊徽章**顯示剩餘數量；有資源消耗的技能在左下角顯示消耗。下方是細的經驗條，「Lv N」在條裡。
- **狀態列**：玩家身上每個狀態一個方格，增益綠框、減益紅框（依狀態的作用判斷：屬性是增是減、持續傷害或治療），縮寫、剩餘時間遮罩和秒數、疊層徽章。
- **操作提示**移到畫面上方中央，有深色底，12 秒後淡出，不再壓在快捷列上。
- `PlayableTestRuntime.text(..., anchor=...)`：文字可以用任何 rect 錨點對齊，標籤和圖形在同一條水平線上。
- 測試：`test_the_hud_shows_keycaps_orbs_statuses_and_item_counts`（鍵名來自輸入表、狀態分類、縮寫、剩餘時間、道具徽章、提示倒數）。截圖 `d23_hud_orbs_actionbar_statuses.png`（1280×720 和 960×540 都檢查過）。

**限制：** 狀態沒有顯示名稱或圖示欄位，所以用 id 轉出來的縮寫和顏色表示增益／減益；敵人頭上的狀態仍是文字。

### D24-1 — 狀態與技能的名稱、圖示欄位；敵人頭上的狀態圖示；法力消耗顯示（使用者回報）

**使用者要求：** 補上 D23-8 列出的三個限制（狀態沒有名稱／圖示、敵人狀態仍是文字、技能格是文字不是圖示），再整體確認引擎、八方旅人 demo 與暗黑 demo。之後回報「法杖旁邊的 1 是什麼」。

**資料格式（向下相容，沒有值就不寫入資料）：**
- `StateDefinition` 新增 `display_name`、`icon_id`；`AbilityDefinition` 新增 `display_name`、`icon_id`（走 `OPTIONAL_DATA`）。舊資料照常載入，沒設定的不會被寫回。
- 編輯器的狀態與技能表單本來就以資料欄位為準，`icon_id` 會自動出現圖示挑選（測試：改名稱和圖示、復原）。
- 八方旅人戰鬥畫面的狀態文字也改讀 `display_name`（沒有就用 id）。

**畫面：**
- 快捷列格子：技能有 `icon_id` 就畫圖示（不再寫名稱），沒有才退回名稱文字；狀態列：有圖示畫圖示，沒有才用縮寫；名稱用 `display_name`。
- 敵人頭上：血條上方有一排小方格（`draw_status_pips`，最多 6 個，綠框增益紅框減益，剩餘時間由上往下遮罩），置中於敵人。
- 法力／資源消耗：左下角深色小膠囊，左邊一顆該資源顏色的小圓珠、右邊數字（原本只有一個孤立的數字，看不出是什麼）。
- demo：技能與狀態圖示取自既有的 CC0 資源（Ninja Adventure），寫入 `playable_assets/icons`。

**確認（全部實機，無跳過計入通過）：**
| 項目 | 結果 |
| --- | --- |
| 完整測試套件 | 2178 passed（之後再加：全部 demo 測試 22 passed） |
| 真實視窗實機驗證 `real_machine_validation.py` 全部檢查 | 66 項 PASS；4 項需要真人或手把（實體鍵盤、手把、可聽音訊、音訊延遲）未執行，原樣標示 |
| 八方旅人 demo（Cocoa、真按鍵） | 指令選單、加速點、目標選單、加速攻擊兩段傷害、神技花 3 點、粒子、調合、勝利、四種遭遇全部 ok |
| 暗黑 demo 三個職業真實視窗 | 皆 60.0 fps；戰士 3 擊殺、遊俠 3、法師 7；走完城鎮、轉職、技能樹、野外、Boss、礦坑、背包 |
| 編輯器稽核 1600×1000／1280×800／1100×700（暗黑與八方旅人兩個專案） | 0 裁切、0 溢出、0 過小；僅有頁面需捲動（資訊性） |

測試：`test_states_and_abilities_carry_a_name_and_an_icon`、`test_enemies_show_their_statuses_as_pips_over_the_bar`、`test_the_editor_edits_a_status_name_and_icon_and_undoes_it`。截圖 `docs/audits/evidence/real_machine/d24_hud_icons.png`。

**仍然存在：** 圖示是從資源包挑的相近圖，不是專屬設計；暗黑 demo 的實機輸入沒有實體鍵盤／手把驗證（需要真人）；`CollisionWorld.from_scene` 仍未快取。

### D24-2 — 冷卻轉圈動畫、從範本新增專案、編輯器左側分頁擠在一起（使用者回報）

**使用者回報：** 技能進入冷卻要有「變暗、轉一圈變亮」的動畫，當成預設；八方旅人與暗黑的設定可以當成預設範本讓使用者修改；GUI 有文字擠在一起，例如 Scene 下面的 Project 跟 Tile。

**做法：**
- **冷卻時鐘**（`hud_bottom.BottomHud._sweep`）：技能用出後整格變暗，一個明亮的扇形從 12 點鐘方向順時針展開，邊緣有一條亮線，轉滿一圈整格恢復明亮並閃一下（0.3 秒）；中間仍顯示剩餘秒數。取代原本由上往下的遮罩。對所有專案的動作戰鬥 HUD 預設生效，不需設定。
- **File > New from Template…（Ctrl+N）**（`editor/project_templates.py`）：兩個範本 —— *Party RPG (Octopath-style)*（弱點與護盾、加速點、職業、寵物、調合、狀態、四種敵人）和 *Action RPG (Diablo-style)*（職業與技能樹、稀有度與詞綴、套裝、藥水、格子背包、有冷卻的快捷列、城鎮／野外／礦坑）。範本是完整的專案資料夾（含美術與授權文件），複製後改名、載入，所有設定（戰鬥規則、數值、HUD、地圖）都能直接改；建置腳本不複製。原範本不會被動到。範本來源是 `reference_projects/`，打包安裝版若沒有這個資料夾，選單會顯示「沒有安裝範本」。
- **左側分頁**：原本「Project / Scene、Tile Palette、Layers」三個分頁在窄的左欄擠不下，第三個被捲動箭頭吃掉。改名為 Project／Tiles／Layers，dock 分頁的左右內距 12 → 8 px，左欄最小寬度 264 px；視窗最小尺寸 1000×640（再小面板會擠字）。
- **稽核腳本**：`editor_ui_audit.py` 新增 `dock_tab_hidden`，停靠面板的分頁掉到分頁列外面就算缺陷（之前被當成可捲動的資訊項而漏掉）。

**確認：** 完整套件 2185 passed；兩個專案在 1280×800 與 1100×700 稽核 0 缺陷（含新規則）；法師真實視窗重跑 60 fps；截圖 `arpg_demo_mage_field_skills.png` 可見技能 2、4 的冷卻扇形與秒數。
測試：`test_a_cooldown_goes_dark_and_a_wedge_turns_clockwise_to_bright_with_a_ready_flash`、`tests/test_project_templates.py`（複製、改名、載入驗證、原檔不變、拒絕非空資料夾、編輯器開啟）。

### D24-3 — 寵物技能、多武器與多段攻擊的測試補齊、手冊（使用者指示）

**使用者要求：** 八方旅人 demo 補寵物（派出抓到的寵物攻擊，沒有寵物就不能用，寵物本身不用是單位）、
多武器（切換武器、技能用不同武器各打一下、多段如打五下、特大火魔法三下）、調合、每個職業的副職技能、
四個奧義都要有測試；處理 lint；寫一份 md 把引擎和 demo 的功能全部記錄下來；然後 commit、push。

**引擎（通用）：**
- `AbilityDefinition.requires_items`：技能需要持有某些道具（不消耗）。沒有時 `ability_unavailable` 回
  「Needs <道具名稱>」，選單灰掉、直接施放會被拒絕。資料只在有設定時才寫入。
- `CaptureRule.pet_item_id`：捕獲成功時把道具放進背包；`actor_id` 可以留空（至少要有其中一個），所以寵物
  不必是隊伍成員。編輯器的 Capture Rules 多了「Becomes Pet Item」，「Joins As Actor」變成可留空。
- **修正一個真的錯誤**：道具的 `battle_ability` 以前不會套用 `apply_states`、資源增益和世界指令
  （`use_battle_item` 沒呼叫 `_after_ability`），所以 Storm Flask 的降防禦從來沒生效。現在會。

**demo：** 拿掉 hero_07 和「召喚寵物」技能；Sera 的 `send_frost_lynx`（需要背包有 `pet_frost_lynx`，三下冰）
和 `send_ember_hound`（捕獲 Ember Hound 後解鎖，兩下火）；新增 `grand_inferno`（一發火球打三下）。

**新增／改寫的測試（`test_octopath_demo.py` 26 → 35，加兩個單元測試）：**
| 項目 | 測試 |
| --- | --- |
| 寵物 | 有寵物可用、沒有時灰掉並說明、直接選會被拒、派出後寵物還在、出戰名單沒有多一個單位；捕獲得到寵物道具並解鎖技能、隊伍沒變 |
| 武器 | 兩種武器各自的攻擊找到各自的弱點；拿下武器後攻擊消失、裝回來恢復 |
| 多段 | 逐段記錄武器／屬性標籤：Brand of Valor（劍矛劍矛雷）、Arrowstorm（五箭＋冰）、Grand Inferno（火×3） |
| 調合 | 四種配方各做一次（材料消耗、全體傷害／補血／降防禦、產物立即用掉） |
| 副職技能 | Sera（毒擊、破甲）、Bram（治療、聖光、淨化）、Ione（孔雀舞、催眠華爾茲）各打一次並驗證狀態或傷害 |
| 奧義 | 四個奧義：不足 3 點時被拒絕並說明、足夠時花光；Last Stand 全隊攻擊提升 |

**文件：** 新增 `docs/ENGINE_HANDBOOK.md`（引擎功能、編輯器、兩個 demo、資料格式變更、測試與驗證方式、
限制與下一步、工作方式）；`README.md` 開頭改指向手冊；octopath README 更新寵物與武器說明。

### D24-4 — Scene 視圖：滑鼠滾輪改為縮放（使用者指示）

**使用者要求：** 中間網格的滑鼠操作，滾輪改成放大縮小，搭配鍵盤上下左右平移；觸控板維持。

**做法（`editor/viewport_widget.py`）：** `wheelEvent` 先判斷是不是實體滑鼠滾輪（沒有像素位移、沒有捲動階段）：
是就以游標位置為中心縮放，一格 ×1.15（游標下的世界座標不動），縮放範圍沿用相機的 0.1–8 倍；其餘（觸控板的
像素位移或有捲動階段的事件）維持原本的平移，捏合手勢縮放也沒動。方向鍵本來就是平移（有選取實體時移動實體）。
測試 `tests/test_viewport_wheel.py`：滾輪縮放且游標下的點不動、反向捲動縮回、觸控板事件仍然平移不縮放。
**限制：** 判斷依據是 Qt 事件的像素位移與捲動階段，沒有拿實體滑鼠在 Cocoa 視窗操作驗證（需要有人用滑鼠滾）。

**D24-4 修正（使用者回報滾輪還是錯的）：** 第一版用「沒有像素位移且沒有捲動階段」判斷滑鼠，但 macOS 上
很多滑鼠（平滑捲動、Logitech 等）會送像素位移，被誤判成觸控板。改成只看捲動階段：觸控板和 Magic Mouse
一定有階段（begin／update／end／momentum），實體滾輪沒有。另外：系統的自然捲動設定（`inverted`）會被
抵消，「往前滾＝放大」固定；環境變數 `ASTERIA_DEBUG_WHEEL=1` 會把每個滾輪事件的像素位移、角度、階段、
來源、判定結果印到終端機，方便對照裝置實際送了什麼。測試補了「有像素位移但沒有階段的滑鼠也縮放」。
**限制：** 仍然沒有實體滑鼠驗證；Magic Mouse 因為有階段，會被當成觸控板（行為是平移）。

### D25-1 — 寶可夢式寵物、目標框、狀態圖示、範本隨套件發布與導覽（使用者指示：下一步 1–8 一起做，5 不做）

**使用者要求：** 滾輪實測、完整實機驗證、範本打包、範本導覽、敵人狀態名稱、專屬狀態圖示、寵物養成（類似寶可夢）；
第三個範本先不做。

**寵物（取代 D24-3 的「寵物道具」做法，道具機制 `requires_items` 保留）：**
- `rpg/pets.py`：`PetSpeciesDefinition`（基礎數值、每級成長、最高等級、`exp_base` × 等級＝升級所需經驗、
  `exp_per_battle`、圖示、標籤）和 `PetRecord`（持有的寵物：物種、暱稱、等級、經驗；`gain` 回傳升了幾級）。
- 資料庫 `pet_species`（有才寫入）；存檔 RPG 狀態的 `pets`、`active_pet_id`（有才寫入，不改版本，舊存檔照常讀）。
- `AbilityDefinition.requires_pet`（`any` 或物種 id）；沒有對應的寵物時 `ability_unavailable` 回「Needs <物種名>」。
  施放前把出戰寵物的數值寫成使用者的 `pet_<stat>`、`pet_level`，公式直接讀；派出的寵物在戰鬥勝利後獲得經驗並升級。
- `CaptureRule.pet_species_id`、`pet_level`：捕獲成功得到持有的寵物，不加入隊伍。
- 遊戲 API：`pets()`、`active_pet()`、`add_pet()`、`rename_pet()`、`set_active_pet()`、`pet_stats()`。
- 畫面：暫停選單 > **Pets**（`runtime/pets_screen.py`）：清單、等級、經驗條、數值、ACTIVE 標記；Enter 選出戰、
  R 改名（打字、Enter 確認、Esc 取消）。截圖 `docs/audits/evidence/real_machine/d25_pets_screen.png`。
- 編輯器：Game Systems > Pet Species；Capture Rules 有「Becomes Owned Pet」和「Pet Starts At Level」。
- demo：Sera 起始有 Frosty（Frost Lynx Lv3）；`send_frost_lynx` 讀 `pet_power`（30 + 5 × 等級-1）；捕獲 Ember Hound
  得到 Lv2 寵物並解鎖 `send_ember_hound`。

**其他：**
- **目標框**（`hud_bottom.draw_target_frame`）：鎖定時畫面上方顯示名稱、血條、最多 4 個狀態的名稱、疊層、剩餘秒數。
- **專屬狀態圖示**：暗黑 demo 的 healing／war_cry／burning／bleeding／chilled 用程式畫（綠十字、橘色上箭頭、火焰、
  血滴、雪花，1 px 深色外框）；`art.py` 的 `status_glyph`，不是 AI 生成。
- **範本隨套件發布**：`scripts/sync_templates.py` 把兩個參考專案複製到 `src/asteria/templates/`（`pyproject`
  的 package-data 包含），`--check` 或測試會在兩邊不一致時失敗；範本內含 `START_HERE.md`（來源
  `docs/templates/`）列出每個規則在編輯器哪裡改，建立專案時顯示在 Console。
- **測試穩定性**：找到並修正先前偶發失敗的測試 `test_every_secondary_job_skill_works_in_battle`（睡眠命中率 80%）。

**限制：** 寵物不是戰鬥單位（沒有自己的血量與回合）；沒有進化與學技能；起始寵物要改 game start 資料（沒有表單）；
八方旅人的寵物沒有圖示；第三個範本依使用者指示沒有做。

**D25-1 驗證（真實 Cocoa 視窗）：**
| 項目 | 結果 |
| --- | --- |
| 完整測試套件 | 2209 passed；ruff（含 E501）全過 |
| `real_machine_validation.py` 全部檢查 | 64 PASS 第一輪；2 項 FAIL 已查明：`replay_BTL-03` 是因為我把一個測試改名而 replay 清單還指著舊名（已更新清單並加入新測試，重跑 PASS）；`vfx_moderngl_field` 54.6 fps 低於門檻，單獨重跑 55.1 fps PASS（接近門檻，其他程式同時在跑時會掉）。4 項需要真人或手把仍未執行 |
| 暗黑 demo 三個職業 | 皆 60.0 fps；戰士 3 擊殺、遊俠 3、法師 7 |
| 編輯器稽核 1600×1000／1280×800／1100×700（兩個專案） | 0 缺陷 |

### D25-2 — 八方旅人式戰鬥畫面：右側隊伍狀態、行動順序兩邊、指令選單、Break 顯示（使用者指示）

- **隊伍狀態在右邊**（`BattleUiLayoutProfile.party_hud="side_list"`）：每人一格，名稱、狀態縮寫、`HP 5,430 / 5,722`、`SP`、BP 圓點，帶細條；列高依人數自動縮減，不超出畫面。
- **行動順序**：上方每個回合一格，敵我用不同底色（友方藍、敵方紅、目前行動者金色）。
- **指令選單**（`BattleCommands(style="root")`，manifest `battle.command_style`）：Attack／Skills／Items；Attack 列出裝備武器給的攻擊，Esc 回上層，Q／R 調 Boost。
- **Break 顯示**（`runtime/battle_extras.py`）：敵人腳下盾牌數字（還要打幾下）、弱點圖示（命中後顯示，未發現是 ?）、Break 時紅色 BREAK 與「Damage up - loses a turn」。
- **不重疊**：舞台排版給每個敵人一個空間（名稱、精靈、盾牌列），選單放在雙方之間；`test_no_information_covers_other_information_on_the_battle_screen` 對四種遭遇檢查面板、選單、精靈與盾牌列互不重疊。
- 測試：`test_octopath_demo.py` 42 個通過。限制：Boost 與武器切換用列表選擇，不是在同一列左右切換。


## D25-3 戰鬥畫面實機回饋修正

- 動作選單改用螢幕座標避開敵人的名字與血條（鏡頭移動時也不會蓋住），行動順序格加高並分開名字與時間。
- 實機驗證腳本改為先開 Attack 清單、用 R 鍵調 Boost，八方旅人實機檢查 PASS。
- 新增測試：鏡頭移動期間選單不蓋住任何敵人名字。

## D25-4 戰鬥畫面全面不重疊與半透明選單

- 指令選單在八方旅人排版下改為半透明，優先放在行動角色旁（面向敵人那一側），不蓋住任何敵人的名字、血條、圖案、盾牌與弱點列；放不下時依序嘗試其他空位。
- 隊伍面板改半透明；pygame 後端面板支援 alpha。
- 選單底部說明超過選單寬度時截短。
- 新增 tests/test_battle_screen_no_overlap.py：5 場遭遇、各選單狀態、鏡頭穩定後逐幀檢查文字、面板、量表、圖案、盾牌列互不重疊。

## D25-5 選單可蓋住其他隊友

- 指令選單不再避開其他隊友（版面較好排），仍避開行動角色、所有隊伍血量面板與所有敵人資訊（名字、血條、圖案、盾牌、弱點）。
- 重疊檢查測試同步：非行動隊友不列入阻擋。

## D25-6 選單固定在行動角色旁

- 八方旅人排版的指令選單固定出現在行動角色左側（變窄而非移位），可蓋住其他隊友，不蓋行動角色、隊伍血量面板與敵人資訊。5 場遭遇逐一截圖確認。
- 實機重跑：input、mv_import、vfx_weather_load 通過；vfx_moderngl_field 在此機器上 44–54 fps（門檻 55），與戰鬥畫面無關。

### D26-1 — Asteria 通用多人連線能力（以 ARPG Demo 驗證）

**使用者要求（2026-10-14）：** 多人連線應是任何 Asteria 遊戲類型都能導入的能力。Diablo 式 ARPG 合作打 Boss 是第一個測試案例，不是功能限定的遊戲類型。

**設計提案：** 提供選配的通用連線套件和獨立 headless authoritative server，涵蓋場次、參與者身分、command/state/event 同步介面；各遊戲以 adapter 接入自身玩法。第一個端到端驗證以 2–4 人共同擊敗 ARPG Boss 為例。大型 MMO 的帳號、公開配對、持久世界、relay／代管服務不列入此提案。

**現況：** 通用 TCP session/lobby、command/state/event、可選即時 input/tick API、editor workspace 和兩個 adapter 範例已加入；ARPG 參考 runtime 仍以單一玩家／save 為中心，多人 Boss 戰尚未整合或驗收。細節、風險、分批與驗收草案見 `docs/audits/MULTIPLAYER_DESIGN.md`。

**待確認：** 正式同步模型、server 或玩家兼任 host、場次資料保存、Internet 連線方式及各玩法的品質門檻。現有程式仍是本機／可信任 LAN 原型；command 雙 client 往返曾人工確認，即時移動 adapter 和網路品質尚未實機驗證。


### D26-2 — 多人連線協定收尾與合作 Boss 範例

**使用者要求：** 延續通用多人連線功能，完成更多部分；用實際功能驗證，並確認原有功能沒有回歸。

**做法：** Server 對即時輸入回覆接受／拒絕（含速率限制原因）；adapter state/event 在 revision 前先做嚴格 JSON 與 frame 大小檢查；拒絕無法序列化的更新。新增 `CooperativeBossAdapter`：四人上限、玩家輸入擁有權、移動／攻擊、仇恨目標、階段與範圍攻擊、倒地／救援、一次性獎勵；Multiplayer workspace 可直接選取並預覽 Boss HP 與玩家位置。Ping 顯示 round-trip 毫秒。

**證據：** 新增 loopback TCP 的多人測試，含兩 client 同步移動和共同擊敗 Boss、command 重播只套用一次、輸入重播／速率限制、斷線／重新加入 spawn、adapter 拒絕及 JSON 序列化錯誤。Editor 測試檢查三種 adapter selector、profile save/load、ack 顯示、Ping 文字與 Boss marker。聚焦 multiplayer/editor 測試目前通過 17 個 case；workspace／theme 回歸測試 19 個通過。

**既有功能回歸：** baseline 發現三個舊測試仍把 workspace 數量固定為六；更新斷言以涵蓋新增 Multiplayer 工作區並仍驗證原頁面。Profiler/debugger 在受限 runner 因 loopback bind 權限失敗；獲准本機 socket 後其原有測試 10 個通過。完整 suite 尚待最後重跑。

**限制：** 這個 Boss 是可由兩個 client 真正連線共同操作的 network adapter 範例，尚未把既有 `reference_projects/diablo_demo` 的 ECS、素材、技能與玩家存檔改成多人。沒有 TLS、身分驗證、NAT relay、adapter 沙箱、網路 delay／jitter／loss 注入或 CPU／頻寬量測；不可宣稱公開 Internet 可用。

**實機與下一步：** 全部介面已加到 Multiplayer workspace；桌面 Cocoa 驗收尚未完成，因本機螢幕鎖定、GUI automation 無法取得視窗。解鎖後需確認版面、選取 Boss 範例、本機 host/client、第二 client 加入、兩端 Boss HP 一致、離開與停止 server，並保存 Cocoa 證據截圖。


## D26 — 補上與 YEP 插件、Godot 比對後缺的功能（2026-10-15，使用者要求「全部都要做」）

**來源：** 使用者提供 YEP_Full_Collection.zip（258 個 RPG Maker MV 插件，不重複的系統約 150 個）和 Godot 原始碼。我把插件說明逐一對照 Asteria，列出缺口，再分七批補上。YEP 只當功能清單，沒有複製任何程式碼。每個功能都是資料驅動、可序列化，沒設定就完全不影響既有行為（舊存檔和專案照常載入）。

**驗證：** 每批都跑完整測試套件（結束時 2400+ passed）、`ruff format`、`ruff check`（含 E501）。畫面類功能用 dummy 視訊驅動繪製成圖片檢查；**沒有**在 Cocoa 真實視窗驗證，也沒有人眼確認。

| 批次 | 內容 | 位置 |
|---|---|---|
| 1 戰鬥規則 | 嘲諷、吸血、過度擊殺、技能次數限制、技能熟練度、先制／被偷襲、站位列標記、偷竊；敵人等級與難度滑桿 | `rpg/battle_extensions.py`、`rpg/enemy_levels.py` |
| 2 ATB／CTB、結算 | 回合量表、預測行動順序、ATB 時鐘（active／semi／wait）；勝利結算畫面（獎勵、升級、掉落，manifest `battle.victory_aftermath` 開啟） | `rpg/battle_scheduler.py`、`rpg/victory.py`、`runtime/victory_screen.py` |
| 3 地圖規則 | 區域（region／tag）事件、地板傷害、滑冰地板、腳步聲、限制通行、潛行視野；事件計時器 | `rpg/map_rules.py`、`runtime/map_rules_field.py`、`events/timers.py` |
| 4 物品與系統 | 裝備耐久與破損／修理、裝備暱稱、拆解、職業點、新遊戲＋ | `rpg/durability.py`、`disassembly.py`、`job_points.py`、`new_game_plus.py` |
| 5 訊息與前端 | 文字控制碼與巨集、翻譯表（地區→語言→預設）、訊息記錄、音樂室、製作人員名單 | `presentation/message_codes.py`、`rpg/localization.py`、`rpg/extras.py`、`runtime/extras_screens.py` |
| 6 引擎 | 地形自動鋪磚（含編輯器可復原的指令）、格狀尋路與 WALK_TO、2D 骨骼動畫（階層、關鍵影格、混合、兩段 IK） | `graphics/autotile.py`、`runtime/navigation.py`、`graphics/skeleton.py` |
| 7 多人連線 | TLS、簽章 token、對外暴露防護、adapter 白名單、缺口偵測與重新同步、網路模擬、度量與量測 | `multiplayer/security.py`、`netsim.py`、`metrics.py`（詳見 MULTIPLAYER_DESIGN §9） |

**更正先前的判斷：** 我之前列了「Y 排序」為缺口，查證後引擎已經用腳底 y 當 depth 排序精靈（`tilemap_field`、`tile_scene_view`），所以沒有做。

**限制（沒做或不完整）：**
- 區域層要用編輯器的 tile 繪製工具畫一個叫 `regions` 的圖層（tile id 即區域編號）；編輯器沒有專用的區域畫筆與規則表單，規則目前用資料／Python 設定。
- 滑冰地板在 `TileMapField`（地圖場景）與動作場景的控制器路徑都接了；沒有在實機視窗手感驗證。
- 地形自動鋪磚有編輯器指令（可復原），但編輯器的 Tiles 面板還沒有「地形筆刷」按鈕。
- 尋路是格狀 A*（不是 navmesh）；`WALK_TO` 不會等走完才繼續（走完會把開關 `walk.<id>.done` 打開）。
- 骨骼動畫是資料與取樣／繪製轉換，沒有編輯器；也沒有匯入 DragonBones／Spine 檔案。
- 耐久度的破損在**下一場戰鬥**才反映到戰鬥數值（已進行中的戰鬥維持原數值）。
- 訊息控制碼的圖示（`\I[n]`）目前畫成方框佔位；CJK 文字要看字型是否支援。
- 沒做的 YEP 項目：圖片點擊事件（PictureCommonEvents）、自由放置裝飾物（GridFreeDoodads）、戰鬥天氣、EnhancedTP 等 TP 模式；Asteria 沒有「圖片」系統，要先決定是否引入。
- 多人連線：NAT 穿透／配對、真正的 adapter 沙箱、本機預測與插值、真實 WAN 測量仍未做；full-state 每 tick 約 40 KB／秒／人。
- 需要真人或裝置的審計 B 項（實體鍵盤、手把、聽感、目視）依然無法在這個環境完成。
- 既有的 `reference_projects/diablo_multiplayer_demo/build_project.py` 第 14–15 行超過 99 字元（不是這次改的）。


## D27 — 多人連線：差量更新、插值與預測工具（2026-10-15）

- **差量更新：** 見 MULTIPLAYER_DESIGN §9.4。4 位玩家打 Boss，每位玩家 server 送出由約 42 KB／秒降到約 10.6 KB／秒；tick CPU 佔比約 1% → 約 3.6%（同機測量）。向下相容：沒要求的 client 照舊收到完整狀態；既有的 83 個多人測試不改就通過。
- **遺失訊息的處理：** 差異的 `base_revision` 對不上就拒絕套用並要求重新同步；不良連線（延遲 120 ms、5% 丟包）下各 client 的最終結果仍一致。
- **工具：** `multiplayer/smoothing.py` 的 `SnapshotInterpolator`（遠端插值，限量外推）和 `InputPredictor`（本機預測與回放對帳）。純函式、有測試，**還沒接進遊戲畫面端**，需要在真實視窗調手感。
- **限制：** 差量的 server 成本隨玩家數成長（每位玩家各有基準狀態）；列表以外的物件陣列沒有鍵時整份替換；事件（`events`）遺失仍無法補回（重新同步只補狀態）。


## D28 — 補上先前列為「沒做」的 YEP 項目（2026-10-15，使用者要求「剩下的都做」）

| 項目 | 做法 | 位置 |
|---|---|---|
| 圖片與點擊事件（PictureCommonEvents／PictureSpritesheets） | Asteria 原本沒有圖片系統，這次新增：`PictureManager`（顯示、移動／淡入淡出含緩動、切換格子、點擊命中）、世界指令 `SHOW_PICTURE`／`MOVE_PICTURE`／`SET_PICTURE_FRAME`／`ERASE_PICTURE`，玩家滑鼠點擊會啟動圖片的事件程式。狀態存在事件變數，隨存檔保存；在執行環境繪製在場景上方 | `runtime/pictures.py`、`runtime/world_command_handlers.py`、`runtime/playable_test_runtime.py` |
| 自由放置裝飾物（GridFreeDoodads） | `DoodadDefinition`（精靈格、腳底碰撞、排序、對齊格距）、編輯器可復原的批次放置指令、隨機散布（有最小距離、可避開）。存在 `RpgDatabase.doodads` | `rpg/doodads.py`、`editor/doodads.py` |
| 戰鬥天氣 | 戰鬥自己的天氣（不是地圖的）：`set_battle_weather` / 指令 `SET_BATTLE_WEATHER`；每位戰鬥單位帶 `weather.<種類>` 標籤（互動規則可依天氣加成，已測 3 倍傷害）；戰鬥畫面繪製；戰鬥結束時從存檔移除標籤 | `runtime/game_session.py` |
| TP 模式（EnhancedTP） | `ResourceGain`：戰鬥資源在「造成傷害／受到傷害／擊倒／使用技能」時增加，可用固定值、傷害比例、佔最大生命比例，並可限制技能標籤。記錄實際增加量（受上限截斷後） | `rpg/battle_extensions.py` |
| Spine 骨骼匯入 | `import_spine_json`：骨骼、插槽、旋轉／位移／縮放時間軸（含拆軸版本）、插槽附件切換、曲線（線性／階梯／貝茲近似）、y 軸翻轉；不支援的部分（網格、皮膚、約束、變形、事件）用 `unsupported_parts` 回報而不是亂猜 | `graphics/skeleton_import.py` |
| 訊息圖示 `\I[n]` | 專案 `MessageSettings.icons` 把編號對應到圖示；沒對應時才畫方框 | `rpg/localization.py` |
| 耐久即時生效 | 戰鬥中武器壞掉：立刻扣掉它給的數值與資源上限，並封鎖它授予的技能 | `runtime/game_session.py`、`rpg/battle.py` |

**修掉的問題：** 不良連線下，重新同步的「回覆」本身遺失時 client 永遠停在舊狀態（因為版本號已經追上，不會再觸發）。現在 client 會在心跳時重送未被回覆的請求（`test_a_lost_resync_reply_is_asked_for_again`）。

**限制：**
- DragonBones 格式沒有做（只做 Spine 風格 JSON）；匯入的骨骼還沒接進場景或編輯器。
- 圖片只能由事件或程式顯示；編輯器沒有圖片的編輯介面。點擊判斷用整張圖的矩形，不看透明像素。
- 戰鬥天氣不會自己隨地圖或遭遇改變；由事件或程式設定。
- 裝飾物的筆刷已在 D29 補上。

## D29 — 編輯器介面：表單、筆刷、骨骼預覽（2026-10-15）

| 項目 | 做法 | 位置 |
|---|---|---|
| Game Systems 表單 | D26／D28 的 12 種規則（戰鬥擴充、敵人等級、地圖區域、耐久、拆解、職業點、新遊戲＋、翻譯、訊息設定、音樂室、製作人員、裝飾物）全都用既有的表單系統編輯，走可復原的指令；字典型欄位用 `ADAPTERS` 轉成表格 | `editor/game_systems_authoring.py` |
| 地形筆刷 | Tiles 面板的 Terrain 按鈕＋下拉（列出有 `terrain` 與 `mask:<n>` 標籤的地形）；拖曳後呼叫 `build_terrain_command`，一次一步復原 | `editor/tile_palette.py`、`tile_palette_widget.py`、`viewport_widget.py` |
| 區域畫筆 | Region 按鈕＋編號＋「清除」；畫在隱藏的 `regions` 圖層（沒有就自動建立，與第一筆同一個復原步驟），視窗上畫半透明編號蓋層。圖層名稱與 `MapRuleSet.region_layer` 一致 | `editor/tile_edit.py`（`build_region_command`） |
| 裝飾物筆刷 | Doodad 按鈕＋下拉（專案的裝飾物定義）；在視窗點一下放一個，可復原 | `editor/doodads.py` |
| 骨骼預覽 | 新的 Skeleton 面板：開啟 Spine JSON、選動畫、拖時間軸或播放，畫骨骼線；讀不了的檔案在狀態列顯示原因，匯入跳過的部分也會列出 | `editor/skeleton_view.py`、`skeleton_widget.py` |

**限制：** 骨骼只能預覽、不能編輯（骨骼與關鍵影格仍要改 JSON）；沒有貼圖預覽，只有骨骼線。蓋層與筆刷在離屏 Qt 測試過，真實視窗的手感沒看過。

## D30 — 骨骼、Picture、區域規則與多人預覽收尾（2026-10-15）

### 完成項目

| 項目 | 做法 | 位置／提交 |
|---|---|---|
| 區域規則面板 | Tiles 面板選區域編號時可直接編輯對應的 `region:<id>` `AreaRule`；編輯與畫筆都走可復原指令 | `editor/tile_palette_widget.py`、`editor/game_systems_authoring.py`；`0c0bcf5` |
| 骨骼與動畫編輯 | Skeleton 面板可新增／刪除／改名骨骼、改父骨骼與變換值；時間軸可新增／移動／刪除 Key、改屬性值與緩動。每次操作各自成為一個 undo 步驟，並能讀寫 Asteria 原生 `.asteria.skeleton.json` | `editor/skeleton_widget.py` 等；`4fdc75c` |
| 插槽貼圖預覽 | 使用 `Skeleton.draws()` 與 `to_texture_draws()` 繪製插槽精靈，Skeleton 面板同時顯示骨骼 | `editor/skeleton_widget.py`；`ee0b61d` |
| 場景骨骼動畫 | 新增可序列化的 `SkeletonAnimation2DComponent`，可掛到場景 entity；場景 viewport 與 `PlayableTestRuntime`（tile／一般場景）更新動畫並畫出貼圖，支援存檔／載入 | `runtime/skeleton_draw.py`、scene/runtime/editor 接線；`d85b75b` |
| DragonBones 匯入 | 新增 5.x JSON 匯入器，回報 `unsupported_parts`，不猜測未支援語意 | `graphics/dragonbones_import.py`；`56a0c29` |
| Picture 指令編輯器 | 可設定 `SHOW_PICTURE`、`MOVE_PICTURE`、`SET_PICTURE_FRAME`、`ERASE_PICTURE` 參數並預覽畫面位置 | event editor／picture preview；`7b7e906` |
| 多人預測／插值 | `SnapshotInterpolator` 與 `InputPredictor` 已接進多人 preview，並以自動化測試覆蓋 | `runtime/multiplayer_preview.py`；`25d683a` |
| Qt／SDL 收尾 | 修正測試結束時 Qt deferred-delete 與 SDL 資源清理問題 | `tests/conftest.py`；`a4ebe2c` |
| Octopath 勝利結算 | 參考專案與 party RPG template 都開啟 `battle.victory_aftermath`，並加回歸測試 | demo manifest、template manifest、`tests/test_octopath_demo.py`；`1ed4bc8` |
| CJK 訊息字型 | RPG 對話、戰鬥 UI、pygame／ModernGL 對話使用系統 CJK 字型；拉丁文字保留既有字型，附單元測試 | `platform/pygame_battle_ui.py` 等、`tests/test_battle_ui_renderer.py`；`ff9eddb` |

### 驗證證據

- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`：**2637 passed、1 warning**，exit code 0；結束時沒有 Qt／SDL／malloc 崩潰訊息。warning 是既有的 PySide `QMouseEvent` deprecation。
- `.venv/bin/ruff check src tests scripts demos reference_projects`：通過。
- `.venv/bin/ruff check --select E501 src tests scripts demos reference_projects`：通過。
- 有測試覆蓋區域規則編輯、原生骨骼序列化／指令復原、DragonBones 支援子集、Picture 參數與預覽、骨骼 component 存取及 runtime 實際像素繪製、多玩家平滑資料流。
- Cocoa 視窗：Octopath 戰鬥及勝利結算、區域地板傷害／滑冰／腳步聲、Music Room／Backlog／Credits、`\\C`／`\\I`／`\\V`／`\\N` 和 CJK glyph、編輯器骨骼／區域規則／Terrain／Region／Doodad 面板均有實機程序驗證與截圖。另以兩個 Cocoa runtime 視窗連同一個本機 server；兩邊都收到兩位玩家狀態、各處理 304 個遠端快照，兩個 client 均正常結束。
- 原生按鍵事件佇列、選單／存檔／設定流程已驗證；CoreAudio 開啟 44.1 kHz 裝置、音效 channel 與音樂串流運作。這些程序驗證不代替真人手按、主觀聽感或實際音訊延遲測量。

### 限制與未完成

- DragonBones 僅支援明確實作的 5.x 子集；IK、FFD、z-order、事件／actions、自訂 easing、替代 skin、多 armature／skin 歧義、部分 display／scale／skew／隱藏與顏色動畫等會回報不支援或要求明確選擇，不會自行近似。
- Skeleton component 目前嵌入原生 rig JSON；貼圖仍依專案資源 ID 解析，引用的貼圖必須存在於該專案。
- Picture 預覽使用事件設計畫布座標；點擊命中仍是既有整張圖片矩形規則。
- 真人主觀手感、實體鍵盤直接操作尚未驗收；測試送入 Cocoa／SDL 事件佇列，不代表由人手按鍵。當時沒有連接 game controller；可播放音訊已測到裝置層，但聽感與 latency 未測。
- 兩個 Cocoa 視窗同機 loopback 的多人資料流、插值與預測已驗證；真人主觀延遲／移動手感仍待確認。原生驗證器先前沒有載入 tilemap sidecar，找到問題後補上資源解析；最後的 Cocoa 重驗通過，使用 Diablo demo 的 tilemap 顯示區域 7 編號及半透明蓋層，截圖 `editor_d30_region_overlay.png`。專案檔案保持未改寫。
- 只有一台可用機器；`multiplayer_netbench.py` 的 loopback 數據不能當跨機器 WAN 結果，WAN 實測未完成。

### NAT／配對與 adapter 沙箱決策

- 第一階段維持遊戲作者自行部署 authoritative server 與手動輸入 host／port，不把 Asteria 核心依賴在託管配對服務上。
- 若後續加入配對，配對服務只交換短效 session code 與連線候選位址；先嘗試直連，失敗才由可自架 relay 轉送。不能把候選位址交換誤稱為完整 NAT 穿透，也不能把 relay 當成現有功能。
- adapter module allowlist 只限制可載入的 Python 模組，並非安全沙箱。對不可信 adapter，後續方案應採獨立 OS process／container、版本化 JSON RPC、資源與時間限制，以及拒絕時 fail closed；未完成威脅模型與跨平台評估前不在引擎行程內任意執行第三方 adapter。
- 本輪只記錄決策與限制，沒有實作 NAT traversal、配對服務、relay 或 adapter sandbox。


## D31 — 寵物進階與 GAP_LIST 缺口（2026-10-16，使用者要求「全部都做」）

**依據：** `docs/audits/GAP_LIST.md`（對照 YEP 258 個插件與 Godot；方法是關鍵字搜尋加讀碼，不是逐行比對）。

| 項目 | 做法 | 位置 |
|---|---|---|
| 寵物進化／學技能／親密度 | 物種有 `evolutions`、`learnset`、`affinity_per_battle`、`max_affinity`；持有的寵物有 `affinity`。進化條件：等級、親密度、道具；`automatic` 者在勝利後自動進化。出現在 learnset 的技能必須學會才能用（`requires_pet` 之外再檢查）。暱稱、等級、親密度進化後保留 | `rpg/pets.py`、`runtime/game_session.py` |
| 寵物戰鬥單位（可選） | 物種 `battle_unit: true` 時，出戰寵物以 `pet:<id>` 加入英雄方，數值取自該等級，資源取 `resources`（或 `max_<name>` 數值），技能取 `battle_abilities`。預設關閉 | `game_session._pet_member` |
| Game Start 表單 | 場景、朝向、位置、隊伍、道具、貨幣、起始寵物；可復原；以整個專案驗證後才套用；未顯示的欄位保持原樣 | `editor/game_start_authoring.py`、`game_start_widget.py` |
| 商店條件 | `ShopEntry.visible_when`、`price_rules`（開關／變數條件，買賣倍率可疊乘） | `rpg/economy.py`、`game_menus.py` |
| 區域戰鬥背景 | `AreaRule.battle_background`：開戰時玩家所在區域指定的背景資產優先於 manifest | `rpg/map_rules.py`、`battle_presentation_adapters.py` |
| 隊伍共用量表 | `BattleExtensionRules.shared_gauges`，`ResourceGain(shared=True, side=…)`；值存在 world counters `gauge.<id>`，戰鬥內外都可用 | `rpg/battle_extensions.py` |
| 狀態分類 | 狀態用 `category.<名稱>` 貢獻標籤分類（無資料格式變更）；`StateRuntime.remove_category`、`session.dispel` | `gameplay/states.py` |
| 自動戰鬥 | `auto_battle_choice`：有 `heal_tag` 且有人血量低於門檻時選治療，否則選消耗最高的可用技能 | `runtime/game_session.py` |
| 暫停選單項目 | `MenuEntry`：標籤、事件程式、顯示／可用開關；只有專案定義才出現 | `rpg/extras.py`、`playable_test_runtime.py` |
| 事件指令 | `MOVE_ROUTE`（相對步數路徑，完成開關 `walk.<id>.done`）、`SHOW_BALLOON`（以既有 popup 顯示符號） | `runtime/world_command_handlers.py` |

**資料相容：** 所有新欄位沒設定就不寫入；舊專案與存檔照常載入。

**驗證：** 新增 `tests/test_pets_advanced.py`（13 項）、`tests/test_game_start_authoring.py`（4 項）及商店、導航測試；完整測試 2678 passed。有 9 項失敗：其中 8 項在未修改的 HEAD 上同樣失敗（`test_editor_dock_tabs` 3、`test_project_templates` 3、`test_region_rules_panel`、`test_theme`），另有 `test_editor_shell_integration_154a::..._starts_without_project...` 也在 HEAD 失敗；`test_skeleton_editing` 的滾輪測試在完整套件中失敗一次、單獨執行兩次通過（疑似順序相依）。`ruff format`、`ruff check`（含 E501）通過。

**沒做／限制：**
- **沒有在 Cocoa 視窗驗證**新的 Game Start 分頁、Pets 畫面的親密度字樣、暫停選單項目。依使用者要求沒有改動既有的版面與字體；唯一的 UI 增加是 Database 工作區最後一個「Game Start」分頁、Game Systems 的幾個新表單欄位與一個新種類。
- 事件複製／變形／生成、點擊觸發、事件圖示未做；A7、A9、A11–A14、A16、A17 未做。
- 寵物戰鬥單位倒下不影響戰敗判定（英雄全倒才算）；自動戰鬥沒有編輯器介面。
- 寵物學到的技能只做「是否可用」的閘門，沒有自動把技能加進選單。
- 手把、實體鍵盤、聽感、WAN 仍需外部條件。

### D31 補記：Cocoa 實機驗證（2026-10-16）

- **編輯器（真實 Cocoa 視窗，`scripts/editor_ui_audit.py`，octopath_demo）：** Game Start 分頁、Pet Species、Shops、Pause Menu Entries、Battle Extension Rules 在 1600×1000 與 1100×700 皆 0 缺陷（只有一般的頁面可捲動提示）。截圖：`d31_game_start_tab.png`、`d31_game_systems_icons.png`。
- **發現並修正：** 商店表單原本把條件放在巢狀表格裡，造成 2 個過小控制項（在未修改的 HEAD 上為 0）。改成平的字串清單欄位（`switch:name==true`；價格規則 `買 賣 | 條件;條件`），以轉接器雙向無損轉換，缺陷歸零。
- **圖示：** 新增 `flag`（Game Start）、`paw`（寵物）、`gauge` 三個圖示，並讓 Game Systems 的種類下拉選單與其他資料庫分類下拉一樣顯示圖示；Revert 按鈕有圖示。
- **Pets 畫面（真實視窗，SDL driver `cocoa`）：** 親密度「Bond 12」顯示於既有的一行內，沒有溢出；按 E 後寵物由 Frost Lynx 進化為 Ember Hound，暱稱與等級保留（`d31_pets_before_evolve.png`、`d31_pets_after_evolve.png`）。
- **仍未驗證：** 真人操作手感；暫停選單的自訂項目與戰鬥單位寵物沒有在實機視窗跑過（只有自動化測試）。


## D32 — GAP_LIST 收尾與測試修正（2026-10-16，使用者要求「全部用好、錯誤都修正」）

**讀碼確認為已具備（不重做）：** A9 命中／迴避（`OutcomeCheckDefinition`）、A12 附魔與裝備成長、A13 技能學習（技能樹節點付職業點）、技能獎勵（`AbilityDefinition.commands`）。

| 項目 | 做法 | 位置 |
|---|---|---|
| 技能類型 | `AbilityDefinition.menu_category`（沒設不寫入）；戰鬥指令選單多出該分類，Tab 循環，根選單多一列 | `gameplay/abilities.py`、`runtime/battle_commands.py` |
| 技能槽 | `AbilityLoadoutRules`（槽數、`capacity_by_level`、受限來源、永遠可用）；角色 `equipped_abilities`；只有裝備的「學會」技能可用；`equip_ability`／`unequip_ability`／`ability_slots`。沒有規則時行為不變 | `rpg/ability_loadout.py`、`rpg/ability_build.py`、`runtime/game_session.py` |
| 事件生成／複製／變形 | `SPAWN_ENTITY`、`COPY_ENTITY`、`MORPH_ENTITY`（世界指令；變形保留位置與名稱）| `runtime/game_session.py`、`world_command_handlers.py` |
| 點擊觸發 | `Interaction2D.trigger` 多一個 `click`；地圖上滑鼠點擊範圍內實體就啟動其事件程式 | `runtime/components2d.py`、`playable_test_runtime.py` |
| 地圖視窗 | manifest `field.hud.gold`／`quest_tracker`：左上角顯示錢包與進行中任務的目標；預設關閉 | `playable_test_runtime.py` |
| 演員變數 | `actor_variable`／`set_actor_variable`（存在事件變數 `actor.<id>.<名稱>`）| `runtime/game_session.py` |
| 編輯器 | Game Systems 新增 Ability Slots；商店條件改成單行文字欄位（`switch:name==true`；價格規則 `買 賣 | 條件;條件`，轉接器雙向無損）| `editor/game_systems_authoring.py` |

**修正的問題：**
- **滾輪蓋過數值欄位的 bug：** `decor._Decorator` 對數值欄位的滾輪事件 `ignore()` 後回傳 `True`，事件被過濾掉、不會傳給父層，滑鼠停在數值欄位上就捲不動面板。改成把事件轉給所在的捲動區。（`test_wheel_over_unfocused_skeleton_field_scrolls_panel_not_field` 在完整測試裡失敗就是這個原因。）
- **多人輸入遺失：** 伺服器對 1/60 秒內的第二筆輸入回 `input rate exceeded`，客戶端沒重送，最新輸入就永遠沒到。客戶端橋接現在在被限流時延遲重送最新輸入（`INPUT_RESEND_DELAY`）；測試 12 次全過（修前約一半失敗）。
- **過期測試（前一個 UI 整理 commit 之後沒跟上）：** `test_editor_dock_tabs`、`test_project_templates`、`test_region_rules_panel`、`test_theme`、`test_editor_shell_integration_154a` 改成對應現行（有意的）結構：卡片包住捲動區、範本多了 `basic_rpg` 與 `empty`、選單文字 `New Project…`、區域規則表單一律換行、分頁邊框逐邊繪製。
- **編輯器稽核找出的版面缺陷：** 粒子效果的最小／最大值框被截斷（改為上下堆疊，並讓表單格子靠上對齊）、Ability Timelines 的 Length 欄位與 Enemy AI 的 Actions per turn 太窄（加最小寬度）。稽核腳本改成跳過被其他分頁蓋住的元件（原本把沒顯示的 Tiles 面板誤報為截斷），並新增 `scene_tiles` 面層。

**驗證：** 完整測試 **2695 passed、0 failed**；`ruff format`、`ruff check`（含 E501）通過。編輯器稽核（真實 Cocoa 視窗，octopath／diablo 兩個專案，1600×1000、1280×800、1100×700）缺陷 0（唯一 1 項 Enemy AI 窄欄位已修正後重跑為 0）。地圖視窗與自訂暫停選單項目在真實視窗（SDL driver `cocoa`）截圖：`d32_field_hud.png`、`d32_pause_menu_entry.png`；`d32_ability_slots_editor.png`。

**限制：**
- A17（弱點姿勢、狀態特效、血條樣式）沒做；事件常駐圖示沒做。
- 技能槽、技能類型、點擊觸發、事件生成只有自動化測試，沒有在真實視窗操作過；技能槽沒有玩家用的畫面（只有 API 與資料編輯）。
- 自動戰鬥沒有編輯器介面；寵物戰鬥單位倒下不影響戰敗判定。
- 真人操作手感、手把、聽感、WAN 仍需外部條件。


## D33 — 剩餘項目收尾（2026-10-16，使用者要求「剩下的幫我做好」）

| 項目 | 做法 | 位置 |
|---|---|---|
| 低血量姿勢 | manifest `battle.weak_below`（0 = 關）；產生出來的戰鬥角色圖多一格 `weak`（較蒼白、下沉），生命比例低於門檻時用，回血就回到 idle；自訂的戰鬥視覺設定檔有 `weak` 狀態／片段才會用，沒有的維持原樣 | `runtime/battle_presentation_adapters.py`、`runtime/battle_visuals.py` |
| 狀態染色 | `StateDefinition.tint`（`#rrggbb`，沒設不寫入）；帶有狀態的戰鬥角色以該色乘上貼圖，多個狀態相乘；`TextureDraw.tint` | `gameplay/states.py`、`runtime/draw.py`、`presentation/battle_runtime.py` |
| 事件常駐圖示 | 世界指令 `SET_ENTITY_ICON`（空 `icon_id` 清除）；存為事件變數 `icon.<實體 id>`；地圖上畫在實體頭上 | `runtime/game_session.py`、`playable_test_runtime.py` |
| 技能槽畫面 | 暫停選單「Skill Slots」（專案有 `AbilityLoadoutRules` 才出現）：選隊員、Enter 裝備／移除、顯示槽數；風格與其他暫停選單附加畫面一致 | `runtime/extras_screens.py` |
| 自動戰鬥鍵 | manifest `battle.auto_key: true` 時 T 鍵讓目前角色依 `auto_battle_choice` 行動 | `runtime/battle_commands.py`、`playable_test_runtime.py` |
| 寵物戰鬥單位 | 以寵物暱稱顯示（原本顯示 `pet:<id>`）；倒下或獨活不決定勝負（`BattleRuntime.outcome_exempt`，勝負判定與「隊伍存活數」條件都略過它） | `runtime/game_session.py`、`rpg/battle.py`、`rpg/battle_lifecycle.py` |

**驗證：** 新測試加進 `tests/test_pets_advanced.py` 與 `tests/test_navigation_session.py`；Cocoa 真實視窗（SDL driver `cocoa`）截圖：`d33_battle_pet_unit_weak_pose.png`（寵物戰鬥單位以暱稱出現在隊伍與時間軸、低血量姿勢）、`d33_skill_slots_screen.png`（技能槽畫面）。

**限制：** 事件圖示只驗證了資料與繪製呼叫，沒有在真實視窗用實際圖示素材看過；弱點姿勢只對產生出來的角色圖自動有，Octopath／Diablo 的自訂角色圖沒有 `weak` 片段所以不變；自動戰鬥沒有編輯器表單（用 manifest 鍵）。


## D34 — 剩餘事項的決定與驗證（2026-10-16）

- **`CollisionWorld.from_scene` 快取：決定不做。** 量測（`from_scene` 已走欄位儲存）：100／500／2000 個碰撞器每次 0.05／0.22／0.85 ms，每幀約一次。收益不到 1 ms，而快取要處理啟用狀態、增刪、換場景與移動的失效，風險較大。
- **事件常駐圖示：** 真實 Cocoa 視窗（SDL driver `cocoa`）用 Diablo 專案的物品圖示（`bone_shard.png`）顯示在玩家頭上（`d34_entity_icon.png`）。同一次也確認 `_field_world_xy`（點擊觸發用的螢幕→世界轉換）與 `_field_screen_xy` 往返誤差為 0。
- **手冊：** `ENGINE_HANDBOOK.md` 新增 D27–D33 的系統表，並把「下一步的候選」改成現況：第三個範本與 Web 匯出依使用者指示暫不做。
- **仍未做：** 第三個範本、Web 匯出（使用者指示先不用）；自動戰鬥與低血量姿勢門檻的編輯器表單；專屬技能圖示與八方旅人寵物圖示。需要外部條件的項目（手把、聽感、WAN）不變。


## D35 — 戰鬥選項表單與原創圖示（2026-10-16）

| 項目 | 做法 | 位置 |
|---|---|---|
| 戰鬥選項表單 | Game Systems > Battle Options（`BattleOptions`：T 鍵自動戰鬥、低血量姿勢門檻）；專案有這筆資料就以它為準，沒有才讀 manifest 的 `battle.auto_key`／`battle.weak_below`；沒設定不寫入 | `rpg/extras.py`、`editor/game_systems_authoring.py`、`playable_test_runtime.battle_option` |
| 原創圖示 | `asteria.graphics.forged_icons`：44 種用程式畫的像素風圖示（武器、元素、治療、狀態、寵物頭像…），4 倍超取樣縮小；以 id 關鍵字對應種類；沒有任何第三方圖片、沒有 AI | `src/asteria/graphics/forged_icons.py`、`scripts/build_original_icons.py` |
| 套用到專案 | Diablo：23 個技能換成原創圖示（藥水沿用道具圖示、狀態沿用既有程式畫的狀態符號）；八方旅人：62 個技能、6 個狀態、2 隻寵物（Frost Lynx、Ember Hound）新增圖示；圖檔在各專案 `playable_assets/icons/skill_*.png`，範本同步；兩個 `build_project.py` 重建後會再套用；CREDITS 註明原創 | `reference_projects/*`、`src/asteria/templates/*` |

**驗證：** 新增 `tests/test_forged_icons.py`（每種圖示畫得出來且不是空白或實心方塊、id 對應、只改 icon 那幾行、兩個專案的圖示檔都存在且可被選單載入）與 `BattleOptions` 測試。Cocoa 真實視窗：八方旅人的 Pets 畫面顯示 Frosty 的 Frost Lynx 頭像、Diablo 的快捷列顯示新的拳頭與翻滾圖示、Battle Options 表單在 1600×1000 稽核缺陷 0（`d35_*.png`）。

**限制：** 圖示是 32 px 的簡單像素風，不是美術師手繪；技能名稱沒有對上關鍵字的不會有圖示（沿用原本的縮寫）；八方旅人的戰鬥選單目前不顯示技能圖示（選單版面沒有改）；Diablo 多人副本專案沒有重建，仍用舊圖示。


## D36 — 戰鬥選單顯示技能圖示、沒對上的 id 也有圖示（2026-10-16）

| 項目 | 做法 | 位置 |
|---|---|---|
| 戰鬥選單圖示 | 技能（含武器普攻）與道具的 `icon_id` 帶進選單列（`BattleActionEntry.icon_asset_id`）；畫面端原本就有 `BattleUiIcon` 與 `resolve_icon` 掛鉤，但沒人接：現在由戰鬥畫面把專案的選單圖示載入並畫在每列左側。選單裡只要有一列有圖示，所有列的文字右移 8 個版面單位並預留位置；名稱太長會以「..」截短，不會碰到右側花費。**沒有任何圖示的選單版面完全不變** | `runtime/battle_commands.py`、`runtime/battle_presentation_adapters.py`、`presentation/battle_ui.py` |
| 沒對上關鍵字的 id | `forge_monogram`：以 id 的前兩個字母加 id 雜湊出的顏色畫成寶石，同一個 id 永遠同一張、不同 id 不同色；`apply_to_project_file` 在關鍵字都不符時自動用它（`skill_mono_<id>.png`），所以每個技能、狀態、寵物都有自己的圖示 | `graphics/forged_icons.py` |

**驗證：** `tests/test_forged_icons.py`（含寶石圖示穩定且互不相同、無關鍵字的紀錄拿到寶石）、`tests/test_pets_advanced.py`（選單列帶圖示、圖示可解析、解析失敗時回 `None`）。Cocoa 真實視窗：八方旅人的戰鬥選單 Attack／Skills 分頁顯示圖示，長名稱截短（`d36_octopath_battle_menu_icons.png`、`d36_monogram_icons.png`）。

**限制：** 目前兩個 demo 的所有技能都對上關鍵字，所以還沒有專案實際用到寶石圖示；選單圖示固定畫 8 個版面單位寬（約 24 px），細長的武器圖示（法杖、匕首）看起來偏小。


## D37 — 場景開啟時角色置中（2026-10-16）

編輯器開啟專案（或按 Reset View）時，如果場景沒有啟用中的遊戲攝影機，過去是把世界原點放在視窗左上附近，八方旅人的角色因此偏在一側。現在 `SceneViewportWidget.frame_initial()` 先用遊戲攝影機的範圍，沒有才呼叫 `frame_entities()`：把所有有位置的實體的外框中心放在視窗正中央，實體分布比視窗寬時縮小到放得下（最多放大 1.5 倍，單一實體維持 1 倍）。視窗改變大小時，如果使用者還沒有平移或縮放，視圖會跟著保持置中；平移過就不動它。

**驗證：** `tests/test_viewport_framing.py`（開啟、縮放視窗、平移後按 Reset View、平移後視窗改變大小）；`tests/test_editor_shell_surface.py` 的 Reset View 期望改成「單一實體在視窗中央」。Cocoa 視窗截圖：`d37_scene_view_centered.png`（六個角色的外框中心與視窗中心差 < 3 px）。


## D38 — 到處都能挑圖示（2026-10-16，使用者要求「寫這些東西時要提供可以選 icon 的位置」）

| 項目 | 做法 | 位置 |
|---|---|---|
| 內建圖示庫 | 圖示 id 可寫 `forged:<種類>`（44 種：武器、元素、治療、狀態、寵物頭像…）或 `forged:mono:<字母>`（寶石字母圖示）；執行期與編輯器縮圖都能解析，不需要任何圖檔 | `runtime/menu_icons.py`、`editor/image_tools.py` |
| 圖示挑選欄位 | 編輯器表單新增 `icon` 欄位：下拉選單（每項附縮圖）列出專案裡所有 `icons` 資料夾的圖檔、`icon` 資產與內建圖示庫，旁邊有預覽與「Browse…」（挑自己的 PNG：專案內的檔案原地使用，專案外的複製進 `icons/`，同一張不重複複製）；資料庫（技能、道具、裝備、狀態…）原本的 `icon_id` 欄位也換成同一個挑選器 | `editor/game_systems_widget.py`（`_IconPicker`）、`editor/image_tools.py`（`IconLibrary`）、`editor/authoring_hub_widget.py` |
| 可以放圖示的紀錄 | 原有：道具、裝備、技能、狀態、寵物物種。**新增 `icon_id`（沒設不寫入，舊資料照常載入）：** 任務、派系、成就、商店、套裝、音樂、暫停選單項目、職業、寶珠／鑲嵌物（Attachment）、被動（Passive） | `rpg/quests.py`、`world_record.py`、`economy.py`、`equipment_sets.py`、`extras.py`、`actors.py`、`items.py`、`ability_build.py` |
| 執行期顯示 | 暫停選單項目的圖示（有圖示時面板自動加寬）、任務記錄、成就列表、商店標題；戰鬥選單的技能／道具圖示（D36）。職業、寶珠、被動、派系、套裝、音樂目前只有資料與編輯器欄位，畫面還沒有地方顯示 | `runtime/playable_test_runtime.py` |
| Game Systems 種類下拉選單 | 每個種類都有圖示（新增任務卷軸、旗幟、獎盃、寶箱、地球、地圖針、鐵鎚、循環、小樹、捕捉網、互動手形） | `editor/icons.py`、`editor/decor.py` |

**驗證：** `tests/test_icon_fields.py`（每種紀錄往返與舊資料相容、內建圖示解析、挑選清單、匯入圖檔、表單欄位往返、每個種類有圖示、暫停選單與任務記錄真的畫出圖示）。Cocoa 真實視窗：編輯器的圖示挑選器（寵物物種、任務）、暫停選單與任務記錄的圖示（`d38_*.png`）；編輯器稽核（Cocoa 與 offscreen，1600×1000／1100×700）缺陷 0。

**順帶修正：** 編輯器在大資料夾下列出圖檔會很慢，改成有深度、資料夾數與數量上限的走訪並略過隱藏／建置資料夾；`scripts/editor_ui_audit.py` 結束時直接離開（避免 Qt 在 macOS 結束時當機），且接受 `-ApplePersistenceIgnoreState YES`（macOS 在程式異常結束後會跳出「是否重新開啟視窗」的對話框，不加這個旗標，下一次啟動的 GUI 程式會停在對話框等人按）。

**限制：** 職業、寶珠、被動、派系、套裝、音樂的圖示目前沒有執行期畫面可以顯示；挑選器是下拉選單加 Browse，不能直接打字輸入任意 id（用 Browse 或內建庫；手寫在資料裡的 id 會保留）。


## D39 — Lucifer 換皮、Diablo 流派與裝備詞條（2026-10-17，使用者要求「全部換成 Lucifer」「Diablo 最重要的是技能樹與裝備詞條」）

**做了什麼：**
- 換皮工具 `scripts/lucifer_reskin.py`、`scripts/reskin_reference_projects.py`：Octopath、reference RPG、party／basic 範本換成 Lucifer 人物、怪物、背景、UI 面板、字型與圖示；basic 起始範本的主角是 Warrior、怪物是 Skeleton Ancient。build 腳本結尾會自動套用。
- 戰鬥畫面：怪物血條放腳下（`overhead_below`）、角色都站在草地上（`stage_top`）、指令選單在行動角色旁、半透明；選單會蓋住沒在行動的隊友（原本的邏輯，使用者確認這樣是對的），不會蓋住行動中的角色。
- 戰鬥 UI 的像素字型缺很多 ASCII 字元（括號、百分比…），缺的字改用內建字型畫。
- Diablo 兩個 demo：Lucifer 人物與地形、UI Set 1 面板、特效（Foozle Pixel Magic Effects）；每個職業三個流派（各 5 技能、3 被動、1 個互斥的關鍵天賦），共 36 個新技能與 7 種新狀態；元素與暴擊屬性（`crit`、`fire_dmg`、`cold_dmg`、`shock_dmg`、`poison_dmg`）；33 種基底、7 個部位、3 套套裝、10 件獨特裝、約 36 種詞條、六種稀有度、每種怪物的掉落表。
- 引擎：技能欄綁定 `slot:N`、技能樹技能可進技能欄（自動放入空格，等級越高格數越多，最多 6 格）、`vfx` 提示、技能樹節點 `icon_id`；技能樹畫面可縮放（滾輪／+ −）、拖曳平移、點選、R 回到全貌，節點永遠不重疊。
- 編輯器：版面表單顯示全部選填欄位，技能樹表單顯示每個節點的圖示欄。

**驗證：** 全套測試 2944 項通過；`tests/test_arpg_builds.py` 涵蓋流派結構、關鍵天賦互斥、技能欄、詞條與稀有度、掉落、特效、技能樹視圖與編輯器欄位；`scripts/arpg_demo_live_check.py`、`scripts/reskin_live_check.py` 在 Cocoa 真實視窗跑過（60 fps）；`scripts/arpg_balance.py` 九個流派綜合分數在平均的 -12% 到 +20% 之間。

**限制：** Diablo 的投射物與弓／魔杖圖示不是 Lucifer；鎮上的房子是上色的墓穴；平衡只比流派之間，沒有裝備也沒有真人；重建 Octopath／reference 會換新的專案 id（舊存檔對不上）。


**D39 補充（同日，使用者看了 Cocoa 實機畫面後的修正）：**
- **去掉舊美術**：Diablo 兩個 demo、Boss Trial、Octopath、reference、範本裡 Ninja Adventure、Kenney、Idylwild 的圖和產生它們的程式都移除了（`art.py` 的 ninja／kenney 函式、`trial_art.py` 的 ninja 程式、三支舊的 `scripts/build_reference_*`）；只留音效檔與 `tests/golden` 的固定測試素材。投射物與特效改用 Foozle Pixel Magic Effects，弓與法杖的圖示用 Lucifer 裝備圖代替，箭是程式畫的。`scripts/prune_orphan_assets.py` 刪掉沒人引用的素材檔，換皮與 Boss Trial 的 build 結尾都會跑。
- **揮劍方向**：Foozle 的 Left 與 Right 攻擊動畫不是鏡像（Left 是由上往下揮，鏡像 Right 會變成由下往上）。隊伍站右邊面向左，所以用 Left 條帶，工作表標記 `facing: left`（`BattleCombatantVisual.art_facing`，不再翻轉）；怪物用 Right。
- **三種攻擊條帶**：普通武器攻擊用第一條；施法、增益、獲得能力、輔助用第二條；大絕招與重擊（神聖技、多段、重砸、斧）用第三條；跳躍用 Jump。Diablo 的四方向角色也有 `attack2`／`attack3`／`jump`，每格依自己的大小放在共同的格子裡（原本不同大小的條帶被壓成同一大小而變形）。
- **異常狀態與特效位置**：狀態名稱放在怪物頭正上方；技能特效以角色本體（不是整張圖框）為中心；斬擊類特效依攻擊方向翻轉（`face_attacker`）。圖框裡待機腳底以下還有別的動畫佔位，所以工作表的 pivot 設在待機的腳底，血條與名字不會蓋到自己。
- **動作結尾**：攻擊、施法、受擊、跳躍的最後一格都是站姿，不會停在半空。
- **卡頓**：Cocoa 實機 5000 幀平均 8.3 ms、最長 10.9 ms；唯一的停頓是第一次放粒子特效時載入 kernel（約 60 ms），改成進戰鬥時預先載入。
- **每個方向都照包裝用**：包裝的四個方向（Left、Right、Up 背影、Down）各有自己的條帶，一律原樣使用，不翻轉、不拼貼、不重排。隊伍站右邊面向左，用 Left（工作表標記 `facing: left`）；怪物站左邊面向右，用 Right；Diablo 四個方向各用自己的。（曾經把 Right 換成「Left 翻轉」，也曾拿 Down 的弧蓋到 Up，都被使用者指出素材本來就有，已還原。）

**D39 再補充（同日，把清單上能修的都修了）：**
- 向上（背對鏡頭）的揮擊：包裝本身就有 Up 條帶，直接照用，不拼貼、不重排（曾經拿 Down 的弧蓋上去，使用者指出素材都有，已還原）。
- 重建不再換 id：`scripts/stable_ids.py` 讓場景與實體 id 在每次 build 都一樣；Octopath 與 Boss Trial 的 build 結尾重跑兩次結果完全相同。complex_reference_rpg 現在可以從頭重建：`build_project.py` 結尾依序跑 `scripts/build_reference_presentation.py`（特效圖框、動作序列、側視版面與 HUD；原本由已刪掉的舊腳本做）和換皮；專案 id 沿用現有的。它的場景與實體 id 每次重建都是新的（沿用舊行為，已提交的存檔、試玩設定與黃金基準都綁著現有的 id），重建後要重跑 `build_saves.py`、更新試玩設定與 `scripts/update_golden_baselines.py`，所以已提交的版本沒有重建。
- `scripts/boss_trial_live_check.py` 在 Cocoa 實機通過（按鍵打贏三個階段）：原因是腳本在最後一階段還一直把 Boss 血量釘回去。
- Diablo：弓、弩、魔杖的圖示在 Lucifer 沒有對應物，改成程式畫的（32×16、和裝備包同樣的外框，`lucifer_art.weapon_icon`）；鎮上的房子用地城圖集組成（紅屋頂、磚牆、門、窗，商店有條紋遮陽、鐵匠有爐火窗）；每個技能的動畫在每個職業的四個方向都有對應片段（有測試）；四人原生連線驗收 `scripts/validate_multiplayer_project.py` 通過。
- 平衡：`scripts/arpg_balance.py --gear` 讓每個流派穿自己的武器、獨特裝與隨機稀有裝；九個流派在「無裝備／有裝備」輸出的幾何平均落在 400–640（坦克型流派的目標是平均的 75–85%），倍率在 `arpg_builds.BUILD_DAMAGE`。
- 還沒做：受擊閃光是包裝本身的「受傷」動畫（白色、紅色剪影），沒改。

**D39 編輯器啟動（同日）：** 開啟編輯器預設會開 `~/Library/Application Support/Asteria/Projects/Basic RPG`，但這個資料夾只在第一次建立，範本改了它就過期（使用者看到的還是舊的 Ninja 美術）。現在 `ensure_starter_project` 會在資料夾旁記一個範本指紋：指紋變了而專案沒被改過就原地重建；被改過或沒有指紋（更早建立的）就整個移到 `Basic RPG (previous)` 再重建，不會丟東西。左邊面板每次開啟都固定停在 Project 頁(不記住上次的頁籤)。

**D39 戰鬥 UI 統一（同日）：** 所有回合制 demo 與範本（Boss Trial、Octopath、complex reference、party 範本、Basic RPG 起始專案）都用八方旅人版面：隊伍 HP 一人一格排在右邊緣（`party_hud=side_list`）、指令選單貼在行動角色旁（`action_menu_placement=actor`）且透明、怪物名字與血條在頭上。選單只可能蓋到「非行動中的隊友」，不會蓋到行動角色或任何怪物（`menu_over_stage` 不再讓選單蓋怪物）。Boss Trial 的怪物不再隱藏血條，Basic RPG 起始專案不再覆寫站位與怪物縮放。`tests/test_lucifer_art_rules.py::test_every_turn_based_demo_uses_the_octopath_battle_ui` 守住這組設定。

**D40 Boss Trial 重整與戰鬥資訊（2026-10-18）：** 依使用者要求：起始只有主角一人；城裡加冒險者公會，Mira 一開始就在，Vesper／Cael 打完各自的 Boss 後到公會等，對話即加入；公會長可讓同伴回公會等候（LEAVE_PARTY，之前 demo 沒用到）。可操作角色的美術互不重複，鎮民改成同造型的棕褐色調；召喚獸改用 Goblin Rider。怪物縮到三個 Boss 加三種小怪（刪掉 Goblin Berserker、Skeleton Grunt 兩種）。戰鬥畫面：指令選單一律貼在行動角色右下角並畫在最上層（可蓋住其他角色、怪物或血量面板）；怪物頭上只顯示名字、不顯示血條（`overhead_bars=False`），名字會往上或左右挪開，不蓋到任何角色或其他名字；怪物圖鑑打倒一次後才顯示弱點與血量，掉落物只列真的掉過的。引擎新增：`action_menu_placement="actor_bottom_right"`、`overhead_bars`、`NpcIdentity2D.starts_hidden`、bestiary 記錄 `drop:<id>`。

## D41 — 對話肖像（2026-10-22，使用者要求「對話框改成會畫頭像，事件編輯器的對話指令也加上選頭像的欄位」）

對話資料原本就有 `portrait_asset_id`，但遊戲的對話框和編輯器都沒用到。現在：

- **遊戲**（`PlayableTestRuntime._draw_dialogue`，場景、過場、即時動作與戰鬥共用）：台詞有肖像就畫出來。專案的 Message Settings 決定樣式：`portrait_style = face`（預設，肖像在訊息框左端或右端的正方形裡，文字往旁邊讓；尺寸大於訊息框時訊息框往上長）或 `bust`（人物站在訊息框上，下半身被訊息框蓋住）。`portrait_size` 是像素（face 是邊長、bust 是高度，0 = 自動：配合訊息框／畫面高度的 55%）。放大用最近鄰（像素臉不糊），縮小用平滑。縮放結果有快取。
- **台詞**：`DialogueLine.portrait_side`（`left`／`right`），DIALOGUE 指令的 `portrait_side` 只在是 `right` 時寫入；`portrait_asset_id` 可以是圖片素材、圖集的格子或專案裡的圖片路徑（png／jpg／webp）。
- **編輯器**：事件編輯器的「Dialogue」按鈕改開對話視窗（說話者、多行文字、肖像清單＋預覽＋Browse…、左右），雙擊既有的對話指令也開同一個視窗；右邊是依專案 Message Settings 畫的訊息框預覽。清單列出專案的 `portrait` 素材和任何 `portraits`／`faces`／`facesets` 資料夾裡的圖；Browse… 會把專案外的圖複製到 `<專案>/portraits/`。序列（Sequence）的對話步驟多了 `portrait_asset_id`、`portrait_side` 兩欄。指令清單會顯示用了哪張肖像。Message Settings 表單多了 Portrait Style、Portrait Size。
- **腳本**：`AuthoringEvent.dialogue(..., portrait=, side=)`、`say(..., portrait=, side=)`。

**相容：** 舊資料照常讀；沒設定就不寫入。

**還沒做：** 輕量的地圖執行器（`runtime/tilemap_field.py`，MV 匯入試玩用）的文字框不畫肖像；MV 匯入的 Show Text 臉圖還沒轉成肖像；文字不會自動換行（和之前一樣，用換行字元）。


## D42 — 戰鬥指令數字預設關閉、主角像其他角色一樣擺放、攝影機跟著主角、RPG Maker 式畫地圖（2026-10-18）

**要求：** 使用者問「行動旁邊的數字是什麼意思」後說「都沒必要 通通關掉 預設就是關掉 然後所有 demo 都拿掉」；「主角也是一個角色 應該就是跟其他角色一樣」（腳底要有位置可以自由放置）→「要 幫我加上」；「做地圖時 有類似 rpg maker 可以直接用潑的…類似小畫家…壓著滑鼠滑動就可以直接畫」→「好幫我加上」。

**做了什麼：**

| 項目 | 做法 | 位置 |
|---|---|---|
| 指令數字 | 頂層戰鬥指令只顯示名稱；版面 `command_counts` 打開才顯示數量（技能花費照常顯示）；所有 demo 都關掉 | `presentation/battle_ui.py`、`presentation/library.py` |
| Game Start | 起始場景用名稱挑（存的仍是 id）；隊伍清單顯示名字；起始位置的勾選框寫「Set position」；新場景自動取不重複的名稱（Scene、Scene 2…）；還原版面後左側面板仍回到 Project 頁 | `editor/game_start_authoring.py`、`editor/game_systems_widget.py`、`editor/scenes.py`、`editor/shell.py` |
| 主角與攝影機 | 每個 `Camera2D` 跟著起始玩家，站在玩家所在或抵達的位置；只是重複 Player 位置的起始座標會清掉，所以在編輯器移動 Player 就是移動遊戲起點；主角用和其他角色一樣的腳底碰撞框；Octopath、complex reference、party 範本每個場景都有一台跟著主角的 Camera；沒有圖塊地圖的「圖片場景」照作者設定的 Camera 取景（manifest 的攝影機設定仍優先） | `editor/scene_cameras.py`、`scripts/center_cameras.py`、`runtime/field_camera.py`、`runtime/playable_test_runtime.py` |
| 畫地圖 | Tiles 面板顯示整張圖塊集：點一格或拖曳選一塊，就用整塊畫（拖曳時無縫重複，矩形與填滿從起點對齊）；筆刷大小（`[`／`]`）放大單格的 Paint 與 Erase；右鍵從地圖吸取一格或一塊；B／G／R／E／S 切換工具；Paint 與 Erase 按住時就畫在地圖上，放開算一個復原步驟 | `editor/tile_palette.py`、`editor/tile_palette_widget.py`、`editor/tile_edit.py`、`editor/viewport_widget.py` |

**測試：** `tests/test_tile_brushes.py`（新增）、`tests/test_editor_startup.py`、`tests/test_viewport_framing.py`、`tests/test_bestiary_and_labels.py`。

**實機證據：** `d42_game_start.png`（起始場景用名稱、Set position、隊伍名稱晶片）、`d42_tiles_panel.png`（整張圖塊集、筆刷大小、快捷鍵說明）。兩張都是 2026-10-22 在 HEAD 的乾淨副本上，用 Cocoa 視窗重拍（見 D51）。

**限制：** 拖曳畫圖的手感沒有真人試過；要看指令數量得在版面打開 `command_counts`。

**狀態：** 7de1c030、ab4c3605、d3e88c2b、8b21ac9f、80851fe9。


## D43 — Boss Trial 補滿所有空的系統，改名 Full Verification（2026-10-18～19）

**要求：** 「我發現壓力測試很多東西沒做」「load json file 從引擎看很多都是空的」「之前排除的先不要，只補其他空的」→ 照五階段計畫做、每階段報告；「順便看到引擎有缺什麼就直接補」；「技能動畫 招式動畫好像都會偏離目標」；「我的技能樹都不見了…技能樹要連 icon 都要顯示在 graph」；「那四個也補上：Map Areas、New Game Plus、Translations、Music Room，都要設計並在遊戲裡用到」；「人物不要重複」；「為何現在關 gui 都會壞掉 會需要強制關掉」；「camera 中間的紅框跟綠色框是啥…不用吧」；「這裡有些看起來是畫錯…深綠色塊跟灰色的」。

**做了什麼：** 逐項內容見 [`FULL_VERIFICATION_COVERAGE.md`](FULL_VERIFICATION_COVERAGE.md)。

| 項目 | 做法 | 位置 |
|---|---|---|
| 1 空的區塊 | 戰鬥表現編排、動畫時間與通道、訊息巨集與記錄、製作人員名單、戰鬥選項、Make Camp 暫停選單項目、場景擺設、公共事件與戰鬥事件，都設計好並在劇情裡用到；導演改成依序列順序放出延遲的事件（原本延遲會讓戰鬥畫面當掉）；同伴有主副職，在 Job Master 進階（Cleric／Priest／Bishop、Necromancer／Lich／Death Lord、Cultist／Zealot／Heretic）：六個新職業、24 個技能、九棵同伴技能樹 | `presentation/battle_presentation_director.py`、demo 的 build 腳本 |
| 2 技能樹四種風格 | 共用的天賦網 Atlas of Fate（六區、名人節點、關鍵天賦、橋接、作者指定位置）；每職業三個互斥專精；每職業三個符文（換掉符文技能的變體；進化可要求標籤，編輯器可改）；每職業十級技能書（花技能點）；共 554 個節點、54 個符文技能 | `rpg/ability_build.py`、`rpg/actors.py`、`rpg/resolved_build.py`、`editor/rpg_progression_authoring.py` |
| 3 裝備與製作 | 40 件可鑲寶石與卡片的裝備；每位同伴一套（武器附魔）；七種寶石合成完美寶石；十張怪物卡；武器與防具精煉，用礦石材料、保級用 Blessed Scroll（`RefineRules.materials`、`protect_item`；裝備指令可寫 `slot:<部位>`）；更多詞條、調和、煉金與分解；每筆紀錄都有 Lucifer 包的圖示 | `rpg/refine.py`、`runtime/game_session.py`、`runtime/world_command_handlers.py` |
| 4 戰鬥類別 | 資源、格擋檢查、時間軸、序列、超限、掩護與追擊、侍僧守夜；達成目標就結束戰鬥；技能可用 `BATTLE_SEQUENCE` 叫出序列；遭遇依標籤選逃跑與場次規則；對已倒下目標的反應跳過 | `rpg/reactions.py`、`runtime/game_session.py` |
| 5 表現、技能槽、場上攻擊 | 四種戰鬥表現類別（站位範本、指令分頁、輸入步驟、絕招）在執行期讀取；技能特效的圖畫置中在目標上（修正「偏離目標」）；技能槽規則保留進化後的技能；`LEARN_ABILITY` 教技能；場上先制攻擊 | `presentation/battle*.py`、`runtime/battle_visuals.py`、`runtime/field_ai.py`、`rpg/ability_loadout.py` |
| 四個系統 | 地圖區域（在遊戲的圖塊視圖與行為樹視線裡生效）、`NEW_GAME_PLUS`、`SET_LOCALE` 與設定裡的 Language、音樂室圖示 | `runtime/map_rules_field.py`、`runtime/tile_scene_view.py`、`runtime/behavior_tree.py`、`runtime/extras_screens.py` |
| 改名與編輯器 | Boss Trial 改名 Full Verification（腳本、測試、證據資料夾一起改）；開同 id 的新專案時重建 Game Data；技能樹畫成圖示卡片加箭頭 | `editor/authoring_hub_widget.py`、`editor/image_tools.py` |
| 鎮民與家 | 鎮民各有自己的外觀（Ninja Adventure 人物，CC0），紀念碑改成雕像與靈體，寶庫改成袋子與寶箱；遊戲從 Aldric 家門口開始，進屋睡床會淡出、全隊回復再淡入 | demo 的 build 腳本 |
| 關閉時卡住 | 置中的停靠頁籤樣式包住了共用的應用程式樣式，而 `QProxyStyle` 會擁有它包住的樣式：視窗刪掉了應用程式樣式，QApplication 結束時當機，pygame 的當機處理又在那裡死結（只能強制結束）。現在代理樣式有自己的底層樣式；延後執行的編輯器呼叫綁在元件上，元件不在了就不執行 | `editor/scrolling_tabs.py`、`editor/shell.py` |
| 紅框與綠框 | 那是即時戰鬥的攻擊與受擊框，屬除錯檢視：場景視圖預設不畫，View > Show Hit & Hurt Boxes 打開才畫（碰撞框與攝影機框照常顯示） | `editor/viewport_widget.py` |
| 切半的擺設 | 樹與石頭散在 Aldric 的地上，不再事後切掉；松樹叢與十字墓碑的印章不再帶到隔壁的圖；沼澤蓋住樹下的地面 | demo 的 build 腳本 |

**測試：** `tests/test_full_verification_campaign.py`（整段劇情）、`test_full_verification_b11.py`、`test_full_verification_b12.py`、`test_refine_materials.py`、`test_battle_rules_choice.py`、`test_battle_presentation_wiring.py`、`test_town_people_and_home.py`、`test_editor_quit.py`、`test_viewport_combat_boxes.py`、`test_map_prop_stamps.py`（每個擺設印章都是完整的圖）、`test_vfx_tool.py`。

**實機證據：** [`evidence/full_verification_campaign/`](evidence/full_verification_campaign/)：整段劇情在 Cocoa 視窗跑完，先用真的按鍵走路與對話，再跑完 4 張地圖、9 場戰鬥；2026-10-22 重新產生（D51）。`d43_skill_tree_graph.png`：編輯器裡勇者技能樹的圖示卡片與箭頭。

**限制：** demo 的數值與流程是驗證用，沒有真人調過平衡；地圖區域等四個系統目前只在這個 demo 裡用到。

**狀態：** efcd352c、8c85e05d、7eb6340e、abaede66、9d415b84、71f67036、22122742、297403a7、7ae09277、6439fb23。


## D44 — 主角勇者／大魔導師、感受得到的戰鬥機制、能力值公式、武器稀有度、素材庫（2026-10-19）

**要求：** 「主角的職業改成勇者 副職業改成大魔導師…勇者可使用全部武器 大魔導師可以用所有屬性的魔法…物魔雙修…創造最複雜 最適合 最強的技能樹」；「繼續做完」；「命中應該不用 用閃避代替就好」→「物防魔防都可寫 然後還是給命中率 只是 命中迴避爆擊等等所有能力值的計算公式要寫好」；「Twin Arts 這個不要 太複雜」；武器改用 Lucifer Equipment 的武器圖與稀有度；「可以新增那個武器…把這些素材讀進去…如果沒有弓 那就另外找可以用的」。

**做了什麼：**

| 項目 | 做法 | 位置 |
|---|---|---|
| 勇者／大魔導師 | 勇者可用所有武器，力量與魔力一起成長；大魔導師可用所有屬性；兩棵樹結合技能、武器專精與元素學派、互斥的誓約與路線、專精、符文、技能書；Demon Ring 可鑲卡片、寶石與新護符，攻擊五次；怪物血量三倍、力量大幅提高 | demo 的 build 腳本 |
| 新裝備先問 | `InventoryRules.equip_offer`（never／empty_slot／always）、`GIVE_EQUIPMENT` 與詢問視窗；Aldric 起始只有 Sunbrand，寶箱裡的 Demon Ring 會問要不要戴在空著的手 | `rpg/items.py`、`runtime/game_session.py`、`runtime/playable_test_runtime.py` |
| 感受得到的機制 | 弱點 ×1.8、抗性 ×0.4、爆擊 ×2.5（有軟上限）；Boss 有 7–10 個弱點，藏在 16／24／36 層護盾後，破防 ×2.5 持續三回合；怪物會防禦與閃避，攻擊會附狀態；毒、燒、流血扣最大生命的比例；畫面顯示 WEAK、CRITICAL、BREAK、GUARD、MISS。引擎：`ClassDefinition.resource_growth`（每級加生命，在職業表單）；狀態的每回合效果與施加／移除／到期效果有公式環境（可讀最大生命比例）；`OutcomeCheckDefinition` 可依來源／目標標籤擋掉檢查（破防的敵人不能防禦）；`Battle.apply_state` 與 `resolve_targets` 用戰鬥的種子骰；浮動數字 10 以上取整 | `gameplay/states.py`、`rpg/interactions.py`、`rpg/battle.py`、`rpg/actors.py` |
| 能力值公式 | `DerivedStatRule`（Game Systems > Stat Formulas：stat += base + Σ(係數 × stat)，可設順序、下限、上限、適用對象；每次組裝最後執行）；`InteractionRule.multiplier_source_terms`／`multiplier_target_terms`（爆傷、元素）；`AbilityDefinition.description` 顯示在戰鬥選單上方。demo：命中 95% + 0.3%×命中 − 0.3%×迴避；爆擊 5% + 0.3%×爆擊，傷害 ×(2 + 1%×爆傷)；格擋只擋物理；魔法對魔防；七種元素攻擊與抗性；STR／DEX／INT／LUK／VIT 由玩家分配（Twin Arts 依使用者要求拿掉） | `rpg/derived_stats.py`、`rpg/interactions.py`、`presentation/rpg_character_screen.py`、`runtime/skill_tree_screen.py` |
| 修正 | 戰鬥把英雄算好的能力值與生命存成基礎值，所以每打完一場，成長、技能樹、裝備、被動又重加一次（數值越打越膨脹）：快照現在保留基礎值；沒人能行動的回合不再卡住；怪物在自己的回合死掉時直接勝利 | `rpg/resolved_build.py`、`rpg/battle.py` |
| 武器圖與稀有度 | `EquipmentDefinition.rarity`（選填），背包依它上色與命名；每把武器對上一張完整的 32×16 Lucifer 武器圖（原本有八張被當成動畫條帶，只切了左半）；Common／Rare／Legendary 依圖決定，另加 Mythic（不會隨機出現）給 Godhammer 與 Demon Ring；Aldric 的 Sunbrand 是 Rare Greatsword | `rpg/items.py`、`runtime/bag_screen.py` |
| 素材庫 | `asset_library/foozle`：35 個 CC0 Foozle 像素包（11 MB；Old Castle 圖塊集的授權不是 CC0，不收；音樂、向量、金礦、寶箱、機器人包也不收）；`asset_library/opengameart`：HomoHikka 與 Falco276 的 CC0 弓；`asteria.assets.library`（包、圖、授權、匯入專案成為資產紀錄）；File > Import from Asset Library…（縮圖、篩選、授權，一個復原步驟）；Titan Cleaver（Mythic 斧，Ancient Skeleton 必掉）；Hunter's Bow 與 Longbow 用 HomoHikka 的弓加稀有度外框 | `assets/library.py`、`assets/registry.py`、`editor/asset_library_dialog.py` |

**測試：** `test_brave_archmage.py`、`test_equip_offers.py`、`test_rpg_interactions_blocked_checks.py`、`test_derived_stats.py`、`test_full_verification_stats.py`、`test_full_verification_weapons.py`、`test_asset_library.py`、`test_gameplay_states.py`、`test_battle_ui_renderer.py`。

**實機證據：** 劇情在 Cocoa 視窗跑完時計到 39 次爆擊、70 次閃避、40 次防禦、3 次破防、78 次狀態扣血、2 次裝備詢問（`evidence/full_verification_campaign/results.json`）；`d44_stat_formulas.png`（Accuracy = DEX×1 + LUK×0.5）、`d44_status_screen.png`（遊戲內狀態畫面：STR／DEX／INT／LUK 與各項衍生能力值）、`d44_asset_library.png`（素材庫視窗，授權 CC0 1.0）。

**限制：** 平衡只針對這個 demo，沒有真人調過；Mythic 不會隨機掉落；素材庫只收 CC0；遊戲內狀態畫面把 MP 排在 HP 上面（和 HUD 相反，見 D51）。

**狀態：** 2eb11637、6b37995a、c5fd5b3d、0147e26b、940bbeca、794c2ca6。


## D45 — 編輯器表單全面改寫（2026-10-19～20）

**要求：** 「先幫我 gui 都改好 現在全部的這種表格都根本太難懂…可以用列表 以及排版好一點…能自動就自動填寫…不只 database 全部…改成比 rpg maker 簡單」；「gui 很多描述都幫我改清楚一點…預設直接改成 full_verification…ability evo 太難懂…商店這個為何要有 item:」；「jobs 那邊排版很爛…整體幫我檢查」；「再幫我重新檢視一次所有的 gui 操作 全部 仔細的…不要我在自己看」。

**做了什麼：**

| 項目 | 做法 | 位置 |
|---|---|---|
| 紀錄表單 | `record_form.py` 取代 Game Data、Battle Rules、Battle Screen、Runtime UI 原本的欄位／值樹：名稱與圖示標頭、分區、數字框（機率以 % 顯示）、每個參照都是附圖示的下拉選單、標籤晶片附建議、兩欄的能力值表、條目卡片（新增、複製、移動、刪除，自動填 id）、空的選填欄位收起來、內部欄位放在 Advanced、每個欄位都有提示 | `editor/record_form.py` |
| 詞彙 | `record_vocabulary.py`：欄位指向什麼、專案裡用到的能力值、資源、標籤與值；固定值的欄位讀引擎自己的檢查 | `editor/record_vocabulary.py` |
| 邊改邊套用 | 停止輸入 0.35 秒後透過可復原的指令套用；錯的值顯示紅色且不套用；紀錄清單顯示名稱與圖示、可依名稱篩選；Game Systems 與 Game Start 也邊改邊套用 | `editor/game_systems_widget.py`、`editor/game_start_widget.py` |
| Inspector | 顯示實體的名稱、開關與每個元件，都可以編輯 | `editor/widgets.py` |
| 白話 | 標籤、觸發、技能進化用文字表達；商店的「Sold Only When」與「Price Changes」改成條件列（不用再寫 `item:`／`switch:`）；參照挑選器顯示名稱；Full Verification 成為第一個範本，也是編輯器預設開啟的起始專案；Sprite Animation 依「畫的是誰」命名，有縮圖與搜尋，片段寫成「Standing, facing left (5 frames, loops)」；角色依大部分方向都有的條帶走路 | `editor/record_form.py`、`editor/project_templates.py`、`editor/animation_editor_widget.py` |
| 整齊 | 清單卡片的欄位並排、以名稱為標題，空的與技術欄位收進一個「More」；勾選框帶著自己的標籤；縮寫用大寫；商店條件、價格規則與任務目標都是卡片；表格與群組不再被高度擠壓（Add 按鈕與框線不再重疊） | `editor/responsive_form.py`、`editor/theme.py` |
| 全編輯器檢查 | 每個清單（Game Data、Game Systems、Enemy AI、Ability Timelines、Behavior Trees、Controls、Real-Time Combat、精靈表）顯示名稱，id 放在提示；指名貨幣、資源、能力值、敵人、開關或資產的文字欄位改成挑選器；固定選項與數字用文字和一般數字（1，不是 1.000）；「+ Add item／skill／quest」說出新增的是什麼；語言用自己的名稱列出；空白狀態說明要做什麼；New／Duplicate 建議 id；捕捉規則可複製到其他敵人；Game Systems 的 Duplicate 對 Battle Extras、Refine、Translations、Message Settings 不再失敗（有回歸測試）；每個動作錯誤都會回報；退役的表單頁留到 Qt 刪除為止（不在處理點擊時釋放） | 多個 `editor/*_widget.py` |

**測試：** `test_record_form.py`（新增）、`test_game_systems_duplicate.py`（新增）、`test_game_systems_editors.py`、`test_shops_and_quests.py`、`test_project_templates.py`、`test_generic_character_inspector.py`、`test_animation_and_timeline_editors_gui.py`、`test_character_composition.py`、`test_event_flow_integration.py`、`test_editor_icons_and_decor.py`。

**實機證據：** `d45_game_data_form.png`（Aldric 的紀錄表單：標頭、分區、兩欄的 Base Stats、標籤與技能晶片）；2026-10-22 在 HEAD 重跑的整份編輯器稽核見 D51。

**限制：** 少數進階欄位仍在 Advanced 裡以原始值編輯；當時的「SP」名稱在 D47 改成 MP。

**狀態：** e9ff4bdf、638d86e1、8523806f、fdf37c2d。


## D46 — 編輯器與技能樹不再卡（2026-10-19～20）

**要求：** 「技能樹都會卡卡」；「為何這個圖大小會偏掉 然後…gui 都會卡卡的 尤其在切換大項目 data、battle 這需要處理」；「技能樹很卡」。

**做了什麼與量測：**

| 項目 | 做法 | 量測 |
|---|---|---|
| 遊戲內技能樹 | 沒有存位置的樹，原本每畫一個節點、每條線都重算一次佈局（每幀走遍所有前置）；現在每張圖只算一次，改過才重算 | Full Verification 職業樹每幀 15–23 ms → 約 2 ms |
| 切換工作區 | 專案自上次顯示後有改才重建；`refresh_all` 只重建畫面上的那一個，其他打開時再建（切換專案仍全部重建）；圖片快取跨重新整理保留（檔案變了才重讀）；圖示清單每份文件共用；下拉詞彙每個專案版本共用；表單拿到同一筆紀錄就保留自己 | 切到 Game Data／Presentation 350–550 ms → 80–95 ms；編輯後重新整理約 950 ms → 50–220 ms |
| Skill Trees 頁 | 技能樹先開圖，表單（50 個節點的樹有上千個欄位）到切到資料檢視才建；超過 8 項的清單一次展開一項；圖示挑選器在打開或搜尋前只放自己的圖示 | 打開 24 s → 0.25 s；選一棵樹 20–30 s → 0.1–0.3 s；切到資料檢視 33 s → 0.2 s |
| 預覽偏掉 | Character Composition 的預覽在顯示或改變大小時重新對準 | — |

**測試：** `test_record_form.py`、`test_arpg_builds.py`。

**實機證據：** 編輯器的量測在 offscreen 平台上做，沒有另外在 Cocoa 視窗量；遊戲內技能樹的量測在遊戲執行期。

**限制：** 第一次開專案仍要建 Game Data、Battle、Presentation（啟動後就先建好）。

**狀態：** 218aef5a、23335f05、73c75a1f。


## D47 — 編輯器逐頁排版、HP 在 MP 上面、BP 金色圓點（2026-10-20）

**要求：** 「rolled value 排版有問題 start pets 排版有問題 文字壓到邊框」；「這邊排版還是跟其他地方不同」；「還是一樣啊 格子都重疊了」；「排版都歪掉了 base status 跟右邊的能力值都歪歪的…type 跟下方框框也太近…每個介面 都檢查一次」；「這個 icon 文字不明所以」，並要做一個顯示框；「幫我把 HPSP 上下順序反向 然後戰鬥的 BP icon 可以改成金色圓圈嗎」「全部的 SP 都換成 MP」。

**做了什麼：**

| 項目 | 做法 | 位置 |
|---|---|---|
| 表格 | Real-Time Combat 的列表每列依最高的欄位決定高度（原本 30 px 會切到數字框與清單），勾選框置中；格子裡的清單不比欄寬（Op 清單原本溢到下一欄）；窄格顯示完整數字（不放箭頭） | `editor/combat_workspace.py` |
| 群組與勾選框 | 群組標題畫在框線上方；Game Systems 的表格與群組（Starting Pets、Stock、Reward、Objectives…）用和其他欄位一樣的標題；所有勾選框用編輯器的顏色；macOS 的版面用較窄的 layout rect 擺勾選框，文字跑進旁邊的數字框（Start X／Y 的 Set position）→ 改用實際大小，框與字距 8 px、到數字框 12 px | `editor/theme.py`、`editor/decor.py`、`editor/game_systems_widget.py` |
| 對齊 | 數字框 26 px，和文字框、下拉選單一樣高（箭頭較小）；表格標題（Base Stats）和提示同一行；欄位上方的標題離框 4 px（y、g 不再碰到框）；刪除鈕和框一樣高；可輸入的清單文字和標籤對齊；Game Adapter 框與標題對齊、示範按鈕在下方；標頭與種類清單寬到放得下最長的名稱與圖示；Region id 框 26 px | `editor/record_form.py`、`editor/ui_fit.py`、`editor/multiplayer_workspace.py`、`editor/tile_palette_widget.py`、`editor/authoring_hub_widget.py` |
| 偶發當機 | 頁面裝飾每次顯示頁面都用 `QLayout.itemAt` 走版面，每次留下一個版面項目的 Python 包裝；Qt 刪掉那個項目後（表單重建、復原），過期的包裝會在之後隨機的地方讓編輯器 segfault。改成不用 `itemAt` 讀版面（`ui_fit.layout_widgets`／`layout_children`）。原本 6 次有 3–4 次當掉的種子，現在每次都通過 | `editor/decor.py`、`editor/ui_fit.py` |
| 圖示欄位 | 「Icon」標題和清單同一行；圖放在有框的方塊裡（沒有圖示時寫 None）；圖示資料夾外的圖片（`playable_assets/...`）也顯示；不是圖示資產的 id 回傳 None，不會出錯 | `editor/game_systems_widget.py`、`editor/image_tools.py` |
| HP／MP／BP | 紀錄的資源 HP 排在 MP 前；technique 資源在編輯器與每個附帶的專案都叫 MP（戰鬥 HUD、角色畫面、技能說明）；戰鬥 HUD 的資源樣式有 `color` 欄位（空白＝主題色，HUD 表單可改）；pips 畫成圓點，空的是暗圈；demo 的 BP 是金色；空的顏色欄位寫「Theme colour」 | `presentation/battle_hud.py`、`presentation/battle_ui.py`、`presentation/battle_ui_renderer.py`、`platform/pygame_battle_ui.py`、`editor/record_vocabulary.py` |
| 程式碼整理 | 全 repo `ruff check` 與 `ruff format` 乾淨（demo 腳本 7 個舊問題，9 個檔案重新格式化；行為不變） | — |

**測試：** `test_editor_icons_and_decor.py`（版面走訪的回歸測試）、`test_full_verification_stats.py`；排版用像素量測與 Cocoa 截圖檢查。

**實機證據：** `d42_game_start.png`（Set position 勾選框與數字框）、`d45_game_data_form.png`（Base Stats 和提示同一行）、`evidence/full_verification_campaign/battle_*.png`（HP 在 MP 上面、BP 金色圓點）。

**限制：** 只在 macOS 看過；2026-10-22 的稽核還有兩處文字被截（見 D51）。

**狀態：** e5e3beb0、56834267、9c7d96ec、ac1b264f、7a78784a、6d24f364、948fb8d6、e6099873、a8b82da5。


## D48 — 執行期效能：給 MacBook Air 與輕量電腦（2026-10-20～22）

**要求：** 「你覺得現在還有什麼地方需要優化嗎 然後 kernel 部分需要增加嗎 多用一些 c++ 提升性能」→「先做第 1 步：碰撞世界改成只更新有動的物件（Python），量測前後差異」；「然後繼續優化 kernel」；「能改就改 因為我是用 macbook air 跑 而且我也打算給輕量化電腦用…處理在底層 保留上層簡單的 python coding 給使用者」。

**決定變更：** D34 決定不替 `CollisionWorld.from_scene` 做快取；使用者 2026-10-20 核准改做。做法是「跟著場景就地更新，做不到完全一致就重建」，測試確認跟著更新的世界對每個點與方框查詢的答案，都和重新建的一樣。

**做了什麼與量測：**

| 項目 | 做法 | 量測 |
|---|---|---|
| 碰撞世界 | `CollisionWorld.follow(scene)`：移動或改大小的碰撞器就地更新（只動自己的格子）；換場景、增刪、啟用或停用、掛父物件、圖層／遮罩／種類／旗標改變時拒絕並重建；`field_update` 跟著世界，不再每幀重建兩次；點與方框查詢直接讀欄位，不再替每個候選建形狀物件 | 場上基準（50 個 AI 怪）每幀 7.3–8.0 → 6.1 ms（AI 4.8–5.0 → 3.4、碰撞 0.72–0.79 → 0.42） |
| 基準本身 | ARPG 壓力與執行期基準原本開著 tracemalloc，每次 Python 配置慢約 40 倍（300 敵、500 投射物的一幀讀成 12 ms，實際約 2 ms），熱點也會看錯；現在不追蹤 heap | — |
| 牆擋移動 | `blocked_boxes` 一次做完寬相位與阻擋測試（C++ 一次完成） | ARPG 壓力的碰撞 1.02 → 0.91 ms |
| 少做重複繪製 | 九宮格面板每個大小組一次再整張貼；HUD 文字每個字串、大小、顏色畫一次；戰場背景在攝影機不動時只縮放一次；沒有視差背景時，最底層圖塊畫在填了背景色的不透明畫布上 | 戰鬥繪製約 3.5 → 3.0 ms；圖塊 1.73 → 0.93 ms；逐像素比對相同 |
| 換音樂 | pygame 的 `music.load` 會等淡出的音樂靜音，每次換音樂就凍住淡出的時間（量到 540 ms）；改成排在後面，舊的一停就開始，交接中停止會取消 | 凍結消失 |
| C++ kernel 不需 numpy | 緩衝區用 `array.array` 進 C++；沒移植的退回 numpy（有裝）或 python；macOS 編成 arm64＋x86_64、最低 macOS 11（原本標成編譯機的版本，舊 Mac 載不進來）；匯出的 .pyz 解開後載入 | 只裝 pygame 的機器：ARPG 壓力每幀約 1.9 ms（python 版 3.3 ms） |
| 戰鬥圖預先解碼 | 工作執行緒在場上時解碼下一場戰鬥可能用到的圖（隊伍、背景、這張地圖的怪、特效，再來其餘），主執行緒每幀轉換約 1 ms；上限 manifest `battle.preload_mb`（預設 64，0 關閉），只在真實視窗執行 | 開戰那一幀 36–48 → 10–18 ms；第二場不用再解碼；戰鬥畫面逐像素相同 |
| HUD 只在變化時排版 | `_hud_commands`、`_action_menu_commands` 保留上次的結果，輸入（成員、陣營、站位、焦點、名字、高度、版面，以及有頭上標籤時每個角色的螢幕位置）變了才重排 | 組 HUD 每幀 0.134 → 0.037 ms；900 幀錄製戰鬥逐像素相同 |
| 場上 AI 批次 | 沒有 `CharacterController2D` 的怪一次走完：新 kernel `fieldai_free_step`、`points_blocked`（python／numpy／C++）；C++ 移植 CPython 的 `math.hypot`，結果逐位元相同；亂數順序不變 | 50 隻史萊姆的場上 AI 0.45 → 0.13 ms（native） |
| 匯出必帶 kernel | `build_native.problem()`／`ensure()` 在新的程序裡檢查程式庫（已編、載得進來、ABI 對、比原始碼新），不行就重編，編好再換上；匯出只帶通過檢查的，不能編時警告（CLI 與編輯器）但不失敗 | — |
| 首幀 | `PlayableTestRuntime.open()` 先載入 kernel 與場上模組 | 第一個場上幀 55–68 → 18–24 ms |
| 指令列 | 戰鬥指令選單原本在英雄回合每幀重建；行動者、選單、花費與負擔得起的都沒變就保留 | `_show_commands` 0.97 → 0.15 ms；技能清單開著時 1.53 → 0.65 ms；900／2400 幀戰鬥逐幀相同 |
| 戰鬥圖與面板 | 戰鬥角色的每一格依大小與翻轉只縮放一次，只貼看得見的部分（加法與旋轉繪製走原路；上限約 24 MB）；一般戰鬥 UI 面板依大小、顏色、圓角、邊框畫一次 | 技能清單開著：幀中位數約 2.5 → 1.6 ms，繪製 1.5 → 0.85 ms；與舊繪製逐像素相同 |

Kernel ABI 從 2 升到 5（`blocked_boxes` 3、不需 numpy 4、場上 AI 5），升級後要跑 `python -m asteria.kernels.build_native`；三套 kernel（python／numpy／native）在壓力測試給出相同的狀態摘要。

**測試：** `test_collision.py`、`test_native_kernels.py`、`test_kernels.py`、`test_ui_skin.py`、`test_skeleton_component.py`、`test_audio_mixer.py`、`test_image_preloader.py`、`test_battle_ui_layout_cache.py`、`test_field_ai_batch.py`、`test_migration_and_export.py`、`test_battle_command_rows.py`、`test_battle_sprite_blits.py`。

**實機證據：** 量測是 headless，或在同一個程序裡交替跑新舊程式碼（真實視窗的時間會被合成器的 vsync 吃掉，看不出差別）；整段劇情在 Cocoa 視窗跑完（D51）。

**限制：** 沒有在真的輕量電腦或低耗電模式下量過（本機 `pmset` 的 lowpowermode 是 0）；不透明畫布在 macOS 截圖裡留下透明的地面，2026-10-22 修正（D51）。

**狀態：** 72bf87ee、5ba59175、84d01ecb、3069284a、6661c299、aa94ee8a、4175570f、0cc71d83、f6d8f0fa、4ba13ab4、8c6fcab4。


## D49 — 選單游標自動對齊、頭上名字不蓋到任何角色（2026-10-20～22）

**要求：** 「這個選取箭頭會歪掉 command 要修正 要能夠自動對準」；「在 command 選取技能時 可能因為字太大加上 icon 會讓選取框框直接蓋到文字 icon…那個箭頭是全部 command 都要改 都不能是偏掉的…進入戰鬥會有一個 zoom in 怪物的 這時候怪物名字會因為 zoom in 疊在怪物身上…我不要有任何文字跟怪物重疊」；「不是為了不要擋到怪物圖 就放在超奇怪的地方 不然就不要放」。

**做了什麼：**

| 項目 | 做法 | 位置 |
|---|---|---|
| 游標 | 所有選單游標改成畫出來的三角形，置中在該列文字大寫字母的高度（原本是像素字型沒有的符號，改由別的字型畫，就偏低又偏旁）：戰鬥指令與流程選單、場上選單（設定、按鍵、製作、商店、技能槽）；每列標籤從同一欄開始，不論有沒有游標 | `platform/pygame_battle_ui.py`、`presentation/battle_ui.py`、`runtime/playable_test_runtime.py`、`runtime/extras_screens.py` |
| 技能圖示 | 圖示放在選取框裡，在列中垂直置中 | `presentation/battle_ui.py` |
| 類別列 | 指令選單的類別列顯示目前的類別與放得下的鄰居，超出邊緣用 < 與 >，不再跑到 HUD 底下 | `presentation/battle_ui.py` |
| 頭上名字 | 依角色待機姿勢看得見的像素與攝影機縮放量出外框，名字不蓋到任何角色（包括自己）；只放在主人附近（頭上、腳下那一排、頭旁），放不下就不顯示；攝影機拉近時（Boss 開場）與動作播放時先不顯示 | `presentation/battle_ui.py`、`presentation/battle_screen.py`、`runtime/battle_presentation_adapters.py` |

**測試：** `test_battle_overhead_labels.py`（新增 6 項：名字不蓋人且在主人附近、沒有位置就不顯示、拉近時等待、拉近時角色外框跟著變大、類別列在選單裡、場上游標與文字同高）、`test_battle_premium_adaptive_ui.py`（scale 1／2／3 游標置中）、`test_battle_action_menu_presentation.py`、`test_bestiary_and_labels.py`。

**實機證據：** `evidence/full_verification_campaign/battle_*.png`（指令選單游標、頭上名字）；`d49_skill_menu.png`（技能清單：圖示在選取框裡、游標）；`d49_settings_menu.png`（場上設定選單的游標與文字同高）；`d49_intro_zoom.png`（Boss 開場拉近時名字先不顯示）。

**限制（2026-10-22 重拍時發現，還沒修）：**
- `d49_intro_zoom.png`：拉近時名字有等，但頭上的狀態文字（Stance Bulwark Ward）還是顯示，而且壓在 Boss 身上，違反「不要有任何文字跟怪物重疊」。
- `d49_skill_menu.png`：選中那一列的名稱和花費黏在一起（「Guard Stance6MP」）；原因還沒查（選單用字數估算寬度，可能是像素字型的大寫字比估計的寬）。
- 名字超過 14 個字會縮成縮寫（「Goblin Slinger 2」→「GS2」、「Skeleton Acolyte」→「SAcolyte」），要怎麼顯示等使用者決定。

**狀態：** 351ecc26。


## D50 — 編輯器繁體中文（2026-10-20～22）

**要求：** 使用者問「要做中文版嗎」並指定「編譯器介面」（編輯器的介面）；之後「繼續做編輯器中文化」。

**做了什麼：**
- English 仍是預設，也是程式碼裡寫的文字；View ▸ Language 即時切換，記在 QSettings `editor/language`。
- `editor/i18n.py` 在元件顯示文字的地方翻譯：標籤、按鈕、標題、頁籤、選單、提示、placeholder、表頭、訊息框、固定選項。英文原文存在元件的動態屬性裡，所以可以切回英文、不用重開。`english()` 反查讓依標題挑圖示、按鈕樣式或停靠面板的程式碼仍比對英文。
- `editor/translations/zh_TW.json`：約 2,500 條完全比對，加 31 條正規式樣板，處理執行時才組出來的文字（例如「Actors · 5 records」→「角色 · 5 筆資料」、「+ Add stat」→「+ 新增屬性」）；CJK 旁用全形標點，選單助記鍵保留「(&F)」。
- 作者輸入的東西絕不翻譯：名稱、id、描述、文字框、資料的清單與表格。
- UI 稽核（`scripts/editor_ui_audit.py`）在任何語言下都用英文命名頁面。

**測試：** `test_editor_i18n.py`（5 項：比對與樣板、元件即時切換與切回、固定選項會翻而資料不翻、儲存的語言與回退、整個編輯器視窗即時切換）。

**實機證據：** `d50_zh_game_data.png`（中文介面的 Game Data：選單、工具列、頁籤與欄位標題是中文，Aldric、STR、技能名稱等資料保持英文）；中文稽核的數字見 D51。

**限制：** 顯示的字就是存檔值的固定選項還是英文（Enemy AI 的條件、動作、目標，事件觸發 Action／Autorun／Parallel，VFX 的錨點與混合模式），要改程式把顯示與值分開；遊戲內玩家看到的文字不在這一批，另開 session 處理。

**狀態：** 088d0127。


## D51 — 文件補齊、實機截圖歸檔、截圖透明的修正（2026-10-22）

**要求：** 「都 commit 然後還有什麼要做」→「先在這裡補文件：DECISION_LOG、ENGINE_HANDBOOK、NEXT_STEPS，還有實機截圖歸檔」。

**做了什麼：**
- D42–D50 補進本檔（D40 之後的 50 個 commit）；`ENGINE_HANDBOOK.md` 與 `NEXT_STEPS.md` 更新到現況；`FULL_VERIFICATION_COVERAGE.md` 開頭的「範圍外」更正（地圖區域、New Game Plus、翻譯、音樂室在 2026-10-18 已經補上）。
- **截圖：** 這個資料夾同時有其他 session 未提交的改動，所以不用工作目錄，而是把 HEAD（8c6fcab）匯出成乾淨副本、加上下面的修正，在 Cocoa 視窗重拍。新增 `evidence/real_machine/d42_*`–`d50_*`；整段劇情的證據 `evidence/full_verification_campaign/` 重新產生。舊的 `battle_crypt_patrol.png` 是 10/19 以前的流程留下的，目前的劇情不會拍它，所以移除。
- **修正：** 重拍時，地圖截圖的地面是透明的（看圖程式顯示成白色）。原因是 D48 的不透明圖塊畫布：在 macOS 視窗的像素格式（有 alpha 位元組）下，有透明度的圖塊貼到畫布上會把 alpha 寫成 0。視窗畫面本身正常（不看 alpha），但 `capture()` 存下的截圖地面是透明的；headless 的畫面格式沒有 alpha，所以測試沒抓到。現在畫布畫完後，用一次 `BLEND_RGBA_MAX` 把 alpha 補成 255：RGB 不變，每幀約多 0.01 ms，只在有 alpha 位元組的格式才做（`runtime/tile_scene_view.py`）。
- **確定性：** 同一場腳本戰鬥（boss_room，900 幀）固定精煉的亂數後，連跑 6 次逐幀相同。先前看到的差異來自戰鬥前的精煉：戰鬥外的精煉每次用新的亂數，這是設計；測試與重播可以設 `game.refine_rng`。

**測試：** `tests/test_tile_layer_alpha.py`（新增：有 alpha 位元組的畫面，在不透明圖層之後仍然全部不透明，顏色和沒有 alpha 的格式相同；修正前失敗 `{0} == {255}`）。修正前 HEAD 的完整測試 3096 通過、1 略過。修正後在乾淨副本（HEAD＋修正）跑完整測試：3058 通過、40 略過、0 失敗；其中 39 項需要 git 忽略的 `local_reference/` RPG Maker MV 素材，這 9 個測試檔另外在工作目錄跑，54 項全過；剩下 1 項是本來就略過的「這個平台沒有鍵盤焦點」。

**實機證據：**
- 劇情：Cocoa 視窗 PASS（真的按鍵走路與對話、4 張地圖、9 場戰鬥），21 張圖全部不透明。
- 編輯器稽核（Full Verification 專案、Cocoa、56 頁）：`d51_editor_audit.json`。英文 1600×1000：1 處文字被截、38 頁要上下捲、1 個表格要橫捲；英文 1100×700：1 處被截、49 頁要上下捲、2 個表格要橫捲；中文 1600×1000：1 處被截、38 頁要上下捲；中文 1100×700：0 處被截、49 頁要上下捲、1 頁要橫捲、2 個表格要橫捲。

**限制（發現但還沒修）：**
- 編輯器：Map Rule Sets 的背景圖路徑（`playable_assets/battle_bog.png`）少約 20 px 被截；1100×700 時 Battle 頁的「When its turn comes」少 4 px。
- 戰鬥：拉近時狀態文字壓在 Boss 身上、選中技能列名稱和花費黏在一起（見 D49）。
- 遊戲內狀態畫面 MP 排在 HP 上面（`d44_status_screen.png`），和 HUD 與編輯器相反。
- `tests/test_skeleton_component.py::test_editor_scene_viewport_advances_attached_skeleton_preview` 單獨跑會失敗，先跑 `test_editor_startup.py` 就通過（完整測試也通過），是既有的測試順序依賴。

**狀態：** 這一批的 commit（使用者同意後提交）。


**D51 補充（同日，使用者要求「修 D51 發現的問題」）：**

| 問題 | 做法 | 位置 |
|---|---|---|
| 拉近時狀態文字壓在 Boss 身上 | 名字畫在頭上的成員，狀態文字只跟著名字出現：名字在等（攝影機拉近、動作播放）或找不到位置時，狀態文字也不畫。哪些成員的名字在頭上，由 `placement_by_member` 與版面的 `overhead_zones` 算出；其他版面的狀態文字位置不變 | `runtime/battle_extras.py`（`caption_follows`）、`runtime/playable_test_runtime.py` |
| 選中的技能列名稱黏花費 | 選中的列字型大一號，花費的數字與大寫也比平均字寬（每格 3.8）寬，原本的估算沒算到。現在依畫出來的樣子估：名稱每格 4.2、花費每格 4.6，中間留一格；選單寬度也照這樣算，放不下才截短 | `presentation/battle_ui.py`（`_row_units`） |
| 狀態畫面 MP 在 HP 上面 | `CharacterScreenProfile.resource_order`（選填，編輯器的表單可改，沒設就不寫入）；沒設定時，遊戲的倒地資源（`knockout_resource_id`，HP）排第一，其餘照名稱 | `presentation/rpg_character_screen.py`、`runtime/status_menu.py` |
| 編輯器兩處被截 | 下拉選單的建議寬度放得下最長的選項（上限 280 px），卡片等寬格子裡的下拉選單最小寬度也放得下（上限 220 px）；手打的檔案路徑只顯示檔名，完整路徑在提示裡 | `editor/record_form.py`、`editor/game_systems_widget.py` |
| 測試順序依賴 | 骨骼預覽的計時器在第一次繪製時才啟動；新的 QApplication 的第一個視窗要多幾輪事件才會畫，測試只等了一輪。改成最多等 2 秒到計時器啟動（功能本身沒問題） | `tests/test_skeleton_component.py` |

**測試：** `tests/test_battle_text_room.py`（新增：拉近時狀態文字跟著名字一起等；Aldric 的 21 頁技能清單，每一列的名稱都不碰到花費，用戰鬥字型實際量、以選中列的大一號計算）、`tests/test_character_screen_resource_order.py`（新增：順序規則、只在有設定時寫入、Full Verification 狀態畫面 HP 在 MP 上面）、`tests/test_skeleton_component.py`（單獨跑連續 3 次都通過）；`tests/test_battle_ui_layout_cache.py` 的對照組也複製 `text_width`。同一個工作目錄裡還有另一個 session（遊戲內建字詞，D52）未提交的改動，所以在「工作目錄快照＋這些修正」的副本跑完整測試：3096 通過、40 略過（39 項 RPG Maker MV 需要 `local_reference/`，1 項沒有鍵盤焦點）、0 失敗；套回工作目錄後再跑一次完整測試（含 MV 素材）：3135 通過、1 略過。

**實機證據：** `d51_intro_zoom_fixed.png`（拉近時 Boss 身上沒有任何字）、`d51_skill_menu_fixed.png`（每一列名稱和花費之間都有空隙）、`d51_status_screen_fixed.png`（HP 第一、MP 第二）；編輯器稽核 `d51_editor_audit_fixed.json`：英文與中文、1600×1000 與 1100×700，被截的文字 0 處，其餘提示和修正前相同。

**限制：** 頭上名字超過 14 字的縮寫（GS2）等使用者決定；選單太窄時名稱仍會截成「..」（至少留一個字）。


## D52 — 遊戲內建字可翻譯：繁體中文（2026-10-22）

**要求：** D50 做了編輯器中文；這一批是玩家看到的那一半：引擎自己畫的每個字都要能透過專案的翻譯表翻譯（也能改名），讓 Asteria 做的遊戲可以用繁體中文顯示；沒有翻譯表的專案畫面不能變；中文要放得下、游標要對齊；驗證放在原本的 Full Verification demo（使用者選擇）。

**做了什麼：**
- **鍵值表**（`rpg/built_in_text.py`）：337 個鍵、依畫面分 27 組（標題、野外、對話、暫停、遊戲結束、設定、按鍵設定、存檔、狀態、任務、商店、製作、成就與圖鑑、訊息紀錄／音樂室／製作人員、技能欄、寵物、戰鬥指令、指令不能用的原因、戰鬥、捕獲、勝利、裝備背包、技能樹、動作 HUD、角色養成與工坊（測試用畫面）、連線合作），每個鍵附它畫出的英文。完整清單 `docs/BUILT_IN_TEXT_KEYS.md`（`scripts/built_in_text_keys.py` 產生）。
- **畫面**：`playable_test_runtime.py` 與它的畫面模組（`game_menus`、`battle_commands`、`battle_presentation_adapters`、`battle_extras`、`extras_screens`、`pets_screen`、`bag_screen`、`skill_tree_screen`、`status_menu`、`save_slots`、`input_rebinding`、`hud_bottom`、`action_play`、`network_bag_screen`、`victory_screen`）、`rpg/victory.py` 的結算頁、`presentation/battle_ui.py`（篩選、Ready、階級）、`presentation/battle_result.py`（勝利／戰敗標題）、`game_session.py`（指令不能用的原因、逃跑原因、壞掉／撿到的通知、過量擊殺）都改成 `game.tr(鍵, 英文)`。內部 id 不變：戰鬥分類「Attack／Skills／Items」仍是 id，只有畫出來的名字經過翻譯（`BattleCommands.category_label`）。勝利頁的金色行改用 `AftermathPage.highlights`，不再比對「Level」「Learned」開頭的英文。
- **專案自己的名稱**：Command Menu Pages 的名稱（`battle.layer.<指令 id>`）、技能分組（`battle.group.<名稱>`）、暫停選單自訂項目（`pause.entry.<id>`）、按鍵設定的動作名稱（`controls.action.<id>`）也能翻，沒寫就照專案寫的。
- **規則拒絕的訊息**：`Words`（帶著鍵的訊息）；商店的買不起／庫存不足／背包放不下／不夠賣改用它丟出，`str()` 仍是原本的英文，畫面用 `translated()` 顯示譯文。
- **引擎附的繁體中文**：`rpg/built_in_text/zh-TW.json`（337 個鍵全有，`{...}` 與英文一致；隨套件發布）。
- **編輯器**：Game Systems ▸ Translations 的表單改成翻譯頁（`editor/translation_table.py`）：依畫面分組列出全部內建字與英文，加上專案自己的名稱與自訂鍵；可搜尋、篩選（全部／未翻譯／已翻譯／引擎／專案）、「填入空白列」（引擎的繁中）、新增／移除鍵；空的文字不會存進表（存了會讓遊戲畫出空白）。窄視窗時按鈕換行、三欄依比例分寬。介面字串都有 zh_TW。
- **中文排版**：`presentation/text_cells.py`：全形字算 2 格、ASCII 長度不變；戰鬥選單寬度、名稱縮寫、頭上名稱、分類列、側欄狀態縮寫、回合條、說明框換行（中文字與字之間可換行，句讀不放行首）、破防格子與狀態字都改用格數。字型：戰鬥畫面的中文字級 = UI 字型實際的 em（`point_size`，以前沒乘 skin 的 `font_scale`，demo 的像素字型下中文大了 1.6 倍）；選單等主畫面 = 英文字型行高的 1.25 倍（以前同字級時中文大了約 45%）；中文垂直置中在英文大寫字母的中線（`glyph_shift`），選單游標與中文同高（置中擺放的標題與提示不超出英文那一行的上緣，不貼邊框）；`text_width` 改用實際畫中文的字型量寬度；野外浮動文字也會用中文字型；skin 字型本身有中文時直接用它。
- **效能**：`Localizer` 的語系鏈快取起來、`GameSessionRuntime.localizer` 只建立一次。Full Verification Boss 戰 129 列指令每幀 0.47 → 0.50 ms。
- **Demo**：Full Verification 的 zh-TW 表加入引擎的繁中與 demo 自己的指令名稱、技能分組、暫停選單項目與按鍵動作（`trial_world.py` 的 `MENU_ZH`，`project.asteria.json` 只改了 zh-TW 表）；預設仍是英文，學者 Lin 或 設定 ▸ 語言 可以切換。

**測試：** `tests/test_built_in_text.py`（21 項）：掃描原始碼，畫面用的每個鍵都在清單裡且英文一致、清單裡的每個鍵都有畫面在用；引擎繁中涵蓋每個鍵且佔位符一致；沒有翻譯表時戰鬥指令、提示與逃跑原因是英文；翻譯表一個鍵就改掉畫出的字（id 不變、沒寫的鍵維持英文）；預設語系的表可改名；指令頁名稱與技能分組；勝利頁與設定的開／關；商店拒絕訊息；暫停、設定、標題、遊戲結束畫面畫出中文；全形字寬、切字與換行（英文換行和舊算法逐字相同）；中文戰鬥選單列的寬度等於兩倍字母；主畫面與戰鬥畫面的中文和游標同高、字級；skin 字型有中文時自己畫；編輯器翻譯頁列出全部鍵、編輯、清空、填入引擎繁中、專案名稱、介面翻譯；demo 的 zh-TW 表完整；鍵清單文件是最新的。完整測試 3132 通過、1 略過、0 失敗（`pytest -q`，約 3 分鐘）；`ruff check`、`ruff format --check` 乾淨。

**實機證據：**
- 截圖從乾淨副本拍（`git archive HEAD` 加上這一批的檔案與編好的 kernel；工作目錄有其他 session 未提交的改動）。
- `scripts/built_in_text_live_check.py`（Cocoa 視窗，真的按鍵）PASS，21 項檢查全過：`d52_zh_title.png`、`d52_zh_field.png`、`d52_zh_pause.png`、`d52_zh_settings.png`、`d52_zh_slots.png`、`d52_zh_status.png`、`d52_zh_battle_menu.png`、`d52_zh_battle_skills.png`、`d52_zh_battle_skill_help.png`、`d52_zh_battle_disabled.png`、`d52_zh_battle_target.png`、`d52_zh_victory.png`、`d52_zh_victory_hero.png`、`d52_zh_game_over.png`，英文對照 `d52_en_pause.png`、`d52_en_battle_menu.png`；每個畫面畫出的字記在 `d52_built_in_text_results.json`。
- 編輯器（Cocoa）：`d52_editor_translations.png`（中文介面的翻譯頁：專案自訂的鍵與標題畫面的內建字）、`d52_editor_translations_menu_names.png`（Command Menu Pages 的名稱與中文）；`editor_ui_audit.py` 的 Translations 頁在英文與中文介面、1600×1000 與 1100×700 都 0 缺陷（只有整頁要上下捲）。
- **沒有翻譯表的畫面不變**：新舊引擎（舊的＝HEAD 版本的這批檔案＋工作目錄其他檔案）各畫 12 個畫面（標題、野外、暫停、設定、任務、成就、圖鑑、遊戲結束、存檔、狀態、戰鬥指令、技能清單），Octopath、Complex Reference（都沒有表）與英文的 Full Verification 共 36 張逐像素相同。

**限制：**
- 專案資料的名稱和說明（角色、技能、道具、狀態、敵人、任務、商店、勝利頁的敵人與貨幣 id、技能說明）照作者寫的顯示；要多語系得另做「資料翻譯」。
- 開發用的錯誤維持英文：`unknown …`、資料設定錯誤、技能樹的條件原因（`insufficient ap: requires …`）、工坊（測試用畫面）的精煉錯誤、捕獲拒絕裡的 id。
- 破防以外的「失去回合」狀態格（例如 SLEEP）還是狀態 id 的大寫。
- 中文用系統字型（macOS STHeiti、Windows 微軟正黑體、Linux Noto）；沒有 CJK 字型的機器會顯示方框，匯出不附中文字型（skin 字型本身有中文就沒問題）。
- 寵物改名的輸入只收 KEYDOWN 字元，中文輸入法的組字還不能用。
- 既有、與翻譯無關：勝利時戰鬥畫面自己的結果面板在 VictoryScreen 後面、最後的指令選單停在畫面上；選中技能列名稱和花費會黏在一起（D49／D51 已記）。

**狀態：** b5021e83。


## D53 — 戰鬥 HUD 的隊伍肖像（2026-10-23）

**要求：** 想用動漫風的圖做 Dragon Quest／Persona 式的戰鬥（隊伍用肖像放在 HUD、敵人正面、攻擊用特效表現），因為可散布的動漫戰鬥行走圖找不到，可用的 CC0 動漫肖像倒是有。戰鬥角色圖（Combatant Sprites，`combatant_visuals`）早就有 `portrait_asset_id`、`small_portrait_asset_id`，Portrait Party Layout 也會把隊伍留在 HUD，但戰鬥畫面從沒畫過肖像（`BattleUiAssemblyRuntime`／`BattleUiMemberCard` 帶著這兩個 id，但只是匯出，實際戰鬥流程沒有用到它）。

**做了什麼：**
- **畫面**（`presentation/battle_ui.py`）：隊伍卡片有肖像就畫出來，三種隊伍 HUD（`column`、`side_list`、`bottom_row`）都支援。肖像放在卡片的左端或右端（名字、血條、數字往旁邊讓並變窄，血條至少留 24 版面單位），或放在列的上方（卡片變高）。放旁邊的肖像不會比卡片的列高，所以卡片大小不變；放上方的只用清單或欄位剩下的空間（不會擠掉別人的列，空間不夠就縮小，再不夠就不畫），底列（bottom row）往上長，戰場的腳底線也跟著上移（`bottom_row_height`，`runtime/battle_visuals.py`）。同一個清單或欄位裡的肖像一樣大（取最小的），小於 10 單位就不畫。
- **大小肖像**：肖像方格 32 單位以上用 `portrait_asset_id`，以下用 `small_portrait_asset_id`，缺一個就用另一個。
- **不會被蓋住**：卡片自己的名字、血條、數字、狀態圖示都排在肖像旁邊或下方；指令選單、技能說明框、目標選擇框碰到肖像時，先變窄（說明框重新換行），不行再移開（`_clear_of_portraits`），沒擋到就完全不動。原本 Vigil 的指令選單會蓋到側欄左緣（截圖裡的「Vesper」），現在停在側欄前面。
- **載入與繪製**：用 D41 的 `PlayableTestRuntime.dialogue_portrait()`（`icon_source` 解析 id，放大用最近鄰、縮小用平滑，結果有快取）。adapter 開戰時用 `skin_image` 確認圖讀得到，讀不到就當作沒有肖像（卡片照舊）。`PygameBattleUiBackend(resolve_portrait=…)` 把肖像以原比例置中畫在方格裡；`BattleUiRenderer` 在面板之後、血條與文字之前畫（沒有 `draw_portrait` 的後端照常畫卡片，只是沒有肖像）。
- **資料**：`BattleUiLayoutProfile.hud_portraits`（`left` 預設／`right`／`above`／`off`）、`hud_portrait_size`（0 = 和卡片的列一樣高），都只在有設定時寫入；新的繪製指令 `BattleUiPortrait` 與 `BattleUiFrame.portraits`（預設空）。
- **編輯器**：Battle Presentation ▸ HUD & Interaction ▸ Battle UI Layout 的表單多出 HUD Portraits（下拉：Above／Left／Off／Right）與 HUD Portrait Size，都有說明；Combatant Sprites 表單的 Portrait、Small portrait 改用對話視窗的肖像選擇器（清單＋預覽＋Browse…，沒選就是 null）。介面字串都有 zh_TW。

**相容：** 沒有設定肖像的專案（目前所有範本與參考專案都沒有）畫面完全不變；舊資料照常讀，新選項沒設定就不寫入。

**測試：** `tests/test_battle_hud_portraits.py`（46 項）：選項只在有設定時寫入、舊資料照讀、錯的值會擋下；編輯器的下拉與中英文、肖像選擇器；三種 HUD × 左／右／上方：肖像在自己的卡片裡，不碰到自己的名字、血條、狀態圖示，卡片大小（放旁邊不變、放上方剛好長高肖像＋2），卡片不重疊、不出畫面；沒有肖像的卡片樣子完全一樣（放旁邊時連位置都一樣）；`off` 和沒有肖像的畫面相同；同一清單或欄位一樣大；大小肖像的選擇與互補；大小選項與極限（滿的側欄只用剩下的空間、太窄的卡片不畫）；四種版面 × 三個行動角色，指令選單、說明框、目標框都不蓋肖像，沒擋到時位置不變；快取（肖像改了才重排）；Headless 後端的繪製順序；pygame 後端的縮放與置中；Octopath demo 的真實戰鬥（肖像畫在方格裡、圖不存在的不畫、`off` 不畫）。完整測試 3181 通過、1 略過、0 失敗（`pytest -q`，約 5 分鐘）；`ruff check`、`ruff format --check` 乾淨。

**實機證據：**
- `scripts/battle_portraits_live_check.py`（Cocoa 視窗，真的跑 frame 到第一位主角的回合、指令選單開著）PASS：五場戰鬥每張肖像都和縮放後的圖逐像素相同（0 個像素不同），沒有字、血條或選單蓋到。肖像用 Ninja Adventure 的 CC0 facesets（Hunter、SorcererBlack、Vampire、SamuraiBlue，取自 `local_reference/`）代替動漫臉，專案只在記憶體裡改。截圖：`d53_vigil_side_list.png`（Portrait Party Layout：身體隱藏、側欄、肖像在左）、`d53_vigil_side_list_right.png`（肖像在右）、`d53_octopath_side_list.png`（側視戰鬥、身體顯示）、`d53_octopath_column.png`（引擎預設的欄位 HUD）、`d53_octopath_bottom_row_above.png`（底列、肖像在上方 30 單位）；結果在 `d53_battle_portraits_results.json`。
- 編輯器（Cocoa，`--editor`）：`d53_editor_battle_ui_layout.png`／`_zh.png`（Battle Screen ▸ Battle UI Layout 的 HUD Portraits 下拉與 HUD Portrait Size，含說明）、`d53_editor_combatant_portraits.png`／`_zh.png`（Combatant Sprites 的 Portrait 肖像選擇器：預覽、清單、Browse…）；英文與繁體中文都畫出（語言只對這個視窗切換，沒有存設定），結果在 `d53_editor_results.json`。
- **沒有肖像的畫面不變**：舊引擎（改之前的 src，HEAD 03558c5f）與新引擎各畫 Octopath（boss_room、slime_pit、samurai_duel）、Full Verification（acolyte_vigil、boss_room）、Complex Reference（boss_room）六場戰鬥，每場五個時刻（主角回合後第 1、60、240 幀，按下、再按確定之後），共 30 張逐像素相同。

**限制：**
- 肖像只在 HUD 卡片上；`BattleUiAssemblyRuntime` 仍沒有接到實際戰鬥流程（和之前一樣）。
- 頭頂資訊（overhead）的成員沒有卡片，所以不畫肖像。
- 「上方」在滿的側欄（例如 Vigil 4 人 × 4 列）沒有剩下的空間，肖像不會出現；側欄建議用左或右。
- 肖像不會依狀態換臉（受傷、倒地），也沒有外框樣式可選。
- 既有、與肖像無關：欄位 HUD 的數字在 Octopath 字型下 4 位數時會壓到血條右端；Battle UI Layout 表單的 Command Counts、Stage Front Right 兩個欄位名還沒有中文。

**狀態：** 已提交（2026-10-23，使用者要求）。

## D54 — 戰鬥站位：隊伍收緊、站在自己那一側、腳一定在地面上（2026-10-23）

**要求：** Full Verification 的戰鬥裡，隊伍成員之間（尤其水平方向）離得太遠，看起來離怪物很近；隊伍要收緊並維持在畫面右側、離敵人遠一點，間距和位置要做成編輯器可調的選項。看截圖時使用者另外要求：所有角色都要站在草地或地板上，有的站到牆上了。

**原因（實測，480×270 版面單位）：**
- 兩欄的距離用整張精靈格的寬度算（約 60 單位，含攻擊動作的空白），身體只有約 25，所以隊伍兩欄中心相距 63.5（1280 寬的畫面上 169px）。
- 前排照 `stage_front` 站在 300，但後排超出舞台右緣（側欄 HUD 的左邊 356），整隊被往左推 37 單位，前排反而靠向敵人；寵物（`front_large_zones` 讓它站在隊伍前）再前一欄，落在 199，比 Crypt Boss 的骷髏（231）還靠左，站進敵陣。
- 側視站位（Side-View Positions）範本用絕對座標，不看地面線 `stage_top`；`crypt_ranks` 的隊伍從 y=120 開始，Aldric 的腳在牆上（地面線 127）。

**做了什麼：**
- **戰鬥版面新選項**（`presentation/battle_ui.py`，編輯器 Battle Screen ▸ Battle UI Layout，附說明與中文）：
  - `column_spacing`（欄距）：同一方相鄰兩欄的中心距離（版面單位）；0 = 自動，也就是原本的規則（整張圖不重疊）。有 Boss（比最小的高 1.5 倍以上）的那一欄一律用自動距離，不會疊在一起；沒有 HUD、站在隊伍前的寵物不算大型，照欄距站。
  - `column_spacing_right`（右側欄距）：右側那一方另設；空白 = 跟著 `column_spacing`（和 `stage_front`／`stage_front_right` 同樣的做法，編輯器顯示時填入跟隨的值，改成相同的值又變回跟隨）。
  - `feet_on_ground`（腳站在地面，預設開）：側視站位或肖像隊伍版面給的位置，腳的高度夾在地面帶內（舞台頂端 `stage_top` 到舞台底），先夾再加角色圖自己的偏移 Y，所以飛行單位照樣能離地；關掉 = 照範本寫的。自動站位本來就在地面帶內，不受影響。
  - 三個選項都只在不是預設值時寫入；舊資料照常讀。
- **隊伍位置**用既有的 `stage_front_right`（右側舞台前緣）：欄距收緊後不再被溢出推擠蓋掉；設 0 = 整方貼著自己的邊緣（後排的圖剛好在舞台內）。編輯器補上它的說明與中文名稱（D53 記下的缺口之一）。
- **Full Verification**：`column_spacing_right` = 30、`stage_front_right` = 0；`crypt_ranks` 的隊伍區 y 從 120（每人 +34）改成 136（每人 +30），x 從 236（每人 +22）改成 246（每人 +20），五個人（含寵物）都站在地板上、往右靠。

**結果（Cocoa 視窗實測，英雄前排／後排／寵物的 x，1280 寬的畫面）：**

| 戰鬥 | 改之前 | 改之後 |
| --- | --- | --- |
| 3 人＋寵物 Crypt Boss | 701／870／531（骷髏在 617） | 790／870／710 |
| 4 人＋寵物 Boss Room、Crypt Boss | 701／870／531 | 790／870／710 |
| 3 人 Woods Boss、4 人 Woods Ambush | 701／870 | 790／870 |
| Aldric 一人＋寵物 | 870／—／701 | 870／—／790 |
| 4 人＋寵物 Crypt Guard（範本） | Aldric 的腳在 y=320px（牆上） | 最高的腳在 y=363px（地板上） |

兩欄間距 169px → 80px；英雄前排到最近敵人 84px → 173px；寵物不再站在敵人前面。敵人的位置都沒變。

**相容：** 沒有設定這些選項的專案站位完全不變：Octopath（boss_room、gazer_nest）與 Complex Reference（boss_room）的座標相同，改之前（HEAD 的乾淨副本）和改之後的 Cocoa 截圖逐像素相同（3 張，0 個像素不同）。目前只有 Full Verification 有站位範本，所以「腳站在地面」預設開也只影響它（Crypt Guard 的 Aldric）。

**測試：** `tests/test_battle_stage_spacing.py`（11 項）：沒設定時和以前一樣（自動距離 64、被推到 262）；欄距兩側都套用、右側欄距覆蓋、敵人保持自動；整方貼著邊緣（後排 326、前排 296，一人時也在 326）；Boss 那一欄保持自動距離；隊伍前的寵物照欄距站；範本的腳不會在牆上或舞台底下、x 與面向照範本；關掉時照範本；偏移 Y 照樣讓飛行單位離地；選項只在有設定時寫入、舊資料照讀、負值擋下；編輯器顯示與跟隨、中英文說明；Full Verification 的資料。`run_campaign.py` 的 Crypt Guard 站位檢查改成新的 x（246）。完整測試 3195 通過、1 略過、1 失敗（`pytest -q`，約 6 分鐘）：失敗的是 `test_asset_library`，因為另一個 session 正在加、還沒提交的 `asset_library/kaykit/`（沒有授權文字），和這次的改動無關；那個 session 把它分成三個各有授權檔的包之後，`test_asset_library` 重跑通過。`ruff check`、`ruff format --check` 乾淨。

**實機證據：** `docs/audits/evidence/battle_stage_spacing/`
- 改之前／改之後對照（上下兩張，Cocoa 視窗，真的跑 frame 到主角回合、指令選單開著）：`3p_crypt_boss.png`、`4p_boss_room.png`、`4p_crypt_boss.png`、`4p_crypt_guard_template.png`（地板背景）、`4p_crypt_boss_hero_03_turn.png`（後排 Vesper 的回合）、`1p_woods_patrol.png`；每個角色的座標在 `before_positions.json`、`after_positions.json`（driver = cocoa）。改之前從 HEAD（13faf4b4）的乾淨副本拍。戰鬥直接開（不經過劇情），背景照遊戲的區域：Crypt Guard 用地下墓穴背景，其他用預設背景。
- 整段劇情（`scripts/full_verification_campaign_live_check.py`，Cocoa 視窗）PASS：Crypt Boss、Boss Room、Crypt Guard 等每場戰鬥在遊戲自己的背景上，所有角色都站在草地或地板上。
- 編輯器（Cocoa）：`editor_battle_ui_layout_en.png`／`_zh_TW.png`：Battle UI Layout 表單的右側舞台前緣、欄距、右側欄距、腳站在地面，含說明；`editor_results.json`。

**限制：**
- **指令選單蓋到 HUD**：Full Verification 的選單放在行動者的右下（`actor_bottom_right`，規則本來就允許沒空間時蓋到 HUD）。前排英雄往右 89px 後，Aldric／Mira 回合的選單蓋到 Vesper 的側欄卡片約 100px（之前約 12px）；後排英雄的位置沒變，他們回合的選單和以前一樣蓋到側欄。使用者看過截圖後決定站位這樣可以、選單先不處理（2026-10-23）。
- 敵人那一側沒改：Crypt Boss 的骷髏被 Boss 很寬的精靈格（含劍的範圍）推到 617px。
- 地面線只有一條（版面的 `stage_top` = 0.47）：預設、沼澤、地下墓穴背景的地面從 44.5% 開始，符合；王座背景的地板從約 64.5% 開始（中間是岩漿），目前那裡只有 Acolyte Vigil（肖像版面，敵人腳在 570px，地板上），但自動站位的戰鬥若在那裡發生，上排會站在岩漿上。依背景設定地面線要另外做。
- 欄距用中心距離；圖格本身的空白仍決定「貼邊」時後排離舞台邊多遠（後排中心最多到 326）。

**狀態：** 未提交（等使用者說）。

## D55 — 精靈表可選縮放方式；KayKit 3D 角色渲染工具（隊伍試用後退回 Lucifer）（2026-10-23）

**要求：** 使用者要一個好看一點的主角，試過各種免費素材後選定 KayKit（Kay Lousberg，CC0）的 3D Q 版角色，用 Blender 拍成 2D 圖，而且要「更接近平滑版」而不是像素化。核准 B1–B5：引擎平滑縮放選項、渲染工具進 repo、整隊角色、地圖行走圖、demo 接入；角色對應 Aldric＝Knight（劍盾）、Mira＝Mage（法杖＋攤開的魔法書）、Vesper＝Rogue_Hooded（魔杖＋魔法書）、Cael＝Rogue（雙匕首）；KayKit 原始檔放進 repo；敵人先維持 Lucifer 像素風。

**原因：** 戰鬥與地圖的角色一律用最近鄰縮放（`pg.transform.scale`），平滑圖一放大（Boss 登場 1.35 倍、不同視窗大小）就出現鋸齒；引擎沒有「這張圖要平滑縮放」的資料。

**做了什麼：**
- **B1 引擎**：精靈表中繼資料 `scaling`：`pixel`（預設，不寫入）／`smooth`。`SpriteSheet.scaling`（`graphics/sprites.py`）、`reference_data.load_sprite_sheet`、`BattleVisualResolver.sprite_sheet` 都帶著它；戰鬥繪製（`PygameTextureDrawer.resized`，含旋轉與快取路徑）與地圖（`TileSceneView._sprite`）照它選 `smoothscale` 或 `scale`。playtest 的玩家行走圖另有 manifest `field.player_scaling: smooth`（連線 HUD 的小人也照它）。編輯器 Sprite Animation ▸ Sheet 多了「縮放方式」下拉（像素風（銳利）／平滑（手繪或 3D 渲染），附說明與中文），`AnimationAuthoringController.set_scaling` 可復原，錯的值會擋下。
- **B2 工具**：`scripts/build_kaykit_art.py`（專案 venv；`--render` 才需要 Blender，沒裝就印出下載網址與 `ASTERIA_BLENDER` 說明；`--keys`、`--views field` 只重拍地圖視角；`--list`）呼叫 `scripts/kaykit_render_blender.py`（Blender 無頭：匯入角色、動畫檔、手上道具掛到 `handslot.r/.l`，正交相機，每個視角逐格拍）。原始影格放 git 忽略的 `local_reference/free_assets/kaykit_render/raw/`；成品放 `asset_library/kaykit/KayKit_Rendered_Sheets/<key>_battle.png/.json`（80 格、每列 10 格、版面單位 ×3、站立 44 單位、`scaling: smooth`、profile scale 1/3、`body_height`、所有戰鬥片段含 revive／transform／victory）與 `<key>_field.png/.json`（3×4 行走圖，48 px 格、站立 32 px，和 Lucifer 行走圖同大小，俯角 30°；地圖的精靈沒有自己的縮放，所以行走圖得先縮到 1 倍大小再由鏡頭放大）。KayKit 來源檔（6 個角色 .glb、31 個道具、8 個動畫檔、各自的 License.txt）放 `asset_library/kaykit/`，分成三個 pack 以符合素材庫的授權檢查。
- **B3／B4**：四位隊員的戰鬥圖與行走圖都拍好（每人約 60 秒）。
- **B5 demo**：`trial_kaykit.py` 在四張圖都存在時把它們登記成 hero_01–04 的戰鬥圖（`scaling: smooth`、facing left、來源 KayKit），地圖上隊員的外觀（`trial_maps` 的 `hero_<face>` look）改由 `trial_kaykit.field_character` 從行走圖建出 idle／walk 四向片段（sheet JSON 帶 `scaling: smooth`，`Assets.sheet` 多了 `scaling` 參數），舊式 manifest 的 `player_field_sheet.png` 也換掉並在 `write_manifest` 後補上 `player_scaling`；沒有圖時照舊用 Lucifer 隊伍，所以 demo 建置永遠不需要 Blender。CREDITS.md 多了 KayKit 一列；THIRD_PARTY_ASSETS.md 記了來源、版本、大小與「No generative AI was used」。

**相容：** 沒設定 `scaling` 的精靈表畫面完全不變（`pixel` 是預設、不寫入）；舊資料照常讀。現有專案與範本都沒設定。

**測試：** `tests/test_sprite_scaling.py`（4 項：資料與驗證、戰鬥繪製只對要求的圖做平滑且與 `smoothscale` 逐像素相同、地圖視圖、編輯器設定→執行期解析器→復原）、`tests/test_kaykit_art.py`（4 項：job 的視角與片段、假影格→格狀圖與行走圖的大小／軸心／片段、demo 不用 Blender 讀回、沒有 Blender 的訊息）；`tests/test_asset_library.py` 通過（三個 pack 都有 CC0 授權文字）。

**實機證據（`docs/audits/evidence/kaykit_smooth/`）：**
- `b1_boss_zoom_pixel_vs_smooth_x4.png`：Boss 登場拉近時，`pixel` 鋸齒、`smooth` 平滑（同一張 KayKit 圖）；`b1_woods_smooth_960.png`：960 寬視窗。
- `b1_editor_sprite_animation_scaling.png`／`_zh.png`：Sprite Animation 的「縮放方式」下拉。
- `b3_party_battle_frames.png`、`b4_party_field_sheets_x3.png`：四位隊員的戰鬥動作與行走圖。
- `campaign/`：`scripts/full_verification_campaign_live_check.py` 在 Cocoa 視窗跑完整段劇情 PASS（`results.json`），`battle_*.png` 每場戰鬥、`map_*.png` 每張地圖都是 KayKit 隊伍；`run_campaign.py` 無頭版所有 REQUIRED 事實成立。

**限制：**
- 敵人仍是 Lucifer 像素風，隊伍是平滑 3D 渲染：混搭是使用者先接受的。
- 換武器時手上的道具不會跟著換（引擎的掛點系統還沒接到戰鬥）；要換武器要重拍。
- 行走圖每個方向只有 3 格（引擎的 3×4 格式），動作幅度小。
- 渲染用 EEVEE 的預設材質，沒有描邊或卡通著色；要更像手繪得再調。
- Blender 是作者機器上的工具，不隨引擎安裝；版本 5.2.3 驗證過。

**後續（同日）：使用者覺得畫風不對，隊伍退回 Lucifer。**
- 平滑 3D 渲染放在 Lucifer 像素背景與敵人旁邊像貼上去的。試了 A 版：Blender 卡通著色（`kaykit_render_blender.py` 的 `toon`：漫射亮度分 3 階後平塗發光）、縮到 Lucifer 的像素大小、全角色共用 40 色調色盤、四向 1 px 深色外框、`scaling: pixel`（`build_kaykit_art.py --style toon --out <dir>`，影格放 `raw/<key>_toon/`）。在 demo 複本的真實視窗跑完整段劇情 PASS（`scripts/full_verification_campaign_live_check.py` 現在可用 `ASTERIA_FV_DEMO` 指定 demo 複本）。外框與像素和環境融合多了，但騎士內部糊成一片灰、色調比 Lucifer 亮，使用者決定退回。
- **Demo**：隊伍回到 Lucifer 像素風。`trial_kaykit.py` 留著但改成選用：建置時 `ASTERIA_FV_PARTY=kaykit` 且圖已建好才換成 KayKit（`built()`／`available()`）；預設建置的隊伍圖、行走圖、manifest、CREDITS 與 HEAD 相同。重建後 `run_campaign.py` 所有 REQUIRED 事實成立，真實視窗 live check PASS（劇情截圖 `full_verification_campaign/` 和 D54 的站位一起重拍，隨 D54 提交）。
- **保留**：引擎的 `scaling` 選項（通用，所有專案可用）、`scripts/build_kaykit_art.py` 與 `kaykit_render_blender.py`（smooth 與 toon 兩種風格）、`asset_library/kaykit/` 的來源檔與平滑版成品。toon 版成品只在 git 忽略的 `local_reference/free_assets/kaykit_render/toon_sheets/`。
- `docs/audits/evidence/kaykit_smooth/` 的 `campaign/` 與 `b3_*`／`b4_*` 是試用時的證據，不代表目前 demo 的樣子。

- **寵物與召喚改成可愛的小動物**（使用者要求）：原本收服的寵物用哥布林投石手的圖、召喚的 Spirit Knight 用哥布林騎兵。改用素材庫裡 Foozle Critters（同一位畫師 Baldur，CC0）：寵物（所有 `pet:` 成員）＝ Little Bird、Spirit Knight ＝ Elite（穿盔甲拿劍的狐狸，使用者挑的；先試過 Mouse）。新模組 `trial_critters.py`（單向條帶：玩家角色包面向右要鏡像，敵人包本來就面向左，`FACING_LEFT` 不鏡像），`trial_lucifer.sheet_from_strips` 從 `character_sheet` 拆出來共用。比例：寵物 0.75、狐狸 0.8——超過隊員 1.5 倍高會被當成「大型」站到隊伍前面靠近敵人（`front_large_zones`），0.9 時就發生過，已確認 0.75 留在隊伍裡。真實視窗 live check PASS（`full_verification_campaign/battle_boss_room.png` 可見小鳥在隊伍中）；召喚的狐狸只在組好的圖上確認過（`kaykit_smooth/summon_fox_frames.png`）：劇情腳本從來不施放 Call Spirit，所以沒有遊戲視窗的召喚截圖。
- 注意：campaign 裡收服的是野生哥布林投石手，收服後外觀變成小鳥（引擎的寵物外觀是共用的 `pet` profile，不分來源）。

- **受擊特效被截一半、偏在一邊**（使用者指出）：Pixel Magic Effects 的 Wind 是一陣往右飛的風，第 6–10 格撞在 64 px 格子的右緣、被壓成半個括號，置中時又被這幾格拉向右邊。所有用 Wind 的特效（slash、cut、claw、spark、circ 等 9 種）現在只播完整弧形的第 1–5 格，以內容置中在目標上（`trial_art.effect_assets`）。真實視窗逐格截圖確認（`kaykit_smooth/hit_effect_whole_arc.png`）。

- **全部戰鬥圖與特效檢查**（使用者問「你都有檢查嗎」：之前沒有）：自動檢查 34 張戰鬥圖每個片段每一格（空格、超出、碰到格子邊緣），並回頭查原始素材：Lucifer 包有多個大動作（Aldric 攻擊第 3 格的劍光、Skeleton Ancient 與 Skeleton King 的揮砍弧與劍身、Cultist 的爆光、冰特效的水柱頂）在素材自己的格子邊緣被直線切斷。
  - 修法（使用者選 A）：`trial_lucifer.fade_cut_edges` 把碰到格子邊緣的那一側在最後 5 個像素淡出（角色保留底邊，因為腳站在那裡；特效四邊都淡），角色圖在 `sheet_from_strips`、特效在 `effect_assets` 套用；特效另外拿掉空白格（Portal 系的 aura、circle、shield、spirit 中間有一格空白，會閃一下）。
  - 新腳本 `scripts/battle_art_gallery_live_check.py`：在真實 Cocoa 視窗用引擎自己的戰鬥繪製（`PygameTextureDrawer`、`vfx_placement`／`vfx_rect`）把每個角色的每個片段逐格畫在戰鬥背景上、每種特效逐格落在一個目標身上，每個角色一張、特效每 4 種一張；PASS，19 張在 `docs/audits/evidence/battle_art_gallery/`。
  - 沒涵蓋的：這是逐格畫出，不是完整戰鬥流程（衝刺、時機、命中同步）逐技能播放；fx_heal 最後一格空白（另一個來源，看不出來）。

**狀態：** 未提交（等使用者）。

## D56 — 程式結構：CI、單一縮放路徑、兩個大檔拆成 mixin、風險文件重核（2026-10-23）

**要求：** 使用者問「程式部分還有需要優化的部分嗎」，實測效能沒有瓶頸後，核准把建議的四項都做完：GitHub Actions、統一的縮放與繪製路徑、拆開 `game_session.py` 與 `playable_test_runtime.py`、重新核對 `ARCHITECTURE_PERFORMANCE_RISKS.md`。

**做了什麼（四個 commit）：**
- **CI**（`.github/workflows/tests.yml`）：每次 push 到 main 與每個 PR 跑 ruff check／format 與全部測試；Ubuntu、Python 3.12 與 3.13、`SDL_VIDEODRIVER=dummy`、`SDL_AUDIODRIVER=dummy`、`QT_QPA_PLATFORM=offscreen`，裝 `.[pygame,editor,mv,dev]` 與 Qt offscreen 需要的系統函式庫。本機用同一組環境變數（另外清掉 HOME 與 `ASTERIA_MUSIC_ASSETS`）跑過 3200 個測試全過；真實視窗的 live check 腳本不在 CI 裡（要桌面），證據照舊提交在 `docs/audits/evidence/`。
- **一個縮放函式、一個快取**（`graphics/scaling.py`）：`resized(pg, image, size, smooth=False)`（最近鄰或平滑，大小永遠至少 1×1，8 位元圖先轉）與 `ScaledImageCache`（縮好的圖依鍵保留，超過像素預算就整個重來）。戰鬥繪製器、地圖視圖、兩個 pygame 材質後端、可玩 runtime 的特效、骨架、法線、組合、NPC、玩家行走圖、連線玩家、圖片都改走它；NPC 圖與玩家的每一步依大小各縮一次，不再每格縮，釋放資源範圍時一起丟。`tests/test_sprite_resizing.py`（4 項：和 pygame 逐像素相同、快取預算、地圖重用、材質後端）。
- **可玩 runtime 拆成 `runtime/playtest/`**（14 個 mixin：resources、environment、text_draw、field_view、multiplayer、field_ui、action_scenes、title_build、workshop、battle_flow、menus_input、save_slots、menus_draw、capture；`support.py` 放模組層的函式）：`PlayableTestRuntime` 留在原模組組合它們，只剩建構、frame 迴圈、present／capture／close、存檔與 run（789 行）。每個方法原樣搬、名字不變；原本的 `from .x import` 改成絕對路徑。
- **遊戲 session 拆成 `runtime/session/`**（18 個 mixin：field_play、action_play、gear、scene_events、npc_state、battle_events、messages、party、inventory_use、builds、encounters、ability_use、pets、strikes、turns、economy、interactions、rewards；`support.py` 放 `GameSessionError`、`BattleLogEntry`、`EquipOffer`、`describe_condition` 等）：`GameSessionRuntime` 留在 `game_session.py` 只剩建構子；模組層名稱照舊可從 `game_session` import。
- **風險文件**（`docs/audits/ARCHITECTURE_PERFORMANCE_RISKS.md`）重寫成 2026-10-23 的現況：十項風險逐一標狀態與證據（已處理：CI、System 子類別、遷移、profiler、字型快取、draw 快取；降級：規則洩漏、MV、assets 依賴上層；未處理：presentation 模組大），新增 RISK-11（兩個大檔，已處理）與實機基準 PERF-07／PERF-08。

**實測（Apple silicon，真實視窗 1280×720，54 個實體，各 600 格；拆之前／之後）：** 地圖平均 4.9→5.1 ms、p95 7.2→7.6 ms；戰鬥平均 4.6→4.3 ms、p95 6.7→6.4 ms；都在每格 16.7 ms 預算的三分之一內，FPS 被螢幕更新率卡在 56–59。差異在量測雜訊內。專案載入 0.08 s。

**相容：** 行為沒有改變：拆檔前後 3205 個測試、`run_campaign.py` 全部 REQUIRED 事實、真實視窗劇情 live check、戰鬥圖庫 live check 都通過；`PlayableTestRuntime`、`GameSessionRuntime`、`GameSessionError`、`walking_row_index` 等名稱的 import 路徑不變。

**限制：**
- CI 只在本機用同樣的環境變數驗過，GitHub 上第一次跑的結果（Qt offscreen 的系統函式庫是否齊）要看 Actions 頁；真實視窗的檢查仍是本機手動。
- mixin 只是把方法搬開，彼此仍透過 `self` 共用狀態；要進一步解耦（各 mixin 自己的狀態與介面）是下一步，不在這次。
- `platform/pygame_backend.py` 的通用 `draw_texture` 仍每次縮放（沒有量到是熱點，未加快取）。
- ENGINE_HANDBOOK 裡指到 `runtime/game_session.py`／`runtime/playable_test_runtime.py` 的列仍指原模組（類別還在那裡）；方法本身現在在 `runtime/session/`、`runtime/playtest/` 的對應模組。

**狀態：** 已提交（2026-10-23，使用者要求）。
