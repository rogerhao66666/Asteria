from __future__ import annotations

import json
from pathlib import Path

from asteria.core import Transform
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime


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
        self._title_selection=0
        self._menu_actor_index=0
        self._build_selection=0
        self._build_tab=0
        self._picker=None
        self._picker_selection=0
        self._boost_level=0
        self._victory_summary=[]
        self._title_buttons=[]
        self._build_action_rects=[]
        self._build_node_rects={}
        self._build_actor_buttons=[]
        self._build_close_rect=None
        self._build_tab_rects=[]
        self._picker_rects=[]
        self._battle_skill_rects=[]

    def path(self, rel):
        return self.resource_root/str(rel)

    def load_image(self, rel):
        rel=str(rel)
        if rel not in self._loaded:
            self._loaded[rel]=self.pg.image.load(self.path(rel)).convert_alpha()
        return self._loaded[rel]

    def open(self):
        self.pg.init()
        self.screen=self.pg.display.set_mode(
            (self.width,self.height), self.pg.RESIZABLE
        )
        self.pg.display.set_caption(self.manifest.get("title","Asteria Playable Test"))
        self.clock=self.pg.time.Clock()
        return self

    def close(self):
        if self.pg.get_init():
            self.pg.quit()

    def text(self, value, x, y, *, size=20, color=(245,245,250), center=False):
        f=self.pg.font.Font(None,int(size))
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

    @staticmethod
    def _contains(rect, position):
        x,y,w,h=rect; px,py=position
        return x<=px<x+w and y<=py<y+h

    def button(self, rect, label, *, selected=False, enabled=True, size=20):
        fill=(55,76,112) if selected else (25,32,48)
        border=(255,215,112) if selected else (105,122,154)
        color=(248,249,252) if enabled else (120,128,145)
        self.pg.draw.rect(self.screen,fill,rect,border_radius=6)
        self.pg.draw.rect(self.screen,border,rect,2,border_radius=6)
        self.text(label,rect[0]+14,rect[1]+(rect[3]-size)//2,size=size,color=color)
        return rect

    def arrow_button(self, rect, direction, *, selected=False):
        self.button(rect,"",selected=selected)
        x,y,w,h=rect; cx=x+w//2; cy=y+h//2; d=min(w,h)//5
        points={
            "left":((cx+d,cy-d),(cx-d,cy),(cx+d,cy+d)),
            "right":((cx-d,cy-d),(cx+d,cy),(cx-d,cy+d)),
            "up":((cx-d,cy+d),(cx,cy-d),(cx+d,cy+d)),
            "down":((cx-d,cy-d),(cx,cy+d),(cx+d,cy-d)),
        }[direction]
        self.pg.draw.polygon(self.screen,(245,248,255),points)
        return rect

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
        rows={"down":0,"left":1,"right":2,"up":3}
        row=rows.get(facing,0)
        col=(self._field_step//8)%3 if moving else 1
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

        boss=next((e for e in self.game.scene.entities() if e.name=="Astral Tyrant"),None)
        if boss is not None:
            bt=boss.get(Transform); bx,by=self._field_screen_xy(bt.x,bt.y)
            bs=self.load_image(self.manifest["field"]["boss_sprite"])
            bs=self.pg.transform.scale(bs,(96,112))
            self.screen.blit(bs,(int(bx-48),int(by-100)))

        pt=self.game.player.get(Transform); px,py=self._field_screen_xy(pt.x,pt.y)
        pf=self._player_frame(self.game.facing,moving)
        pf=self.pg.transform.scale(pf,(64,96))
        self.screen.blit(pf,(int(px-32),int(py-86)))

        self.panel((18,self.height-92,self.width-36,72))
        self.text("Field Test",34,self.height-82,size=24,color=(255,220,124))
        self.text("Move",34,self.height-52,size=19)
        for i,direction in enumerate(("left","up","down","right")):
            self.arrow_button((86+i*28,self.height-58,24,24),direction)
        self.text("C: Menu   E: Interact   F5: Save   Esc: Quit",210,self.height-52,size=19)
        candidate=self._interaction_candidate()
        if candidate is not None:
            self.text("E  Interact — Astral Tyrant",self.width/2,55,size=26,
                      color=(255,226,129),center=True)
        if self.message and self.pg.time.get_ticks()<self.message_until:
            self.text(self.message,self.width/2,92,size=22,color=(175,235,255),center=True)

    def _field_input(self, events, dt):
        keys=self.pg.key.get_pressed()
        dx=(1 if keys[self.pg.K_RIGHT] else 0)-(1 if keys[self.pg.K_LEFT] else 0)
        dy=(1 if keys[self.pg.K_DOWN] else 0)-(1 if keys[self.pg.K_UP] else 0)
        moving=bool(dx or dy)
        if moving:
            mag=(dx*dx+dy*dy)**0.5
            speed=36.0
            pt=self.game.player.get(Transform)
            pt.x=max(-120.0,min(120.0,pt.x+dx/mag*speed*dt))
            pt.y=max(-52.0,min(52.0,pt.y+dy/mag*speed*dt))
            self.game.save.player_position=(pt.x,pt.y)
            if abs(dx)>abs(dy):
                self.game.set_player_facing("right" if dx>0 else "left")
            else:
                self.game.set_player_facing("down" if dy>0 else "up")
            self._field_step+=1

        interact=False
        for event in events:
            if event.type==self.pg.KEYDOWN and event.key==self.pg.K_c:
                self._ui_mode="build"
            if event.type==self.pg.KEYDOWN and event.key in (self.pg.K_e,self.pg.K_RETURN,self.pg.K_SPACE):
                interact=True
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if interact:
            trigger=self.game.field_step({"interact":1.0})
            self.game.field_step({"interact":0.0})
            if trigger is not None:
                self.message="Encounter started"
                self.message_until=self.pg.time.get_ticks()+1000
        return moving


    def _draw_title(self):
        bg=self.load_image(self.manifest["field"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg,(self.width,self.height)),(0,0))
        shade=self.pg.Surface((self.width,self.height),self.pg.SRCALPHA); shade.fill((5,8,16,150)); self.screen.blit(shade,(0,0))
        self.text("ASTERIA",self.width/2,120,size=64,color=(255,220,120),center=True)
        self.text("Complex Reference RPG",self.width/2,180,size=36,center=True)
        menu_w=min(440,self.width-48); menu_x=(self.width-menu_w)//2
        self.panel((menu_x,245,menu_w,190))
        self.arrow_button((menu_x+92,258,28,28),"up")
        self.arrow_button((menu_x+124,258,28,28),"down")
        self.text("Choose, then Enter or click",menu_x+166,264,size=18,color=(180,205,235))
        self._title_buttons=[
            (menu_x+24,295,menu_w-48,48),
            (menu_x+24,351,menu_w-48,48),
        ]
        self.button(self._title_buttons[0],"New Game",selected=self._title_selection==0,size=24)
        save_path=self.resource_root/"saves"/"playtest_autosave.asteria-save.json"
        self.button(self._title_buttons[1],"Load Game",selected=self._title_selection==1,enabled=save_path.exists(),size=24)
        self.text("Save found" if save_path.exists() else "No player save yet",self.width/2,416,size=17,color=(170,210,240),center=True)

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

    def _actor_name(self, actor_id):
        actor=self.project.rpg_database.actors.get(actor_id)
        return getattr(actor,"display_name",None) or str(actor_id).replace("_"," ").title()

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
        margin=24; panel_w=self.width-margin*2; panel_h=self.height-margin*2
        self.panel((margin,margin,panel_w,panel_h),fill=(11,15,25,246))
        self.text("Character Build",margin+20,margin+14,size=30,color=(255,220,120))
        self.text("Mouse click or arrows + Enter",margin+245,margin+22,size=16,color=(170,210,240))
        close_w=92
        self._build_close_rect=(self.width-margin-close_w-14,margin+12,close_w,36)
        self.button(self._build_close_rect,"Close",size=18)

        actor_y=margin+58; arrow_w=48; actor_w=min(330,panel_w//2-70)
        actor_x=margin+20
        self._build_actor_buttons=[
            (actor_x,actor_y,arrow_w,42),
            (actor_x+arrow_w+actor_w,actor_y,arrow_w,42),
        ]
        self.arrow_button(self._build_actor_buttons[0],"left")
        self.arrow_button(self._build_actor_buttons[1],"right")
        self.button((actor_x+arrow_w,actor_y,actor_w,42),self._actor_name(actor_id),selected=True,size=20)
        self.text(f"Level {state.level}   EXP {int(state.experience)}   AP {int(allocation.balance('ap'))}   Ability Points {int(state.points.get('ability_points',0))}",margin+20,margin+108,size=19,color=(170,220,255))

        tab_y=margin+140; tab_w=(panel_w-40)//3
        self._build_tab_rects=[]
        for i,label in enumerate(("Character","Skills","Equipment")):
            rect=(margin+20+i*tab_w,tab_y,tab_w-6,40); self._build_tab_rects.append(rect)
            self.button(rect,label,selected=i==self._build_tab,size=19)
        content_y=tab_y+54; self._build_action_rects=[]; self._build_node_rects={}
        if self._build_tab==0:
            primary=state.active_class_ids[0] if state.active_class_ids else None
            secondary=state.active_class_ids[1] if len(state.active_class_ids)>1 else None
            rows=[
                ("Main Class",db.classes[primary].display_name if primary else "None"),
                ("Secondary Class",db.classes[secondary].display_name if secondary else "None — click to choose"),
                ("Party / Formation",f"{len(self.save.rpg_state.party_active_actor_ids)} active members — click to rotate"),
            ]
            for i,(label,value) in enumerate(rows):
                rect=(margin+28,content_y+i*62,panel_w-56,50); self._build_action_rects.append(rect)
                self.button(rect,label,selected=i==self._build_selection,size=19)
                self.text(value,rect[0]+230,rect[1]+15,size=18,color=(174,202,232))
        elif self._build_tab==1:
            cls=state.active_class_ids[-1] if state.active_class_ids else None
            graph=db.progression_graphs.get(f"{cls}_tree") if cls else None
            left_w=(panel_w-74)//2
            self.text("Skill Tree",margin+28,content_y,size=22,color=(255,220,120))
            if graph:
                ranks=allocation.allocations.get(graph.graph_id,{})
                for i,node in enumerate(graph.nodes):
                    rect=(margin+28,content_y+34+i*43,left_w,36); self._build_node_rects[node.node_id]=rect
                    learned=bool(ranks.get(node.node_id,0))
                    prefix="Learned" if learned else "Learn"
                    self.button(rect,f"{prefix}: {node.display_name}",selected=learned,size=16)
            px=margin+44+left_w
            self.text("Passives (choose up to 4)",px,content_y,size=22,color=(255,220,120))
            passive_ids=sorted(db.passives)
            for i,pid in enumerate(passive_ids):
                col=i//8; row=i%8; rect=(px+col*(left_w//2+4),content_y+34+row*32,left_w//2,27)
                self._build_action_rects.append(rect)
                active=pid in ability.active_passives
                self.button(rect,("Equipped: " if active else "Equip: ")+db.passives[pid].display_name,selected=active,size=14)
        else:
            loadout=self.save.rpg_state.loadouts[actor_id]
            accessories=loadout.equipped("accessory")
            armor=loadout.equipped("armor")
            rows=[
                ("Weapon",weapon.equipment.display_name if weapon else "None"),
                ("Armor",armor[0].equipment.display_name if armor else "None"),
                ("Accessory 1",accessories[0].equipment.display_name if len(accessories)>0 else "None"),
                ("Accessory 2",accessories[1].equipment.display_name if len(accessories)>1 else "None"),
            ]
            for i,(label,value) in enumerate(rows):
                rect=(margin+28,content_y+i*54,int(panel_w*.52),44); self._build_action_rects.append(rect)
                self.button(rect,label,selected=i==self._build_selection,size=18)
                self.text(value,rect[0]+190,rect[1]+13,size=16,color=(174,202,232))
            gx=margin+int(panel_w*.57); self.text("Weapon Upgrades",gx,content_y,size=22,color=(255,220,120))
            if weapon and weapon.growth:
                for i,node in enumerate(weapon.growth.definition.nodes):
                    rect=(gx,content_y+36+i*48,int(panel_w*.38),38); self._build_node_rects[node.node_id]=rect
                    rank=weapon.growth.ranks.get(node.node_id,0)
                    self.button(rect,("Upgraded: " if rank else "Upgrade: ")+node.display_name,selected=bool(rank),size=16)
            else:self.text("Equip a weapon to view upgrades",gx,content_y+42,size=17,color=(174,202,232))
        if self._picker:self._draw_picker()

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

    def _allocate_tree_node(self, actor_id, node_id):
        state=self.save.rpg_state.actor_progression[actor_id]
        cls=state.active_class_ids[-1] if state.active_class_ids else None
        if not cls:return
        graph_id=f"{cls}_tree"; allocation=self.save.rpg_state.progression_allocations[actor_id]
        graph=self.project.rpg_database.progression_graphs[graph_id]
        node=graph.node(node_id)
        preview=allocation.preview_allocate(graph_id,node_id,1)
        if preview.allowed:
            allocation.allocate(graph_id,node_id,1)
            self.message=f"Learned {node.display_name}"
        else:
            self.message="This skill is already learned, locked, or needs more AP"
        self.message_until=self.pg.time.get_ticks()+1600

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

    def _open_picker(self, kind, actor_id, slot_index=0):
        db=self.project.rpg_database
        if kind=="secondary":
            state=self.save.rpg_state.actor_progression[actor_id]
            options=[(None,"No Secondary Class")]+[(cid,db.classes[cid].display_name) for cid in state.unlocked_class_ids if cid!=state.active_class_ids[0]]
        else:
            options=[(None,f"Unequip {kind.title()}")]+[(eid,item.display_name) for eid,item in sorted(db.equipment.items()) if item.slot==kind]
        self._picker={"kind":kind,"actor":actor_id,"slot_index":slot_index,"options":options}
        self._picker_selection=0

    def _draw_picker(self):
        options=self._picker["options"]; cols=2 if len(options)>8 else 1; rows=(len(options)+cols-1)//cols
        w=min(760,self.width-80); h=min(self.height-80,110+rows*42); x=(self.width-w)//2; y=(self.height-h)//2
        self.panel((x,y,w,h),fill=(10,14,24,252),border=(255,215,112))
        self.text("Choose an option",x+22,y+18,size=25,color=(255,220,120))
        self._picker_rects=[]; cell_w=(w-52)//cols
        for i,(_,label) in enumerate(options):
            col=i//rows; row=i%rows; rect=(x+20+col*(cell_w+10),y+58+row*42,cell_w,34)
            self._picker_rects.append(rect); self.button(rect,label,selected=i==self._picker_selection,size=16)

    def _apply_picker(self):
        data=self._picker; value,_=data["options"][self._picker_selection]; actor=data["actor"]; kind=data["kind"]
        if kind=="secondary":
            state=self.save.rpg_state.actor_progression[actor]
            if value is None:self.game.set_active_classes(actor,state.active_class_ids[:1])
            else:self.game.set_secondary_class(actor,value)
        else:
            loadout=self.save.rpg_state.loadouts[actor]; index=data["slot_index"]
            equipped=loadout.equipped(kind)
            if index<len(equipped):loadout.unequip(kind,index)
            if value is not None:self.game.equip_definition(actor,value,slot_id=kind,replace=False)
        self._picker=None

    def _toggle_passive(self, actor, passive_id):
        values=list(self.game._ability_state(actor).active_passives)
        if passive_id in values:values.remove(passive_id)
        elif len(values)<4:values.append(passive_id)
        else:
            self.message="Four passives are already equipped"; self.message_until=self.pg.time.get_ticks()+1600; return
        self.game.set_passives(actor,values,capacity=4)

    def _activate_build_action(self, actor, index):
        if self._build_tab==0:
            if index==1:self._open_picker("secondary",actor)
            elif index==2:self._rotate_party()
        elif self._build_tab==1:
            passive_ids=sorted(self.project.rpg_database.passives)
            if index<len(passive_ids):self._toggle_passive(actor,passive_ids[index])
        else:
            if index==0:self._open_picker("weapon",actor)
            elif index==1:self._open_picker("armor",actor)
            elif index in (2,3):self._open_picker("accessory",actor,index-2)

    def _build_menu_input(self, events):
        actor=self._menu_actor()
        for event in events:
            if self._picker:
                if event.type==self.pg.KEYDOWN:
                    if event.key==self.pg.K_ESCAPE:self._picker=None
                    elif event.key in (self.pg.K_UP,self.pg.K_LEFT):self._picker_selection=(self._picker_selection-1)%len(self._picker["options"])
                    elif event.key in (self.pg.K_DOWN,self.pg.K_RIGHT):self._picker_selection=(self._picker_selection+1)%len(self._picker["options"])
                    elif event.key in (self.pg.K_RETURN,self.pg.K_SPACE):self._apply_picker()
                elif event.type==self.pg.MOUSEBUTTONDOWN and event.button==1:
                    for index,rect in enumerate(self._picker_rects):
                        if self._contains(rect,event.pos):self._picker_selection=index; self._apply_picker(); break
                continue
            if event.type==self.pg.KEYDOWN:
                if event.key==self.pg.K_c:self._ui_mode="field"
                elif event.key==self.pg.K_LEFT:self._build_tab=(self._build_tab-1)%3; self._build_selection=0
                elif event.key==self.pg.K_RIGHT:self._build_tab=(self._build_tab+1)%3; self._build_selection=0
                elif event.key==self.pg.K_UP:self._build_selection=max(0,self._build_selection-1)
                elif event.key==self.pg.K_DOWN:self._build_selection+=1
                elif actor is not None and event.key in (self.pg.K_RETURN,self.pg.K_SPACE):
                    self._activate_build_action(actor,self._build_selection)
            elif event.type==self.pg.MOUSEBUTTONDOWN and event.button==1:
                pos=event.pos
                if self._build_close_rect and self._contains(self._build_close_rect,pos):
                    self._ui_mode="field"; continue
                if self._build_actor_buttons and self._contains(self._build_actor_buttons[0],pos):
                    self._menu_actor_index-=1; continue
                if self._build_actor_buttons and self._contains(self._build_actor_buttons[1],pos):
                    self._menu_actor_index+=1; continue
                for index,rect in enumerate(self._build_tab_rects):
                    if self._contains(rect,pos):self._build_tab=index; self._build_selection=0; break
                for index,rect in enumerate(self._build_action_rects):
                    if self._contains(rect,pos):
                        self._build_selection=index
                        if actor is not None:self._activate_build_action(actor,index)
                        break
                for node_id,rect in self._build_node_rects.items():
                    if actor is not None and self._contains(rect,pos):
                        if self._build_tab==1:self._allocate_tree_node(actor,node_id)
                        elif self._build_tab==2:self._upgrade_weapon(actor)
                        break

    def _member_resource(self, member_id, resource="vitality"):
        member=self.game.battle.member(member_id)
        pool=member.subject.resources
        return pool.current(resource),pool.maximum(resource)

    def _battle_actor(self):
        ids=self.game.active_hero_ids()
        return ids[0] if ids else None

    def _skills_for_actor(self, actor_id):
        if actor_id is None:return []
        member=self.game.battle.member(actor_id)
        authored=self.manifest["battle"].get("skills",{})
        values=[]
        for ability_id in ("strike","fire_arc","heal","meteor"):
            if ability_id in member.ability_ids and ability_id in authored:
                values.append((ability_id,authored[ability_id]))
        # Ensure at least some menu entries if a custom save changed build.
        for ability_id in member.ability_ids:
            if ability_id not in {x[0] for x in values}:
                values.append((ability_id,{"label":ability_id.replace("_"," ").title()}))
            if len(values)>=4:break
        return values[:4]

    def _enemy_sprite(self, member_id):
        enemy_id=str(member_id).split(":",1)[0]
        rel=self.manifest["battle"]["enemy_sprites"].get(enemy_id)
        return None if rel is None else self.load_image(rel)

    def _draw_battle(self):
        bg=self.load_image(self.manifest["battle"]["background"])
        self.screen.blit(self.pg.transform.smoothscale(bg,(self.width,self.height)),(0,0))

        hero_ids=list(self.game.battle.parties["heroes"].ids())
        active=set(self.game.active_hero_ids())
        for i,hid in enumerate(hero_ids[:6]):
            img=self.load_image(self.manifest["battle"]["heroes"][i % len(self.manifest["battle"]["heroes"])])
            img=self.pg.transform.smoothscale(img,(96,120))
            x=85+(i%3)*112; y=235+(i//3)*120
            if hid not in active:
                ghost=img.copy(); ghost.set_alpha(80); img=ghost
            self.screen.blit(img,(x,y))
            cur,mx=self._member_resource(hid)
            self.bar(x,y+103,92,10,cur,mx)
            self.text(hid,x,y+116,size=15)

        enemies=list(self.game.battle.parties["enemies"].ids())
        live=set(self.game.active_enemy_ids())
        for i,eid in enumerate(enemies):
            img=self._enemy_sprite(eid)
            if img is None:continue
            if eid.startswith("astral_tyrant"):
                size=(220,220); x,y=650,100
            else:
                size=(90,90); x,y=610+(i-1)*120,315
            img=self.pg.transform.smoothscale(img,size)
            if eid not in live:
                dead=img.copy(); dead.set_alpha(50); img=dead
            self.screen.blit(img,(x,y))
            cur,mx=self._member_resource(eid)
            self.bar(x,y+size[1]-8,size[0],10,cur,mx,fill=(215,86,105))
            self.text(eid,x,y+size[1]+5,size=16)

        actor=self._battle_actor()
        skills=self._skills_for_actor(actor)
        self.panel((20,22,420,178))
        self.text("Battle",36,34,size=28,color=(255,219,126))
        self.text(f"Current: {self._actor_name(actor) if actor else '—'}",36,67,size=19)
        self._battle_skill_rects=[]
        for i,(ability_id,meta) in enumerate(skills):
            rect=(34+(i%2)*196,96+(i//2)*48,186,40)
            self._battle_skill_rects.append(rect)
            self.button(rect,meta.get('label',ability_id),selected=i==self._battle_skill_index,size=18)

        self.panel((460,22,480,92))
        self.text("Select",478,36,size=18)
        for i,direction in enumerate(("left","up","down","right")):
            self.arrow_button((535+i*27,31,23,23),direction)
        self.text("Enter / Click: Use",650,36,size=18)
        self.text("B: Boost   F5: Save   Esc: Quit",478,62,size=18)
        self.text(self._last_action_name or "Choose an action",478,88,size=18,color=(172,220,255))
        if actor:
            momentum=self.game.battle.battle_resources.current(actor,"momentum")
            self.text(f"Momentum {int(momentum)}   Boost x{self._boost_level+1}",700,88,size=17,color=(255,220,120))
        boss=next((x for x in enemies if x.startswith("astral_tyrant")),None)
        if boss:
            stagger=self.game.battle.battle_resources.current(boss,"stagger")
            self.text(f"Shield {int(stagger)}/8",730,118,size=18,color=(255,205,120))

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

    def _enemy_response(self):
        if not self.game.active_enemy_ids() or not self.game.active_hero_ids():
            return
        target=self.game.active_hero_ids()[0]
        for enemy_member_id in tuple(self.game.active_enemy_ids()):
            enemy_id=enemy_member_id.split(":",1)[0]
            binding=self.project.rpg_database.enemy_behavior_bindings.get(enemy_id)
            if binding is not None:
                try:
                    self.game.enemy_turn(enemy_member_id,binding.ai_id)
                    self._last_action_name=f"{enemy_id.replace('_',' ').title()} acts"
                except Exception as exc:
                    self._last_action_name=f"Enemy AI: {exc}"
            else:
                definition=self.project.rpg_database.enemies[enemy_id]
                if definition.abilities:
                    ability_id=definition.abilities[0]
                    try:
                        self.game.execute(enemy_member_id,ability_id,(target,))
                        self._last_action_name=f"{enemy_id.replace('_',' ').title()}: {ability_id}"
                    except Exception:
                        pass
            if not self.game.active_hero_ids():
                self._defeat=True
                return

    def _use_skill(self, slot):
        actor=self._battle_actor()
        skills=self._skills_for_actor(actor)
        if actor is None or slot<0 or slot>=len(skills):return
        ability_id,meta=skills[slot]
        target_enemy=ability_id not in {"heal","revive","party_barrier","haste_song","guard","focus_charge","counter_stance"}
        targets=(self.game.active_enemy_ids()[0],) if target_enemy else (actor,)
        if not targets:return
        try:
            repeat=self._boost_level+1
            if self._boost_level:
                self.game.battle.battle_resources.spend(actor,"momentum",self._boost_level,trigger="reference.boost")
            for _ in range(repeat):
                if not targets or (target_enemy and targets[0] not in self.game.active_enemy_ids()): break
                result=self.game.execute(actor,ability_id,targets)
                if target_enemy:
                    outcome=self.game.battle.resolve_interaction(result.action,targets[0],1.0)
                    self.game.battle.apply_gauge_impact("stagger_system",actor,targets[0],trigger="battle.hit",outcome=outcome)
            self._last_action_name=f"{actor}: {meta.get('label',ability_id)} x{repeat}"
            self._boost_level=0
            self._play_fx(ability_id,target_is_enemy=target_enemy)
        except Exception as exc:
            self._last_action_name=f"Action failed: {exc}"
            return
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
                    self._victory_summary.append(f"{hero_id}: Lv {info['old_level']} to {info['new_level']} +{info['levels_gained']*2:g} AP +{info['levels_gained']:g} ability pts")
                self._victory=True
                self._last_action_name="Victory — rewards + progression applied"
            except Exception as exc:
                self._last_action_name=f"Victory finalize failed: {exc}"
            return
        self._enemy_response()

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
            if event.type==self.pg.KEYDOWN:
                if event.key==self.pg.K_b:
                    actor=self._battle_actor()
                    if actor:
                        available=int(self.game.battle.battle_resources.current(actor,"momentum"))
                        self._boost_level=(self._boost_level+1)%max(1,min(3,available)+1)
                elif event.key==self.pg.K_LEFT:self._battle_skill_index=(self._battle_skill_index-1)%max(1,len(self._skills_for_actor(self._battle_actor())))
                elif event.key==self.pg.K_RIGHT:self._battle_skill_index=(self._battle_skill_index+1)%max(1,len(self._skills_for_actor(self._battle_actor())))
                elif event.key==self.pg.K_UP:self._battle_skill_index=(self._battle_skill_index-2)%max(1,len(self._skills_for_actor(self._battle_actor())))
                elif event.key==self.pg.K_DOWN:self._battle_skill_index=(self._battle_skill_index+2)%max(1,len(self._skills_for_actor(self._battle_actor())))
                elif event.key in (self.pg.K_RETURN,self.pg.K_SPACE):self._use_skill(self._battle_skill_index)
            elif event.type==self.pg.MOUSEBUTTONDOWN and event.button==1:
                for index,rect in enumerate(self._battle_skill_rects):
                    if self._contains(rect,event.pos):
                        self._battle_skill_index=index; self._use_skill(index); break

    def save_playtest(self):
        self.game.sync_world_state()
        out=self.resource_root/"saves"/"playtest_autosave.asteria-save.json"
        out.parent.mkdir(parents=True,exist_ok=True)
        self.save.save_json(out)
        self.message=f"Saved: {out.name}"
        self.message_until=self.pg.time.get_ticks()+1800
        self._last_action_name=self.message
        return out

    def run(self, target_fps=60):
        self.open()
        try:
            while self.running:
                dt=min(self.clock.tick(int(target_fps))/1000.0,0.05)
                events=self.pg.event.get()
                for event in events:
                    if event.type==self.pg.QUIT:
                        self.running=False
                    elif event.type==self.pg.VIDEORESIZE:
                        # Keep the logical canvas in sync with the native
                        # window so HUD anchors and field rendering remain
                        # usable after a real desktop resize.
                        self.width=max(320,int(event.w))
                        self.height=max(180,int(event.h))
                        self.screen=self.pg.display.set_mode(
                            (self.width,self.height), self.pg.RESIZABLE
                        )
                    elif event.type==self.pg.KEYDOWN and event.key==self.pg.K_ESCAPE:
                        if self._ui_mode=="build": self._ui_mode="field"
                        else: self.running=False
                    elif event.type==self.pg.KEYDOWN and event.key==self.pg.K_F5 and self._ui_mode!="title":
                        self.save_playtest()

                if self._ui_mode=="title":
                    for event in events:
                        if event.type==self.pg.KEYDOWN:
                            if event.key in (self.pg.K_UP,self.pg.K_DOWN):self._title_selection=1-self._title_selection
                            elif event.key in (self.pg.K_RETURN,self.pg.K_SPACE):
                                if self._title_selection==0:self._ui_mode="field"
                                else:self._load_player_save()
                            elif event.key==self.pg.K_n:self._ui_mode="field"
                            elif event.key==self.pg.K_l:self._load_player_save()
                        elif event.type==self.pg.MOUSEBUTTONDOWN and event.button==1:
                            for index,rect in enumerate(self._title_buttons):
                                if self._contains(rect,event.pos):
                                    self._title_selection=index
                                    if index==0:self._ui_mode="field"
                                    else:self._load_player_save()
                                    break
                    self._draw_title()
                elif self._ui_mode=="build":
                    self._build_menu_input(events); self._draw_build_menu()
                elif self.game.mode=="field":
                    moving=self._field_input(events,dt)
                    self._draw_field(moving)
                elif self.game.mode=="battle":
                    self._battle_input(events)
                    self._draw_battle()
                self.pg.display.flip()
        finally:
            self.close()
        return 0


def run_playable_test_runtime(project, resource_root, *, runtime_save=None, save_path=None, width=960, height=540, target_fps=60):
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
    ).run(target_fps)
