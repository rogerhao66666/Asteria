from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.runtime import Camera2D

from .battle import BattlePresentationScene
from .battle_camera_feedback import BattleCameraFeedbackFrame
from .battle_feedback import BattleFeedbackRuntime, BattleValueKind
from .battle_hud import BattleHudMember
from .battle_party_layout import BattlePartyLayoutPolicy
from .battle_action_menu import BattleActionMenuView
from .battle_action_workflow import BattleActionWorkflowView
from .battle_result import BattleResultView
from .battle_runtime import BattlePresentationFrame
from .battle_turn_timeline import BattleTurnTimelineView
from .battle_ui_polish import BattleUiPolishProfile


def _finite(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class BattleUiLayoutProfile:
    virtual_width: int = 320
    virtual_height: int = 180
    margin: float = 8.0
    hud_panel_width: float = 112.0
    hud_row_height: float = 10.0
    timeline_y: float = 7.0
    result_panel_width: float = 196.0
    result_panel_height: float = 116.0

    def __post_init__(self):
        if self.virtual_width <= 0 or self.virtual_height <= 0:
            raise ValueError("virtual battle UI size must be positive")
        for name in ("margin", "hud_panel_width", "hud_row_height", "result_panel_width", "result_panel_height"):
            if _finite(getattr(self, name), name) < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True, slots=True)
class BattleUiText:
    text: str
    x: float
    y: float
    role: str = "body"
    align: str = "left"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiPanel:
    panel_id: str
    x: float
    y: float
    width: float
    height: float
    role: str = "panel"
    member_id: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiGaugeBar:
    member_id: str
    resource_id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    normalized: float
    current: float
    maximum: float
    presentation: str = "bar"
    segments: int = 0
    icon_asset_id: str | None = None


@dataclass(frozen=True, slots=True)
class BattleUiIcon:
    asset_id: str
    x: float
    y: float
    role: str
    member_id: str = ""
    label: str = ""


@dataclass(frozen=True, slots=True)
class BattleUiMarker:
    member_id: str
    x: float
    y: float
    primary: bool = False


@dataclass(frozen=True, slots=True)
class BattleUiFrame:
    scene_id: str
    background_asset_id: str
    combatant_draws: tuple
    panels: tuple[BattleUiPanel, ...]
    texts: tuple[BattleUiText, ...]
    gauges: tuple[BattleUiGaugeBar, ...]
    icons: tuple[BattleUiIcon, ...]
    markers: tuple[BattleUiMarker, ...]
    vfx: tuple
    screen_fx: tuple


