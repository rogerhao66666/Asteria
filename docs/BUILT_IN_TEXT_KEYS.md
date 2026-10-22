# 遊戲內建字的翻譯鍵

這頁由 `scripts/built_in_text_keys.py` 從 `src/asteria/rpg/built_in_text.py` 產生，不要手改。
說明在 [`ENGINE_HANDBOOK.md`](ENGINE_HANDBOOK.md) 的「遊戲內建字的翻譯」。

- 專案的翻譯表（Database ▸ Game Systems ▸ Translations）在某一列寫了文字，遊戲畫這個鍵時就用它；
  沒寫就畫下表的 English。所以沒有翻譯表的專案畫面和以前一模一樣。
- `{name}` 是遊戲執行時填進去的值，譯文要保留同樣的 `{...}`（順序可以換）。
- 「引擎的繁體中文」是 `rpg/built_in_text/zh-TW.json`，編輯器的「填入空白列」會把它填進 zh-TW 表。
- 另外四種鍵由專案自己的資料決定（編輯器的 Translations 頁會依專案列出）：
  `controls.action.<動作 id>`（按鍵設定畫面的動作名稱）、`battle.layer.<指令 id>`
  （Command Menu Pages 的名稱）、`battle.group.<分組名>`（技能的 `menu_category`）、
  `pause.entry.<項目 id>`（暫停選單的自訂項目）。沒寫譯文就照專案寫的顯示。

共 337 個鍵，27 組。

## Title screen

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `title.name` | ASTERIA | ASTERIA |
| `title.subtitle` | Complex Reference RPG | 綜合參考 RPG |
| `title.server_session` | N   Enter Server Session | N   進入伺服器場次 |
| `title.server_save` | L   Reload Server Save | L   重新載入伺服器存檔 |
| `title.guest` | Guest: {player} | 訪客：{player} |
| `title.new_game` | N   New Game | N   新遊戲 |
| `title.load_game` | L   Load Game | L   讀取進度 |
| `title.saves` | {count} save(s) found | 找到 {count} 個存檔 |
| `title.no_saves` | No saves yet | 還沒有存檔 |
| `title.no_player_save` | No player save exists yet | 還沒有玩家存檔 |
| `title.loaded` | Loaded player save | 已讀取玩家存檔 |
| `title.new_game_plus` | New Game+ | 二周目 |

## Field

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `notice.gained` | +{count} {name} | {name} +{count} |
| `notice.broke` | {name} broke! | {name} 壞掉了！ |
| `field.skip_cutscene` | Esc: skip | Esc：略過 |
| `field.title` | Field Test | 野外測試 |
| `field.controls` | Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   Esc: Pause | 移動：WASD／方向鍵   C：角色養成   Q：任務   E：互動   F5：存檔   Esc：暫停 |
| `field.interact` | E  Interact — {name} | E  互動 — {name} |
| `equip_offer.instead` | {who}: wear it instead of {old}? | {who}：要換下 {old} 改穿這件嗎？ |
| `equip_offer.new` | New: {name} | 新裝備：{name} |
| `equip_offer.free` | {who} has a free {slot} place. Wear it now? | {who} 的 {slot} 欄位是空的，要現在裝備嗎？ |
| `equip_offer.keys` | 1 / Enter: wear it     2 / Esc: keep it in the bag | 1／Enter：裝備     2／Esc：收進背包 |
| `field.saved` | Saved: {file} | 已存檔：{file} |
| `notice.no_room` | No room for {name} | 背包放不下 {name} |

## Dialogue

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `dialogue.continue` | Enter / E: continue | Enter／E：繼續 |
| `dialogue.choose` | Choose | 請選擇 |

## Pause menu

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `pause.resume` | Resume | 繼續遊戲 |
| `pause.status` | Status / Items / Equipment / Skills | 狀態／道具／裝備／技能 |
| `pause.achievements` | Achievements | 成就 |
| `pause.bestiary` | Bestiary | 怪物圖鑑 |
| `pause.title` | Return to Title | 回到標題畫面 |
| `pause.quit` | Quit | 結束遊戲 |
| `pause.pets` | Pets | 寵物 |
| `pause.backlog` | Message Log | 訊息紀錄 |
| `pause.skill_slots` | Skill Slots | 技能欄 |
| `pause.music` | Music Room | 音樂室 |
| `pause.credits` | Credits | 製作人員 |
| `pause.save` | Save Game | 儲存進度 |
| `pause.load` | Load Game | 讀取進度 |
| `pause.crafting` | Crafting | 製作 |
| `pause.settings` | Settings | 設定 |
| `pause.quests` | Quest Log | 任務紀錄 |
| `pause.heading` | Paused | 暫停 |

