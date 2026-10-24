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

共 628 個鍵，29 組。

## Creature battle

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `creature.wild_name` | Wild {name} | 野生的{name} |
| `creature.you` | You | 你 |
| `creature.fainted` | {name} fainted! | {name}倒下了！ |
| `creature.threw` | {player} used {item}! | {player}使用了{item}！ |
| `creature.out_of_creatures` | {player} is out of usable creatures! | {player}已經沒有可以戰鬥的夥伴了！ |
| `creature.whited_out` | {player} whited out! | {player}眼前一片漆黑！ |
| `creature.cmd.fight` | FIGHT | 戰鬥 |
| `creature.cmd.bag` | BAG | 背包 |
| `creature.cmd.party` | PARTY | 隊伍 |
| `creature.cmd.run` | RUN | 逃走 |
| `creature.pp` | PP | PP |
| `creature.type` | TYPE/{type} | 屬性/{type} |
| `creature.choose` | Choose a creature. | 請選擇夥伴。 |
| `creature.pocket.items` | ITEMS | 道具 |
| `creature.pocket.balls` | BALLS | 捕獲球 |
| `creature.foe_name` | Foe {name} | 對手的{name} |
| `creature.trainer_challenge` | {trainer} would like to battle! | {trainer}向你發起了對戰！ |
| `creature.trainer_sent_out` | {trainer} sent out {name}! | {trainer}派出了{name}！ |
| `creature.go` | Go! {name}! | 去吧！{name}！ |
| `creature.cant_escape` | Can't escape! | 逃不掉！ |
| `creature.caught` | Gotcha! {name} was caught! | 好耶！抓到{name}了！ |
| `creature.defeated_trainer` | {player} defeated {trainer}! | {player}打敗了{trainer}！ |
| `creature.cancel` | CANCEL | 取消 |
| `creature.bag_empty` | Nothing here. | 什麼都沒有。 |
| `creature.no_running` | No! There's no running from a trainer battle! | 不行！不能從訓練家的對戰中逃走！ |
| `creature.got_away` | Got away safely! | 順利逃走了！ |
| `creature.used` | {user} used {move}! | {user}使用了{move}！ |
| `creature.sent_to_storage` | {name} was transferred to storage. | {name}被送到寄放處了。 |
| `creature.exp` | {name} gained {amount} EXP. Points! | {name}獲得了{amount}經驗值！ |
| `creature.level_up` | {name} grew to LV. {level}! | {name}升到了等級{level}！ |
| `creature.evolved` | {name} evolved into {species}! | {name}進化成了{species}！ |
| `creature.prize` | {player} got {amount} for winning! | {player}獲得了{amount}作為獎金！ |
| `creature.come_back` | {name}, come back! | {name}，回來吧！ |
| `creature.used_item` | {player} used {item}! | {player}使用了{item}！ |
| `creature.no_effect` | It doesn't affect {name}... | 對{name}好像沒有效果…… |
| `creature.critical` | A critical hit! | 擊中了要害！ |
| `creature.already_out` | {name} is already in battle! | {name}已經在戰鬥中了！ |
| `creature.no_energy` | There's no will to battle! | 已經沒有力氣戰鬥了！ |
| `creature.hp_restored` | {name}'s HP was restored. | {name}的體力恢復了。 |
| `creature.super_effective` | It's super effective! | 效果絕佳！ |
| `creature.state_applied` | {name} is now {state}! | {name}陷入了{state}狀態！ |
| `creature.no_pp` | There's no PP left for this move! | 這個招式已經沒有 PP 了！ |
| `creature.not_very_effective` | It's not very effective... | 效果不太好…… |
| `creature.what_will` | What will {name} do? | 要讓 {name}做什麼？ |
| `creature.no_stealing` | The trainer blocked the ball! Don't be a thief! | 訓練家擋住了球！不可以搶別人的東西！ |
| `creature.foe` | The foe | 對手 |
| `creature.broke_free` | Oh, no! It broke free! | 啊！被牠掙脫了！ |
| `creature.almost` | Aww! It appeared to be caught! | 唉！差一點就抓到了！ |
| `creature.so_close` | Aargh! Almost had it! | 可惡！只差一點！ |
| `creature.shoot` | Shoot! It was so close, too! | 糟糕！明明就快抓到了！ |
| `creature.legendary_appeared` | {name} appeared! | {name}出現了！ |
| `creature.appeared` | Wild {name} appeared! | 野生的{name}出現了！ |
| `creature.level` | Lv{level} | Lv{level} |
| `creature.close_bag` | CLOSE BAG | 關上背包 |
| `creature.no_moves_left` | {name} has no moves left! | {name}已經沒有可以使用的招式了！ |
| `creature.do_it` | Do it! {name}! | 就是現在！{name}！ |
| `creature.go_for_it` | Go for it, {name}! | 加油，{name}！ |
| `creature.foe_weak` | Your foe's weak! Get 'em, {name}! | 對手很虛弱了！ 上吧，{name}！ |
| `creature.thats_enough` | {name}, that's enough! Come back! | {name}，夠了！ 回來吧！ |
| `creature.ok_come_back` | {name}, OK! Come back! | {name}，好！ 回來吧！ |
| `creature.good_come_back` | {name}, good! Come back! | {name}，做得好！ 回來吧！ |
| `creature.missed` | {name}'s attack missed! | {name}的 攻擊沒有命中！ |
| `creature.stat_sharply_rose` | {name}'s {stat} sharply rose! | {name}的{stat} 大幅提高了！ |
| `creature.stat_rose` | {name}'s {stat} rose! | {name}的{stat} 提高了！ |
| `creature.stat_fell` | {name}'s {stat} fell! | {name}的{stat} 降低了！ |
| `creature.stat_harshly_fell` | {name}'s {stat} harshly fell! | {name}的{stat} 大幅降低了！ |
| `creature.stat_wont_rise` | {name}'s {stat} won't go higher! | {name}的{stat} 已經無法再提高了！ |
| `creature.stat_wont_fall` | {name}'s {stat} won't go lower! | {name}的{stat} 已經無法再降低了！ |
| `creature.but_it_failed` | But it failed! | 但是失敗了！ |
| `creature.about_to_use` | {trainer} is about to use {name}. | {trainer} 準備派出{name}。 |
| `creature.will_change` | Will {player} change creatures? | {player}要更換 夥伴嗎？ |
| `creature.use_next` | Use next creature? | 要派出下一隻嗎？ |
| `creature.yes` | YES | 是 |
| `creature.no` | NO | 否 |
| `creature.hit_times` | Hit {count} time(s)! | 命中了{count}次！ |
| `creature.drained` | {name} had its energy drained! | {name}的 體力被吸取了！ |
| `creature.recoil` | {name} is hit with recoil! | {name}受到了 反作用力的傷害！ |
| `menu.exit` | EXIT | 離開 |
| `creature.menu.summary` | SUMMARY | 能力 |
| `creature.menu.switch` | SWITCH | 替換 |
| `creature.menu.do_what` | Do what with this {name}? | 要對{name}做什麼？ |
| `creature.menu.move_where` | Move to where? | 要移到哪裡？ |
| `creature.menu.use` | USE | 使用 |
| `creature.menu.toss` | TOSS | 丟掉 |
| `creature.menu.cant_use` | This can't be used now. | 現在不能使用。 |
| `creature.menu.tossed` | Threw away 1 {item}. | 丟掉了1個{item}。 |
| `creature.menu.close_bag_words` | CLOSE BAG | 關上背包 |
| `creature.summary.info` | INFO | 資料 |
| `creature.summary.skills` | SKILLS | 能力值 |
| `creature.summary.moves` | MOVES | 招式 |
| `creature.summary.none` | NONE | 無 |
| `creature.summary.exp` | EXP. POINTS | 經驗值 |
| `creature.summary.next` | NEXT LV. | 距離升級 |
| `creature.summary.pp` | PP | PP |
| `creature.menu.use_on_which` | Use on which creature? | 要對哪一隻使用？ |
| `creature.menu.no_effect` | It won't have any effect. | 沒有任何效果。 |
| `creature.menu.hp_restored` | {name}'s HP was restored by {amount} point(s). | {name}的HP回復了{amount}點。 |
| `creature.menu.cured` | {name} was cured. | {name}恢復了。 |
| `creature.card.name` | NAME:  | 名字： |
| `creature.card.id` | IDNo. | ID號碼 |
| `creature.card.money` | MONEY | 金錢 |
| `creature.card.dex` | DEX | 圖鑑 |
| `creature.card.time` | TIME | 時間 |
| `creature.options.title` | OPTION | 設定 |
| `creature.dex.seen` | SEEN | 見過 |
| `creature.dex.owned` | OWN | 捕獲 |
| `creature.dex.height` | HT | 身高 |
| `creature.dex.weight` | WT | 體重 |
| `creature.save.player` | PLAYER | 玩家 |
| `creature.save.badges` | BADGES | 徽章 |
| `creature.save.confirm` | Would you like to save the game? | 要記錄冒險嗎？ |
| `creature.save.saving` | SAVING… DON'T TURN OFF THE POWER. | 記錄中……請不要關掉電源。 |
| `creature.save.saved` | {player} saved the game. | {player}記錄了冒險。 |

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
| `pause.equipment` | Equipment | 裝備 |
| `pause.enhance` | Enhance | 強化 |
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
| `settings.developer_menu` | Developer Menu | 開發者選單 |
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
| `controls.pad_stick` | stick | 搖桿 |
| `controls.pad_hat` | d-pad | 十字鍵 |
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
| `quests.objective.defeat` | Defeat {name} | 擊敗{name} |
| `quests.objective.item` | Collect {name} | 收集{name} |

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
| `crafting.hint` | Up/Down: recipe   Left/Right: how many   Enter: make   Tab / Q / E: tab   Esc: back | 上／下：配方   左／右：數量   Enter：製作   Tab／Q／E：分頁   Esc：返回 |
| `crafting.all` | Recipes | 配方 |
| `crafting.disassemble` | Disassemble | 分解 |
| `crafting.gold` | Gold {gold} | 金幣 {gold} |
| `crafting.recipes` | Recipes | 配方 |
| `crafting.items` | Items to break down | 可分解的道具 |
| `crafting.nothing_to_break` | Nothing in the bag can be broken down. | 背包裡沒有能分解的東西。 |
| `crafting.can_make` | can make {count} | 可做 {count} |
| `crafting.owned` | x{count} | x{count} |
| `crafting.unknown` | You have not discovered this recipe yet. | 你還沒發現這個配方。 |
| `crafting.unknown_hint` | Learn it, or make it by its exact materials. | 學會它，或用正確的材料做出來。 |
| `crafting.makes` | Makes | 成品 |
| `crafting.gives` | Gives | 得到 |
| `crafting.fee` | Fee {fee} {currency} | 費用 {fee} {currency} |
| `crafting.materials` | Materials (held / needed) | 材料（持有／需要） |
| `crafting.chance` | Success chance {chance}% | 成功率 {chance}% |
| `crafting.qualities` | Quality: {tiers} | 品質：{tiers} |
| `crafting.quality_tier` | {quality} {percent}%+ | {quality} {percent}%以上 |
| `crafting.quantity` | How many: {count}  (most {limit}) | 數量：{count}（最多 {limit}） |
| `crafting.crafted_some` | Crafted {items} ({done} of {count} succeeded) | 製作了 {items}（{count} 次中成功 {done} 次） |
| `crafting.disassembled` | Broke down {item}: {items} | 分解了 {item}：{items} |

