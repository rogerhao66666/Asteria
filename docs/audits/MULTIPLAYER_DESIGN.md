# Asteria 多人連線能力設計提案

**日期：** 2026-10-15
**狀態：** 通用連線、SQLite、可編輯規則模板及完整原 ECS 遊戲副本已完成四人原生驗收；本機／可信任 LAN 開發範圍。
**首個驗證案例：** Diablo 式即時 ARPG 合作打 Boss。此案例用來驗證多人連線，不限制功能只能用於 ARPG。
**關聯：** `docs/audits/ARPG_DESIGN.md` §7、§8；原 D22 將多人連線排除在 ARPG 計畫批次之外，本提案另記錄引擎層的通用能力。

### 目前原型進度（2026-10-15）

- 已加入版本化 JSON Lines 協定、TCP session/lobby server、client API、`GameNetworkAdapter` 介面，以及 headless server 啟動方式。
- 即時遊戲 adapter 可選擇實作 `network_tick(dt)` 與 `network_tick_interval`，讓 server 按 adapter 設定推進權威模擬；回合制 adapter 不需 tick hook。
- 編輯器新增 Multiplayer workspace，可啟停本機 server、加入場次、查看參與者、ping server、送出 adapter command 並檢視權威 state/event；連線設定存入專案的 `.asteria/multiplayer.json`。
- 提供通用 shared-counter adapter（`asteria.multiplayer.examples:build_counter_adapter`），可在 GUI 一鍵套用並從一個或多個 client 驗證伺服器命令裁定。
- 即時遊戲可實作 `handle_input(player_id, input_state)`；每位玩家有獨立輸入序號和 60 frame／秒上限，server 會回覆接受或拒絕及原因。
- Counter 與 Movement adapter 分別展示權威指令和即時移動；Boss Co-op adapter 位於 `asteria.multiplayer.boss_demo:build_boss_adapter`，最多四位玩家可各自移動／攻擊同一隻伺服器權威 Boss。範例含仇恨選目標、三個階段、第三階段範圍攻擊、倒地／隊友救援和只結算一次的獎勵。
- Network Position Preview 會顯示帶有 x/y 的玩家；Boss 範例另外顯示 Boss 方形標記與目前 HP。實際遊戲素材仍由遊戲 runtime 繪製。
- 本機 server 可指定 SQLite database；編輯器預設放在專案 `.asteria/multiplayer.sqlite3`。玩家的 Guest ID 保存在 Connection Profile，重連會取回伺服器端經驗、遊戲 JSON state 和 inventory。Guest ID 是可更改的 guest key，沒有密碼、驗證或防冒用能力。
- Multiplayer 的 **Game Rules Template** 可編輯／驗證專案 `.asteria/multiplayer-rules.json`。Boss 預設只把伺服器接受的正傷害當作參與：設定 100 XP 時，每位符合條件的玩家各得完整 100 XP，不會平均分配；每一項 Boss 掉落各自隨機派給一位有造成傷害的玩家。個人拾取、指定持有人、先到先得、輪替與隨機持有人可由 SQLite world-drop API 原子裁定。
- `reference_projects/diablo_multiplayer_demo` 是離線 demo 的獨立副本，預載 `asteria.multiplayer.project_demo:build_project_adapter`。server 透過 `--project` 載入實際選定專案；原 ECS 戰鬥、技能、NPC、商店、製作、場景、背包、裝備與角色存檔由 server 裁定並同步。
- Server 會先驗證 adapter state/event 可編碼成協定上限內的嚴格 JSON，再增加 revision 和發布；過期輸入、重播命令、超速輸入、NaN／Infinity 會被拒絕。
- loopback 測試涵蓋兩 client Boss 戰、全額 per-player XP、未參戰者排除、規則覆寫、穩定 Guest ID、SQLite 重開恢復、多人競搶／個人掉落、重複 operation 與 editor 實際啟動本機 server。
- 最新驗證：完整回歸 **2307 passed（154.86s）**；四個獨立 Cocoa 遊戲程序擊殺原始 900 HP Cyclops，四位參與者各得 100 XP，原掉落由持有人拾取並穿戴，SQLite 重開保存資料。輸入由驗證程式送出。
- 連線副本接收權威 ECS 快照，原遊戲 UI 送出命令；F5／存讀檔走 server，斷線暫停並以 F3 重連。詳見 [可載入遊戲模板](MULTIPLAYER_GAMEPLAY_TEMPLATE.md)。
- Cocoa 原生編輯器自動化控制驗收：Host／Join／Ping／Leave／Stop、Profile 保存及 Save Profile 幾何置中均通過。
- 安全與網路品質補強（2026-10-15，見下方「N3 補強」）：TLS、簽章 token 身分驗證、對外暴露防護、adapter 載入白名單、丟包／延遲／抖動模擬、缺口偵測與重新同步、CPU／頻寬量測都已完成。仍未完成：NAT relay／配對、真正的 adapter 沙箱（白名單只限制能載入什麼，不限制載入後的程式做什麼）、跨機器 WAN 實測。
- 預設仍是本機開發設定；要對外開放必須啟用 TLS 與 token（見「N3 補強」），否則 server 拒絕監聽 127.0.0.1 以外的位址。

