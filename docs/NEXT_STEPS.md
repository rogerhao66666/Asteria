# 接續工作說明（給在本機繼續的人，也給下一個 session）

**更新：** 2026-10-15。分支 `claude/confident-shannon-3ohnfj`。
最新實作與限制：看 [`audits/DECISION_LOG.md`](audits/DECISION_LOG.md) 的 **D30**；先前基線見 D26，
多人連線看
[`audits/MULTIPLAYER_DESIGN.md`](audits/MULTIPLAYER_DESIGN.md) §9，總覽看 [`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md)。

---

## 1. 在本機接續

```bash
git fetch origin
git checkout claude/confident-shannon-3ohnfj      # 或先合併進 main 再繼續
git config core.hooksPath .githooks               # 啟用 commit 檢查（見下）

python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[pygame,editor,mv,dev]"
QT_QPA_PLATFORM=offscreen python -m pytest -q      # 本次：2637 passed、1 warning
```

- 測試必須以 exit code 0 正常結束，且不能有 Qt／SDL／malloc 崩潰訊息；若出現就要修。
- 本次完整測試為 **2637 passed、1 warning**，沒有收尾崩潰；warning 是既有測試的
  `DeprecationWarning`。
- Cocoa 視窗已驗證 Octopath 戰鬥與勝利結算、CJK 訊息、音樂室／回想／名單、區域規則，
  以及 Skeleton 與 Terrain／Region／Doodad 面板；多人也以兩個 Cocoa 視窗連同機 server
  驗證。真人操作手感、實體鍵盤、手把和可聽音訊仍待人工確認。沒有第二台機器，真實
  WAN 量測未完成；區域蓋層在正確解析 TileMap 資源後的 Cocoa 畫面仍待補驗。
- 提交前：`ruff format .`、`ruff check --select E501 .`、`ruff check src tests scripts demos reference_projects`。
  每行 Python ≤ 99 字元。
- **commit 規則：** `.githooks/commit-msg` 要求作者是 `rogerhao66666` 且訊息**不能有 Co-Authored-By**。
  在你的機器上 git 身分本來就是你，直接 commit 即可。D26 的 7 個 commit 是這樣寫的。
- 專案慣例：結果寫進 `docs/audits/DECISION_LOG.md`（中文、說明做了什麼／證據／限制）。

### 讓下一個 AI session 接得上

開新 session 時貼這句就夠：

> 讀 `docs/NEXT_STEPS.md`、`docs/ENGINE_HANDBOOK.md` 和 `docs/audits/DECISION_LOG.md` 的 D30，然後繼續做 NEXT_STEPS 第 3 節的第 N 項。

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
| 地形鋪磚 | `graphics/autotile.py`、`editor/tile_edit.py`（`build_terrain_command`） | Tiles 面板 Terrain 筆刷與選單 |
| 尋路 | `runtime/navigation.py` | `find_path()`、`walk_to()`、世界指令 `WALK_TO` |
| 骨骼動畫 | `graphics/skeleton.py`、`runtime/skeleton_draw.py` | Skeleton 面板可編輯與預覽；`SkeletonAnimation2DComponent` 接進場景及測試 runtime |
| 多人連線補強 | `multiplayer/security.py`、`netsim.py`、`metrics.py`、`scripts/multiplayer_netbench.py` | `server.py`、`client.py` |

所有新規則都存在 `RpgDatabase` 的選填欄位（沒設定就不寫入，不升版本，舊專案照常載入）。

---

## 3. 本輪完成與尚待人工驗證

**A. 編輯器與骨骼（完成，D30）**

- 骨骼、變換、父子關係、動畫 Key 與緩動可在 Skeleton 面板編輯；每個操作走可復原指令，並可存回 Asteria JSON。
- 插槽精靈預覽、DragonBones 5.x 子集匯入及不支援部分回報已完成。
- 骨骼動畫 component 可保存／載入，在編輯器場景與 `PlayableTestRuntime` 播放及繪製。
- 區域畫筆與 `region:<id>` 的 `AreaRule` 編輯表單已合併到 Tiles 面板。
- Picture 指令參數編輯與圖片位置預覽已完成。

**B. 原生視窗驗證（功能畫面已驗證；人工手感仍待確認）**

- Cocoa 視窗實際跑過 `octopath_demo` 戰鬥與勝利結算、地板傷害／滑冰／腳步聲、Music
  Room、Backlog、Credits，以及 `\\C`、`\\I`、`\\V`、`\\N` 和 CJK 字型。
- Cocoa 編輯器已操作區域規則編輯／復原、Terrain／Region／Doodad 筆刷模式、Skeleton
  骨骼與 Key 編輯／復原；用 Diablo demo 的有效 TileMap sidecar 重跑後，區域 7 的數字
  和半透明蓋層亦在真實 Cocoa 畫面確認。
- SDL 鍵盤事件佇列、選單／存檔／設定等亦已在視窗驗證；CoreAudio 能開裝置並播放音效
  與串流音樂。但真人手按鍵盤、手把（當時沒有控制器連接）、主觀聽感與音訊延遲仍未驗收。

**C. 多人連線（雙視窗 loopback 驗證完成；WAN 未完成）**

- `SnapshotInterpolator` 與 `InputPredictor` 已接進 `runtime/multiplayer_preview.py`，並有自動化測試。
- 兩個原生 Cocoa runtime 視窗已連同一個 loopback server；兩端都看見 2 位玩家，各收到
  304 個遠端快照並套用本機預測。這是資料流／視窗整合驗證；真人主觀手感仍待確認。
- WAN 量測僅有單機 loopback，沒有第二台實體機器，跨機器結果未完成。
- NAT 穿透／配對與真正的 adapter 沙箱只新增設計決策，沒有實作。

**D. 其他先前完成項目**

- D26–D29 已完成的戰鬥規則、遊戲系統表單、筆刷、多人差量同步、圖片、裝飾物、戰鬥天氣、TP、Spine 匯入與訊息圖示仍維持完成；本輪全套測試通過。

---

## 4. 已經決定的事（不要重做）

- 美術：維持現有 CC0 素材（Ninja Adventure、Kenney），不買也不再找。付費素材絕對不能進 repo。
- 「Y 排序」不需要做：引擎已經用腳底 y 當 depth 排序精靈。
- Godot 的剛體物理刻意不做（文件寫只做 AABB 和圓形）。
