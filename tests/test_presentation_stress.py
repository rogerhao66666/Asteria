from asteria.presentation import BattleRenderDraw
from asteria.validation import BattlePresentationStressHarness

def test_stress_draw_volume_is_high_density():
    report=BattlePresentationStressHarness().run(planner_iterations=2)
    assert report.total_draws >= 4000
    assert report.visible_draws > 3000
    assert report.culled_draws >= 1000

def test_culling_happens_before_batching_and_removes_offscreen_load():
    harness=BattlePresentationStressHarness(vfx_draws=1000,offscreen_draws=500)
    draws=harness.build_draws()
    culled=harness.culler.resolve(draws)
    batches=harness.batcher.build(culled.visible)
    assert len(culled.culled_ids) >= 500
    assert sum(len(x.draws) for x in batches)==len(culled.visible)

def test_batching_reduces_many_draws_to_small_group_count():
    report=BattlePresentationStressHarness().run(planner_iterations=1)
    assert report.batch_count < report.visible_draws // 20
    assert report.largest_batch_size > 100

def test_pool_is_bounded_and_reused_under_thousands_of_cycles():
    report=BattlePresentationStressHarness().run(planner_iterations=1)
    assert report.transient_capacity==512
    assert report.transient_peak_active==512
    assert report.transient_active_after_release==0

def test_preload_registry_is_ready_before_hot_processing():
    report=BattlePresentationStressHarness().run(planner_iterations=1)
    assert report.required_assets > 5
    assert report.preload_ready

def test_event_driven_motion_releases_5000_beats_with_one_coarse_update():
    report=BattlePresentationStressHarness().run(planner_iterations=1)
    assert report.motion_beats==5000
    assert report.motion_released_beats==5000
    assert report.motion_peak_active_beats > 0

def test_frame_budget_tracker_counts_only_frames_over_60fps_budget():
    report=BattlePresentationStressHarness().run(planner_iterations=1)
    assert report.synthetic_frame_count==10
    assert report.synthetic_dropped_frames==2
    assert report.synthetic_average_ms > 0

def test_planner_benchmark_is_informational_not_hardware_gate():
    report=BattlePresentationStressHarness().run(planner_iterations=3)
    assert report.planner_iterations==3
    assert report.planner_elapsed_ms >= 0

def test_culler_accepts_generator_without_materializing_input_contract():
    harness=BattlePresentationStressHarness(vfx_draws=2,offscreen_draws=0)
    draws=(
        BattleRenderDraw(str(i),"asset",0,0,10+i,10,5,5)
        for i in range(4)
    )
    result=harness.culler.resolve(draws)
    assert len(result.visible)==4

def test_batcher_accepts_generator_without_materializing_input_contract():
    harness=BattlePresentationStressHarness(vfx_draws=2,offscreen_draws=0)
    draws=(
        BattleRenderDraw(str(i),"asset",0,float(i),10,10,5,5,atlas_id="atlas.shared")
        for i in range(50)
    )
    batches=harness.batcher.build(draws)
    assert len(batches)==1
    assert len(batches[0].draws)==50

def test_stress_report_is_structurally_repeatable_ignoring_wall_clock():
    a=BattlePresentationStressHarness().run(planner_iterations=1)
    b=BattlePresentationStressHarness().run(planner_iterations=1)
    assert a.total_draws==b.total_draws
    assert a.visible_draws==b.visible_draws
    assert a.culled_draws==b.culled_draws
    assert a.batch_count==b.batch_count
    assert a.motion_released_beats==b.motion_released_beats
    assert a.synthetic_dropped_frames==b.synthetic_dropped_frames
