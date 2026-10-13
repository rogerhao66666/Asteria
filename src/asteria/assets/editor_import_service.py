from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditorImportIssue:
    stage: str
    code: str
    message: str
    path: str = ""
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class EditorAssetImportResult:
    import_report: object
    reconciliation_report: object | None = None
    issues: tuple = ()

    @property
    def ok(self):
        return (
            self.import_report.ok
            and self.reconciliation_report is not None
            and self.reconciliation_report.ok
            and not any(x.severity == "error" for x in self.issues)
        )

    @property
    def changes(self):
        return () if self.reconciliation_report is None else self.reconciliation_report.changes

    @property
    def refresh_asset_ids(self):
        return tuple(x.asset_id for x in self.changes)

    @property
    def error_navigation(self):
        return tuple((x.stage, x.path, x.code) for x in self.issues if x.severity == "error")


class EditorAssetImportService:
    def __init__(self, importer, reconciler):
        self.importer = importer
        self.reconciler = reconciler

    def import_package(self, source_root, *, destination="", collision="error"):
        imp = self.importer.import_tree(source_root, destination=destination, collision=collision)
        issues = tuple(
            EditorImportIssue("import", x.code, x.message, x.path, x.severity) for x in imp.issues
        )
        if not imp.ok:
            return EditorAssetImportResult(imp, None, issues)
        rec = self.reconciler.reconcile(self.importer.assets_root)
        ri = tuple(
            EditorImportIssue("reconcile", x.code, x.message, x.path, x.severity)
            for x in (rec.store_report.issues if rec.store_report else ())
        )
        return EditorAssetImportResult(imp, rec, issues + ri)
