from __future__ import annotations

import json
from pathlib import Path

from asteria.core import Transform
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
from asteria.runtime.audio_mixer import AudioMixer
from asteria.runtime.collision import CollisionWorld
from asteria.runtime.input_map import InputActionTracker
from asteria.runtime.game_menus import GAME_OVER_OPTIONS, PAUSE_OPTIONS, MenuCursor, ShopScreen, quest_rows


WALK_ROW_BY_FACING = {"down": 0, "left": 1, "right": 2, "up": 3}
WALK_PATTERN_SEQUENCE = (0, 1, 2, 1)


def walking_row_index(facing: str) -> int:
    return WALK_ROW_BY_FACING.get(facing, 0)


def walking_pattern_index(field_step: int) -> int:
    """Use MV's 0-1-2-1 walk loop; never jump directly from stride to stride."""
    return WALK_PATTERN_SEQUENCE[(max(0, int(field_step)) // 8) % len(WALK_PATTERN_SEQUENCE)]


def field_player_render_size(frame_size, render_width=64) -> tuple[int, int]:
    """Scale field sprites to ``render_width`` while preserving each source frame's ratio."""
    frame_w, frame_h = (int(frame_size[0]), int(frame_size[1]))
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("player frame dimensions must be positive")
    render_w = int(render_width)
    render_h = max(1, round(frame_h * render_w / frame_w))
    return render_w, render_h


def _load_manifest(resource_root):
    path=Path(resource_root)/"playable_test_manifest.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema")!="asteria.playable_test_content" or data.get("version")!=1:
        raise ValueError("unsupported playable test manifest")
    return data


class PlayableTestRuntime:
    """Small human-operable pygame adapter for serialized Asteria reference games.

    This module is intentionally adapter/test-content code. Game rules remain in
    Project + GameRuntimeSave + GameSessionRuntime. The adapter only handles
    input, pixels, simple menu navigation and VFX playback.
    """

    def __init__(self, project, runtime_save, resource_root, *, width=960, height=540):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError(
                "Playable reference game requires pygame-ce. "
                "Install with: pip install 'pygame-ce>=2.5'"
            ) from exc

        self.pg=pygame
        self.project=project
        self.resource_root=Path(resource_root)
        self.manifest=_load_manifest(self.resource_root)
        self.game=GameSessionRuntime(project,runtime_save)
        self.save=runtime_save
        self.width=int(width); self.height=int(height)
        self.screen=None; self.clock=None
        self.running=True
        self.message=""
        self.message_until=0
        self._field_step=0
        self._held_interact=False
        self._battle_skill_index=0
        self._last_action_name=""
        self._victory=False
        self._defeat=False
        self._loaded={}
        self._ui_mode="title"
        self._menu_actor_index=0
        self._boost_level=0
        self._turn_actor=None
        self._victory_summary=[]
        self._fonts={}
        self._battle_presentation=create_battle_presentation_adapter(self)
        self._pause_menu=MenuCursor(PAUSE_OPTIONS)
        self._game_over_menu=MenuCursor(GAME_OVER_OPTIONS)
        self._shop_screen=None
        self._quest_return="field"

    def path(self, rel):
        return self.resource_root/str(rel)

    def load_image(self, rel):
        rel=str(rel)
        if rel not in self._loaded:
            self._loaded[rel]=self.pg.image.load(self.path(rel)).convert_alpha()
        return self._loaded[rel]

    def open(self):
        self.pg.init()
        self.screen=self.pg.display.set_mode((self.width,self.height))
        self.pg.display.set_caption(self.manifest.get("title","Asteria Playable Test"))
        self.clock=self.pg.time.Clock()
        from asteria.platform.pygame_input import PygameInputSource
        self.input_source=PygameInputSource(self.pg)
        self.input=InputActionTracker(self.project.input_map)
        from asteria.platform.pygame_audio import open_audio_device
        self.audio=AudioMixer(open_audio_device(self.pg),self._audio_path)
        return self

    def _audio_path(self, asset_id):
        """Manifest audio map first, then a canonical project asset; None when missing."""
        rel=self.manifest.get("audio",{}).get(asset_id)
        if rel is not None:
            path=self.path(rel)
        else:
            try:
                path=Path(self.project.assets.resolve(asset_id).source.uri)
            except KeyError:
                return None
            if not path.is_absolute():path=self.resource_root/path
        return path if path.is_file() else None

    def close(self):
        audio=getattr(self,"audio",None)
        if audio is not None:audio.stop_music()
        if self.pg.get_init():
            self.pg.quit()

    def text(self, value, x, y, *, size=20, color=(245,245,250), center=False):
        f=self._fonts.get(int(size))
        if f is None:
            f=self._fonts[int(size)]=self.pg.font.Font(None,int(size))
        surf=f.render(str(value),True,color)
        rect=surf.get_rect()
        if center:
            rect.center=(int(x),int(y))
        else:
            rect.topleft=(int(x),int(y))
        self.screen.blit(surf,rect)
        return rect

    def panel(self, rect, fill=(13,17,28,220), border=(124,145,190)):
        s=self.pg.Surface((rect[2],rect[3]),self.pg.SRCALPHA)
        s.fill(fill)
        self.screen.blit(s,(rect[0],rect[1]))
        self.pg.draw.rect(self.screen,border,rect,2,border_radius=6)

    def bar(self, x,y,w,h,current,maximum, *, fill=(90,203,130), bg=(48,53,66)):
        maximum=max(float(maximum),1.0)
        ratio=max(0.0,min(1.0,float(current)/maximum))
        self.pg.draw.rect(self.screen,bg,(x,y,w,h),border_radius=4)
        self.pg.draw.rect(self.screen,fill,(x,y,int(w*ratio),h),border_radius=4)
        self.pg.draw.rect(self.screen,(220,225,235),(x,y,w,h),1,border_radius=4)

    def _field_screen_xy(self, world_x, world_y):
        scale=float(self.manifest["field"].get("world_to_screen_scale",3.0))
        return (
            self.width/2 + float(world_x)*scale,
            self.height/2 + 65 + float(world_y)*scale,
        )

    def _player_frame(self, facing, moving):
        sheet=self.load_image(self.manifest["field"]["player_sheet"])
        fw,fh=self.manifest["field"]["player_frame_size"]
        row=walking_row_index(facing)
        col=walking_pattern_index(self._field_step) if moving else 1
        return sheet.subsurface((col*fw,row*fh,fw,fh))

    def _interaction_candidate(self):
        try:
            return self.game.interaction.query.nearest(
                self.game.scene,self.game.player,self.game.facing
            )
        except Exception:
            return None

    def _draw_field(self, moving=False):
        bg=self.load_image(self.manifest["field"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg,(self.width,self.height)),(0,0))

        sprites=self.manifest["field"].get("entity_sprites",{})
        for entity in self.game.scene.entities():
            spec=sprites.get(entity.name)
            if spec is None or entity is self.game.player:continue
            et=entity.get(Transform); ex,ey=self._field_screen_xy(et.x,et.y)
            w,h=spec.get("size",(96,112))
            image=self.pg.transform.scale(self.load_image(spec["sprite"]),(int(w),int(h)))
            self.screen.blit(image,(int(ex-w/2),int(ey-h+12)))

        pt=self.game.player.get(Transform); px,py=self._field_screen_xy(pt.x,pt.y)
        pf=self._player_frame(self.game.facing,moving)
        render_w,render_h=field_player_render_size(pf.get_size(),self.manifest["field"].get("player_render_width",64))
        pf=self.pg.transform.scale(pf,(render_w,render_h))
        self.screen.blit(pf,(int(px-render_w/2),int(py-render_h+10)))

        self.panel((18,self.height-92,self.width-36,72))
        self.text("Field Test",34,self.height-82,size=24,color=(255,220,124))
        self.text("Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   Esc: Pause",
                  34,self.height-52,size=19)
        candidate=self._interaction_candidate()
        if candidate is not None and not self.game.event_busy:
            self.text(f"E  Interact — {candidate.entity.name}",self.width/2,55,size=26,
                      color=(255,226,129),center=True)
        if self.message and self.pg.time.get_ticks()<self.message_until:
            self.text(self.message,self.width/2,92,size=22,color=(175,235,255),center=True)
        self._draw_dialogue()

    def _draw_dialogue(self):
        request=self.game.pending_dialogue
        if request is None:return
        self.panel((60,self.height-230,self.width-120,130),fill=(10,14,24,235),border=(240,201,93))
        line=getattr(request,"line",None)
        if line is not None:
            if line.speaker:self.text(line.speaker,84,self.height-218,size=24,color=(255,220,124))
            self.text(line.text,84,self.height-184,size=22)
            self.text("Enter / E: continue",self.width-250,self.height-128,size=18,color=(170,210,240))
            return
        self.text(request.prompt or "Choose",84,self.height-218,size=22,color=(255,220,124))
        for i,choice in enumerate(request.choices[:9],1):
            self.text(f"{i}. {choice.text}",84+((i-1)%3)*270,self.height-184+((i-1)//3)*26,size=20)

    def _dialogue_input(self, events):
        """Route keys to a waiting dialogue/choice. Returns True when one is open."""
        request=self.game.pending_dialogue
        if request is None:return False
        if getattr(request,"line",None) is not None:
            if self.input.just_pressed("confirm") or self.input.just_pressed("interact"):
                self.game.acknowledge_dialogue()
                self._sound(self.manifest.get("dialogue_confirm_sfx"))
            return True
        for event in events:
            if event.type!=self.pg.KEYDOWN:continue
            if getattr(request,"choices",None) and self.pg.K_1<=event.key<=self.pg.K_9:
                index=event.key-self.pg.K_1
                if index<len(request.choices):
                    self.game.choose(index); break
        return True

    def _field_input(self, events, dt):
        if self._dialogue_input(events) or self.game.event_busy:
            return False
        # Project input map: keyboard and gamepad (stick / d-pad) both drive movement.
        dx,dy=self.input.current.movement_vector()
        moving=bool(dx or dy)
        if moving:
            mag=max(1.0,(dx*dx+dy*dy)**0.5)
            speed=36.0
            pt=self.game.player.get(Transform)
            blocked=CollisionWorld.from_scene(self.game.scene).blocking_query(exclude={self.game.player.id})
            nx=max(-120.0,min(120.0,pt.x+dx/mag*speed*dt))
            if not blocked.collides_world_point(nx,pt.y):pt.x=nx
            ny=max(-52.0,min(52.0,pt.y+dy/mag*speed*dt))
            if not blocked.collides_world_point(pt.x,ny):pt.y=ny
            self.game.save.player_position=(pt.x,pt.y)
            if abs(dx)>abs(dy):
                self.game.set_player_facing("right" if dx>0 else "left")
            else:
                self.game.set_player_facing("down" if dy>0 else "up")
            self._field_step+=1

        if self.input.just_pressed("menu"):
            self._ui_mode="build"
        if self.input.just_pressed("cancel"):
            self._pause_menu.index=0; self._ui_mode="pause"; return moving
        if any(e.type==self.pg.KEYDOWN and e.key==self.pg.K_q for e in events):
            self._quest_return="field"; self._ui_mode="quests"; return moving
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if self.input.just_pressed("interact"):
            self.game.field_step({"interact":1.0})
            if self.game.mode=="field":
                self.game.field_step({"interact":0.0})
        return moving


    def _draw_title(self):
        bg=self.load_image(self.manifest["field"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg,(self.width,self.height)),(0,0))
        shade=self.pg.Surface((self.width,self.height),self.pg.SRCALPHA); shade.fill((5,8,16,150)); self.screen.blit(shade,(0,0))
        self.text("ASTERIA",self.width/2,120,size=64,color=(255,220,120),center=True)
        self.text("Complex Reference RPG",self.width/2,180,size=36,center=True)
        self.panel((280,250,400,150))
        self.text("N   New Game",330,282,size=28)
        self.text("L   Load Player Save",330,330,size=28)
        save_path=self.resource_root/"saves"/"playtest_autosave.asteria-save.json"
        self.text("Save found" if save_path.exists() else "No player save yet",330,372,size=18,color=(170,210,240))

    def _load_player_save(self):
        path=self.resource_root/"saves"/"playtest_autosave.asteria-save.json"
        if not path.exists():
            self.message="No player save exists yet"; self.message_until=self.pg.time.get_ticks()+1800; return False
        loaded=GameRuntimeSave.load_json(path,self.project)
        self.save=loaded; self.game=GameSessionRuntime(self.project,loaded)
        self._victory=False; self._defeat=False; self._ui_mode="field"
        self.message="Loaded player save"; self.message_until=self.pg.time.get_ticks()+1800
        return True

    def _menu_actor_ids(self):
        return tuple(self.save.rpg_state.party_actor_ids)

    def _menu_actor(self):
        ids=self._menu_actor_ids()
        if not ids:return None
        self._menu_actor_index%=len(ids); return ids[self._menu_actor_index]

    def _current_weapon(self, actor_id):
        loadout=self.save.rpg_state.loadouts[actor_id]
        values=loadout.equipped("weapon")
        return values[0] if values else None

    def _draw_build_menu(self):
        self._draw_field(False)
        overlay=self.pg.Surface((self.width,self.height),self.pg.SRCALPHA); overlay.fill((6,9,18,210)); self.screen.blit(overlay,(0,0))
        actor_id=self._menu_actor()
        if actor_id is None:return
        db=self.project.rpg_database; state=self.save.rpg_state.actor_progression[actor_id]
        ability=self.game._ability_state(actor_id); weapon=self._current_weapon(actor_id)
        allocation=self.save.rpg_state.progression_allocations[actor_id]
        self.panel((24,22,912,496),fill=(11,15,25,242))
        self.text("Character / Build Acceptance Menu",44,38,size=30,color=(255,220,120))
        self.text(f"Q/E Actor   C Close     Current: {actor_id}",44,76,size=19)
        self.text(f"Level {state.level}   EXP {int(state.experience)}   AP {int(allocation.balance('ap'))}   Ability Pts {int(state.points.get('ability_points',0))}",44,106,size=20,color=(170,220,255))
        classes=" + ".join(state.active_class_ids) or "—"
        self.text(f"1 Secondary Class: {classes}",44,148,size=20)
        self.text(f"3 Passives: {', '.join(ability.active_passives[:4]) or '—'}",44,178,size=20)
        self.text(f"4 Weapon: {weapon.equipment.display_name if weapon else '—'}",44,208,size=20)
        growth="—" if weapon is None or weapon.growth is None else ", ".join(f"{k}:{v}" for k,v in sorted(weapon.growth.ranks.items())) or "base"
        self.text(f"5 Weapon Upgrade: {growth}",44,238,size=20)
        accessories=self.save.rpg_state.loadouts[actor_id].equipped("accessory")
        self.text(f"6 Accessories: {', '.join(x.equipment.display_name for x in accessories) or '—'}",44,268,size=20)
        active=self.save.rpg_state.party_active_actor_ids
        self.text(f"7 Party / Formation: {', '.join(active)}",44,298,size=20)
        self.text("2 Skill Tree: allocate next available node",44,328,size=20)
        graph_id=(state.active_class_ids[-1] if state.active_class_ids else next(iter(db.classes)))+"_tree"
        graph=db.progression_graphs.get(graph_id)
        if graph is not None:
            ox,oy=485,150
            self.text(graph.display_name,ox,116,size=22,color=(255,220,120))
            if graph.node_positions:
                ranks=allocation.allocations.get(graph.graph_id,{})
                for node in graph.nodes:
                    x,y=graph.node_positions.get(node.node_id,(0,0)); x=ox+x*0.55; y=oy+y*0.65
                    for req in node.prerequisites:
                        px,py=graph.node_positions.get(req.node_id,(0,0)); px=ox+px*0.55; py=oy+py*0.65
                        self.pg.draw.line(self.screen,(100,120,155),(int(px+38),int(py+12)),(int(x+38),int(y+12)),2)
                    rect=(int(x),int(y),78,25); self.pg.draw.rect(self.screen,(45,70,60) if ranks.get(node.node_id,0) else (40,46,62),rect,border_radius=4); self.pg.draw.rect(self.screen,(190,200,225),rect,1,border_radius=4)
                    self.text(node.display_name.replace(graph.display_name.split()[0],"")[:10],x+4,y+5,size=14)
            else:
                ranks=allocation.allocations.get(graph.graph_id,{})
                for i,node in enumerate(graph.nodes[:6]):
                    self.text(("[x] " if ranks.get(node.node_id,0) else "[ ] ")+node.display_name,ox,155+i*38,size=18)
        self.text("All changes are Runtime State and are verified again after Save/Load.",44,480,size=18,color=(170,210,240))

    def _cycle_secondary_class(self, actor_id):
        state=self.save.rpg_state.actor_progression[actor_id]; current=state.active_class_ids[-1] if len(state.active_class_ids)>1 else None
        choices=[x for x in state.unlocked_class_ids if x != state.active_class_ids[0]]
        if not choices:return
        idx=(-1 if current not in choices else choices.index(current)); self.game.set_secondary_class(actor_id,choices[(idx+1)%len(choices)])

    def _allocate_next_tree_node(self, actor_id):
        state=self.save.rpg_state.actor_progression[actor_id]; cls=state.active_class_ids[-1] if state.active_class_ids else None
        if not cls:return
        graph_id=f"{cls}_tree"; allocation=self.save.rpg_state.progression_allocations[actor_id]
        graph=self.project.rpg_database.progression_graphs[graph_id]
        for node in graph.nodes:
            preview=allocation.preview_allocate(graph_id,node.node_id,1)
            if preview.allowed:
                allocation.allocate(graph_id,node.node_id,1); self.message=f"Learned {node.display_name}"; self.message_until=self.pg.time.get_ticks()+1400; return
        self.message="No affordable/unlocked node"; self.message_until=self.pg.time.get_ticks()+1400

    def _cycle_passive(self, actor_id):
        ids=sorted(self.project.rpg_database.passives); state=self.game._ability_state(actor_id); current=list(state.active_passives)
        candidate=next((x for x in ids if x not in current),ids[0] if ids else None)
        if candidate is None:return
        values=(current+[candidate])[-4:]; self.game.set_passives(actor_id,values,capacity=4)

    def _cycle_weapon(self, actor_id):
        ids=sorted(k for k,v in self.project.rpg_database.equipment.items() if v.slot=="weapon")
        current=self._current_weapon(actor_id); cur=None if current is None else current.equipment.equipment_id
        idx=-1 if cur not in ids else ids.index(cur); self.game.equip_definition(actor_id,ids[(idx+1)%len(ids)],slot_id="weapon")

    def _upgrade_weapon(self, actor_id):
        item=self._current_weapon(actor_id)
        if item is None:return
        growth=item.ensure_growth(self.project.rpg_database.equipment_growth)
        for node in growth.definition.nodes:
            if growth.preview_unlock(node.node_id).allowed:
                growth.unlock(node.node_id); self.message=f"Weapon upgraded: {node.display_name}"; self.message_until=self.pg.time.get_ticks()+1400; return
        self.message="Weapon growth maxed or blocked"; self.message_until=self.pg.time.get_ticks()+1400

    def _cycle_accessory(self, actor_id):
        ids=sorted(k for k,v in self.project.rpg_database.equipment.items() if v.slot=="accessory")
        loadout=self.save.rpg_state.loadouts[actor_id]
        if loadout.equipped("accessory"): loadout.unequip("accessory",0)
        self.game.equip_definition(actor_id,ids[(self._menu_actor_index)%len(ids)],slot_id="accessory",replace=False)

    def _rotate_party(self):
        roster=list(self.save.rpg_state.party_actor_ids); active=list(self.save.rpg_state.party_active_actor_ids)
        if len(roster)<=1:return
        rotated=roster[1:]+roster[:1]; chosen=rotated[:min(6,len(rotated))]
        self.game.set_active_party(chosen,{actor_id:f"slot_{i+1}" for i,actor_id in enumerate(chosen)})

    def _build_menu_input(self, events):
        actor=self._menu_actor()
        for event in events:
            if event.type!=self.pg.KEYDOWN:continue
            if event.key==self.pg.K_c:self._ui_mode="field"
            elif event.key==self.pg.K_q:self._menu_actor_index-=1
            elif event.key==self.pg.K_e:self._menu_actor_index+=1
            elif actor is not None and event.key==self.pg.K_1:self._cycle_secondary_class(actor)
            elif actor is not None and event.key==self.pg.K_2:self._allocate_next_tree_node(actor)
            elif actor is not None and event.key==self.pg.K_3:self._cycle_passive(actor)
            elif actor is not None and event.key==self.pg.K_4:self._cycle_weapon(actor)
            elif actor is not None and event.key==self.pg.K_5:self._upgrade_weapon(actor)
            elif actor is not None and event.key==self.pg.K_6:self._cycle_accessory(actor)
            elif event.key==self.pg.K_7:self._rotate_party()

    def _member_resource(self, member_id, resource=None):
        resource=resource or self.game.rules.knockout_resource_id
        pool=self.game.battle.member(member_id).subject.resources
        if not resource or resource not in pool.to_data()["values"]:
            return None
        return pool.current(resource),pool.maximum(resource)

    def _battle_actor(self):
        return None if self.game.battle is None else self._turn_actor

    def _advance_to_hero_turn(self):
        """Let the battle scheduler run enemy turns until a hero must act."""
        hero,log=self.game.run_enemy_turns()
        if log:
            member_id,outcome=log[-1]
            name=member_id.split(":",1)[0].replace("_"," ").title()
            self._last_action_name=f"Enemy AI: {outcome}" if isinstance(outcome,Exception) else f"{name} acts"
        self._turn_actor=hero
        self._boost_level=0
        if not self.game.active_hero_ids():
            self._defeat=True

    def _skills_for_actor(self, actor_id):
        if actor_id is None:return []
        member=self.game.battle.member(actor_id)
        authored=self.manifest["battle"].get("skills",{})
        values=[]
        for ability_id in authored:
            if ability_id in member.ability_ids:
                values.append((ability_id,authored[ability_id]))
            if len(values)>=4:break
        # Ensure at least some menu entries if a custom save changed build.
        for ability_id in member.ability_ids:
            if ability_id not in {x[0] for x in values}:
                values.append((ability_id,{"label":ability_id.replace("_"," ").title()}))
            if len(values)>=4:break
        return values[:4]

    def _enemy_layout(self, member_id):
        enemy_id=str(member_id).split(":",1)[0]
        return self.manifest["battle"].get("enemy_layouts",{}).get(enemy_id)

    def _enemy_sprite(self, member_id):
        enemy_id=str(member_id).split(":",1)[0]
        rel=self.manifest["battle"]["enemy_sprites"].get(enemy_id)
        return None if rel is None else self.load_image(rel)

    def _draw_battle(self):
        self._battle_presentation.draw()

    def _present_battle(self, dt):
        """Feed new canonical battle facts to the active presentation adapter and draw."""
        self._battle_presentation.consume(self.game.drain_battle_log())
        self._battle_presentation.update(dt)
        self._battle_presentation.draw()

    def _draw_battle_world(self, show_labels=True):
        """Legacy world layer: background and combatant sprites (plus bars/names when show_labels)."""
        bg=self.load_image(self.manifest["battle"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg,(self.width,self.height)),(0,0))
        if self.game.battle is None:return

        hero_ids=list(self.game.battle.parties["heroes"].ids())
        active=set(self.game.active_hero_ids())
        for i,hid in enumerate(hero_ids[:6]):
            img=self.load_image(self.manifest["battle"]["heroes"][i % len(self.manifest["battle"]["heroes"])])
            img=self.pg.transform.smoothscale(img,(96,120))
            x=85+(i%3)*112; y=235+(i//3)*120
            if hid not in active:
                ghost=img.copy(); ghost.set_alpha(80); img=ghost
            self.screen.blit(img,(x,y))
            if not show_labels:continue
            vital=self._member_resource(hid)
            if vital is not None:self.bar(x,y+103,92,10,*vital)
            self.text(hid,x,y+116,size=15)

        enemies=list(self.game.battle.parties["enemies"].ids())
        live=set(self.game.active_enemy_ids())
        for i,eid in enumerate(enemies):
            img=self._enemy_sprite(eid)
            if img is None:continue
            layout=self._enemy_layout(eid)
            if layout is not None:
                size=tuple(layout["size"]); x,y=layout["position"]
            else:
                size=(90,90); x,y=610+(i-1)*120,315
            img=self.pg.transform.smoothscale(img,size)
            if eid not in live:
                dead=img.copy(); dead.set_alpha(50); img=dead
            self.screen.blit(img,(x,y))
            if not show_labels:continue
            vital=self._member_resource(eid)
            if vital is not None:self.bar(x,y+size[1]-8,size[0],10,*vital,fill=(215,86,105))
            self.text(eid,x,y+size[1]+5,size=16)

    def _draw_battle_hud(self):
        """Legacy HUD: action list, controls, boost and gauge text, result panels."""
        enemies=[] if self.game.battle is None else list(self.game.battle.parties["enemies"].ids())
        live=set(self.game.active_enemy_ids())
        actor=self._battle_actor()
        skills=self._skills_for_actor(actor)
        self.panel((20,22,420,155))
        self.text("Battle Test",36,34,size=28,color=(255,219,126))
        self.text(f"Current: {actor or '—'}",36,67,size=19)
        for i,(ability_id,meta) in enumerate(skills,1):
            color=(255,234,150) if i-1==self._battle_skill_index else (235,238,245)
            self.text(f"{i}. {meta.get('label',ability_id)}",36+((i-1)%2)*190,100+((i-1)//2)*32,size=20,color=color)

        self.panel((460,22,480,92))
        self.text("1–4: Skill   B: Boost   F5: Save   Esc: Quit",478,36,size=20)
        self.text(self._last_action_name or "Choose an action",478,70,size=20,color=(172,220,255))
        boost_resource=self.game.rules.boost_resource_id
        if actor and self.game.rules.boost_enabled:
            amount=self.game.battle.battle_resources.current(actor,boost_resource)
            label=boost_resource.replace("_"," ").title()
            self.text(f"{label} {int(amount)}   Boost x{self._boost_level+1}",700,70,size=18,color=(255,220,120))
        for eid in enemies:
            gauge=(self._enemy_layout(eid) or {}).get("gauge")
            if gauge is None or eid not in live:continue
            resource=gauge["resource"]
            current=self.game.battle.battle_resources.current(eid,resource)
            maximum=self.game.battle.battle_resources.definitions[resource].maximum
            self.text(f"{gauge.get('label',resource)} {int(current)}/{int(maximum)}",730,118,size=18,color=(255,205,120))

        if self._victory:
            self.panel((300,190,360,150),fill=(12,18,28,240),border=(240,201,93))
            self.text("VICTORY",480,225,size=44,color=(255,220,105),center=True)
            self.text("Rewards / EXP / AP / Ability Points applied",480,266,size=20,center=True)
            if self._victory_summary:self.text(self._victory_summary[0],480,293,size=17,center=True)
            self.text("Press Enter to return to field",480,318,size=18,center=True)
        elif self._defeat:
            self.panel((300,190,360,130),fill=(25,12,18,240),border=(220,90,110))
            self.text("PARTY DEFEATED",480,225,size=38,color=(255,140,150),center=True)
            self.text("Esc to quit / reopen save to retry",480,280,size=20,center=True)

    def _play_fx(self, ability_id, target_is_enemy=True):
        meta=self.manifest["battle"].get("skills",{}).get(ability_id)
        if not meta or "fx" not in meta:return
        sheet=self.load_image(meta["fx"])
        frame_count=int(meta.get("frames",16)); cols=4; rows=max(1,(frame_count+cols-1)//cols)
        fw=sheet.get_width()//cols; fh=sheet.get_height()//rows
        start=self.pg.time.get_ticks()
        duration=420
        while self.running:
            elapsed=self.pg.time.get_ticks()-start
            if elapsed>=duration:break
            for event in self.pg.event.get():
                if event.type==self.pg.QUIT:
                    self.running=False; return
                if event.type==self.pg.KEYDOWN and event.key==self.pg.K_ESCAPE:
                    self.running=False; return
            self._draw_battle()
            index=min(frame_count-1,int(elapsed/duration*frame_count))
            src=self.pg.Rect((index%cols)*fw,(index//cols)*fh,fw,fh)
            frame=sheet.subsurface(src)
            frame=self.pg.transform.smoothscale(frame,(160,160))
            pos=(700,170) if target_is_enemy else (180,250)
            self.screen.blit(frame,pos)
            self.pg.display.flip()
            self.clock.tick(60)

    def _use_skill(self, slot):
        actor=self._battle_actor()
        skills=self._skills_for_actor(actor)
        if actor is None or slot<0 or slot>=len(skills):return
        ability_id,meta=skills[slot]
        boost=self._boost_level
        try:
            offensive=self.game.ability_relation(ability_id).value=="opponent"
            self.game.use_ability(actor,ability_id,boost_level=boost)
            self._last_action_name=f"{actor}: {meta.get('label',ability_id)} x{boost+1}"
            self._boost_level=0
            self._sound(meta.get("sfx"))
            self._play_fx(ability_id,target_is_enemy=offensive)
        except Exception as exc:
            self._last_action_name=f"Action failed: {exc}"
            return
        self.game.end_turn()
        if not self.game.active_enemy_ids():
            try:
                self.game.finish_victory()
                self._victory_summary=[]
                rewards=self.manifest.get("progression_rewards",{})
                for hero_id in self.save.rpg_state.party_active_actor_ids:
                    info=self.game.grant_actor_experience(
                        hero_id,rewards.get("experience",1600),
                        level_threshold=rewards.get("level_threshold",1000),
                        ap_per_level=rewards.get("ap_per_level",2),
                        ability_points_per_level=rewards.get("ability_points_per_level",1),
                    )
                    self._victory_summary.append(f"{hero_id}: Lv {info['old_level']}→{info['new_level']} +{info['levels_gained']*2:g} AP +{info['levels_gained']:g} ability pts")
                self._victory=True
                self.audio.stop_music(fade_out=0.3)
                self._sound(self.manifest["battle"].get("victory_jingle"))
                self._last_action_name="Victory — rewards + progression applied"
            except Exception as exc:
                self._last_action_name=f"Victory finalize failed: {exc}"
            return
        self._advance_to_hero_turn()

    def _battle_input(self, events):
        if self._victory:
            for event in events:
                if event.type==self.pg.KEYDOWN and event.key in (self.pg.K_RETURN,self.pg.K_e,self.pg.K_SPACE):
                    self._victory=False
                    self.game.mode="field"
                    self._last_action_name=""
            return
        if self._defeat:return
        for event in events:
            if event.type!=self.pg.KEYDOWN:continue
            if event.key==self.pg.K_b:
                actor=self._battle_actor()
                if actor:
                    self._boost_level=(self._boost_level+1)%(self.game.max_boost_level(actor)+1)
            elif event.key in (self.pg.K_1,self.pg.K_KP1):self._use_skill(0)
            elif event.key in (self.pg.K_2,self.pg.K_KP2):self._use_skill(1)
            elif event.key in (self.pg.K_3,self.pg.K_KP3):self._use_skill(2)
            elif event.key in (self.pg.K_4,self.pg.K_KP4):self._use_skill(3)

    # --- pause, quests, shop and game over (UI-02) --------------------------

    def _menu_step(self, cursor):
        if self.input.just_pressed("move_up"): cursor.move(-1)
        if self.input.just_pressed("move_down"): cursor.move(1)
        return self.input.just_pressed("confirm")

    def _restart_to_title(self):
        if self.project.game_start is not None:
            self.save=self.project.game_start.instantiate(self.project)
            self.game=GameSessionRuntime(self.project,self.save)
        self._victory=False; self._defeat=False; self._shop_screen=None
        self.audio.stop_music(fade_out=0.3)
        self._ui_mode="title"

    def _pause_input(self):
        if self.input.just_pressed("cancel"):
            self._ui_mode="field"; return
        if not self._menu_step(self._pause_menu):return
        choice=self._pause_menu.selected
        if choice=="resume":self._ui_mode="field"
        elif choice=="quests":self._quest_return="pause"; self._ui_mode="quests"
        elif choice=="save":self.save_playtest()
        elif choice=="load":
            if self._load_player_save():self._ui_mode="field"
        elif choice=="title":self._restart_to_title()
        elif choice=="quit":self.running=False

    def _game_over_input(self):
        if not self._menu_step(self._game_over_menu):return
        if self._game_over_menu.selected=="load":
            self._load_player_save()
        else:
            self._restart_to_title()

    def _quests_input(self):
        if self.input.just_pressed("cancel") or self.input.just_pressed("confirm"):
            self._ui_mode=self._quest_return

    def _shop_input(self):
        screen=self._shop_screen
        if screen is None or screen.shop is None or self.input.just_pressed("cancel"):
            if screen is not None:screen.close()
            self._shop_screen=None; self._ui_mode="field"; return
        if self.input.just_pressed("move_up"):screen.move(-1)
        if self.input.just_pressed("move_down"):screen.move(1)
        if self.input.just_pressed("move_left") or self.input.just_pressed("move_right"):screen.switch_tab()
        if self.input.just_pressed("confirm") and screen.confirm() is not None:
            self._sound(self.manifest.get("dialogue_confirm_sfx"))

    def _draw_backdrop(self, base="field"):
        if base=="battle":self._draw_battle_world(show_labels=False)
        else:self._draw_field(False)
        shade=self.pg.Surface((self.width,self.height),self.pg.SRCALPHA); shade.fill((5,8,16,170)); self.screen.blit(shade,(0,0))

    def _draw_overlay_menu(self, title, cursor, base="field"):
        self._draw_backdrop(base)
        height=90+34*len(cursor.options)
        x,y=self.width/2-170,self.height/2-height/2
        self.panel((x,y,340,height))
        self.text(title,self.width/2,y+18,size=34,color=(255,220,124),center=True)
        for i,(_,label) in enumerate(cursor.options):
            selected=i==cursor.index
            self.text(("> " if selected else "   ")+label,x+40,y+70+i*34,size=24,color=(255,226,129) if selected else (235,238,245))
        if self.message and self.pg.time.get_ticks()<self.message_until:
            self.text(self.message,self.width/2,y+height+14,size=20,color=(175,235,255),center=True)

    def _draw_quests(self):
        self._draw_backdrop()
        self.panel((60,40,self.width-120,self.height-80))
        self.text("Quest Log",self.width/2,56,size=32,color=(255,220,124),center=True)
        rows=quest_rows(self.game)
        if not rows:
            self.text("No quests yet.",90,110,size=22,color=(170,210,240))
        y=104
        colors={"active":(235,238,245),"completed":(130,220,150),"failed":(230,120,120)}
        for row in rows:
            if y>self.height-110:break
            self.text(f"{row.name}  [{row.status}]",90,y,size=24,color=colors[row.status]); y+=30
            for description,value,required,done in row.objectives:
                self.text(f"{'[x]' if done else '[ ]'} {description}  {value}/{required}",120,y,size=19,color=(170,210,240)); y+=24
            y+=8
        self.text("Enter / Esc: back",self.width-260,self.height-72,size=18,color=(170,210,240))

    def _draw_shop(self):
        screen=self._shop_screen
        self._draw_backdrop()
        if screen is None or screen.shop is None:return
        self.panel((60,40,self.width-120,self.height-80))
        self.text(screen.shop.display_name,90,54,size=30,color=(255,220,124))
        for i,tab in enumerate(("buy","sell")):
            self.text(tab.title(),self.width-300+i*100,60,size=24,color=(255,226,129) if screen.tab==tab else (130,140,160))
        self.text("Item",90,104,size=19,color=(170,210,240)); self.text("Price",420,104,size=19,color=(170,210,240))
        self.text("Stock",640,104,size=19,color=(170,210,240)); self.text("Owned",740,104,size=19,color=(170,210,240))
        for i,row in enumerate(screen.rows()):
            y=134+i*30
            if y>self.height-130:break
            color=(255,226,129) if i==screen.index else (235,238,245) if row.available else (120,125,140)
            self.text(("> " if i==screen.index else "   ")+row.name,90,y,size=22,color=color)
            self.text(row.price,420,y,size=22,color=color); self.text(row.stock,640,y,size=22,color=color)
            self.text(str(row.owned),740,y,size=22,color=color)
        self.text(screen.wallet(),90,self.height-100,size=20,color=(175,235,255))
        if screen.message:self.text(screen.message,self.width/2,self.height-100,size=20,color=(255,220,124))
        self.text("Up/Down: select   Left/Right: buy/sell   Enter: confirm   Esc: leave",90,self.height-72,size=18,color=(170,210,240))

    def save_playtest(self):
        self.game.sync_world_state()
        out=self.resource_root/"saves"/"playtest_autosave.asteria-save.json"
        out.parent.mkdir(parents=True,exist_ok=True)
        self.save.save_json(out)
        self.message=f"Saved: {out.name}"
        self.message_until=self.pg.time.get_ticks()+1800
        self._last_action_name=self.message
        return out

    def run(self, target_fps=60, max_frames=None):
        self.open()
        frames=0
        try:
            while self.running:
                dt=min(self.clock.tick(int(target_fps))/1000.0,0.05)
                self._frame(self.pg.event.get(),dt)
                self.pg.display.flip()
                frames+=1
                if max_frames is not None and frames>=max_frames:break
        finally:
            self.close()
        return 0

    def _sound(self, asset_id):
        if asset_id:self.audio.play_effect(asset_id)

    def _music(self, asset_id, fade=0.5):
        if asset_id:self.audio.play_music(asset_id,fade_in=fade)

    def _frame(self, events, dt):
        """Process one frame of input, event programs and drawing (no flip)."""
        self.input_source.handle_events(events)
        self.input.update(self.input_source.raw_state())
        while self.game.presentation_requests:
            self.audio.handle_world_request(self.game.presentation_requests.pop(0))
        for cue in getattr(self._battle_presentation,"audio_cues",()):
            self._sound(dict(cue.payload).get("asset_id"))
        if hasattr(self._battle_presentation,"audio_cues"):self._battle_presentation.audio_cues.clear()
        for event in events:
            if event.type==self.pg.QUIT:
                self.running=False
            elif event.type==self.pg.KEYDOWN and event.key==self.pg.K_ESCAPE:
                if self._ui_mode=="build": self._ui_mode="field"
                elif self._ui_mode=="title": self.running=False
            elif event.type==self.pg.KEYDOWN and event.key==self.pg.K_F5 and self._ui_mode!="title":
                self.save_playtest()

        if self._ui_mode=="title":
            for event in events:
                if event.type==self.pg.KEYDOWN and event.key==self.pg.K_n:self._ui_mode="field"
                elif event.type==self.pg.KEYDOWN and event.key==self.pg.K_l:self._load_player_save()
            self._draw_title()
        elif self._ui_mode=="build":
            self._build_menu_input(events); self._draw_build_menu()
        elif self._ui_mode=="pause":
            self._pause_input(); self._draw_overlay_menu("Paused",self._pause_menu)
        elif self._ui_mode=="quests":
            self._quests_input(); self._draw_quests()
        elif self._ui_mode=="shop":
            self._shop_input(); self._draw_shop()
        elif self._ui_mode=="game_over":
            self._game_over_input(); self._draw_overlay_menu("Game Over",self._game_over_menu,base="battle")
        elif self.game.mode=="battle" or self._victory:
            self._battle_input(events)
            self._present_battle(dt)
            if self._defeat:
                self._game_over_menu.index=0; self._ui_mode="game_over"
                self.audio.stop_music(fade_out=0.5)
        elif self.game.mode=="field":
            moving=self._field_input(events,dt)
            self.game.update_events(dt)
            if self._ui_mode=="field" and self.game.open_shop_id and not self.game.event_busy:
                self._shop_screen=ShopScreen(self.game); self._ui_mode="shop"
            if self.game.mode=="field":
                self.game.check_visible_encounter()
            if self.game.mode=="battle":
                self._turn_actor=None
                self._battle_presentation.begin()
                self._music(self.manifest["battle"].get("bgm"))
                self._advance_to_hero_turn()
                self._present_battle(dt)
            else:
                self._music(self.manifest["field"].get("bgm"))
                self._draw_field(moving)


def run_playable_test_runtime(project, resource_root, *, runtime_save=None, save_path=None, width=960, height=540, target_fps=60, max_frames=None):
    resource_root=Path(resource_root)
    if runtime_save is None:
        if save_path is not None:
            runtime_save=GameRuntimeSave.load_json(save_path,project)
        else:
            raise ValueError(
                "playable test content requires Project Game Start runtime state "
                "or an explicit Player Save"
            )
    return PlayableTestRuntime(
        project,runtime_save,resource_root,width=width,height=height
    ).run(target_fps, max_frames)