## Game over

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `game_over.load` | Load Last Save | 讀取上次的存檔 |
| `game_over.title` | Return to Title | 回到標題畫面 |
| `game_over.heading` | Game Over | 遊戲結束 |

## Settings

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `settings.music_volume` | Music Volume | 音樂音量 |
| `settings.effects_volume` | Effects Volume | 音效音量 |
| `settings.show_battle_log` | Battle Messages | 戰鬥訊息 |
| `settings.controls` | Controls… | 按鍵設定… |
| `settings.back` | Back | 返回 |
| `settings.language` | Language | 語言 |
| `language.name` | English | 繁體中文 |
| `settings.on` | On | 開 |
| `settings.off` | Off | 關 |
| `settings.hint` | Left/Right: change   Esc: save and back | 左／右：調整   Esc：儲存並返回 |

## Controls

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `controls.pad_button` | Pad {button} | 手把 {button} |
| `controls.pad_axis` | Pad {axis} | 手把 {axis} |
| `controls.reset_all` | Reset all to defaults | 全部恢復預設 |
| `controls.all_reset` | All controls reset | 已恢復所有按鍵的預設 |
| `controls.press` | Press a key or pad button for {action} (Esc cancels) | 請按下要給「{action}」的按鍵或手把按鈕（Esc 取消） |
| `controls.title` | Controls | 按鍵設定 |
| `controls.hint` | Enter: rebind   Backspace: reset action   Esc: save and back | Enter：重新設定   Backspace：恢復此項預設   Esc：儲存並返回 |

## Save and load

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `slots.loaded` | Loaded slot {slot} | 已讀取存檔 {slot} |
| `slots.autosave` | Autosave (F5) | 自動存檔（F5） |
| `slots.slot` | Slot {slot} | 存檔 {slot} |
| `slots.hint` | Enter: choose   Delete: erase   Esc: back | Enter：選擇   Delete：刪除   Esc：返回 |
| `slots.damaged` | damaged save ({error}) | 存檔已損壞（{error}） |
| `slots.empty_slot` | — empty — | — 空 — |
| `slots.summary` | {scene} · {leader} Lv {level} · {saved_at} | {scene} · {leader} Lv {level} · {saved_at} |
| `slots.is_empty` | That slot is empty | 這個存檔欄是空的 |
| `slots.is_damaged` | That save is damaged | 這個存檔已損壞 |
| `slots.overwrite` | Overwrite slot {slot}? Press Enter again | 要覆蓋存檔 {slot} 嗎？再按一次 Enter |
| `slots.saved` | Saved to slot {slot} | 已存到存檔 {slot} |
| `slots.delete` | Delete slot {slot}? Press Delete again | 要刪除存檔 {slot} 嗎？再按一次 Delete |
| `slots.deleted` | Deleted slot {slot} | 已刪除存檔 {slot} |

## Status menu

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `status.tab.status` | Status | 狀態 |
| `status.tab.items` | Items | 道具 |
| `status.tab.equipment` | Equipment | 裝備 |
| `status.tab.skills` | Skills | 技能 |
| `status.reason.not_in_inventory` | not_in_inventory | 背包裡沒有 |
| `status.reason.effect_rejected` | effect_rejected | 沒有效果 |
| `status.member` | Q / E  {name} | Q／E  {name} |
| `status.empty` | Nothing here yet. | 這裡還沒有東西。 |
| `status.hint` | Tab: next tab   Up/Down: choose   Enter: use / equip / unequip   Esc: back | Tab：下一頁   上／下：選擇   Enter：使用／裝備／卸下   Esc：返回 |
| `status.usable` | (use) | （可使用） |
| `status.learned` | learned | 已學會 |
| `status.active` | active | 生效中 |
| `status.used` | Used {name} | 使用了 {name} |
| `status.cannot_use` | {name} can't be used ({reason}) | {name} 無法使用（{reason}） |
| `status.equipped` | Equipped {name} | 裝備了 {name} |
| `status.unequipped` | Unequipped {name} | 卸下了 {name} |
| `status.nothing_to_unequip` | Nothing to unequip | 沒有可卸下的裝備 |