---

## 1. 目標與邊界

讓任何 Asteria 遊戲專案都能選擇導入多人連線能力，並由作者啟動或部署自己的遊戲伺服器。連線基礎應跨遊戲類型共用；各遊戲以 adapter 接上自己的模擬、指令和狀態。離線遊戲仍可使用 Asteria，不需載入連線依賴。

### 通用連線能力

- 建立和管理連線場次、參與者身分、加入／離開與連線狀態。
- 提供伺服器與客戶端之間的訊息傳輸、遊戲指令驗證、狀態／事件同步和權限邊界。
- 允許遊戲 adapter 選擇適合玩法的同步方式：即時遊戲可同步輸入與狀態，回合制遊戲可同步指令與結果，其他玩法可定義自己的狀態和事件。
- 提供可選套件、客戶端 API、headless server 啟動方式、範例和部署文件。
- 首個端到端驗證採 2–4 位玩家共同進入 Diablo 式 ARPG 場景並擊敗同一隻 Boss。

連線套件提供通用網路與場次基礎；每個遊戲仍需提供 adapter，將自身規則接到連線命令和狀態同步介面。第一個 ARPG adapter 是驗證案例，不代表通用連線層依賴 RPG、戰鬥或 Boss 資料。

### 本提案不涵蓋

- 大型 MMO 世界、數百至數千名同場玩家、分片或持久常駐世界。
- Asteria 代管的伺服器、帳號系統、公開配對、好友、聊天或公會服務。
- 完整防作弊產品或商業級營運後台。

這些服務需要另外規劃產品範圍、伺服器營運和安全設計。

---

## 2. 建議架構：通用連線層與遊戲 Adapter

建議提供選配的 Multiplayer Runtime，負責連線、場次、參與者身分、訊息傳輸、權限、同步和伺服器啟動。遊戲 adapter 負責將自己的規則接入這些介面。伺服器是權威狀態來源；權威遊戲模擬由 server runtime 執行對應 adapter。即時遊戲可實作 `TickableGameNetworkAdapter`，設定 `network_tick_interval`（目前限制 1/120 至 1 秒）並於 `network_tick(dt)` 推進固定步長。Adapter 可在模擬步不需發布快照時回傳 `None`；回合制遊戲只需處理命令，不會被強制套用固定更新頻率。

### 通用連線層負責

- 建立場次、指派網路 ID、處理加入／離開、斷線與訊息順序。
- 驗證參與者是否有權送出特定指令，檢查訊息格式、速率和序號。
- 傳遞遊戲 adapter 定義的指令、狀態快照和事件；去重已處理訊息。
- 提供 server／client lifecycle、可替換的 transport 介面和網路診斷資訊。

### 遊戲 Adapter 負責

