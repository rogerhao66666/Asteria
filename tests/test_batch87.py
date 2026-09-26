import pytest
from asteria.presentation.attachments import *
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.actor_attachment import ActorAnimationPose
from asteria.presentation.project_integration import *
from asteria.presentation.render_integration import RenderTransform

class Store:
 def __init__(self,d): self.d=d; self.resolved=[]
 def exists(self,k): return k in self.d
 def resolve(self,k): self.resolved.append(k); return self.d[k]
class Anim:
 def presentation_pose(self): return ActorAnimationPose("project.walk",0,.25)

def attachments(rec,store):
 rig=SocketRig();rig.add(Socket("hand"))
 rt=AttachmentRuntime(rig)
 for spec in rec.metadata.get("attachments",()): rt.attach(spec)
 return rt
def animator(rec,asset): return Anim()

def test_project_asset_scene_presentation_renderer_path():
 sword=Attachment("held","visual.sword","hand")
 store=Store({"char.hero":{"kind":"sprite"},"visual.sword":{"kind":"sprite"}})
 rec=ProjectPresentationRecord((ProjectActorRecord("hero","char.hero",transform=RenderTransform(x=7),
        metadata={"attachments":(sword,)}),))
 pipe=ProjectPresentationIntegrator(store,animator,attachments).materialize(rec)
 f=pipe.sample(0)
 assert [p.asset_id for p in f.draw_packets]==["char.hero","visual.sword"]
 assert f.draw_packets[0].transform.x==7
 assert store.resolved==["char.hero","visual.sword"]

def test_arbitrary_asset_kind_is_not_filtered_by_presentation():
 custom=Attachment("custom","project.visual.anything","hand")
 store=Store({"char":{"kind":"sprite"},"project.visual.anything":{"kind":"project-defined"}})
 rec=ProjectPresentationRecord((ProjectActorRecord("a","char",metadata={"attachments":(custom,)}),))
 assert len(ProjectPresentationIntegrator(store,animator,attachments).materialize(rec).sample(0).draw_packets)==2

def test_missing_actor_ref_fails_during_materialization():
 store=Store({})
 rec=ProjectPresentationRecord((ProjectActorRecord("a","missing"),))
 with pytest.raises(ValueError,match="unknown asset: missing"):
  ProjectPresentationIntegrator(store,animator,attachments).materialize(rec)

def test_missing_attachment_ref_fails_during_materialization():
 a=Attachment("x","missing.fx","hand"); store=Store({"char":{}})
 rec=ProjectPresentationRecord((ProjectActorRecord("a","char",metadata={"attachments":(a,)}),))
 with pytest.raises(ValueError,match="missing.fx"):
  ProjectPresentationIntegrator(store,animator,attachments).materialize(rec)

def test_asset_records_not_duplicated():
 actor_obj={"payload":object()}; fx_obj={"payload":object()}
 store=Store({"char":actor_obj,"fx":fx_obj})
 a=Attachment("x","fx","hand")
 rec=ProjectPresentationRecord((ProjectActorRecord("a","char",metadata={"attachments":(a,)}),))
 pipe=ProjectPresentationIntegrator(store,animator,attachments).materialize(rec)
 assert pipe.actors[0].actor_asset_id=="char"
 assert pipe.actors[0].attachments.instances["x"].spec.asset_id=="fx"
 assert store.d["char"] is actor_obj and store.d["fx"] is fx_obj

def test_duplicate_scene_actor_rejected():
 a=ProjectActorRecord("same","char")
 with pytest.raises(ValueError,match="duplicate actor"): ProjectPresentationRecord((a,a))

def test_no_gameplay_semantics_required():
 store=Store({"actor":{"kind":"whatever"},"hat":{"kind":"whatever"}})
 v=Attachment("cosmetic","hat","hand")
 rec=ProjectPresentationRecord((ProjectActorRecord("npc","actor",metadata={"attachments":(v,),"project_role":"merchant"}),))
 f=ProjectPresentationIntegrator(store,animator,attachments).materialize(rec).sample(3)
 assert {p.asset_id for p in f.draw_packets}=={"actor","hat"}
