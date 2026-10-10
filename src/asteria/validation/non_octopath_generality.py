from __future__ import annotations

from dataclasses import dataclass

from asteria.presentation import (
    BattleActionEntry,
    BattleInformationItem,
    BattleInformationPolicy,
    BattleInformationRuntime,
    BattleInteractionLayer,
    BattleInteractionProfile,
    BattleInteractionRuntime,
    BattleRosterDensityPolicy,
    BattleSideviewTemplateProfile,
    BattleSideviewTemplateRuntime,
    BattleSideviewZone,
)


@dataclass(frozen=True, slots=True)
class GeneralityArchetypeResult:
    archetype_id: str
    roster_size: int
    primary_count: int
    compact_count: int
    overflow_count: int
    action_count: int
    primary_layer_ids: tuple[str, ...]
    overflow_layer_ids: tuple[str, ...]
    persistent_info_count: int
    compact_info_count: int
    focused_info_count: int
    contextual_info_count: int
    info_overflow_count: int
    layout_member_count: int
    layout_overflow_count: int
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NonOctopathGeneralityReport:
    archetypes: tuple[GeneralityArchetypeResult, ...]
    shared_mechanisms: tuple[str, ...]
    no_reference_game_ids_required: bool


class NonOctopathGeneralityHarness:
    """Proves presentation mechanisms are not coupled to one reference JRPG.

    The scenarios deliberately vary party scale, command grammar, information
    density and side-view staging. They use opaque project-owned IDs and the
    same generic presentation runtimes.
    """

    def _run(self, spec):
        roster = tuple(f"{spec['prefix']}.member.{i}" for i in range(spec["roster"]))
        density = BattleRosterDensityPolicy(primary_limit=spec["primary"], compact_limit=spec["compact"]).resolve(
            roster, focus_member_id=roster[-1] if spec["focus_last"] else roster[0]
        )

        layers = tuple(
            BattleInteractionLayer(layer_id, label=label, role=role, order=i)
            for i, (layer_id, label, role) in enumerate(spec["layers"])
        )
        interaction = BattleInteractionRuntime(
            BattleInteractionProfile(layers, page_size=spec["page_size"], max_primary_layers=spec["max_layers"])
        )
        entries = tuple(
            BattleActionEntry(
                f"{spec['prefix']}.action.{i}",
                f"Action {i}",
                category=layers[i % len(layers)].layer_id,
            )
            for i in range(spec["actions"])
        )
        interaction.set_actions(entries)
        iv = interaction.view

        info = []
        for i in range(spec["persistent"]):
            info.append(
                BattleInformationItem(
                    f"{spec['prefix']}.persistent.{i}",
                    "resource",
                    f"Resource {i}",
                    i,
                    priority=100 - i,
                    visibility="persistent",
                    group="core",
                    member_id=roster[i % len(roster)],
                )
            )
        for i in range(spec["compact_info"]):
            info.append(
                BattleInformationItem(
                    f"{spec['prefix']}.compact.{i}",
                    "state",
                    f"State {i}",
                    i,
                    priority=50 - i,
                    visibility="compact",
                    group="state",
                    member_id=roster[i % len(roster)],
                )
            )
        for i in range(spec["focused"]):
            info.append(
                BattleInformationItem(
                    f"{spec['prefix']}.focused.{i}",
                    "detail",
                    f"Detail {i}",
                    i,
                    priority=30 - i,
                    visibility="focused",
                    group="detail",
                    member_id=roster[-1],
                )
            )
        for i in range(spec["contextual"]):
            info.append(
                BattleInformationItem(
                    f"{spec['prefix']}.context.{i}",
                    "context",
                    f"Context {i}",
                    i,
                    priority=20 - i,
                    visibility="contextual",
                    group="hot_context",
                    member_id=roster[0],
                )
            )
        policy = BattleInformationPolicy(
            persistent_limit=spec["info_caps"][0],
            compact_limit=spec["info_caps"][1],
            focused_limit=spec["info_caps"][2],
            contextual_limit=spec["info_caps"][3],
        )
        infov = BattleInformationRuntime(policy).resolve(
            info, focus_member_id=roster[-1], active_contexts=("hot_context",)
        )

        # Custom staging profile deliberately avoids the default reference preset.
        profile = BattleSideviewTemplateProfile(
            f"{spec['prefix']}.layout",
            BattleSideviewZone(f"{spec['prefix']}.zone.a", spec["x_a"], 40, 13, spec["face_a"]),
            BattleSideviewZone(f"{spec['prefix']}.zone.b", spec["x_b"], 44, 11, spec["face_b"]),
            left_hud_zone_id=f"{spec['prefix']}.hud.a",
            right_hud_zone_id=f"{spec['prefix']}.hud.b",
            battlefield_center_x=spec["center"],
            max_visible_per_zone=spec["layout_cap"],
        )
        split = spec["split"]
        layout = BattleSideviewTemplateRuntime(profile).resolve(
            left_member_ids=roster[:split], right_member_ids=roster[split:]
        )

        return GeneralityArchetypeResult(
            spec["id"],
            len(roster),
            len(density.primary_member_ids),
            len(density.compact_member_ids),
            len(density.overflow_member_ids),
            len(entries),
            tuple(x.layer_id for x in iv.primary_layers),
            tuple(x.layer_id for x in iv.overflow_layers),
            len(infov.persistent),
            len(infov.compact),
            len(infov.focused),
            len(infov.contextual),
            len(infov.overflow),
            len(layout.placements),
            len(layout.overflow_member_ids),
            tuple(spec["notes"]),
        )

    def run(self):
        specs = (
            dict(
                id="solo_reactive",
                prefix="solo",
                roster=1,
                primary=1,
                compact=0,
                focus_last=False,
                layers=(("intent", "Intent", "action"), ("reaction", "Reaction", "context")),
                page_size=4,
                max_layers=2,
                actions=7,
                persistent=3,
                compact_info=2,
                focused=3,
                contextual=2,
                info_caps=(3, 2, 3, 2),
                x_a=160,
                x_b=260,
                face_a="none",
                face_b="left",
                center=190,
                layout_cap=None,
                split=1,
                notes=("single controllable actor", "reaction-heavy command grammar", "no job/break assumptions"),
            ),
            dict(
                id="atb_squad",
                prefix="atb",
                roster=6,
                primary=3,
                compact=3,
                focus_last=True,
                layers=(
                    ("tech", "Tech", "action"),
                    ("item", "Supply", "action"),
                    ("stance", "Stance", "modifier"),
                    ("wait", "Wait", "timing"),
                ),
                page_size=6,
                max_layers=4,
                actions=28,
                persistent=8,
                compact_info=10,
                focused=5,
                contextual=4,
                info_caps=(6, 6, 5, 4),
                x_a=45,
                x_b=275,
                face_a="right",
                face_b="left",
                center=160,
                layout_cap=4,
                split=3,
                notes=(
                    "six-member ATB-style squad",
                    "stance and timing commands",
                    "dense gauges without fixed BP semantics",
                ),
            ),
            dict(
                id="monster_roster",
                prefix="monster",
                roster=18,
                primary=2,
                compact=5,
                focus_last=True,
                layers=(
                    ("move", "Moves", "action"),
                    ("swap", "Swap", "roster"),
                    ("capture", "Capture", "context"),
                    ("item", "Pack", "action"),
                    ("inspect", "Inspect", "information"),
                ),
                page_size=5,
                max_layers=3,
                actions=60,
                persistent=12,
                compact_info=24,
                focused=6,
                contextual=7,
                info_caps=(5, 7, 6, 4),
                x_a=80,
                x_b=240,
                face_a="right",
                face_b="left",
                center=160,
                layout_cap=3,
                split=9,
                notes=(
                    "large collection roster",
                    "swap/capture interaction grammar",
                    "presentation overflow is not gameplay cap",
                ),
            ),
            dict(
                id="tactical_raid",
                prefix="raid",
                roster=24,
                primary=6,
                compact=6,
                focus_last=True,
                layers=(
                    ("weapon", "Weapon", "action"),
                    ("support", "Support", "action"),
                    ("order", "Order", "command"),
                    ("formation", "Formation", "roster"),
                    ("device", "Device", "action"),
                    ("retreat", "Retreat", "system"),
                    ("scan", "Scan", "information"),
                    ("signal", "Signal", "context"),
                ),
                page_size=10,
                max_layers=5,
                actions=96,
                persistent=20,
                compact_info=30,
                focused=12,
                contextual=12,
                info_caps=(8, 8, 8, 6),
                x_a=25,
                x_b=295,
                face_a="right",
                face_b="left",
                center=160,
                layout_cap=6,
                split=12,
                notes=(
                    "24-unit raid roster",
                    "eight project-defined command layers",
                    "high information pressure with bounded surface",
                ),
            ),
        )
        results = tuple(self._run(x) for x in specs)
        return NonOctopathGeneralityReport(
            results,
            (
                "opaque action/category IDs",
                "adaptive roster density",
                "information hierarchy",
                "project-authored staging",
                "paging/overflow without gameplay caps",
            ),
            True,
        )
