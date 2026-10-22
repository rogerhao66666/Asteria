# 接續工作說明（給在本機繼續的人，也給下一個 session）

**更新：** 2026-10-22。分支 `main`（直接在 main 上提交，不開分支）。
現況總覽看 [`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md)；最新的決策與證據看
[`audits/DECISION_LOG.md`](audits/DECISION_LOG.md) 的 **D42–D51**（D41 是對話肖像）；缺口對照表
[`audits/GAP_LIST.md`](audits/GAP_LIST.md)；多人連線看 [`audits/MULTIPLAYER_DESIGN.md`](audits/MULTIPLAYER_DESIGN.md) §9。

---

## 1. 在本機接續

```bash
git config core.hooksPath .githooks               # 啟用 commit 檢查（見下）
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[pygame,editor,mv,dev]"
python -m asteria.kernels.build_native            # C++ kernel（ABI 5；沒編也能跑，退回 numpy／python）
python -m pytest -q                               # 2026-10-22 的 HEAD：3096 passed、1 skipped，約 5 分鐘
```

- 測試必須以 exit code 0 結束，且不能有 Qt／SDL／malloc 崩潰訊息。
- 提交前：`ruff format .`、`ruff check --select E501 .`、`ruff check src tests scripts demos reference_projects`；
  每行 Python ≤ 99 字元。
- **commit 規則：** `.githooks/commit-msg` 要求作者是 `rogerhao66666`，訊息**不能有 Co-Authored-By**；
  不 push、不改寫歷史，除非使用者要求。
- 每一批的結果寫進 DECISION_LOG（中文，六段：要求、做了什麼、測試、實機證據、限制、狀態）；UI 與實機的東西
  在 Cocoa 視窗驗證，截圖放 `docs/audits/evidence/real_machine/`。
- 同一個資料夾常有幾個 session 同時在改：只提交自己改的檔案；實機截圖從 HEAD 的乾淨副本拍（手冊 §8）。

### 讓下一個 AI session 接得上

開新 session 時貼這句就夠：

> 讀 `docs/NEXT_STEPS.md`、`docs/ENGINE_HANDBOOK.md` 和 `docs/audits/DECISION_LOG.md` 的 D42–D51，然後做 NEXT_STEPS 第 2 節的第 N 項。

這個 repo 沒有 CI，「測試是綠的」要在本機確認。

---

## 2. 還沒做的（2026-10-22）

**A. 重拍證據時發現的問題：已修（DECISION_LOG D51 補充）**

拉近時的狀態文字、選中技能列的名稱與花費、狀態畫面的 HP／MP 順序、編輯器兩處被截的文字、
`test_skeleton_component` 的測試順序依賴；修正後的證據 `audits/evidence/real_machine/d51_*_fixed.*`。

**B. 等使用者決定**

- 頭上名字超過 14 字會縮成縮寫（「Goblin Slinger 2」→「GS2」）：要顯示全名（小字或兩行）、保留最後一個字
  加編號，還是放不下就不顯示。

**C. 進行中或下一步**

- 遊戲內建字詞已接上專案的翻譯表（D52，手冊 3.7；Full Verification 可切成繁體中文）。下一步可做專案資料的
  翻譯（角色、技能、道具、狀態、敵人的名稱與說明依語系不同），以及寵物改名的中文輸入法組字。
- 編輯器剩下的英文：顯示的字就是存檔值的固定選項（Enemy AI 的條件／動作／目標、事件觸發
  Action／Autorun／Parallel、VFX 錨點與混合），要把顯示和值分開。

**D. 需要真人或外部條件**

- 在真的輕量電腦或低耗電模式下玩一輪（效能只在本機量過）。
- 實體鍵盤、手把、音效聽感與延遲（實機清單裡需要真人的 4 項）。
- 多人連線的 WAN 量測（沒有第二台機器）、公開部署、TLS、登入驗證。

**E. 使用者說先不做**

- 第三個範本、Web 匯出、手繪技能圖示（2026-10-16）；載具（A18）不做。

---

## 3. 已經決定的事（不要重做）

- 美術：主要用 Foozle Lucifer（CC0，在 `asset_library/`）；Ninja Adventure、Kenney 只補缺。只收授權允許重新
  散布的素材（CC0 或 CC-BY，寫進 CREDITS）；不用 AI 美術；購買由使用者自己做。
- 編輯器介面預設英文，可即時切換繁體中文；作者的資料不翻。
- 效能交給引擎底層（kernel、繪製快取），上層保持簡單的 Python 給使用者寫。
- 碰撞世界跟著場景就地更新：2026-10-20 使用者核准（推翻 D34 的「不做」）。
- 戰鬥外的精煉每次用新的亂數（是設計）；測試或重播要可重現就設 `game.refine_rng`。
- 「Y 排序」不需要做：引擎已經用腳底 y 當 depth 排序精靈。
- Godot 的剛體物理刻意不做（只做 AABB 和圓形）。

2026-10-15 版本的 D26 檔案對照表與 D30 驗證紀錄，在 git 歷史與 DECISION_LOG D26–D30。
