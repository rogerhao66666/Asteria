from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnimationClipSet:
    clips: dict[str, object]

    def validate(self, sprite_sheet):
        if not self.clips:
            raise ValueError("animation clip set requires clips")
        for name, clip in self.clips.items():
            if not name or clip.name != name:
                raise ValueError("clip key/name mismatch")
            clip.validate(sprite_sheet)

    def get(self, name):
        return self.clips.get(name)
