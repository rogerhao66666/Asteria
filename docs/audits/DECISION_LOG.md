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
- 備份：`~/Documents/Vscode/Asteria_backup_2026-10-09_generated_art.zip`（repo 外，30 MB，180 個項目，`unzip -t` 通過）。內容包括整個 `assets/`（含從 git 取出的 `ready_user_hero`）、下列被移除的程式／腳本／測試／設計文件，以及修改前的 `shell.py`、`assets/__init__.py`、`test_editor_mv_character_creator.py`
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
| 使用者 demo 回饋（同日） | 角色右、怪物左（預設）；角色與怪物站在地面、不擋背景；怪物 HP 顯示在頭上；指令只在輪到角色時顯示（隊伍 RPG 式）。以 `BattleUiLayoutProfile` 的 opt-in 欄位（`party_hud`、`overhead_zones`、`action_menu_placement`、`stage_top`）實作，預設值維持原行為；reference project 採用 |
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
- **倍率規則：** 任意倍率、克制、屬性、武器類型都可以設定，弱點也可以是「劍」。攻擊在能力上標武器類型（`weapon.sword`），物品只標攜帶的裝備（`equip.sword`）。破盾倍率、Boost 的連擊（repeat）或增幅（power，`boost_mode`）、雙武器、副職業都可以只靠資料組出隊伍 RPG 式的系統。
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

### D20-6 — 破防／加速戰鬥 demo（`6fb8d9c`、`524b8cd`）
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

**Demo（`reference_projects/party_rpg_demo`）：**
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
- 形式：通用功能放進引擎，另外做一個 demo 專案 `reference_projects/arpg_demo`，專案裡有俯視野外和橫向地城兩種區域。
- 第一階段做完整核心：判定、無敵幀、擊退、投射物、敵人 AI、受傷和死亡，加上壓力場景（300 隻敵人 + 500 顆投射物），先量測效能。
- 先寫設計文件，核准後再實作。

**設計：** [ARPG_DESIGN.md](ARPG_DESIGN.md)：現有系統盤點、架構原則、戰鬥流程、新資料、A1–A9 分批計畫、效能目標、不在範圍內的項目。

**狀態：** 已核准，實作中。

**需要你決定：** 橫向素材的來源（建議下載 CC0 的 Kenney Pixel Platformer）；核准計畫後從 A1 開始。

**核准（2026-10-13）：** 使用者核准計畫並同意下載 Kenney Pixel Platformer 1.2（CC0，kenney.nl，`kenney_pixel-platformer.zip`，260 KB，存到 git-ignored 的 `local_reference/free_assets/kenney_pixel-platformer/`，已下載，授權檔確認是 CC0）。Demo 改成動作 RPG 式：打怪掉寶、職業、技能樹也一起做進引擎。計畫改成 A1–A11（新增 A6 掉寶、A7 職業和技能樹），見 [ARPG_DESIGN.md](ARPG_DESIGN.md)。

**使用者追加（2026-10-13）：**
- 系統一律做成通用的。動作 RPG 玩法只是 demo，引擎不能只支援這一種玩法；不限制作者的程式、想法、美術和玩法。已寫進 ARPG_DESIGN §3 原則 0。
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
3. 敵人每一下小攻擊都會打斷玩家的連擊 → playground 設定 `hitstun_rule = never`（動作 RPG 手感）和自動瞄準最近的敵人。兩者都是引擎原本就有的選項。
4. 參考專案原本回合制的 Boss 精靈站在競技場裡擋住玩家 → playground 停用場景裡的回合制遭遇。

**執行的測試：** 完整套件 **2132 passed**。

**量測（300 + 500 壓力場景，numpy）：** 13.4 ms。

**還沒做：**
- 橫向的玩家精靈目前沿用參考專案俯視角色的走路圖，比例偏大；A10 的 demo 會換成 Pixel Platformer 的橫向素材。
- 開場選職業畫面、技能樹專用畫面：目前用建構選單（C）配點和換職業；動作 RPG 技能樹畫面放在 A10 的 demo。
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

### D22-A10 — ARPG demo 專案（動作 RPG 範例，系統全部通用）

**Demo 專案 `reference_projects/arpg_demo/`**（`build_project.py` 產生，可重跑；`art.py` 切素材、`maps.py` 用程式排地圖；README 說明每條規則在資料的哪裡）：
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
- 背包仍是 A8 的清單畫面，不是動作 RPG 的格子背包；也還沒有裝備比較的提示框。
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

**使用者回報：** 下方文字疊在一起；血量的圖示和數字沒在同一條水平線；Potion 的「x3」很醜；希望快捷鍵像動作 RPG、魔獸世界的鍵盤式快捷列；血量改成左紅右藍的圓球；增益、護盾、減益、異常狀態都要顯示。

**做法（`runtime/hud_bottom.py`，新；`action_play.draw_overlay` 改用它）：**
- **圓球**：生命資源在左邊紅色圓球，第一個其他資源在右邊（名稱像魔力的用藍色，怒氣橘色，體力黃色），依比例填充（逐列畫弦、頂端較亮、液面線、高光、外框），數字在球內。其他資源是快捷列右上方的細條；名稱含 shield／barrier／ward／guard 的資源自己有淺藍色的條（護盾）。
- **快捷列**：攻擊和閃避兩個較大的格子在左，後面是編號技能；每格左上角有鍵帽（鍵名從專案的輸入表讀，不是寫死；Shift、Space 等縮寫；手把顯示 PAD 號碼）；技能名稱；冷卻用由上往下的遮罩加上秒數；魔力不足時變暗；消耗道具的技能在**右下角有小方塊徽章**顯示剩餘數量；有資源消耗的技能在左下角顯示消耗。下方是細的經驗條，「Lv N」在條裡。
- **狀態列**：玩家身上每個狀態一個方格，增益綠框、減益紅框（依狀態的作用判斷：屬性是增是減、持續傷害或治療），縮寫、剩餘時間遮罩和秒數、疊層徽章。
- **操作提示**移到畫面上方中央，有深色底，12 秒後淡出，不再壓在快捷列上。
- `PlayableTestRuntime.text(..., anchor=...)`：文字可以用任何 rect 錨點對齊，標籤和圖形在同一條水平線上。
- 測試：`test_the_hud_shows_keycaps_orbs_statuses_and_item_counts`（鍵名來自輸入表、狀態分類、縮寫、剩餘時間、道具徽章、提示倒數）。截圖 `d23_hud_orbs_actionbar_statuses.png`（1280×720 和 960×540 都檢查過）。

**限制：** 狀態沒有顯示名稱或圖示欄位，所以用 id 轉出來的縮寫和顏色表示增益／減益；敵人頭上的狀態仍是文字。

### D24-1 — 狀態與技能的名稱、圖示欄位；敵人頭上的狀態圖示；法力消耗顯示（使用者回報）

**使用者要求：** 補上 D23-8 列出的三個限制（狀態沒有名稱／圖示、敵人狀態仍是文字、技能格是文字不是圖示），再整體確認引擎、隊伍 RPG demo 與 ARPG demo。之後回報「法杖旁邊的 1 是什麼」。

**資料格式（向下相容，沒有值就不寫入資料）：**
- `StateDefinition` 新增 `display_name`、`icon_id`；`AbilityDefinition` 新增 `display_name`、`icon_id`（走 `OPTIONAL_DATA`）。舊資料照常載入，沒設定的不會被寫回。
- 編輯器的狀態與技能表單本來就以資料欄位為準，`icon_id` 會自動出現圖示挑選（測試：改名稱和圖示、復原）。
- 隊伍 RPG 戰鬥畫面的狀態文字也改讀 `display_name`（沒有就用 id）。

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
| 隊伍 RPG demo（Cocoa、真按鍵） | 指令選單、加速點、目標選單、加速攻擊兩段傷害、神技花 3 點、粒子、調合、勝利、四種遭遇全部 ok |
| ARPG demo 三個職業真實視窗 | 皆 60.0 fps；戰士 3 擊殺、遊俠 3、法師 7；走完城鎮、轉職、技能樹、野外、Boss、礦坑、背包 |
| 編輯器稽核 1600×1000／1280×800／1100×700（ARPG 與隊伍 RPG 兩個專案） | 0 裁切、0 溢出、0 過小；僅有頁面需捲動（資訊性） |

測試：`test_states_and_abilities_carry_a_name_and_an_icon`、`test_enemies_show_their_statuses_as_pips_over_the_bar`、`test_the_editor_edits_a_status_name_and_icon_and_undoes_it`。截圖 `docs/audits/evidence/real_machine/d24_hud_icons.png`。

**仍然存在：** 圖示是從資源包挑的相近圖，不是專屬設計；ARPG demo 的實機輸入沒有實體鍵盤／手把驗證（需要真人）；`CollisionWorld.from_scene` 仍未快取。

### D24-2 — 冷卻轉圈動畫、從範本新增專案、編輯器左側分頁擠在一起（使用者回報）

**使用者回報：** 技能進入冷卻要有「變暗、轉一圈變亮」的動畫，當成預設；隊伍 RPG 與 ARPG 的設定可以當成預設範本讓使用者修改；GUI 有文字擠在一起，例如 Scene 下面的 Project 跟 Tile。

**做法：**
- **冷卻時鐘**（`hud_bottom.BottomHud._sweep`）：技能用出後整格變暗，一個明亮的扇形從 12 點鐘方向順時針展開，邊緣有一條亮線，轉滿一圈整格恢復明亮並閃一下（0.3 秒）；中間仍顯示剩餘秒數。取代原本由上往下的遮罩。對所有專案的動作戰鬥 HUD 預設生效，不需設定。
- **File > New from Template…（Ctrl+N）**（`editor/project_templates.py`）：兩個範本 —— *Party RPG (break and boost battles)*（弱點與護盾、加速點、職業、寵物、調合、狀態、四種敵人）和 *Action RPG (real-time loot and skill trees)*（職業與技能樹、稀有度與詞綴、套裝、藥水、格子背包、有冷卻的快捷列、城鎮／野外／礦坑）。範本是完整的專案資料夾（含美術與授權文件），複製後改名、載入，所有設定（戰鬥規則、數值、HUD、地圖）都能直接改；建置腳本不複製。原範本不會被動到。範本來源是 `reference_projects/`，打包安裝版若沒有這個資料夾，選單會顯示「沒有安裝範本」。
- **左側分頁**：原本「Project / Scene、Tile Palette、Layers」三個分頁在窄的左欄擠不下，第三個被捲動箭頭吃掉。改名為 Project／Tiles／Layers，dock 分頁的左右內距 12 → 8 px，左欄最小寬度 264 px；視窗最小尺寸 1000×640（再小面板會擠字）。
- **稽核腳本**：`editor_ui_audit.py` 新增 `dock_tab_hidden`，停靠面板的分頁掉到分頁列外面就算缺陷（之前被當成可捲動的資訊項而漏掉）。

**確認：** 完整套件 2185 passed；兩個專案在 1280×800 與 1100×700 稽核 0 缺陷（含新規則）；法師真實視窗重跑 60 fps；截圖 `arpg_demo_mage_field_skills.png` 可見技能 2、4 的冷卻扇形與秒數。
測試：`test_a_cooldown_goes_dark_and_a_wedge_turns_clockwise_to_bright_with_a_ready_flash`、`tests/test_project_templates.py`（複製、改名、載入驗證、原檔不變、拒絕非空資料夾、編輯器開啟）。

### D24-3 — 寵物技能、多武器與多段攻擊的測試補齊、手冊（使用者指示）

**使用者要求：** 隊伍 RPG demo 補寵物（派出抓到的寵物攻擊，沒有寵物就不能用，寵物本身不用是單位）、
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

**新增／改寫的測試（`test_party_rpg_demo.py` 26 → 35，加兩個單元測試）：**
| 項目 | 測試 |
| --- | --- |
| 寵物 | 有寵物可用、沒有時灰掉並說明、直接選會被拒、派出後寵物還在、出戰名單沒有多一個單位；捕獲得到寵物道具並解鎖技能、隊伍沒變 |
| 武器 | 兩種武器各自的攻擊找到各自的弱點；拿下武器後攻擊消失、裝回來恢復 |
| 多段 | 逐段記錄武器／屬性標籤：Brand of Valor（劍矛劍矛雷）、Arrowstorm（五箭＋冰）、Grand Inferno（火×3） |
| 調合 | 四種配方各做一次（材料消耗、全體傷害／補血／降防禦、產物立即用掉） |
| 副職技能 | Sera（毒擊、破甲）、Bram（治療、聖光、淨化）、Ione（孔雀舞、催眠華爾茲）各打一次並驗證狀態或傷害 |
| 奧義 | 四個奧義：不足 3 點時被拒絕並說明、足夠時花光；Last Stand 全隊攻擊提升 |

**文件：** 新增 `docs/ENGINE_HANDBOOK.md`（引擎功能、編輯器、兩個 demo、資料格式變更、測試與驗證方式、
限制與下一步、工作方式）；`README.md` 開頭改指向手冊；隊伍 RPG 範例的 README 更新寵物與武器說明。

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
- **專屬狀態圖示**：ARPG demo 的 healing／war_cry／burning／bleeding／chilled 用程式畫（綠十字、橘色上箭頭、火焰、
  血滴、雪花，1 px 深色外框）；`art.py` 的 `status_glyph`，不是 AI 生成。
- **範本隨套件發布**：`scripts/sync_templates.py` 把兩個參考專案複製到 `src/asteria/templates/`（`pyproject`
  的 package-data 包含），`--check` 或測試會在兩邊不一致時失敗；範本內含 `START_HERE.md`（來源
  `docs/templates/`）列出每個規則在編輯器哪裡改，建立專案時顯示在 Console。
- **測試穩定性**：找到並修正先前偶發失敗的測試 `test_every_secondary_job_skill_works_in_battle`（睡眠命中率 80%）。

**限制：** 寵物不是戰鬥單位（沒有自己的血量與回合）；沒有進化與學技能；起始寵物要改 game start 資料（沒有表單）；
隊伍 RPG 的寵物沒有圖示；第三個範本依使用者指示沒有做。

**D25-1 驗證（真實 Cocoa 視窗）：**
| 項目 | 結果 |
| --- | --- |
| 完整測試套件 | 2209 passed；ruff（含 E501）全過 |
| `real_machine_validation.py` 全部檢查 | 64 PASS 第一輪；2 項 FAIL 已查明：`replay_BTL-03` 是因為我把一個測試改名而 replay 清單還指著舊名（已更新清單並加入新測試，重跑 PASS）；`vfx_moderngl_field` 54.6 fps 低於門檻，單獨重跑 55.1 fps PASS（接近門檻，其他程式同時在跑時會掉）。4 項需要真人或手把仍未執行 |
| ARPG demo 三個職業 | 皆 60.0 fps；戰士 3 擊殺、遊俠 3、法師 7 |
| 編輯器稽核 1600×1000／1280×800／1100×700（兩個專案） | 0 缺陷 |

### D25-2 — 破防／加速戰鬥畫面：右側隊伍狀態、行動順序兩邊、指令選單、Break 顯示（使用者指示）

- **隊伍狀態在右邊**（`BattleUiLayoutProfile.party_hud="side_list"`）：每人一格，名稱、狀態縮寫、`HP 5,430 / 5,722`、`SP`、BP 圓點，帶細條；列高依人數自動縮減，不超出畫面。
- **行動順序**：上方每個回合一格，敵我用不同底色（友方藍、敵方紅、目前行動者金色）。
- **指令選單**（`BattleCommands(style="root")`，manifest `battle.command_style`）：Attack／Skills／Items；Attack 列出裝備武器給的攻擊，Esc 回上層，Q／R 調 Boost。
- **Break 顯示**（`runtime/battle_extras.py`）：敵人腳下盾牌數字（還要打幾下）、弱點圖示（命中後顯示，未發現是 ?）、Break 時紅色 BREAK 與「Damage up - loses a turn」。
- **不重疊**：舞台排版給每個敵人一個空間（名稱、精靈、盾牌列），選單放在雙方之間；`test_no_information_covers_other_information_on_the_battle_screen` 對四種遭遇檢查面板、選單、精靈與盾牌列互不重疊。
- 測試：`test_party_rpg_demo.py` 42 個通過。限制：Boost 與武器切換用列表選擇，不是在同一列左右切換。


## D25-3 戰鬥畫面實機回饋修正

- 動作選單改用螢幕座標避開敵人的名字與血條（鏡頭移動時也不會蓋住），行動順序格加高並分開名字與時間。
- 實機驗證腳本改為先開 Attack 清單、用 R 鍵調 Boost，隊伍 RPG 實機檢查 PASS。
- 新增測試：鏡頭移動期間選單不蓋住任何敵人名字。

## D25-4 戰鬥畫面全面不重疊與半透明選單

- 指令選單在隊伍 RPG 排版下改為半透明，優先放在行動角色旁（面向敵人那一側），不蓋住任何敵人的名字、血條、圖案、盾牌與弱點列；放不下時依序嘗試其他空位。
- 隊伍面板改半透明；pygame 後端面板支援 alpha。
- 選單底部說明超過選單寬度時截短。
- 新增 tests/test_battle_screen_no_overlap.py：5 場遭遇、各選單狀態、鏡頭穩定後逐幀檢查文字、面板、量表、圖案、盾牌列互不重疊。

## D25-5 選單可蓋住其他隊友

- 指令選單不再避開其他隊友（版面較好排），仍避開行動角色、所有隊伍血量面板與所有敵人資訊（名字、血條、圖案、盾牌、弱點）。
- 重疊檢查測試同步：非行動隊友不列入阻擋。

## D25-6 選單固定在行動角色旁

- 隊伍 RPG 排版的指令選單固定出現在行動角色左側（變窄而非移位），可蓋住其他隊友，不蓋行動角色、隊伍血量面板與敵人資訊。5 場遭遇逐一截圖確認。
- 實機重跑：input、mv_import、vfx_weather_load 通過；vfx_moderngl_field 在此機器上 44–54 fps（門檻 55），與戰鬥畫面無關。

### D26-1 — Asteria 通用多人連線能力（以 ARPG Demo 驗證）

**使用者要求（2026-10-14）：** 多人連線應是任何 Asteria 遊戲類型都能導入的能力。ARPG 合作打 Boss 是第一個測試案例，不是功能限定的遊戲類型。

**設計提案：** 提供選配的通用連線套件和獨立 headless authoritative server，涵蓋場次、參與者身分、command/state/event 同步介面；各遊戲以 adapter 接入自身玩法。第一個端到端驗證以 2–4 人共同擊敗 ARPG Boss 為例。大型 MMO 的帳號、公開配對、持久世界、relay／代管服務不列入此提案。

**現況：** 通用 TCP session/lobby、command/state/event、可選即時 input/tick API、editor workspace 和兩個 adapter 範例已加入；ARPG 參考 runtime 仍以單一玩家／save 為中心，多人 Boss 戰尚未整合或驗收。細節、風險、分批與驗收草案見 `docs/audits/MULTIPLAYER_DESIGN.md`。

**待確認：** 正式同步模型、server 或玩家兼任 host、場次資料保存、Internet 連線方式及各玩法的品質門檻。現有程式仍是本機／可信任 LAN 原型；command 雙 client 往返曾人工確認，即時移動 adapter 和網路品質尚未實機驗證。


### D26-2 — 多人連線協定收尾與合作 Boss 範例

**使用者要求：** 延續通用多人連線功能，完成更多部分；用實際功能驗證，並確認原有功能沒有回歸。

**做法：** Server 對即時輸入回覆接受／拒絕（含速率限制原因）；adapter state/event 在 revision 前先做嚴格 JSON 與 frame 大小檢查；拒絕無法序列化的更新。新增 `CooperativeBossAdapter`：四人上限、玩家輸入擁有權、移動／攻擊、仇恨目標、階段與範圍攻擊、倒地／救援、一次性獎勵；Multiplayer workspace 可直接選取並預覽 Boss HP 與玩家位置。Ping 顯示 round-trip 毫秒。

**證據：** 新增 loopback TCP 的多人測試，含兩 client 同步移動和共同擊敗 Boss、command 重播只套用一次、輸入重播／速率限制、斷線／重新加入 spawn、adapter 拒絕及 JSON 序列化錯誤。Editor 測試檢查三種 adapter selector、profile save/load、ack 顯示、Ping 文字與 Boss marker。聚焦 multiplayer/editor 測試目前通過 17 個 case；workspace／theme 回歸測試 19 個通過。

**既有功能回歸：** baseline 發現三個舊測試仍把 workspace 數量固定為六；更新斷言以涵蓋新增 Multiplayer 工作區並仍驗證原頁面。Profiler/debugger 在受限 runner 因 loopback bind 權限失敗；獲准本機 socket 後其原有測試 10 個通過。完整 suite 尚待最後重跑。

**限制：** 這個 Boss 是可由兩個 client 真正連線共同操作的 network adapter 範例，尚未把既有 `reference_projects/arpg_demo` 的 ECS、素材、技能與玩家存檔改成多人。沒有 TLS、身分驗證、NAT relay、adapter 沙箱、網路 delay／jitter／loss 注入或 CPU／頻寬量測；不可宣稱公開 Internet 可用。

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
- 既有的 `reference_projects/arpg_multiplayer_demo/build_project.py` 第 14–15 行超過 99 字元（不是這次改的）。


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
| Party RPG 勝利結算 | 參考專案與 party RPG template 都開啟 `battle.victory_aftermath`，並加回歸測試 | demo manifest、template manifest、`tests/test_party_rpg_demo.py`；`1ed4bc8` |
| CJK 訊息字型 | RPG 對話、戰鬥 UI、pygame／ModernGL 對話使用系統 CJK 字型；拉丁文字保留既有字型，附單元測試 | `platform/pygame_battle_ui.py` 等、`tests/test_battle_ui_renderer.py`；`ff9eddb` |

### 驗證證據

- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`：**2637 passed、1 warning**，exit code 0；結束時沒有 Qt／SDL／malloc 崩潰訊息。warning 是既有的 PySide `QMouseEvent` deprecation。
- `.venv/bin/ruff check src tests scripts demos reference_projects`：通過。
- `.venv/bin/ruff check --select E501 src tests scripts demos reference_projects`：通過。
- 有測試覆蓋區域規則編輯、原生骨骼序列化／指令復原、DragonBones 支援子集、Picture 參數與預覽、骨骼 component 存取及 runtime 實際像素繪製、多玩家平滑資料流。
- Cocoa 視窗：Party RPG 戰鬥及勝利結算、區域地板傷害／滑冰／腳步聲、Music Room／Backlog／Credits、`\\C`／`\\I`／`\\V`／`\\N` 和 CJK glyph、編輯器骨骼／區域規則／Terrain／Region／Doodad 面板均有實機程序驗證與截圖。另以兩個 Cocoa runtime 視窗連同一個本機 server；兩邊都收到兩位玩家狀態、各處理 304 個遠端快照，兩個 client 均正常結束。
- 原生按鍵事件佇列、選單／存檔／設定流程已驗證；CoreAudio 開啟 44.1 kHz 裝置、音效 channel 與音樂串流運作。這些程序驗證不代替真人手按、主觀聽感或實際音訊延遲測量。

### 限制與未完成

- DragonBones 僅支援明確實作的 5.x 子集；IK、FFD、z-order、事件／actions、自訂 easing、替代 skin、多 armature／skin 歧義、部分 display／scale／skew／隱藏與顏色動畫等會回報不支援或要求明確選擇，不會自行近似。
- Skeleton component 目前嵌入原生 rig JSON；貼圖仍依專案資源 ID 解析，引用的貼圖必須存在於該專案。
- Picture 預覽使用事件設計畫布座標；點擊命中仍是既有整張圖片矩形規則。
- 真人主觀手感、實體鍵盤直接操作尚未驗收；測試送入 Cocoa／SDL 事件佇列，不代表由人手按鍵。當時沒有連接 game controller；可播放音訊已測到裝置層，但聽感與 latency 未測。
- 兩個 Cocoa 視窗同機 loopback 的多人資料流、插值與預測已驗證；真人主觀延遲／移動手感仍待確認。原生驗證器先前沒有載入 tilemap sidecar，找到問題後補上資源解析；最後的 Cocoa 重驗通過，使用 ARPG demo 的 tilemap 顯示區域 7 編號及半透明蓋層，截圖 `editor_d30_region_overlay.png`。專案檔案保持未改寫。
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

- **編輯器（真實 Cocoa 視窗，`scripts/editor_ui_audit.py`，party_rpg_demo）：** Game Start 分頁、Pet Species、Shops、Pause Menu Entries、Battle Extension Rules 在 1600×1000 與 1100×700 皆 0 缺陷（只有一般的頁面可捲動提示）。截圖：`d31_game_start_tab.png`、`d31_game_systems_icons.png`。
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

**驗證：** 完整測試 **2695 passed、0 failed**；`ruff format`、`ruff check`（含 E501）通過。編輯器稽核（真實 Cocoa 視窗，隊伍 RPG 與動作 RPG 兩個專案，1600×1000、1280×800、1100×700）缺陷 0（唯一 1 項 Enemy AI 窄欄位已修正後重跑為 0）。地圖視窗與自訂暫停選單項目在真實視窗（SDL driver `cocoa`）截圖：`d32_field_hud.png`、`d32_pause_menu_entry.png`；`d32_ability_slots_editor.png`。

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

**限制：** 事件圖示只驗證了資料與繪製呼叫，沒有在真實視窗用實際圖示素材看過；弱點姿勢只對產生出來的角色圖自動有，Party RPG／ARPG 的自訂角色圖沒有 `weak` 片段所以不變；自動戰鬥沒有編輯器表單（用 manifest 鍵）。


## D34 — 剩餘事項的決定與驗證（2026-10-16）

- **`CollisionWorld.from_scene` 快取：決定不做。** 量測（`from_scene` 已走欄位儲存）：100／500／2000 個碰撞器每次 0.05／0.22／0.85 ms，每幀約一次。收益不到 1 ms，而快取要處理啟用狀態、增刪、換場景與移動的失效，風險較大。
- **事件常駐圖示：** 真實 Cocoa 視窗（SDL driver `cocoa`）用 ARPG 專案的物品圖示（`bone_shard.png`）顯示在玩家頭上（`d34_entity_icon.png`）。同一次也確認 `_field_world_xy`（點擊觸發用的螢幕→世界轉換）與 `_field_screen_xy` 往返誤差為 0。
- **手冊：** `ENGINE_HANDBOOK.md` 新增 D27–D33 的系統表，並把「下一步的候選」改成現況：第三個範本與 Web 匯出依使用者指示暫不做。
- **仍未做：** 第三個範本、Web 匯出（使用者指示先不用）；自動戰鬥與低血量姿勢門檻的編輯器表單；專屬技能圖示與隊伍 RPG 寵物圖示。需要外部條件的項目（手把、聽感、WAN）不變。


## D35 — 戰鬥選項表單與原創圖示（2026-10-16）

| 項目 | 做法 | 位置 |
|---|---|---|
| 戰鬥選項表單 | Game Systems > Battle Options（`BattleOptions`：T 鍵自動戰鬥、低血量姿勢門檻）；專案有這筆資料就以它為準，沒有才讀 manifest 的 `battle.auto_key`／`battle.weak_below`；沒設定不寫入 | `rpg/extras.py`、`editor/game_systems_authoring.py`、`playable_test_runtime.battle_option` |
| 原創圖示 | `asteria.graphics.forged_icons`：44 種用程式畫的像素風圖示（武器、元素、治療、狀態、寵物頭像…），4 倍超取樣縮小；以 id 關鍵字對應種類；沒有任何第三方圖片、沒有 AI | `src/asteria/graphics/forged_icons.py`、`scripts/build_original_icons.py` |
| 套用到專案 | ARPG：23 個技能換成原創圖示（藥水沿用道具圖示、狀態沿用既有程式畫的狀態符號）；隊伍 RPG：62 個技能、6 個狀態、2 隻寵物（Frost Lynx、Ember Hound）新增圖示；圖檔在各專案 `playable_assets/icons/skill_*.png`，範本同步；兩個 `build_project.py` 重建後會再套用；CREDITS 註明原創 | `reference_projects/*`、`src/asteria/templates/*` |

**驗證：** 新增 `tests/test_forged_icons.py`（每種圖示畫得出來且不是空白或實心方塊、id 對應、只改 icon 那幾行、兩個專案的圖示檔都存在且可被選單載入）與 `BattleOptions` 測試。Cocoa 真實視窗：隊伍 RPG 的 Pets 畫面顯示 Frosty 的 Frost Lynx 頭像、ARPG 的快捷列顯示新的拳頭與翻滾圖示、Battle Options 表單在 1600×1000 稽核缺陷 0（`d35_*.png`）。

**限制：** 圖示是 32 px 的簡單像素風，不是美術師手繪；技能名稱沒有對上關鍵字的不會有圖示（沿用原本的縮寫）；隊伍 RPG 的戰鬥選單目前不顯示技能圖示（選單版面沒有改）；ARPG 多人副本專案沒有重建，仍用舊圖示。


## D36 — 戰鬥選單顯示技能圖示、沒對上的 id 也有圖示（2026-10-16）

| 項目 | 做法 | 位置 |
|---|---|---|
| 戰鬥選單圖示 | 技能（含武器普攻）與道具的 `icon_id` 帶進選單列（`BattleActionEntry.icon_asset_id`）；畫面端原本就有 `BattleUiIcon` 與 `resolve_icon` 掛鉤，但沒人接：現在由戰鬥畫面把專案的選單圖示載入並畫在每列左側。選單裡只要有一列有圖示，所有列的文字右移 8 個版面單位並預留位置；名稱太長會以「..」截短，不會碰到右側花費。**沒有任何圖示的選單版面完全不變** | `runtime/battle_commands.py`、`runtime/battle_presentation_adapters.py`、`presentation/battle_ui.py` |
| 沒對上關鍵字的 id | `forge_monogram`：以 id 的前兩個字母加 id 雜湊出的顏色畫成寶石，同一個 id 永遠同一張、不同 id 不同色；`apply_to_project_file` 在關鍵字都不符時自動用它（`skill_mono_<id>.png`），所以每個技能、狀態、寵物都有自己的圖示 | `graphics/forged_icons.py` |

**驗證：** `tests/test_forged_icons.py`（含寶石圖示穩定且互不相同、無關鍵字的紀錄拿到寶石）、`tests/test_pets_advanced.py`（選單列帶圖示、圖示可解析、解析失敗時回 `None`）。Cocoa 真實視窗：隊伍 RPG 的戰鬥選單 Attack／Skills 分頁顯示圖示，長名稱截短（`d36_break_battle_menu_icons.png`、`d36_monogram_icons.png`）。

**限制：** 目前兩個 demo 的所有技能都對上關鍵字，所以還沒有專案實際用到寶石圖示；選單圖示固定畫 8 個版面單位寬（約 24 px），細長的武器圖示（法杖、匕首）看起來偏小。


## D37 — 場景開啟時角色置中（2026-10-16）

編輯器開啟專案（或按 Reset View）時，如果場景沒有啟用中的遊戲攝影機，過去是把世界原點放在視窗左上附近，隊伍 RPG 的角色因此偏在一側。現在 `SceneViewportWidget.frame_initial()` 先用遊戲攝影機的範圍，沒有才呼叫 `frame_entities()`：把所有有位置的實體的外框中心放在視窗正中央，實體分布比視窗寬時縮小到放得下（最多放大 1.5 倍，單一實體維持 1 倍）。視窗改變大小時，如果使用者還沒有平移或縮放，視圖會跟著保持置中；平移過就不動它。

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


## D39 — Lucifer 換皮、ARPG 流派與裝備詞條（2026-10-17，使用者要求「全部換成 Lucifer」「ARPG 最重要的是技能樹與裝備詞條」）

**做了什麼：**
- 換皮工具 `scripts/lucifer_reskin.py`、`scripts/reskin_reference_projects.py`：Party RPG、reference RPG、party／basic 範本換成 Lucifer 人物、怪物、背景、UI 面板、字型與圖示；basic 起始範本的主角是 Warrior、怪物是 Skeleton Ancient。build 腳本結尾會自動套用。
- 戰鬥畫面：怪物血條放腳下（`overhead_below`）、角色都站在草地上（`stage_top`）、指令選單在行動角色旁、半透明；選單會蓋住沒在行動的隊友（原本的邏輯，使用者確認這樣是對的），不會蓋住行動中的角色。
- 戰鬥 UI 的像素字型缺很多 ASCII 字元（括號、百分比…），缺的字改用內建字型畫。
- ARPG 兩個 demo：Lucifer 人物與地形、UI Set 1 面板、特效（Foozle Pixel Magic Effects）；每個職業三個流派（各 5 技能、3 被動、1 個互斥的關鍵天賦），共 36 個新技能與 7 種新狀態；元素與暴擊屬性（`crit`、`fire_dmg`、`cold_dmg`、`shock_dmg`、`poison_dmg`）；33 種基底、7 個部位、3 套套裝、10 件獨特裝、約 36 種詞條、六種稀有度、每種怪物的掉落表。
- 引擎：技能欄綁定 `slot:N`、技能樹技能可進技能欄（自動放入空格，等級越高格數越多，最多 6 格）、`vfx` 提示、技能樹節點 `icon_id`；技能樹畫面可縮放（滾輪／+ −）、拖曳平移、點選、R 回到全貌，節點永遠不重疊。
- 編輯器：版面表單顯示全部選填欄位，技能樹表單顯示每個節點的圖示欄。

**驗證：** 全套測試 2944 項通過；`tests/test_arpg_builds.py` 涵蓋流派結構、關鍵天賦互斥、技能欄、詞條與稀有度、掉落、特效、技能樹視圖與編輯器欄位；`scripts/arpg_demo_live_check.py`、`scripts/reskin_live_check.py` 在 Cocoa 真實視窗跑過（60 fps）；`scripts/arpg_balance.py` 九個流派綜合分數在平均的 -12% 到 +20% 之間。

**限制：** ARPG 的投射物與弓／魔杖圖示不是 Lucifer；鎮上的房子是上色的墓穴；平衡只比流派之間，沒有裝備也沒有真人；重建 Party RPG／reference 會換新的專案 id（舊存檔對不上）。


**D39 補充（同日，使用者看了 Cocoa 實機畫面後的修正）：**
- **去掉舊美術**：ARPG 兩個 demo、Boss Trial、Party RPG、reference、範本裡 Ninja Adventure、Kenney、Idylwild 的圖和產生它們的程式都移除了（`art.py` 的 ninja／kenney 函式、`trial_art.py` 的 ninja 程式、三支舊的 `scripts/build_reference_*`）；只留音效檔與 `tests/golden` 的固定測試素材。投射物與特效改用 Foozle Pixel Magic Effects，弓與法杖的圖示用 Lucifer 裝備圖代替，箭是程式畫的。`scripts/prune_orphan_assets.py` 刪掉沒人引用的素材檔，換皮與 Boss Trial 的 build 結尾都會跑。
- **揮劍方向**：Foozle 的 Left 與 Right 攻擊動畫不是鏡像（Left 是由上往下揮，鏡像 Right 會變成由下往上）。隊伍站右邊面向左，所以用 Left 條帶，工作表標記 `facing: left`（`BattleCombatantVisual.art_facing`，不再翻轉）；怪物用 Right。
- **三種攻擊條帶**：普通武器攻擊用第一條；施法、增益、獲得能力、輔助用第二條；大絕招與重擊（神聖技、多段、重砸、斧）用第三條；跳躍用 Jump。ARPG 的四方向角色也有 `attack2`／`attack3`／`jump`，每格依自己的大小放在共同的格子裡（原本不同大小的條帶被壓成同一大小而變形）。
- **異常狀態與特效位置**：狀態名稱放在怪物頭正上方；技能特效以角色本體（不是整張圖框）為中心；斬擊類特效依攻擊方向翻轉（`face_attacker`）。圖框裡待機腳底以下還有別的動畫佔位，所以工作表的 pivot 設在待機的腳底，血條與名字不會蓋到自己。
- **動作結尾**：攻擊、施法、受擊、跳躍的最後一格都是站姿，不會停在半空。
- **卡頓**：Cocoa 實機 5000 幀平均 8.3 ms、最長 10.9 ms；唯一的停頓是第一次放粒子特效時載入 kernel（約 60 ms），改成進戰鬥時預先載入。
- **每個方向都照包裝用**：包裝的四個方向（Left、Right、Up 背影、Down）各有自己的條帶，一律原樣使用，不翻轉、不拼貼、不重排。隊伍站右邊面向左，用 Left（工作表標記 `facing: left`）；怪物站左邊面向右，用 Right；ARPG 四個方向各用自己的。（曾經把 Right 換成「Left 翻轉」，也曾拿 Down 的弧蓋到 Up，都被使用者指出素材本來就有，已還原。）

**D39 再補充（同日，把清單上能修的都修了）：**
- 向上（背對鏡頭）的揮擊：包裝本身就有 Up 條帶，直接照用，不拼貼、不重排（曾經拿 Down 的弧蓋上去，使用者指出素材都有，已還原）。
- 重建不再換 id：`scripts/stable_ids.py` 讓場景與實體 id 在每次 build 都一樣；Party RPG 與 Boss Trial 的 build 結尾重跑兩次結果完全相同。complex_reference_rpg 現在可以從頭重建：`build_project.py` 結尾依序跑 `scripts/build_reference_presentation.py`（特效圖框、動作序列、側視版面與 HUD；原本由已刪掉的舊腳本做）和換皮；專案 id 沿用現有的。它的場景與實體 id 每次重建都是新的（沿用舊行為，已提交的存檔、試玩設定與黃金基準都綁著現有的 id），重建後要重跑 `build_saves.py`、更新試玩設定與 `scripts/update_golden_baselines.py`，所以已提交的版本沒有重建。
- `scripts/boss_trial_live_check.py` 在 Cocoa 實機通過（按鍵打贏三個階段）：原因是腳本在最後一階段還一直把 Boss 血量釘回去。
- ARPG：弓、弩、魔杖的圖示在 Lucifer 沒有對應物，改成程式畫的（32×16、和裝備包同樣的外框，`lucifer_art.weapon_icon`）；鎮上的房子用地城圖集組成（紅屋頂、磚牆、門、窗，商店有條紋遮陽、鐵匠有爐火窗）；每個技能的動畫在每個職業的四個方向都有對應片段（有測試）；四人原生連線驗收 `scripts/validate_multiplayer_project.py` 通過。
- 平衡：`scripts/arpg_balance.py --gear` 讓每個流派穿自己的武器、獨特裝與隨機稀有裝；九個流派在「無裝備／有裝備」輸出的幾何平均落在 400–640（坦克型流派的目標是平均的 75–85%），倍率在 `arpg_builds.BUILD_DAMAGE`。
- 還沒做：受擊閃光是包裝本身的「受傷」動畫（白色、紅色剪影），沒改。

**D39 編輯器啟動（同日）：** 開啟編輯器預設會開 `~/Library/Application Support/Asteria/Projects/Basic RPG`，但這個資料夾只在第一次建立，範本改了它就過期（使用者看到的還是舊的 Ninja 美術）。現在 `ensure_starter_project` 會在資料夾旁記一個範本指紋：指紋變了而專案沒被改過就原地重建；被改過或沒有指紋（更早建立的）就整個移到 `Basic RPG (previous)` 再重建，不會丟東西。左邊面板每次開啟都固定停在 Project 頁(不記住上次的頁籤)。

**D39 戰鬥 UI 統一（同日）：** 所有回合制 demo 與範本（Boss Trial、Party RPG、complex reference、party 範本、Basic RPG 起始專案）都用隊伍 RPG 版面：隊伍 HP 一人一格排在右邊緣（`party_hud=side_list`）、指令選單貼在行動角色旁（`action_menu_placement=actor`）且透明、怪物名字與血條在頭上。選單只可能蓋到「非行動中的隊友」，不會蓋到行動角色或任何怪物（`menu_over_stage` 不再讓選單蓋怪物）。Boss Trial 的怪物不再隱藏血條，Basic RPG 起始專案不再覆寫站位與怪物縮放。`tests/test_lucifer_art_rules.py::test_every_turn_based_demo_uses_the_break_battle_ui` 守住這組設定。

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
| 主角與攝影機 | 每個 `Camera2D` 跟著起始玩家，站在玩家所在或抵達的位置；只是重複 Player 位置的起始座標會清掉，所以在編輯器移動 Player 就是移動遊戲起點；主角用和其他角色一樣的腳底碰撞框；Party RPG、complex reference、party 範本每個場景都有一台跟著主角的 Camera；沒有圖塊地圖的「圖片場景」照作者設定的 Camera 取景（manifest 的攝影機設定仍優先） | `editor/scene_cameras.py`、`scripts/center_cameras.py`、`runtime/field_camera.py`、`runtime/playable_test_runtime.py` |
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

**實機證據：** [`evidence/full_verification_campaign/`](evidence/full_verification_campaign)：整段劇情在 Cocoa 視窗跑完，先用真的按鍵走路與對話，再跑完 4 張地圖、9 場戰鬥；2026-10-22 重新產生（D51）。`d43_skill_tree_graph.png`：編輯器裡勇者技能樹的圖示卡片與箭頭。

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
- **沒有翻譯表的畫面不變**：新舊引擎（舊的＝HEAD 版本的這批檔案＋工作目錄其他檔案）各畫 12 個畫面（標題、野外、暫停、設定、任務、成就、圖鑑、遊戲結束、存檔、狀態、戰鬥指令、技能清單），Party RPG、Complex Reference（都沒有表）與英文的 Full Verification 共 36 張逐像素相同。

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

**測試：** `tests/test_battle_hud_portraits.py`（46 項）：選項只在有設定時寫入、舊資料照讀、錯的值會擋下；編輯器的下拉與中英文、肖像選擇器；三種 HUD × 左／右／上方：肖像在自己的卡片裡，不碰到自己的名字、血條、狀態圖示，卡片大小（放旁邊不變、放上方剛好長高肖像＋2），卡片不重疊、不出畫面；沒有肖像的卡片樣子完全一樣（放旁邊時連位置都一樣）；`off` 和沒有肖像的畫面相同；同一清單或欄位一樣大；大小肖像的選擇與互補；大小選項與極限（滿的側欄只用剩下的空間、太窄的卡片不畫）；四種版面 × 三個行動角色，指令選單、說明框、目標框都不蓋肖像，沒擋到時位置不變；快取（肖像改了才重排）；Headless 後端的繪製順序；pygame 後端的縮放與置中；Party RPG demo 的真實戰鬥（肖像畫在方格裡、圖不存在的不畫、`off` 不畫）。完整測試 3181 通過、1 略過、0 失敗（`pytest -q`，約 5 分鐘）；`ruff check`、`ruff format --check` 乾淨。

**實機證據：**
- `scripts/battle_portraits_live_check.py`（Cocoa 視窗，真的跑 frame 到第一位主角的回合、指令選單開著）PASS：五場戰鬥每張肖像都和縮放後的圖逐像素相同（0 個像素不同），沒有字、血條或選單蓋到。肖像用 Ninja Adventure 的 CC0 facesets（Hunter、SorcererBlack、Vampire、SamuraiBlue，取自 `local_reference/`）代替動漫臉，專案只在記憶體裡改。截圖：`d53_vigil_side_list.png`（Portrait Party Layout：身體隱藏、側欄、肖像在左）、`d53_vigil_side_list_right.png`（肖像在右）、`d53_break_battle_side_list.png`（側視戰鬥、身體顯示）、`d53_break_battle_column.png`（引擎預設的欄位 HUD）、`d53_break_battle_bottom_row_above.png`（底列、肖像在上方 30 單位）；結果在 `d53_battle_portraits_results.json`。
- 編輯器（Cocoa，`--editor`）：`d53_editor_battle_ui_layout.png`／`_zh.png`（Battle Screen ▸ Battle UI Layout 的 HUD Portraits 下拉與 HUD Portrait Size，含說明）、`d53_editor_combatant_portraits.png`／`_zh.png`（Combatant Sprites 的 Portrait 肖像選擇器：預覽、清單、Browse…）；英文與繁體中文都畫出（語言只對這個視窗切換，沒有存設定），結果在 `d53_editor_results.json`。
- **沒有肖像的畫面不變**：舊引擎（改之前的 src，HEAD 03558c5f）與新引擎各畫 Party RPG（boss_room、slime_pit、samurai_duel）、Full Verification（acolyte_vigil、boss_room）、Complex Reference（boss_room）六場戰鬥，每場五個時刻（主角回合後第 1、60、240 幀，按下、再按確定之後），共 30 張逐像素相同。

**限制：**
- 肖像只在 HUD 卡片上；`BattleUiAssemblyRuntime` 仍沒有接到實際戰鬥流程（和之前一樣）。
- 頭頂資訊（overhead）的成員沒有卡片，所以不畫肖像。
- 「上方」在滿的側欄（例如 Vigil 4 人 × 4 列）沒有剩下的空間，肖像不會出現；側欄建議用左或右。
- 肖像不會依狀態換臉（受傷、倒地），也沒有外框樣式可選。
- 既有、與肖像無關：欄位 HUD 的數字在 Party RPG 字型下 4 位數時會壓到血條右端；Battle UI Layout 表單的 Command Counts、Stage Front Right 兩個欄位名還沒有中文。

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

**相容：** 沒有設定這些選項的專案站位完全不變：Party RPG（boss_room、gazer_nest）與 Complex Reference（boss_room）的座標相同，改之前（HEAD 的乾淨副本）和改之後的 Cocoa 截圖逐像素相同（3 張，0 個像素不同）。目前只有 Full Verification 有站位範本，所以「腳站在地面」預設開也只影響它（Crypt Guard 的 Aldric）。

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

## D57 — 刪掉盤點出來沒人用的 presentation 程式（2026-10-23）

**要求：** D56 的 presentation 用量盤點列出三處沒有任何引用的程式，使用者逐項核准刪除：`presentation/preview.py`、`presentation/workspace_controller.py`，以及 `presentation/performance.py` 裡沒人用的類別。

**做了什麼：**
- 刪除 `presentation/preview.py`（130 行：`PreviewDiagnostic`、`PreviewExecutorRegistry`、`PresentationPreviewSession`）與 `presentation/workspace_controller.py`（104 行：`AssetIntakeRequest`、`AssetIntakeAction`、`PresentationWorkspaceController`、`ASSET_INTAKE_INVARIANTS`）；兩者只互相引用，`src/`、`tests/`、`scripts/`、`reference_projects/` 都沒有用到。`presentation/__init__.py` 拿掉它們的 `from .x import *`。
- `presentation/performance.py` 只留 `FrameBudget`、`FrameDiagnostics`、`diagnose`（`fidelity_editor.py` 在用；`diagnose` 回傳 `FrameDiagnostics`，所以它雖然在外面沒被點名也要留）；刪掉 `IndexedEvents`、`BoundedDispatcher`、`ReuseBuffer`、`DegradationPolicy`、`DEFAULT_DEGRADATION_POLICY`（盤點說的五個名稱裡，`FrameDiagnostics` 其實有人用，改刪 `DEFAULT_DEGRADATION_POLICY`）。
- 風險文件 RISK-07 的待辦清掉。

**測試：** 全部 3205 個測試通過；`asteria.presentation` 與 `asteria.editor` 照常 import。

**狀態：** 已提交（2026-10-23，使用者要求）。

## D58 — README 重寫；匯出修好並實測三種成品；歷史文件標示（2026-10-23）

**要求：** 使用者問 repo 上有沒有寫清楚這個專案是什麼、怎麼安裝、怎麼用、要不要打包。

**做了什麼：**
- `README.md` 重寫（中文為主、附英文摘要）：特色、安裝（extras 說明、C++ kernel 選用）、五個指令（`asteria-editor`、`asteria-preview`、`asteria-upgrade`、`asteria-export`、`asteria-import-mv`）、從範本開新專案、遊戲鍵位、範例專案表、開發與實機驗證指令、CI、文件地圖、授權狀態。舊 README 的 Batch 98 歷史內容移除（git 歷史與 `ASTERIA_PROGRESS.md` 仍有）。
- **匯出修好**：`asteria-export` 對 Full Verification 失敗，因為兩個粒子特效資產（`fx.divine_burst`、`fx.restore`）是純資料、`source.uri` 為空，`referenced_files` 把空路徑算成 `.` 而判定缺檔。現在沒有檔案的資產直接略過。新增 `tests/test_migration_and_export.py::test_export_skips_data_only_assets_that_have_no_file`。
- **三種成品都實跑過**（2026-10-23，repo 外的資料夾，各跑 120 格後正常結束）：遊戲資料夾（26 MB，`python run_game.py`）、單檔 `Asteria_Full_Verification_Demo.pyz`（11 MB）、macOS `Asteria Full Verification Demo.app`（用 `ASTERIA_PYTHON` 指定直譯器）。所以「打包」已經有：使用者只需要對專案跑 `asteria-export … --pyz --app`。
- `START_HERE_MAC.md`、`PROJECT_HANDOFF.md` 頂端標示為歷史文件並指向 README／手冊；`VSCODE_QUICK_GUIDE.md` 指向 README。

**限制：** 程式碼授權還沒決定（沒有 `LICENSE`），使用者說之後再定；成品仍需要使用者機器上有 Python 3.12+ 與 pygame-ce（.app 不是自含的）。

**狀態：** 已提交（2026-10-23，使用者要求）。

## D59 — Web 匯出：Asteria 專案在瀏覽器裡玩（pygbag）（2026-10-23）

**要求：** 使用者 2026-10-23 決定做 Web 匯出（手冊「下一步的候選」第 5 項）。先盤點依賴（`docs/audits/WEB_EXPORT_ASSESSMENT_2026-10-23.md`），使用者核准路線 A（pygbag：CPython + pygame-ce 編成 WebAssembly）、把 Noto Sans TC 放進 asset_library 預設帶上、runtime 預設從 CDN 載入（`--cdn` 留給自架）、存檔先用 localStorage。

**做了什麼：**
- **匯出指令** `python -m asteria.export_web PROJECT.json OUT_DIR`（也裝成 `asteria-export-web`；`src/asteria/export_web.py`）。寫出 `OUT_DIR/<遊戲>/`：專案與它引用的每個檔案（含各包的 CREDITS／LICENSE，重用 `project_tools.export_game`）、精簡的引擎（排除 `editor`、`multiplayer`、`validation`、`templates`、`kernels/native`、`__pycache__`，4.1 MB 原始碼）、`fonts/NotoSansTC-Regular.otf` 與 OFL 授權、pygbag 要跑的 `main.py`；再呼叫 `pygbag --build --no_opt --disable-sound-format-error`（`--no_opt`：pygbag 的最佳化會把 PNG 有損重新量化、重新編碼音訊，像素圖不能給它碰），產物在 `build/web/`（`index.html`、圖示、遊戲 `.tar.gz`／`.apk`），整個資料夾放到任何靜態主機或 itch.io 即可。選項：`--serve [--port]`（建好後用自己的靜態伺服器開在 `http://127.0.0.1:PORT/`）、`--no-build`（只寫資料夾；配 `--serve` 開上次建好的）、`--cjk-font PATH|none`、`--cdn URL`、`--icon PNG`、`--allow-missing`、`--allow-unsupported-audio`（mp3 等瀏覽器不能解的格式預設拒絕匯出）、`--width/--height`。pyproject 新增選用依賴 `web=["pygbag>=0.9"]`。
- **`main.py`**：async 主迴圈（每幀 `runtime.step(dt)` 後 `await asyncio.sleep(0)`）、`ASTERIA_KERNELS=python`、`ASTERIA_CJK_FONT` 指向帶上的字型、存檔鏡像每 30 幀同步、每 600 幀在 pygbag 的終端印一幀的毫秒數；`RUNTIME` 全域給頁面的 Python 主控台用。同一個檔在桌面也能跑（`ASTERIA_WEB_MAX_FRAMES`、`ASTERIA_WEB_FAKE_STORAGE`），測試就是這樣驗它。
- **瀏覽器裡的存檔** `runtime/web_persistence.py`：`FolderMirror` 把 `saves/`（slot、autosave、settings.json）鏡像到 `localStorage`（鍵 `asteria.saves.<檔名>` 加一個 index 鍵）；開場 `restore`、之後 `sync` 比對大小與 mtime 只寫有變的、刪掉的也忘掉。遊戲程式碼照舊寫檔。
- **引擎守衛（桌面行為不變）**：`image_preloader.py` 在 emscripten 不開執行緒（`threads` 參數；沒有執行緒時每幀同步解一張，`_Loaded` 長得像 Future）；`platform/pygame_battle_ui.py` 的 `cjk_font_path` 先看 `ASTERIA_CJK_FONT`（桌面匯出也可用，順便補了 D52 記的「匯出不附中文字型」）；`PlayableTestRuntime.step(dt, events=None)`（`run()` 改呼叫它）；`multiplayer_preview` 的 import 改成可缺（沒有 multiplayer 套件時 `multiplayer_profile_error` 說明）；`runtime/profiler.py` 不再硬性 import `resource`、`tracemalloc`、`statistics`（pygbag 的 CPython 3.12 三個都沒有；用探測頁掃過引擎全部 import，缺的只有這三個加上本來就只在桌面用的 certifi／zipapp）。
- **pygbag 的四個坑，匯出工具都繞掉了**：(1) 它自己下載頁面模板與圖示用 urllib，python.org 的 Python 沒憑證會卡住 → 匯出工具自己抓（urllib → certifi → curl）到 `OUT_DIR/.pygbag-cache/` 再用 `--template`／`--icon` 傳給它；(2) 它的測試伺服器會把 CDN 改成本機代理、代理又用同一個沒憑證的 Python → `--serve` 改用自己的靜態伺服器（不加 `cross-origin-embedder-policy`，否則擋 CDN）；(3) 它的 runtime 看到網址是 `localhost:8xxx` 就當成自己的開發伺服器、去 `localhost:8000/cdn/` 找 pygame → 用 `127.0.0.1` 開；(4) 它只從 `main.py` 頂層的 import 決定要載哪些 wasm 套件 → `main.py` 頂層 `import pygame`。
- **字型**：`asset_library/fonts/noto_sans_tc/NotoSansTC-Regular.otf`（5.4 MB，SIL OFL 1.1，`LICENSE.txt`，`THIRD_PARTY_ASSETS.md` 登記）。`assets/library.py` 列圖包時略過沒有圖片的資料夾（字型不是圖包，`test_asset_library` 的 CC0 檢查不套在它身上）。
- 評估文件 `docs/audits/WEB_EXPORT_ASSESSMENT_2026-10-23.md`（路線比較與依賴表）。
- **靜音開關**（使用者 2026-10-23 要求測試不要出聲）：`ASTERIA_MUTE=1` 讓 `open_audio_device` 一律回傳無聲的 `RecordingAudioDevice`（真實視窗的 live check 也不出聲）；網頁版網址加 `?mute=1` 同義。全域 skill `~/.claude/skills/quiet-testing` 規定自動化檢查一律帶著它。

**測試：** `tests/test_export_web.py`（13 項）：app 資料夾的內容與排除、`main.py` 在桌面無頭跑 40 幀（同一段 async 迴圈）、pin 住純 Python kernel 與字型、mp3 拒絕與 `--allow-unsupported-audio`、pygbag 命令列、靜態伺服器的回應與 wasm 媒體型別、存檔鏡像（還原、只寫有變的、刪除、壞掉的 index 與奇怪檔名）、預載器無執行緒逐位元相同、瀏覽器預設不開執行緒、`ASTERIA_CJK_FONT` 優先且真的畫得出中文、`step()` 是 `run()` 用的那一幀。`test_asset_library`、`test_image_preloader`、`test_built_in_text`、`test_runtime_profiler` 照常。全套 pytest 見狀態。

**實機證據（`docs/audits/evidence/web_export/`，`results.json` 逐項）：** 內建瀏覽器（Chromium）開 `http://127.0.0.1:8765/`，runtime 從 pygame-web CDN 載入（CPython 3.12.12 wasm、pygame-ce 2.5.7），遊戲包 13.0 MB。標題 → N 新遊戲 → 鍵盤走路、Esc 暫停 → 設定 ▸ 語言切繁體中文（Noto Sans TC 畫的，`05_settings_zh`、`06_pause_zh`、`10_loaded_field_zh`）→ F5 存檔，`localStorage` 出現 index、settings.json、autosave（12,960 字）→ 重新整理頁面 → L 讀取畫面列出 Autosave（`09_load_screen_after_reload`）→ 讀回後語言仍是中文 → 戰鬥（`11_battle`）。每幀在 `step()` 裡的 CPU 時間：標題 13.5–14.2 ms、野外走路 5.2–7.2 ms、戰鬥待機 3.2–3.7 ms（60 fps 的預算 16.7 ms）。截圖是在頁面裡用 `pygame.image.save` 存到 Emscripten 檔案系統再 POST 給 `--serve` 的 `/shot` 端點（瀏覽器工具的截圖拿不到 WebGL canvas 的內容）。

**限制：**
- Web 上沒有：編輯器、多人連線（沒有 TCP socket）、ModernGL 後端、C++ kernel（純 Python kernel）、debug server、預先解碼的執行緒（改成每幀解一張）、手把沒驗。
- 玩家開頁面時要能連到 pygame-web 的 CDN 下載 Python runtime（約 20 MB，瀏覽器快取）；完全離線要自架一份並用 `--cdn`。
- 存檔在同一個瀏覽器、同一個網址的 `localStorage`（約 5 MB 上限，清站台資料就沒了）；沒有匯出／匯入存檔檔案。
- 音訊只有 `.ogg` 與 `.wav`；wav 有沒有真的出聲沒有自動化檢查（沒有音訊擷取）。
- 第一次載入約 20–30 秒（下載 runtime 與解壓 13 MB），之後有快取。標題畫面每幀 14 ms 比野外還貴（整張背景每幀縮放）。
- 要用 `127.0.0.1` 開本機測試頁，`localhost:8xxx` 會被 pygbag 的 runtime 誤認。
- 鍵盤：瀏覽器自動化工具送的按鍵沒有 `code` 欄位時 SDL 收不到（真人按鍵正常）。
- 工作目錄同時有另一個 session（寵物／創造物）未提交的改動；本批的檔案清單見狀態。

**狀態：** 已提交（2026-10-23，使用者要求；只含本批檔案，`playable_test_runtime.py` 只提交兩段）。本批的檔案：`src/asteria/export_web.py`、`src/asteria/runtime/web_persistence.py`、`src/asteria/runtime/image_preloader.py`、`src/asteria/runtime/profiler.py`、`src/asteria/platform/pygame_battle_ui.py`、`src/asteria/assets/library.py`、`src/asteria/runtime/playable_test_runtime.py`（只有 multiplayer import 與 `step()` 兩段）、`pyproject.toml`、`THIRD_PARTY_ASSETS.md`、`asset_library/fonts/`、`tests/test_export_web.py`、`docs/audits/WEB_EXPORT_ASSESSMENT_2026-10-23.md`、`docs/audits/evidence/web_export/`、本文與手冊。

## D60 — 專案資料翻譯：名稱、說明、對話依語系不同（2026-10-23；T1 引擎）

**要求：** 使用者 2026-10-23 決定做「專案資料的翻譯」（手冊「下一步的候選」第 3 項）：角色、職業、技能、道具、裝備、狀態、敵人、任務、地圖名、對話的名稱與說明可依語系不同；沒設定就不寫入、舊專案照讀；編輯器有翻譯表可編；Full Verification 做 zh-TW 示範並在真實視窗切換語言截圖。核准的做法：**鍵放在現有的翻譯表**（D52 的 `LocaleTable`），**對話用選填的 `text_key`**。分三批：T1 引擎、T2 編輯器翻譯頁、T3 demo 示範與實機證據。

**做了什麼（T1）：**
- **鍵的規則** `rpg/data_text.py`：`data.<種類>.<id>.name`、`data.<種類>.<id>.description`；種類由紀錄的類別決定（`KINDS`，29 種：actor、class、ability、passive、attack、state、item、equipment、attachment、equipment_set、growth、growth_node、rarity、affix、enemy、quest、objective、shop、recipe、pet_species、skill_tree、skill_tree_node、track、stat、faction、achievement、interaction、party、drop_table）。另外 `data.map.<場景 id>.name`（地圖名）、`data.speaker.<名字>.name`（說話者）、`data.currency.<id>.name`（貨幣）、`data.resource.<id>.name`、`data.slot.<id>.name`（狀態選單的資源與部位）。紀錄本身的資料完全不改。
- **取字**：`GameSessionRuntime.name_of(record, fallback)`、`description_of`、`map_name`、`line_text`、`speaker_of`、`prompt_of`、`pet_display`、`currency_names`（`runtime/session/messages.py`、`pets.py`、`rewards.py`）。`data_lookup` 在專案沒有任何翻譯表時是 None，畫面直接用紀錄自己的字、不查表。
- **畫面**：約 70 處直接讀 `display_name`／`description` 的地方改走上面的方法：商店、任務紀錄與野外任務追蹤、製作、成就、圖鑑、技能欄、寵物、技能樹（大小兩種畫面）、角色養成與工坊（測試用畫面）、背包（含隨機詞綴與套裝，`rpg/loot.item_display_name` 加選填 `name_of`）、狀態選單（道具、裝備、技能、被動、能力值、資源、部位）、動作 HUD 的狀態與技能、地上掉落物的標籤、獲得道具／裝備壞掉的通知、新裝備提示、存檔欄的地圖名與隊長名、戰鬥（成員名、技能名與說明、道具、調合材料、狀態、捕獲、技能不能用的原因）、勝利頁（道具；被擊敗的敵人與貨幣只在有翻譯時換字，沒有表的專案照舊顯示 id）、訊息控制碼 `\N[..]`／`\P[..]`。戰鬥技能名的順序：翻譯 → manifest 的 label → id。
- **對話**：`DialogueLine.text_key`、`DialogueChoice.text_key`、`ChoiceRequest.prompt_key`（都只在有設定時寫入，舊資料照讀）；DIALOGUE／CHOICE 指令的參數 `text_key`、`prompt_key`；野外訊息框、選項、說話者、訊息紀錄、tilemap 場景的對話都查表。
- 開發用的錯誤訊息（`GameSessionError` 的職業解鎖原因等）維持英文（同 D52）。

**測試：** `tests/test_data_text.py`（9 項）：每個種類都對得上真的紀錄類別與 id 欄位、種類不重複；查不到時回到紀錄自己的字；對話鍵只在有設定時寫入、舊資料照讀、多餘欄位拒絕；Full Verification 加上一組 zh-TW 資料鍵後，道具、角色、技能名與說明、狀態、地圖名、成就、圖鑑、貨幣、商店、任務與目標、`\N[hero_01]`、對話與選項與說話者、戰鬥成員名與技能名都換成中文，切回英文就還原；沒有翻譯表時 `data_lookup` 是 None、勝利頁照舊用 id；**原始碼掃描**：`runtime/` 與 `presentation/` 不再有直接畫 `display_name` 的地方（允許清單：開發錯誤、資料複製、寵物戰鬥單位、多人連線名稱、presentation 自己的 view model，以及明確標記的無 session 後援）。全套 3243 通過、1 略過；`run_campaign.py` 結束碼 0（REQUIRED 全有）；ruff 乾淨。

**畫面不變的證據：** HEAD 的引擎（`git archive HEAD`）與目前工作目錄各畫 13 個畫面（標題、野外、暫停、設定、任務、成就、圖鑑、讀檔、技能欄、訊息紀錄、製作人員、遊戲結束、戰鬥），Party RPG、Complex Reference、英文的 Full Verification 共 **39 張逐像素相同**（狀態畫面兩邊都要先選角色才能開，這次沒比到）。

**限制（T1）：**
- 編輯器還沒有資料翻譯的頁面（T2）；Full Verification 還沒有資料的 zh-TW 翻譯（T3）。
- 同一個 id 的技能樹節點出現在兩棵樹時共用一個翻譯（鍵只看節點 id）。
- presentation 的戰鬥畫面模型（`rpg_character_screen`、`rpg_inventory_screen`）自己產生的標籤經狀態選單轉換；直接用這兩個模型的程式要自己呼叫 `name_of`。
- 工作目錄同時有另一個 session 的創造物改動，部分檔案兩邊都改（提交時分 hunk）。

**T2：編輯器的翻譯頁（2026-10-23）**

- **專案資料分組**（`editor/data_translation.py`，不依賴 Qt）：Database ▸ Game Systems ▸ Translations 在引擎字詞與專案名稱之後列出專案資料，每種紀錄一組（角色、職業、技能、被動、狀態、道具、裝備、鑲嵌物、套裝、裝備成長、稀有度與詞綴、敵人、寵物物種、任務〔含目標〕、商店、製作配方、技能樹〔含節點〕、成長軌道、能力值、陣營與成就、場景互動、隊伍設定與掉落表），加上地圖名稱、貨幣、說話者，以及已有鍵的台詞與選項。每列：鍵、英文（紀錄自己的字）、譯文。Full Verification 共 1,746 列；資料分組預設收合，搜尋時有符合的組自動展開；「顯示」多一個「專案資料」；計數多「資料文字 N 個 · 已翻譯 M 個」。頁面建立 55 ms（第一次 149 ms），搜尋 11 ms。
- **鍵已經對不到紀錄的**（紀錄被刪了）留在表裡，列在「專案自訂的鍵」組，不會不見。
- **替對話產生鍵**：按鈕把每個沒有鍵的 DIALOGUE 台詞、CHOICE 選項與提示加上 `dlg.<事件程式>.<指令序號>`（選項 `.<n>`、提示 `.prompt`；重名時加 `_2`），整批是一個可復原步驟（`CommandTransaction` 加 `ReplaceEventProgramCommand`），台詞本身不改、已有的鍵保留；只寫了 `\T[..]` 的台詞本來就從翻譯表取字，不給鍵。Full Verification：41 個事件程式、106 個指令拿到鍵，之後頁面列出 173 列台詞與選項；Ctrl+Z 全部還原（頁面的資料快取跟著文件修訂號更新）。
- 新的介面文字（26 個分組標題、篩選、按鈕、提示、兩個樣板）都有 zh_TW。

**T2 測試：** `tests/test_data_text.py` 新增 6 項（共 15 項）：資料分組列出名稱與說明、地圖、貨幣、說話者，鍵不重複；產生鍵一次可復原、不改字、已有的鍵保留、第二次按不再改；頁面資料組收合、搜尋展開、「專案資料」篩選、對不到紀錄的鍵留在自訂組；復原後頁面跟著更新；只有 `\T[..]` 的台詞不給鍵；新字詞都有中文。全套 3247 通過、1 略過、2 失敗：都是 `test_built_in_text` 抓到另一個 session 進行中加的 `creature.close_bag` 鍵（不是本批）。

**T2 實機證據（`docs/audits/evidence/data_translation/`）：** `scripts/data_translation_editor_live_check.py`（Cocoa 視窗，Full Verification）PASS：`t2_en_data_groups`（資料組收合）、`t2_en_search_healing`（搜尋「Healing」展開技能、道具、配方）、`t2_en_project_data_filter`、`t2_en_dialogue_keys`（按下後的台詞與選項組）、`t2_zh_project_data`、`t2_zh_search_aegis`（中文介面）；`results.json` 記下計數、產生前後沒有鍵的數目、復原後計數回到 1,746。`editor_ui_audit.py` 的 Translations 頁在 1600×1000 與 1100×700 都 0 缺陷（只有整頁上下捲）。截圖從工作目錄拍（另一個 session 的改動不碰編輯器這頁）。

**T2 限制：** 戰鬥序列（`BATTLE_SEQUENCE` 的軌道）裡的對話不在清單、也不會產生鍵；資源與裝備部位（`data.resource.*`、`data.slot.*`）沒有自動列出，要用「新增鍵」；同一個說話者名稱在不同事件裡共用一個翻譯。

**T3：Full Verification 的繁體中文（2026-10-23）**

- **翻譯方式**：`trial_zh_data.py`（`apply(project)`，`build_project.py` 在 `finalize_names` 之後呼叫，也能直接套在已建好的專案上，重複套用不會多加）先替每句對話產生鍵，再把 Translations 頁列出的每一列翻成中文寫進 zh-TW 表（已在表裡的鍵不覆蓋）。demo 的名稱有固定句型（「Fire Bolt (Echo)」「Rune: Siphon (Holy Blade)」「Spec: Frost」「Vigor Notable 3」「Bishop Training」「Flawless Ruby」「Craft amethyst_item」…）、技能說明由固定片語組成（「Magic / Dark: all foes, 4 hits, inflicts Magic Down」），所以翻譯是詞彙表加句型：`trial_zh_words.py` 的 `WORDS`（約 690 個詞：人物、地點、職業、敵人、能力值、狀態、武器、道具、裝備、技能、被動、節點）、`DESCRIPTION`（說明的開頭與片語、能力值與任務的整句說明）、`LINES`（155 句台詞與選項）。接在「施加／自身獲得／解除」後的多個狀態用頓號接續（「施加暈眩、燃燒」）。
- **結果**：1,923 列全部有中文（`missing()` 為空），對話 106 個指令、41 個事件程式有鍵；英文表沒有任何 `data.*`／`dlg.*`（英文照紀錄自己的字）。只寫 `\T[..]` 的台詞（區域名稱）本來就由 D52 的表翻，不給鍵。
- **T3 順手補的引擎缺口**（實機截圖時看到的英文）：互動提示的 NPC 名稱（`speaker_name`，同說話者的鍵）、狀態選單右上的角色名、新裝備提示裡的部位 id（`slot_name`，`data.slot.<id>.name`；Translations 頁多一組「裝備部位」）、戰鬥側欄狀態字（`BattleHudRuntime.state_label`，由 adapter 接 `data.state.<id>.name`）、商店價格與錢包的貨幣名（`currency_names`，一次算好整張表）。
- **run_campaign**：學者林切到中文時，檢查 6 個專案名稱（角色、道具、敵人、技能、地圖、任務）畫出的是中文，新事實 `translated_data`（6）加進 REQUIRED；整段劇情結束碼 0。

**T3 測試：** `tests/test_data_text.py` 共 17 項：demo 每一列都有中文、每句對話都有鍵、重複套用加 0、英文表沒有資料鍵；句型翻譯的例子（符文、變體、交會、技能書、製作、說明的頓號、「+」相連的屬性）；T1／T2 的測試改從「未翻譯的 demo」開始（`_plain`）。全套 3253 通過、1 略過；ruff 乾淨。

**T3 實機證據（`docs/audits/evidence/data_translation/`）：** `scripts/data_translation_live_check.py`（Cocoa、真的按鍵、`ASTERIA_MUTE=1`）PASS：同一組畫面先英文再中文——跟守衛瑟莎莉說話（`t3_*_dialogue`：說話者與台詞）、狀態選單的道具／裝備／技能（`t3_*_items`、`t3_*_equipment`、`t3_*_skills`）、商店（`t3_*_shop`：「30 金幣」）、任務紀錄（`t3_*_quests`）、戰鬥（`t3_*_battle`：隊伍名、頭上的「哥布林投石兵 1」、側欄「流血 失明」）、技能清單（`t3_*_battle_skills`：名稱與說明的語言跟著切換）、勝利頁（`t3_*_victory`：「打倒了：哥布林投石兵」「金幣 +786」）。`results.json` 記下每張圖畫出的字；中文畫面上沒有任何一個表裡有翻譯的專案名稱以英文出現。編輯器那支（T2）改在記憶體裡先拿掉 demo 的翻譯與鍵再操作，證據照舊。

**T3 限制：**
- 翻譯是我寫的，需要使用者讀過；名詞統一見 `trial_zh_words.py`。少數由程式產生、沒有可讀名稱的紀錄（`w_bone_scepter Enchant`）照 id 的意思翻。
- 頭目、戰鬥中的說話（`BATTLE_SEQUENCE`）、music room 的曲名、製作人員名單、manifest 的技能 label 還沒有資料鍵。
- 標題畫面的副標題（「Complex Reference RPG」）是 manifest 的字，不在表裡。
- demo 的 `project.asteria.json` 這次是用 `trial_zh_data.apply` 直接套在現有檔案上（讀存不改其他內容），沒有重跑整個建置（工作目錄有另一個 session 直接寫進這個檔的改動）；`build_project.py` 已接上，下次重建會產生同樣結果。

**狀態：** 已提交（2026-10-24，使用者要求；只含本批檔案：與另一個 session 共用的 8 個程式檔是 HEAD 加上本批的改動，`zh_TW.json` 只含本批的 31 個詞與 2 個樣板，demo 的 `project.asteria.json` 是 HEAD 版本套用 `trial_zh_data.apply` 的結果）。

## D61 — Full Verification 補武器、道具、裝備（2026-10-24；G1 武器）

**要求：** 使用者 2026-10-23 要求 Full Verification 的武器、裝備與道具補多：每種武器類型（劍、斧、矛、弓、匕首、法杖、書、拳、投擲）都有數把、分稀有度；防具每個部位多幾件；道具（藥水、狀態藥、戰鬥投擲、材料、寶珠、卡片）多一批；圖用 asset_library 的 CC0 圖並登記；商店買得到、工坊能精煉與鑲嵌；run_campaign 事實跟著增加；編輯器 Database 看得到。使用者核准的做法：部位維持「防具」與「飾品」兩個；7Soul 496 icons 放進 asset_library，新東西都用它；爐心鎮加武器、防具、道具三間新商店；寶珠＝可鑲嵌、讓武器帶屬性的珠子。分三批：G1 武器、G2 防具飾品道具、G3 商店與驗證。

**做了什麼（G1）：**
- **素材**：`asset_library/opengameart/7Soul_496_RPG_Icons/`（496 張 34×34，1.9 MB，原檔不改）。授權 2026-10-24 重新查 OpenGameArt 頁面：License 欄位 CC0，作者另稱 Public Domain；`Readme.txt` 記出處；`THIRD_PARTY_ASSETS.md` 登記；demo 的 `CREDITS.md` 由 `trial_art.write_credits` 寫入一列（`trial_arsenal.credits_rows`）。
- **`trial_arsenal.py`**（`build_project.py` 在翻譯之前呼叫；也能直接套在已建好的專案，重複套用加 0）：
  - 三種新武器類型的普通攻擊 `attack_book`、`attack_fist`、`attack_throw`：複製既有的法杖／匕首／弓攻擊，換成 `weapon.book`／`weapon.fist`／`weapon.throw` 標籤（弱點與抗性讀這個標籤），同樣的命中檢查；戰鬥選目標規則照抄；manifest 的戰鬥名稱「Attack (book)」等（建置時寫進 `skill_names`，現有檔案用 `patch_manifest`）。
  - 29 把新武器，每種類型補到至少 5 把且五個稀有度都有：劍 +2（騎士之刃、煉獄之刃）、斧 +2（戰鬥斧、嗜血斧）、矛 +3（闊頭槍、潮汐三叉戟、穿天槍）、弓 +3（反曲弓、不死鳥之弓、星墜之弓）、匕首 +2（左手短劍、霜牙）、法杖 +2（翡翠法杖、太陽法杖）、書 5（入門書～寒霜法典）、拳 5（皮革纏手～泰坦之拳）、投擲 5（投擲斧～虛空星鏢）。
  - 數值依稀有度（`TIERS`）：主要能力（力量；法杖與書是魔力）普通 12／魔法 20／稀有 30／傳說 45／神話 65；稀有以上有自己的屬性攻擊（10／15／25）與暴擊；匕首、拳、投擲、弓另有速度。鑲嵌孔：魔法 1 個寶石孔，稀有以上 2 個寶石孔加 1 個卡片孔。全部帶 `weapon` 標籤，工坊的 +N 精煉（`plus`）都適用。
  - 圖示從素材庫複製到 `playable_assets/icons_7soul/`（29 張）。
- **中文**：29 個武器名與「書／拳／投擲」加進 `trial_zh_words.py`，zh-TW 表多 35 筆，`missing()` 仍為空。
- **順手修的**：狀態選單的裝備頁在英文下顯示 id（`w_titan_fists`、`a_warden_plate`、`f_normal`），因為 presentation 的裝備清單標籤預設是 id；現在標籤只是 id 時改用紀錄自己的名稱（`status_menu._word`）。中文本來就因 D60 的表而正確。
- 舊測試 `test_full_verification_weapons` 原本規定每把武器的圖都是 Lucifer 的 32×16，改成依圖的來源檢查（7Soul 是 34×34）。

**測試：** `tests/test_arsenal.py`（6 項）：九種類型各 ≥5 把且五個稀有度都有；新類型的攻擊帶自己的武器標籤、有選目標規則、武器給的就是它；數值與鑲嵌孔照稀有度；圖示與素材庫的檔案逐位元相同、CREDITS 與 THIRD_PARTY_ASSETS 都有；重複套用加 0、每個名稱都有中文；穿上普通與神話拳套後力量差 53（65－12）、`attack_fist` 打得到敵人。全套 3264 通過、1 略過；`run_campaign.py` 結束碼 0；ruff 乾淨。

**實機證據（`docs/audits/evidence/arsenal/`）：** `scripts/arsenal_live_check.py`（Cocoa、真的按鍵、`ASTERIA_MUTE=1`）PASS：給艾德里克星鏢、魔導書、拳套（一次只能拿一把武器，最後的拳套穿著，另兩把在背包），英文與中文各拍狀態選單裝備頁（`g1_*_equipment`）、戰鬥按「攻擊」（`g1_*_fight`）與出拳後（`g1_*_after_fist`）；選單上的名稱「Attack (fist)」／「攻擊（拳）」，按鍵真的呼叫到 `attack_fist`。編輯器 Database ▸ Game Data ▸ Equipment（`g1_editor_equipment_en.png`／`_zh.png`）：71 筆裝備，選中「Titan Fists」顯示 7Soul 圖示、稀有度 Mythic、技能「Attack (fist)」。

**限制（G1）：**
- 書的普通攻擊和既有法杖一樣以力量計算傷害，書與法杖給的魔力只影響法術。
- 7Soul 的圖是 34×34、Lucifer 的武器是 32×16，兩種風格在背包裡並存。
- 部位名稱在英文是作者寫的 id（weapon、armor）；中文由 D61 前的 `data.slot.*` 翻。
- 商店、工坊實際操作、run_campaign 的新事實在 G3。

**G2：防具、飾品、道具（2026-10-24）**

- **`trial_supplies.py`**（建置時接在 `trial_arsenal` 之後；可重複套用）新增 65 筆：
  - 防具 8 件（襯墊短衣～天界板甲：輕／重／布三種重量，普通到神話）與飾品 8 件（銅戒指～王家勳章）；稀有度決定防禦、魔防、抗性或飾品的加成（`TIERS`），稀有以上防具有卡片孔、飾品有寶石孔。防具 18 件、飾品 19 件。
  - 藥水 6（藥水、高級藥水、超級藥水、以太、高級以太、萬能藥）、狀態藥 7（解毒藥、眼藥、回聲草、燒傷藥膏、止血藥、鬧鐘、萬靈藥）：每個是戰鬥道具，有自己的技能（對一名隊友；狀態藥用 `apply_states` 加 `remove`）。
  - 投擲 6：投擲石、鐵球（物理，鐵球會暈眩）與雷電、旋風、神聖、黑暗炸彈（`damage.<元素>` 標籤，敵人的屬性弱點會讀；各帶一個狀態）。
  - 材料 8（狼毛、利牙、上等布料、煤炭、秘銀錠、金錠、蝙蝠翅膀、蠍鉗）。
  - 寶珠 7（火、冰、雷、風、土、光、闇）：鑲嵌物帶 `gem` 與 `orb` 標籤，鑲在寶石孔；給該屬性攻擊 15 與魔力 6，鑲進武器後攻擊帶上那個屬性。
  - 卡片 4（騎士、賢者、流浪者、學者），拿下來會毀掉，和怪物卡片一樣。
  - 圖示都是 7Soul（`icons_7soul/` 共 83 張）；CREDITS 那一列改寫成涵蓋武器、防具、飾品與道具。
- **順手修的**：會解除狀態的技能（Purify 等）說明原本寫「user gains Poison, Burn…」，因為說明產生器把被解除的狀態也算成獲得；`trial_stats` 的產生器改了，現有專案用 `fix_removal_words` 改寫成「removes …」，中文跟著變成「輔助：解除中毒、燃燒…」。`trial_zh_data.apply` 現在每次重算 `data.*`／`dlg.*` 的譯文（英文改了，中文跟著改），手寫的其他鍵照舊不動。
- 中文：54 個名稱與「restores MP」「all allies」加進詞彙表；zh-TW 多 103 筆，`missing()` 仍為空。

**G2 測試：** `tests/test_supplies.py`（5 項）：每筆紀錄都在 demo 且有圖、防具鑲嵌孔照稀有度、重複套用加 0；道具分類（藥水、狀態藥、投擲、材料、寶珠、卡片）；戰鬥中藥水把 HP 100 回到 600、解毒藥解掉中毒、萬靈藥解掉失明與沉默、雷電炸彈造成傷害並暈眩且帶 `damage.lightning`；冰之寶珠鑲進嗜血斧後冰屬性攻擊 +15、寶珠從背包扣掉；每個會解除狀態的技能說明都寫 removes、Purify 的中文正確。全套 3268 通過、1 略過、1 失敗：`test_skeleton_component` 的地圖繪製測試，失敗來自另一個 session 未提交的 `tile_scene_view.py`（地圖動畫格、跳躍影子），不是本批；`run_campaign.py` 結束碼 0。

**G2 實機證據（`docs/audits/evidence/arsenal/`）：** `scripts/supplies_live_check.py`（Cocoa、真的按鍵、靜音）PASS：背包道具頁捲到新道具（`g2_*_items`）、穿上秘銀鎧甲與獵人護符的裝備頁（`g2_*_equipment`）、戰鬥的道具選單（`g2_*_battle_items`：解毒藥、萬能藥、以太…與 7Soul 圖示）、按鍵丟出雷電炸彈（`g2_*_after_bomb`）；`results_g2.json`。編輯器 Database ▸ Game Data ▸ Items（`g2_editor_items_en.png`／`_zh.png`）：94 筆道具，火之寶珠帶圖示與鑲嵌物欄位。

**G2 限制：** 防具只有「防具」與「飾品」兩個部位（使用者選的）；材料目前只能買賣，還沒有用它們的配方；寶珠讓攻擊帶屬性靠的是屬性攻擊數值，不改技能本身的屬性標籤。

**G3：爐心鎮三間新商店、工坊精煉與鑲嵌、run_campaign 新事實（2026-10-24）**

- **引擎：商店可以賣裝備。** `ShopRuntime` 多了 `receive_equipment` 與 `equipment`：商品 id 是裝備時，買下的東西進裝備背包（`gain_equipment`），不佔道具背包的格子；沒給 `receive_equipment` 時行為和以前一樣。遊戲階段把 `gain_equipment` 與資料庫的裝備傳進去；資料驗證允許商品是裝備 id；商店畫面的名稱與「持有」會讀裝備背包。
- **引擎：商店清單會捲動。** 商品超過一頁時清單跟著游標捲，標題列右邊顯示「28/38」。原本只畫前 16 列，游標往下就看不到了。
- **引擎：工坊文字。** 精煉結果（成功／失敗／失敗但等級保住）走翻譯鍵 `workshop.outcome.*`；下一級費用的貨幣用翻譯後的名稱（原本寫 gold）；按鍵列的角色用名字（原本寫 hero_01）。
- **編輯器：** 遊戲系統 ▸ 商店的商品欄改名為「道具或裝備」，選單列出道具和裝備，兩者都顯示名稱與圖示（原本裝備只能手打 id，清單也只顯示 id）；`zh_TW.json` 加一筆。
- **`trial_shops.py`**（建置時接在 `trial_supplies` 之後；可重複套用）：
  - 布蘭武器店（武器匠布蘭）：G1 的 29 把武器。
  - 希爾德防具店（防具匠希爾德）：G2 的 8 件防具與 8 件飾品。
  - 瑟拉藥鋪（藥師瑟拉）：藥水、狀態藥、投擲、材料、7 顆寶珠、4 張卡片，共 38 項；可以四分之一價賣回。
  - 裝備依稀有度定價：普通 120、魔法 400、稀有 1200、傳說 3500、神話 9000。
  - 三位店主站在爐心鎮廣場北邊的路兩側，各用一個 Ninja Adventure 角色（CC0），先說一句話再開店。
- **demo 的中文表：** `trial_zh_data.apply` 也會補上中文表缺少的引擎翻譯鍵。原本中文表是建置時複製的，之後新增的引擎文字不會進來；這次補了 3 筆。屬性節點「STR (Strength)」原本翻成「力量（力量）」，改成「力量（STR）」，其他四個屬性也一樣。
- **run_campaign 新事實：**
  - 在王座之前到三間店：九種武器各買最便宜的一把、買襯墊短衣、買四樣藥鋪商品。
  - 把騎士之刃給米拉，鑲上火之寶珠（確認火屬性攻擊 +15），再精煉一次。精煉用自己的亂數，不影響之後的戰鬥。
  - 最後一個魔王之後再打一場巡邏：丟雷電炸彈、讓英雄中毒再用解毒藥解掉。
  - 這場原本放在守夜侍僧戰裡，但會改變之後的戰鬥亂數，害魔王戰少了破防（`boss_breaks`），所以移到最後。
  - 新的必要事實：weapon_kinds_bought 9、armour_bought 1、remedies_bought 4、orbs_socketed 1、new_weapon_refines 1、thrown_items 1、cures_used 1。
  - 連跑兩次都是 exit 0。

**G3 測試：** `tests/test_shops.py`（4 項）：
- 商店直接賣裝備時進裝備背包，道具照舊進道具背包，金幣扣對。
- 三間店的商品與價格正確，裝備不收購，九種武器都有，重複套用加 0。
- 每位店主在鎮上只有一位，事件會打開自己的店，店名有中文。
- 買下騎士之刃與火之寶珠、裝上、鑲嵌 +15 火屬性、精煉花掉材料。
- 全部測試：3291 通過、1 跳過、1 失敗。失敗的是 `test_built_in_text`，原因是另一個 session 未追蹤的 `runtime/creature_battle.py` 用了沒登記的 `creature.foe_weak`，不是這批的檔案。ruff check 全過；ruff format 只剩另一個 session 的 `formulas.py`、`battle_states.py`。

**G3 實機證據（`docs/audits/evidence/arsenal/`）：** `scripts/shops_live_check.py`（Cocoa、真的按鍵、靜音）PASS，英文和中文各跑一次：
- 按 E 跟三位店主說話（`g3_*_line`），按 Enter 進店，按方向鍵和 Enter 買騎士之刃、襯墊短衣、火之寶珠（`g3_*_shop`）。
- 藥鋪清單捲到第 28 項。
- 工坊按 S 鑲上火之寶珠（火屬性攻擊 0 → 15），按 R 精煉，畫面顯示「精煉：成功」（`g3_*_workshop`）。
- 結果在 `results_g3.json`。
- 編輯器截圖：`g3_editor_shops_en/zh.png`（瑟拉藥鋪）、`g3_editor_arms_en/zh.png`（布蘭武器店，裝備顯示名稱）。

**G3 限制：**
- 商店不收購裝備（賣出分頁只列道具）。
- 工坊的 S 鍵鑲背包裡第一顆合適的寶石。實機檢查先把其他寶石移開，所以鑲的是火之寶珠。
- 米拉換騎士之刃、精煉完再換回原武器，是腳本做的。
- 材料仍只能買賣，沒有用到它們的配方。

**狀態：** 已提交（2026-10-24，使用者要求；只含本批檔案與 hunk，demo JSON 是在 HEAD 的乾淨副本上套用 `trial_arsenal`、`trial_supplies`、`trial_shops`、`trial_zh_data` 後的版本）。

## D62 — 生物收集 RPG 的引擎功能：隊伍與戰鬥畫面、格子行走、地圖動畫、區域音樂與遇敵（2026-10-24）

**要求：** 使用者要用 Asteria 做生物收集 RPG（自己私人的寶可夢綠寶石復刻，以 pret/pokeemerald 為參考），同時能當範本給別人換素材。引擎只加通用功能，不寫死任何遊戲；寶可夢的圖、音樂與資料只在使用者私人的 `~/Documents/Vscode/AsteriaEmerald`（不進本 repo）。

**B1：生物隊伍與戰鬥（引擎）**
- Pet Rules（`rpg/pets.py`）：隊伍人數、同時上場數、倉庫、角色是否參戰、由生物決定勝負、換人是否花一回合、經驗分配與除數、升級回滿、招式上限、回復時補 PP、能力公式（`PetStatFormula`：基礎×倍率＋基因項，再乘性格基因）、基因範圍與基因組、招式用完時用的招式（掙扎）。物種有經驗曲線（三次式或表）、經驗值、捕獲率、正面與背面外觀。
- 捕獲（`rpg/capture.py`）有 rate 模式（捕獲率、道具與狀態加成）；遭遇成員可以是物種＋等級範圍＋預備（`EncounterMember.reserve`）。
- 戰鬥：預備成員（bench／send_in／standing），換人（Switch 指令），敵方生物選隨機可用招式，PP 用完改用掙扎。
- `runtime/creature_battle.py`：`battle.style: "creature"` 的戰鬥畫面（掌機式：雙方位置、血條框、訊息窗、指令與招式窗、隊伍與背包畫面、野生／訓練家／傳說的音樂、勝利音樂）。所有圖、字型、座標都在 manifest 的 `battle.creature_screen`，引擎不帶任何遊戲的圖。
- `graphics/bitmap_font.py`：點陣字型（JSON：格子大小、字寬、字元表），缺字時用系統字。

**B2：地圖與行走（引擎）**
- `runtime/grid_walk.py`：`field.movement: "grid"` 一格一格走；輕點只轉身、按住才走、按跑步鍵加速。
- 對話框可用遊戲自己的訊息窗圖（manifest `dialogue.window`：文字區、行高、點陣字型、顏色、打字速度、翻頁箭頭）。
- `field.test_hints: false` 收掉 Field Test 提示。
- 修正：對話開始後放開互動鍵的那一下沒被記到，下一次按鍵被當成「還按著」，所以講完話再按告示牌沒反應。現在事件執行中也會追蹤按鍵（`InteractionController.observe`）。

**B3：地圖下一批（引擎）**
- **地圖圖塊動畫**：tileset 的 tile 可有 `animation`（幀序）與 `frame_ms`；只重畫含動畫格的 chunk。
- **遮蓋格（cover）**：帶 `cover` 標籤的格不畫在圖層裡，只畫在站在那格的角色身上，動畫從踩進去開始播一次，之後停在最後一格（高草遮腳）。
- **格子角色** `GridMover2D`（`runtime/grid_actors.py`）：站著、四處看、四處走、只走上下或左右；各軸範圍（0 = 不限）、隨機停頓、講話時面向玩家。不走進牆、玩家、玩家要走去的格、別人站著或要走去的格；走路時同時佔兩格。玩家也不會走進它們的格。
- **跳台階**：格子帶 `ledge_<方向>` 標籤（前綴可用 `field.ledge_tag` 改）時，往那個方向走會跳過去落在下一格（那格要空），以步行速度、最高 `field.jump_height`（12）；`field.jump_shadow` 是跳起時留在地上的影子。
- **地圖區域**（`AreaRule`）新增：`music`（進入時的音樂；劇情事件指定的曲子優先）、`title`（進入時從上方滑下的地名牌，`field.area_name` 設定牌子圖、字型、顏色、滑動速度、停留秒數；同名不重複顯示，換地圖後重新顯示）、`encounters`（遭遇 id → 權重）、`encounter_chance`（每走完一格的機率）、`encounter_first_step`（從區外踏進來那一步的倍率）。有生物規則且由生物決定勝負時，隊伍沒有能戰鬥的生物就不會遇敵。編輯器的地圖區域表單有這幾欄（含中文）；參考檢查會抓不存在的遭遇 id。
- 修正：換場景後新地圖還沒綁定前，舊場景的區域規則會用新位置判斷一次（綠寶石實機在研究所裡跳出「OLDALE TOWN」）。現在區域規則只在綁定它的場景執行。

**私人的綠寶石專案（不在本 repo）：** 用上面這些功能，從使用者 clone 的 pokeemerald 讀資料（只讀不執行）做出未白鎮、101 號道路、小田卷鎮與 12 個室內場景：地圖、圖塊、花朵與電視動畫、NPC 與他們的走法、告示牌、門、台階、高草、各地圖音樂（自寫的 m4a 音源模擬器從樂譜渲染）、地名牌、101 號道路的野生寶可夢（物種、等級、權重、機率照原作），以及捕獲率、能力、性格、經驗表、招式、屬性相剋。

**測試：** `tests/test_grid_walk.py`（7）、`tests/test_grid_actors.py`（6）、`tests/test_tile_animation.py`（3）、`tests/test_map_rules.py` 新增 4、`tests/test_map_rules_session.py` 新增 3、`tests/test_interaction_foundation.py` 新增 1、`tests/test_creature_party.py`（16）。

**實機證據：** 本 repo 的 `scripts/creature_battle_live_check.py`、`scripts/creature_party_live_check.py`；綠寶石場景的真實視窗檢查在私人專案（`tools/field_live_check.py`，Cocoa、靜音、18 步全部通過），截圖不進 repo。

**限制：**
- 招式傷害還不是原作公式（引擎的數值公式是線性的）：暫用「2 + 0.08×威力 ＋ 每多 1 點攻擊比防禦 0.01×威力」；逃跑機率也是暫代。下一批戰鬥規則再做。
- 能力變化招式（叫聲、搖尾巴…）以「改一次能力值」近似，沒有段數上限；戰鬥訊息還沒有「攻擊下降了」之類的句子。
- 高草的晃動只在角色踩進格子時播一次；原作的開門動畫、劇情、標題畫面在之後的批次。

**狀態：** 已提交（be5d3c01，2026-10-25）。

## D63 — 戰鬥規則可寫算式；狀態、命中、逃跑、捕捉、換人與進場細節（2026-10-24）

**要求：** 使用者要綠寶石的戰鬥規則跟原作一樣：傷害公式、能力段數、逃跑機率、異常狀態，以及收服、換寶可夢、位置的細節。引擎只加通用功能；寶可夢的數字與文字只在私人專案的資料裡。

**引擎（通用）：**
- **算式**（`gameplay/expressions.py`）：安全的算式語言，用 `ast` 白名單（數字、四則、比較、`and/or/not`、`x if c else y`、指定的函式）。主體可讀能力值、資源（`current`／`maximum`／`ratio`）、`has(標籤或狀態)`；函式有 `floor ceil round min max abs sqrt clamp random randint stage(n, base) choose`。不准屬性存取（主體以外）、匯入、索引、lambda；超大次方會擋。
- 能寫算式的地方（都只在設定時寫進資料）：
  - `ValueFormula.expression`：取代線性項，例如傷害公式；骰子用戰鬥自己的。
  - `OutcomeCheckDefinition.chance_expression`：命中率等判定。
  - `BattleEscapeRule.chance_expression`：可讀 `source`、`opponent`、`attempts`（之前試過幾次）。
  - `BattleSessionRules.initiative_expression`：行動順序。
  - `BattleSessionRules.final_damage_expression`：每一擊在互動規則（屬性相剋）之後的最後一步，例如亂數 85～100%、取整數、至少 1；只作用在倒下用的資源上。
- `BattleSessionRules.battle_counters`：每個戰鬥者在戰鬥中帶的計數器（名稱 → 最小、最大、起始），例如能力段數 −6～+6；招式用一般的 resource_delta 改它，算式讀它。被收回來時（換人）回到起始值。
- `BattleSessionRules.vary_seed`：每場戰鬥用自己的亂數（依存檔已開始幾場），不再每場都是同一串。
- 戰鬥狀態政策新增：
  - `prevent_chance`：每回合有機率不能行動（麻痺），擲一次、整回合有效。
  - `remove_chance`：每回合有機率先自然解除（解凍）。
  - `duration_range`：隨機回合數（睡眠）。
  - `exclusive_group`：同群組一次一個（主要異常）。
  - 套用的結果多回報 `reason`（already／exclusive／immune）。
  - 週期效果造成的變化、到期、機率解除都會發出 hook，對戰紀錄寫成 `state_tick`／`state_expired`／`state_removed`。
- 技能的 `apply_states` 每筆可有 `chance`（招式自己的機率，如 30% 中毒）和 `unless_outcome`（判定結果帶這些標籤時不套用，例如沒打中）。
- 捕捉規則 `shake_checks`：N 次判定，每次機率為整體機率的 N 次方根；整體機率不變，通過幾次就是晃幾下（記在 capture 紀錄）。
- 敵方生物的招式改走和我方一樣的每擊流程，命中、會心判定都會擲。
- 戰鬥開始一律由畫面處理（不論從場地或事件開始）。

**戰鬥畫面（`runtime/creature_battle.py`）：**
- 開場：敵方（或訓練家）從左滑入、玩家背影從右滑入；訓練家退場後丟球；生物從球裡長大出來；資訊框各自從邊緣滑入。
- 換人台詞依對手血量（原作 hpthresholds）：「Go!／Do it!／Go for it／Your foe's weak!」，收回時「that's enough／come back／OK!／good!」。
- 訓練家要派下一隻前，問「要更換嗎？」（是：先換、不花回合）；野生戰我方倒下時問「要派下一隻嗎？」（否：嘗試逃跑）。
- 隊伍畫面依「這場戰鬥的順序」排（場上的在第一格，換人互換位置；戰後原本的隊伍順序不變）。
- 訊息：
  - 沒打中、擊中要害。
  - 屬性效果：只算 id 以 `effectiveness_rules` 開頭的規則，會心的 ×2 不會被當成「效果絕佳」。
  - 能力段數的升降與「無法再提高／降低」。
  - 異常狀態的每個時刻：中了、已經是、每回合傷害、不能動、醒來、解凍，台詞由 `state_messages` 提供。
  - 「但是失敗了！」。
- 資訊框的異常圖示畫在 HP 標籤的位置；`player_name` 是遊戲還沒有玩家名字時用的名字。

**私人的綠寶石專案：** 以上功能讓 `tools/build_battle.py` 寫出原作規則：
- 傷害照 pokemon.c CalculateBaseDamage 與 damagecalc 的順序：
  - 依序算攻擊×威力×(2×等級/5+2)／防禦／50，每一步取整數。
  - 灼傷減半，再加 2。
  - 會心 ×2：攻擊方被降的段數、防守方被提高的段數都不算。
  - 本系 ×1.5。
  - 接著屬性相剋，最後亂數 85～100%，至少 1。
- 段數照 (2+n)/2 與 2/(2−n)。
- 命中照每個招式的命中率乘上 3 為底的命中／閃避段數。
- 會心率 1/16。
- 逃跑照 battle_util.c TryRunFromBattle：速度不比對手慢必逃得掉；否則為 (速度×128/對手速度 + 30×次數) mod 256，再除以 256。
- 行動順序：速度 × 速度段數，麻痺時 ×1/4。
- 五種主要異常：
  - 中毒、灼傷：每回合結束扣 1/8。
  - 麻痺：1/4 機率不能動。
  - 睡眠：2～5 回合。
  - 冰凍：每回合 1/5 機率解凍。
  - 同時只能有一種；毒、鋼系不會中毒，火系不會灼傷，冰系不會冰凍。
- 捕捉用原作的值：(3×最大HP − 2×目前HP)×捕捉率×球的倍率／(3×最大HP)，睡眠、冰凍 ×2，中毒、灼傷、麻痺 ×1.5，再分成 4 次晃動判定。

**測試：**
- `tests/test_battle_expressions.py`（12 項）：算式、危險算式被擋、值算式、命中算式、逃跑次數、計數器、行動順序、最終傷害、每場不同亂數。
- `tests/test_battle_state_options.py`（7 項）：中毒每回合 1/8、睡眠 2～5 回合、麻痺約 1/4、冰凍平均 5 回合解凍、互斥群組、招式狀態機率與資料、捕捉晃動。
- `tests/test_creature_party.py` 新增 2 項：換人歸零計數器、效果判斷只算屬性規則。
- 全套 3313 通過、1 略過；ruff 乾淨。

**實機證據：**
- 私人專案 `tools/battle_live_check.py`：Cocoa、真的按鍵、靜音，25 步、12 項檢查全部通過；截圖在私人的 `evidence/battle_b4/`。
- `scripts/creature_battle_live_check.py`（本 repo 的 demo）31 步通過：強制換人改成選第一隻還能戰鬥的，因為戰鬥順序把倒下的放在第一格。
- 綠寶石的場地檢查（18 步）也重跑通過。

**限制：**
- 招式的先制度（電光一閃先出手）還沒做：現在是玩家先選、照速度輪流，敵方在自己的回合才選招。
- 吸取、多段、會心等級提升、天氣等特殊招式效果之後再做；目前只會造成傷害，或沒有效果。
- 異常狀態在測試裡是用引擎的狀態 API 加上去的；初期的招式（毒針 30%）在實戰裡也會照機率套上。
- 訓練家是測試用的；原作的訓練家、視線、獎金在訓練家批次。

**狀態：** 已提交（be5d3c01，2026-10-25）。

## D64 — 訓練家：視線、挑戰、獎金；招式先制度與特殊招式（2026-10-24）

**要求：** 使用者要原作的訓練家資料、視線發現玩家、獎金，並補上招式先制度與吸取等特殊招式。引擎只加通用功能；訓練家、台詞、數字只在私人專案的資料裡。

**引擎（通用）：**
- **格子角色的視線**（`runtime/grid_actors.py` 的 `SightTrigger2D`）：
  - 角色朝向前方 `range` 格的直線上若有玩家，而且中間沒有牆或其他人，就會注意到。
  - 注意到時頭上出現 `emote`（`field.emotes` 的圖），播放 `music`（暫時性），走到玩家旁邊，雙方面對面，再開始它自己的互動事件。
  - `done_switch` 開著時不再注意（被打敗了）。
  - `line_of_sight()` 是共用的判斷。
  - 看到期間玩家不能動（`event_busy`）。
  - 隊伍沒有能戰鬥的生物時不會被注意。
- `GridMover2D.look_facings`：四處看的角色只在指定的方向之間轉，例如「下、右」。
- **暫時音樂**：`PLAY_BGM` 可帶 `temporary`，下一場戰鬥開始時就結束；戰後回到地圖自己的音樂。
- **招式**（`AbilityDefinition`）新增：
  - `priority`：先制度。
  - `drain`／`recoil`：造成傷害的一部分回復給自己，或自己承受，至少 1。
  - `hit_counts`：一次使用打幾下，依權重擲。
  - 每擊的 `first_checks`：只在第一下擲的判定；沒中的話整招都沒中。
- **大家先選再出手**：`plan_round()` 讓場上的敵方生物在回合開始就選好招，之後照先制度、再照速度排。排序由排程器的 `set_priorities()` 處理；敵方輪到時用選好的招。
- 戰鬥狀態政策 `battle_only`：只在這場戰鬥有效（畏縮、守住、集中…），戰後不會留在生物身上；戰鬥計數器（能力段數）也不寫回存檔。
- **戰鬥畫面**：
  - 吸取、反作用、打了幾下的台詞。
  - `outcome_lines`：某個判定結果標籤對應的台詞，例如「守住了」。
  - `fail_tag`：做不到的招式顯示「但是失敗了！」。
  - 能力段數的台詞也包含招式附帶的變化。
  - 狀態台詞可設成不說話（空字串）。
  - 訓練家的 `defeat_text`：勝利後訓練家回到畫面說完，再發獎金。

**私人的綠寶石專案：**
- 地圖加上 102 號道路與橙華市，共 20 個場景；橙華市的音樂、道館音樂都從樂譜渲染。
- 訓練家（`trainers.h`、`trainer_parties.h`、`gTrainerMoneyTable`）讀出：
  - 職業名、名字、圖片。
  - 遇見音樂、戰鬥音樂與勝利音樂，依職業，照 `GetBattleBGM`。
  - 隊伍：等級、IV 換算成 0～31、自訂招式。
  - 獎金：4 × 最後一隻的等級 × 職業倍率，例如 YOUNGSTER CALVIN 是 ¥80。
- 地圖腳本的 `trainerbattle_single` 給挑戰、落敗與之後的台詞。視線格數照地圖資料。
- 102 號道路有 4 位訓練家，橙華道館有 7 位。
- 招式：
  - 先制度直接照資料，例如電光一閃 +1、守住 +3。
  - 吸取類 1/2、撞擊類 1/4 反作用、捨身衝撞 1/3。
  - 連續攻擊 2～5 下（3:3:1:1），二連踢 2 下。
  - 會心等級：易出會心 +1、集中 +2，機率 1/16、1/8、1/4、1/3、1/2。
  - 畏縮 30%。
  - 附帶能力變化，例如泥巴射擊 100% 降命中、咬碎 20% 降特防。
  - 守住／看穿、睡覺（完全回復並睡 2 回合）、回復一半。
  - 抓狂／起死回生依 HP 的威力表、蠻幹。
  - 固定傷害：音爆 20、龍之怒 40、等級傷害、終結門牙，保留屬性免疫，不受屬性倍率與亂數影響。
  - 大爆炸：對方防禦減半、自己倒下。
- 範圍內 24 個招式效果還沒做：
  - 混亂、綁住、偷東西等仍會造成傷害。
  - 其他變化類招式會顯示「但是失敗了！」。

**測試：**
- `tests/test_moves_and_sight.py`（9 項）：
  - 新招式欄位、先制度排序、吸取與反作用、連續攻擊的次數與台詞。
  - 敵方回合開始先選招、只限這場的狀態不留下。
  - 視線判斷、訓練家注意 → 走過來 → 開始事件 → 被打敗後不再注意。
  - 只在指定方向之間轉身。
- 全套 3329 通過、1 略過；ruff 乾淨。

**實機證據：** 私人專案 `tools/trainer_live_check.py`（Cocoa、靜音）16 步、14 項檢查全部通過：
- 走進 CALVIN 的視線、頭上出現「!」、遇見音樂、他走過來、挑戰台詞、戰鬥音樂。
- 吸取的體力被吸取台詞、勝利訊息、CALVIN 回到畫面說落敗台詞、獎金 ¥80、勝利音樂。
- 回到道路音樂、之後的台詞、不再被注意。
- 守住、反作用、打 2 下。
- 速度被設成 1 的木守宮用電光一閃仍先出手。

**限制：**
- 訓練家的 AI 還是隨機選招（原作有 AI 旗標）；訓練家的道具（傷藥）、雙打、再戰還沒做。
- 輸給訓練家的流程（扣錢、回寶可夢中心）在劇情批次。
- 混亂、綁住、天氣、看穿、挑撥等還沒做；守住連用成功率不會下降。

**狀態：** 已提交（be5d3c01，2026-10-25）。

## D65 — Full Verification 主角改名為 Roger（2026-10-24）

**要求：** 使用者要把 Full Verification 主角的名字改成 Roger。

**做了什麼：**
- 主角 `hero_01` 的名字從 Aldric 改成 Roger，中文從「艾德里克」改成「羅傑」（和米拉、薇絲珀、凱爾一樣用音譯）。
- 主角的家從 Aldric's House 改成 Roger's House，中文「羅傑的家」。
- 對話和文字裡的名字一起改：老師父的台詞、營火的台詞、英雄之廳的石碑（中文改成「這裡刻著羅傑的名字」）。
- demo 的建置腳本（`trial_*.py`、`run_campaign.py`、`build_project.py` 等）的名字與註解都改了，重建時也是 Roger。
- `project.asteria.json` 直接替換文字（英文 12 處、中文 4 處），沒有重建；`trial_zh_data.apply` 確認中文表一致，沒有缺字。
- id 不變（仍是 `hero_01`），存檔、事件、測試用的 id 都不受影響。
- demo 的測試與實機檢查腳本跟著改名；引擎測試裡拿 Aldric 當範例資料的三處（`test_built_in_text`、`test_editor_startup`、`test_editor_i18n`）沒有讀 demo，維持原樣。
- `FULL_VERIFICATION_COVERAGE.md` 改成 Roger，開頭註明舊名。之前決策紀錄裡寫 Aldric 的段落是歷史，不改。

**測試：** run_campaign exit 0。全部測試 3327 通過、1 跳過、1 失敗：中文石碑那句在 JSON 裡被替換成「刻著 Roger 的名字」，和建置腳本的「刻著羅傑的名字」不同；改正後相關測試 50 項全過。

**實機證據（`docs/audits/evidence/roger_rename/`）：** `scripts/data_translation_live_check.py`（Cocoa、真的按鍵、靜音）PASS：英文畫面顯示 Roger，中文畫面顯示羅傑（對話、狀態選單、商店、任務、戰鬥、勝利）。

**狀態：** 已提交（2026-10-24，使用者要求；D65、D67、D68 一起提交，只含這三批的檔案與 hunk，其他工作階段的生物戰鬥與劇情改動沒有包含）。


## D66 — 劇情：開場、救博士、初始寶可夢、媽媽與家、輸了回去、道館條件（2026-10-24）

**要求：** 使用者要做劇情批次：開場、博士救援、拿到初始寶可夢、媽媽與家、輸給訓練家回寶可夢中心，以及道館的進入條件。引擎只加通用功能；劇本、台詞、地點只在私人專案的資料裡。

**引擎（通用）：**
- **事件**：
  - `WAIT` 可帶 `until`（一個條件），條件成立才繼續。
  - `EXIT`：整個事件結束，包含呼叫它的程式；`runner.stop()` 也會清掉呼叫堆疊。
  - `SET_VARIABLE` 可帶 `from_variable`：複製另一個變數的值（編輯器輸入 `@名稱`）。
  - `CHOICE` 可帶 `box_at`：遊戲自己的選項框放在哪裡。
- **新的世界指令**：
  - `GRID_ROUTE(entity, steps)`：格子角色照路線走（走、快走、原地踏步、轉向、跳、等待、驚嘆號、隱藏、顯示、`face_player`）。結束時開關 `route.<名字或 id>.done`、`route.all.done` 會打開，事件可以 `WAIT until` 它。
  - `SET_POSITION(entity, x, y, facing, permanent)`：放到某處；`permanent` 會記住，之後回到這個場景時還在那裡。
  - `SHOW_ENTITY(entity, shown)`：有 `SwitchVisibility2D` 的就切它的開關，其他的到換場景為止。
  - `SET_MOVEMENT(entity, behaviour, facing)`：改格子角色的走法。
  - `GIVE_PET`、`SET_LOOK`、`SET_RESPAWN(scene_id, x, y, facing)`、`RESTORE_BGM`（回到區域自己的音樂）。
  - `entity` 可以寫 `self`（觸發這個事件的人）或 `var:<變數>`（變數裡記的人）。
- **新元件**：`SwitchVisibility2D`（開關打開時不見，關掉又出現）；`LookByVariable2D`（外觀跟著變數，例如對手或主角的性別）。
- **區域規則**：`AreaRule.autorun`：玩家在區域裡、沒有其他事件時，第一個條件成立的程式會執行（`when: "enter"` 則是進入時執行一次）。進入時事件忙碌的話，`on_enter` 會排隊，等事件結束再跑。編輯器的區域表單有這個表格。
- **事件可讀的值**：`player.facing`（事件開始時玩家的朝向）、開關 `battle.running`（戰鬥進行中）。
- **輸掉戰鬥**：`BattleSessionRules` 新增 `defeat`（`game_over` 或 `respawn`）、`defeat_currency`、`defeat_currency_loss`、`defeat_event`。`respawn` 會補滿隊伍、扣錢、送回 `SET_RESPAWN` 記的地方、結束帶來這場戰鬥的事件，再執行 `defeat_event`。遭遇標籤 `defeat_continues`：輸了劇情照樣進行。
- **畫面**：
  - 選項可用方向鍵移動游標、確定鍵選擇（數字鍵照舊）。
  - 套用遊戲自己的視窗時，選項框用 `dialogue.choice_frame` 畫，有指標；`cancel_picks_last` 讓取消鍵選最後一個（YES／NO 的 NO）。
  - `field.notices: false` 可關掉「+1 道具」的浮動提示。
  - 戰鬥畫面的 `player_name`、`player_back` 可用 `\V[...]`；`encounters.<id>.no_running_text` 是不能逃跑時的台詞；訓練家落敗台詞會展開 `\V[...]`。
- **修正**：
  - 劇情移動或轉動玩家後，玩家原本開始的那一步會被取消（否則事件後玩家會自己一直走）。
  - 被開關藏起來的人，開關關掉後會再出現（之前一旦藏起來就不會回來）。

**私人的綠寶石專案：**
- `tools/emerald_scripts.py`：把 pokeemerald 的事件腳本翻成引擎的事件程式，共 879 個。
  - 對照：`goto`／`call`／`end`／`return`、條件跳轉、`switch`／`case`、旗標與變數、對話、YES／NO、移動、物件出現與消失、位置、傳送、重生點、音樂、給寶可夢與道具、訓練家戰鬥。
  - 特殊程式：`HealPlayerParty`、`ChooseStarter`（三選一、給寶可夢、救援戰）、`GetRivalSonDaughterString`。
  - 每張地圖的 `ON_TRANSITION`、`ON_WARP_INTO`、`ON_FRAME` 都接上區域規則。
- 開場：博士的演講（`birch_speech.inc` 的台詞、原作背景、博士、蓮葉童子、男孩／女孩圖片、ROUTE122 音樂）、選男孩或女孩、卡車行駛。名字輸入還沒做，先用 BRENDAN／MAY。
- 主角與對手的外觀跟著性別；對話裡的名字用 `\V[player.name]`、`\V[rival.name]`。
- 地圖加上 103 號道路；卡車內部、所有物件（包含劇情才出現的人、寶可夢球、紙箱、卡車）。
- 輸掉戰鬥：錢減半、隊伍補滿、回到最後的重生點（家裡房間，或最後去過的寶可夢中心門口，照 `heal_locations.json`），之後執行原作的 `EventScript_WhiteOut`。
- 救博士的戰鬥輸了劇情照樣進行（原作 `CB2_EndFirstBattle`），而且不能逃跑（「Don't leave me like this!」）。
- 道館條件：照原作腳本，諾曼依 `VAR_PETALBURG_GYM_STATE` 回應（第一次來時開始滿充的事件、徽章不夠時要你先去收集、4 個徽章時對戰）。

**測試：**
- `tests/test_story_events.py`（11 項）：路線、等待路線走完、`EXIT`、區域自動執行與排隊、出現／外觀／記住的位置、輸掉的規則、送回重生點、新指令、`self`、事件開始時的朝向、`battle.running`、進入時執行、藏起來的人回來。
- 全套第一次 3333 通過、1 略過（加入最後一項前）。最後一次全套有 12 項失敗，都在另一個工作階段正在改、還沒完成的選單畫布（`playtest/text_draw.py`、`menu_canvas.py`、`menu_preview.py`，錯誤是 `PlayableTestRuntime` 沒有 `project`、找不到 `playable_test_manifest.json`）與 Full Verification 的商店；這批相關的 94 項測試全過；ruff 乾淨。

**實機證據：** 私人專案 `tools/story_live_check.py`（Cocoa、真的按鍵、靜音）31 張截圖、40 項檢查全部通過：
- 開場：博士、蓮葉童子、男孩／女孩選項框與游標、「You're BRENDAN…」、卡車。
- 媽媽在卡車旁、家裡、二樓的時鐘、電視的道館報導、隔壁的媽媽、在房間遇見 MAY。
- 雙胞胎、「H-help me!」與求救音樂、博士的包包、選初始寶可夢、救援戰、博士道謝、研究所給寶可夢、取名的 YES／NO。
- 103 號道路的 MAY、對手戰的音樂、戰後的台詞。
- 輸掉：「whited out!」、回到家裡房間、錢 3000 → 1500、隊伍補滿；去過橙華寶可夢中心後輸掉，回到它門口。
- 道館：諾曼第一次來的台詞、滿充出現、沒有徽章時的台詞、4 個徽章時開始對戰。
- 為了縮短，長距離移動是直接放到目的地前（全部列在 `injected`）；救援戰與對手戰把對方體力設成 1。
- 之前的實機檢查改成從「開場之後」開始（共用 `tools/story_state.py`），重跑都通過：地圖 11/11、訓練家 14/14、戰鬥 12/12；引擎的 Full Verification 生物戰鬥檢查 31 步通過。

**限制：**
- 還沒做：名字輸入、選初始寶可夢的專用畫面（用選項框代替）、時鐘設定畫面、開門動畫與 `setmetatile`（橙華道館裡的門因此還不會打開）、音效與獲得道具的短曲、第一場戰鬥不會會心一擊的規則。
- 滿充的抓寶教學戰（`StartWallyTutorialBattle`）、`multichoice` 選單、其他 `special`／`specialvar`（多數先當 0）。
- 跑腿任務與地圖上撿道具的球（`finditem`）還沒接。
- 執行這批時用 `ruff format` 整理整個 `src/asteria`，順便把另一個工作階段正在改的 `playtest/menus_input.py` 一行換行（只是排版）。
- `scripts/creature_party_live_check.py`（生物隊伍批次寫的、之前從沒完整跑過）查清楚了，不是 D63/D64 的出手順序造成的：2026-10-23（D63 之前）留下的截圖在同一步就一樣失敗。原因都在檢查腳本：
  - 這個 demo 的生物沒有魔防，一發射擊固定打 72，狼只有 24 HP，換上場就一定倒下；腳本接著把倒下的狼設成 1 HP，等於把它救起來，提示就關了。改成只在狼還站著時才設。
  - 換回 Fang 後對方先出手，同樣一發打倒；給 Fang 500 HP 撐過那一回合（注入值，寫在腳本註解）。
  - 學招提示要等勝利訊息都關掉才出現；暫停選單的「寵物」改用 id 找（選單變長了）。
  - `press()` 只送按下、不送放開，所有按鍵一直被當成按住，選單收不到新的按鍵。
  - 修好後 Cocoa 實機 14 步全部通過（`docs/audits/evidence/creature_party/`）：換寵物、倒下後的提示、送出、收服、勝利、學新招、寵物畫面、「隊伍已滿」、補血與寄放。

**狀態：** 已提交（be5d3c01，2026-10-25）。


## D67 — 選單畫面：中文不再出現 id 與英文（U1）；選單版面系統與編輯器「版面」頁（U2a–U2c）（2026-10-24）

**要求：** 使用者核准 `UI_PLAN_2026-10-24.md`，要求「一次做多一點，直接做到 U3」。計畫的建議全部採用：新增頭、手、腳、副手部位；箱子素材縮小複製；貨幣用星石；拉丁字用 PixelRpgFont、中文用 Noto Sans TC；養成驗收選單只在開發者選項下出現；順序 U1 → U2a → U2b → U2c → U3。

**U1 做了什麼：**
- 數值、部位、標籤名稱都經過翻譯：`stat_name`、`slot_name`（找不到時用畫面設定的標籤，再不然把 id 轉成字）、`game.tag_name`（`data.tag.<標籤>.name`）。
- 背包說明框、套裝效果、技能樹標題列、寵物數值、養成選單都改用這些名稱。
- 任務目標顯示目標的名稱：`quests.objective.defeat`／`item`。
- `SocketDefinition.label` 是選填的孔名稱，有設定時才寫入存檔；沒有名稱時顯示「孔 N」。
- 翻譯頁新增「Data: tags shown in menus」組。
- 防止再發生：`trial_ui_tour.py` 打開每個畫面；`tests/test_full_verification_ui_words.py` 在中文下畫每個畫面，只要出現資料庫 id 或該翻譯的英文詞就失敗。

**U2a 引擎：**
- `presentation/menu_layout.py`：`MenuLayout`、`MenuElement`、`MenuSlotPlace`、`MenuTheme`。演出庫的類別是 `menu_layout` 與 `menu_theme`。
  - 每個畫面有固定的元件 id、欄位與說明（`screen_spec`）。
  - 元件可以搬移、縮放、改色、換九宮格或圖片、隱藏，也可以加上作者自己的元件（`extra.*`）。
  - 錨點從畫面的角或邊量起，另有圖層與背景（顏色、圖片、調暗）。
- `runtime/menu_canvas.py`：每個畫面都經由它畫，並把元件的位置記下來給編輯器用。
- 主題：拉丁字型、中日韓字型、字級倍率、文字顏色、游標圖、九宮格，以及開啟、移動、確定、取消、購買、失敗的音效；版面也可以指定音樂。
- 沒有版面時畫法和以前一樣：測試逐像素比對。
- `runtime/menu_preview.py`：`MenuPreview` 用遊戲真正的繪製程式和範例資料，在畫面外畫出任何一個畫面；`open_menu_screen` 用遊戲自己的方式打開畫面。

**U2b 編輯器：** 演出 ▸ 選單畫面分成「版面」與「選單資料」兩個子頁（`editor/menu_layout_widget.py`、`menu_layout_authoring.py`）。
- 左邊是畫面清單，有自訂版面的畫面前面加 ●。
- 中間是畫布：遊戲畫出來的畫面加上元件外框，可拖曳移動、拖曳右下角縮放，對齊 4 px 格線。
- 右邊是元件屬性：錨點、位置、大小、顯示、圖層、九宮格（四條線與預覽）、圖片（選檔會複製到專案 `ui/`，也可以從素材庫挑）、填滿方式、顏色、字型、字級、綁定欄位；紙娃娃還有部位表。
- 工具列：新增元件、移除、重設畫面、從別的畫面複製、背景、選單主題、在遊戲中開啟（`ASTERIA_OPEN_MENU`）、預覽語言。
- 每次修改都可以用 Ctrl+Z 復原，所有新字都有中文。
- 預覽只在這一頁顯示時才畫，所以打開專案不會先建立遊戲執行環境。

**U2c：** 標題、暫停、設定、存讀檔、遊戲結束、狀態四頁、背包、技能樹、商店、製作、任務、寵物、成就、圖鑑、訊息紀錄、音樂室、製作人員、技能欄、穿裝提示、地圖提示列，全部改成依版面繪製。

**其他：**
- `GameSettings.developer_menu`（設定 ▸ 開發者選單，預設關閉）：C 鍵打開養成驗收選單需要開啟它。
- 暫停選單在專案有裝備欄時多「裝備」，有精煉、鑲嵌或成長規則時多「強化」。

**像素比對（U3 之前的基準，52 張）：** 只有以下幾張不同：
- en/zh 的暫停與設定：多了新選項，預期中。
- 工坊：已移除，預期中。
- zh_backlog：說話者名字現在顯示中文（守衛瑟莎莉／羅傑），是改善。

**狀態：** 已提交（2026-10-24，使用者要求；D65、D67、D68 一起提交，只含這三批的檔案與 hunk，其他工作階段的生物戰鬥與劇情改動沒有包含）。


## D68 — 裝備紙娃娃與強化畫面，取代工坊（U3）（2026-10-24）

**做了什麼：**
- `runtime/equipment_screen.py`（`EquipmentScreen`）：
  - 紙娃娃畫出成員所有部位，一個部位能穿幾件就有幾格（例如兩把武器、兩個飾品）。
  - 選一格後只列出能穿在那裡的裝備（依 `equipment.slot` 或部位的標籤），不能穿的灰掉並寫出原因。
  - 說明框顯示和身上那件的比較、耐久、孔數、套裝效果；數值表顯示穿上後的變化（→ 後的值）。
  - Enter 穿上、X 卸下、Q／E 換成員。
  - 版面沒有安排位置的部位，排在紙娃娃下面一列。
  - 新的 `game.wear_from_bag(actor, instance, slot, index)`：換掉第幾件、填空格，失敗時還原。
- `runtime/enhance_screen.py`（`EnhanceScreen`），四頁：
  - 精煉：材料（已有／需要，不足標紅）、金幣、成功率、失敗的後果、保護道具（P 開關），並預覽 +1 後的數值。
  - 鑲嵌：先選裝備，再選孔（顯示接受哪些標籤），再從背包挑合適的寶石或寶珠；鑲上前先看數值變化；X 取下時寫出會不會毀掉。
  - 卡片：同樣的流程，只列卡片孔與卡片。
  - 成長：裝備的計數與各階段；可以解鎖時按 Enter。
  - 這一頁用不到的裝備畫成灰色；游標一開始就停在第一件可用的裝備上。
- 舊的工坊（R／S／X／A 熱鍵）移除。養成選單的 8 鍵改開強化畫面。屬性點照舊在技能樹畫面分配。
- 暫停選單的「裝備」「強化」、選單主題的音效（開啟、移動、確定、取消；商店的購買與失敗）、游標圖。
- 文字：新增 9 個 `equipment.*` 鍵、44 個 `enhance.*` 鍵，以及 `pause.equipment`、`pause.enhance`、`settings.developer_menu`；刪掉工坊不再用的 10 個鍵。`BUILT_IN_TEXT_KEYS.md` 已重新產生。

**Demo（`trial_doll.py`）：**
- 每個主角多了頭、腿、腳三個部位（容量 1）。
- 新增 14 件裝備：頭 5、腿 5、腳 4，五個稀有度；稀有以上有一個寶石孔。防具店有賣。
- 裝備畫面用 Lucifer UI 的 `InventoryEmptyFields.png` 當紙娃娃，9 個格子。強化畫面用 Lucifer 的石頭面板。

**和計畫不同的地方（我自己決定的）：**
- **腿取代手**：Lucifer 的紙娃娃圖畫的是腿，沒有手，所以 demo 用頭、腿、腳。引擎的部位仍由作者自由定義。
- **副手格**：Roger 原本就有容量 2 的武器部位，所以紙娃娃上的副手格顯示第二把武器，沒有另外新增副手部位。
- **圖示**：新裝備用 Lucifer Equipment 的圖示，不用 7Soul，因為它們和紙娃娃圖是同一套。

**測試：**
- `tests/test_full_verification_workshop.py` 改寫成 3 項：紙娃娃穿上與卸下、強化四頁、開發者選項。
- `tests/test_menu_layout.py`（9 項）、`test_full_verification_ui_words.py` 涵蓋新畫面。
- 舊測試跟著調整：暫停選單照專案實際的選項移動、防具店清單、演出類別、沒有專案的測試用執行環境。
- 全套 3345 通過、1 略過；之後編輯器排版的修改，相關的 43 項重跑通過；ruff 乾淨。

**實機證據：**
- `docs/audits/evidence/ui_u3/`：`scripts/ui_tour_live_check.py`（Cocoa、靜音）中英文各 33 個畫面，共 66 張，沒有錯誤；包含 `equipment`、`equipment_list`、`enhance_refine`／`sockets`／`cards`／`growth`。
- 編輯器（Cocoa）：版面頁的裝備、強化、商店，中英文各一張；另有選單資料子頁。
- 截圖時發現並修好的編輯器問題：畫面清單太窄、名稱沒翻譯，自訂畫面的 ● 吃掉一個字，X／Y／寬／高四格擠在一列看不到數字，狀態列被通用句型先翻了一半。

**看到的問題後來都修好了：**
- 精煉頁中間欄原本是空的：現在列出精煉等級表，每一級的成功率與費用，已經達到的級數是綠色（`enhance.levels`、`enhance.level_row`）。
- 英文的 → 原本顯示成 ->：拉丁字型缺字時，那幾個字改用有這個字的字型畫（選單主題的中日韓字型，再不然是系統字型）。
- 編輯器在 1470 寬的螢幕上，右邊屬性欄會被切掉。改法：按鈕三個一列、狀態列可以換行、位置／大小與九宮格四邊兩格一列、選圖按鈕移到路徑下面、屬性欄寬度 340–460。
- 屬性「Field」原本翻成「野外」，改成「綁定欄位」。
- `full_verification_b13_live_check` 的戰鬥步驟：用 HEAD 的程式和資料一樣失敗，所以不是這批或其他工作階段的回歸。原因是剛開始的 Roger 一個人，在輪到他之前就被 9 隻的 swarm 打倒。逃跑檢查改用 woods_patrol，5 項全過。

**還沒做（留給之後）：** 背包格與耐久條的獨立元件、整套範本、多選拖曳。

**狀態：** 已提交（2026-10-24，使用者要求；D65、D67、D68 一起提交，只含這三批的檔案與 hunk，其他工作階段的生物戰鬥與劇情改動沒有包含）。

## D69 — 寶可夢的開始選單：圖鑑、寶可夢、背包、訓練家卡片、記錄、設定（2026-10-24）

**要求：** 使用者看到 Full Verification 的暫停選單，問寶可夢有沒有這些；回答那是引擎測試專案的選單、綠寶石還沒做開始選單後，使用者要下一批把開始選單和裡面的畫面做完。

**引擎（通用，`runtime/creature_menu.py`）：**
- 播放清單 `field.creature_menu` 有內容時，暫停鍵打開遊戲自己的開始選單，取代引擎的暫停選單；畫法和生物戰鬥畫面一樣（遊戲原本的解析度、整數倍放大、同一套字型與圖片）。
- 開始選單：每一列 `{id, label, screen, switch}`；`switch` 沒開就不顯示，`label` 可用 `\V[...]`；位置與寬度可設；外框用遊戲自己的 3 × 3 邊框圖。
- 隊伍：沿用戰鬥的隊伍畫面，選一隻後跳出「能力／替換／取消」；替換會改存檔裡的隊伍順序。
- 能力：三頁背景、圖片與各欄位置都由資料決定（`places`、`stats` 每一格的位置、`name_on_pages`、`move_step`）；位置寫 `null` 就不畫。
- 背包：口袋依道具標籤分（`capture` 收所有捕獲道具），左右換口袋；道具有「使用／丟掉／取消」，田野上還不能用道具，所以「使用」說 `cant_use` 那句（可分頁）。
- 訓練家卡片：背景與人物圖可依變數換（例如性別），名字、編號、金錢、圖鑑數、遊玩時間。
- 設定：每一項存在事件變數 `option.<id>`；`dialogue.speeds` 讓 `option.text_speed` 決定對話每秒幾個字；選中的值與其他值顏色可設。
- 圖鑑：讀項目 JSON；見過＝戰鬥遇過或擁有，捕獲＝擁有或抓過；清單列到最後一隻見過的；`cursor_row` 讓清單在固定的選取列底下移動；項目頁有圖片、分類、身高體重、說明（四行）。
- 記錄：資訊視窗（目前地名、玩家、徽章數、圖鑑、時間）＋「要記錄嗎？」YES／NO →「記錄中」→ 寫入存檔欄 `save_slot` →「…記錄了」。
- 遊玩時間：世界計數器 `play.seconds`，標題畫面以外每幀累加，跟著存檔。
- 新的畫面文字 33 條加進 `rpg/built_in_text.py` 和 `zh-TW.json`，`BUILT_IN_TEXT_KEYS.md` 重產。

**私人的綠寶石專案：**
- `tools/emerald_menus.py` 用原作的圖塊、tile map、調色盤合成：能力三頁（其他兩頁疊在資料頁上，跟原作一樣）、訓練家卡片（男生／女生）、圖鑑清單與項目頁、捕獲球記號；並讀出豐緣圖鑑 202 筆（順序、分類、身高換成英尺英寸、體重換成磅、說明）。
- 開始選單照 `start_menu.c`：圖鑑（拿到圖鑑後）、寶可夢（拿到寶可夢後）、背包、主角名字、記錄、設定、離開；窗格在 (22, 1) 格、寬 7 格。
- 文字用原作的：`Do what with this …?`、`Move to where?`、DAD 的忠告、記錄三句、`OT/`、`IDNo`、設定的各項與 SLOW／MID／FAST（預設 MID，選中紅色、其他綠色）。
- 背包五個口袋：ITEMS、POKé BALLS、TMs & HMs、BERRIES、KEY ITEMS。
- 新遊戲時決定訓練家編號（`player.id`）。

**測試：**
- `tests/test_creature_menu.py`（8 項）：列依開關出現、名字展開、離開；替換兩隻、打開能力換頁；口袋分法、丟掉一個；圖鑑見過／捕獲；設定存進變數；記錄寫出存檔欄；遊玩時間。
- 全套：3346 通過、1 略過；跑全套時抓到兩個自己的問題並修好：選單直接讀道具的 `display_name`（違反 D60 規則，改用 `game.name_of`／`description_of`）、遊玩時間在連線凍結時仍在累加（改成連線遊戲不算）。
- 其餘失敗不是這批造成的：另一個工作階段剛在 Full Verification 的 Hearthfold 加了「Forge」（鍛造爐），擺在神秘學導師的位置上，按互動會選到鍛造爐，所以戰役跑到轉職那步失敗（`mystic`），`test_data_text` 的新頁面文字也是那邊的（那邊之後把鍛造爐移到 (312, 200)，重跑戰役 8 項與 `test_data_text` 全過）；`test_full_verification_ui_words` 同樣是那邊正在改的選單。

**實機證據：** 私人專案 `tools/menu_live_check.py`（Cocoa、真的按鍵、靜音）21 張截圖、16 項檢查全部通過：
- 沒有寶可夢時選單只有 BAG／BRENDAN／SAVE／OPTION／EXIT，拿到後多了 POKéDEX、POKéMON。
- 圖鑑清單與木守宮的項目頁；隊伍、「Do what with this TREECKO?」、能力三頁、替換後蛇紋熊排第一。
- 背包的 POKé BALLS ×5、「使用」說 DAD 的忠告；訓練家卡片（¥3000、圖鑑 3、時間）。
- 設定 MID → FAST → SLOW；記錄問句、記錄中、BRENDAN saved the game.，存檔檔案寫出，選單關掉。
- 注入：開場直接略過、給圖鑑與兩隻寶可夢、5 個寶貝球、見過刺尾蟲、¥3000（列在 `injected`）。

**限制：**
- 圖鑑只有清單與項目頁：沒有搜尋、分布圖、叫聲、大小比較，也沒有開圖鑑時的動畫。
- 能力：屬性用文字（原作是屬性圖示）、沒有特性、性格與遇見地點的備忘、沒有招式說明與威力命中。
- 背包：道具沒有說明文字與圖示（除了寶貝球）、田野上不能用道具、丟掉固定一個（原作會問數量）、沒有 GIVE 與登記。
- 訓練家卡片沒有背面、沒有星星，徽章格空著（還沒有道館徽章）。
- 設定只有文字速度有效果；戰鬥動畫、戰鬥方式、聲音、按鍵模式、外框樣式只記住選擇。
- 記錄只有一個存檔欄；原作會先問是否覆蓋舊紀錄。
- POKéNAV 還沒做（原作拿到後才出現）。

**狀態：** 已提交（be5d3c01，2026-10-25）。

## D70 — 工作台與製作畫面：分頁、數量、成功率與品質、未發現配方、分解（U4）（2026-10-24）

（D69 已被另一個工作階段的生物開始選單用掉，U4 用 D70。）

**做了什麼：**
- 新的資料種類「工作台」`rpg/workstations.py`（`WorkstationDefinition`、`WorkstationCategory`），存在 `rpg_database.workstations`：
  - `station_id` 就是配方的 `station` 與 `OPEN_CRAFTING` 的 `station`；名稱、圖示、說明。
  - 分頁（分類）：依配方標籤分；沒有標籤的分頁收其餘配方。沒有分頁時只有一頁「配方」。
  - `show_undiscovered`（未發現配方顯示 ???）、`max_quantity`（一次最多做幾個）、`disassembly`（分解頁，可用 `disassembly_tags` 限定道具）。
  - 成功音效、失敗音效、成功後閃現的圖片與秒數、開啟時的音樂、`layout`（選單版面）。
  - 專案沒定義的工作台照樣能開：一頁、所有能做的配方、最多 99 個。
- 製作畫面 `runtime/crafting_screen.py` 取代舊的清單：
  - 分頁（Tab／Q／E），各分頁附圖示；配方清單附成品圖示、「可做 N」與產出。
  - 右側面板：成品與說明（自動換行）、材料「持有／需要」（依數量計算，不足標紅）、成功率、品質分級、數量。
  - 左右鍵改數量，上限是工作台設定和材料能做的較小值；一次做多個時，部分失敗會寫出「N 次中成功 M 次」。
  - 未發現的配方排在最後，名稱與內容都是 ???，選到時說明怎麼發現。
  - 分解頁列出背包中能分解的道具與會得到的材料、機率、費用；可一次分解多個。
  - `CraftingScreen`／`CraftingRow` 仍可從 `game_menus` 匯入（連線版的 `NetworkCraftingScreen` 照舊）。
- 選單版面：
  - `crafting` 畫面的元素加上 `wallet`、`tabs`、`detail`、`quantity`、`undiscovered`、`flash`。
  - 每個工作台可以有自己的版面 `crafting.<工作台>`（`base_screen()`），沒有就用共用的 `crafting`。編輯器「版面」頁在「製作（工作台）」下列出每個工作台。
  - 順手修了 U2 的問題：改了版面後，畫面清單會變回英文（`_mark_screens` 沒翻譯）。
- 翻譯：
  - 工作台與分頁的名稱用 `data.workstation.<id>.name`、`data.workstation_category.<id>.name`，列在翻譯頁「資料：工作台」。
  - 品質名稱新增 `data.quality.<名稱>.name`，翻譯頁「資料：製作品質」。
  - 新增 20 個 `crafting.*` 內建文字鍵，`crafting.hint` 改了英文與中文；`BUILT_IN_TEXT_KEYS.md` 已重新產生。
- 編輯器：遊戲系統頁新增「工作台（製作）」，分頁用表格編輯；24 條新的編輯器中文。

**Demo（`trial_crafting.py`）：**
- 爐心鎮廣場：決鬥導師下方、藥師瑟拉旁的**煉金台**（藥瓶），武器匠布蘭下方的**鍛造爐**（鐵砧），兩張圖都是 Ninja Adventure（CC0），和其他鎮民同一套。
  - 鍛造爐第一次放在 (280, 168)，和神秘導師重疊，完整測試裡的 campaign 跟他說話時打開了鍛造爐而失敗；已移到 (312, 200)。
- 煉金台：藥水（新：藥水、高級藥水（品質「精良」做 2 瓶、「傑作」做出超級藥水）、解毒藥、眼藥、萬能藥（70% 成功、失敗得到藥水、要先發現））、寶石、融合、卡片（原有配方加上標籤），加上分解頁。
- 鍛造爐：金屬錠（秘銀；金錠 80% 成功）、投擲物（鐵球、雷電與旋風炸彈）、寶珠（火、冰，要先發現），一次最多 10 個。
- 材料用 G2 的蝙蝠翅膀、蠍子螯、煤炭、秘銀錠、金錠等。成功圖用 demo 的 `fx_heal.png`，音效用 demo 原有的 heal、hit，沒有加新素材。
- 中文：工作台、分頁、品質名稱；配方名稱的「Brew／Smelt／Forge X」譯成「調製／冶煉／鍛造 X」。

**驗證：**
- `tests/test_crafting_workstations.py`（5 項）：資料往返與分頁歸類；煉金台的分頁、圖示、???、一次做兩次、品質顯示、Tab 換頁；分解頁；鍛造爐的上限與沒有資料的工作台；編輯器的工作台資料與每個工作台的版面預覽。
- `scripts/crafting_live_check.py`（真實 Cocoa 視窗、靜音）：中英文各走到煉金台與鍛造爐按 E 打開、做兩次藥水、一次打三份鐵球、Tab 換頁、Esc 關閉，12 項全過。
- 導覽腳本新增 5 個製作畫面（煉金台藥水、寶石、分解，鍛造爐投擲物、未發現的寶珠），中英文共 10 張。
- 證據：`docs/audits/evidence/ui_u4/`（遊戲截圖、`crafting_results.json`、編輯器工作台頁與兩個版面頁的中英文截圖）。

**狀態：** 未提交（等使用者）。

## D71 — 任務告示板與任務卡片、招募事務所、抽獎（U5）（2026-10-24）

**做了什麼：**
- 三種新資料（`rpg/boards.py`、`rpg/gacha.py`），全部在編輯器「遊戲系統」編輯，事件指令打開：
  - **任務告示板** `QuestBoardDefinition`（`rpg_database.quest_boards`）：任務清單（卡片順序）、同時最多接幾件、可重複任務在交回後幾分鐘（遊玩時間）重新出現、開放開關、版面。
  - 任務多了卡片欄位：`card_image`、`rank`（S、A、銅……）、`category`（討伐、運送……）、`repeatable`、`time_limit`（接下後的遊玩分鐘，逾時算失敗）。
  - **招募事務所** `RecruitOfficeDefinition`：候選人（角色、貨幣、價格、等級範圍、備註、肖像、需要的開關）、隊伍上限、可否遣散與退款比例、每個擲出等級的經驗值。
  - **抽獎卡池** `GachaBanner`：貨幣、單抽與多連抽價格與抽數；稀有度（由低到高：名稱、顏色、關閉與打開的寶箱圖、開啟音效）；獎品（道具／裝備／角色／寵物、權重、稀有度、主打、已擁有時改給的道具）；主打權重倍數、硬保底（第幾抽必中、哪個稀有度）、軟保底（從第幾抽起每抽加多少機率）、多連抽至少一個某稀有度、寶箱出現／搖晃／打開的秒數與音效、幸運加成。
- 事件指令 `OPEN_QUEST_BOARD`、`OPEN_RECRUIT`、`OPEN_GACHA`（參數 `board_id`／`office_id`／`banner_id`）。
- 規則 `runtime/boards_play.py`：
  - 告示板：每張卡的狀態（可接取、未開放、進行中、可回報、已完成、等待重新出現、失敗、已滿），逾時自動失敗，重新接取會清掉舊進度，回報才給報酬（`auto_complete=False`）。
  - 招募：付費、入隊、擲等級並給經驗值；遣散退款，最後一位成員不能遣散。
  - 抽獎：狀態（總抽數、距保底、紀錄）存在 `world.systems["gacha.<id>"]`，跟存檔走；固定種子可重現；已擁有的角色／寵物改給道具。
- 畫面 `runtime/service_screens.py`：
  - 告示板：卡片格（圖示、等級章、類別、報酬、狀態戳記），Space／F 翻面看目標進度、時限、報酬與說明；右側詳情。
  - 招募：候選人清單附肖像；右側大肖像、價格、遣散退款、非零能力值、備註；雇用要再按一次 Enter（金色確認條），X 遣散。
  - 抽獎：卡池頁（圖、說明、主打、機率面板一直顯示、保底剩餘抽數）、單抽／多連抽按鈕、寶箱出現→搖晃→打開（依稀有度發光與音效），結果格（重複時註明改給什麼）；R 機率表、H 紀錄。
- 選單版面：`quest_board`、`recruit`、`gacha` 三個畫面，每筆資料可有自己的版面 `<畫面>.<id>`，資料的 `layout` 欄可指定。
- 編輯器：遊戲系統新增「任務告示板」「招募事務所」「抽獎卡池」（稀有度、獎品、候選人用表格）；抽獎卡池有「模擬 10,000 抽」按鈕（種子 0），顯示各稀有度實際比例與設定機率、保底與多連抽保證的次數、最長未出最高稀有度、最常抽到的獎品。
- 翻譯：75 個 `board.*`／`recruit.*`／`gacha.*` 內建文字鍵；資料文字（告示板、事務所、卡池、稀有度、卡片類別 `data.quest_category.*`、招募備註）列在翻譯頁「資料：任務告示板、招募、抽獎」等三組；85 條編輯器中文（含模擬結果的三個句型）。

**Demo（`trial_boards.py`）：**
- 第二種貨幣「星石」，開局 300。
- 爐心鎮廣場：**懸賞告示板**（四張懸賞：投石兵討伐（可重複）、藥草運送（10 分鐘時限）、獵手掃蕩、維勒爾懸賞（地下墓穴後開放）），**公會職員**（米菈、薇絲珀、凱爾，金幣或星石，等級隨機），**星落寶箱**（普通／稀有／神話，十連保證稀有、第 50 抽保底神話、第 36 抽起軟保底、凱爾機率兩倍，已擁有改給萬靈藥）。
- 寶箱圖：Foozle Chest and Key Pack（CC0），放在 `asset_library/foozle/Foozle_2DO0002_Chest_and_Key_Pack`，demo 用 7 張；肖像是 Lucifer 角色的第一格待機圖。`CREDITS.md` 已加上。
- 順手修了：Lucifer 撿拾物圖示是 9–10 格的動畫條，在卡片和結果格裡被壓扁；demo 資料給這 16 個圖示設了第一格的區域（寬 ≥ 高 4 倍才算動畫條，32×16 的長武器不受影響）。

**驗證：**
- `tests/test_boards_gacha.py`（8 項）：資料往返、機率、10,000 抽的保底與多連抽保證、告示板流程（擊敗計數、等待重新出現、逾時、重新接取）、招募雇用／遣散／上限、寶箱抽獎／重複／存檔、翻譯鍵、編輯器種類與模擬、版面預覽。
- `scripts/boards_live_check.py`（真實 Cocoa 視窗、靜音）：中英文各走到三個物件按 E：接懸賞、翻卡、雇用、遣散、十連抽（寶箱搖晃、打開、結果）、機率頁、紀錄頁，26 項全過。
- 編輯器模擬（種子 0、10,000 抽）：神話 4.43%（設定 3.00%，加上軟保底與主打）、稀有 18.09%、普通 77.48%；硬保底 0 次（軟保底在第 50 抽前就出了）、多連抽保證 114 次、最長 44 抽未出神話。
- 證據：`docs/audits/evidence/ui_u5/`（遊戲截圖、`boards_results.json`、編輯器三頁與三個版面頁的中英文截圖）。

**狀態：** 未提交（等使用者）。

## D72 — 選單畫面全面驗收（U6）（2026-10-24）

**做了什麼：**
- 導覽 `trial_ui_tour.py` 加上 U5 的 8 個畫面（告示板、翻面卡片、招募、雇用確認、抽獎卡池、十連結果（固定種子）、機率表、紀錄），現在共 43 個畫面；`reset` 會關掉服務畫面。
- `run_campaign.py` 在最後一場戰鬥之後加了 `services()` 與 `enhance_on_screen()`，用畫面本身的操作（不是直接呼叫規則）：
  - 告示板接下投石兵懸賞 → 在森林打到完成 → 回告示板交回（拿到星石）。
  - 公會事務所遣散米菈（退一半）再雇回來（扣 500 金幣），隊伍維持 4 人。
  - 星落寶箱十連抽（種子 "campaign"），確認至少一個稀有以上。
  - 煉金台畫面做一瓶高級藥水。
  - 裝備紙娃娃從背包把惡魔之戒戴到空的手上。
  - 強化畫面：鑲嵌頁把紅寶石鑲進戒指的空孔，精煉頁精煉一次（自己的亂數，不影響前面的戰鬥）。
  - 新的必須事實：`bounties_taken`、`bounties_done`、`guild_hires`、`gacha_pulls`、`brewed_on_screen`、`doll_worn`、`screen_sockets`、`screen_refines`。
- 新腳本 `scripts/menu_frame_time_check.py`：真實視窗裡每個導覽畫面先畫 10 幀，再量 60 幀的 `_frame`（輸入、更新、繪製、翻頁），寫出平均、95 百分位與最慢；95 百分位超過 16.7 ms 就失敗。

**驗證：**
- 導覽（真實 Cocoa 視窗、靜音）：中英文共 90 張截圖（43 個畫面 ×2，加上戰鬥與遊戲結束），沒有錯誤；`tests/test_full_verification_ui_words.py` 確認中文畫面（含新畫面）沒有 id 和英文。
- 每幀時間（真實 Cocoa 視窗）：86 個畫面全部在預算內；最慢的是翻面告示板，平均 4.50 ms、95 百分位 4.55 ms；全部平均 2.86 ms。版面系統沒有讓選單變慢。
- `run_campaign.py`：通過，所有必須事實非零；隊伍 4 人、完成 6 個任務（多了一個懸賞）；強化畫面精煉 +0 → +1。
- `scripts/full_verification_campaign_live_check.py`（真實視窗）：PASS，上面的事實都在 `results.json`。
- 編輯器新頁面的中英文截圖：U3 `ui_u3/`（裝備、強化、商店版面）、U4 `ui_u4/`（工作台、製作版面）、U5 `ui_u5/`（告示板、招募、抽獎與模擬、三個版面）。
- 證據：`docs/audits/evidence/ui_u6/`（導覽截圖與 `results.json`、`frame_times.json`、`campaign/`）。

**狀態：** 未提交（等使用者）。

## D73 — 綠寶石推到第一個道館：滿充的抓寶教學、橙華森林、卡那茲道館、商店與傷藥（2026-10-25）

**要求：** 使用者要先把劇情推到第一個道館，自己試玩，之後再照建議的順序（提交、補基礎）。

**引擎（通用）：**
- **道具用在生物身上**：`game.use_item_on_pet(pet, item)`（田野）與戰鬥裡的道具都會套用使用效果，並移除道具標籤 `cures:<狀態>`（`cures:*` 全部）列的狀態；倒下的只吃標籤 `revives` 的道具；沒有效果就不消耗。戰鬥背包的第一袋也列出只會治狀態的道具。
- **使用效果的公式環境**：道具效果用自己當來源與目標（之前固定數值的效果在戰鬥與田野都會出錯）。
- **借別人的隊伍**：世界指令 `PARTY_STASH`／`PARTY_RESTORE`：先把玩家的生物收起來，之後放回，中間得到的（借來的、抓到的）一起拿掉。
- **遊戲自己打的戰鬥**：生物戰鬥畫面的 `encounters.<id>` 可設 `player_name`、`player_back`（別人的戰鬥）、`auto_choices`（依序出招、丟球）與 `auto_delay`；遭遇標籤 `sure_capture` 讓捕獲一定成功。
- **事件**：`SET_VARIABLE` 可帶 `add`（加減數字）；條件來源 `rpg` 多了 `pets`（隊伍隻數）。
- **奔跑**：預設按鍵多了 `run`（Shift、手把 B）——之前沒有這個動作，所以格子移動從來跑不起來；`field.run_switch` 讓奔跑要等某個開關（例如拿到跑步鞋）。
- **整數經驗值**：Pet Rules 的 `exp_whole`（每隻分到的經驗無條件捨去），編輯器有欄位與中文。
- **開始選單**：背包「使用」可選一隻生物，顯示回復了幾點或已治好；訓練家卡片可畫 `badges`（開關打開的徽章）。

**私人的綠寶石專案：**
- 地圖加上 104 號道路、卡那茲市與它們的建築（橙華森林、布魯尼小屋、卡那茲道館、得文公司、學校、寶可夢中心、商店…），共 47 個場景。
- 劇本翻譯補上：`trainerbattle_single` 的原作規則（打過就繼續下一行；沒打過就挑戰、戰鬥，贏了跑指定的後續腳本）、撿道具球（`finditem`）、`checkitem`、`removeitem`、`getpartysize`、`addvar`／`subvar`、商店（`pokemart` 的清單變成商店）、`SavePlayerParty`／`LoadPlayerParty`、滿充的抓寶教學（借蛇紋熊 7 級、撞擊、寶貝球、一定抓到拉魯拉絲）。
- 道具照 `items.h`：名字、價格、口袋（關鍵道具、招式學習器、樹果各自的口袋），傷藥類的回復量、解毒藥等治哪個狀態；超級球的捕獲加成 1.5（還有高級球 2、大師球）。
- 拿到跑步鞋才能跑；`giveitem` 之後 `VAR_RESULT` 是 TRUE（之前小遙會多說「背包滿了」）。
- 新歌：橙華森林、104 號道路、卡那茲市、學校、水薙隊遇見曲。
- `tools/play.py`：直接開始新遊戲，或從開始選單的記錄繼續（音樂照常播放，給使用者試玩）。
- 走得通的檢查：在真實碰撞（含單向跳台）上從未白鎮走到橙華森林南口、穿過森林、走到卡那茲道館門口、再走到杜鵑面前，都通。

**測試：**
- `tests/test_items_and_borrowed_parties.py`（7 項）：傷藥從背包補血與消耗、滿血與倒下時不能用、`cures:` 治狀態、收起與放回隊伍、一定捕獲、`pets` 條件、`SET_VARIABLE add`、整數經驗。
- 無頭跑完整條劇情：圖鑑 → 媽媽的跑步鞋 → 諾曼與滿充 → 教學戰 → 回道館 → 橙華森林水薙隊、得文研究員的超級球 → 杜鵑 → 岩石徽章、招式學習器 39。

**實機證據：** `AsteriaEmerald/tools/badge_live_check.py`（Cocoa 960×640、`ASTERIA_MUTE=1` 靜音、只用按鍵）17 張截圖、20 項檢查全部通過（`evidence/badge_b8/badge_results.json`）：媽媽給跑步鞋與 Shift 跑步、商店買傷藥（¥300）、背包對寶可夢用傷藥（+20 HP）、滿充的抓寶教學（WALLY 丟球、「Gotcha! RALTS was caught!」、隊伍還原）、橙華森林水艇隊手下、杜鵑戰、STONE BADGE 旗標、TM39、訓練家卡第一格徽章。注入（全部記在 results 的 injected）：劇情狀態設在拿到圖鑑之後（TREECKO lv12、5 顆球、¥3000）、用傳送跳過走路段落、用傷藥前 TREECKO HP 設 5、水艇隊手下與杜鵑的對手 HP 設 1（WALLY 的自動教學戰不注入）；路徑可走性另以真實碰撞 BFS 驗過四段。

**限制：**
- 商店用的是引擎的通用商店視窗，不是綠寶石的畫面；跑步鞋、徽章、招式學習器的取得短曲與音效還沒有。
- 招式學習器還不能用（只放進口袋）；`multichoice` 選單、HM（居合斬）與道館裡的開門還沒做。
- 訓練家 AI 還是隨機選招；名字固定 BRENDAN／MAY。

**狀態：** 已提交（be5d3c01，2026-10-25）。

## D74 — 基礎批次：音效與短曲、地圖圖塊變化、開門動畫、多選項選單（2026-10-25）

**使用者要求：** 試玩到第一道館之後「照你說的」——先提交，再做基礎批次（門與 setmetatile、音效與短曲、取名字、選初始寶可夢畫面、田野用道具／招式學習器、綠寶石的商店）。這一批做前四項；後四項是下一批。

**引擎（通用，編輯器拿得到）：**
- **短曲（ME）**：世界指令 `PLAY_ME`（`asset_id`、`volume`）播一次短曲，區域音樂先暫停，播完從原處接著放（`AudioMixer.play_me`、`update`；裝置多了 `pause_music`、`resume_music`、`sound_busy`）。短曲播放中開始新的音樂時，短曲直接結束。
- **等聲音放完**：條件來源 `audio`：`me`（短曲播放中）、`se`（最後一個 `PLAY_SE` 還在響）。只有會出聲的宿主（試玩視窗）會設 `plays_audio` 並更新狀態；無頭執行不等。靜音裝置（`ASTERIA_MUTE=1`）照音檔長度等，所以靜音的實機檢查時間跟有聲時一樣。
- **改圖塊**：世界指令 `SET_TILE`（`layer` 圖層名、`x`、`y` 格、`tile`，`-1` 清空，`permanent`）。沒有 `permanent` 的只到玩家離開這個場景為止（GBA 遊戲是每次進地圖由地圖腳本重設）；`permanent` 的存進存檔（`world.systems` 的 `tiles.<場景>`）。田野畫面用自己的地圖副本畫（只複製改到的區塊，原本載入的地圖不動），改到碰撞圖層就會開路或擋路。
- **選項**：`CHOICE` 多了 `cursor`（游標起始的選項）、`cancel`（按取消鍵得到的值；沒寫就沒作用）、`columns`（並排幾個；上下移一整列、左右移一格、不繞回）。對應 `ChoiceRequest` 欄位、存讀、`game.cancel_choice()`。
- **編輯器**：事件指令多了「選項」對話框（提示、每行「文字 = 值」的選項、答案變數、游標起始、取消鍵的答案、欄數、選項框位置），可以新增也可以雙擊修改；新增「等待」指令與對話框（秒數，或直到條件成立：開關、變數、rpg、npc、battle、audio）。之前編輯器沒有等待指令，D66 的「等路線走完」也只能手寫。全部有繁中。

**私人的綠寶石專案：**
- 用現有的 m4a 算繪器算出 269 個音效（`se_*`）與 17 首短曲（取得道具、招式學習器、徽章、回復、升級…）；不循環的歌在最後一個聲音後切掉（之前尾巴多 2–4 秒靜音）。
- 劇本翻譯：`playse`／`waitse`、`playfanfare`／`waitfanfare`、`playmoncry`／`waitmoncry`（叫聲直接用 checkout 的音檔）、`setmetatile`（三個圖層：下層、上層、碰撞）、`opendoor`／`closedoor`（`field_door.c` 的三張開門圖，每張 4 個 GBA 幀、門的音效；位置放在變數裡的門也照每扇門比對）、`multichoice`／`multichoicedefault`／`multichoicegrid`／`yesnobox`（`script_menu.h` 的 99 組選項、框的位置、B 鍵得 127）、`DrawWholeMapView`（引擎本來就立刻畫）。前一行 `message` 的字當成選項的提示（GBA 是訊息留在框裡、選單開在旁邊）。
- 地圖進場先跑 `MAP_SCRIPT_ON_LOAD`（例如家裡的搬家紙箱、拿到跑步鞋後桌上的說明書、103 號道路的洞窟）。
- 走進有門的出入口：門先打開（音效、三張圖），再進屋；從屋裡出來：門在身後關上。
- 撿到／拿到道具：取得短曲（招式學習器用自己的短曲）跟「拿到了」那行一起出現，短曲播完才出現「放進口袋」；撿道具球時球先消失（照原作順序）。
- 開始選單與各選單的按鍵音：開啟 `SE_WIN_OPEN`，移動、確定、取消 `SE_SELECT`（專案的選單主題 `sounds`）。

**測試：** `tests/test_sounds_tiles_choices.py`（7 項）：短曲暫停與恢復音樂、事件等短曲（無頭不等）、`SET_TILE` 這次與永久（存讀）、田野畫面畫出與走過改過的圖塊（原地圖不變）、選項的游標起始／取消鍵／欄數、選項編輯器、等待編輯器。

**實機證據：** `AsteriaEmerald/tools/foundations_live_check.py`（Cocoa 960×640、`ASTERIA_MUTE=1`、只用按鍵）11 張截圖、13 項檢查全部通過（`evidence/foundations_b9/foundations_results.json`）：走進家門時門的三張圖依序出現、`se_door`、進到屋內；屋裡 ON_LOAD 放的跑步鞋說明書；出門時門在身後關上並回到原本的圖；102 號道路的道具球：`pause_music` → `mus_obtain_item` → 1.88 秒後才出現第二行 → `resume_music`，球消失；卡那茲寶可夢學校的黑板：6 個選項 3 個一列、右＋下移到 FRZ、B 退出得 127；開始選單的 `se_win_open`、`se_select`。注入：劇情狀態設在拿到圖鑑與跑步鞋之後、用傳送到家門口、道具球下方、學校黑板前。

**回歸：** 全部測試 3380 通過、1 略過；之前的實機檢查重跑（Cocoa、靜音）：開始選單 16/16、第一道館 20/20、劇情 41/41。劇情檢查有兩項是 D73 留下的過時期待，已修正檢查本身：Oldale 寶可夢中心前的重生點座標寫死成 D73 加地圖之前的位置（改成跟存下的重生點比）；D73 加了 WALLY 的抓寶教學後，檢查沒有把教學戰看完，後面諾曼的三項卡住（加上 `wally_tutorial_over`）。

**限制：**
- 走進門：玩家先站到門的格子上門才打開（原作是門先開、玩家再走進去）；出門時玩家出現在門下一格，門關上（原作是從門口走出來）。
- 戰鬥裡還沒有音效與短曲（攻擊、丟球、抓到、升級）。
- 布魯尼船長、得文公司化石等多選項要等劇情到那裡才會用到；橙華道館的房間門（`special PetalburgGym*`）、連線室與賽場的圖塊還沒做。
- 取名字、選初始寶可夢畫面、田野用道具與招式學習器、綠寶石樣式的商店：下一批。

**狀態：** 未提交（等使用者）。

## D75 — 取名字、選初始寶可夢、商店、招式學習器（2026-10-25）

**使用者要求：** 「繼續」——基礎批次的後半：取名字、選初始寶可夢的畫面、田野用道具與招式學習器、綠寶石樣式的商店。

**引擎（通用，編輯器拿得到）：**
- **不等按鍵的對話**：`DIALOGUE` 的 `wait: false`：字顯示在訊息窗，事件繼續往下；留到下一句、下一個選項或事件結束（`game.held_dialogue`）。沒寫提示的 `CHOICE` 會用這句當提示（GBA 的 `message` + `waitmessage` 就是這樣：字留在框裡，選單開在旁邊）。訊息窗不畫「按鍵繼續」的箭頭。
- **取名字**：世界指令 `NAME_INPUT`（`target`：`variable:<變數>` 或 `pet:last` / `pet:<編號>`，`max_length`、`title`（`{species}`＝那隻的種類）、`default`（什麼都沒打就按 OK 時用）、`initial`）。名字畫面 `runtime/name_input.py`：幾頁鍵盤（大寫、小寫、符號，TAB＝SELECT 換頁）、BACK／OK 按鈕、B 刪字、打滿時游標跳到 OK；`field.name_input` 給遊戲自己的圖與位置，沒給就用簡單的形狀。事件用條件 `rpg` `name_input` 等它結束。
- **圖片選擇**：世界指令 `PICTURE_CHOICE`（`layout`、`variable`）：`field.picture_choices.<layout>` 的背景、選項圖（被選中的有動畫）、上下浮動的指標、選中時加暗的標籤、確認時長大的圓與預覽圖、YES／NO。選初始寶可夢、選職業之類都能用；條件 `rpg` `picture_choice`。
- **教招式的道具**：道具標籤 `teaches:<能力>`（`reusable` 不會用掉，像 HM）；種族的 `teachable` 列它可以被教的能力（編輯器有欄位與中文）。`game.teaching_check(pet, item)`：`able`／`learned`／`not_able`。招式滿了就問要忘記哪一招，回答之後才用掉道具；放棄就不用掉。
- **開始選單的背包**：招式學習器「使用」：開機、內容、要教嗎 YES／NO，隊伍欄位顯示 ABLE／NOT ABLE／LEARNED（`slot_label`），學會時可播 `bag.learned_sound`。
- **遊戲樣式的商店**：`field.creature_shop` 有設定時，`OPEN_SHOP` 開 `runtime/creature_shop.py`：BUY／SELL／QUIT 視窗疊在田野上（訊息窗留著店員剛說的話）；購買畫面：錢、商品與價格、選中商品的圖示與說明、要幾個（上下 1、左右 10，兩端繞回）與總價、YES／NO、`buy_sound`、`bonus`（買滿幾個送一個）；賣出用背包。購買畫面的地圖：田野鏡頭讓玩家面前那格停在 `map_front_at`（`TileSceneView.player_at`）。事件等商店關掉（條件 `rpg` `shop`）再往下（「歡迎再來」）。這種商店會立刻打開，不必等事件結束。
- **道具說明**：`ItemDefinition.description`（只在有寫時存；翻譯頁會列出來）。
- 新的內建字：`creature.menu.*`（招式學習器）、`creature.shop.*`（商店）都有繁中。

**私人的綠寶石專案：**
- 取名字畫面照 `naming_screen.c`：背景、三頁鍵盤圖、PAGE 鍵（框、下一頁顏色的鍵與字）、BACK／OK、16×16 游標、底線、標題與玩家／寶可夢圖示、字置中；伯奇的開場：「你叫什麼名字？」→ 取名字（沒打字就用 `main_menu.c` 預設名字中的一個）→「是 XXX 嗎？」NO 回到選男生女生。收到寶可夢後的取暱稱（`ChangePokemonNickname`）用同一個畫面，回到田野時淡入。
- 選初始寶可夢照 `starter_choose.c`：草地與伯奇的包包、三顆球（被選中的會晃）、手指、加暗的標籤（「WOOD GECKO POKéMON」＋名字）、長大的圓與寶可夢、「Do you choose this POKéMON?」YES／NO。
- 商店照 `shop.c`：`menu.bin` 的框（第 0 格看得到地圖）、MONEY 標籤、說明照 `item_descriptions.h`、圖示照 `item_icon_table.h`、SE_SHOP、買 10 顆寶貝球送紀念球（紀念球也是捕獲道具）。`message` 的最後一頁、`waitbuttonpress`、拿到道具時「拿到了」那行改成不等按鍵（照原作）。
- 招式學習器與 HM：`tms_hms.h` 的順序、`tmhm_learnsets.h` 的相容表；學會時 MUS_LEVEL_UP。

**測試：** `tests/test_teaching_items.py`（3 項）、`tests/test_held_lines_shops_names.py`（8 項：不等按鍵的對話與選項提示、留到事件結束、取名字給變數與寵物、圖片選擇、道具說明、商店用按鍵買 3 個與繞回、名字畫面換頁刪字與預設名字、圖片選擇的確認與返回）。

**實機證據：** `AsteriaEmerald/tools/screens_live_check.py`（Cocoa 960×640、`ASTERIA_MUTE=1`、只用按鍵）18 張截圖、13 項檢查全部通過（`evidence/screens_b10/screens_results.json`）：開場在鍵盤上打出「RoGER」（大寫、小寫兩頁都用到）、「So it's RoGER?」YES；暱稱畫面「TREECKO's nickname?」打「LEAF」；Oldale 商店：店員的「How may I serve you?」留在 BUY／SELL／QUIT 下面、買 10 顆寶貝球（×10、¥2000、YES、`se_shop`、送紀念球、錢 ¥3000→¥1000）、從背包賣傷藥（¥150）、QUIT 之後「Please come again!」；開始選單的背包：招式學習器 BULLET SEED（開機、問要不要教、LEAF 顯示 ABLE、蛇紋熊 NOT ABLE、學會並播 MUS_LEVEL_UP、道具用掉）。注入：劇情狀態設在拿到圖鑑之後、給 TREECKO 5 級、直接開始實驗室的取暱稱腳本、傳送到商店櫃台、¥3000 與一個傷藥、給招式學習器與一隻蛇紋熊。

**回歸：** 全部測試 3423 通過、1 略過；實機（Cocoa、靜音）劇情 43/43（開場改成在鍵盤打 BRENDAN、選初始寶可夢改成包包畫面）、開始選單 16/16、第一道館 20/20（商店改成綠寶石的購買流程）、D74 基礎 13/13、D75 畫面 13/13。Full Verification demo 的中文表補上 28 個新的內建字。

**限制：**
- 名字畫面上方的按鍵說明列（十字鍵 MOVE、A OK、B BACK 的圖示）還沒畫；換頁沒有原作翻頁的動畫。
- 選初始寶可夢：圓長大與移到中間是直線近似，不是原作的仿射動畫步驟。
- 商店賣東西用的是開始選單的背包畫面（原作的賣出也是背包，但標題列與數量視窗的位置不完全一樣）。

**狀態：** 未提交（等使用者）。

## D76 — 遊戲中畫面的版面：點陣字、對話框、動作 RPG HUD、戰鬥畫面（UI_PLAN_2 V1–V4、V6）（2026-10-25）

使用者 2026-10-25 核准 `UI_PLAN_2_2026-10-25.md`：照 V1→V6 的順序做、戰鬥畫面用建議的自由度（現有元件可移動、縮放、換外觀、隱藏，加作者自己的裝飾；戰鬥邏輯不動）；V5（生物畫面）等寶可夢 session 這輪結束後再做。也要求「所有設定都在 GUI 改，不用寫 JSON」與「手繪素材適用任何介面與圖示」。

**做了什麼：**
- **V1 共用基礎：**
  - `ScreenSpec.size`（畫面自己的解析度，版面座標用它）與 `group`（編輯器清單分「選單」與「遊戲進行中」）。
  - 元件的動畫條：`frames`、`frame_axis`、`fps`；`MenuCanvas.strip_frame` 依畫面給的進度（冷卻）或時鐘選格。
  - 點陣字 `MenuBitmapFont`（演出庫類別 `bitmap_font`，只在有資料時寫入，舊專案檔不變）：字寬從畫出的像素量；三種顏色模式；字圖沒有的字改用一般字型。編輯器「點陣字型…」對話框：字圖、格子、每列字元（可插入空格 `⬚`）、個別字寬表、切格預覽（每格標出字元）、遊戲中的樣子。
  - 技能樹的節點外框（鎖住、可學、已學、滿級、選中）、連線顏色與線寬、點數圖示都能換成作者的圖。
  - `picture_field()`：通用表單裡所有放圖的欄位都有預覽與「選擇…」；`success_image`、`battle_background` 改成圖片選擇器。
- **V2 對話框：**
  - 一般視窗走 `dialogue`／`dialogue_choice` 版面：視窗、名字與名字框、頭像位置、台詞（文字區、字級、顏色、點陣字、行高、每秒字數）、繼續提示、箭頭動畫條；選項的欄數、格寬、行高、選中外框（有外框時不畫「>」）。
  - 圖片視窗搬進專案資料 `DialogueWindowStyle`（類別 `dialogue_window`），編輯器「圖片對話視窗…」每個欄位都能改；「從遊戲資料夾的 manifest 轉入」一鍵轉換（字型 JSON 轉成點陣字），測試確認轉換後逐像素相同。
- **V3 動作 RPG HUD（`hud_action`，30 個元件）：** 兩顆球（外框、液體、空球的圖，名稱與數值字）或改成條；底板帶著技能格移動；技能格與大技能格的外框、格子大小、間距；按鍵帽；冷卻動畫條；徽章；消耗；經驗、等級；狀態格；其他資源條；上方提示；鎖定框；橫幅；倒下的色調與字。`MenuTheme.resource_colors` 讓作者指定每種資源的顏色（取代依名稱猜）。
- **V4 戰鬥畫面（`battle`）：**
  - `presentation/battle_layout.py`：composer 照舊排好之後，依組整組處理——隊伍卡片、頭上名字與條、指令選單（含技能與道具頁）、說明框、目標與步驟清單、行動順序列、傷害數字、結果面板、目標游標。
  - 可移動（x、y）、縮放（寬高 0＝引擎大小，所以拖曳就是移動）、換外觀（九宮格、圖、填色、外框；選中列有自己的外觀）、改字色字級、隱藏；作者自己的圖、面板、文字（`key:` 可翻譯；圖層 < 0 在下面）。
  - 戰鬥 HUD 的「只在變化時重排」（D48）不變：沒有 `battle` 版面時這一步完全不跑。
  - 編輯器預覽會開一場範例戰鬥（第一個遭遇）；版面座標是戰鬥的虛擬座標，畫布用 `MenuPreview.unit` 換算像素，預覽完的戰鬥直接丟掉不結算。
- **編輯器順便修的：**
  - 主題的數字框右側 padding 和上下箭頭重複扣寬，73 px 寬的框只剩 8 px 文字區（「590」只看到「59」）；改成 padding 0 後同寬有 38 px，箭頭仍在框內。影響整個編輯器的數字框。
  - 數字框的「特殊值文字」（例如「引擎預設」「半格」）現在也跟著介面語言切換（`i18n` 包裝 `setSpecialValueText`）。
  - 新增的編輯器文字都有繁中（`zh_TW.json` 約 135 條、3 條格式）。
- **遊戲文字：** 預覽用的範例選項改用自己的鍵 `dialogue.sample_yes`／`sample_no`／`sample_ask`（原本借用 `title.new_game`，英文不一致被測試抓到），zh-TW 各一條，Full Verification 的 zh-TW 表也補了這 3 條。

**驗證：**
- 新測試：`test_ui_layout_v1.py`（10）、`test_picture_fields.py`（4）、`test_dialogue_layout_v2.py`（7）、`test_hud_layout_v3.py`（6）、`test_battle_layout_v4.py`（5），共 32 個通過。
- **沒有版面時逐像素不變**（HEAD 的 src 與現在的 src 各畫一次、固定時鐘）：UI 導覽 43 個畫面中英文、Party RPG 戰鬥兩幀、ARPG HUD 共 89 張，加上對話框（台詞、無名字台詞、選項）中英文 6 張，全部相同。
  - 比對時抓到一個回歸：選項框背後的視窗面板在 V2 不見了；已修，修完重比為相同。
- **每幀時間**（真實 Cocoa 視窗）：選單 86 個畫面都在 16.7 ms 內，最慢翻面告示板 95 百分位 5.86 ms；Party RPG 戰鬥沒版面 0.97 ms、有版面 0.88 ms（95 百分位）；ARPG HUD 沒版面 2.82 ms、有版面 3.02 ms。
- 真實視窗截圖（中英文，引擎樣子與作者版面各一）：對話、選項、技能樹、戰鬥（Full Verification）、HUD（ARPG）。
- 編輯器截圖（Cocoa，中英文）：技能樹、對話、選項、戰鬥、HUD 版面頁，點陣字型、圖片對話視窗、選單主題三個對話框。
- 圖示與圖片的匯入檢查：遊戲系統表單、內附專案裡所有放圖的鍵、通用資料樹、版面屬性欄都由 `test_picture_fields.py` 守著（新增欄位沒有選擇器會失敗）；角色、戰鬥圖、圖塊這類資源是從「素材 ▸ 匯入」進來的檔案（`uri`／`source_path`），本來就有自己的檔案選擇。
- 證據：`docs/audits/evidence/ui_plan2/`（截圖、`pixel_identity.json`、`menu_frame_times.json`、`battle_hud_frame_times.json`）。

**還沒做或已知的限制：**
- **V5 生物畫面**：寶可夢 session 結束後做完，見 D77。
- 舊的 manifest 字型沒有空白字時：舊版遇到含空白的句子整句改用系統字（`covers()` 不成立），轉成點陣字後用點陣字畫、空白半格——這是改善，不是誤差（D78 查證）。
- 範本裡只在 manifest 的欄位（`field.background`、`player_sheet`、`entity_sprites`，舊的試玩 manifest）沒有搬。D78 已改：「遊戲資料夾設定…」用設定樹編輯整個檔案。
- 選項框的預設大小是訊息視窗的大小，作者把行高調大時要自己把框拉大（不會自動長高）。D78 已改：自動長高。
- 戰鬥版面一組只能整組移動；組裡的單一列（例如只移動某張隊伍卡片）不能分開放。D78 已改：隊伍卡片與頭上名字條可以一張一張放。

**狀態：** 未提交（等使用者）。

## D77 — 生物遊戲自己的畫面搬進專案資料，編輯器可改（UI_PLAN_2 V5）（2026-10-25）

使用者核准 UI_PLAN_2 時說 V5「等寶可夢 session 這輪結束後由你做」；那個 session 做完 D74、D75 後通知可以開始。

**做了什麼：**
- **專案資料：** 一對一生物戰鬥、開始選單、生物商店、輸入名字、圖片選項，五個畫面的設定原本只寫在遊戲資料夾的 `playable_test_manifest.json`。現在放在演出庫的新類別 `creature_screen`（一個畫面一筆，記錄 id 就是它取代的 manifest 路徑，例如 `battle.creature_screen`），只在有資料時寫入，舊專案檔不變。
  - `presentation/creature_screens.py`：`CreatureScreenSettings`（`data` 保持 manifest 原本的形狀；`enabled` 關掉時留著記錄但改用 manifest）。
  - `creature_settings(runtime, 畫面)`：專案的記錄開著就用它，否則用 manifest（舊遊戲照常跑）；回傳複本，畫面改自己的不會動到專案。
  - `creature_battle_on(runtime)`：戰鬥記錄開著，或 manifest 的 `battle.style` 是 `creature`。
  - 畫面讀取改走它：`creature_battle.py`、`creature_menu.py`（對話視窗也改走 `rt.dialogue_settings()`，D76 留下的尾巴）、`creature_shop.py`、`name_input.py`、`picture_choice.py`、`field_ui.py`、`battle_flow._creature_style`。
  - `playable_test_runtime.py` 三處 `manifest["battle"]` 改成 `.get`，manifest 沒有 `battle` 的遊戲也能開。
- **編輯器：** 簡報 ▸ 選單畫面 ▸ 版面的新按鈕「生物畫面…」：
  - 左邊五個畫面（● 表示專案有自己的設定）；「使用這些設定」開關。
  - 中間是每個設定的樹，依種類給欄位：圖片（預覽、選擇…、素材庫…）、音效與字型檔、顏色按鈕、位置 (x, y)、數字、是／否、文字；表格與清單可展開，右鍵可新增一列、複製這一列、移除、新增設定（選種類）。戰鬥的 `layout` 位置與 `colours` 文字顏色即使專案沒寫也列出引擎預設，作者可直接改；存檔時只留下和預設不同的。
  - 右邊是畫面的 240 × 160 預覽：背景圖上畫出每個位置的圓點，拖曳就改座標，和樹的選取互相連動；只標出選中點的名字（其他點滑過才顯示），避免名字疊在一起。
  - 「從遊戲資料夾的 manifest 轉入」一次轉入五個畫面；「為這個畫面建立設定」「移除這個畫面的設定」。每個畫面的變更都是一個可復原的步驟（`MenuLayoutAuthoringController.set_creature_screen`、`read_creature_manifest`、`import_creature_manifest`）。
  - 編輯器新文字都有繁中（23 條、4 條格式）。

**驗證：**
- 新測試 `test_creature_screens_v5.py`（7）：記錄來回存讀、沒資料不寫入、專案優先與關掉後退回 manifest、戰鬥開關、manifest 轉換、編輯器轉入與復原、設定樹的位置／拖曳／新增列／移除與只存差異、開始選單從記錄畫出來與從 manifest 畫出來逐位元組相同。寶可夢 session 指定要保持綠燈的四個測試檔照樣通過。
- **逐像素**（AsteriaEmerald，960×640，固定時鐘與亂數；開始選單、商店、戰鬥第 30／120／399 幀）：
  - 用 manifest 與轉成專案記錄（並從 manifest 刪掉那幾段）：5 張相同。
  - V5 的讀法與舊的直接讀 manifest：5 張相同。
  - 和 HEAD 比：選單相同；商店在 HEAD 還不存在（寶可夢 session 未提交的檔案）；戰鬥訊息的打字進度差幾個字，來自工作區其他未提交的改動（舊讀法也一樣），不是 V5。
- **每幀時間**（真實 Cocoa 視窗）：開始選單中位數 3.05 ms、95 百分位 3.14 ms；戰鬥 1.20／1.22 ms；用 manifest 時 3.06／1.20 ms，沒有差別。
- 編輯器截圖（Cocoa，中英文）：版面頁、生物戰鬥（位置展開）、開始選單。Full Verification 的截圖放 `docs/audits/evidence/ui_plan2/v5/`；AsteriaEmerald 的截圖與遊戲畫面只放在本機暫存（那是私人專案的美術，不進這個 repo）。

**還沒做或已知的限制：**
- 設定樹照 manifest 的鍵名顯示（例如 `foe_box`、`state_messages`），沒有逐一寫說明；種類是從鍵名與值推測的（`*_at`、`*_box`、`colour`、圖片副檔名）。D78 已加說明（取自畫面程式的說明文字）。
- 位置預覽只畫背景圖與圓點，不是真的把畫面畫出來；要看實際樣子仍用「在遊戲中開啟」。D78 已改：用遊戲的程式畫出來。
- 戰鬥以外的畫面沒有引擎預設可列，專案沒寫的設定要用「新增設定」自己加。D78 已改：開始選單、商店、輸入名字也列出預設。

**狀態：** 未提交（等使用者）。

## D78 — UI_PLAN_2 收尾：D76、D77 列出的限制全部處理（2026-10-25）

使用者 2026-10-25 在提交 D76＋D77 後說「commit 完後繼續把剩下的都優化完」。這一批處理 D76、D77「還沒做或已知的限制」列出的每一條。

**做了什麼：**
- **只寫在專案裡的生物商店也會開：** 事件開商店時，原本判斷「這是生物商店」只看 manifest（`field.creature_shop`），只存在專案記錄的商店不會開。改成走 `creature_settings`（這個修正已在 `ed2bc517` 一起提交，這批補測試）。
- **選項框自動長高：** 作者把選項的行高調大或改成一欄時，框會長到包住提問與每一列（提問上方 12 px、最後一列下方 6 px，和引擎原本的留白相同，所以沒有版面時大小不變）。作者自己放了框（`box` 有位置）就照作者的。
- **舊字型的空白：** 查證後發現 D76 寫的限制描述不對：舊字型沒有空白字時，含空白的句子整句改用系統字；轉成點陣字後是用點陣字畫、空白半格。這是改善，程式不改，D76 的說明更正。
- **生物畫面頁：**
  - 預覽改成**遊戲自己畫出來的畫面**（`MenuPreview.render_creature`）：每次改設定，停手 0.15 秒後重畫；圓點畫在真畫面上。設定只是「借」給預覽，畫完就還原專案原本的記錄（測試守著）。畫不出來（沒有遭遇、沒有生物可派）時退回背景圖。
  - 每個設定有**說明**：滑過顯示提示，選中時顯示在樹下方；文字取自畫面程式本身的說明（同一張表的句子優先，例如 `badges` 裡的 `switch` 不會拿到開始選單那列的說明）。
  - 開始選單（摘要頁、訓練家卡的位置）、商店（各視窗位置）、輸入名字（字母頁）也列出**引擎預設**，作者可直接改；存檔時只留和預設不同的。
  - 視窗內框 `[x, y, w, h]` 也是位置：四個數字框（不放上下箭頭，免得擠掉數字），預覽畫出虛線框，拖曳時寬高不變。
- **戰鬥版面一張一張放：** `party_hud.1`、`party_hud.2`……（隊伍卡片，依畫出來的順序）與 `overhead.1`……（頭上名字與條），在整組排好之後單獨移動、縮放、換外觀或隱藏。編輯器的元素清單列出 1–6（執行時沒有上限），預覽畫出每張卡的外框可直接拖。沒有這類元素時什麼都不動。
- **遊戲資料夾設定：** 範本與舊遊戲只寫在 `playable_test_manifest.json` 的設定（野外背景、主角圖、地圖人物的圖、戰鬥的英雄、敵人圖與排列、技能名稱、音樂、操作說明……）改用同一棵設定樹編輯（圖片選擇器、顏色、位置、數字、是／否、表格；右鍵新增、複製、移除）。入口：執行 ▸ 遊戲資料夾設定…，以及版面頁的「遊戲資料夾設定…」。按確定才寫回檔案，沒改就不寫；寫回的格式和原檔相同（四個內附範本不改內容按確定，檔案逐位元組相同）。沒有這個檔案的遊戲不會被建立（有沒有這個檔案決定試玩走哪條路）。
- 新文字都有翻譯：編輯器 8 條、3 條格式；遊戲文字 `dialogue.sample_name`（輸入名字預覽的標題）。

**驗證：**
- 新測試：`test_game_folder_settings.py`（6）；`test_creature_screens_v5.py` 加 3 個（只在專案的商店會開、預設與說明、借設定畫畫面且還原）；`test_battle_layout_v4.py` 加 2 個（單張卡片、沒有卡片元素時不動）；`test_dialogue_layout_v2.py` 加 1 個（選項框長高，作者放的框不變）。
- **沒有版面時逐像素不變**（和 HEAD `ed2bc517` 比，固定時鐘）：UI 導覽、戰鬥、HUD 89 張，對話框 6 張，全部相同。
- **每幀時間**（真實 Cocoa 視窗，Party RPG 戰鬥，各跑兩次）：95 百分位 HEAD 1.62–2.75 ms，現在 1.68–2.03 ms（沒版面、有版面、有卡片元素三種），差異在雜訊內。
- 生物畫面重畫時間（AsteriaEmerald）：戰鬥 525 ms（要跑 200 幀讓生物出場），開始選單 9 ms、商店 15 ms、輸入名字 21 ms、圖片選項 15 ms。
- 截圖（Cocoa，中英文）：遊戲資料夾設定、戰鬥版面頁選中 `party_hud.1`；遊戲畫面（真實視窗）：長高的選項框、單獨放的隊伍卡片。放在 `docs/audits/evidence/ui_plan2/opt/`（含 `checks.json`）。AsteriaEmerald 的生物畫面頁截圖只在本機暫存（私人專案的美術）。

**還沒做或已知的限制：**
- 設定的說明是畫面程式裡的英文說明，介面切成中文時說明仍是英文。（D80 已改：90 句說明都有中文。）
- 生物戰鬥的預覽每次重畫要約 0.5 秒（只在停手後重畫一次）。（D80 已改：約 4 ms。）
- 開始選單與商店是疊在野外上的畫面，預覽裡野外的部分是黑的。（D80 已改：畫出野外。）
- 遊戲資料夾設定的分區名稱照檔案的鍵名（`progression_rewards`、`audio` 沒有中文名稱），設定沒有逐一說明；寫回檔案不在編輯器的復原紀錄裡（按取消可放棄）。（D80 已改：分區有名稱、寫回可復原；逐項說明仍沒有。）

**狀態：** 已提交。D78 的程式與文件隨 `f4f5bf08`（D79 的提交；兩個工作階段共用同一個暫存區，D79 提交時把已暫存的 D78 檔案一起帶進去）進了 main；歷史不改寫，這裡記下對應關係。

## D79 — 綠寶石推到第二個道館：搶回得文貨物、布魯尼出航、武斗道館的黑暗（2026-10-25）

**使用者要求：** 「commit 完後繼續」——D74、D75 提交（db6ada42）之後接著做下一批；照之前的方向把劇情往下推。

**引擎（通用，編輯器拿得到）：**
- **黑暗與照明**：世界指令 `SET_LIGHT`（`radius` 世界單位、`speed` 每秒、`off`）：田野除了玩家周圍的圓之外全黑；`speed` 讓圓慢慢變大或變小，`off` 時變大到看不見再關掉。照明屬於設定它的場景（換到別的地方就不暗，回來還是暗，地圖進場腳本會重設）。條件 `rpg` `light`：圓還在變的時候是 "moving"。
- **`SET_POSITION` 沒給的軸留在原地**：只寫 `permanent` 就是「它現在站哪就永遠站哪」。

**私人的綠寶石專案：**
- 戶外地圖加上 116 號道路、105、106 號水路與釣鎮，經由出入口連到釣鎮的房子、道館、寶可夢中心、石之洞窟、Rusturf 隧道（還有隧道另一頭的地圖，之後才會用到）。
- **同一格的多個觸發點**：原作在同一格依序找第一個條件成立的觸發點（`GetCoordEventScriptAtPosition`）；之前每個觸發點各自一個實體，引擎只會觸發其中 id 最小的那個，條件不成立就什麼都不做（卡那茲的「貨物拿回來了」因此不會觸發）。現在一格合成一個實體、一個程式，依序判斷。
- 劇本翻譯補上：`copyobjectxytoperm`、`setflashlevel`／`animateflash`（`field_screen_effect.c` 的半徑表；`animateflash` 每幀 1 像素，等它變完）、`pokenavcall`（爸爸的來電，不等按鍵）、開始選單教學（`ScriptMenu_CreateStartMenuForPokenavTutorial`：照原作順序的開始選單選項，選 POKéNAV 才繼續）；`requires_flash` 的地圖（石之洞窟 B1F、B2F）進去就暗。
- 開始選單多了 POKéNAV 這一列（拿到之後才出現；POKéNAV 畫面還沒做）。
- 新歌：釣鎮、出航、紫堇鎮、封印之間。
- 實機檢查共用的 `tools/live_kit.py`（開視窗、按鍵、對話、戰鬥、放置玩家；`ASTERIA_DRY=1` 用同樣的步驟無頭跑）；`badge_live_check.py` 最後把遊戲存到 `evidence/saves` 第 1 格，`knuckle_live_check.py` 從那裡接著玩。

**測試：** `tests/test_light_and_positions.py`（4 項）：照明立刻設定與慢慢變亮並等待、照明只屬於它的場景、田野畫面畫出黑暗與照亮的圓、`SET_POSITION` 保留沒給的軸。

**實機證據：** `AsteriaEmerald/tools/knuckle_live_check.py`（Cocoa 960×640、`ASTERIA_MUTE=1`、只用按鍵），從 `badge_live_check.py` 存下的岩石徽章之後接著玩，19 張截圖、23 項檢查全部通過（`evidence/knuckle_b11/knuckle_results.json`）：卡那茲的水艇隊手下搶走貨物、116 號道路布魯尼拜託救 PEEKO、Rusturf 隧道手下後退並對戰、拿回得文貨物、員工帶到 3F、石先生給 POKéNAV 與信、走出得文公司：研究員加上 MATCH CALL、開始選單教學（選 POKéNAV 那一列）、南出口小遙對戰、布魯尼小屋「出航」、坐船到釣鎮（「Ahoy!」）、武斗道館一進去只剩半徑 24 的光圈、阿武戰、拳頭徽章、燈全亮、TM 健美。注入：從存檔開始、用傳送跳過走路與樓梯、對手 HP 設 1（手下、小遙、阿武）、直接走到阿武面前（道館訓練家沒打）。

**回歸：** 全部測試 3446 通過、1 略過；劇情 43/43（觸發點合併後改用 `LittlerootTown trigger 1`）、第一道館 20/20。

**限制：**
- POKéNAV 畫面還沒有（教學裡選了 POKéNAV 之後直接跳過畫面）；Match Call 只登記，不能打電話。
- 武斗道館的燈：照原作每打贏一個訓練家亮一級，但檢查是直接走到阿武面前（訓練家沒打）。
- 往紫堇鎮的 Rusturf 隧道另一頭要碎岩（HM），還沒做。
- 出航時的船與海浪只是格子路線，沒有原作的船身晃動。

**狀態：** 未提交（等使用者）。

## D80 — D78 剩下的限制：中文說明、戰鬥預覽變快、預覽畫出野外、遊戲資料夾設定可復原（2026-10-25）

**使用者要求：** 「都做」——D78 留下的三件事：在決策紀錄註明 D78 的程式隨 `f4f5bf08` 進了 main（已提交 `4b64ee11`）、處理 D78 列出的限制、推上 GitHub。

**做了什麼：**
- **設定說明有中文：** 生物畫面頁的說明取自畫面模組的英文 docstring；現在 `help_for` 回傳前經過編輯器的翻譯，五個畫面共 90 句說明都加了中文（`zh_TW.json`）。docstring 句首的項目符號 `*` 不再顯示。測試會逐句檢查：之後改了 docstring 卻沒補翻譯，測試就失敗。
- **生物戰鬥預覽變快：** 原本跑 200 個完整的遊戲幀（每幀都畫整個畫面）讓生物出場；現在第一幀讓執行環境開啟戰鬥畫面，之後只推進戰鬥畫面本身的 200 步邏輯，最後畫一次。AsteriaEmerald 重複重畫：140–144 ms → 3–6 ms，畫出來的畫面逐像素相同。（D78 記的 525 ms 包含第一次載入。）
- **開始選單與商店的預覽畫出野外：** 這兩個畫面在遊戲裡是疊在野外上的；預覽現在先照遊戲的方式畫野外（鏡頭對準主角），取出 240 × 160 的部分，再把畫面疊上去。輸入名字、圖片選項、戰鬥本來就是整張畫面，不變。
- **遊戲資料夾設定：**
  - 引擎會讀的分區有名稱，鍵名留在括號裡：場景（field）、戰鬥（battle）、訊息視窗（dialogue）、音訊（audio）、操作（controls）、成長獎勵（progression_rewards）、繪製（render）、標題畫面（title）。引擎不認得的分區照鍵名顯示。
  - 按確定寫回檔案改成編輯器復原紀錄裡的一步（「Game Folder Settings」）：編輯 ▸ 復原把檔案原本的文字（連原本的縮排）寫回去，重做再寫一次新的。
  - 版面頁的預覽記住它讀到的檔案內容，檔案變了（寫回、復原、重做）就重新開一個預覽，不再在寫回後手動關掉。

**驗證：**
- 測試：`test_game_folder_settings.py` 加 3 個（寫回是一步復原且還原原文、分區名稱都有中文、預覽比對檔案內容）並更新分區名稱；`test_creature_screens_v5.py` 加 1 個（每句說明都有中文、中文介面拿到中文說明），預覽測試加「開始選單旁邊是不透明、不是黑的野外」。
- 戰鬥預覽時間與逐像素比對：AsteriaEmerald（私人專案，只在本機暫存）。
- 截圖（Cocoa，中英文）：生物畫面頁的開始選單、商店、戰鬥（Full Verification demo），遊戲資料夾設定，放在 `docs/audits/evidence/ui_plan2/d80/`（含 `checks.json`）。AsteriaEmerald 的生物畫面頁截圖只在本機。

**還沒做或已知的限制：**
- Full Verification demo 不是生物戰鬥的專案，生物戰鬥預覽畫不出來（狀態列顯示原因）；改動前就一樣。repo 裡沒有可以測生物戰鬥預覽的專案，速度與像素是在 AsteriaEmerald 上驗證的。
- 遊戲資料夾設定的每個設定仍沒有逐項說明（這個檔案沒有對應的說明文字可取）。
- 復原標籤「Game Folder Settings」和其他復原標籤一樣沒有翻譯。

**狀態：** 已提交。

## D81 — 資料表單的說明只在滑鼠移上去時顯示（2026-10-25）

**使用者要求：** 看到技能表單「說明 ⓘ」底下印著「Shown to players in menus.」，問 Description 要寫什麼，接著說：「description 或者其他的那種驚嘆號說明文，都改成使用者滑鼠移到那個上面會顯示、移開就沒有的那種，不用直接顯示在 GUI 上面。」

**回答：** Description 是給玩家看的說明。戰鬥中游標停在這個技能上時，顯示在說明列（`battle_commands.py` 的 `detail=game.description_of(...)`），可以用 `data.ability.<id>.description` 翻譯。

**做了什麼（`editor/record_form.py`）：**
- 欄位的說明不再印在欄位底下或表格上方，只在標籤上的 ⓘ 提示裡出現（滑鼠移上去顯示，移開就消失；欄位本身也有同一個提示）。提示照樣跟著介面語言翻譯。
- 分區標題旁的說明（例如「基本」旁的「技能與攻擊：目標、消耗、命中與效果」）也改成標題後面一個 ⓘ，滑鼠移上去才顯示。
- 表單因此變短，一個畫面看得到更多欄位。其他頁面沒有用 ⓘ 說明，不受影響。

**驗證：**
- 新測試 `test_record_form.py::test_help_shows_on_hover_only`：技能表單裡找不到說明文字的標籤，「Description ⓘ」的提示以說明開頭，分區的 ⓘ 有分區說明。
- 截圖（Cocoa，中英文）：`docs/audits/evidence/hover_help/editor_skill_en.png`、`editor_skill_zh.png`。提示是獨立的小視窗，截圖拍不到，靠測試確認。

**還沒做或已知的限制：**
- 生物畫面頁（D78）選中設定時，樹下方仍會顯示該設定的說明（那不是 ⓘ 說明，而是選中項目的說明欄）；要不要也改成只用滑鼠提示，等使用者決定。

**狀態：** 已提交。


## D82 — 綠寶石的開場與標題畫面照原作：Lotad 出球、男女滑入、整段博士演說、烈空坐標標題、主選單（2026-10-25）

**使用者要求：** 「沒有做那個 從寶可夢出來的動畫 開頭動畫裡面 然後 選男生女生 右邊的動畫也要跟著改」，接著「把開頭列空座的也做好 做成一模一樣」。開場影片（GAME FREAK、腳踏車）之後另外做。

**引擎（通用，編輯器拿得到）：**
- **圖片**（`SHOW_PICTURE` / `MOVE_PICTURE`，圖片指令對話框都有欄位）：
  - `tint` + `tint_color`：和一個顏色混合（0＝原色，1＝全是那個顏色），可以補間；出球時的粉紅、畫面閃白、變暗都用它。
  - `MOVE_PICTURE` 的 `delay`：幾秒後才開始（先一個立即的 MOVE、再一個延後的 MOVE，就能一個接一個）。
  - `frame_rate`（每秒幾格，從 `frame` 開始輪播）與 `frame_loop`（關掉＝播一次停在最後一格）。
  - `scroll_x` / `scroll_y`（內容每秒移動幾個圖片像素，捲出去的從另一邊回來）與 `wave_amplitude` / `wave_length` / `wave_speed`（每一列左右偏移的正弦波，GBA 的掃描線波動）。
  - `blend`：`add`＝顏色乘上不透明度後加到下面（GBA 的加法混色，發光）。
  - **文字圖片**：`text`（沒有圖片，畫文字；`\V[...]` 每次畫的時候帶入）、`font`（點陣字型 id，空的＝訊息視窗的字型）、`text_color`、`shadow_color`、`text_align`（x 是左端、右端或中間）。
- **選項的 hover 指令**：`CHOICE` 每個選項可以有 `hover`（游標移到這個選項時執行的世界指令清單）；選項對話框的「游標移到選項時」欄位。
- **訊息視窗**：
  - 選項框等提問的字打完才出現、才接受按鍵（`dialogue.choice_after_text`，預設開；GBA 的 menu.c 也是這樣）。
  - 不等按鍵的句子（`wait=False`）之後，同樣的句子再等按鍵時不再重打一次。
  - 超過兩行的句子會往上捲（原作的 `\l`）；之前第三行根本不會顯示（例如「at times as cooperative workmates.」）。
- **標題畫面可以是一個事件程式**：遊戲資料夾設定的 `title_screen.program`（編輯器：執行 ▸ 遊戲資料夾設定…，「Title screen program」分區）。
  - 標題時只跑這個程式和它的圖片（沒有場景、共通、計時事件）。如果有存檔，它在最新的存檔裡跑（文字可以顯示那個存檔的名字、時間、徽章）。
  - 世界指令 `TITLE_COMMAND`：`action` 是 `new_game`、`continue`（重新讀入最新存檔）、`load`（存檔欄）、`screen`（單獨開遊戲選單的一個畫面，例如 `options`，離開就回到標題）、`quit`。
  - 標題程式在跑的時候，Esc 不會關掉遊戲（程式自己用這個鍵）。
- **條件**：`rpg` `pressed:<動作>` / `held:<動作>`（這一幀剛按下／按住；`a|b`＝其中一個）、`rpg` `saves`（有幾格存檔）。
- **`WAIT` 同時給 `until` 和 `seconds`**：條件成立或時間到，先到的那個結束（等待指令對話框的「直到條件成立，最多等候秒數」）。
- **訊息的內建字**：`\V[play.time]`（遊玩時間 `h:mm`）、`\V[creatures.owned]`（擁有過的生物種數）；同名變數優先。
- **生物選單**：`CreatureMenuScreen.open_alone(screen)`：單獨開一個畫面，離開時整個選單關掉。

**私人的綠寶石專案（`local_reference/AsteriaEmerald`，不進 git）：**
- **Birch 的演說照 main_menu.c 演出：**
  - 開始時平台是暗的，216 幀後博士淡入（176 幀），平台的燈一格一格亮起來（`bg2.pal` 的 9 個階段做成 9 列的圖）。
  - 「This is what we call a POKéMON.」打完停頓時，精靈球（112, 58）在 32 幀後打開：SE_BALL_OPEN、16 顆星形粒子往 8 個方向散開、背景閃白 8+8 幀。Lotad 從球的顏色（粉紅）變回原色，從 0x28/0x100 長大，用 32 幀飛到 (100, 75)，中途往左上拱起 32 像素；到了就叫一聲、播兩格動畫。
  - 「And you are?」之後博士和 Lotad 淡出，平台暗掉並往右滑 60 像素，再淡入男主角。
  - 男女選單：游標一動，原本的角色往右移並淡出（17 幀），新的從 x=240 滑到 180 並淡入。
  - 名字之後博士和 Lotad 回來，最後主角縮小、往下移、背景變黑、主角變白，然後接卡車。
- **標題畫面照 title_screen.c**：白色淡入，POKéMON 標誌閃三次（一次、兩道快的加背景閃、一次加背景閃），EMERALD VERSION 一邊下滑一邊混入，標誌上移，然後烈空坐標（花紋每 4 幀變色）、雲（6/16 加法混色、每 4 幀往上 1 像素、每列波動 4 像素）、PRESS START 每 16 幀閃一次、版權。A／B／START 跳過開頭，A／START 白色淡出到主選單；曲子（MUS_TITLE，新算出來的）結束就從頭再來（原作這裡會播開場影片）。
- **主選單照 main_menu.c**：沒有存檔時是 NEW GAME、OPTION；有存檔時是 CONTINUE（玩家名字、時間、拿到圖鑑後的圖鑑數、徽章數，男生藍字、女生粉紅字）、NEW GAME、OPTION。沒選中的視窗變暗（BLDY 7）。A 是選擇音效加黑色淡出，B 回標題，OPTION 開設定畫面、離開回主選單。
- 所有圖片都由 checkout 的圖塊、圖塊地圖、調色盤算出來（標誌是 8bpp 仿射圖層；調色盤是標誌的 224 色加上 `rayquaza_and_clouds.pal` 當第 14 組）。

**測試：**
- `tests/test_choice_hover_and_tint.py`（8 項）：hover、選項對話框寫出 hover、混色與補間、延後的 MOVE、輪播與只播一次、捲動與波動（含加法混色的設定）、場景畫出捲動。
- `tests/test_title_program.py`（6 項）：TITLE_COMMAND 與按鍵條件、標題程式跑完後開新遊戲且 Esc 不關遊戲、讀檔與單獨開的設定畫面回到標題、文字圖片帶入變數、遊玩時間與擁有數、WAIT 條件或時間先到者。
- `tests/test_picture_command_dialog.py` 更新 MOVE 的欄位。

**實機證據（Cocoa 960×640、`ASTERIA_MUTE=1`，私人專案只在本機）：**
- `intro_live_check.py` 29/29：暗平台、博士淡入、燈亮、球、打開（粉紅小 Lotad、閃白、粒子）、弧線、就位、平台滑開、男生右移淡出後女生滑入、提問打完才出選單、名字、博士回來、縮小。
- `title_live_check.py` 16/16：白色淡入、閃光、背景閃、版本字混入、烈空坐標畫面、沒存檔的主選單、OPTION 亮起與設定畫面、回到主選單、B 回標題、有存檔的 CONTINUE（名字、時間、徽章）、繼續進入存檔的場景。
- 回歸：劇情 43/43、第一道館、拳頭徽章 23/23、選單、基礎、畫面 13/13 全部通過（提問要打完才出選單之後，檢查腳本改成等選單出現再按）。

**還沒做或已知的限制：**
- 開場影片（intro.c：GAME FREAK、腳踏車）還沒做；標題曲結束後從標題重來。
- Lotad 的 ANIM_V_SQUISH_AND_BOUNCE（只有垂直方向的壓扁）沒做，圖片只能等比縮放。
- 標誌閃光是預先算好的動畫格（原作是 OBJ 視窗＋亮度），每幀結果相同。
- 原作有 MYSTERY GIFT／MYSTERY EVENTS 的主選單版本，沒做（沒有對應的系統）。
- 主角變白時，原作的訊息視窗跟背景一起變黑；這裡訊息視窗在最後一頁按鍵後就消失。

**狀態：** 已提交。

## D83 — 滑鼠提示更快出現（2026-10-25）

**使用者要求：** D81 把說明改成 ⓘ 的滑鼠提示後，說「驚嘆號形式詞延遲太久才出現了」。

**做了什麼（`editor/theme.py`）：** 編輯器的樣式外面包一層 `QProxyStyle`（`_quick_tooltips`），把 Qt 的提示等待時間（`SH_ToolTip_WakeUpDelay`，原本 700 ms）改成 `TOOLTIP_DELAY_MS` = 120 ms。整個編輯器的滑鼠提示都一樣快，不只 ⓘ。換配色時重新套用主題不會再包一層。

**驗證：**
- 新測試 `test_theme.py::test_tooltips_show_quickly_and_the_theme_can_be_applied_again`。
- Cocoa 真實視窗：等待時間讀回 120（沒包時是 700）；技能表單包與不包各拍一次中英文截圖，逐像素比對只差一個輸入框的焦點框（約 1000 像素，焦點動畫的時間點不同），版面與顏色沒有變。

**限制：** 延遲是固定值，編輯器沒有設定可以改；要的話可以加到偏好設定。

**狀態：** 已提交。

## D84 — 提示貼著 ⓘ、復原／重做按鈕、技能樹不列圖表位置、標題對齊（2026-10-25）

**使用者要求（同一輪三句）：**
- 「提示字距離驚嘆號太遠了」
- 「不要有下面那句話……就直接做一個 redo、一個 undo 就好」「全部的這些都拿掉」（指頁面底部的「Changes apply as you edit · Ctrl+Z undoes」）
- 指著技能樹表單的「More fields ▸ Positions in the graph view（No positions yet. ＋ Add position）」：「這個是啥、為何不使用、然後這排版有問題」

**做了什麼：**
- **提示貼著 ⓘ（`record_form._HelpTip`）：** 原本欄位本身也掛著同一個說明，滑鼠在表格裡任何地方都會跳出提示，而且出現在游標下方，離 ⓘ 很遠。現在說明只掛在標籤上，提示固定出現在 ⓘ 右邊、和標籤同高，不管滑鼠從標籤哪裡進來；Qt 自己加的游標偏移被移回去。分區標題的 ⓘ 也一樣。
- **復原／重做按鈕（新檔 `editor/undo_buttons.py`）：** 遊戲資料、遊戲系統、遊戲開始三個頁面底部那句話都拿掉，換成「復原」「重做」兩個按鈕（新畫的箭頭圖示，和旁邊「複製…」同樣式）。按鈕執行視窗本來的 編輯 ▸ 復原／重做（同一步、同樣的重新整理），能不能按跟著那兩個動作一起變；不在編輯器視窗裡時是灰的。那句話的樣式與翻譯一併刪掉。
- **技能樹的「Positions in the graph view」：** 這是技能樹每個節點在圖表檢視裡的位置（`node_positions`），由圖表檢視拖曳節點再按「儲存圖表版面」寫入；沒存過時圖表自動排列，所以清單是空的。它不該在表單裡手打，表單不再列出它（`OWN_VIEW_KEYS`），存檔時原本的位置照樣保留。
- **排版：** 表單裡清單類的欄位，標籤現在對齊清單的第一行（「還沒有…」那行小字），不再對齊一個看不見的輸入框高度而往下歪。
- **名稱和 Internal ID 那行對齊（使用者：「這個 BP 跟下面的 internal id 那行字可以對齊嗎，幫我把全部這種寫法的都改成對齊」）：** 原因是 Qt 的規則：樣式表給標籤 `padding` 時，Qt 把它算成邊框寬度，縮排設定 -1 的標籤就會自動內縮半個「x」寬（18px 粗體約 5 像素）。現在全域 `QLabel` 規則加 `qproperty-indent: 0`，所有有 padding 的標籤都不再偷偷內縮：表單標題對齊 Internal ID 那行，欄位標籤（例如 Shop ID、Name）對齊下面輸入框的左緣，頁面標題（例如「Battle Resources · 4 records」）對齊篩選框，面板標題離圖示近一點。沒有任何地方自己設過縮排。

**驗證：**
- 測試：`test_undo_buttons.py`（2：按鈕跟著視窗的動作並執行；三個頁面都不再有那句話）、`test_record_form.py` 加 2 個（提示由標籤處理而不是游標、技能樹不列圖表位置）、`test_theme.py` 加 1 個（有 padding 的標籤縮排是 0）。
- Cocoa 真實視窗：標題「BP」的第一個像素和 Internal ID 那行只差 1 像素（字形本身），修改前差 11 像素（Retina 下）；四個頁面修改前後的差異逐一看過，全部是標籤少了那段內縮（`label_indent_before_after.png`、`title_align_before.png`／`title_align_after.png`）。
- Cocoa 真實視窗：提示視窗的位置讀回來：標籤右緣 x=724、頂端 y=385，提示在 (729, 381)，中英文都一樣；修改前在游標下方 36 像素。截圖 `docs/audits/evidence/undo_buttons/`（提示貼著 ⓘ 的合成圖、技能樹清單檢視底部的復原／重做按鈕，中英文）。

**還沒做或已知的限制：**
- 提示位置的截圖是把提示視窗貼回主視窗合成的（系統截圖沒有權限），位置以讀回的座標為準。
- 復原／重做按鈕的提示文字（例如「Undo Rename」）和 編輯 選單一樣，動作名稱沒有翻譯。

**狀態：** 已提交。


## D85 — 滑鼠操作：選單、對話、戰鬥都能用滑鼠，作者可在編輯器關掉（2026-10-26）

**使用者要求：** 「開始做滑鼠操作：所有選單、對話、戰鬥都能用滑鼠，作者可以在編輯器開關」。

**做了什麼：**
- **指標層（新檔 `runtime/pointer.py`）：** 每個畫面在畫的時候標出滑鼠能指的地方（`rt.hotspot(rect, pick, key=)`）；下一幀把滑鼠事件換成鍵盤會做的事：
  - 移到一列上：執行 `pick`（游標移過去）；
  - 左鍵：`pick` 後按下那一列的鍵（預設 Enter）；
  - 右鍵：Esc（返回／取消；地圖上打開選單）；
  - 滾輪：上／下（只在有可指區域的畫面）。
  按鍵是真的 pygame 按鍵事件，同時進入輸入對應（`confirm`／`cancel` 按住一幀後放開）和讀按鍵事件的畫面，所以每個畫面對滑鼠的反應就是它對鍵盤的反應。連續快速點擊不會在同一幀放開又按下（會被當成一次長按），第二下延到下一幀。沒點到任何區域的點擊原樣傳下去（圖片、地圖人物的點擊事件照舊）。
- **有標出可指區域的畫面：**
  - 標題（New Game／Load Game＝N／L 鍵）、暫停、遊戲結束、設定（含數值左右箭頭）、按鍵設定、狀態（分頁、下一位隊員、各列）、存讀檔、任務／成就／圖鑑（滾輪捲動）、商店（列、買／賣分頁）。
  - 對話：一行字時點畫面任何地方繼續；選項逐一可指可點（含遊戲自己的選項框）；選項以外的點擊被吃掉，不會點到地圖。
  - 戰鬥：指令選單各列、分類列（Tab）、選目標時直接指敵人；捕捉／換人／學招的編號列；勝利畫面點一下翻頁。
  - 寶可夢式戰鬥（240×160 放大）：FIGHT／BAG／PARTY／RUN、招式、是／否、隊伍格與 CANCEL、背包列與口袋箭頭、訊息時點一下繼續。
  - 背包格、裝備人偶與候選清單、強化分頁與清單、任務板卡片、招募列、扭蛋按鈕與結果、製作分頁與配方、寵物（兩欄都可）、訊息紀錄、音樂室、製作人員、技能欄位。
  - 寶可夢式開始選單、隊伍、背包、選項、圖鑑、存檔是／否；商店選單、商品、數量框（滾輪調數量）、是／否；取名鍵盤的每個字與 PAGE／BACK／OK；圖片選項。小畫面的區域由 `pointer.hand_over` 換算到視窗座標。
- **不轉右鍵的地方：** 引擎自己的標題（Esc 會關遊戲）和技能樹（右鍵拖曳圖表）。技能樹本來的滑鼠操作不變。
- **作者開關：** `InputActionMap.mouse`（預設開；關掉時專案檔寫 `"mouse": false`，開著時不寫，舊專案不變）。編輯器 呈現 ▸ Controls 上方有「滑鼠操作」勾選框（復原／重做），說明只在 ⓘ 的滑鼠提示裡；玩家自己的按鍵設定保留這個開關。

**驗證：**
- `tests/test_mouse_control.py`（23 項）：指標層（點擊變按鍵並放開、沒點到時原樣傳下、右鍵＝Esc、關掉時不轉、滾輪、快速連點）、開關存檔、暫停選單、對話與選項、經典戰鬥（指令、選目標、右鍵返回）、寶可夢式戰鬥（指令、招式、隊伍、CANCEL）、11 個選單畫面都有可指區域且指過去不會出錯、存檔列／設定列／裝備人偶的游標、標題、寶可夢式選單／商店／取名、編輯器勾選框（復原、存檔、中文）。
- Cocoa 真實視窗（Full Verification，960×640，`ASTERIA_MUTE=1`，事件經過視窗自己的佇列 `rt.step`）：英文、中文各 10/10——點 New Game 進地圖、右鍵打開選單、指到「設定」游標跟著移、點下打開設定、右鍵返回兩次回到地圖、戰鬥指令指到第二列游標跟著移、點下打開。截圖 `docs/audits/evidence/mouse_control/`。

**後續修正（使用者：「幫我把剩下的問題修好」）：**
- **按鍵設定：** 等待新按鍵時，滑鼠換出來的按鍵不會被綁上去；右鍵仍等於 Esc，取消等待；等待時指到別列也不會移動游標。
- **太長的選單會捲動：** 暫停／遊戲結束這類疊加選單超過視窗高度時，只畫放得下的列，標題旁顯示「n/總數」。游標離開看得到的範圍才捲動，所以滑鼠指著的那一列不會被捲走。Full Verification 的暫停選單 19 項，「結束遊戲」現在看得到（滾輪也到得了）。
- **滑鼠提示：** 玩家動過滑鼠後，有可指區域的畫面右下角會出現「點擊：選擇   右鍵：返回」；按任何鍵就消失，只用鍵盤的玩家永遠看不到。新的內建文字鍵是 `hint.mouse`（英文、zh-TW、Full Verification 的中文表、`docs/BUILT_IN_TEXT_KEYS.md`）。作者把這段文字設成空白就不顯示。
- **點地圖走過去：** 新增 `InputActionMap.click_move`，預設關，打開時才寫進專案檔 `"click_move": true`。編輯器 Controls 上方「滑鼠操作」旁邊有「點擊移動」勾選框，附 ⓘ 提示與復原；滑鼠操作關掉時這個框會變灰。
  - 打開後，地圖上的左鍵如果沒點到圖片、人物或選單，主角就沿 `find_path`（A*，會繞過圖塊牆、實體碰撞與地圖規則）走過去；格子移動的地圖用 `field.grid_size` 當路徑格。
  - 走路的方式是每幀把方向交給原本的移動程式，所以碰撞、門與觸發都照舊。
  - 按方向鍵、換地圖或事件開始，都會停下；卡住 0.4 秒也會停下。
- **圖鑑固定游標列：** 這是刻意保留的 Emerald 行為。點一列時，選到的就是點的那一項；之後清單會捲回固定列。指標只在進入「新的一格」時才換選擇，所以不會一直跳。

**驗證（後續修正）：**
- `tests/test_mouse_control.py` 從 23 項增加到 29 項：
  - 等待按鍵時的點擊與右鍵；
  - 長選單捲動，以及指著的列不被捲走；
  - 滑鼠提示的出現與消失、中文；
  - `click_move` 存檔；
  - 點地圖走到目的地，按鍵接手；
  - 編輯器勾選框（存檔、變灰、復原、中文）。
- Cocoa 真實視窗（Full Verification 960×640），英文、中文各 7/7：
  - 滾輪到「結束遊戲」，且它在畫面內；
  - 提示出現；
  - 點設定；
  - 等待按鍵時點擊沒被綁上、右鍵取消；
  - 點地圖後主角從 x=608 走到 x≈655（目標 656）。
- 全套測試：3499 通過、1 略過、1 失敗。失敗的是 `test_built_in_text` 的暫停選單測試：19 列的選單在 540 高的視窗裡會捲動（這批的預期行為），所以把該測試的視窗高度設成 900，讓每列都畫得出來，修完後通過。
- 截圖：`en_／zh_07`～`10`。編輯器的 `controls_en／zh_TW.png` 重拍，已含「點擊移動」。

**收尾（使用者：「把剩下的做完後 commit push」）：**
- **點人物＝走過去說話：** 點擊移動打開時，點在可對話人物（`action` 觸發、有事件）上 16 單位內，主角會沿路走到它的對話範圍內，轉向它，再按一次互動鍵，和自己按鍵的效果一樣。
  - 找路時把那個人物自己的碰撞排除，因為它就是目的地；已經在範圍內就直接說話。
  - 有 `click` 觸發的人物照舊執行自己的點擊事件。
- **動作場景與連線遊戲：**
  - 從上方看的動作場景（`CharacterController2DComponent.mode` 不是 `platformer`）也能點擊移動：路徑方向換成這一幀的 move_left／right／up／down 輸入，交給原本的控制器，所以碰撞、閃避、技能都照舊。
  - 橫向平台場景不用點擊移動，因為那裡的主角要跳。
  - 連線遊戲的方向一樣交給預測與送出的輸入；點人物說話會送出互動輸入。

**驗證（收尾）：**
- `tests/test_mouse_control.py` 增加到 31 項：
  - 點人物後走過去，事件開始，面向它，停在範圍內；
  - 從上方看的動作場景可以點擊移動，平台場景不行。
- 原本的點擊移動測試改成往人物的反方向點，因為點在人物旁邊現在會去說話。
- Cocoa 真實視窗（ARPG 示範的城鎮，動作場景，960×540）3/3：
  - 是從上方看的動作場景；
  - 點地面後從 (312,200) 走到 (374.4,200)，目標 376；
  - 點「Brann the Smith」，走過去後對話框出現。
- 全套測試：3502 通過、1 略過。
- 截圖：`en_11_arpg_click_walking.png`、`en_12_arpg_click_figure_talks.png`。這個示範沒有中文語系，所以只拍英文。

**還沒做或已知的限制：**
- 連線遊戲的路徑是用本機的地圖算的，伺服器擋住時會在 0.4 秒後停下。這部分只有程式碼路徑，沒有連線實機測試。

**狀態：** 已提交。

---

## D86 — 給遊戲作者的完整使用手冊（中英文，2026-10-26）

**使用者要求（由主工作階段轉交）：** 為遊戲作者寫一份完整、詳細的使用手冊，繁體中文與英文各一份，附真實截圖；最後一章是從原始碼產生的 Python API 清單。

**做了什麼：**
- **兩份手冊：** `docs/manual/USER_MANUAL.zh-TW.md` 與 `docs/manual/USER_MANUAL.en.md`，內容相同，15 章：
  1. Asteria 是什麼；2. 安裝與啟動（`.venv/bin/python`）；3. 專案；4. 編輯器視窗（工作區、面板、分頁）；
  5. 地圖與場景；6. 事件與事件程式（含程式碼工作區）；7. 資料庫；8. 戰鬥（傳統、戰鬥畫面、生物、即時）；
  9. 選單與版面畫布；10. 對話與選項；11. 輸入（含 D85 的滑鼠操作與點擊移動）；
  12. 翻譯（編輯器 檢視 ▸ 語言、遊戲 `game.tr` 與內建鍵）；13. 試玩、存檔、匯出（含網頁版）；
  14. 四個參考專案；15. 給作者的 Python API。
- **介面名稱都對過：** 中文版的每個介面字都用 `i18n.translate` 與 `zh_TW.json` 查過，再對照中文截圖；目前仍是英文的地方照實寫（見下方限制）。
- **截圖（`docs/manual/images/`，119 張，約 11 MB）：**
  - 編輯器：Cocoa 真實視窗開 Full Verification，1440×900，先英文再用 `set_language('zh_TW')` 切中文，每個畫面中英各一張（場景、遊戲資料各類別、遊戲系統、遊戲開始、戰鬥規則、戰鬥畫面、選單版面、操作、三個事件分頁、程式碼、對話框、六個選單）。
  - 遊戲：`PlayableTestRuntime` 的真實畫格，中英各一套（標題、地圖、暫停、設定、按鍵設定、存檔、狀態、背包、技能樹、裝備、商店、任務、戰鬥、遊戲結束、製作、寵物、對話、選項），加上 D85 的滑鼠畫面、生物戰鬥、破防／加速戰鬥、ARPG 城鎮。
- **API 產生器（新檔 `scripts/manual_api_list.py`）：** 列出 14 組常用 API（專案載入、遊戲視窗、地圖與移動、事件與對話、翻譯、隊伍、道具、任務、戰鬥、寵物、輸入、程式碼工作區、事件程式資料、匯出），簽名用 `inspect` 從真實程式碼取得（省略型別註記），再加上事件 opcode 表與 83 個世界指令的參數（`WORLD_COMMAND_ARGUMENTS`）。寫在兩份手冊的 `<!-- BEGIN API … -->`／`<!-- END API -->` 之間；`--check` 在過期時回傳 1。
- **索引：** `docs/ENGINE_HANDBOOK.md` 開頭加上手冊連結，並新增「D86 新增」表格。

**驗證：**
- `tests/test_user_manual.py`（4 項，全過）：API 章節與程式碼一致；每個 API 目標都解析得到；兩份手冊的每張圖都存在且數量相同（各 67 張）；目錄連結都指到真的標題。
- `scripts/manual_api_list.py --check`：「API chapters match the code」。
- `ruff format`、`ruff check --select E501`、`ruff check` 對兩個新 .py 檔都通過。
- 截圖逐張看過；編輯器截圖腳本 70 張無錯誤；生物戰鬥實機檢查 31 步通過。

**還沒做或已知的限制（介面本身的缺口，手冊照實描述，沒有在這批修）：**
- 「匯出遊戲」與「新專案」（從範本）對話框在中文介面仍是英文。
- 程式碼工作區的「Run」按鈕與演出的「Skeleton」分頁沒有翻譯。
- 戰鬥畫面頁的 Menu Layout、Bitmap Font、Dialogue Window、Creature Screen 類別名稱，以及事件觸發值 Action／Autorun／Parallel 在中文介面仍是英文。
- 遊戲系統 ▸ 翻譯頁把說明文字直接印在表單上，沒有只放在 ⓘ 提示裡。
- 手冊是 Markdown；沒有做 PDF 或網頁版。

**狀態：** 已提交。

## D87 — 選單塞進小視窗、人物用腳擋路、走路跟上移動、暫停選單分頁、能力值表格（2026-10-26）

**使用者回報（由主工作階段轉交，加上使用者直接留言）：** FV 示範在 960×540 的視窗裡，星落寶箱的提示壓到「抽 1 次」、按鈕與機率框被切掉；主角穿過 NPC 與房子；地圖下方的「Field Test」提示框擋住整排 NPC；戰士走路腳幾乎沒動、畫面卻移動很快。使用者再補：裝備畫面也被切掉，「被截掉的問題 GUI 需要自己處理」；暫停選單的「狀態／道具／裝備／技能」和另外的裝備、技能重複，應該各自一項；沒有能力值加點，要做成楓之谷那種表格；道具要自己一頁，能分類、能篩選；以上都要能在編輯器設定。

**原因（逐一查證）：**
- 選單畫面（裝備、強化、製作、商店、懸賞板、公會、寶箱、狀態、任務、背包、寵物…）的版面是照 1280×720 寫死的常數，試玩視窗預設 960×540，右邊與下面就超出去。
- 地圖行走（非動作場景，`field_ui._field_input`）只拿一個點去撞牆，身體可以滑進別人身體一半；房子、名人堂牌、勝利旗、舊寶藏、封印寶庫、草叢沒有碰撞框。
- Lucifer 戰士的圖格底下有 8 列透明，樞紐在圖格底邊，所以畫出來比站的位置高 8 px，排序與「站在屋頂上」都錯。
- 走路動畫照時鐘播（8 格 × 0.1 秒），步幅約 24 px，但每秒走 64 px：一圈動畫走了 51 px，腳在地上滑。
- 提示框蓋住畫面最下面 92 px，鏡頭卻當作整個視窗都看得到。

**做了什麼（引擎通用，作者都能在編輯器改）：**
- **選單自動縮進視窗**（新檔 `runtime/playtest/menu_fit.py`）：清單裡的選單畫面在視窗比設計尺寸小時，畫在同比例、至少設計尺寸的畫布上，再平滑縮進視窗；這一幀標的滑鼠區域一起縮放，點到的就是看到的；後面的地圖／戰鬥直接畫在視窗上（`window_drawing`）。設計尺寸是 `render.menu_size`（遊戲資料夾設定 ▸ Rendering，預設 `[1280, 720]`，`[0, 0]` 關掉）。技能樹自己讀滑鼠位置，不縮。
- **寶箱畫面**依畫面大小排版（`service_screens.gacha_places`），按鈕固定在下方、提示在按鈕下面。
- **用腳的碰撞框擋路**（`collision.feet_box`／`box_blocked`）：有實心 Collider2D 的角色用框的四角、邊中點與中心去測，沒有框就照舊用一點。
- **走路照距離播**（`Animator2D` v2 的 `stride`「Walk Stride」，編輯器 Inspector 可改）：大於 0 時，走一個步幅播完整個走路動畫；0 照舊用時間。走路速度改成遊戲資料夾設定 `field.walk_speed`（預設 36／磁磚地圖 64，跟以前一樣）。
- **站在腳上**（`character_placement.feet_pivot_y`）：算出整張圖格裡最低的不透明列，當作樞紐高度。
- **提示框不擋地圖**（`TileSceneView.inset_bottom`）：試玩提示框顯示時，鏡頭把最下面 92 px 當作看不到，地圖的最後幾排會捲到提示框上面。
- **暫停選單分頁**（新檔 `rpg/menu_rules.py`、`runtime/playtest/menu_pages.py`）：狀態、道具、裝備、技能各自一項。裝備開紙娃娃畫面；技能有技能樹就開技能樹（關掉回到暫停選單），沒有就開技能清單；狀態、道具是單獨一頁、沒有分頁列。`PAUSE_WORDS` 列出全部內建項目，遊戲用不到的（沒寵物就沒「寵物」…）自動不顯示。
- **能力值表格（狀態頁）**：左上是角色（名字、等級、職業、經驗值、HP／MP 條），左下是「能力點數」：剩餘點數，加上能力成長圖每個節點一列（名稱、目前數值、等級／上限、綠色 +）；Enter、→ 鍵或點 + 加 1 點（`game.allocate_progression`），點數不夠或已滿時說明原因。右邊是「詳細能力」兩欄表格。
- **道具頁分類與篩選**：上方是分類分頁（左右鍵、Tab、點選），右上是篩選（F 或點選，循環：無 → 每個篩選 → 無）。每個道具除了自己的標籤，還帶 `item` 或 `equipment`。沒設定時：全部／道具／裝備，篩選是「可使用」。
- **編輯器：遊戲系統 ▸ 選單頁面（Menu Pages）**：暫停選單項目與順序（勾選＋拖曳）、能力點數加在哪張成長圖（空白＝標籤 attributes 的那張，`-`＝不顯示 +）、詳細能力列與順序、道具頁分類表（ID、名稱、標籤、圖示）、篩選表（ID、名稱、標籤、只留可使用）。資料翻譯（D60）新增「資料：選單頁面」群組（`data.item_category.<id>.name`、`data.item_filter.<id>.name`）。
- **狀態選單技能頁**顯示技能名稱而不是 id（`attack_ring`），裝備頁的部位用 `game.slot_name`。
- **新內建字**：`pause.items`、`pause.skills`、`status.profile`、`status.ability_points`、`status.details`、`status.items.*`、`status.filter*`、`status.hint.*`、`status.raised`、`status.cannot_raise`、`status.reason.max_rank`／`no_points`…；`pause.status` 改為「Status／狀態」。`docs/BUILT_IN_TEXT_KEYS.md` 已重產。

**FV 示範資料**（`build_project.py` 已無法重現現有資料，所以用 `trial_d87.py` 修補，可重複執行；原始碼 `trial_maps.py`、`trial_home.py`、`trial_world.py`、`trial_story.py`、`trial_systems.py`、`trial_content.py` 同步改好）：
- 50 張人物圖格的樞紐改在腳底（戰士 0.8542）；所有 Animator2D 的 `stride` = 24；人的腳框寬 10 → 14。
- 房子（60×40，往上 22）、名人堂、勝利旗、舊寶藏、封印寶庫、草叢加上碰撞框。
- `field.walk_speed` = 48、`render.menu_size` = [1280, 720]。
- 選單頁面 `trial_menu`：能力點數加在 `attributes`；詳細能力 9 項；道具分類「全部、消耗品、投擲物、素材、武器、防具」；篩選「現在可用、藥水、獨特裝備」；中文翻譯；zh-TW 表補上引擎新字。
- `trial_ui_tour.py` 新增 `page_status`、`page_items`、`page_items_potions` 三個畫面。

**驗證：**
- 新測試 `tests/test_menu_pages.py`（10 項）、`tests/test_field_fit_d87.py`（9 項）。
- 全套測試：3525 passed、1 skipped（7 分 17 秒）；`ruff check`、`ruff format --check` 通過。使用手冊的 API 章節已重產（`open_status_menu` 多了 `page`）。
- 真實 Cocoa 視窗（`driver: cocoa`）960×540 的修改前（HEAD 的副本）／修改後截圖，中英各一套：`docs/audits/evidence/d87/before/`、`after/`。地圖（起點、房子、Mira、地圖底部、連續四格走路）與選單（寶箱四個畫面、裝備、強化四頁、製作五頁、懸賞板、公會、商店、任務、背包、寵物、狀態四頁、暫停、技能樹，以及新的狀態頁、道具頁）。
- 實測位置（`*_field.json`）：往上走進房子的牆，修改前停在 y=112.5（站在屋頂上），修改後停在 116（門前）；往左走進 Mira（x=88），修改前停在 93.3（身體疊在她身上），修改後停在 102.4（站在旁邊）。

**還沒做或已知的限制：**
- 技能樹不縮放（它自己讀滑鼠的拖曳與縮放）；在 960×540 下仍以視窗大小排版。
- FV 的道具都是戰鬥中使用（`battle_ability`），沒有 `use_effects`，所以「現在可用」篩選在選單裡是空的——這是資料本身，不是錯。
- 經驗值只顯示累積值，沒有「距下一級」，因為升級門檻是呼叫 `grant_actor_experience` 的人決定的。
- `build_project.py` 仍無法重現現有的 FV 資料（早就如此，這批沒有修）。

**狀態：** 已提交（a3eefc8c，未推送）。

## D88 — 每個物件都能設定穿越或阻擋、裝備圖示填滿格子、道具頁的詳細說明（2026-10-26）

**使用者回報：** 主角會穿過寶箱；「人物、道具、房子等等都要能夠設定穿越或者不穿越，不穿越就整個都不能」，參考 RPG Maker 的做法。裝備畫面的武器圖示要能放大到跟背景的武器框一樣，而且編輯器對應的地方要能設定、能預覽（圖示放上去的樣子、放大多少）。再補：物品、道具、裝備要能預覽，或者有看詳細的按鈕；道具頁按 Enter 會出現原始錯誤「cannot use card_acolyte_item on hero_01」。

**RPG Maker 怎麼做：** 地圖圖塊有通行設定（○ 可走、× 不可走、☆ 在角色上面）；事件有「穿越」(Through) 勾選與優先度（在角色下、與角色相同、在角色上），「與角色相同」時整格擋住。人站在一格上，所以「擋住」就是那一格。

**原因（查證）：**
- 寶箱、床、工作台、告示板只在腳下有一塊小碰撞框（或沒有），圖比框大很多，所以從旁邊可以走進圖裡。
- 裝備圖示畫成固定大小，不看格子大小；圖示四周有透明邊，放大後看起來還是小。
- 道具頁對每個道具都呼叫 `use_item`；沒打過仗的角色沒有 `actor_snapshots`，所以任何道具都會丟出原始錯誤；FV 的道具也沒有 `use_effects`（只有戰鬥用的 `battle_ability`）。
- 道具頁把背包裡的裝備列在 `return` 後面，永遠不會顯示。

**做了什麼（引擎通用，都能在編輯器設定）：**
- **通行設定**（新檔 `editor/passability.py`，Inspector 的「Passability／通行設定」區塊，任何有圖或有碰撞框的物件都有）：三種模式
  - 可穿越（Through）：沒有實心碰撞框（觸發框仍然會觸發事件）；
  - 腳下阻擋：實心框在腳下，大小在 Collider 2D 改（人物用這個，能站在前面、後面）；
  - 整張圖阻擋：碰撞框量成整張圖（所有圖格不透明像素的聯集，跟著左右翻轉），圖的任何地方都走不進去；有「重新量測圖片」按鈕（換圖之後用）。
  - 預覽：目前圖格放大，紅框是擋住玩家的範圍，藍色十字是站立點。一次切換是一個復原步驟。
- **`Collider2D.fit`**（v4，「Size From／大小來源」）：`custom` 照寫的寬高偏移，`picture` 表示框是從整張圖量出來的；舊資料遷移成 `custom`。`graphics/character_placement.picture_box` 算出框。
- **裝備格圖示**（`MenuSlotPlace` 新欄位，選單版面 ▸ 紙娃娃 ▸ 格位表新增四欄）：圖示大小（格子的倍數，0.1–4）、圖示旋轉（逆時針度數）、裁掉圖示空白邊（yes/no）、填滿方式（fit 保持比例／stretch 拉滿）。`resources.fitted_icon` 照這些畫；像素圖能整數倍就整數倍放大。選單版面的預覽會讓第一位成員每一格都穿上範例裝備，所以改了馬上看得到。
- **道具頁詳細說明**（遊戲系統 ▸ 選單頁面 ▸ `item_details`「Item Details／道具詳細」）：`panel` 清單右邊固定顯示，`button` 按「D 詳細」按鈕或 D 打開、Esc 關，`off` 不顯示。內容（`StatusMenu.detail()` → `ItemDetail`）：大圖示、名字（稀有度顏色）、類別、說明、資料表（持有數／上限、選單可用、戰鬥中的技能；裝備則是稀有度、部位、各項能力值、插槽）。
- **背包裡的裝備**出現在道具頁（武器、防具分頁），有圖示與詳細；按 Enter 說「請從『裝備』穿上」。
- **選單裡不能用的道具**（沒有 `use_effects`）不再呼叫 `use_item`，改說「{name} 無法在選單使用」。
- **`use_item` 修正**：沒打過仗的隊員先用基礎能力建立快照，再使用道具（以前直接丟錯）。
- **新內建字**：`status.item_info`、`status.details_button`、`status.hint.details`、`status.detail.count`、`status.detail.menu_use`、`status.detail.battle_use`、`status.detail.sockets`、`status.yes`、`status.wear_in_equipment`、`status.cannot_use_here`（英文＋繁中），`docs/BUILT_IN_TEXT_KEYS.md` 已重產；編輯器新字都有繁中。

**FV 示範資料**（`trial_d88.py`，可重跑）：
- 14 個物件改成整張圖阻擋：Roger's House、Hall of Heroes、Alchemy Table、Forge、Bounty Board、Starfall Chest、Old Cache、Sealed Vault、Victory Banner、Family Chest、Bed，以及墓碑、草叢等 `doodad:`。人物維持腳下阻擋。
- 裝備版面每一格 `icon_trim = yes`。
- 藥水類（Potion、Hi-Potion、Mega Potion、Ether、Hi-Ether、Elixir）加上選單用的效果（複製戰鬥效果的 HP／MP 回復），像 RPG Maker 一樣選單裡也能喝。
- 大部分道具加上說明（中英），zh-TW 表補上引擎新字。
- `trial_ui_tour.py` 新增 `page_items_gear`。

**驗證：**
- 新測試 `tests/test_passability_d88.py`（16 項）；`tests/test_menu_pages.py` 的「現在可用」篩選改成期望兩種藥水。
- 全套測試：3539 passed、1 skipped、2 failed（9 分 17 秒；兩個 FV 翻譯詞表測試：新的道具說明不在詞表裡）。修正方式：`trial_zh_words.DESCRIPTION` 讀入 `trial_d88.chinese()`；這兩個檔案加上 D88 與選單頁測試重跑 49 passed。`ruff check`、`ruff format` 通過；使用手冊 API 章節 `--check` 一致。
- 真實 Cocoa 視窗截圖（中英）：`docs/audits/evidence/d88/`。實測：從左往右走向星落寶箱，修改前走到 x=540（穿過兩個寶箱），修改後停在 472.8；房子的門照樣進得去。編輯器 Inspector 的通行設定（寶箱、房子＝整張圖阻擋；Mira＝腳下阻擋）與紙娃娃格位表的四個新欄位。

**還沒做或已知的限制：**
- 從下面走向寶箱時，腳停在寶箱下緣，但主角比寶箱高，頭會畫在寶箱前面（俯視角的前後關係，跟 RPG Maker 站在事件下一格一樣）。若要連主角的身體都不重疊，可以把主角自己的通行設定也改成「整張圖阻擋」。
- 選單裡喝藥水時，HP 已滿也會用掉（沿用 `use_inventory_item` 的規則）。
- 裝備沒有自己的說明文字（資料本身沒有），詳細面板只顯示能力值。
- 沒有說明的 FV 道具（鬧鐘、祝福卷軸、鳳凰種子…）面板只有名字與資料表。

**狀態：** 已提交（3c693d9c，與 D89 同一個提交，未推送）。

## D89 — 楓之谷式的能力值視窗：VIT 與 HP／MP 分開加點、來源拆開顯示、詳細屬性表格與一批新的戰鬥屬性（2026-10-26）

**使用者要求：** 能力值學楓之谷：VIT 點了提高防禦、魔防等相關能力；HP、MP 另外點，一點加 100、1000 這種量，其他能力一點加 1。每個能力要看得到「本身（升等、職業、加點）＋裝備」。詳細屬性不要擠成兩排，大分類（攻擊…）各一組；攻擊是浮動的所以顯示範圍；命中這類要顯示百分比。用好看的表格，整個能力值介面要更清楚。詳細屬性參考楓之谷，「無視防禦」改成「穿透」，用不到的不硬加；做我們自己的 BP 加成（每 BP 本來加 10% 技能效果，裝備、飾品可以提高）；不要移動速度，要行動速度（影響行動順序）、破防傷害、弱點傷害；再補上系統會用到的屬性，「盡可能複雜化 full verification」。追加：「我沒說的，我們系統用的所有相關的都可以寫出來。」

**做了什麼（引擎通用，都能在編輯器設定）：**
- **能力值表**（狀態頁左下，`menu_pages._draw_stat_table`）：每列一個加點節點，欄位是等級（已點／上限）、總計、基礎、加點、裝備、每點（再點一次加多少），最右邊是 ＋。數字來自 `GameSessionRuntime.stat_breakdown(actor_id)`：同一個角色解三次 build（完整；不含裝備；不含加點和裝備），所以「基礎」包含角色本身、職業、等級成長與被動，「加點」是能力點，「裝備」是裝備（含能力值公式的連帶，例如裝備給 1 STR 讓物攻 +2，這 2 算在裝備）。資源上限（HP、MP）也拆。
- **詳細屬性表**（狀態頁右邊，`_draw_stat_details`）：遊戲系統 ▸ 選單頁面新增兩個表格
  - `stat_groups`（Detail Table Groups／詳細表格分組）：分組 ID 與名稱，一組一個標題；
  - `stat_lines`（Detail Table Lines／詳細表格各行）：每行一個能力值、所屬分組、顯示方式 `number`／`percent`／`range`（上下 `spread`% 的最低～最高，攻擊浮動用）／`chance`（透過戰鬥判定 `check` 算出真正的機率：暴擊 = 5% + 0.3%×暴擊值、最高 65%；迴避 = 讓對手命中率少掉多少）、自訂名稱。
  - 分組由上往下排，放不下整組移到下一欄（一組不會被拆開）；有裝備加成的行在數值左邊用藍字寫（基礎＋加點 ＋裝備）。沒填 `stat_lines` 時照舊用 `stat_rows`，全部以數字顯示。
- **穿透**：`BattleSessionRules.penetration_stat`（General Battle Rules ▸ Penetration Stat／穿透能力值）：施放者這個能力值是百分比，傷害公式裡目標的能力值項（`TARGET_STAT`，例如 `-1 × 防禦`）只算 `1 − 穿透%`（`FormulaContext.target_stat_scale`，0～1）。對自己施放不受影響。
- 新內建字：`status.col.rank`／`total`／`base`／`points`／`gear`／`gain`（等級／總計／基礎／加點／裝備／每點），`docs/BUILT_IN_TEXT_KEYS.md` 已重產。編輯器新欄位都有繁中；Stat 下拉選單改用角色畫面的能力值名稱（以前沒有公式的能力值只顯示 id）。

**FV 示範資料**（`trial_d89.py`，可重跑）：
- 加點：STR、DEX、INT、LUK、**VIT**（一點 +1 體力；體力進防禦 ×1.5、魔防 ×1.0、異常抗性 ×0.5），**HP**（一點 +100，上限 50）、**MP**（一點 +30，上限 50）各自一列。各角色有 VIT 基礎值。
- 新屬性，每一個在戰鬥裡都有作用（互動規則，全部相乘）：
  - 穿透 %（無視目標防禦的比例）；
  - BP 加成 %：強化規則 `boost_power_1/2/3` 加上 `bp_bonus` 項；「每 BP 技能強化 %」= 100 + BP 加成（顯示用公式）；
  - 弱點傷害 %（所有 `outcome.weak` 規則）、破防傷害 %（`broken` 規則）、首領傷害 %（新規則，目標有 `boss` 標籤）、傷害 %（所有攻擊）、最終傷害 %（最後乘，優先度 −5）；
  - 異常抗性 %：所有壞狀態的命中率 −1%×異常抗性（`BattleStatePolicy.target_stat_terms`）；
  - 行動速度（原本的 speed，顯示名稱改成 Action Speed／行動速度，決定行動順序）。
- 傷害浮動 ±10%：`final_damage_expression = value * (0.9 + random() * 0.2)`，所以物攻、魔攻顯示成範圍。
- 裝備帶這些屬性：武器（穿透、傷害、弱點傷害）、飾品（BP 加成、首領、破防、異常抗性）、防具／頭／腿／腳（VIT、異常抗性、最終傷害）。
- 詳細表格五組：攻擊（物攻、魔攻＝範圍；傷害、最終傷害、首領傷害、穿透、暴擊率＝機率、暴擊傷害、吸血）、防禦（物防、魔防、迴避＝機率、異常抗性）、戰鬥（行動速度、命中＝機率、每 BP 技能強化、弱點傷害、破防傷害）、屬性攻擊、屬性抗性（各 7 屬性）。
- 英文名稱放在角色畫面的 `stat_labels`，中文在 zh-TW 表，詞表 `trial_zh_words` 讀入 `trial_d89.chinese()`；`trial_d87` 重跑時保留之後加的 `item_details`、`stat_groups`、`stat_lines`。
- 腳本戰役（`run_campaign.py`）：
  - 加點改成 HP（原本的 VIT 現在只加防禦）；
  - 不對「吸收某屬性」的敵人用那個屬性的技能（以前 Vesper 對吸收暗屬性的骷髏古王用暗屬性技能，替王補了兩萬多血）；
  - 打王前休息；
  - **輸了就讀取戰前存檔重打**（最多 3 次，`retries` 記錄）：戰鬥骰子由存檔的戰鬥次數決定，重打時骰子一樣，但隊伍的選擇不同。

**驗證：**
- 戰役是看運氣的：D89 之前用種子 1–7 只贏 3 場（2、5、7）；D89 的資料在修改戰役腳本前也是 3 場（1、2、4），英雄的能力值在 D89 全部相同或更高。修改後種子 1–10 贏 9 場（種子 7 三次都輸給骷髏古王：骰子固定），測試用的種子 5 重打 1 次後通關。
- 新測試 `tests/test_stat_window_d89.py`（10 項：四種顯示方式與機率、選單規則來回、編輯器表單來回與新增一行、繁中標籤、穿透比例、戰鬥規則來回、示範的能力值表、詳細分組、中文繪製）。更新期望：`test_menu_pages`（7 列加點：VIT、HP、MP）、`test_brave_archmage`（加點節點多了 attr_hp、attr_mp）、`test_full_verification_ui_words`（BP 跟 SP、AP 一樣是保留字）。
- 全套測試：全部通過，沒有失敗（`-x` 跑完，exit 0；輸出沒有印總數）。全套跑的期間又改了編輯器的 Stat 下拉名稱、加了編輯器表單測試，之後重跑相關的 12 個檔案：116 passed。`ruff check`、`ruff format` 通過。
- 真實 Cocoa 視窗截圖：`docs/audits/evidence/d89/`（狀態頁中英修改前後、編輯器選單頁面的分組與各行表格）。

**還沒做或已知的限制：**
- FV 沒有 SP 資源：HP＝vitality、MP＝technique；楓之谷的 HP 一點加 1000 這種量，作者在節點的 `resource_bonuses` 自己填。
- 使用者說「每 BP 本來加 10%」；FV 原本的強化是 ×2／×3／×4（每 BP 等於 +100%），這次保留，BP 加成加在上面。要改成每 BP +10% 只要改 `boost_power_*` 的倍率。
- 能力值說明（例如「穿透：攻擊時無視敵人防禦的比例」）目前只有公式型能力值存在資料裡，狀態頁沒有顯示說明的地方。
- 戰役重打時骰子不變，所以種子 7 打不過；若要每次重打不同骰子，要開 `vary_seed`（會改變所有戰鬥的結果）。

**狀態：** 已提交（3c693d9c，與 D88 同一個提交，未推送）。

## D90 — 編輯器的下拉列表從格子下方展開；能力值表的欄位可以選（2026-10-27）

**使用者要求：** GUI 所有的列表都要顯示在那一格的下方，不要直接擋住那一格，要是連在一起的列表（截圖：遊戲系統的種類選單蓋在格子上）。選取的藍色框不能超出列表。能力值表的 Rank 是什麼？demo 不要，但要保留可以設定。

**原因（查證）：** 主題的樣式表已經寫了 `combobox-popup: 0`，但 macOS 的 style 用 `SH_ComboBox_Popup` 要求選單式的彈出，還把清單位置（`SC_ComboBoxListBoxPopup`）定成格子本身，所以清單蓋在格子上、以目前選的那一項為中心。

**做了什麼：**
- `editor/theme.py` 的 style 包裝（原本只管提示延遲）：`SH_ComboBox_Popup` 回 0；清單位置回傳格子的範圍，所以清單掛在格子下緣、左邊對齊、至少跟格子一樣寬。整個編輯器的下拉列表一起改。
- 清單外框是焦點色、圓角；清單內留 3 px，選取的那一列是圓角底色，不碰到外框。
- **能力值表欄位**：`MenuRules.stat_columns`（遊戲系統 ▸ 選單頁面 ▸「能力值表的欄位與順序」，勾選＋排序）：`rank`（已點／上限）、`total`、`base`、`points`、`gear`、`gain`；都不勾＝全部。沒勾的欄位不留空，其他欄往右靠。FV 示範不顯示 rank（`trial_d89.py`）。

**驗證：**
- Cocoa 真實視窗打開三個列表（遊戲系統種類、商店的品項、帶圖示的道具）：清單上緣＝格子下緣（y 差 25，格子高 26）、左邊對齊；截圖中選取列在外框內。
- 狀態頁截圖沒有等級欄（`docs/audits/evidence/d89/after/*_status.png`），編輯器截圖有新的欄位（`*_menu_pages_stat_groups.png`）。
- 新測試 2 項（欄位來回、壞欄位報錯、隱藏欄位不留空、demo 畫面沒有 Rank）；相關 5 個檔案 69 passed。全套跑了兩次：第一次清單修改之後 3551 passed、1 skipped；改了選取框之後再跑一次，3551 passed、1 skipped（12 分 49 秒）。能力值表欄位選項是在第二次全套開跑之後才加的，只跑了相關的 5 個檔案（69 passed）。

**狀態：** 已提交（49e4894e，與 D91、D92 同一個提交，未推送）。

## D91 — 遊戲裡每個標籤、數值、技能都有明確定義；全系統與 demo 檢查（2026-10-27）

**使用者要求：** 所有遊戲內的東西都要有地方明確定義所有行為，對整個系統跟 demo 做完整檢查。actor 的 Base Stats 只顯示 STR、DEX、INT、LUK、VIT、SPD，其他在別處設定。

**原因（查證）：**
- 標籤（`weak.fire`、`equip.sword`、`no_escape`…）沒有任何地方寫它是什麼、誰帶著它、誰讀它；demo 用了 323 個標籤，沒有一個有說明。
- 被動技能、狀態、職業、角色、敵人、裝備、寶石沒有說明欄位；技能樹的被動只顯示名字，看不出效果。
- 檢查 demo 時找到的問題：
  - 職業給了 `capability.weapon.*`，但沒有任何武器要求它，等於沒作用；
  - 刪掉 Hero 職業後，`brave_slash`、`dawn_and_dusk`、`twilight_judgment`、`dragon_form`、`rally_cry` 沒有人學得到；
  - 另有 15 個技能只出現在自己的時機表裡（`add_bite`、`boss_cleave`…，當作 build 範本），只回報、沒刪；
  - Skeleton Ancient 的 boss 戰本來就很勉強（HEAD 在 seed 3 也會輸）。

**做了什麼：**
- **標籤定義**：新增 `rpg/tag_definitions.py` 的 `TagDefinition`：
  - 可以定義單一標籤，也可以用 `rune.*` 定義一整個家族；最長的家族優先，單一定義勝過家族；
  - 引擎自己會讀的標籤（`no_escape`、`scheduler:*`、`capture`、`equip.*`…）在 `BUILT_IN` 寫明引擎會做什麼。
- **編輯器**：遊戲系統 ▸ 標籤頁（名稱、意思、排序），下方的卡片寫出：
  - 引擎怎麼用；
  - 家族涵蓋哪些標籤；
  - 誰帶著它；
  - 誰讀它（逐條列出）。
- **問題清單**：專案一旦有標籤定義，用到但沒定義的標籤會列成問題。
- **說明欄位**：被動、狀態、職業、角色、敵人、裝備、寶石都加了 `description`。有寫才存，空的也會顯示在編輯器裡。
- **效果文字**：新增 `rpg/effect_text.py`，依能力值的顯示方式寫效果（`+12%`、`x1.6`、`（裝備劍時）`）。技能樹的被動顯示成「名稱（MAG +18）」。新增遊戲內文字 `effect.when` 和繁中翻譯。
- **demo**（`trial_d91.py`）：
  - 定義了 105 條標籤或家族，涵蓋全部 323 個標籤，中英文都有；
  - 每把武器要求自己種類的 `capability.weapon.*`；
  - Brave 拿得起全部 10 種武器，也接手原本 Hero 的技能；`rally_cry` 給 Guardian；
  - 書、拳、投擲武器分給合適的職業；
  - 角色只存六項基本能力值（以最小平方法擬合舊數值，每個英雄的特色不變），其他數值改由公式基數設定。
- **demo 腳本**：
  - smoke 腳本的勇者在第一次破防前，優先使用打 boss 弱點的技能。原本破防只是運氣：練好等級的隊伍把 36 盾的 boss 打死時還剩 22 盾。
  - 戰役腳本拿掉已不存在的技能。
- **編輯器版面修正**：說明卡片被切掉，原因是 QSS 的 padding 和跨欄列的上邊距沒有算進高度。改用 `setContentsMargins`，`_Cell` 也把自己的邊距算進去。

**驗證：**
- demo 的問題清單是空的：323 個標籤都有定義，能力值也都有定義。
- Cocoa 真實視窗的繁中截圖：
  - 標籤頁（`weak.*`）：`docs/audits/evidence/d91/tags_zh.png`；
  - 能力值頁（`str`）：`stats_zh.png`；
  - 兩頁的說明卡片都完整顯示。
- smoke：破防 1 次、19/19 職業、用了 154 個技能、9 場勝利。戰役跑完。
- 新測試 `tests/test_d91_definitions.py` 15 passed。
- 全套：3545 passed、1 skipped、9 failed（8 分 7 秒）。9 個失敗都是舊測試還用已刪掉的 hero 職業、hero_01 舊的 STR 12，以及複製 `damage.*` 時變成 `damage.*_copy`。建議的複製 id 改成保留家族的 `*`（`damage_copy.*`），測試改用 brave 和 21，這 4 個檔案 30 passed。全套開跑後才改的版面、主題、翻譯，相關的 62 個檔案重跑：609 passed，另外 3 個失敗就是上面那幾個，已經修好。

**狀態：** 已提交（49e4894e，與 D90、D92 同一個提交，未推送）。武器格系統在 D92 完成。

## D92 — 武器格：主武器在中間、副武器在右、特殊道具在左；攜帶武器在戰鬥中切換；雙手武器（2026-10-27）

**使用者要求：** 主武器在中間、副武器在右、特殊道具在左；可以攜帶全部武器並在戰鬥中切換；要有雙手武器；全部都能在 GUI 設定。

**原因（查證）：**
- 裝備欄位只是存檔裡每個英雄各自的 `slots`，沒有專案層級的定義，所以沒有名稱、排序、說明，也無法在編輯器裡改。
- 沒有「帶著但沒穿」的狀態：裝備不是穿上（給能力值），就是在背包。
- 沒有雙手武器：一件裝備不能同時佔兩格。
- 戰鬥中不能換裝備。

**做了什麼：**
- **欄位定義**：`EquipmentSlotDefinition` 新增名稱、排序、說明、`stowed`（攜帶，不算穿戴）和 `required_capabilities`（只有擁有能力標籤的英雄才有這一格）。
  - 專案的 `equipment_slots` 載入存檔時會同步到每個英雄的欄位，已經穿著的裝備保留。
  - 編輯器：遊戲系統 ▸ 裝備欄位頁可以編輯全部欄位設定。
- **攜帶格**：裡面的裝備不給能力值、技能、標籤或套裝效果，要等戰鬥中換上才有。
- **雙手武器**：裝備的 `blocks_slots`（編輯器：「同時佔用（雙手）」）。被佔用的格子必須空著，雙手武器也放不進它佔用的格子。
  - 背包規則 ▸「格子被佔用時」：`take_off` 把擋路的裝備收回背包，`refuse` 拒絕並說明。
- **戰鬥中換武器**：新增「換武器」指令，列出攜帶的武器和要換到哪一格。
  - 換下的裝備放回攜帶格；攜帶格滿了就放進背包。
  - 立刻套用差異：能力值、資源上限、失去的技能被封鎖、得到的技能加入、標籤更新。破防時的裝備損壞也改用同一套。
  - 背包規則 ▸「戰鬥中換攜帶武器」：`turn`（用掉一回合）、`free`（不用回合）、`off`（關閉）。
- **裝備畫面**：欄位依排序列出，英雄用不到的空格不顯示。詳細面板會註明「雙手：也佔用…」和「攜帶中：…」。
  - 人偶的格子可以設定底圖（`MenuSlotPlace.backdrop`，編輯器的「底圖」欄），空格也看得到。
- **demo**（`trial_d92.py`）：
  - 欄位：特殊道具（左）、主武器（中）、副武器（右，任何 `weapon` 標籤），加上 6 格攜帶武器，只有 Brave（`capability.carry_weapons`）有；
  - 戒指標上 `special`；弓、杖、矛、斧是雙手武器；
  - Roger 開場穿日炎劍、Warden Ring 在特殊道具格，攜帶弓、斧、祈禱書、拳套；副武器格空著，留給戰役找到的魔戒。
- **修好的問題**：
  - `gain_equipment` 會產生重複的裝備實例 id（`w_demon_ring:bag1`），造成鑲嵌失敗。現在避開所有已經用過的 id。
  - 戰鬥畫面的指令選單沒有「換人」那組，選了會跳到別的類別。現在「換人」和「換武器」都有。
  - 裝備提示：先找空的穿戴格，再找可以替換的，最後才放攜帶格。
  - 戰役腳本挑技能前先排序：引擎列技能的順序不會再改變結果。

**驗證：**
- 戰鬥中換上弓：物理攻擊 748.8 → 612.8、HP 不變、劍的攻擊被封鎖、標籤從劍換成弓。截圖 `docs/audits/evidence/d92/d92_battle_zh-TW.png`、`d92_battle_en.png`。
- 裝備畫面：`d92_eq_zh-TW_main.png`、`d92_eq_zh-TW_bow.png` 和英文版。
- Cocoa 真實視窗繁中截圖：
  - 裝備欄位頁：`d92_slots_zh.png`；
  - 背包規則：`d92_inv_zh.png`；
  - 弓的「同時佔用（雙手）」：`d92_record_zh.png`；
  - 人偶格子的「選擇圖片…」：`d92_doll_places_zh.png`。
- 新測試 `tests/test_d92_weapon_slots.py` 10 passed。
- 戰役：seed 7 打贏，沒有重試；seed 3 一樣會輸（D91 就記錄過的 boss 戰邊緣情況）。
- 全套：3573 passed、1 skipped、6 failed（7 分 35 秒）。
  - 5 個是 `test_battle_command_rows.py`：全套開跑後才改了「換人／換武器」那組指令和測試，重跑通過。
  - 1 個是真的問題：人偶格子的底圖只能打字，沒有選檔按鈕。已補上「選擇圖片…」按鈕，在空格圖片或底圖那一格按兩下也可以選檔；選的檔案會匯入專案。新增測試，Cocoa 截圖 `d92_doll_places_zh.png`。
  - 重跑相關檔案：112 passed。ruff check 和 ruff format 都通過。

**狀態：** 已提交（49e4894e，與 D90、D91 同一個提交，未推送）。使用手冊還沒有 D92 的章節。

## D93 — 職業圖示不用裝備；說明框固定在左邊；標籤頁不再卡；能力點加號一致（2026-10-27）

**使用者要求：**
- 職業 icon 不要用裝備表示。
- 有的驚嘆號提示在左邊、有的在左下角、有的在右下角，很亂，都固定出現在左邊。
- 點標籤分頁時會卡。
- 加點的加號大小不一致。

**原因（查證）：**
- D91 的職業圖示是把 demo 的裝備圖拼起來的（Brave 是日炎劍、Knight 是頭盔），看起來像道具。
- ⓘ 說明有兩條路：
  - 資料表單的標籤由自己的程式放在文字結尾的右邊；
  - 遊戲系統的欄位和區段標記用 Qt 預設，跟著滑鼠出現，靠近螢幕邊緣時會翻到另一邊。
  - Qt 的提示框顯示後還會自己改大小和位置；改成換行時，它還會自己消失。
- 標籤頁：列表為每一筆取名字時，順便算了每一筆的「誰帶有它、誰讀取它」，而每一次都要走過整個專案。108 筆要 4.1 秒。
- 加號是 22 px 的「+」文字。視窗縮小時，每一列的字被縮掉的像素不一樣，所以看起來大小不一。

**做了什麼：**
- **職業圖示**（`trial_d93.py`）：20 個職業改用 7Soul 圖示（CC0，原檔不改，放在 `playable_assets/icons_7soul/`）。
  - 戰士系是不同顏色的人形，神聖系是十字與天使，黑暗系是暗影、骷髏與五芒星。
  - 沒有兩個職業共用同一張圖，也沒有其他資料用到這些圖。
  - D91 的 `lucifer/icons/job_*.png` 已刪除。
- **說明框**（`decor.show_help_tip`）：改用編輯器自己的說明框，不用 Qt 的提示框。所有 ⓘ 都走同一個規則：
  - 說明框的右邊貼著文字開頭的左邊，和標籤同高；不管滑鼠從哪裡進來，位置都一樣；
  - 太長會換行，寬度最多 460 px，或左邊剩下的空間；
  - 左邊空間不到 200 px（視窗貼著螢幕左邊）時，改放在右邊；
  - 滑鼠離開、按下或標記被隱藏時，說明框就消失。
- **標籤頁**：`form_data(..., info=False)`，列表取名字時不算說明卡片，只有選到的那一筆才算。4.1 秒變 0.05 秒。
- **加號**：改畫兩條實心的橫條和直條，每一列一樣大、置中。

**驗證：**
- Cocoa 真實視窗繁中截圖（`docs/audits/evidence/d93/`）：
  - `d93_tip_record_zh.png`：角色的「基礎屬性 ⓘ」；
  - `d93_tip_systems_zh.png`：遊戲系統 ▸ 標籤的「標籤 ⓘ」；
  - 兩個說明框都在文字左邊，長說明會換行。
- `jobs_zh.png`：編輯器的職業列表顯示新圖示；`job_icons.png` 是 20 個職業的圖示總覽。
- `zh_status_plus.png`：狀態頁 7 個加號；縮到 62% 後看起來一樣大。
- 新測試：
  - `test_record_form.py`：說明框在左邊、同高、離開就消失；長說明會換行；
  - `test_d93_editor_speed.py`：列表不再為每一筆算說明卡片。
- 相關測試檔：153 passed。
- 全套：3582 passed、1 skipped（8 分 4 秒）。
  - Zealot 的圖示是全套開跑後才從天使改成火焰（和 Bishop 太像），只改了圖片和一個 `icon_id`。

**狀態：** 已提交（`0e4e883b`）。

## D94 — 公式：只能用「遊戲系統 ▸ 屬性」宣告的變數；可以打字也可以按插入按鈕；沒寫就用原本的欄位（2026-10-27）

**需求：**
- 開發者在「遊戲系統 ▸ 屬性」宣告能力值，公式裡才能引用；沒宣告的變數拿來計算就是錯誤。
- 公式要讓程式看得懂；可以自己打，也有按鈕可以插入。
- 有寫公式就用公式，沒寫就用預設（原本的欄位）。說明文字只給人看，程式不讀。

**做了什麼：**
- **哪些欄位是公式**（`gameplay/expressions.FORMULA_FIELDS`），每個欄位能用哪些名字：
  - 屬性公式 `derived_stat.expression`：`self`；
  - 機率判定 `outcome_check.chance_expression`：`source`、`target`；
  - 逃跑 `battle_escape_rule.chance_expression`：`source`、`opponent`、`attempts`；
  - 戰鬥規則 `initiative_expression`：`self`；`final_damage_expression`：`value`、`source`、`target`；
  - 技能數值 `value_formula.expression`：`source`、`target`。
- **屬性公式可以寫成文字**（`rpg/derived_stats.py`）：新欄位 `expression`。有寫就用它算，沒寫就用「基礎數量 + 讀取自」。上下限照樣套用。
- **檢查**：
  - `variables(text)` 列出公式讀到的屬性和資源；`undeclared(...)` 列出沒宣告的；
  - 專案有定義屬性時才嚴格檢查（和 D91 標籤相同）；沒有定義時只檢查公式能不能解析。
- **公式欄位**（`editor/formula_field.py`）：
  - 等寬字的輸入框，可以直接打；
  - 每個可用的名字一顆按鈕（`source ▾`、`target ▾`、`self ▾`），選單裡是宣告過的屬性（`ACC · source.accuracy`）和「資源」子選單（current / maximum / ratio）；
  - 「函式 ▾」（min、max、clamp、floor…）和運算子按鈕（+ − × ÷ ( )），插在游標位置；
  - 底下一行狀態：綠色「✓ 讀取：ACC, EVA」；紅色「✗ 沒有在「遊戲系統 ▸ 屬性」宣告：charm · 未套用」；空白時「空白：使用其他欄位」。
  - 錯的公式不會寫進資料，資料保留最後一個正確的公式；遊戲系統頁按套用時會擋下並說明原因。
- **用在哪裡**：資料表單（`record_form`）的上述欄位，以及「遊戲系統 ▸ 屬性公式」的新「公式」欄。技能數值公式空白時也會顯示欄位。
- **問題面板**：新區域「公式」，公式讀到沒宣告的屬性時列為錯誤（`problems.project_formulas`）。
- **屬性用途卡片**（`stat_usage`）：來源與效果會列出公式；讀取 `source.x` 的公式也能被找到（原本的比對漏掉）。
- **Demo**（`trial_d94.py`，跑過一次）：
  - Accuracy 改成 `self.dex + 0.5 * self.luk`，清掉「讀取自」；
  - Land 改成 `0.95 + 0.003 * source.accuracy - 0.003 * target.evade`，清掉屬性係數；最低 30%、最高 100% 照樣套用；
  - 兩個公式算出的數字和原本的欄位一樣，所以 demo 戰鬥不變。
- 17 個新的編輯器字串加入 `zh_TW.json`。

**驗證：**
- Cocoa 真實視窗繁中截圖（`docs/audits/evidence/d94/`）：
  - `d94_stat_formula_zh.png`：Accuracy 的公式欄、按鈕和綠色狀態；
  - `d94_stat_menu_zh.png`：`self ▾` 選單列出宣告過的屬性；
  - `d94_stat_error_zh.png`：打 `self.charm` 時顯示紅色錯誤、未套用；
  - `d94_land_zh.png`：機率判定 Land 的公式欄，讀取 ACC、EVA。
- 新測試 `test_d94_formulas.py`（10 個）：
  - 變數解析、沒宣告的變數、只在有定義屬性時嚴格；
  - Demo 兩個公式和舊欄位的數字相同；
  - 問題面板、按鈕插入、表單只在正確時寫入、遊戲系統頁擋下錯的公式。
- 相關測試檔：67 passed。
- 全套：1 failed、3591 passed、1 skipped（8 分 6 秒）。
  - 唯一失敗的是 `test_full_verification_stats.py`：它檢查 Land 的舊屬性係數，而這些係數已依設計改成公式。
  - 改成檢查 Land 的公式、確認係數已清空後，這個檔案 4 passed。

**狀態：** 已提交（`0e4e883b`）。

## D95 — 屬性的「來源與作用」逐步列出每一筆；ⓘ 說明框緊貼在 ⓘ 右邊、半透明（2026-10-27）

**需求：**
- 「這格內容哪來的」「我看不懂 到底列在哪裡」「where it comes from 要做成好懂一點 清楚一點 可以列詳細一點」。
- 「驚嘆號提示應該就是直接顯示在驚嘆號右邊 就在旁邊就好 不用離很遠 擋到其他沒關係 做成透明格 而且這只是提示」。

**原因（查證）：**
- D91 的卡片只寫數量（「Base Stats of 12 jobs」「added by 3 pieces of gear」），沒有名字、數字，也沒說在哪一頁改。
- 「changed by 1 passive」是錯的：被動技能只要資料裡出現 "str" 三個字母就算，STR 算到的是 Destruction Mastery（ID `archmage_destruction_capstone`），它只改 MATK 和 CRI。
- 職業的「屬性加成」和「每級成長」被混成一句 Base Stats；技能樹加點（Attributes ▸ STR）完全沒列。
- D93 的說明框放在標籤文字的左邊，離 ⓘ 很遠。

**做了什麼：**
- **來源**（`stat_usage._sources`）照遊戲實際相加的順序，一步一行，每步寫明是什麼、在哪一頁改，下一行列出那一頁的每一筆和它的數字（不再「還有 N 筆」）：
  1. 角色的起始值（資料庫 ▸ 角色 ▸ 基礎屬性）；
  2. 職業一次給的（資料庫 ▸ 職業 ▸ 屬性加成）；
  3. 成長路線的階段（資料庫 ▸ 成長路線）；
  4. 每升一級加一次，×（等級 − 1）（資料庫 ▸ 職業 ▸ 每級成長）；
  5. 玩家花點數學的，技能樹的階（資料庫 ▸ 技能樹），一個節點一行，寫「每階 +1，最多 30 階」；
  6. 穿戴的裝備、7. 鑲在裝備上的附件、8. 學會的被動技能（各自的「屬性變化」）；只算真的改到這個屬性的；
  9. 它自己的能力值公式，最後才算（遊戲系統 ▸ 能力值公式 ▸ 名稱）。
  - 沒有東西的步驟不列；敵人另列「敵人直接用自己的數字」。
- **作用**：「STR 每 1 點，ATK +2（遊戲系統 ▸ 能力值公式 ▸ 物理攻擊）」；機率判定寫成「Land機率 = 公式（戰鬥規則 ▸ 機率判定 ▸ Land）」。
- 卡片改成粗體標題加分行（rich text），29 個新字串加入 `zh_TW.json`。
- **說明框**（`decor.show_help_tip`）：
  - 左邊緣貼在 ⓘ 右邊 4 px，和標籤同高；ⓘ 的位置由 `_mark_span` 從標籤文字算出（不管靠左、靠右或置中）；
  - 半透明（主題的 raised 顏色 86% 不透明），蓋住底下的欄位也沒關係，滑鼠點不到它；
  - 右邊不到 200 px（ⓘ 貼著螢幕右邊）時，改放在 ⓘ 左邊。

**驗證：**
- Cocoa 真實視窗繁中截圖（`docs/audits/evidence/d95/`）：
  - `d95_usage_str_zh.png`：STR 的卡片，5 個步驟和 3 個作用，沒有被動技能；
  - `d95_usage_evade_zh.png`：EVA 的卡片，7 個步驟（含被動技能，能力值公式排最後），敵人另列；
  - `d95_tip_record_zh.png`：角色「基礎屬性 ⓘ」的說明框貼在 ⓘ 右邊、半透明，底下欄位隱約可見，字清楚。
- 新測試 `test_d95_stat_usage.py`：每一筆和它的頁面都列出；被動技能只算真的改到屬性的；能力值公式排最後、敵人另列。
- `test_record_form.py` 的兩個說明框測試改成檢查 ⓘ 右邊、同高、半透明。
- 相關測試檔：28 passed。
- 全套：3595 passed、1 skipped（8 分 12 秒）。

**狀態：** 已提交（`22f351aa`）。

## D96 — 通用選單頁：每一頁由區塊組成，狀態頁和物品頁只是其中兩頁（第一步）（2026-10-27）

**需求：**
- 「這個為何要status item放在一起 可以分成兩個去設定嗎 ... 怎麼會是menu page(status item)這太混淆了」「畢竟使用者也是會做出各種菜單 透過這個菜單頁」。
- 「拆 當然是要做成 各種菜單都支援的通用設計頁面 怎可能 item要一種 status要一種 這樣其他的怎辦」。
- 「照這個區塊設計做通用選單頁，先做第一步（資料、編輯器、遊戲端用區塊組出狀態頁和物品頁，外觀不變）」。

**原因（查證）：**
- D87～D89 把狀態頁和物品頁的設定，連同暫停選單的順序，全部寫在同一筆 `MenuRules`（「Menu Pages (status, items)」）。
- 遊戲端的狀態頁和物品頁位置都寫死在程式裡，作者沒辦法做第三種頁面。

**做了什麼：**
- **資料**（新檔 `rpg/menu_pages.py`）：
  - `MenuPage`：ID、名稱、圖示，以及依序排列的 `blocks`；
  - `MenuBlock`：類型（`profile` 角色資料、`stat_points` 能力點表、`stat_details` 能力細項、`item_list` 物品清單）、位置（左欄、右欄、整排）、高度（0 = 和同一欄平分剩下的高度），加上該類型自己的設定；別的類型的設定不會被存下來；
  - 資料庫新增 `menu_pages` 表；`default_pages` 是引擎原本的狀態頁和物品頁；`menu_pages(db)` 回傳專案的頁面，沒有的就用內建頁面補上。D96 以前的專案，原本寫在 `MenuRules` 上的設定照樣會填進內建頁面。
- **暫停選單**：
  - 「狀態」和「道具」開啟 ID 為 `status`、`items` 的頁面；
  - 專案自己的其他頁面，每頁都是一個項目（`page:<id>`），顯示頁面名稱和圖示；
  - 沒勾順序時，排在「道具」後面；有勾順序時，照勾的順序，沒勾到的頁面不顯示；
  - `MenuRules` 現在只剩暫停選單的順序。
- **遊戲端**：
  - `StatusMenu` 從目前頁面的區塊讀設定（每頁只算一次）；
  - `_draw_menu_page` 依 `menu_page_boxes` 排版：整排區塊放在最上面，下面是左右兩欄，左欄是寬度的 45%、最多 560 px；
  - 物品清單抽成 `_draw_item_list(rect)`，任何頁面都能放；
  - 一頁的游標和按鍵，交給第一個「物品清單」區塊，沒有的話交給「能力點表」。
- **編輯器**（遊戲系統）：
  - 「暫停選單」：只剩暫停選單的頁面和順序；
  - 「選單頁」：ID、名稱、圖示、區塊表。清單每一行寫「物品清單 · 整排」，可以 ↑ ↓ 調整順序；
  - 每個區塊只顯示自己類型的設定（新的 `FormField.when` 和 `ResponsiveForm.set_shown`）；
  - 新增 ID 為 `status` 或 `items` 的頁面時，會從引擎原本的版面開始；
  - 暫停選單的順序清單裡，可以勾「頁面：Materials」。
- **翻譯**：頁面名稱用 `data.menu_page.<id>.name`；區塊裡的分頁和篩選名稱，照樣出現在資料翻譯清單。
- **用途卡片和問題面板**：改讀各頁「能力細項」區塊裡的行。
- **Demo**（`trial_d96.py`，跑過一次）：
  - `trial_menu` 的設定搬進 `status` 頁（角色資料、能力點表放左欄，能力細項放右欄）和 `items` 頁（物品清單）；
  - 新增範例頁 `materials`：只放「Materials」分頁的物品清單，在暫停選單「道具」後面。
- **順便修好 D94 造成的問題**：狀態頁的「機率」行（ACC、EVA 透過 Land）原本讀 Land 的舊係數，D94 把係數改成公式後，這兩行只顯示 95%。現在 `StatLine.chance` 會讀判定的公式，數字和改公式前相同。

**驗證：**
- 遊戲端 1280×720 截圖：改之前、改繪製之後、跑完 demo 遷移之後，狀態頁和物品頁**逐像素相同**（`ImageChops.difference` 為空）。
  - 證據：`docs/audits/evidence/d96/game_status_page.png`、`game_items_page.png`、`game_materials_page.png`。
- Cocoa 真實視窗繁中截圖（`docs/audits/evidence/d96/`）：
  - `d96_pages_status_zh.png`：status 頁的三個區塊，選到「角色資料」時只有區塊、位置、高度；
  - `d96_pages_details_zh.png`：選到「能力細項」時，只有細項屬性、分組和行；
  - `d96_pages_materials_zh.png`：Materials 頁的物品清單和它的分頁；
  - `d96_pause_menu_zh.png`：暫停選單只剩順序。
- 新測試 `test_d96_menu_pages.py`（6 個）：區塊只保留自己類型的設定、頁面的設定從區塊讀、排版位置、demo 的頁面、自己的頁面從暫停選單打開、勾選順序。
- `test_d94_formulas.py` 新增一個測試：機率行讀公式和讀係數的數字相同。
- 改寫配合新結構的舊測試：`test_menu_pages.py`、`test_stat_window_d89.py`、`test_passability_d88.py`、`test_d91_definitions.py`。
- 相關測試檔：39 passed（選單頁、D89、D94、D96）。
- 全套第一次跑有 6 個失敗，全部是 demo 的新名稱沒有中文，或舊檢查還假設只有內建項目。已修好：
  - demo 字表加入「Pause menu／Status／Items」，zh-TW 表加入四個名稱（`trial_d96.CHINESE`）；
  - `trial_d87` 重跑時，不再把 D96 前的舊紀錄寫回去；
  - 暫停選單的頁面名稱改走翻譯鍵（符合「畫面不直接讀名稱」的檢查）；
  - `test_built_in_text` 跳過專案自己的頁面項目。
- 全套：3602 passed, 1 skipped。

**限制（第一步）：** 一頁只有一個區塊吃游標和按鍵（先找「物品清單」，沒有再找「能力點表」）；有勾暫停選單順序時，沒勾到的頁面不會出現。

**狀態：** 已提交（`22f351aa`）。

## D97 — 暫停選單合成一頁：左邊是完整清單，右邊是選到那項的設定（2026-10-28）

**需求：**
- 「改這頁：直接列出目前暫停選單的完整順序，每項可以勾選顯示或隱藏、可以拖曳排序，按鈕和標題的字要改清楚」。
- 「你的這三個menu相關的設計做好一點 現在根本看不懂要幹麻 很亂 每種列表 設計都要有必要性」。
- 「照這個設計合併：遊戲系統只留一個「暫停選單」，左邊是完整清單（勾選、拖曳、新增頁面、新增事件項目），右邊依選到的那列顯示它的設定；拿掉規則 ID、名稱和 Order 欄位」。

**原因（查證）：**
- 「暫停選單」「選單頁」「暫停選單項目」三個分類其實都在改同一個東西：暫停選單。
- 「暫停選單」紀錄：一個專案只會有一筆，卻要顯示紀錄清單、規則 ID 和名稱。順序欄是「+ 加入順序」：空著時看不到實際順序，而且只要加了一項，沒加到的就全部消失。
- 「暫停選單項目」：有自己的 Order 數字，和暫停選單的順序重複。
- macOS 上，清單裡的勾選框只有被選到的那一列畫得出來。

**做了什麼：**
- **資料**：
  - `MenuRules` 新增 `pause_hidden`，版本改為 2。
  - `pause_entries` 改成「排序」：沒列到的項目留在引擎順序裡的位置（`pause_order`），所以之後新增的頁面會自動出現。
  - 版本 1 的資料照舊：列出的才顯示（讀進來時，沒列的內建項目轉成隱藏）。
  - 順序也可以放專案自己的事件項目（`entry:<id>`）。
- **引擎**（`rpg/menu_pages.py`）：
  - 用到這份規則的地方，引擎和編輯器共用同一份程式：
    - `engine_pause_order`：內建項目，加上專案頁面（排在「道具」後面）和事件項目（排在「設定」前面）；
    - `usable_pause_entries`：哪些項目這個遊戲有東西可以打開；
    - `pause_menu`：最後要顯示的清單。
  - `PAUSE_NEEDS` 記每一項需要什麼才會出現，`PAUSE_OPENS` 記每一項打開什麼。
  - 遊戲端的 `_pause_options` 改用 `pause_menu`。
- **編輯器**：遊戲系統的分類選單只剩一個「暫停選單」（新檔 `pause_menu_widget.py`），取代原本的三個分類。
  - **左邊**：完整的暫停選單，順序和遊戲裡一樣。
    - 勾選＝顯示，拖曳＝移動，變更馬上存。
    - 上方是「全部顯示」「引擎順序」；下方是「新增頁面」「新增事件項目」（輸入名稱，ID 由名稱產生）。
    - 遊戲還沒有東西可以打開的項目會變灰，提示裡寫需要什麼。
  - **右邊**：選到哪一列，就顯示那一列的設定。
    - 標題下方寫這是內建項目、選單頁或事件項目。
    - 內建項目寫它打開什麼；隱藏的項目、遊戲目前不會出現的項目，也會寫出原因。
    - 「狀態」「道具」和專案頁面：名稱、圖示、區塊。「狀態」「道具」第一次修改時才建立紀錄；有改過時，可以按「回到引擎的頁面」改回去。
    - 事件項目：名稱、圖示、事件程式、兩個開關，可以「刪除項目」。
  - 拿掉的欄位：規則 ID、紀錄名稱、頁面 ID、項目 ID、Order。刪除頁面或事件項目時，順序也會一起更新。
  - 所有清單和表格的勾選框都改用編輯器自己的樣式（`QAbstractItemView::indicator`），macOS 上每一列都畫得出來。
- **翻譯**：新字句都加進 `zh_TW.json`，包含每個內建項目打開什麼、需要什麼。

**驗證：**
- Cocoa 真實視窗截圖（`docs/audits/evidence/d97/`）：
  - `d97_merged_status_zh.png`：「狀態」的區塊；
  - `d97_merged_page_zh.png`：Materials 頁；
  - `d97_merged_entry_zh.png`：事件項目 Make Camp；
  - `d97_merged_builtin_zh.png`：內建項目「設定」；
  - `d97_merged_new_page_zh.png`：新增的頁面 Key Items；
  - `d97_merged_grey_zh.png`：沒有寵物、音樂時，灰色的項目和原因（只在記憶體裡改，沒有存檔）；
  - `d97_merged_status_en.png`：英文介面。
- 新測試（`test_menu_pages.py`）：
  - 完整清單、勾選和拖曳都會存；
  - 新增、刪除頁面和事件項目；
  - 「狀態」頁改回引擎的版本；
  - 版本 1 的資料照舊；
  - 沒列到的頁面留在原位，隱藏的項目不會出現（`test_d96_menu_pages.py`）。
- 改寫配合新頁面的舊測試：`test_stat_window_d89.py`、`test_game_systems_editors.py`。
- 全套：3604 passed, 1 skipped。

**還沒做：** Layout 分頁的問題（左右排版、預覽上的虛線框、Element 旁邊的「＋」和箭頭、Menu Records 頁）是下一個工作。

**狀態：** 已提交（`4ad1f4ae`，和 D98 一起）。

## D98 — 版面（Layout）分頁重排、拿掉「選單資料」分頁（2026-10-28）

**需求：**
- 「這個頁面設計的不好 很多地方排版都很亂 … layout為何都會有虛線邊匡 然後 element旁邊的+跟箭頭是怎樣 做錯了吧 record那個頁面完全看不懂」。
- 「照這五點修法改，選單資料先查清楚每個欄位遊戲還有沒有用，再搬家或刪掉」。

**查證：「選單資料」每個欄位遊戲有沒有用：**
- 這個分頁是六類紀錄：角色、裝備、技能、成長、道具、隊伍畫面。遊戲只讀每類的第一筆，而且只讀其中四類（`status_menu._profile`、`messages._profile_labels`）。
- 有用到的：
  - 角色畫面的屬性／資源名稱和屬性順序（狀態頁的列名、HP/MP 條）；
  - 角色、裝備畫面的欄位名稱（`slot_name` 的最後備案）；
  - 道具、裝備、技能、被動的名稱覆寫（只是重複紀錄自己的名稱，所有範例都是空的）；
  - 道具分組（只影響排序，所有範例都是空的）、`include_incompatible_candidates`（所有範例都是預設值）。
- 遊戲完全沒讀的：
  - 區塊順序、隱藏區塊、資源呈現方式；
  - 群組名稱、顯示上限、`page_size`、鑲嵌／成長名稱；
  - 隊伍畫面、成長畫面整類。
- 實際有填資料的只有 Full Verification 範例：38 個屬性名稱（都已經在「屬性」裡有同樣的名稱）、HP/MP 兩個資源名稱、28 個屬性順序。

**做了什麼：**
- **選單資料搬家、刪除**：
  - 六類紀錄從演出資料庫拿掉（`presentation/retired_screens.py`）。舊專案檔讀進來時：
    - 屬性／資源名稱和順序 → 遊戲系統 ▸ 屬性（屬性已有名稱就不覆寫；沒有定義的屬性會建立定義）；
    - 欄位名稱 → 遊戲系統 ▸ 裝備欄位（只改已定義、還沒名稱的欄位；替沒定義的欄位建立定義會改變它能裝的東西，所以不做）；
    - 其他欄位丟掉。
  - 狀態頁的屬性名稱和順序改讀「屬性」，欄位名稱讀「裝備欄位」（都經過翻譯）。
  - 移除「選單資料」分頁和它的編輯器程式（`runtime_rpg_ui_authoring.py`、`runtime_rpg_ui_workspace.py` 和測試）。「選單畫面」現在只有版面。
  - 7 個內附專案檔拿掉這六類紀錄，Full Verification 的 HP、MP 變成「屬性」裡的定義。建置腳本（`complex_reference_rpg/build_project.py`、`trial_stats.py`、`trial_d89.py`、`trial_d91.py`）不再寫這些紀錄。
- **版面分頁**：
  - 上方兩列工具：
    - 第一列：元素選單、「新增元素」（一般按鈕加選單，取代「＋」和箭頭）、「移除元素」；
    - 第二列：「這個畫面 ▾」（重設、從別的畫面複製、背景）、「共用設定 ▾」（選單主題、點陣字型、圖片訊息窗、生物畫面、遊戲資料夾設定）、「顯示所有外框」、預覽語言、「在遊戲中開啟」。
  - 預覽上的外框：
    - 預設不畫，畫面看起來和遊戲一樣；
    - 滑鼠移上去：虛線框，上方有名稱標籤；
    - 選到：實線框加名稱；
    - 勾「顯示所有外框」才全部畫出來。
  - 沒選元素時，右邊是提示和這個畫面所有元素的清單，不再是一頁空白欄位。
  - 畫面清單的「●」改成「（已修改）」。
  - 狀態頁的區塊寫明「顯示什麼在 遊戲系統 ▸ 暫停選單 設定」。
- **互相連結**：
  - 版面的狀態頁有「頁面的區塊：遊戲系統 ▸ 暫停選單」；
  - 暫停選單的頁面有「在畫面上調整位置（版面）」。
- **能力點表只寫縮寫**（「我覺得能力值str後面不用加上strength了 其他都改」）：Full Verification 的五個能力點節點（屬於成長圖的資料）名稱從「STR (Strength)」等改成「STR」「DEX」「INT」「LUK」「VIT」，中文也一樣（原本是「力量（STR）」）。建置腳本 `trial_stats.py`、`trial_d89.py`、`trial_zh_words.py` 一起改。
- **能力點表的加號**（「each的+100的加號有點偏移」）：數字前的「+」原本用字型的加號，比數字小、位置偏低。現在跟 + 按鈕一樣用兩條線自己畫（`_draw_stat_table`）。每列的數字也改成和按鈕垂直置中。
- **範例不顯示「每點」欄**（「我覺得each就不用寫了 保留可以寫就好 我這個demo不要」）：Full Verification 狀態頁的能力點區塊 `stat_columns` 拿掉 `gain`（`trial_d89.py` 一起改）。引擎和編輯器裡這個選項保留（暫停選單 ▸ 狀態 ▸ 能力點區塊的欄位）。
- **Materials 頁不放圖示**（「這個material旁邊的icon沒必要吧」）：範例的 Materials 頁拿掉圖示（`trial_d96.py` 一起改），因為暫停選單其他項目都沒有圖示。引擎的圖示選項保留（`test_icon_fields.py` 仍會驗證）。
- **範例一開始就多帶裝備**（「這個demo直接多給一點武器裝備飾品等等吧 現在太少」）：
  - 查證：範例本來就定義了 101 件裝備，但一開始背包裡一件備用的都沒有，只有角色身上穿的 11 件。
  - 引擎：遊戲開始頁新增「初始裝備（備用，放在背包）」欄位（裝備 → 件數），寫進開始狀態的裝備背包（`equipment_bag`）。已有的件會照原樣保留；舊版的開始狀態只補上背包版本需要的鍵，其他照原樣保留。
  - 範例：用這個欄位給 86 件。除了神話稀有度、型態（form）和進化版（`_ex`）以外，每件裝備各一件：武器 37、飾品 18、身體 17、頭部 5、腿部 5、腳部 4。腳本是 `trial_d98_gear.py`。
- **粒子特效頁的「使用處」文字疊在欄位上**（「這邊文字重疊」）：fx.divine_burst 被 17 個技能時間軸使用，整串名稱換行後蓋住了上方的欄位。現在只寫一行：「17 個地方使用：前三個 等另外 14 個」，完整清單放在滑鼠停留提示。「Revert」也補上中文「還原」。

**驗證：**
- Cocoa 真實視窗截圖（`docs/audits/evidence/d98/`）：
  - `d98_layout_status_zh.png`：沒選元素時的元素清單，預覽沒有外框；
  - `d98_layout_picked_zh.png`：選到「能力細項」時的實線框和名稱；
  - `d98_layout_all_outlines_zh.png`：顯示所有外框；
  - `d98_pause_status_link_zh.png`：暫停選單「狀態」頁和連到版面的按鈕；
  - `d98_stats_hp_zh.png`：HP 搬進「屬性」。
  - `d98_game_start_gear_zh.png`：遊戲開始頁的「初始裝備」；`d98_gear_bag_zh.png`、`d98_gear_equipment_zh.png`：遊戲裡的背包和紙娃娃裝備畫面；
  - `d98_particle_usage_zh.png`：粒子特效頁的使用處只佔一行；
  - `d98_pause_no_icon_en.png`：暫停選單，Materials 沒有圖示；
  - `d98_status_short_names_en.png`、`d98_status_short_names_zh.png`：能力點表只寫縮寫、沒有「每點」欄（遊戲預覽畫出來的畫面）。
- 新測試：
  - `test_d98_retired_screens.py`：舊檔讀進來的搬家規則、內附專案不再有這些紀錄；
  - `test_d98_layout_page.py`：外框、元素清單、「（已修改）」、兩個方向的連結。
  - `test_game_start_authoring.py`：初始裝備寫進背包、改件數時保留已有的件、範例一開始有 80 件以上。
- 改寫配合的舊測試：`test_complex_reference_rpg_project.py`、`test_editor_shell_integration_154a.py`、`test_full_verification_editable.py`、`test_full_playable_reference_validation.py`、`test_editor_battle_presentation_authoring.py`、`test_data_text.py`。
- 範例一開始有備用裝備，所以 `test_equip_offers.py`、`test_full_verification_b12.py`、`test_full_verification_workshop.py` 會先清空背包再測（它們測的是掉落、詢問要不要穿、紙娃娃換裝）；`test_stat_window_d89.py` 改成預期沒有「Each +」欄。
- 全套：3606 passed, 1 skipped。

**注意：**
- Full Verification 狀態頁的屬性順序改用「屬性」的順序。原本的順序把速度排在暴擊傷害後面，現在排在 VIT 後面。
- 「屬性」頁的 HP 卡片有兩個問題：標題寫成「Materials 從哪裡來」，內容寫「還沒有任何東西給它數值」（角色的基礎資源其實有給）。原因還沒查。這是 D95 卡片的問題，不是這次改的。

**狀態：** 已提交（`4ad1f4ae`）。

## D99 — 「屬性」頁 HP／MP 卡片的標題和來源（2026-10-28）

**問題（D98 注意事項第二點）：** HP 卡片標題寫「Materials 從哪裡來」，內容寫「還沒有任何東西給它數值」。

**原因（`src/asteria/editor/stat_usage.py`）：**
1. 標題：`stat_usage()` 列「顯示在哪個選單頁」時，迴圈寫了 `name = page.display_name`，蓋掉了屬性自己的名稱 `name`。範例最後一個選單頁是「Materials」，所以標題變成它。這個錯誤從 D96 加選單頁區塊時就有，每一個屬性的卡片都會中，不只 HP。
2. 內容：`_sources()` 只看屬性欄位（角色基礎屬性、職業屬性加成、每級成長、技能樹的屬性加成、裝備等），沒有看資源欄位。HP、MP 在引擎裡是資源，上限來自角色的「HP、MP 與其他資源」、職業的「資源加成」和「每級資源成長」，以及技能樹節點的資源加成。這些卡片都沒有列出。

**修法：**
- 迴圈變數改名 `page_name`。
- 來源多三步：角色的起始上限、職業一次加到上限、每升一級加到上限一次。技能樹節點的資源加成也算進去。順序和 `resolved_build` 加總資源時一樣。
- 新增 3 個中文詞條。

**驗證：**
- `tests/test_d95_stat_usage.py` 新增兩個測試：
  - HP 卡片的標題、四個來源步驟和頁面路徑都對，MP 卡片有「Attributes ▸ MP」；
  - 每個屬性卡片的標題都是它自己的名稱。
- Cocoa 視窗截圖：`docs/audits/evidence/d99/hp_card_zh.png`、`hp_card_en.png`。
- 全套：3608 passed, 1 skipped。

**還沒做：** HP 卡片的「它會改變什麼」仍然寫「還沒有東西讀它」。這是事實：沒有公式或規則讀 HP 的數值，戰鬥只扣它的現值。要不要在資源卡片寫明「傷害和治療改它的現值」，留給使用者決定。

**狀態：** 已提交。

## D100 — 免安裝版 app：編輯器、試玩、匯出都不需要 Python（AST-06，2026-10-28）

**問題：** AST-06 的缺口「不產生免直譯器執行檔」。輕度使用者要先裝 Python、PySide6、pygame，還會遇到版本衝突。匯出的遊戲也一樣，玩家要有 python3＋pygame-ce。

**決定（使用者選擇）：** 用 PyInstaller（不用 Nuitka、Briefcase）。先做 macOS，Windows／Linux 的 CI 留到之後。只做 ad-hoc 簽章，不做 Developer ID 公證。匯出的遊戲內附免安裝播放器。

**做法：**
- `scripts/build_app.py` 一個指令產生 `dist/Asteria.app`、`.zip`、`.dmg`（`build/`、`dist/` 已加入 .gitignore）。PyInstaller 凍結直譯器、整個標準函式庫（專案自己的 Python 程式碼也能用）、PySide6、pygame-ce、numpy、ModernGL。
- 引擎本身不凍結，以原始碼放在 `Contents/Resources/engine/src/asteria`（建置時預先編好 .pyc，執行時不寫 bytecode）。旁邊放 `engine/asset_library` 和 `engine/reference_projects/full_verification_demo`。引擎用 `__file__` 找的路徑因此都和原始碼目錄一樣，原有程式不用改。這包括素材庫、Full Verification 範本，以及匯出時複製引擎。
- 新模組 `src/asteria/frozen.py`：編輯器用 `sys.executable -m asteria.runtime.preview` 啟動試玩，用 `-m asteria.multiplayer.server` 啟動多人伺服器；kernel 檢查用 `-I -c`。在 app 裡 `sys.executable` 就是 app 本身，所以由 `run_python_style` 照 Python 的方式處理 `-m`、`-c` 和 `script.py`。`runtime_launcher.py`、`multiplayer_workspace.py` 都不用改。另有 `preview`／`export`／`upgrade` 子指令。
- 播放器 `AsteriaPlayer.app` 不含 Qt，放在 `Contents/Resources/player/`。`project_tools.build_player_game` 匯出時複製一份，改成遊戲名稱和 bundle id，把遊戲放進 `Contents/Resources/game`，再重新做 ad-hoc 簽章。在 Windows／Linux 上則產生 `Name/` 資料夾，裡面有改名的執行檔和 `game/`。
- app bundle 內不能寫入，所以遊戲從使用者資料夾的鏡像目錄執行（`~/Library/Application Support/Asteria Games/<名稱>`）。鏡像裡每一項都連結回 app，`saves/` 留在鏡像裡，換新版 app 後存檔還在。
- `package_game` 多了 `player` 參數和 `standalone` 結果。從 app 匯出時，預設不再產生 .pyz（它需要 Python）。Export Game 對話框會說明哪些產物需要 Python。

**驗證：**
- `tests/test_frozen_app.py`：8 項。涵蓋 `-m`／`-c`／script、內附遊戲的位置、鏡像目錄與存檔、匯出的 .app 與資料夾。加上匯出與 kernel 既有測試，共 36 passed。
- 凍結版在 repo 外執行，環境用 `env -i`（只有 `/usr/bin:/bin`，沒有 Python 路徑）：
  - `asteria.__file__` 指向 app 內的引擎，native kernel 從 app 內載入；
  - `-m asteria.runtime.preview` 跑 120 幀，結束碼 0；
  - `Asteria export … --app` 產生 `FV Quest.app`，`codesign --verify --deep --strict` 通過；
  - 匯出的遊戲跑 120 幀，結束碼 0，存檔資料夾建在使用者資料夾。
- `scripts/standalone_app_live_check.py` 由 app 本身執行，使用真實 Cocoa 視窗、靜音：編輯器開啟 Full Verification、▶ 試玩（8 秒後仍在跑，debug 通道有開）、匯出不需要 Python 的遊戲，遊戲以結束碼 0 結束。結果 **PASS**。截圖與結果在 `docs/audits/evidence/ast06/`。
- 試玩視窗：凍結版以 cocoa driver 存下自己第 90 幀的畫面（`frozen_playtest_window.png`）。匯出的遊戲用 `open` 啟動（等同 Finder 雙擊），會出現在最前面（`exported_game_window.png`）。
- 由背景程式（腳本、終端機）啟動的遊戲視窗會開在其他視窗後面。原始碼版做同樣測試也一樣，所以不是打包造成的，是 macOS 的視窗啟用規則。
- 檢查過程中出現 3 份 `Asteria` SIGABRT 當機報告，都來自檢查腳本早期版本收尾時只 `hide()` 視窗：QThread 還在跑時 widget 就被解構。改成 `close()` 後再跑，沒有新的報告。

**大小：** `Asteria.app` 277 MB（播放器 58 MB、引擎＋素材＋範例 83 MB）；zip 126 MB、dmg 158 MB。PySide6 外掛會帶進 QtQuick／QtQml／QtPdf／QtVirtualKeyboard。在 excludes 排除這些模組沒有效果，所以沒有保留。

**還沒做：**
- Developer ID 簽章與公證（需要帳號）。
- Windows／Linux 建置與 CI。
- 縮小 Qt 外掛。
- 網頁版匯出在 app 內不能用（需要 pygbag）。
- `multiplayer/project_demo.py` 預設的範例專案路徑在 app 內找不到（app 沒有帶 `arpg_multiplayer_demo`）。
- 人工在 Finder 雙擊 app、第一次右鍵打開的流程還沒有人實際做過。

**狀態：** 未提交（等使用者指示）。