## Quest log

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `quests.status.active` | active | 進行中 |
| `quests.status.completed` | completed | 已完成 |
| `quests.status.failed` | failed | 失敗 |
| `quests.none` | No quests yet. | 還沒有任務。 |
| `quests.hint` | Enter / Esc: back | Enter／Esc：返回 |

## Shop

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `shop.buy` | Buy | 購買 |
| `shop.sell` | Sell | 出售 |
| `shop.error.stock` | {shop} has only {count} {item} | {shop} 的 {item} 只剩 {count} 個 |
| `shop.error.not_now` | {shop} is not offering {item} now | {shop} 現在不賣 {item} |
| `shop.error.afford` | cannot afford {count} {item} | 錢不夠買 {count} 個 {item} |
| `shop.error.no_room` | no room for {count} {item} (room for {room}) | 背包放不下 {count} 個 {item}（只能再放 {room} 個） |
| `shop.error.sell` | not enough {item} to sell | 沒有足夠的 {item} 可以出售 |
| `shop.bought` | Bought {name} | 買了 {name} |
| `shop.sold` | Sold {name} | 賣了 {name} |
| `shop.item` | Item | 物品 |
| `shop.price` | Price | 價格 |
| `shop.stock` | Stock | 庫存 |
| `shop.owned` | Owned | 持有 |
| `shop.hint` | Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave | 上／下：選擇   左／右：購買／出售   Enter：確定   Esc：離開 |

## Crafting

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `crafting.nothing` | nothing | 什麼都沒有 |
| `crafting.crafted_quality` | Crafted {items} ({quality}) | 製作了 {items}（{quality}） |
| `crafting.crafted` | Crafted {items} | 製作了 {items} |
| `crafting.failed` | Crafting failed — got {items} | 製作失敗，得到 {items} |
| `crafting.none` | No known recipes here. | 這裡沒有已知的配方。 |
| `crafting.hidden` | ??? {count} recipe(s) not yet discovered | ??? 還有 {count} 個配方尚未發現 |
| `crafting.hint` | Up/Down: select   Enter: craft   Esc: back | 上／下：選擇   Enter：製作   Esc：返回 |

## Achievements and bestiary

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `bestiary.tag.weak` | weak | 弱點 |
| `bestiary.tag.resist` | resist | 抗性 |
| `bestiary.tag.immune` | immune | 免疫 |
| `bestiary.tag.absorb` | absorb | 吸收 |
| `bestiary.tag.reflect` | reflect | 反射 |
| `bestiary.tag.trait` | trait | 特性 |
| `achievements.hidden_name` | ??? | ??? |
| `achievements.hidden` | Hidden achievement | 隱藏成就 |
| `bestiary.unseen` | ??? | ??? |
| `achievements.title` | Achievements  {done}/{count} | 成就  {done}/{count} |
| `bestiary.title` | Bestiary  {seen}/{count} seen | 怪物圖鑑  已發現 {seen}/{count} |
| `list.hint` | Up/Down: scroll   Enter / Esc: back | 上／下：捲動   Enter／Esc：返回 |
| `bestiary.counts` | seen {seen}   defeated {defeated}   captured {captured} | 遇見 {seen}   打倒 {defeated}   捕獲 {captured} |
| `bestiary.nothing_special` | nothing special | 沒有特別之處 |
| `bestiary.unknown` | Defeat one to learn its weaknesses and health. | 打倒一次就能知道牠的弱點與體力。 |
| `bestiary.drops` | Drops: {items} | 掉落：{items} |
| `bestiary.no_drops` | Drops: none seen yet | 掉落：還沒看過 |

## Message log, music room, credits

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `backlog.title` | Message Log | 訊息紀錄 |
| `backlog.hint` | Up / Down: scroll   Esc: back | 上／下：捲動   Esc：返回 |
| `backlog.empty` | Nothing has been said yet. | 還沒有任何對話。 |
| `music.title` | Music Room | 音樂室 |
| `music.hint` | Up / Down: choose   Enter: play   Esc: back | 上／下：選擇   Enter：播放   Esc：返回 |
| `music.empty` | There are no tracks. | 沒有任何曲目。 |
| `music.locked` | ? ? ? | ? ? ? |
| `music.playing` | PLAYING | 播放中 |
| `credits.title` | Credits | 製作人員 |
| `credits.hint` | Left / Right: page   {page}/{pages}   Esc: back | 左／右：翻頁   {page}/{pages}   Esc：返回 |

