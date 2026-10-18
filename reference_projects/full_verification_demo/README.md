# Full Verification demo（單一主角打 Boss，壓力測試）

一個主角對一個 Boss，把引擎已經做好的系統全部用上。**所有資料都在專案檔裡，用編輯器打開就能改**；
`build_project.py` 只是產生它的食譜（不是必要的），讀起來可以當作「這個系統怎麼用資料描述」的範例。
這個 demo 的選擇（職業、數值、版面）都只是範例，引擎裡沒有它們的程式碼。

```bash
.venv/bin/asteria-editor                                                    # File > Open 這個資料夾的 project.asteria.json
.venv/bin/asteria-preview reference_projects/full_verification_demo/project.asteria.json   # 直接玩
.venv/bin/python reference_projects/full_verification_demo/run_campaign.py       # 通關腳本:四張地圖、三個 Boss、四位隊友
.venv/bin/python reference_projects/full_verification_demo/run_trial_smoke.py      # 腳本化通關，列出每個系統打到幾次
```

整個遊戲:Hearthfold(城鎮)→ Whispering Woods(森林)→ Catacombs(地下墓穴)→ Ember Throne(王座),
`run_campaign.py` 從第一句話一路打到通關(逐項清單見 `docs/audits/FULL_VERIFICATION_COVERAGE.md`)。
走到畫面上的 NPC 前按 E：訓練師換副職業、鐵匠精煉、珠寶匠鑲嵌、煉金師合成、商人買賣、神殿給經驗與點數；
走到 Vaelor 前按 E 開戰。戰鬥內：Attack／Skills／Items；Skills 裡有「Concoct」（調和）與各職業技能。

## 每個系統在編輯器哪裡改

| 系統 | 位置（工作區 > 分頁 > 種類） | 這個 demo 的例子 |
|---|---|---|
| 職業與每級成長 | Database > Game Data > Classes / Jobs | 9 個職業，`level_growth` 是每級成長 |
| 技能（多段、爆擊、即死、狀態、BP 消耗） | Database > Game Data > Abilities | 每一下攻擊 `hits` 的 `checks`、`kill` |
| 技能樹、職業點、能力點 | Database > Game Data > Skill Trees；Game Systems > Job Points | 9 張職業樹＋屬性樹；互斥關鍵節點 |
| 被動 | Game Data > Passives | 各職業的 Mastery |
| 狀態（毒、燃燒、姿態、附魔…） | Game Data > Status Definitions；Battle > Battle Rules > Status Effects | 27 種；姿態與附魔用「提供標籤」 |
| 武器、裝備、套裝 | Game Data > Equipment；Game Systems > Equipment Sets | Sunbrand、Warden 三件套 |
| 鑲嵌（卡片、寶珠） | Game Data > Attachments；Items 的「Attachment」欄位 | 寶珠返還、卡片消耗 |
| 武器成長 | Game Data > Equipment Growth | 覺醒、互斥路線、進化 |
| 武器 +N 精煉 | Game Systems > Weapon Refine (+N) | 成功率、費用、失敗後果 |
| 耐久 | Game Systems > Equipment Durability | |
| 煉金（場上）、調和（戰鬥中） | Game Data > Crafting / Alchemy | `station` 是 alchemy 或 concoct |
| 拆解、商店 | Game Systems > Disassembly／Shops | |
| 敵人、Boss 階段、AI | Game Data > Enemies / Bosses；Enemy AI / Boss Phases | 3 階段、姿態、召喚 |
| 反擊、跟進動作 | Battle > Battle Rules > Counters & Follow-ups | `reactor_tags` 要求反應者帶某標籤 |
| 屬性相剋、爆擊與迴避 | Battle > Battle Rules > Damage Interactions；Chance Checks | |
| 破防（護盾） | Battle > Battle Rules > Break Gauges | |
| 先制、偷襲、吸血、嘲諷 | Database > Game Systems > Battle Extras | |
| 技能特效與動作（衝向目標、特效順序） | Presentation > Ability Timelines（或 Battle Screen > Motion Sequences） | `move` 通道 `advance`／`return` |
| 版面（敵人不顯示血條、選單貼角色） | Presentation > Battle Screen > Battle UI Layout | `hidden_zones`、`action_menu_placement` |
| 精靈表：動畫、本體高度、特效位置 | Presentation > Sprite Animation | 「Battle use」區的 Body height 與 Appears at |
| NPC 與對話 | Scene（選實體）＋ Events | 每個服務一個事件程式 |
| 失控狀態（混亂、魅惑、狂暴、即死倒數） | Battle > Battle Rules > Status Effects 的目標覆寫與可用技能標籤；狀態的到期效果 | confuse / charm / berserk / doom |
| 一個技能多種施放（屬性、武器） | Abilities 的 Forms、Follow tags | Dawn and Dusk、Elemental Edge、Arcane Tome、Versatile Strike |
| 技能消耗（血、道具、金幣、BP） | Abilities 的 Costs / Item costs / Currency costs / Battle costs | Dark Pact、Molten Strike、Gilded Hammer、Pass the Torch |
| BP 轉讓與補充 | Abilities 的 Battle resource gains | Pass the Torch、Rekindle、Mira 的 Boost Gift |
| 同伴 | Game Data > Actors；Game Start 的隊伍 | Mira（牧師），與主角並肩 |
| 掉落（稀有度、詞綴、機率） | Game Data > Drop Tables / Rarities / Affixes；敵人的 Reward | warlord_spoils、acolyte_drops；掉落裝備會骰稀有度與詞綴 |
| 偷竊、使用次數、熟練度、戰鬥中得 BP | Game Systems > Battle Extras；技能 tag `action.steal` | Pilfer、終極技能每場一次、Dawn and Dusk 熟練 |
| 寵物（捕捉、當單位戰鬥、進化） | Game Data > Pets / Capture Rules | Tame Slinger → War Slinger |
| 召喚（玩家方） | 技能的 commands：SUMMON actor_id | Mira 的 Call Spirit |
| 變身 | 裝備欄 form ＋狀態 | Dragon Form / Revert |
| 技能進化 | Game Data > Ability Evolutions；Progression Tracks | Brave Slash → II（戰鬥經驗 rank 2） |
| 任務、成就、敵人等級與難度 | Game Data > Quests / Achievements；Game Systems > Enemy Levels | Slay Vaelor、三種難度 |
| 職業解鎖條件、非線性經驗曲線 | Classes 的 Unlock level / classes；Progression Tracks（level_track） | level_curve、各進階職業 |
| 逃跑 | Battle > Escape Rules；Encounter 的 tag `no_escape` | 蟲群可逃，Boss 房不行 |
| 工作坊畫面（精煉、鑲嵌、屬性點） | 測試主機的 Build 選單按 8 | R / S / X / A 鍵 |
| 起始狀態（點數、背包、裝備） | Database > Game Start | |

## 不在專案檔裡的部分

`playable_test_manifest.json` 是預覽用的設定（場上實體要畫哪張圖、背景、音樂、按鍵）。
技能與狀態的名稱已經在專案資料裡（`display_name`），不依賴它。

## 素材

全部可再散布：Foozle 的 Lucifer 系列、Pixel Magic Effects 與音樂包（CC0），音效取自參考專案。
出處見 `playable_assets/CREDITS.md` 與根目錄 `THIRD_PARTY_ASSETS.md`。