- 定義遊戲狀態、可接受的玩家指令、規則驗證，以及伺服器如何推進或裁定狀態。
- 選擇適合玩法的同步模型。即時遊戲可採固定步進、輸入序號、快照與本機預測；回合制遊戲可採命令提交、回合解析和結果事件；其他遊戲可實作自己的 command/state/event 流程。
- 將遊戲狀態轉成可同步資料，並從伺服器確認的結果更新遊戲世界。
- 定義斷線時玩家、局內進度、存檔和獎勵如何處理。

### 自訂 Adapter 最小範例

把 adapter 放在遊戲專案的 Python import path 中，例如專案根目錄的 `network_game.py`。GUI 的
**Game Adapter** 欄位填 `network_game:build_adapter`；headless server 則用同一個 factory spec：

```python
from collections.abc import Mapping

from asteria.multiplayer import AdapterUpdate


class NetworkGame:
    def __init__(self):
        self.turn = 0
        self.players = {}

    def initial_state(self) -> Mapping:
        return {"turn": self.turn, "players": dict(self.players)}

    def on_player_joined(self, player_id: str, display_name: str):
        self.players[player_id] = display_name
        return AdapterUpdate(
            state=self.initial_state(),
            events=({"type": "player_joined", "player_id": player_id},),
        )

    def handle_command(self, player_id: str, command: str, payload: Mapping):
        if player_id not in self.players:
            raise ValueError("player is not in the session")
        if command != "advance_turn":
            raise ValueError("unsupported command")
        self.turn += 1
        return AdapterUpdate(
            state=self.initial_state(),
            events=({"type": "turn_advanced", "turn": self.turn},),
        )

    def on_player_left(self, player_id: str):
        self.players.pop(player_id, None)
        return AdapterUpdate(
            state=self.initial_state(),
            events=({"type": "player_left", "player_id": player_id},),
        )


def build_adapter():
    return NetworkGame()
```

Client code can use the same protocol from the game loop. Network callbacks run on a background
thread, so queue messages there and apply them on the runtime's own update thread:

```python
from queue import SimpleQueue

from asteria.multiplayer import MultiplayerClient

incoming = SimpleQueue()
client = MultiplayerClient(on_message=incoming.put)
welcome = client.connect("127.0.0.1", 8765, "Player")
client.send_command("advance_turn", {})

# Call this drain step from the game's main/update loop.
while not incoming.empty():
    network_message = incoming.get()
    if network_message.get("type") == "game_update":
        apply_authoritative_state(
            network_message.get("state"), network_message.get("events", ())
        )

client.close()
```

`apply_authoritative_state` is the game project's own bridge into its scene/runtime. The generic
client does not instantiate actors or mutate a game's world automatically.

### 客戶端負責

- 收集並傳送目前遊戲 adapter 定義的輸入或指令。
- 顯示伺服器同步的狀態與事件。即時玩法可加入本機預測、校正和遠端插值；非即時玩法依遊戲流程呈現權威結果。
- 將命中、傷害、掉落、回合結果等遊戲規則交由伺服器端 adapter 裁定，避免客戶端直接指定權威結果。

通用網路層不應固定 60 Hz 或要求所有遊戲使用相同的傳輸語意。即時 adapter 可依遊戲設定 server tick 與狀態發布節奏；範例每秒模擬 20 次，輸入 frame 最多每秒 60 次。回合制或其他遊戲依其規則採合適的節奏。目前原型用 TCP 傳輸 JSON Lines，供 session、lobby 與初步 adapter API 驗證；server 對同場最多 64 條連線設上限、hello 握手限時 5 秒。這是資源保護，不代表產品已支援 64 位玩家。是否適合即時遊戲及是否需要其他 transport，仍要經過延遲、頻寬和封包行為量測後決定。

第一版不要求跨機器 bitwise deterministic simulation，也不先承諾 rollback netcode。

---

## 3. 在 Asteria 的整合方式

### 選配套件，而非強制引擎依賴

連線 API 應由遊戲專案明確安裝和匯入；離線使用 Asteria 不需安裝或載入它。初期可作為獨立 Python 套件或可選 extra。一般 Plugin Runtime 尚屬另一項未實作的能力，因此連線套件不應依賴尚不存在的通用外掛系統。