## Skill slots

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `skill_slots.title` | Skill Slots | 技能欄 |
| `skill_slots.hint` | Up / Down: choose   Enter: equip / remove   Left / Right: member   Esc: back | 上／下：選擇   Enter：放入／取下   左／右：切換成員   Esc：返回 |
| `skill_slots.no_party` | No party members. | 隊伍裡沒有成員。 |
| `skill_slots.count` | {name}   Slots {used}/{capacity} | {name}   技能欄 {used}/{capacity} |
| `skill_slots.nothing` | Nothing learned yet. | 還沒有學會任何技能。 |
| `skill_slots.equipped` | EQUIPPED | 已裝備 |

## Pets

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `pets.sent_out` | {name} will be sent out | 下次派出 {name} |
| `pets.evolved` | {name} evolved! | {name} 進化了！ |
| `pets.not_ready` | Not ready to evolve | 還不能進化 |
| `pets.renamed` | Renamed | 已改名 |
| `pets.title` | Pets | 寵物 |
| `pets.hint` | Up / Down: choose   Enter: send this one out   R: rename   Esc: back | 上／下：選擇   Enter：派這隻出戰   R：改名   Esc：返回 |
| `pets.none` | You have no pets yet. | 你還沒有寵物。 |
| `pets.level` | {kind}   Lv {level} | {kind}   Lv {level} |
| `pets.bond` | Bond {bond} | 親密度 {bond} |
| `pets.active` | ACTIVE | 出戰中 |
| `pets.rename_hint` | Type a name, Enter keeps it, Esc cancels | 輸入名字，Enter 確定，Esc 取消 |

## Battle commands

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `battle.command.attack` | Attack | 攻擊 |
| `battle.command.skills` | Skills | 技能 |
| `battle.command.items` | Items | 道具 |
| `battle.command.escape` | Escape | 逃跑 |
| `battle.command.more` | More | 更多 |
| `battle.command.back` | Back | 返回 |
| `battle.menu.command` | Command | 指令 |
| `battle.menu.target` | Target | 目標 |
| `battle.menu.form` | Form | 施放方式 |
| `battle.menu.filter` | Filter: {query} | 篩選：{query} |
| `battle.workflow.ready` | Ready | 準備完成 |
| `battle.hint.attack` | Choose a weapon | 選擇武器 |
| `battle.hint.skills` | Abilities, concoct, capture | 技能、調合、捕獲 |
| `battle.hint.group` | Abilities | 技能 |
| `battle.hint.items` | Use an item from the bag | 使用背包裡的道具 |
| `battle.hint.escape` | {chance}% to get away | {chance}% 機率逃走 |
| `battle.hint.back` | The first commands | 回到前面的指令 |
| `battle.hint.more` | More commands | 更多指令 |
| `battle.nothing_to_use` | Nothing to use | 沒有可用的項目 |
| `battle.hint.concoct` | Pick ingredients | 選擇材料 |
| `battle.capture_row` | X  Capture ({chance}%) | X  捕獲（{chance}%） |
| `battle.boost_row` | Boost x{level} | 加速 x{level} |
| `battle.hint.boost` | Left / Right (or Enter here) set the boost for the next action | 左／右（或在此按 Enter）設定下一個行動的加速 |
| `battle.pick_count` | Pick {count} | 請選 {count} 個 |
| `battle.concoct_nothing` | These ingredients make nothing | 這些材料調不出東西 |
| `battle.boost_key_row` | B  Boost x{level} ({points} {amount}) | B  加速 x{level}（{points} {amount}） |
| `battle.boost_level` | BOOST x{level} | 加速 x{level} |

