# Asteria 剩餘缺口整理與分批收尾設計

**日期：** 2026-10-15
**狀態：** 設計草案，待使用者審閱；尚未開始產品功能修改。

## 目標

把 Asteria 的「已完成、仍可在 repo 內完成、需要外部設備／服務、刻意不做」分開記錄，消除手冊、待辦文件、範本說明與稽核紀錄互相矛盾的地方；再依序完成證據確認後仍成立、可在本機完整驗收的工作。每項功能要有自動化測試；涉及編輯器或執行畫面的功能要以 macOS Cocoa 實際視窗驗收。

不把關鍵字搜尋不到直接當成功能不存在，也不把已完成項目重做。所有新增玩法規則仍以專案資料可設定為原則，不把隊伍 RPG 或 ARPG 的範例行為寫死進引擎。

## 現況基線與已知文件問題

- 分支為 `claude/confident-shannon-3ohnfj`，工作樹在開始檢查時乾淨，HEAD 為 `52394f0`。
- 在允許本機 loopback 的環境完整執行：`2637 passed, 1 warning`，退出碼 0，未見 Qt／SDL 收尾崩潰。唯一 warning 是 `tests/test_editor_brushes.py` 使用已棄用的 `QMouseEvent` 建構子。一般 sandbox 首次執行時，測試伺服器因 `PermissionError` 無法 bind loopback；該次結果不作為基線。
- `docs/NEXT_STEPS.md`、D30 與近期審計記載 Skeleton、Picture、Region UI、多人 TLS／token／平滑與四人本機驗收已完成。這些列為既有功能，不在此設計中重做。
- `docs/ENGINE_HANDBOOK.md` 同時把多項已完成功能列在「未完成」和 D26 已完成功能段落；需依程式碼、測試與最新證據統一狀態。
- `docs/templates/START_HERE_party_rpg.md` 和 `START_HERE_action_rpg.md` 仍寫 Game Start 沒有表單；目前 targeted scan 只找到 Game Start 資料模型／執行與 Problems 驗證，尚未找到 editor authoring form。實作前再完整追查 editor 路徑。
- `docs/audits/MULTIPLAYER_GAMEPLAY_TEMPLATE.md` 對 TLS／網際網路安全的說法需和 `MULTIPLAYER_DESIGN.md` §9 的已完成記錄對齊。
- `docs/audits/evidence/real_machine/results.json` 的 `vfx_moderngl_field` 記錄為 56.584 FPS（5 秒）；舊的 44–54 FPS 描述不可未核對就當成目前失敗。

## 分批方案

### 第 0 批：建立可相信的缺口清單

新增 `docs/audits/GAP_LIST.md` 作為剩餘工作單一入口。逐條回查實作、測試、現有設計決策與最新實機證據，標記：

- **已完成**：附程式碼／測試／實機證據位置；從待辦移出。
- **可在 repo 完成**：寫清楚缺少的行為、邊界與驗收條件。
- **外部條件未具備**：指出缺少的第二台機器、手把、真人聽感／操作、公開服務或帳號等。
- **刻意排除**：例如文件已決定不做的剛體物理；不得再當成待辦。
- **待查證**：目前只能說搜尋未找到，尚不能承諾實作或宣稱缺失。

更新 `NEXT_STEPS.md`、`ENGINE_HANDBOOK.md`、模板 `START_HERE`、多人設計／玩法模板及必要的稽核索引，讓它們引用同一份狀態，不複製過期清單。保留歷史決策紀錄的時間脈絡，不改寫成從未發生。

### 第 1 批：可用性與資料編輯

優先補上專案作者目前需要直接改 JSON／Code workspace 的基本作者流程：Game Start 表單（起始場景、隊伍／角色、背包及目前 schema 支援的寵物欄位）。先依現有 `GameStartDefinition` 與驗證規則定義 UI 欄位、無效資料回報、存檔／重開行為；不新增 Player Save 編輯功能。

寵物進化、學技能、親密度是另外的玩法資料與執行規則，不因 Game Start 表單順便塞入。先在缺口清單列出現有 schema／runtime 支援程度；只有確認設計可通用、可資料化後，才為該功能另開規格與計畫。