套件需提供：

- Client session API：設定 server address、加入／離開場次、讀取連線狀態。
- `GameNetworkAdapter` 介面：註冊遊戲命令、伺服器端驗證／推進邏輯，以及同步狀態和事件。
- 可選的即時輸入介面：`handle_input(player_id, input_state)` 驗證並儲存玩家最新輸入；若同時實作 `TickableGameNetworkAdapter`，server 會在權威 tick 中推進遊戲模擬。
- Headless server entry point：讀取專案資料、載入指定 adapter、建立場次並執行權威遊戲邏輯。
- 可替換的 transport 介面，讓網路機制不進入 Core、RPG 或戰鬥規則。
- 範例專案、設定說明與伺服器部署／啟動說明。

### 目前的引擎整合缺口

目前 runtime 和 ARPG 參考執行路徑仍以單一玩家為中心。ARPG 的 `GameSessionRuntime` 有單一 `player`／`save`，玩家輸入系統只驅動該玩家，場景 AI 預設也以單一玩家為目標。這些是第一個 ARPG 驗證案例要處理的現況，不是通用連線層對遊戲類型的限制。

多人能力需先讓場次世界狀態和每位參與者的輸入／擁有權分開，再由各遊戲 adapter 管理自己的存檔與規則。網路識別、同步訊息和場次生命週期應保持通用，不把 Diablo、特定職業、Boss 或遊戲服務商寫死在 Core。

### 開發原型的操作方式

1. 在 Asteria Editor 開啟專案，切到 **Multiplayer**（`Ctrl+7`）。
2. 選 **Use Counter Demo**、**Use Movement Demo** 或 **Use Boss Co-op Demo**，再點 **Start Local Server**。Boss 範例會載入 `asteria.multiplayer.boss_demo:build_boss_adapter`，預設持續攻擊；可編輯輸入 JSON 加入 `move_x`／`move_y`。
3. 點 **Join Session**，確認玩家名單和初始 state 出現。計數器範例使用 **Send Game Command**；移動範例使用 **Send Input State**，預設向右持續移動，按 **Stop Input** 傳送零軸狀態。
4. 第二個 client 可用另一個 Editor 視窗或 `MultiplayerClient` API 連到相同位址／port；Boss 範例中每個 client 只控制自己的角色，兩端收到同一份 Boss HP／階段／玩家狀態。輸入持續生效，直到 client 傳送新狀態或離開。
5. Guest ID 預設由 Connection Profile 保存；同一台機器開第二個測試 client 時，先按 **New ID** 避免重複。此 ID 只用來找回 SQLite guest state，不是登入驗證。Boss 倒地玩家附近的隊友可在 Command 填 `revive`，Payload 填 `{"target_player_id":"<倒地玩家 ID>"}` 來救援。完成後先 **Leave Session**，再 **Stop Server**。
6. 預設 Boss 獎勵是每位正傷害參與者各得設定的完整 XP（100），每一項掉落隨機給一位正傷害參與者。開啟 Game Rules Template 可修改 eligibility、XP 數值、Boss 掉落分配和 world pickup policy，再按 **Save Project Rules**；自訂 adapter 可採用其他任意遊戲規則。

### Diablo 多人地圖預覽操作

1. 在 Editor 開啟 `reference_projects/diablo_multiplayer_demo/project.asteria.json`，切到 Multiplayer。
2. 確認 **Connect Run Project to this multiplayer session** 已勾選，保留副本的 project adapter，按 **Start Local Server**。
3. 按 **Run Project** 開始遊戲；使用原綁定移動、J 攻擊、F 拾取（G 亦可）、B 背包、F5 存檔及 F3 斷線重連。
4. 測第二名玩家時，另開一個 Editor／專案副本，先在 Multiplayer 按 **New ID** 並儲存 profile，再連到相同 server 後 Run Project。不要讓兩個 client 共用 Guest ID。
5. server 接受至少一次正傷害的玩家都各得完整設定 XP：預設 100 XP 表示每位符合條件者各拿 100，不除以隊伍人數。每個 Boss 掉落各自隨機分配給其中一位參與者；SQLite 會保存 adapter 獎勵。

