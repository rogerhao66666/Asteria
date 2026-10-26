# D87 實機截圖（Cocoa 真實視窗，960×540）

- `before/`：修改前（`git archive HEAD` 的副本）；`after/`：修改後。檔名開頭 `en_` 英文、`zh_` 繁體中文。
- 地圖：`*_field_start`、`*_field_house`（往上走進房子）、`*_field_npc`（往左走進 Mira）、
  `*_field_bottom`（地圖底部與提示框）、`*_field_walk0..3` 與 `en_field_walk_strip`（連續四格走路）。
  `*_field.json` 是實測位置，`driver` 是 `cocoa`。
- 選單（`scripts/ui_tour_live_check.py … --size 960x540`）：寶箱 `gacha*`、裝備 `equipment*`、強化 `enhance_*`、
  製作 `crafting*`、懸賞板 `board*`、公會 `recruit*`、商店 `shop_*`、任務、背包、寵物、狀態四頁 `status*`、
  暫停 `pause`、技能樹；`after/` 另有新的狀態頁 `page_status`、道具頁 `page_items`、`page_items_potions`。
  `results.json` 列出拍到的畫面與錯誤（兩次都沒有錯誤）。
