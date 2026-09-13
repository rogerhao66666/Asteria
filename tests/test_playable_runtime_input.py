from types import SimpleNamespace

from asteria.runtime.playable_test_runtime import PlayableTestRuntime


def _runtime_for_build_input():
    runtime=object.__new__(PlayableTestRuntime)
    runtime.pg=SimpleNamespace(
        KEYDOWN=1,
        MOUSEBUTTONDOWN=2,
        K_c=10,
        K_LEFT=11,
        K_RIGHT=12,
        K_UP=13,
        K_DOWN=14,
        K_RETURN=15,
        K_SPACE=16,
    )
    runtime._ui_mode="build"
    runtime._menu_actor_index=0
    runtime._build_selection=0
    runtime._build_tab=0
    runtime._picker=None
    runtime._build_tab_rects=[]
    runtime._build_close_rect=(0,0,10,10)
    runtime._build_actor_buttons=[(10,0,10,10),(20,0,10,10)]
    runtime._build_action_rects=[(0,20+i*10,100,10) for i in range(7)]
    runtime._build_node_rects={}
    runtime._menu_actor=lambda: "hero"
    runtime.actions=[]
    runtime._activate_build_action=lambda actor,index:runtime.actions.append((actor,index))
    return runtime


def test_build_menu_uses_arrow_keys_and_enter():
    runtime=_runtime_for_build_input()
    event=lambda key:SimpleNamespace(type=runtime.pg.KEYDOWN,key=key)

    runtime._build_menu_input([event(runtime.pg.K_RIGHT)])
    runtime._build_menu_input([event(runtime.pg.K_DOWN),event(runtime.pg.K_RETURN)])

    assert runtime._build_tab==1
    assert runtime._build_selection==1
    assert runtime.actions==[("hero",1)]


def test_build_menu_rows_can_be_clicked():
    runtime=_runtime_for_build_input()
    click=SimpleNamespace(type=runtime.pg.MOUSEBUTTONDOWN,button=1,pos=(50,45))

    runtime._build_menu_input([click])

    assert runtime._build_selection==2
    assert runtime.actions==[("hero",2)]
