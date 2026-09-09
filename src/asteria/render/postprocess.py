from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class PostEffect2D:
    effect_id:str
    enabled:bool=True
    parameters:tuple[tuple[str,float],...]=()
    def validate(self):
        if not self.effect_id:
            raise ValueError("effect_id required")
        names=[name for name,_ in self.parameters]
        if len(names)!=len(set(names)):
            raise ValueError("duplicate post-effect parameter")

@dataclass(frozen=True,slots=True)
class PostProcessStack:
    effects:tuple[PostEffect2D,...]=()
    def enabled_effects(self):
        for effect in self.effects:
            effect.validate()
        return tuple(effect for effect in self.effects if effect.enabled)
