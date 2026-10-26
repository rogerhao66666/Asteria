# D89 實機截圖（Cocoa 真實視窗）

- `before/`：修改前的狀態頁（D88 時的版本）；`after/`：修改後。檔名開頭 `en_` 英文、`zh_` 繁體中文。
- 狀態頁（960×540，`after/*_status.png`）：Roger 點了 1 STR、1 HP、1 VIT 之後，選在 HP 那一列。
  左下是能力值表（等級、總計、基礎、加點、裝備、每點、＋），右邊是五組詳細屬性（攻擊、防禦、戰鬥、屬性攻擊、屬性抗性）。
  `status.json` 記錄每一列的數字與每一行的文字，`driver` 是 `cocoa`。
- 編輯器（`after/`，1600×1000）：`*_menu_pages_stat_groups.png`（遊戲系統 ▸ 選單頁面的分組表格）、
  `*_menu_pages_stat_lines.png`（各行表格：能力值、分組、顯示方式、範圍、自訂名稱、戰鬥判定）。`editor.json` 記錄平台與列數。
