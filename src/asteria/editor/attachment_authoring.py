from dataclasses import dataclass
from asteria.presentation.attachments import Socket,SocketKey,SocketRig,Attachment
from asteria.presentation.attachment_runtime import AttachmentRuntime

@dataclass(frozen=True,slots=True)
class AuthoringSnapshot:
    sockets: tuple
    attachments: tuple

class AttachmentAuthoringModel:
    def __init__(self):
        self.rig=SocketRig(); self.runtime=AttachmentRuntime(self.rig); self._undo=[]; self._redo=[]
    def snapshot(self): return AuthoringSnapshot(tuple(self.rig.sockets.values()),tuple(tuple(i.spec for i in self.runtime.instances.values() if i.state.value != 'detached')))
    def _checkpoint(self): self._undo.append(self.snapshot()); self._redo.clear()
    def _restore(self,s):
        rig=SocketRig(); pending=list(s.sockets)
        while pending:
            progress=False
            for x in pending[:]:
                if x.parent is None or x.parent in rig.sockets:
                    rig.add(x); pending.remove(x); progress=True
            if not progress: raise ValueError("invalid hierarchy")
        rt=AttachmentRuntime(rig)
        for a in s.attachments: rt.attach(a)
        self.rig,self.runtime=rig,rt
    def undo(self):
        if not self._undo:return False
        cur=self.snapshot(); snap=self._undo.pop(); self._redo.append(cur); self._restore(snap); return True
    def redo(self):
        if not self._redo:return False
        cur=self.snapshot(); snap=self._redo.pop(); self._undo.append(cur); self._restore(snap); return True
    def add_socket(self,s): self._checkpoint(); self.rig.add(s)
    def remove_socket(self,i):
        if any(x.parent==i for x in self.rig.sockets.values()): raise ValueError("socket has children")
        if any(a.socket_id==i for a in tuple(i.spec for i in self.runtime.instances.values() if i.state.value != 'detached')): raise ValueError("socket has attachments")
        self._checkpoint(); del self.rig.sockets[i]
    def set_socket_key(self,i,frame,transform):
        old=self.rig.sockets[i]; self._checkpoint(); keys={k.frame:k for k in old.keys}; keys[frame]=SocketKey(frame,transform)
        self.rig.sockets[i]=Socket(id=old.id,parent=old.parent,pivot_x=old.pivot_x,pivot_y=old.pivot_y,default=old.default,keys=tuple(keys[k] for k in sorted(keys)),metadata=dict(old.metadata))
    def remove_socket_key(self,i,frame):
        old=self.rig.sockets[i]; keys=tuple(k for k in old.keys if k.frame!=frame)
        if keys==old.keys:return False
        self._checkpoint(); self.rig.sockets[i]=Socket(id=old.id,parent=old.parent,pivot_x=old.pivot_x,pivot_y=old.pivot_y,default=old.default,keys=keys,metadata=dict(old.metadata)); return True
    def attach(self,a): self._checkpoint(); self.runtime.attach(a)
    def detach(self,i):
        if i not in self.runtime.instances or self.runtime.instances[i].state.value == 'detached':return False
        self._checkpoint(); self.runtime.detach(i); return True
    def preview(self,frame=0,subframe=0.): return self.runtime.resolve_all(frame,subframe)
