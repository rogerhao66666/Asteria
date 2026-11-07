"""The turn timeline, hit feedback and the battle result's commands."""

from __future__ import annotations

from asteria.presentation.battle.feedback import BattleValueKind
from asteria.presentation.battle.ui_parts import BattleUiPanel, BattleUiText, _value_text


class FeedbackCompositionMixin:
    """The turn timeline, hit feedback and the battle result's commands."""

    def _stands_right(self, member_id):
        """True for a member standing on the right half of the stage (the party's side by the
        usual staging); the turn bar only uses it to tint the tiles."""
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return True
        return visual.anchor.x > self.layout.virtual_width / 2

    def _timeline_commands(self, timeline):
        panels, texts = [], []
        if timeline is None:
            return panels, texts
        L = self.layout
        slot, padding = 32.0, 9.0
        capacity = max(1, int((L.virtual_width - 2 * L.margin - 2 * padding) // slot))
        turns = tuple(timeline.turns)[:capacity]
        width = 2 * padding + slot * len(turns)
        panels.append(
            BattleUiPanel(
                "timeline", (L.virtual_width - width) / 2, L.timeline_y, width, 24.0, "timeline"
            )
        )
        x = (L.virtual_width - width) / 2 + padding + slot / 2
        max_chars = max(3, int(slot // self.TIMELINE_CHAR_WIDTH))
        for entry in turns:
            # a tile per turn, tinted by the side of the field the member stands on
            ally = self._stands_right(entry.member_id)
            kind = "current" if entry.is_current else ("ally" if ally else "enemy")
            panels.append(
                BattleUiPanel(
                    f"turn:{entry.member_id}",
                    x - slot / 2 + 1.0,
                    L.timeline_y + 1.0,
                    slot - 2.0,
                    22.0,
                    f"timeline_tile:{kind}",
                    entry.member_id,
                )
            )
            role = "timeline_current" if entry.is_current else "timeline_entry"
            texts.append(
                BattleUiText(
                    self._fit(self._name(entry.member_id), max_chars),
                    x,
                    L.timeline_y + 7,
                    role,
                    "center",
                    entry.member_id,
                )
            )
            if timeline.scheduler_mode == "continuous":
                texts.append(
                    BattleUiText(
                        f"{entry.ready_time:.1f}",
                        x,
                        L.timeline_y + 16,
                        "timeline_time",
                        "center",
                        entry.member_id,
                    )
                )
            x += slot
        for i, cast in enumerate(timeline.casts):
            texts.append(
                BattleUiText(
                    f"{cast.actor_id}: {cast.ability_id} {int(round(cast.progress * 100))}%",
                    L.margin,
                    L.timeline_y + 26 + i * 9,
                    "cast",
                    "left",
                    cast.actor_id,
                )
            )
        return panels, texts

    def _feedback_commands(self, camera, feedback):
        texts = []
        if feedback is None:
            return texts
        for value in feedback.values:
            pos = self._anchor_screen(camera, value.target_id)
            if pos is None:
                continue
            x, y = pos
            lift = 10.0 + 12.0 * min(1.0, value.age / max(value.duration, 1e-9))
            sign = "+" if value.kind == BattleValueKind.HEAL and value.value >= 0 else ""
            texts.append(
                BattleUiText(
                    f"{sign}{_value_text(value.value)}",
                    x,
                    y - lift,
                    f"value:{value.kind.value}",
                    "center",
                    value.target_id,
                )
            )
        per_target = {}
        for label in feedback.labels:
            pos = self._anchor_screen(camera, label.target_id)
            if pos is None:
                continue
            offset = per_target.get(label.target_id, 0)
            per_target[label.target_id] = offset + 1
            texts.append(
                BattleUiText(
                    label.label,
                    pos[0],
                    pos[1] - 24.0 - offset * 8.0,
                    "feedback_label",
                    "center",
                    label.target_id,
                )
            )
        return texts

    def _result_commands(self, result):
        panels, texts = [], []
        if result is None or not result.finished:
            return panels, texts
        L = self.layout
        x = (L.virtual_width - L.result_panel_width) / 2
        y = (L.virtual_height - L.result_panel_height) / 2
        panels.append(
            BattleUiPanel(
                "battle_result", x, y, L.result_panel_width, L.result_panel_height, "result"
            )
        )
        texts.append(
            BattleUiText(result.headline, L.virtual_width / 2, y + 12, "result_headline", "center")
        )
        line_y = y + 28
        for reward in result.currencies:
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.amount:g}", x + 12, line_y, "reward", "left"
                )
            )
            line_y += 9
        for reward in result.items:
            texts.append(
                BattleUiText(f"{reward.label}  x{reward.amount}", x + 12, line_y, "reward", "left")
            )
            line_y += 9
        for reward in result.progression:
            rank = "battle.result.rank", "Rank {old} → {new}"
            suffix = (
                "  " + self._tr(*rank, old=reward.old_rank, new=reward.new_rank)
                if reward.new_rank != reward.old_rank
                else ""
            )
            texts.append(
                BattleUiText(
                    f"{reward.label}  +{reward.new_total - reward.old_total:g}{suffix}",
                    x + 12,
                    line_y,
                    "progression",
                    "left",
                )
            )
            line_y += 9
        return panels, texts
