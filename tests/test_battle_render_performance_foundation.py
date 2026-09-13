from asteria.presentation import (
    BattleAssetPreloadRegistry,
    BattleFrameBudgetTracker,
    BattleRenderBatcher,
    BattleRenderDraw,
    BattleRenderVisibilityCuller,
    BattleTransientPool,
)

def draws(count=120):
    out=[]
    for i in range(count):
        out.append(BattleRenderDraw(
            f"d{i}",
            f"asset.{i%8}",
            layer=i%4,
            depth=i/1000,
            x=(i%20)*18,
            y=(i%6)*28,
            width=16,
            height=24,
            material_id=f"mat.{i%2}",
            atlas_id=f"atlas.{i%2}",
        ))
    return tuple(out)

def test_batcher_groups_many_draws_by_atlas_material_and_layer():
    batches=BattleRenderBatcher().build(draws(120))
    assert len(batches) <= 8
    assert sum(len(x.draws) for x in batches)==120

def test_batcher_preserves_depth_order_inside_batch():
    batches=BattleRenderBatcher().build(draws(40))
    for batch in batches:
        depths=[x.depth for x in batch.draws]
        assert depths==sorted(depths)

def test_visibility_culling_removes_offscreen_and_hidden_draws():
    culler=BattleRenderVisibilityCuller(min_x=0,min_y=0,max_x=320,max_y=180,padding=0)
    values=(
        BattleRenderDraw("inside","a",0,0,10,10,16,16),
        BattleRenderDraw("outside","a",0,0,500,10,16,16),
        BattleRenderDraw("hidden","a",0,0,10,10,16,16,visible=False),
    )
    result=culler.resolve(values)
    assert tuple(x.draw_id for x in result.visible)==("inside",)
    assert result.culled_ids==("outside","hidden")

def test_transient_pool_reuses_objects_without_unbounded_growth():
    pool=BattleTransientPool(32)
    first=[pool.acquire("vfx",{"i":i}) for i in range(32)]
    assert pool.active_count==32
    assert pool.acquire("overflow") is None
    ids=[x.object_id for x in first]
    for obj in first:
        assert pool.release(obj)
    second=[pool.acquire("popup") for _ in range(32)]
    assert sorted(x.object_id for x in second)==sorted(ids)
    assert pool.capacity==32
    assert pool.peak_active==32

def test_preload_registry_exposes_missing_assets_and_ready_state():
    p=BattleAssetPreloadRegistry()
    p.require("hero.sheet","boss.sheet","impact.vfx","hit.audio")
    assert not p.ready
    assert p.missing==("hero.sheet","boss.sheet","impact.vfx","hit.audio")
    p.mark_loaded("hero.sheet","impact.vfx")
    assert p.missing==("boss.sheet","hit.audio")
    p.mark_loaded("boss.sheet","hit.audio")
    assert p.ready

def test_frame_budget_tracker_counts_frames_over_60fps_budget():
    tracker=BattleFrameBudgetTracker(60)
    for ms in (10.0,12.0,16.0,17.0,25.0):
        metrics=tracker.record(ms)
    assert metrics.frame_count==5
    assert metrics.dropped_frames==2
    assert metrics.max_frame_ms==25.0
    assert 15.9 < metrics.average_frame_ms < 16.1

def test_stress_case_12_party_boss_adds_summon_and_vfx_batches_compactly():
    # Representative renderer-plan stress: 12 party bodies/HUD elements,
    # boss + 4 adds + summon + 300 VFX/transient draws.
    values=[]
    member_count=12+1+4+1
    for i in range(member_count):
        values.append(BattleRenderDraw(
            f"member.{i}","characters.atlas",1,i/100,40+i*8,60,32,48,
            material_id="sprite",atlas_id="characters.atlas",
        ))
    for i in range(300):
        values.append(BattleRenderDraw(
            f"vfx.{i}",f"vfx.asset.{i%12}",2,i/10000,
            (i%25)*18,(i%12)*18,24,24,
            material_id="additive" if i%2 else "alpha",
            atlas_id=f"vfx.atlas.{i%3}",
        ))
    cull=BattleRenderVisibilityCuller(max_x=320,max_y=180,padding=24).resolve(values)
    batches=BattleRenderBatcher().build(cull.visible)
    assert len(values)==318
    assert len(cull.visible) < 318
    assert len(batches) <= 8

def test_pool_stress_supports_thousands_of_acquire_release_cycles():
    pool=BattleTransientPool(128)
    seen=set()
    for _ in range(100):
        active=[pool.acquire("multi_hit") for _ in range(128)]
        seen.update(x.object_id for x in active)
        for obj in active:
            pool.release(obj)
    assert seen==set(range(128))
    assert pool.active_count==0
    assert pool.capacity==128

def test_batching_does_not_require_gameplay_semantics():
    values=(
        BattleRenderDraw("x","same",0,0,0,0,10,10,atlas_id="atlas"),
        BattleRenderDraw("y","same",0,1,10,0,10,10,atlas_id="atlas"),
    )
    batches=BattleRenderBatcher().build(values)
    assert len(batches)==1
    assert tuple(x.draw_id for x in batches[0].draws)==("x","y")
