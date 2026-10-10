from __future__ import annotations

from dataclasses import dataclass

from .battle_combatant_visuals import BattleCombatantVisualState
from .battle_information import BattleInformationView, BattleRosterSummary
from .battle_interaction import BattleInteractionView


@dataclass(frozen=True, slots=True)
class BattleUiMemberCard:
    member_id: str
    density: str
    focused: bool
    portrait_asset_id: str | None
    small_portrait_asset_id: str | None
    icon_asset_id: str | None
    visible_information_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattleUiActionSurface:
    stage: str
    root_layer_ids: tuple[str, ...]
    overflow_layer_ids: tuple[str, ...]
    entry_ids: tuple[str, ...]
    contextual_entry_ids: tuple[str, ...]
    selected_action_id: str | None
    target_ids: tuple[str, ...]
    modifier_ids: tuple[str, ...]
    can_confirm: bool


@dataclass(frozen=True, slots=True)
class BattleUiBattlefieldVisual:
    member_id: str
    asset_id: str
    state_id: str
    clip_role: str
    scale_x: float
    scale_y: float
    anchor_x: float
    anchor_y: float
    offset_x: float
    offset_y: float
    z_order: int


@dataclass(frozen=True, slots=True)
class BattleUiAssemblyFrame:
    member_cards: tuple[BattleUiMemberCard, ...]
    reserve_overflow_ids: tuple[str, ...]
    battlefield_visuals: tuple[BattleUiBattlefieldVisual, ...]
    action_surface: BattleUiActionSurface
    persistent_information_ids: tuple[str, ...]
    compact_information_ids: tuple[str, ...]
    focused_information_ids: tuple[str, ...]
    contextual_information_ids: tuple[str, ...]
    information_overflow_ids: tuple[str, ...]
    revision: int


class BattleUiAssemblyRuntime:
    """Combines existing presentation projections into one renderer-ready view.

    It never resolves gameplay. It only assembles already-projected interaction,
    information, roster-density and combatant-visual state.
    """

    def __init__(self):
        self.revision = 0
        self._frame = BattleUiAssemblyFrame(
            (),
            (),
            (),
            BattleUiActionSurface("root", (), (), (), (), None, (), (), False),
            (),
            (),
            (),
            (),
            (),
            0,
        )

    @property
    def frame(self):
        return self._frame

    @staticmethod
    def _action_surface(view: BattleInteractionView):
        entries = ()
        if view.menu_view is not None:
            entries = tuple(x.action_id for x in view.menu_view.entries)
        contextual = tuple(x.action_id for x in view.contextual_entries)
        return BattleUiActionSurface(
            view.stage,
            tuple(x.layer_id for x in view.primary_layers),
            tuple(x.layer_id for x in view.overflow_layers),
            entries,
            contextual,
            view.selected_action_id,
            tuple(view.target_ids),
            tuple(view.modifier_ids),
            bool(view.can_confirm),
        )

    @staticmethod
    def _information_ids(view: BattleInformationView):
        return (
            tuple(x.info_id for x in view.persistent),
            tuple(x.info_id for x in view.compact),
            tuple(x.info_id for x in view.focused),
            tuple(x.info_id for x in view.contextual),
            tuple(x.info_id for x in view.overflow),
        )

    @staticmethod
    def _member_card(member_id, density, focused, visual, information):
        if visual is None or not visual.hud_visible:
            return None
        ids = []
        for item in (
            *information.persistent,
            *information.compact,
            *information.focused,
            *information.contextual,
        ):
            if item.member_id in (None, member_id) and item.info_id not in ids:
                ids.append(item.info_id)
        return BattleUiMemberCard(
            member_id,
            density,
            bool(focused),
            visual.portrait_asset_id,
            visual.small_portrait_asset_id,
            visual.icon_asset_id,
            tuple(ids),
        )

    @staticmethod
    def _battlefield_visual(state):
        if state is None or not state.battlefield_visible:
            return None
        t = state.transform
        return BattleUiBattlefieldVisual(
            state.member_id,
            state.battlefield_asset_id,
            state.state_id,
            state.clip_role,
            float(t.scale_x),
            float(t.scale_y),
            float(t.anchor_x),
            float(t.anchor_y),
            float(t.offset_x),
            float(t.offset_y),
            int(t.z_order),
        )

    def assemble(
        self,
        *,
        interaction: BattleInteractionView,
        information: BattleInformationView,
        roster: BattleRosterSummary,
        visuals,
    ):
        visual_map = {str(x.member_id): x for x in visuals}
        cards = []
        for member_id in roster.primary_member_ids:
            card = self._member_card(
                member_id,
                "full",
                member_id == roster.focus_member_id,
                visual_map.get(member_id),
                information,
            )
            if card is not None:
                cards.append(card)
        for member_id in roster.compact_member_ids:
            card = self._member_card(
                member_id,
                "compact",
                member_id == roster.focus_member_id,
                visual_map.get(member_id),
                information,
            )
            if card is not None:
                cards.append(card)

        battlefield = []
        for member_id, state in sorted(visual_map.items()):
            draw = self._battlefield_visual(state)
            if draw is not None:
                battlefield.append(draw)
        battlefield.sort(key=lambda x: (x.z_order, x.member_id))

        p, c, f, x, o = self._information_ids(information)
        self.revision += 1
        self._frame = BattleUiAssemblyFrame(
            tuple(cards),
            tuple(roster.overflow_member_ids),
            tuple(battlefield),
            self._action_surface(interaction),
            p,
            c,
            f,
            x,
            o,
            self.revision,
        )
        return self._frame
