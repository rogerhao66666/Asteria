from asteria.core import Component,Entity

class Probe(Component):
    def __init__(self):
        super().__init__(); self.events=[]
    def on_create(self): self.events.append("create")
    def on_enable(self): self.events.append("enable")
    def on_disable(self): self.events.append("disable")
    def on_detach(self): self.events.append("detach")
    def on_destroy(self): self.events.append("destroy")

def test_detach_is_reversible_but_destroy_is_terminal():
    e=Entity(); p=e.add_component(Probe())
    detached=e.detach_component(Probe)
    assert detached is p
    assert p.events==["create","enable","disable","detach"]
    e.add_component(p)
    assert p.events[-2:]==["create","enable"]
    e.remove_component(Probe)
    assert p.events[-2:]==["disable","destroy"]