## Quest board, recruiting and gacha

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `board.accepted` | Accepted: {name} | 已接取：{name} |
| `board.count` | Taken {count} | 已接 {count} |
| `board.count_limit` | Taken {count} / {limit} | 已接 {count}／{limit} |
| `board.done_long` | Already done. | 已經完成了。 |
| `board.empty` | No quests on this board. | 告示板上沒有任務。 |
| `board.experience` | {amount} EXP | {amount} 經驗值 |
| `board.failed_long` | This quest failed. | 這個任務失敗了。 |
| `board.full` | You can take {count} of these at once. | 這類任務同時只能接 {count} 件。 |
| `board.hint` | Arrows: card   Enter: take / hand in   Space / F: turn over   Esc: back | 方向鍵：選卡片   Enter：接取／回報   Space／F：翻面   Esc：返回 |
| `board.locked_long` | Not open to you yet. | 還不能接這個任務。 |
| `board.needs` | After: {quests} | 需先完成：{quests} |
| `board.no_reward` | no reward | 沒有報酬 |
| `board.not_ready` | Finish the objectives first. | 請先完成目標。 |
| `board.objectives` | Objectives | 目標 |
| `board.repeatable` | repeatable | 可重複 |
| `board.reported` | Handed in: {name} | 已回報：{name} |
| `board.reward` | Reward | 報酬 |
| `board.state.active` | Taken | 進行中 |
| `board.state.available` | Open | 可接取 |
| `board.state.done` | Done | 已完成 |
| `board.state.failed` | Failed | 失敗 |
| `board.state.full` | Full | 已滿 |
| `board.state.locked` | Locked | 未開放 |
| `board.state.ready` | Report! | 可回報！ |
| `board.state.waiting` | Back in {time} | {time} 後重新張貼 |
| `board.time_left` | Time left {time} | 剩餘時間 {time} |
| `board.time_limit` | Time limit {minutes} min | 時限 {minutes} 分鐘 |
| `board.waiting_long` | Back on the board soon. | 很快就會重新張貼。 |
| `recruit.ask` | Hire {name} for {price}?  Enter: yes   Esc: no | 要花 {price} 雇用 {name} 嗎？  Enter：是   Esc：否 |
| `recruit.cannot_dismiss` | {name} cannot be sent away here. | 這裡不能遣散 {name}。 |
| `recruit.dismissed` | {name} left the party | {name} 離開了隊伍 |
| `recruit.empty` | Nobody is looking for work here. | 這裡沒有人在找工作。 |
| `recruit.free` | Free | 免費 |
| `recruit.full_long` | The party is full. | 隊伍已滿。 |
| `recruit.hint` | Up/Down: candidate   Enter: hire   X: send away   Esc: back | 上／下：候選人   Enter：雇用   X：遣散   Esc：返回 |
| `recruit.hint_no_dismiss` | Up/Down: candidate   Enter: hire   Esc: back | 上／下：候選人   Enter：雇用   Esc：返回 |
| `recruit.hired_long` | {name} is already in the party. | {name} 已經在隊伍裡了。 |
| `recruit.joined` | {name} joined the party (Lv {level}) | {name} 加入了隊伍（Lv {level}） |
| `recruit.last` | The last member cannot leave. | 最後一名隊員不能離開。 |
| `recruit.level` | Lv {level} | Lv {level} |
| `recruit.level_own` | Lv 1 | Lv 1 |
| `recruit.level_range` | Lv {low}-{high} | Lv {low}–{high} |
| `recruit.locked_long` | {name} will not join yet. | {name} 現在還不願意加入。 |
| `recruit.party` | Party {count} | 隊伍 {count} |
| `recruit.party_limit` | Party {count} / {limit} | 隊伍 {count}／{limit} |
| `recruit.poor_long` | You cannot afford it. | 錢不夠。 |
| `recruit.price` | Price {price} | 價格 {price} |
| `recruit.refund` | Sent away: {refund} back | 遣散時退還 {refund} |
| `recruit.state.full` | Party full | 隊伍已滿 |
| `recruit.state.hired` | In the party | 已在隊伍中 |
| `recruit.state.locked` | Not yet | 尚未開放 |
| `recruit.state.poor` | Too dear | 錢不夠 |
| `recruit.stats` | Stats | 能力值 |
| `gacha.closed` | This banner is closed. | 這個卡池已關閉。 |
| `gacha.duplicate` | → {item} | → {item} |
| `gacha.featured` | Rate up: {prizes} | 機率提升：{prizes} |
| `gacha.hint` | Left/Right: choose   Enter: pull   R: rates   H: history   Esc: back | 左／右：選擇   Enter：抽取   R：機率   H：紀錄   Esc：返回 |
| `gacha.hint.back` | Enter / Esc: back | Enter／Esc：返回 |
| `gacha.hint.results` | Enter / Esc: back to the banner | Enter／Esc：回到卡池 |
| `gacha.hint.show` | Enter: skip | Enter：略過 |
| `gacha.history` | Last pulls | 最近的抽取紀錄 |
| `gacha.history_button` | History | 抽取紀錄 |
| `gacha.more` | +{count} more (R) | 還有 {count} 項（R） |
| `gacha.multi` | Pull x{count} | 抽 {count} 次 |
| `gacha.no_history` | No pulls yet. | 還沒有抽過。 |
| `gacha.pity` | {rarity} guaranteed within {count} pulls | {count} 抽內必得 {rarity} |
| `gacha.poor` | Not enough {currency}. | {currency}不夠。 |
| `gacha.rates` | Rates | 機率 |
| `gacha.rates_button` | All rates | 完整機率 |
| `gacha.rule.featured` | ★ rate up x{times} | ★ 機率提升 x{times} |
| `gacha.rule.multi` | Every x{count}: at least one {rarity} | 每 {count} 連抽至少一個 {rarity} |
| `gacha.rule.pity` | {rarity} at the latest on pull {count} | 最晚第 {count} 抽必得 {rarity} |
| `gacha.rule.soft` | From pull {start} each pull adds {step}% | 從第 {start} 抽起，每抽提高 {step}% |
| `gacha.single` | Pull x1 | 抽 1 次 |
| `gacha.total` | Pulls so far: {count} | 已抽次數：{count} |

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
| `pets.party` | Party | 隊伍 |
| `pets.storage` | Storage | 寄放 |
| `pets.party_hint` | Up / Down: choose   Left / Right: party / storage   Enter: move   R: rename   Esc: back | 上／下：選擇   左／右：隊伍／寄放   Enter：移動   R：改名   Esc：返回 |
| `pets.party_full` | The party is full | 隊伍已滿 |
| `pets.no_storage` | There is nowhere to keep it | 沒有地方可以寄放 |
| `pets.last_one` | The last one must stay with you | 最後一隻必須留在身邊 |
| `pets.moved_in` | {name} joins the party | {name} 加入隊伍 |
| `pets.moved_out` | {name} goes into storage | {name} 送去寄放 |
| `pets.health` | HP {current}/{maximum} | HP {current}/{maximum} |
| `pets.learn_title` | {name} wants to learn {move} | {name} 想學會 {move} |
| `pets.learn_hint` | 1-9: forget that move and learn it   Esc: do not learn | 1-9：忘掉那一招來學   Esc：不學 |
| `pets.learned` | {name} learned {move} | {name} 學會了 {move} |
| `pets.not_learned` | {name} did not learn {move} | {name} 沒有學 {move} |

