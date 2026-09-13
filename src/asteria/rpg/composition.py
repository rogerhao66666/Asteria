from __future__ import annotations
from dataclasses import dataclass


def _id(v,label):
    v=str(v).strip()
    if not v: raise ValueError(f"{label} is required")
    return v


@dataclass(frozen=True, slots=True)
class CompositionSelection:
    step_id: str
    item_ids: tuple[str,...]

    def __init__(self, step_id, item_ids=()):
        object.__setattr__(self,"step_id",_id(step_id,"step_id"))
        object.__setattr__(self,"item_ids",tuple(_id(x,"item_id") for x in item_ids))

    def to_data(self):
        return {"step_id":self.step_id,"item_ids":list(self.item_ids)}

    @classmethod
    def from_data(cls,data):
        if set(data)!={"step_id","item_ids"}: raise ValueError("invalid composition selection")
        return cls(data["step_id"],data["item_ids"])


@dataclass(frozen=True, slots=True)
class CompositionOutput:
    item_id: str
    amount: int=1

    def __init__(self,item_id,amount=1):
        amount=int(amount)
        if amount < 1: raise ValueError("composition output amount must be >= 1")
        object.__setattr__(self,"item_id",_id(item_id,"item_id"))
        object.__setattr__(self,"amount",amount)

    def to_data(self):
        return {"item_id":self.item_id,"amount":self.amount}

    @classmethod
    def from_data(cls,data):
        if set(data)!={"item_id","amount"}: raise ValueError("invalid composition output")
        return cls(data["item_id"],data["amount"])


@dataclass(frozen=True, slots=True)
class CompositionRecipeDefinition:
    recipe_id: str
    display_name: str
    selections: tuple[CompositionSelection,...]
    outputs: tuple[CompositionOutput,...]
    tags: tuple[str,...]=()

    def __init__(self,recipe_id,display_name=None,*,selections,outputs,tags=()):
        selections=tuple(x if isinstance(x,CompositionSelection) else CompositionSelection.from_data(x) for x in selections)
        outputs=tuple(x if isinstance(x,CompositionOutput) else CompositionOutput.from_data(x) for x in outputs)
        if not selections: raise ValueError("composition recipe requires selections")
        if not outputs: raise ValueError("composition recipe requires outputs")
        ids=[x.step_id for x in selections]
        if len(ids)!=len(set(ids)): raise ValueError("composition step ids must be unique")
        object.__setattr__(self,"recipe_id",_id(recipe_id,"recipe_id"))
        object.__setattr__(self,"display_name",str(display_name or recipe_id))
        object.__setattr__(self,"selections",selections)
        object.__setattr__(self,"outputs",outputs)
        object.__setattr__(self,"tags",tuple(sorted({_id(x,"tag").lower() for x in tags})))

    def matches(self,payload):
        selected={str(k):tuple(sorted(str(x) for x in v)) for k,v in dict(payload).items()}
        required={x.step_id:tuple(sorted(x.item_ids)) for x in self.selections}
        return selected==required

    def to_data(self):
        return {
            "schema":"asteria.rpg.composition_recipe","version":1,
            "recipe_id":self.recipe_id,"display_name":self.display_name,
            "selections":[x.to_data() for x in self.selections],
            "outputs":[x.to_data() for x in self.outputs],"tags":list(self.tags),
        }

    @classmethod
    def from_data(cls,data):
        if data.get("schema")!="asteria.rpg.composition_recipe" or data.get("version")!=1:
            raise ValueError("unsupported composition recipe")
        return cls(data["recipe_id"],data["display_name"],
                   selections=[CompositionSelection.from_data(x) for x in data["selections"]],
                   outputs=[CompositionOutput.from_data(x) for x in data["outputs"]],
                   tags=data["tags"])


@dataclass(frozen=True, slots=True)
class CompositionResult:
    recipe_id: str
    consumed: tuple[tuple[str,int],...]
    produced: tuple[tuple[str,int],...]


class CompositionRuntime:
    def __init__(self,recipes=()):
        self.recipes={x.recipe_id:x for x in recipes}
        if len(self.recipes)!=len(tuple(recipes)): raise ValueError("duplicate composition recipe")

    def resolve(self,payload):
        return next((x for x in self.recipes.values() if x.matches(payload)),None)

    def craft(self,inventory,payload):
        recipe=self.resolve(payload)
        if recipe is None: raise ValueError("no matching composition recipe")
        needed={}
        for values in dict(payload).values():
            for item_id in values:
                item_id=str(item_id); needed[item_id]=needed.get(item_id,0)+1
        missing=[(k,n,inventory.count(k)) for k,n in sorted(needed.items()) if inventory.count(k)<n]
        if missing:
            raise ValueError("insufficient materials: "+", ".join(f"{k} requires {n}, owned {o}" for k,n,o in missing))
        before=inventory.to_data()
        try:
            for k,n in sorted(needed.items()):
                if not inventory.remove(k,n): raise RuntimeError("inventory changed during composition")
            for out in recipe.outputs: inventory.add(out.item_id,out.amount)
        except Exception:
            inventory.replace_from_data(before); raise
        return CompositionResult(recipe.recipe_id,tuple(sorted(needed.items())),
                                 tuple((x.item_id,x.amount) for x in recipe.outputs))