### 第 2 批：逐條核實的玩法規則缺口

對使用者提供的 YEP／Godot 對照清單逐項查證目前 engine、schema、editor 與測試。候選項目包括隊伍共用量表、商店條件價格、依 Region 設定戰鬥背景、STB／先制與偷襲語意、Steal／Snatch 差異，以及其他目前證據仍不足的條目。

只有確認缺失後才個別立項。每項規則都需以可序列化、可由遊戲專案覆寫的資料/API 呈現；不得只做在 demo。先測 runtime 規則，再加資料庫表單與 Party RPG／ARPG 相應的原生視窗驗收（若該功能有 UI）。

### 第 3 批：範本與可攜性

- 評估並補第三個可載入的範本（橫向平台動作或彈幕射擊，先由缺口盤點確認最能代表通用能力者）。素材優先沿用 repo 現有 CC0 資產或程式繪製，不加入付費素材；範本需能由 `New from Template` 建立、執行、保存，且有 `START_HERE.md`。
- 先針對 Web 匯出做 runtime/backend/輸入/音訊/檔案存取依賴盤點及最小技術驗證，再決定是否能形成可承諾的產品範圍。不可因「Godot 有」就直接承諾可行，也不可只加空白匯出按鈕。

### 第 4 批：效能及其餘本機可驗項目

`CollisionWorld.from_scene` 場景快取需先建立可重現 benchmark，設計 entity 啟用狀態、碰撞器增刪、場景切換與移動的失效測試；只有效益可量測且失效模型可靠才實作。既有決策紀錄顯示簡單批次建立未改善壓力場景，因此不能把未量測的 cache 當成必做修復。

完成仍成立且有明確 repo 驗收條件的文件／範本／runtime 工作後，更新總表與決策紀錄，跑完整 pytest、Ruff，以及相關壓力測試和 Cocoa 原生畫面驗收。

## 外部依賴及不作虛假驗收

以下列為外部依賴，這台工作站能做的自動化／本機部分仍先完成；缺少條件的結果明確標「未完成」：

- WAN 與跨機器量測、NAT 穿透、公網配對／relay：需要第二台可連線機器和／或外部服務。現有 loopback、雙視窗測試不能代替 WAN 證據。
- 手把、真人長時間鍵盤操作、主觀音質／延遲與真人視覺品質判斷：需要已接上的控制器或真人操作；功能測試不等同感官驗收。
- 公網身份／帳號、付費或持續營運服務：只寫出協定或本機原型不代表已具備 production service。
- 剛體物理與付費美術是已決定的排除項目。

## 驗收方式

1. 每個功能先增加會失敗的自動化測試，再實作；Python 檔案需符合 Ruff line length 99。graphics/runtime 不得依賴 editor。
2. 每個可交付項跑對應測試及 `ruff format`、`ruff check`；完成批次後跑完整 `pytest -q` 與 `ruff check src tests scripts demos reference_projects`，確認程序以正常退出結束且沒有 Qt／SDL 崩潰。
3. GUI／runtime 需要視覺驗收時，從已開啟的 Asteria checkout 的 VS Code integrated terminal 啟動 Cocoa 視窗，實際檢視並記錄操作步驟／結果；離屏測試只用於自動化。
4. 對可重現的畫面或操作問題補測試，修正後重跑相關驗收。
5. 文件寫明實際跑過的測試、原生視窗證據與仍受外部條件限制的項目；沒有第二台機器時不得聲稱 WAN 驗收完成。

## 交付順序

採用「第 0 批文件盤點 → 第 1 批 Game Start 作者流程 → 第 2 批經查證的規則缺口 → 第 3 批範本／Web 可攜性評估 → 第 4 批有量測依據的效能與其餘本機項目 → 完整驗證及狀態回報」。各批獨立規格、計畫與驗收；若某候選項目已存在、效益不足或依賴外部條件，從程式待辦移到正確狀態並說明證據，不為了清單看起來短而補造功能。
