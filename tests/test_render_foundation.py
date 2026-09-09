from asteria.graphics import *
from asteria.runtime import Camera2D
from asteria.render import *
def test_2d_native_25d_render_environment_pipeline():
    mat=Material2D("hero","hero_albedo","hero_normal")
    draw=LitSpriteDraw("hero",(0,0,16,16),0,20,16,16,0,.5,1.0)
    cam=Camera2D()
    shadow=build_shadow_command(ShadowCaster2D("wall",((0,0),(10,0),(10,10))),cam)
    light=build_light_command(Light2D("torch",x=20,y=20,casts_shadow=True),cam)
    env=build_environment_command(
        ambient=AmbientLight2D(intensity=.2),
        fog=Fog2D(.1),
        particle_emitters=(ParticleEmitter2D("dust"),),
        post_stack=PostProcessStack((PostEffect2D("color_grade"),))
    )
    plan=build_frame_plan(draws=(draw,),shadow_casters=(shadow,),lights=(light,),environment=env)
    b=HeadlessRenderBackend();execute_frame(plan,b,(mat,))
    names=[x[0] for x in b.ops]
    assert names==["begin","sprite","shadow","ambient","light","particles","fog","post","end"]