這個流程同步原始 ECS 與每位玩家 RPG 存檔。角色資料持久保存；server 重開會重建場次 AI／生成計時／未拾取掉落。詳見 [模板與保存方式](MULTIPLAYER_GAMEPLAY_TEMPLATE.md)。

也可用 headless CLI 啟動範例 server：

```sh
python -m asteria.multiplayer.server \
  --host 127.0.0.1 --port 8765 \
  --adapter asteria.multiplayer.examples:build_movement_adapter \
  --database .asteria/multiplayer.sqlite3 \
  --rules .asteria/multiplayer-rules.json
```

這是本機開發流程。公開配對與 NAT relay 仍未提供。要讓 LAN／Internet 的玩家連線，請看下一節「N3 補強」。

---

## 4. 建議的實作階段

| 階段 | 內容 | 驗收證據 |
|---|---|---|
| **N0 技術驗證** | 兩個獨立 client 程序連到本機 headless server；使用最小測試 adapter 驗證場次、身分、指令、狀態／事件往返和斷線 | 兩端收到同一份伺服器權威狀態；可注入延遲、抖動和封包遺失；記錄 CPU、頻寬和修正次數 |
| **N1 通用連線 API** | 場次生命週期、參與者擁有權、通用 command/state/event 介面、adapter 載入和 server 驗證；離線路徑維持可用 | 測試 adapter 可連線並同步其自訂資料；連線核心不需匯入 ARPG 或 RPG 模組 |
| **N2 首個遊戲整合案例** | 以 Diablo 式 ARPG Demo 撰寫第一個 adapter；接上多玩家輸入、Boss AI 多目標／仇恨、權威命中與傷害、階段事件、死亡／復活和戰利品結算 | 2–4 位玩家擊敗同一隻 Boss；各 client 的生命與階段最終一致；命中、死亡和掉落不重複結算 |
| **N3 網路手感與容錯** | 依遊戲 adapter 的同步模型實作必要的預測／插值、超時、斷線處理和重連；對即時案例做延遲測試 | ARPG 案例在明確記錄的 RTT、抖動和丟包條件下完成 Boss 戰；無永久狀態分歧，連線恢復後可繼續操作 |
| **N4 可導入交付** | 套件安裝、作者 API、adapter 範例、headless server 啟動器、文件和發佈包 | 新專案依文件安裝套件、實作或載入 adapter、啟動 server，讓兩個 client 完成多人遊戲流程；沒有套件的專案仍能離線遊玩 |

目前 Counter、Movement 與 Boss adapter 都可由 GUI 或 `MultiplayerClient` 操作；自動化 loopback 測試覆蓋兩 client 的共享權威 Boss 戰。Ping Server 顯示單次 round-trip latency；尚未注入延遲／抖動／應用訊息遺失，也尚未量測 CPU／頻寬，因此不代表 WAN 品質驗收已完成。

先在本機多程序完成 N0–N2，再逐步加入跨網路測試。網路品質驗收依玩法訂定：即時案例記錄 LAN 與 WAN 條件；回合制等非即時案例驗證指令順序和結果一致性。

---

## 5. 第一版驗收條件草案

1. 兩個以上 client 可加入同一個 headless server；第一個 ARPG 驗證案例最多四位玩家。
2. 通用 session／network ID 不依賴遊戲角色型別；只有有權控制對應參與者的 client 可送出其指令。
3. 每個遊戲透過 adapter 定義自己的命令、驗證和權威狀態；伺服器拒絕未授權或無效的命令。
4. 重送封包不會讓已處理命令重複套用；各 client 最終收到一致的伺服器確認狀態或事件。
5. 遊戲客戶端不能直接指定其 adapter 定義為權威的結果；ARPG 案例的 Boss HP、傷害和掉落由伺服器裁定。
6. 一位玩家斷線時，該場次依遊戲 adapter 的政策移除、暫停或接管該參與者；其他玩家可依政策繼續。
7. 離線遊戲與未安裝連線套件的專案不受新增套件影響。
8. 通用連線核心不依賴 ARPG 專用資料；文件能讓作者安裝套件、提供 adapter、啟動伺服器並完成多人流程。