## Battle: why a command cannot be used

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `battle.reason.cooldown_one` | Ready in {turns} turn | {turns} 回合後可用 |
| `battle.reason.cooldown` | Ready in {turns} turns | {turns} 回合後可用 |
| `battle.reason.short` | Needs {amount} {resource} (has {have}) | 需要 {amount} {resource}（目前 {have}） |
| `battle.reason.form_needs` | needs {amount} {resource} | 需要 {amount} {resource} |
| `battle.reason.form_short` | needs {amount} {resource} ({have}) | 需要 {amount} {resource}（目前 {have}） |
| `battle.reason.blocked` | Blocked by {states} | 受到 {states} 影響無法使用 |
| `battle.reason.no_uses` | No uses left this battle | 本場戰鬥已用完次數 |
| `battle.reason.a_pet` | a pet | 寵物 |
| `battle.reason.needs_items` | Needs {what} x{count} | 需要 {what} x{count} |
| `battle.reason.needs_amount` | Needs {amount} {resource} | 需要 {amount} {resource} |
| `battle.reason.needs` | Needs {what} | 需要 {what} |
| `battle.reason.no_ingredients` | No ingredients | 沒有材料 |
| `battle.reason.pet_unlearned` | {pet} has not learned this | {pet} 還沒學會這招 |
| `battle.condition.not` | no {what} | 沒有 {what} |
| `battle.condition.or` |  or  |  或  |
| `battle.condition.state` | state {state} | 狀態 {state} |
| `battle.condition.some` | conditions | 特定條件 |

## Battle

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `battle.result.victory` | Victory | 勝利 |
| `battle.result.defeat` | Defeat | 戰敗 |
| `battle.result.escape` | Escaped | 成功逃脫 |
| `battle.result.complete` | Battle Complete | 戰鬥結束 |
| `battle.result.rank` | Rank {old} → {new} | 階級 {old} → {new} |
| `battle.tile.break` | BREAK | 破防 |
| `battle.break_caption` | Damage up - loses a turn | 受到的傷害提高，失去一回合 |
| `battle.item_none_left` | no {name} left | {name} 已經用完了 |
| `battle.escape.no_rule` | The project defines no escape rule | 這個專案沒有設定逃跑規則 |
| `battle.escape.blocked` | This battle has no_escape: there is no running away | 這場戰鬥無法逃跑 |
| `battle.capture.needs` | capturing needs {item} | 捕獲需要 {item} |

## Capture

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `capture.failed` | Capture failed: {reason} | 捕獲失敗：{reason} |
| `capture.caught` | Captured {name}! | 捕獲了 {name}！ |
| `capture.broke_free` | {name} broke free | {name} 掙脫了 |
| `capture.title` | Capture | 捕獲 |
| `capture.uses` | (uses {item}: {count}) | （使用 {item}：剩 {count}） |
| `capture.cancel` | Esc: cancel | Esc：取消 |

## Victory

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `victory.defeated` | Defeated: {names} | 打倒了：{names} |
| `victory.title` | Victory | 勝利 |
| `victory.exp` | EXP  +{amount} | 經驗值  +{amount} |
| `victory.level` | Level {before} -> {after} | 等級 {before} → {after} |
| `victory.learned` | Learned {name} | 學會了 {name} |
| `victory.spoils` | Spoils | 戰利品 |
| `victory.overkill` | Overkill x{scale} | 過量擊殺 x{scale} |
| `victory.next` | Enter: next | Enter：下一頁 |
| `victory.close` | Enter: continue | Enter：繼續 |

## Equipment bag (action games)

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `bag.set_tag` | tag {tag} | 標籤 {tag} |
| `bag.set_bonus` | bonus | 加成 |
| `bag.unequipped` | Unequipped {name} | 卸下了 {name} |
| `bag.equipped` | Equipped {name} | 裝備了 {name} |
| `bag.cannot_equip` | Cannot equip: {reason} | 無法裝備：{reason} |
| `bag.title` | Equipment | 裝備 |
| `bag.hint` | Arrows: choose   Enter: equip / unequip   B / Esc: close | 方向鍵：選擇   Enter：裝備／卸下   B／Esc：關閉 |
| `bag.worn` | Worn | 身上的裝備 |
| `bag.count` | Bag  ({count}) | 背包（{count}） |
| `bag.empty` | Nothing here. | 這裡沒有東西。 |
| `bag.common` | Common | 普通 |
| `bag.item_line` | {rarity}  ·  item level {level}  ·  {slot} | {rarity}  ·  物品等級 {level}  ·  {slot} |
| `bag.compared` | Compared with the worn piece | 與身上的裝備比較 |
| `bag.stats` | Stats | 能力值 |
| `bag.replaces` | (replaces {name}) | （換下 {name}） |
| `bag.affixes` | Affixes | 詞綴 |

