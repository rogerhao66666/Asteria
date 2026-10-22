"""Write docs/BUILT_IN_TEXT_KEYS.md: every built-in word a game's screens draw, by key, with its
English and the engine's Traditional Chinese (``rpg/built_in_text.py``).

    python scripts/built_in_text_keys.py

Run it after adding or changing a built-in word; ``tests/test_built_in_text.py`` checks that
the page lists every key.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

PAGE = REPO / "docs" / "BUILT_IN_TEXT_KEYS.md"
HEAD = """# 遊戲內建字的翻譯鍵

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
"""


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ") or " "


def page():
    from asteria.rpg.built_in_text import GROUPS, engine_translations

    chinese = engine_translations("zh-TW")
    lines = [HEAD]
    total = sum(len(rows) for _, rows in GROUPS)
    lines.append(f"共 {total} 個鍵，{len(GROUPS)} 組。\n")
    for title, rows in GROUPS:
        lines.append(f"## {title}\n")
        lines.append("| 鍵 | English | 引擎的繁體中文 |")
        lines.append("| --- | --- | --- |")
        for key, english in rows:
            lines.append(f"| `{key}` | {_cell(english)} | {_cell(chinese.get(key, ''))} |")
        lines.append("")
    return "\n".join(lines)


def main():
    PAGE.write_text(page(), encoding="utf-8")
    print("wrote", PAGE.relative_to(REPO))


if __name__ == "__main__":
    main()