---

## 6. 後續發佈前仍需決定

- **伺服器模式：** 目前原型使用獨立 headless server；是否另外支援一位玩家同時當 host 和 client，需考量 host 對權威狀態的控制與斷線風險。
- **遊戲狀態保存：** 場次結束後保留哪些資料、由遊戲 adapter 如何接到各遊戲自己的 save 格式。
- **場次加入時機：** 是否允許遊戲中途加入；重連後如何恢復參與者狀態，由連線核心和遊戲 adapter 分工。
- **連線範圍：** 第一版是同區域網路加上可手動連線的 Internet server，還是只驗證 LAN。若要穿越 NAT 而不設定 port forwarding，通常還需另建 relay／配對服務。
- **同步模型：** 原型提供 command/state/event adapter hook；第一個 ARPG adapter 預計使用即時輸入與狀態快照，其他遊戲可使用指令／事件流程。需以實際遊戲確認通用 API 對這些需求是否足夠。
- **權威邊界：** 各遊戲可設定哪些狀態由 server 裁定；第一版建議 server authoritative，之後再依玩法評估 host-authoritative 等模式。

---

## 7. 風險與明確不承諾

- **不同玩法需要不同同步模型：** 通用連線核心應提供穩定介面，但不把所有遊戲強行轉成固定頻率的位置同步。
- **即時手感需獨立測量：** 本機 60 fps 不等於 WAN 操作流暢；預測、伺服器校正和遠端插值需要在封包延遲下驗證。回合制等玩法則有不同的品質指標。
- **遊戲規則仍需伺服器驗證：** 權威結果由各遊戲 adapter 定義和裁定。第一個 ARPG 案例需處理 Boss 多目標選擇與戰利品權威；其他遊戲依其規則處理。
- **伺服器執行使用者專案程式有安全界線：** 開放 server hosting 前需限制可載入內容、檔案存取與連線輸入；此提案不宣稱已完成沙箱或商業級防作弊。
- **營運成本不隨套件消失：** 作者仍要自行提供可連線的 server。Asteria 第一版不提供帳號、配對、relay、雲端保存或 uptime 保證。
- **不需先引入 C++：** 第一版的主要風險在連線邊界、各遊戲權威模擬和同步手感，不是計算 kernel。只有量測證明 server simulation 是瓶頸後才評估 native code。
- **不依賴正式美術包：** 可用現有 Diablo Demo 資料驗證網路流程；多人連線核心適用於其他遊戲，驗收不要求先完成 Asteria Starter art。

---

## 8. 範圍紀錄

D22 原 ARPG 計畫把該計畫中的多人連線實作列為「不在這次範圍」。2026-10-14 使用者進一步說明，多人連線應是 Asteria 各類遊戲皆可導入的通用能力；Diablo 式 ARPG 合作打 Boss 只是第一個驗證案例。本文件因此記錄引擎層的通用連線方向，不把能力範圍限定為 ARPG。TCP 原型與 GUI lobby 已開始實作；場次狀態保存、正式同步模型、網路品質門檻和產品化部署仍待後續驗證與決策。


---

## 9. N3 補強：安全與網路品質（2026-10-15）

### 9.1 對外暴露防護、TLS 與身分驗證