## Battle commands

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `battle.command.attack` | Attack | 攻擊 |
| `battle.command.skills` | Skills | 技能 |
| `battle.command.items` | Items | 道具 |
| `battle.command.escape` | Escape | 逃跑 |
| `battle.command.switch` | Switch | 交換 |
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
| `battle.hint.switch` | Send out another creature | 換另一隻上場 |
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
| `battle.reason.no_pp` | No uses left | 沒有使用次數了 |
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
| `battle.no_one` | No one can fight: the party has no creature standing | 沒有人能戰鬥：隊伍裡沒有站得住的生物 |
| `battle.switch.no_room` | There is no room on the stage | 場上沒有空位 |
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
| `capture.ball` | Throw which? 1-9: an item   Esc: cancel | 丟哪一個？1-9：道具   Esc：取消 |
| `capture.item_row` | {item} x{count}   {chance}% | {item} x{count}   {chance}% |
| `switch.title` | Send out which? | 派誰上場？ |
| `switch.row` | {name}   Lv {level}   HP {current}/{maximum} | {name}   Lv {level}   HP {current}/{maximum} |
| `switch.hint` | 1-9: choose | 1-9：選擇 |

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
| `points.ap` | AP | 能力點 |
| `points.skill_points` | SP | 技能點 |
| `points.stat_points` | Stat points | 屬性點 |
| `points.jp` | {name} JP | {name}職業點 |
| `socket.number` | Socket {number} | 孔 {number} |

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

