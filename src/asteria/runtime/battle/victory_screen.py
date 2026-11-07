"""Victory results screen: pages of rewards, each hero's experience and level-up, and the spoils.

``VictoryScreen`` holds the page cursor (confirm moves on); ``draw`` paints the current page with a
host that offers ``text()``, ``panel()`` and a ``screen`` surface (the playable runtime).
"""

from __future__ import annotations


class VictoryScreen:
    def __init__(
        self, aftermath, *, item_names=None, currency_names=None, stat_names=None, tr=None
    ):
        self.aftermath = aftermath
        self.tr = tr  # GameSessionRuntime.tr: the screen's own words in the player's language
        self.pages = aftermath.pages(
            item_names=item_names, currency_names=currency_names, stat_names=stat_names, tr=tr
        )
        self.index = 0
        self.age = 0.0

    @property
    def page(self):
        return self.pages[self.index]

    @property
    def finished(self):
        return self.index >= len(self.pages)

    def update(self, dt):
        self.age += max(0.0, float(dt))

    def confirm(self):
        """Next page; returns True once the last page has been dismissed."""
        self.index += 1
        self.age = 0.0
        return self.finished

    def draw(self, host):
        if self.finished:
            return
        width, height = host.screen.get_size()
        page = self.page
        rows = max(1, len(page.lines))
        box_w = min(width - 80, 520)
        box_h = 96 + rows * 30
        x, y = (width - box_w) // 2, max(40, (height - box_h) // 2)
        host.panel((x, y, box_w, box_h), fill=(12, 16, 30, 232), border=(214, 188, 110))
        host.text(page.title, x + box_w // 2, y + 30, size=34, color=(255, 226, 140), center=True)
        for i, line in enumerate(page.lines):
            color = (255, 226, 140) if i in page.highlights else (236, 240, 250)
            host.text(line, x + 36, y + 70 + i * 30, size=26, color=color)
        more = self.index + 1 < len(self.pages)
        tr = self.tr or (lambda key, english: english)
        hint = (
            tr("victory.next", "Enter: next") if more else tr("victory.close", "Enter: continue")
        )
        host.text(
            f"{hint}   ({self.index + 1}/{len(self.pages)})",
            x + box_w - 18,
            y + box_h - 14,
            size=20,
            color=(160, 170, 195),
            anchor="bottomright",
        )
