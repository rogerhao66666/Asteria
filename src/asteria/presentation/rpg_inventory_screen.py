from __future__ import annotations
from dataclasses import dataclass
from asteria.rpg.items import Inventory, ItemDefinition

@dataclass(frozen=True, slots=True)
class InventoryItemView:
    item_id: str
    label: str
    count: int
    stack_limit: int
    tags: tuple[str, ...]
    usable: bool
    selected: bool

@dataclass(frozen=True, slots=True)
class InventoryGroupView:
    group_id: str
    label: str
    item_ids: tuple[str, ...]
    visible_item_ids: tuple[str, ...]
    overflow_count: int

@dataclass(frozen=True, slots=True)
class InventoryScreenView:
    items: tuple[InventoryItemView, ...]
    groups: tuple[InventoryGroupView, ...]
    query: str
    selected_item_id: str | None
    revision: int

@dataclass(frozen=True, slots=True)
class InventoryScreenProfile:
    item_labels: tuple[tuple[str,str], ...] = ()
    item_groups: tuple[tuple[str,str], ...] = ()
    group_labels: tuple[tuple[str,str], ...] = ()
    visible_limits: tuple[tuple[str,int], ...] = ()
    default_group: str = "items"
    SCHEMA="asteria.inventory_screen_profile"
    VERSION=1

    def __init__(self, *, item_labels=None, item_groups=None, group_labels=None, visible_limits=None, default_group="items"):
        object.__setattr__(self,"item_labels",tuple(sorted((str(k),str(v)) for k,v in dict(item_labels or {}).items())))
        object.__setattr__(self,"item_groups",tuple(sorted((str(k),str(v)) for k,v in dict(item_groups or {}).items())))
        object.__setattr__(self,"group_labels",tuple(sorted((str(k),str(v)) for k,v in dict(group_labels or {}).items())))
        limits=[]
        for k,v in dict(visible_limits or {}).items():
            v=int(v)
            if v<1: raise ValueError("visible limit must be >= 1")
            limits.append((str(k),v))
        object.__setattr__(self,"visible_limits",tuple(sorted(limits)))
        object.__setattr__(self,"default_group",str(default_group))

    def item_label(self,k):
        k=str(k); return dict(self.item_labels).get(k,k)
    def group_for(self,k):
        return dict(self.item_groups).get(str(k),self.default_group)
    def group_label(self,k):
        k=str(k); return dict(self.group_labels).get(k,k)
    def visible_limit(self,k):
        return dict(self.visible_limits).get(str(k))

    def to_data(self):
        return {"schema":self.SCHEMA,"version":self.VERSION,"item_labels":dict(self.item_labels),
                "item_groups":dict(self.item_groups),"group_labels":dict(self.group_labels),
                "visible_limits":dict(self.visible_limits),"default_group":self.default_group}

    @classmethod
    def from_data(cls,data):
        if data.get("schema")!=cls.SCHEMA or data.get("version")!=cls.VERSION:
            raise ValueError("unsupported inventory screen profile")
        return cls(item_labels=data.get("item_labels",{}),item_groups=data.get("item_groups",{}),
                   group_labels=data.get("group_labels",{}),visible_limits=data.get("visible_limits",{}),
                   default_group=data.get("default_group","items"))

class InventoryScreenRuntime:
    SCHEMA="asteria.inventory_screen_runtime"
    VERSION=1
    def __init__(self,profile=None):
        self.profile=profile or InventoryScreenProfile()
        if not isinstance(self.profile,InventoryScreenProfile):
            raise TypeError("profile must be InventoryScreenProfile")
        self.query=""
        self.selected_item_id=None
        self.revision=0
        self._view=None

    @property
    def view(self): return self._view

    def project(self, inventory, item_catalog=()):
        if not isinstance(inventory,Inventory):
            raise TypeError("inventory must be Inventory")
        defs={}
        for item in item_catalog:
            if not isinstance(item,ItemDefinition):
                raise TypeError("item_catalog must contain ItemDefinition values")
            defs[item.item_id]=item
        query=self.query.casefold().strip()
        ids=tuple(dict.fromkeys(tuple(inventory.to_data()["counts"]) + tuple(defs)))
        items=[]
        for item_id in ids:
            definition=defs.get(item_id)
            count=inventory.count(item_id)
            label=self.profile.item_label(item_id)
            tags=() if definition is None else tuple(definition.tags)
            group=self.profile.group_for(item_id)
            haystack=" ".join((item_id,label,group,*tags)).casefold()
            if query and query not in haystack: continue
            items.append(InventoryItemView(
                item_id=item_id,label=label,count=count,
                stack_limit=(0 if definition is None else definition.stack_limit),
                tags=tags,
                usable=(False if definition is None else bool(definition.use_effects)),
                selected=item_id==self.selected_item_id,
            ))
        items=tuple(sorted(items,key=lambda x:(self.profile.group_for(x.item_id),x.label.casefold(),x.item_id)))
        groups=[]
        cats=[]
        for item in items:
            g=self.profile.group_for(item.item_id)
            if g not in cats: cats.append(g)
        for g in cats:
            ids=tuple(x.item_id for x in items if self.profile.group_for(x.item_id)==g)
            limit=self.profile.visible_limit(g)
            visible=ids if limit is None else ids[:limit]
            groups.append(InventoryGroupView(g,self.profile.group_label(g),ids,tuple(visible),max(0,len(ids)-len(visible))))
        valid={x.item_id for x in items}
        if self.selected_item_id not in valid:
            self.selected_item_id=items[0].item_id if items else None
        self.revision+=1
        self._view=InventoryScreenView(items,tuple(groups),self.query,self.selected_item_id,self.revision)
        return self._view

    def set_query(self,q): self.query=str(q); return self.query
    def select(self,item_id):
        if self._view is None: raise RuntimeError("inventory screen has not been projected")
        item_id=str(item_id)
        if item_id not in {x.item_id for x in self._view.items}: raise KeyError(f"unknown inventory item: {item_id}")
        self.selected_item_id=item_id; return item_id

    def snapshot(self):
        return {"schema":self.SCHEMA,"version":self.VERSION,"profile":self.profile.to_data(),
                "query":self.query,"selected_item_id":self.selected_item_id,"revision":self.revision}

    def restore(self,data):
        if data.get("schema")!=self.SCHEMA or data.get("version")!=self.VERSION:
            raise ValueError("unsupported inventory screen snapshot")
        if InventoryScreenProfile.from_data(data["profile"])!=self.profile:
            raise ValueError("inventory screen profile mismatch")
        self.query=str(data.get("query",""))
        self.selected_item_id=data.get("selected_item_id")
        self.revision=int(data["revision"])
        self._view=None
        return self
