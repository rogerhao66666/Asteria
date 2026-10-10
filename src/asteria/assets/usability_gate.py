import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    asset_id: str | None = None


@dataclass
class Report:
    expected: int
    semantic: int
    reconciled: int
    registered: int
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self):
        return (
            self.expected > 0
            and self.expected == self.semantic == self.reconciled == self.registered
            and not self.issues
        )


class StarterPackUsabilityGate:
    CLIPS = {"idle", "walk", "run", "attack", "hurt", "death"}
    TYPES = {"character_animation", "monster", "vfx", "tileset", "prop", "icon", "portrait", "background"}

    def validate(self, root: Path, semantic: int, reconciled: int, registered: int):
        issues = []
        docs = []
        for p in sorted(root.rglob("*.asset.json")):
            try:
                docs.append(json.loads(p.read_text()))
            except Exception as e:
                issues.append(Issue("invalid_json", str(e)))
        n = len(docs)
        if n == 0:
            issues.append(Issue("empty_package", "No asset documents discovered"))
        if n and not n == semantic == reconciled == registered:
            issues.append(Issue("asset_count_mismatch", f"{n}/{semantic}/{reconciled}/{registered}"))
        types = set()
        clips = set()
        for d in docs:
            aid = d.get("asset_id")
            src = d.get("source")
            payload = d.get("payload") or {}
            typ = payload.get("asset_type")
            if typ:
                types.add(typ)
            if not src or not (root / src).is_file():
                issues.append(Issue("missing_source", str(src), aid))
            if typ == "character_animation":
                clips.add((payload.get("clip") or str(aid).split(".")[-1]).lower())
                for key in ("frame_size", "grid", "frame_ms"):
                    if not payload.get(key):
                        issues.append(Issue("invalid_animation_metadata", key, aid))
        missing = self.TYPES - types
        if missing:
            issues.append(Issue("missing_categories", ",".join(sorted(missing))))
        missing = self.CLIPS - clips
        if missing:
            issues.append(Issue("missing_character_clips", ",".join(sorted(missing))))
        return Report(n, semantic, reconciled, registered, issues)