## Skill tree (action games)

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `skill_tree.status.learned` | learned | 已學會 |
| `skill_tree.status.maxed` | maxed | 已滿級 |
| `skill_tree.status.available` | available | 可學習 |
| `skill_tree.status.locked` | locked | 未解鎖 |
| `skill_tree.max` | max {name} +{value} | {name} 上限 +{value} |
| `skill_tree.skill` | Skill: {name} | 技能：{name} |
| `skill_tree.passive` | Passive: {name} | 被動：{name} |
| `skill_tree.tag` | Tag: {name} | 標籤：{name} |
| `skill_tree.unmet` | requirements not met | 條件不足 |
| `skill_tree.cannot_learn` | Cannot learn {name}: {reason} | 無法學習 {name}：{reason} |
| `skill_tree.learned` | Learned {name} (rank {rank}/{max}) | 學會了 {name}（{rank}/{max} 級） |
| `skill_tree.title` | Skill Tree | 技能樹 |
| `skill_tree.none` | No skill tree for this character. | 這個角色沒有技能樹。 |
| `skill_tree.header` | {tree}   ·   {classes}   ·   Lv {level} | {tree}   ·   {classes}   ·   Lv {level} |
| `skill_tree.trees` | Tree {index}/{count}  (O: next tree) | 技能樹 {index}/{count}（O：下一棵） |
| `skill_tree.hint` | Arrows: choose   Enter: learn   Wheel / + -: zoom   Drag: move   R: fit   O: next tree   C: back | 方向鍵：選擇   Enter：學習   滾輪／+ -：縮放   拖曳：移動   R：全覽   O：下一棵   C：返回 |
| `skill_tree.rank` | Rank {rank}/{max}   ·   {status} | 等級 {rank}/{max}   ·   {status} |
| `skill_tree.free` | free | 免費 |
| `skill_tree.cost` | Next rank costs {cost} | 下一級需要 {cost} |
| `skill_tree.gives` | Next rank gives: | 下一級獲得： |
| `skill_tree.so_far` | Learned so far: | 目前已獲得： |
| `skill_tree.needs` | Needs: | 前置條件： |

## Action HUD

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `action.level_up` | Level {level}! | 升到 {level} 級！ |
| `action.fell` | You fell — back in {seconds}s | 你倒下了 — {seconds} 秒後復活 |
| `hud.level` | Lv {level} | Lv {level} |
| `hud.skills` | Skills 1-{last} | 技能 1-{last} |
| `hud.skill` | Skill 1 | 技能 1 |
| `hud.controls` | Move WASD   Attack J   Dodge K   {skills}   Lock L   Pick up F   Bag B   Skill tree C   Pause Esc | 移動 WASD   攻擊 J   閃避 K   {skills}   鎖定 L   撿取 F   背包 B   技能樹 C   暫停 Esc |

## Build menu (testing)

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `build.title` | Character / Build Acceptance Menu | 角色／養成驗收選單 |
| `build.keys` | Q/E Actor   C Close     Current: {actor} | Q/E 切換角色   C 關閉     目前：{actor} |
| `build.points` | Level {level}   EXP {exp}   AP {ap}   Ability Pts {ability_points} | 等級 {level}   經驗 {exp}   AP {ap}   技能點 {ability_points} |
| `build.class` | 1 Secondary Class: {value} | 1 副職業：{value} |
| `build.passives` | 3 Passives: {value} | 3 被動技能：{value} |
| `build.weapon` | 4 Weapon: {value} | 4 武器：{value} |
| `build.base` | base | 基本 |
| `build.upgrade` | 5 Weapon Upgrade: {value} | 5 武器強化：{value} |
| `build.accessories` | 6 Accessories: {value} | 6 飾品：{value} |
| `build.party` | 7 Party / Formation: {value} | 7 隊伍／隊形：{value} |
| `build.tree` | 2 Skill Tree: allocate next available node | 2 技能樹：學習下一個可學的節點 |
| `build.note` | All changes are Runtime State and are verified again after Save/Load. | 所有變更都存在執行狀態裡，存檔／讀檔後會再驗證一次。 |
| `build.learned` | Learned {name} | 學會了 {name} |
| `build.no_node` | No affordable/unlocked node | 沒有點數足夠或已解鎖的節點 |
| `build.upgraded` | Weapon upgraded: {name} | 武器強化：{name} |
| `build.no_upgrade` | Weapon growth maxed or blocked | 武器已強化到頂或無法強化 |