## Equipment and enhance

| 鍵 | English | 引擎的繁體中文 |
| --- | --- | --- |
| `workshop.refined` | Refine: {outcome} | 精煉：{outcome} |
| `workshop.outcome.success` | success | 成功 |
| `workshop.outcome.failure` | failure | 失敗 |
| `workshop.outcome.protected` | failed, level kept | 失敗，等級保住了 |
| `workshop.took_out` | Took {name} out of {socket} | 從 {socket} 取下了 {name} |
| `workshop.socketed` | Socketed {name} into {socket} | 把 {name} 鑲進了 {socket} |
| `workshop.locked` | locked | 鎖住 |
| `workshop.empty` | empty | 空 |
| `workshop.socket_row` | {socket}: {value} | {socket}：{value} |
| `equipment.title` | Equipment | 裝備 |
| `equipment.member` | {name}  ·  Lv {level}  ·  {job}   (Q / E) | {name}  ·  Lv {level}  ·  {job}   (Q / E) |
| `equipment.hint` | Arrows: choose   Enter: change   X: take off   Q / E: member   Esc: back | 方向鍵：選擇   Enter：更換   X：卸下   Q / E：成員   Esc：返回 |
| `equipment.fits` | For {slot} | 可裝備於{slot} |
| `equipment.nothing_fits` | Nothing in the bag fits. | 背包裡沒有可以裝備的東西。 |
| `equipment.empty_slot` | Nothing worn here. | 這裡沒有裝備。 |
| `equipment.durability` | durability {now}/{most} | 耐久 {now}/{most} |
| `equipment.sockets` | Sockets {filled}/{total} | 鑲嵌孔 {filled}/{total} |
| `equipment.stats` | Stats | 能力值 |
| `enhance.title` | Enhance | 強化 |
| `enhance.member` | {name}  ·  Gold {gold}   (Q / E) | {name}  ·  金幣 {gold}   (Q / E) |
| `enhance.hint.refine` | Enter: refine   P: protection on / off   Tab: page   Q / E: member   Esc: back | Enter：精煉   P：保護開／關   Tab：換頁   Q / E：成員   Esc：返回 |
| `enhance.hint.sockets` | Enter: choose / socket   X: take out   Tab: page   Q / E: member   Esc: back | Enter：選擇／鑲嵌   X：取下   Tab：換頁   Q / E：成員   Esc：返回 |
| `enhance.hint.growth` | Enter: choose / unlock   Tab: page   Q / E: member   Esc: back | Enter：選擇／解鎖   Tab：換頁   Q / E：成員   Esc：返回 |
| `enhance.tab.refine` | Refine | 精煉 |
| `enhance.tab.sockets` | Sockets | 鑲嵌 |
| `enhance.tab.cards` | Cards | 卡片 |
| `enhance.tab.growth` | Growth | 成長 |
| `enhance.gear` | Worn gear | 身上的裝備 |
| `enhance.sockets` | Sockets | 鑲嵌孔 |
| `enhance.card_sockets` | Card sockets | 卡片孔 |
| `enhance.fits` | From the bag | 背包裡可用的 |
| `enhance.stages` | Growth stages | 成長階段 |
| `enhance.levels` | Refine levels | 精煉等級 |
| `enhance.level_row` | +{level}   {chance}%   {cost} {currency} | +{level}   {chance}%   {cost} {currency} |
| `enhance.no_growth` | This piece does not grow. | 這件裝備不會成長。 |
| `enhance.no_sockets` | This piece has no such socket. | 這件裝備沒有這種孔。 |
| `enhance.nothing_fits` | Nothing in the bag fits this socket. | 背包裡沒有能放進這個孔的東西。 |
| `enhance.unlocked` | {name} unlocked | 已解鎖 {name} |
| `enhance.destroyed` | the piece was destroyed | 裝備損毀了 |
| `enhance.cannot_refine` | This piece cannot be refined. | 這件裝備不能精煉。 |
| `enhance.max_level` | At the highest level (+{level}) | 已達最高等級（+{level}） |
| `enhance.next_level` | +{level} → +{next}   chance {chance}% | +{level} → +{next}   成功率 {chance}% |
| `enhance.price` | Price {cost} {currency} (have {have}) | 費用 {cost} {currency}（持有 {have}） |
| `enhance.materials` | Materials | 材料 |
| `enhance.material_row` | {name}  {have}/{need} | {name}  {have}/{need} |
| `enhance.fail.keep` | A failure loses nothing but the price | 失敗只會損失費用 |
| `enhance.fail.drop` | A failure drops one level | 失敗會降一級 |
| `enhance.fail.break` | A failure breaks the piece (repair it) | 失敗會讓裝備損壞（需要修理） |
| `enhance.fail.destroy` | A failure destroys the piece | 失敗會讓裝備消失 |
| `enhance.safe` | Always succeeds up to +{level} | +{level} 以前必定成功 |
| `enhance.protect` | {name} x{have}: protection {state} (P) | {name} x{have}：保護 {state}（P） |
| `enhance.preview` | At the next level | 下一級的效果 |
| `enhance.takes` | Takes: {tags} | 可放入：{tags} |
| `enhance.takes_any` | anything | 任何東西 |
| `enhance.removal.lost` | Taking it out destroys it | 取下時會消失 |
| `enhance.removal.kept` | Taking it out returns it to the bag | 取下後會回到背包 |
| `enhance.stage_done` | Complete | 已完成 |
| `enhance.needs` | Next rank needs | 下一階需要 |
| `enhance.counter_row` | {name}  {now}/{need} | {name}  {now}/{need} |
| `enhance.gives` | Gives | 獲得 |
| `enhance.opens_sockets` | Opens {count} socket(s) | 開啟 {count} 個孔 |
| `enhance.evolves` | Evolves into {name} | 進化為 {name} |
| `enhance.auto` | Unlocks by itself when ready | 條件達成時自動解鎖 |
| `enhance.ready` | Ready: Enter unlocks it | 可以解鎖：按 Enter |

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
