from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class QualityEvidence:
    technical: GateStatus
    art: GateStatus
    motion: GateStatus
    in_scene: GateStatus
    notes: tuple[str, ...] = ()

    @property
    def final_pass(self) -> bool:
        return all(x is GateStatus.PASS for x in (self.technical, self.art, self.motion, self.in_scene))


@dataclass(frozen=True)
class QualityIssue:
    asset_id: str
    gate: str
    status: GateStatus
    message: str


@dataclass
class PackQualityReport:
    assets_checked: int = 0
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.assets_checked > 0 and not self.issues


def evidence_from_dict(d: dict) -> QualityEvidence:
    return QualityEvidence(
        technical=GateStatus(d.get("technical", "review_required")),
        art=GateStatus(d.get("art", "review_required")),
        motion=GateStatus(d.get("motion", "review_required")),
        in_scene=GateStatus(d.get("in_scene", "review_required")),
        notes=tuple(d.get("notes", ())),
    )


class PackQualityGate:
    """Requires explicit four-gate evidence for every runtime asset.

    Static assets may mark motion PASS with a note explaining that the asset is
    intentionally static; absence of evidence is never interpreted as PASS.
    """

    KEYS = ("technical", "art", "motion", "in_scene")

    def validate(self, package_root: Path) -> PackQualityReport:
        report = PackQualityReport()
        for p in sorted(package_root.rglob("*.asset.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            aid = str(doc.get("asset_id", "<missing>"))
            report.assets_checked += 1
            q = (doc.get("payload") or {}).get("quality")
            if not isinstance(q, dict):
                for key in self.KEYS:
                    report.issues.append(QualityIssue(aid, key, GateStatus.REVIEW_REQUIRED, "quality evidence missing"))
                continue
            ev = evidence_from_dict(q)
            for key, status in (
                ("technical", ev.technical),
                ("art", ev.art),
                ("motion", ev.motion),
                ("in_scene", ev.in_scene),
            ):
                if status is not GateStatus.PASS:
                    report.issues.append(QualityIssue(aid, key, status, f"{key} gate is {status.value}"))
        return report
