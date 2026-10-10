from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from asteria.presentation import (
    BattleAssetPreloadRegistry,
    BattleFrameBudgetTracker,
    BattleMotionBeat,
    BattleMotionRuntime,
    BattleMotionSequence,
    BattleRenderBatcher,
    BattleRenderDraw,
    BattleRenderVisibilityCuller,
    BattleTransientPool,
)


@dataclass(frozen=True, slots=True)
class PresentationStressReport:
    total_draws: int
    visible_draws: int
    culled_draws: int
    batch_count: int
    largest_batch_size: int
    transient_capacity: int
    transient_peak_active: int
    transient_active_after_release: int
    required_assets: int
    preload_ready: bool
    motion_beats: int
    motion_released_beats: int
    motion_peak_active_beats: int
    synthetic_frame_count: int
    synthetic_dropped_frames: int
    synthetic_average_ms: float
    planner_iterations: int
    planner_elapsed_ms: float


class BattlePresentationStressHarness:
    """Backend-neutral high-density battle presentation stress scenario.

    This measures planning/runtime structure only. It does not claim GPU/render
    throughput because no concrete renderer/backend is involved here.
    """

    def __init__(self, *, vfx_draws=3000, offscreen_draws=1000):
        self.vfx_draws = int(vfx_draws)
        self.offscreen_draws = int(offscreen_draws)
        if self.vfx_draws < 1 or self.offscreen_draws < 0:
            raise ValueError("invalid stress draw counts")
        self.culler = BattleRenderVisibilityCuller()
        self.batcher = BattleRenderBatcher()
        self.pool = BattleTransientPool(512)
        self.preload = BattleAssetPreloadRegistry()
        self.frame_budget = BattleFrameBudgetTracker(60)

    def build_draws(self):
        draws = []
        # 12 party portraits/cards.
        for i in range(12):
            draws.append(
                BattleRenderDraw(
                    f"party.{i}",
                    "atlas.party",
                    20,
                    float(i),
                    8 + (i % 4) * 28,
                    120 + (i // 4) * 14,
                    24,
                    24,
                    atlas_id="atlas.party",
                )
            )
        # Boss + four adds + one summon.
        combatants = (("boss", 2.8), ("add.0", 1), ("add.1", 1), ("add.2", 1), ("add.3", 1), ("summon", 1))
        for i, (name, scale) in enumerate(combatants):
            draws.append(
                BattleRenderDraw(
                    name,
                    "atlas.combatants",
                    10,
                    100 + i,
                    150 + i * 15,
                    40 + i * 4,
                    32 * scale,
                    48 * scale,
                    atlas_id="atlas.combatants",
                )
            )
        # 80 action-menu rows/icons split across two UI atlases.
        for i in range(80):
            atlas = "atlas.ui.skills" if i < 60 else "atlas.ui.misc"
            draws.append(
                BattleRenderDraw(
                    f"action.{i}",
                    atlas,
                    30,
                    float(i),
                    4 + (i % 10) * 30,
                    4 + (i // 10) * 12,
                    26,
                    10,
                    atlas_id=atlas,
                )
            )
        # Status/resource clutter: 12 members x 8 indicators.
        for member in range(12):
            for j in range(8):
                draws.append(
                    BattleRenderDraw(
                        f"indicator.{member}.{j}",
                        "atlas.ui.status",
                        31,
                        float(member * 8 + j),
                        6 + (member % 4) * 32 + j * 2,
                        92 + (member // 4) * 12,
                        8,
                        8,
                        atlas_id="atlas.ui.status",
                    )
                )
        # Dense VFX sharing a small atlas/material family.
        for i in range(self.vfx_draws):
            atlas = f"atlas.vfx.{i % 6}"
            draws.append(
                BattleRenderDraw(
                    f"vfx.{i}",
                    atlas,
                    15 + i % 3,
                    float(i % 50),
                    20 + (i % 25) * 11,
                    20 + ((i // 25) % 10) * 12,
                    16,
                    16,
                    material_id=f"vfx.material.{i % 3}",
                    atlas_id=atlas,
                )
            )
        # Explicitly offscreen effects that should be culled before batching.
        for i in range(self.offscreen_draws):
            draws.append(
                BattleRenderDraw(
                    f"offscreen.{i}",
                    "atlas.vfx.offscreen",
                    15,
                    0,
                    1000 + i,
                    1000,
                    16,
                    16,
                    atlas_id="atlas.vfx.offscreen",
                )
            )
        return tuple(draws)

    def build_motion(self, count=5000):
        count = int(count)
        beats = tuple(
            BattleMotionBeat(
                f"beat.{i}",
                i * 0.0005,
                "vfx" if i % 3 else "camera",
                f"cue.{i % 11}",
                duration=0.001 if i % 5 else 0.004,
            )
            for i in range(count)
        )
        return BattleMotionSequence("stress.motion", max(3.0, count * 0.0005 + 0.1), beats)

    def run(self, *, planner_iterations=20):
        draws = self.build_draws()

        # All hot assets are known before frame processing.
        required = tuple(sorted({d.asset_id for d in draws} | {d.atlas_id for d in draws if d.atlas_id}))
        self.preload.require(*required)
        self.preload.mark_loaded(*required)

        # Representative transient pressure with bounded reuse.
        held = []
        for i in range(self.pool.capacity):
            obj = self.pool.acquire("vfx", {"i": i})
            if obj is not None:
                held.append(obj)
        for obj in held:
            self.pool.release(obj)
        for i in range(5000):
            obj = self.pool.acquire("popup", i)
            if obj is not None:
                self.pool.release(obj)

        start = perf_counter()
        last_cull = None
        last_batches = ()
        planner_iterations = int(planner_iterations)
        for _ in range(planner_iterations):
            last_cull = self.culler.resolve(draws)
            last_batches = self.batcher.build(last_cull.visible)
        elapsed_ms = (perf_counter() - start) * 1000.0

        motion = self.build_motion()
        clock = BattleMotionRuntime()
        clock.start(motion)
        # One coarse host update should still release every event boundary.
        clock.update(10.0)
        motion_metrics = clock.metrics()

        # Synthetic frame times verify accounting without claiming hardware fps.
        for ms in (8.0, 9.0, 10.5, 12.0, 14.0, 16.0, 16.6, 17.2, 20.0, 11.0):
            self.frame_budget.record(ms)
        fm = self.frame_budget.metrics()

        return PresentationStressReport(
            len(draws),
            len(last_cull.visible),
            len(last_cull.culled_ids),
            len(last_batches),
            max((len(x.draws) for x in last_batches), default=0),
            self.pool.capacity,
            self.pool.peak_active,
            self.pool.active_count,
            len(required),
            self.preload.ready,
            len(motion.beats),
            motion_metrics.released_beats,
            motion_metrics.peak_active_beats,
            fm.frame_count,
            fm.dropped_frames,
            fm.average_frame_ms,
            planner_iterations,
            elapsed_ms,
        )
