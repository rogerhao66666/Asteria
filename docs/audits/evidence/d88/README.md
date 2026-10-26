# D88 實機截圖（Cocoa 真實視窗）

- `before/`：修改前（`git archive HEAD` 的副本）；`after/`：修改後。檔名開頭 `en_` 英文、`zh_` 繁體中文。
- 地圖（960×540）：`*_field_chest`（從下往上走向星落寶箱）、`*_field_chest_side`（從左往右走向寶箱）。
  `*_field.json` 是實測位置，`driver` 是 `cocoa`：修改前往右走到 x=540（穿過兩個寶箱），修改後停在 472.8（寶箱左邊）；
  兩邊往上走都停在寶箱下緣；房子的門照樣進得去（`house_door_scene` = Roger's House）。
- 選單（`scripts/ui_tour_live_check.py … --size 960x540`）：裝備 `equipment*`（武器圖示放大到填滿武器格）、
  道具頁 `page_items`、`page_items_potions`（藥水的說明與「選單可用」）、`page_items_gear`（`after/` 才有：背包裡的武器與它的能力值）。
- 編輯器（`after/`，1600×1000）：`*_inspector_starfall`／`_roger`（整張圖阻擋＋紅框預覽）、`*_inspector_mira`（腳下阻擋）、
  `*_editor_chest_window`、`*_menu_layout_doll`（紙娃娃預覽：每格都穿上範例裝備）、`*_menu_layout_slots`（格位表的圖示欄）。
  `editor.json` 記錄各下拉選單的值與表格欄名。