## Workshop (testing)

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `workshop.refined` | Refine: {outcome} | 精煉：{outcome} |
| `workshop.took_out` | Took {name} out of {socket} | 從 {socket} 取下了 {name} |
| `workshop.socketed` | Socketed {name} into {socket} | 把 {name} 鑲進了 {socket} |
| `workshop.nothing_to_socket` | Nothing to socket (no free socket or no fitting item in the bag) | 沒有可以鑲嵌的（沒有空孔，或背包裡沒有合適的道具） |
| `workshop.no_attributes` | This project has no attribute graph | 這個專案沒有屬性圖 |
| `workshop.point_spent` | +1 {name} | {name} +1 |
| `workshop.no_points` | No attribute points left | 沒有剩下的屬性點 |
| `workshop.title` | Workshop | 工坊 |
| `workshop.keys` | R Refine   S Socket   X Take out   A Attribute point   C Back  [{actor}] | R 精煉   S 鑲嵌   X 取下   A 屬性點   C 返回  [{actor}] |
| `workshop.gold` | Gold {amount} | 金幣 {amount} |
| `workshop.no_weapon` | No weapon equipped | 沒有裝備武器 |
| `workshop.next` | Next +{level}: {chance}% for {cost} {currency} | 下一級 +{level}：成功率 {chance}%，需要 {cost} {currency} |
| `workshop.locked` | locked | 鎖住 |
| `workshop.empty` | empty | 空 |
| `workshop.socket` | Socket {socket}: {value} | 孔 {socket}：{value} |
| `workshop.points` | Attribute points: {count} | 屬性點：{count} |

## Co-op

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `coop.bag_title` | Co-op Inventory | 連線背包 |
| `coop.experience` | Experience: {amount} | 經驗值：{amount} |
| `coop.no_items` | No items yet | 還沒有道具 |
| `coop.boss_rule` | Boss reward: full XP to contributors; loot to one contributor | 首領獎勵：有出力的人都得到全部經驗值；掉落物給其中一人 |
| `coop.close` | B / Esc: close | B／Esc：關閉 |
| `coop.craft_requested` | Craft requested from server | 已向伺服器要求製作 |
| `coop.learn_requested` | Learning requested from server | 已向伺服器要求學習 |
| `coop.bind_requested` | Slot {slot} binding requested from server | 已向伺服器要求設定第 {slot} 格 |
| `coop.bind_hint` | 1–4: bind learned skill to slot | 1–4：把學會的技能放進技能格 |
| `coop.offline` | Co-op offline: {error} | 連線中斷：{error} |
| `coop.requested` | Server {command} requested | 已向伺服器要求：{command} |
| `coop.required` | Server connection required · F3 to retry | 需要連上伺服器 · 按 F3 重試 |
| `coop.connected_project` | Co-op connected · WASD / arrows · J attack · F pickup | 已連線 · WASD／方向鍵移動 · J 攻擊 · F 撿取 |
| `coop.connected` | Co-op connected · move with WASD / arrows · attack with F | 已連線 · 用 WASD／方向鍵移動 · 用 F 攻擊 |
| `coop.boss_defeated` | Boss defeated · +{amount} XP | 首領已擊敗 · 經驗值 +{amount} |
| `coop.boss_loot` | Boss loot: {item} | 首領掉落：{item} |
| `coop.profile_error` | Co-op profile error: {error} | 連線設定錯誤：{error} |
| `coop.start_server` | Start the local server in Multiplayer first | 請先在 Multiplayer 工作區啟動本機伺服器 |
| `coop.retry` | Co-op offline · {status} · F3 to retry | 連線中斷 · {status} · 按 F3 重試 |
| `coop.players` | Co-op · {count} players | 連線 · {count} 名玩家 |
| `coop.boss` | Co-op Boss · {hp}/{max_hp} | 連線首領 · {hp}/{max_hp} |
| `coop.claim` | G: claim treasure | G：領取寶物 |
| `coop.status` | Co-op · {count} players · XP {xp} · B: bag / G: loot | 連線 · {count} 名玩家 · 經驗 {xp} · B：背包／G：拾取 |
| `coop.player` | Player | 玩家 |
| `coop.player_hp` | {name} · {hp} HP | {name} · {hp} HP |
| `coop.paused` | Server connection paused · F3 to retry | 伺服器連線已暫停 · 按 F3 重試 |
| `coop.confirmed` | Server {command} confirmed | 伺服器已確認：{command} |
| `coop.rejected` | Server rejected command | 伺服器拒絕了指令 |
