from dataclasses import dataclass
from .workspace import PresentationWorkspaceModel
from .visual_authoring import PresentationVisualProjection
from .visual_editing import PresentationVisualEditor
@dataclass(frozen=True,slots=True)
class AssetIntakeRequest:
 source_uri:str;source_kind:str="auto";desired_role:str|None=None;manual_region:tuple[int,int,int,int]|None=None
@dataclass(frozen=True,slots=True)
class AssetIntakeAction:id:str;label:str;description:str
class PresentationWorkspaceController:
 MODES=("hierarchy","graph","timeline")
 def __init__(self,editor):
  self.editor=editor;self.workspace=PresentationWorkspaceModel(editor);self.visual=PresentationVisualProjection(editor);self.edit=PresentationVisualEditor(editor);self.mode="hierarchy";self.asset_intake_requests=[]
 def set_mode(self,m):
  if m not in self.MODES:raise ValueError(m)
  self.mode=m
  if m in ("hierarchy","timeline"):self.workspace.set_mode(m)
 def command_palette(self,q=""):return self.workspace.palette(q)
 def problems(self):return self.workspace.problems()
 def keyboard_action(self,a,**k):
  if a=="undo":return self.editor.undo()
  if a=="redo":return self.editor.redo()
  if a=="delete":return self.edit.delete(k.get("node_id",self.editor.selected_id))
  if a=="copy":return self.edit.copy(k.get("node_id"))
  if a=="cut":return self.edit.cut(k.get("node_id"))
  if a=="paste":return self.edit.paste(k["parent_id"],k.get("suffix","_copy"),k.get("index"),k.get("branch","children"))
  if a=="duplicate":return self.edit.duplicate(k["node_id"],k["parent_id"],k.get("index"),k.get("branch","children"),k.get("suffix","_copy"))
  raise KeyError(a)
 def drop_node(self,node_id,parent_id,index=None,branch="children"):return self.edit.reorder(node_id,parent_id,index,branch)
 def sync_preview(self,p):self.edit.sync_preview(p)
 def asset_intake_actions(self):return (AssetIntakeAction("import_any_source","Import Art…","Broad source intake."),AssetIntakeAction("review_candidates","Review Candidates…","Resolve ambiguous/detached content."),AssetIntakeAction("manual_region","Manual Region…","Explicit source selection."),AssetIntakeAction("reimport","Reimport Source…","Re-run source adapter."))
 def request_asset_intake(self,r):
  if not r.source_uri:raise ValueError("source required")
  self.asset_intake_requests.append(r);return len(self.asset_intake_requests)-1
ASSET_INTAKE_INVARIANTS=("User art need not match presets at intake.","Auto detection assists; manual override is first-class.","Ambiguous/detached content is never silently discarded.","Strict canonical assets follow broad intake/normalization.","Presentation references canonical assets; it does not redefine the asset import pipeline.")
