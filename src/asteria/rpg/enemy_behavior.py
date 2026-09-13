from __future__ import annotations
from dataclasses import dataclass

def _id(v,label):
    v=str(v).strip()
    if not v: raise ValueError(f"{label} is required")
    return v

@dataclass(frozen=True, slots=True)
class EnemyBehaviorBinding:
    enemy_id: str
    ai_id: str
    tags: tuple[str,...]=()

    def __init__(self,enemy_id,ai_id,*,tags=()):
        object.__setattr__(self,"enemy_id",_id(enemy_id,"enemy_id"))
        object.__setattr__(self,"ai_id",_id(ai_id,"ai_id"))
        object.__setattr__(self,"tags",tuple(sorted({_id(x,"tag").lower() for x in tags})))

    def to_data(self):
        return {"schema":"asteria.rpg.enemy_behavior_binding","version":1,
                "enemy_id":self.enemy_id,"ai_id":self.ai_id,"tags":list(self.tags)}

    @classmethod
    def from_data(cls,data):
        if data.get("schema")!="asteria.rpg.enemy_behavior_binding" or data.get("version")!=1:
            raise ValueError("unsupported enemy behavior binding")
        return cls(data["enemy_id"],data["ai_id"],tags=data["tags"])
