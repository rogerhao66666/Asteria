import pytest
from asteria.editor.attachment_authoring import AttachmentAuthoringModel
from asteria.presentation.attachments import Socket,Attachment,Transform2D
def T(x=0,y=0):return Transform2D(x=x,y=y)
def test_preview():
 m=AttachmentAuthoringModel();m.add_socket(Socket("hand",default=T(3,4)));m.attach(Attachment("s","sword","hand"));r=m.preview()[0];assert (r.transform.x,r.transform.y)==(3,4)
def test_key():
 m=AttachmentAuthoringModel();m.add_socket(Socket("h"));m.set_socket_key("h",2,T(20,5));assert m.rig.sample("h",2,0).x==20
def test_generic():
 m=AttachmentAuthoringModel();m.add_socket(Socket("head"));m.attach(Attachment("hat","asset.hat","head"));assert m.preview()[0].asset_id=="asset.hat"
def test_guard_attachment():
 m=AttachmentAuthoringModel();m.add_socket(Socket("x"));m.attach(Attachment("a","z","x"))
 with pytest.raises(ValueError):m.remove_socket("x")
def test_guard_child():
 m=AttachmentAuthoringModel();m.add_socket(Socket("r"));m.add_socket(Socket("c",parent="r"))
 with pytest.raises(ValueError):m.remove_socket("r")
def test_remove_key():
 m=AttachmentAuthoringModel();m.add_socket(Socket("x"));m.set_socket_key("x",1,T(2,3));assert m.remove_socket_key("x",1);assert not m.remove_socket_key("x",9)
def test_undo_redo():
 m=AttachmentAuthoringModel();m.add_socket(Socket("x"));assert m.undo() and "x" not in m.rig.sockets;assert m.redo() and "x" in m.rig.sockets
def test_undo_attach():
 m=AttachmentAuthoringModel();m.add_socket(Socket("x"));m.attach(Attachment("a","z","x"));assert m.undo() and not m.preview()
def test_edit_clears_redo():
 m=AttachmentAuthoringModel();m.add_socket(Socket("a"));m.undo();m.add_socket(Socket("b"));assert not m.redo()
def test_snapshot_hierarchy():
 m=AttachmentAuthoringModel();m.add_socket(Socket("r",default=T(10,0)));m.add_socket(Socket("h",parent="r",default=T(5,0)));m.attach(Attachment("a","z","h"));s=m.snapshot();m.detach("a");m._restore(s);assert m.preview()[0].transform.x==15
