# 接續工作說明（給在本機繼續的人，也給下一個 session）

**更新：** 2026-10-15。分支 `claude/confident-shannon-3ohnfj`（比 `main` 多 7 個 commit，沒有開 PR）。
做了什麼、為什麼、限制：看 [`audits/DECISION_LOG.md`](audits/DECISION_LOG.md) 的 **D26**，多人連線看
[`audits/MULTIPLAYER_DESIGN.md`](audits/MULTIPLAYER_DESIGN.md) §9，總覽看 [`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md)。

---

## 1. 在本機接續

```bash
git fetch origin
git checkout claude/confident-shannon-3ohnfj      # 或先合併進 main 再繼續
git config core.hooksPath .githooks               # 啟用 commit 檢查（見下）

python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[pygame,editor,mv,dev]"
QT_QPA_PLATFORM=offscreen python -m pytest -q      # 約 3–4 分鐘；預期 2441 passed、66 skipped
```

- 全套測試結束時印 `malloc_consolidate(): unaligned fastbin chunk detected` **不是**新問題：
  `main` 上一樣會（Qt／pygame 結束時的問題），測試結果本身是全過。
- `real_machine_validation.py`、Cocoa 視窗、手把、聽感這些要在你的 Mac 上跑，雲端環境沒有。
- 提交前：`ruff format .`、`ruff check --select E501 .`、`ruff check src tests scripts demos reference_projects`。
  每行 Python ≤ 99 字元。
- **commit 規則：** `.githooks/commit-msg` 要求作者是 `rogerhao66666` 且訊息**不能有 Co-Authored-By**。
  在你的機器上 git 身分本來就是你，直接 commit 即可。D26 的 7 個 commit 是這樣寫的。
- 專案慣例：結果寫進 `docs/audits/DECISION_LOG.md`（中文、說明做了什麼／證據／限制）。

### 讓下一個 AI session 接得上

開新 session 時貼這句就夠：

> 讀 `docs/NEXT_STEPS.md`、`docs/ENGINE_HANDBOOK.md` 和 `docs/audits/DECISION_LOG.md` 的 D26，然後繼續做 NEXT_STEPS 第 3 節的第 N 項。

這個 repo 沒有 CI（workflow 已被移除），所以「測試是綠的」要在本機確認。

---

## 2. D26 新增的檔案在哪

| 系統 | 資料／邏輯 | 接到哪裡 |
|---|---|---|
| 戰鬥規則擴充 | `rpg/battle_extensions.py`（嘲諷、吸血、過度擊殺、次數限制、熟練度、先制、偷竊、站位列標記） | `BattleRuntime(extensions=...)`；`GameSessionRuntime.steal()`、`extension_rules` |
| 敵人等級／難度 | `rpg/enemy_levels.py` | `GameSessionRuntime._enemy_member`、`set_difficulty()` |
| ATB／CTB | `rpg/battle_scheduler.py`：`gauge()`、`preview_order()`、`ATBClock` | continuous 排程器 |
| 勝利結算 | `rpg/victory.py`、`runtime/victory_screen.py` | manifest `battle.victory_aftermath: true` 才開 |
| 地圖規則 | `rpg/map_rules.py`、`runtime/map_rules_field.py` | `GameSessionRuntime.bind_map_rules()`、`TileMapField` |
| 事件計時器 | `events/timers.py` | 世界指令 `TIMER_START/STOP/PAUSE/RESUME/ADD` |
| 耐久／暱稱 | `rpg/durability.py`、`rpg/items.py`（`EquippedItem.durability`） | `wear_equipment()`、`repair_equipment()`、`rename_equipment()` |
| 拆解／職業點／新遊戲＋ | `rpg/disassembly.py`、`job_points.py`、`new_game_plus.py` | `disassemble()`、`finish_victory()`、`new_game_plus()` |
| 訊息／翻譯 | `presentation/message_codes.py`、`rpg/localization.py` | `expand_message()`、`tr()`、`set_locale()` |
| 記錄／音樂室／名單 | `runtime/backlog.py`、`rpg/extras.py`、`runtime/extras_screens.py` | 專案有資料才出現在暫停選單 |
| 地形鋪磚 | `graphics/autotile.py`、`editor/tile_edit.py`（`build_terrain_command`） | 還沒有按鈕 |
| 尋路 | `runtime/navigation.py` | `find_path()`、`walk_to()`、世界指令 `WALK_TO` |
| 骨骼動畫 | `graphics/skeleton.py`、`runtime/skeleton_draw.py` | 還沒接進場景或編輯器 |
| 多人連線補強 | `multiplayer/security.py`、`netsim.py`、`metrics.py`、`scripts/multiplayer_netbench.py` | `server.py`、`client.py` |

所有新規則都存在 `RpgDatabase` 的選填欄位（沒設定就不寫入，不升版本，舊專案照常載入）。

---

## 3. 還沒做的事（依我的建議順序）

**A. 編輯器介面（現在這些功能只能用資料或 Python 設定）**
1. 區域畫筆：在 Tiles 面板畫 `regions` 圖層（tile id＝區域編號），旁邊一張規則表（`AreaRule`）。
2. 地形筆刷按鈕：呼叫 `build_terrain_command`，tileset 面板可標記 `terrain` 和 `mask:<n>`。
3. Game Systems 下的表單：戰鬥擴充規則、敵人等級／難度、耐久、拆解配方、職業點、新遊戲＋、
   翻譯表、訊息設定、音樂室、製作人員名單。
4. 骨骼編輯器：骨骼、關鍵影格、預覽。

**B. 沒做的 YEP 項目**
5. 圖片點擊事件（PictureCommonEvents）、自由放置裝飾物（GridFreeDoodads）：Asteria 沒有「圖片」系統，
   要先決定是否引入。
6. 戰鬥天氣、EnhancedTP 的多種 TP 模式、DragonBones／Spine 匯入。

**C. 要在你的機器上驗證（雲端做不了）**
7. 勝利結算畫面、區域／滑冰／腳步聲、音樂室、訊息控制碼：在 Cocoa 真實視窗看一次畫面和手感。
8. 手把、實體鍵盤、聽感、目視（原本審計的 B 項）。
9. 耐久破損目前在**下一場戰鬥**才影響戰鬥數值（進行中的戰鬥維持原數值）：想要即時生效再改。

**D. 多人連線**
10. ~~差量更新~~ 已完成（D27，頻寬降到約 1/4）。
11. 把 `multiplayer/smoothing.py` 的插值與預測接進 `runtime/multiplayer_preview.py`，並在真實視窗調手感（工具已寫好、有測試，還沒接）。
12. 真實跨機器 WAN 量測（`python scripts/multiplayer_netbench.py` 只量了單機迴圈回送）。
13. NAT 穿透／配對、真正的 adapter 沙箱（白名單只限制載入什麼）。

**E. 小問題**
14. `reference_projects/diablo_multiplayer_demo/build_project.py` 第 14–15 行超過 99 字元
    （你上一個 commit 帶來的，`ruff check --select E501` 會報）。
15. 訊息控制碼的圖示 `\I[n]` 目前畫成方框；CJK 文字要確認字型。

---

## 4. 已經決定的事（不要重做）

- 美術：維持現有 CC0 素材（Ninja Adventure、Kenney），不買也不再找。付費素材絕對不能進 repo。
- 「Y 排序」不需要做：引擎已經用腳底 y 當 depth 排序精靈。
- Godot 的剛體物理刻意不做（文件寫只做 AABB 和圓形）。