class BattleUiComposer:
    """Composes existing Battle Presentation view-state into adapter-ready UI.

    This layer owns layout only. It never reads or mutates Battle Core, resolves
    targets, changes resources, advances scheduler time, or applies rewards.
    """

    def __init__(self, scene: BattlePresentationScene, layout=None, party_layout=None, polish=None):
        if not isinstance(scene, BattlePresentationScene):
            raise TypeError("scene must be BattlePresentationScene")
        self.scene = scene
        self.layout = layout or BattleUiLayoutProfile()
        if not isinstance(self.layout, BattleUiLayoutProfile):
            raise TypeError("layout must be BattleUiLayoutProfile")
        self.party_layout = party_layout or BattlePartyLayoutPolicy()
        if not isinstance(self.party_layout, BattlePartyLayoutPolicy):
            raise TypeError("party_layout must be BattlePartyLayoutPolicy")
        self.polish = polish or BattleUiPolishProfile()
        if not isinstance(self.polish, BattleUiPolishProfile):
            raise TypeError("polish must be BattleUiPolishProfile")

    def _anchor_screen(self, camera, member_id):
        try:
            visual = self.scene.visual_for(member_id)
        except KeyError:
            return None
        return camera.world_to_screen(visual.anchor.x, visual.anchor.y)

    def _hud_commands(self, members, side_by_member, placement_by_member=None, focus_member_id=None):
        panels, texts, gauges, icons = [], [], [], []
        L = self.layout

        # Explicit presentation placement wins. Legacy side metadata remains only
        # for backward compatibility with pre-Batch-105 projects.
        explicit = {str(k): str(v) for k, v in dict(placement_by_member or {}).items()}
        legacy = {str(k): str(v) for k, v in dict(side_by_member or {}).items()}

        # Legacy direct-call compatibility groups members by opaque side ID, but
        # never interprets side names. Distinct groups are assigned visual zones
        # deterministically by first appearance. Projects should prefer explicit
        # placement metadata when more than two presentation zones are desired.
        side_order = []
        for member in members:
            side = legacy.get(member.member_id, "")
            if side and side not in side_order:
                side_order.append(side)
        fallback_zone = {
            side: ("left" if index % 2 == 0 else "right")
            for index, side in enumerate(side_order)
        }

        zone_by_member = {}
        for member in members:
            member_id = member.member_id
            if member_id in explicit:
                zone_by_member[member_id] = explicit[member_id]
            else:
                side = legacy.get(member_id, "")
                zone_by_member[member_id] = fallback_zone.get(side, self.party_layout.default_zone)

        available_height = max(1.0, L.virtual_height - L.timeline_y - 42.0 - L.margin)
        layout = self.party_layout.resolve(
            [x.member_id for x in members],
            zone_by_member=zone_by_member,
            focus_member_id=focus_member_id,
            available_height=available_height,
        )
        member_by_id = {x.member_id: x for x in members}

        for zone_layout in layout.zones:
            density = zone_layout.density
            row_height = self.party_layout.row_height(density)
            right = zone_layout.zone == "right"
            center = zone_layout.zone == "center"
            for row_index, member_id in enumerate(zone_layout.visible_member_ids):
                member = member_by_id[member_id]
                if center:
                    x = (L.virtual_width - L.hud_panel_width) / 2
                elif right:
                    x = L.virtual_width - L.margin - L.hud_panel_width
                else:
                    x = L.margin

                # Stack upward from the lower battle HUD safe area.
                base_y = L.virtual_height - L.margin - 8.0
                y = base_y - row_index * row_height

                resource_limit = self.party_layout.resource_limit(density)
                ordered_gauges = sorted(
                    member.gauges,
                    key=lambda g: (-int(getattr(g, "priority", 0)), g.order, g.resource_id),
                )
                selected = ordered_gauges if resource_limit is None else ordered_gauges[:resource_limit]
                selected_ids = {g.resource_id for g in selected}
                selected = [g for g in member.gauges if g.resource_id in selected_ids]

                status_limit = self.party_layout.status_limit(density)
                selected_statuses = list(member.statuses)
                if status_limit is not None:
                    selected_statuses = selected_statuses[:status_limit]

                if density == "expanded":
                    height = max(24.0, 18.0 + len(selected) * L.hud_row_height)
                elif density == "compact":
                    height = max(20.0, 14.0 + len(selected) * 8.0)
                else:
                    height = 16.0

                panel_y = y - height
                focused = (
                    self.polish.focus_member_emphasis
                    and focus_member_id is not None
                    and member.member_id == str(focus_member_id)
                )
                panel_role = f"hud:{density}:focus" if focused else f"hud:{density}"
                name_role = f"member_name:{density}:focus" if focused else f"member_name:{density}"
                panels.append(BattleUiPanel(
                    f"hud:{member.member_id}", x, panel_y, L.hud_panel_width, height,
                    panel_role, member.member_id
                ))
                texts.append(BattleUiText(
                    member.member_id, x+4, panel_y+3, name_role, "left", member.member_id
                ))

                gy = panel_y + (13 if density != "minimal" else 9)
                for gauge in selected:
                    mode = str(gauge.presentation)
                    if density == "minimal":
                        # Minimal density shows only the highest-priority resource
                        # with no redundant label/value unless the project uses a
                        # number-style resource.
                        if mode in {"number", "contextual"}:
                            texts.append(BattleUiText(
                                f"{gauge.current:g}", x+L.hud_panel_width-4, panel_y+3,
                                f"resource_value:{mode}", "right", member.member_id
                            ))
                        else:
                            gauges.append(BattleUiGaugeBar(
                                member.member_id, gauge.resource_id, gauge.label,
                                x+38, panel_y+6, max(8.0, L.hud_panel_width-44), 4.0,
                                max(0.0, min(1.0, float(gauge.normalized))),
                                float(gauge.current), float(gauge.maximum),
                                mode, int(gauge.segments), gauge.icon_asset_id,
                            ))
                        continue

                    if gauge.show_label and density == "expanded":
                        texts.append(BattleUiText(
                            gauge.label, x+4, gy, "gauge_label", "left", member.member_id
                        ))

                    if mode in {"number", "contextual"}:
                        if gauge.show_value:
                            texts.append(BattleUiText(
                                f"{gauge.current:g}", x+L.hud_panel_width-4, gy,
                                f"resource_value:{mode}", "right", member.member_id
                            ))
                    else:
                        label_space = 30 if (gauge.show_label and density == "expanded") else 4
                        value_space = 26 if (gauge.show_value and not gauge.compact and density == "expanded") else 8
                        bar_x = x + label_space
                        bar_w = max(8.0, L.hud_panel_width - label_space - value_space)
                        gauges.append(BattleUiGaugeBar(
                            member.member_id, gauge.resource_id, gauge.label, bar_x, gy,
                            bar_w, 5.0 if density == "expanded" else 4.0,
                            max(0.0, min(1.0, float(gauge.normalized))),
                            float(gauge.current), float(gauge.maximum),
                            mode, int(gauge.segments), gauge.icon_asset_id,
                        ))
                        if gauge.show_value and not gauge.compact and density == "expanded":
                            texts.append(BattleUiText(
                                f"{gauge.current:g}/{gauge.maximum:g}",
                                x+L.hud_panel_width-4, gy, "gauge_value", "right", member.member_id
                            ))
                    gy += L.hud_row_height if density == "expanded" else 8.0

                if density != "minimal":
                    ix = x+4
                    iy = y-8
                    for status in selected_statuses:
                        if status.icon_asset_id:
                            icons.append(BattleUiIcon(
                                status.icon_asset_id, ix, iy, "status", member.member_id, status.label
                            ))
                            ix += 10

            if zone_layout.overflow_count:
                if zone_layout.zone == "right":
                    ox = L.virtual_width - L.margin
                    align = "right"
                elif zone_layout.zone == "center":
                    ox = L.virtual_width / 2
                    align = "center"
                else:
                    ox = L.margin
                    align = "left"
                texts.append(BattleUiText(
                    f"+{zone_layout.overflow_count}",
                    ox,
                    L.timeline_y + 31.0,
                    "hud_overflow",
                    align,
                    "",
                ))
        return panels, texts, gauges, icons

    def _action_menu_commands(self, menu):
        panels, texts, icons = [], [], []
        if menu is None:
            return panels, texts, icons
        if not isinstance(menu, BattleActionMenuView):
            raise TypeError("action_menu must be BattleActionMenuView")
        L, P = self.layout, self.polish
        width = min(P.interaction_width, L.virtual_width - 2 * L.margin)
        x = (L.virtual_width - width) / 2
        header_rows = (1 if menu.categories else 0) + (1 if menu.query else 0)
        body_rows = max(1, len(menu.entries))
        height = (
            2 * P.interaction_padding
            + header_rows * P.interaction_header_height
            + body_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        panels.append(BattleUiPanel("action_menu", x, y, width, height, "interaction:action_menu"))

        ty = y + P.interaction_padding
        if menu.categories:
            category_text = "  ".join(
                f"[{value}]" if value == menu.active_category else value
                for value in menu.categories
            )
            texts.append(BattleUiText(category_text, x + P.interaction_padding, ty, "action_categories", "left"))
            ty += P.interaction_header_height

        if menu.query:
            texts.append(BattleUiText(
                f"Filter: {menu.query}", x + P.interaction_padding, ty, "action_filter", "left"
            ))
            ty += P.interaction_header_height

        if not menu.entries:
            texts.append(BattleUiText(
                P.empty_label, x + width / 2, ty + 3, "action_empty", "center"
            ))
        else:
            for index, entry in enumerate(menu.entries):
                selected = index == menu.cursor
                role = "action_selected" if selected else ("action_entry" if entry.enabled else "action_disabled")
                prefix = P.selected_prefix if selected else P.idle_prefix
                texts.append(BattleUiText(
                    prefix + entry.label, x + P.interaction_padding + 2, ty, role, "left"
                ))
                if entry.cost_text:
                    texts.append(BattleUiText(
                        entry.cost_text, x + width - P.interaction_padding, ty,
                        "action_cost" if entry.enabled else "action_cost_disabled", "right"
                    ))
                if entry.icon_asset_id:
                    icons.append(BattleUiIcon(
                        entry.icon_asset_id, x + 1, ty, "action", "", entry.label
                    ))
                ty += P.interaction_row_height

            selected = menu.selected
            if selected is not None:
                footer = selected.detail
                footer_role = "action_detail"
                if not selected.enabled and selected.disabled_reason:
                    footer = selected.disabled_reason
                    footer_role = "action_disabled_reason"
                if footer:
                    texts.append(BattleUiText(
                        footer,
                        x + P.interaction_padding,
                        y + height - P.interaction_footer_height,
                        footer_role,
                        "left",
                    ))

        if menu.page_count > 1:
            texts.append(BattleUiText(
                f"{menu.page + 1}{P.page_separator}{menu.page_count}",
                x + width - P.interaction_padding,
                y + height - P.interaction_footer_height,
                "action_page",
                "right",
            ))
        return panels, texts, icons

    def _workflow_commands(self, workflow):
        panels, texts, icons = [], [], []
        if workflow is None:
            return panels, texts, icons
        if not isinstance(workflow, BattleActionWorkflowView):
            raise TypeError("action_workflow must be BattleActionWorkflowView")
        L, P = self.layout, self.polish
        width = min(P.interaction_width + 10.0, L.virtual_width - 2 * L.margin)
        x = (L.virtual_width - width) / 2
        option_rows = max(1, len(workflow.options))
        height = (
            2 * P.interaction_padding
            + 2 * P.interaction_header_height
            + option_rows * P.interaction_row_height
            + P.interaction_footer_height
        )
        y = max(
            L.timeline_y + 28.0,
            L.virtual_height - L.margin - P.interaction_bottom_gap - height,
        )
        panels.append(BattleUiPanel("action_workflow", x, y, width, height, "interaction:workflow"))
        texts.append(BattleUiText(
            workflow.label, x + P.interaction_padding, y + P.interaction_padding,
            "workflow_title", "left"
        ))

        if workflow.complete:
            texts.append(BattleUiText(
                "Ready", x + width/2, y + P.interaction_padding + P.interaction_header_height + 4,
                "workflow_complete", "center"
            ))
            return panels, texts, icons

        step = workflow.step
        step_y = y + P.interaction_padding + P.interaction_header_height
        texts.append(BattleUiText(
            f"{workflow.step_index + 1}{P.page_separator}{workflow.step_count}  {step.label}",
            x + P.interaction_padding, step_y, "workflow_step", "left"
        ))
        selected = set()
        for value in workflow.selections:
            if value.step_id == step.step_id:
                selected.update(value.option_ids)

        oy = step_y + P.interaction_header_height
        for option in workflow.options:
            is_selected = option.option_id in selected
            mark = P.selected_option_prefix if is_selected else P.idle_prefix
            if is_selected:
                role = "workflow_option_selected"
            else:
                role = "workflow_option" if option.enabled else "workflow_option_disabled"
            texts.append(BattleUiText(
                mark + option.label, x + P.interaction_padding + 3, oy, role, "left"
            ))
            if option.icon_asset_id:
                icons.append(BattleUiIcon(
                    option.icon_asset_id, x + 1, oy, "workflow_option", "", option.label
                ))
            oy += P.interaction_row_height
        return panels, texts, icons

    def _timeline_commands(self, timeline):
        panels, texts = [], []
        if timeline is None:
            return panels, texts
        L = self.layout
        width = min(L.virtual_width - 2*L.margin, 18.0 + 32.0*len(timeline.turns))
        panels.append(BattleUiPanel("timeline", (L.virtual_width-width)/2, L.timeline_y, width, 20.0, "timeline"))
        x = (L.virtual_width-width)/2 + 8
        for entry in timeline.turns:
            role = "timeline_current" if entry.is_current else "timeline_entry"
            texts.append(BattleUiText(entry.member_id, x, L.timeline_y+6, role, "center", entry.member_id))
            if timeline.scheduler_mode == "continuous":
                texts.append(BattleUiText(f"{entry.ready_time:g}", x, L.timeline_y+13, "timeline_time", "center", entry.member_id))
            x += 32
        for i, cast in enumerate(timeline.casts):
            texts.append(BattleUiText(
                f"{cast.actor_id}: {cast.ability_id} {int(round(cast.progress*100))}%",
                L.margin, L.timeline_y+26+i*9, "cast", "left", cast.actor_id
            ))
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
            texts.append(BattleUiText(f"{sign}{value.value:g}", x, y-lift, f"value:{value.kind.value}", "center", value.target_id))
        per_target = {}
        for label in feedback.labels:
            pos = self._anchor_screen(camera, label.target_id)
            if pos is None:
                continue
            offset = per_target.get(label.target_id, 0)
            per_target[label.target_id] = offset + 1
            texts.append(BattleUiText(label.label, pos[0], pos[1]-24.0-offset*8.0, "feedback_label", "center", label.target_id))
        return texts

    def _result_commands(self, result):
        panels, texts = [], []
        if result is None or not result.finished:
            return panels, texts
        L = self.layout
        x = (L.virtual_width-L.result_panel_width)/2
        y = (L.virtual_height-L.result_panel_height)/2
        panels.append(BattleUiPanel("battle_result", x, y, L.result_panel_width, L.result_panel_height, "result"))
        texts.append(BattleUiText(result.headline, L.virtual_width/2, y+12, "result_headline", "center"))
        line_y = y+28
        for reward in result.currencies:
            texts.append(BattleUiText(f"{reward.label}  +{reward.amount:g}", x+12, line_y, "reward", "left")); line_y += 9
        for reward in result.items:
            texts.append(BattleUiText(f"{reward.label}  x{reward.amount}", x+12, line_y, "reward", "left")); line_y += 9
        for reward in result.progression:
            suffix = f"  Rank {reward.old_rank} → {reward.new_rank}" if reward.new_rank != reward.old_rank else ""
            texts.append(BattleUiText(f"{reward.label}  +{reward.new_total-reward.old_total:g}{suffix}", x+12, line_y, "progression", "left")); line_y += 9
        return panels, texts

    def compose(
        self,
        camera: Camera2D,
        battle_frame: BattlePresentationFrame,
        *,
        hud_members=(),
        timeline: BattleTurnTimelineView | None = None,
        feedback: BattleFeedbackRuntime | None = None,
        camera_feedback: BattleCameraFeedbackFrame | None = None,
        result: BattleResultView | None = None,
        action_menu: BattleActionMenuView | None = None,
        action_workflow: BattleActionWorkflowView | None = None,
        side_by_member=None,
        placement_by_member=None,
        focus_member_id=None,
    ):
        if not isinstance(camera, Camera2D):
            raise TypeError("camera must be Camera2D")
        if not isinstance(battle_frame, BattlePresentationFrame):
            raise TypeError("battle_frame must be BattlePresentationFrame")
        if battle_frame.scene_id != self.scene.scene_id:
            raise ValueError("battle frame scene mismatch")
        hud_members = tuple(hud_members)
        if any(not isinstance(x, BattleHudMember) for x in hud_members):
            raise TypeError("hud_members must contain BattleHudMember")
        side_by_member = dict(side_by_member or {})

        panels, texts, gauges, icons = self._hud_commands(
            hud_members, side_by_member, placement_by_member, focus_member_id
        )
        pw, tw, iw = self._workflow_commands(action_workflow)
        panels.extend(pw); texts.extend(tw); icons.extend(iw)
        if action_workflow is None:
            pa, ta, ia = self._action_menu_commands(action_menu)
            panels.extend(pa); texts.extend(ta); icons.extend(ia)
        p2, t2 = self._timeline_commands(timeline)
        panels.extend(p2); texts.extend(t2)
        texts.extend(self._feedback_commands(camera, feedback))
        p3, t3 = self._result_commands(result)
        panels.extend(p3); texts.extend(t3)

        markers = ()
        screen_fx = ()
        if camera_feedback is not None:
            markers = tuple(BattleUiMarker(x.member_id, x.screen_x, x.screen_y, x.primary) for x in camera_feedback.targets)
            screen_fx = tuple(camera_feedback.screen_fx)

        if feedback is None:
            vfx = ()
        else:
            vfx = tuple(sorted(
                feedback.vfx,
                key=lambda item: (
                    int(dict(item.payload.get("staging", {}) or {}).get("layer", 0)),
                    -int(dict(item.payload.get("staging", {}) or {}).get("priority", 0)),
                    item.sequence,
                ),
            ))
        return BattleUiFrame(
            self.scene.scene_id, battle_frame.background_asset_id, tuple(battle_frame.combatant_draws),
            tuple(panels), tuple(texts), tuple(gauges), tuple(icons), markers, vfx, screen_fx,
        )