- **暴露防護：** server 只接受監聽 `127.0.0.1`／`localhost`／`::1`；要監聽其他位址，必須同時啟用 TLS 與 token，或明確傳 `--insecure-lan`（可信任網路）。編輯器選擇非本機位址時會自動帶 `--insecure-lan` 並在 Log 顯示警告——這是使用者明確的選擇，不是預設。
- **TLS：** `--tls-cert cert.pem --tls-key key.pem`。每條連線在讀取任何資料前先做 TLS 握手（TLS 1.2 以上）。Client：`connect(..., tls=True, cafile="cert.pem")` 會驗證憑證與主機名稱；`tls=client_context(verify=False)` 只供拋棄式測試憑證使用。
- **Token：** 簽章 token（HMAC-SHA256），格式 `<player>.<到期時間>.<簽章>`。server 以 `--auth-secret-file`（至少 16 位元組）啟用；`hello` 必須帶 `token`，token 的玩家必須和 `guest_id` 相符（沒帶 `guest_id` 時以 token 為準）。偽造、過期、改名、改到期時間的 token 都會被拒絕。發放：`python -m asteria.multiplayer.security issue --secret-file secret.txt --player alice --hours 24`。Client：`connect(..., token=...)`。
- **Adapter 白名單：** `--adapter-allow asteria.multiplayer --adapter-allow mygame`（可重複）只允許從這些模組前綴載入 adapter。**這不是沙箱**：載入後的 Python 程式仍擁有 server 行程的所有權限；它只防止 server 被指示去載入任意模組。
- 範例（對外開放）：

```sh
python -m asteria.multiplayer.server --host 0.0.0.0 --port 8765 \
  --adapter asteria.multiplayer.boss_demo:build_boss_adapter --adapter-allow asteria.multiplayer \
  --tls-cert cert.pem --tls-key key.pem --auth-secret-file secret.txt --metrics-file metrics.json
```

### 9.2 缺口偵測與重新同步

`game_update` 的 `revision` 逐一遞增。client 發現缺號（或 `pong` 顯示 server 的 revision 更新）會送 `resync_request`，server 回一則 `resync: true` 的 `game_update`（目前完整狀態）。每位玩家 0.25 秒內只受理一次（`resync rate` 計入拒絕）。`connect(..., heartbeat=0.5)` 會定時 ping，補抓「最後一則更新遺失」的情況。`client.gaps` 記錄遺失次數。

### 9.3 網路模擬與量測

- `asteria.multiplayer.netsim.LinkSimulator`：以 JSON 行為單位的 TCP 代理，可設定單向延遲、抖動、丟包（整則訊息；握手不丟）與頻寬上限；保持順序。
- `server.metrics_snapshot()` / `--metrics-file`：各類訊息數與位元組、tick 平均／最差耗時、tick CPU 佔比、拒絕原因、尖峰人數。
- `scripts/multiplayer_netbench.py`：4 位玩家打 Boss 的量測。**迴圈回送（loopback）、client 與 server 在同一台機器同一行程**，所以 CPU 是上限而非專用主機的數字；頻寬是 server 實際寫出的位元組。本機結果（每個設定跑 6 秒）：

| 連線設定 | server 送出（位元組／秒／人） | tick 平均／最差（ms） | tick CPU 佔比 | client 偵測到的缺口 | 代理丟掉的訊息 | 最終 Boss 血量一致 |
|---|---|---|---|---|---|---|
| ideal | 42,312 | 0.508 / 1.874 | 1.0% | 0 | 0 | 是 |
| lan 5ms | 42,318 | 0.536 / 2.374 | 1.1% | 0 | 0 | 是 |
| wan 60ms | 39,811 | 0.571 / 3.051 | 1.1% | 0 | 0 | 是 |
| bad wan 120ms 5% loss | 37,960 | 0.645 / 6.703 | 1.3% | 19 | 80 | 是 |

**誠實說明：**
- 每個 tick 都送完整狀態（含戰鬥紀錄），約 40 KB／秒／人（約 320 kbps）。這是已知的成本；差量更新（delta）尚未做，玩家多或網路窄時是第一個要改的地方。
- 「Boss 血量一致」比較的是 Boss 死亡這個最終結果；玩法中途的瞬時位置在不良連線上會落後一到數個 tick，沒有做本機預測與遠端插值（這屬於遊戲畫面端，仍待做）。
- 丟包模擬丟的是整則訊息（像 UDP），比真正的 TCP 丟包更嚴苛；TCP 實際表現是延遲尖峰而不是缺口。
- 跨機器、跨網路（真實 WAN）的測量尚未做。
