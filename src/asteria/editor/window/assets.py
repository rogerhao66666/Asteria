"""The Assets panel: its list, the selected pictures, importing from the asset library, auto-fix
and packing."""

from __future__ import annotations

from pathlib import Path

from asteria.editor.ui.icons import icon as workspace_icon

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
    )
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.editor.ui.widgets import asset_icon_name


class AssetPanelMixin:
    """The Assets panel."""

    def refresh_asset_list(self):
        from asteria.editor.assets.thumbnails import (
            ImageCache,
            asset_thumbnail,
            canonical_asset_thumbnail,
        )

        self.asset_list.clear()
        if self.document.project is None:
            return
        cache = ImageCache()
        for record in self.document.project.assets.records():
            item = QListWidgetItem(f"{record.kind}: {record.source_path}")
            item.setData(Qt.UserRole, str(record.source_path))
            icon = asset_thumbnail(self.document, record, cache)
            item.setIcon(
                icon if icon is not None else workspace_icon(asset_icon_name(record.source_path))
            )
            self.asset_list.addItem(item)
        for asset in self.document.project.assets.snapshot():
            item = QListWidgetItem(f"{asset.kind}: {asset.source.uri}")
            item.setData(Qt.UserRole, str(asset.source.uri))
            icon = canonical_asset_thumbnail(self.document, asset, cache)
            item.setIcon(
                icon if icon is not None else workspace_icon(asset_icon_name(asset.source.uri))
            )
            self.asset_list.addItem(item)

    def selected_asset_images(self):
        """Absolute paths of the selected Asset list entries that are PNG files on disk."""
        from asteria.editor.assets.image_tools import project_root

        root = project_root(self.document)
        paths = []
        for item in self.asset_list.selectedItems():
            source = item.data(Qt.UserRole)
            if not source:
                continue
            path = Path(source)
            path = path if path.is_absolute() else root / path
            if path.suffix.lower() == ".png" and path.is_file():
                paths.append(path)
        return paths

    def _asset_context_menu(self, position):
        from PySide6.QtWidgets import QMenu

        images = self.selected_asset_images()
        menu = QMenu(self.asset_list)
        fix = menu.addAction("Auto-fix Image…", lambda: self.auto_fix_selected_image())
        fix.setEnabled(len(images) == 1)
        pack = menu.addAction("Pack into Atlas…", lambda: self.pack_selected_images())
        pack.setEnabled(len(images) >= 1)
        menu.addSeparator()
        menu.addAction("Import from Asset Library…", lambda: self.import_from_asset_library())
        menu.exec(self.asset_list.viewport().mapToGlobal(position))

    def import_from_asset_library(self, *, dialog_hook=None, root=None):
        """Copy pictures from the engine's asset library into the project (one undo step)."""
        from asteria.editor.assets.image_tools import project_root
        from asteria.editor.assets.library_dialog import (
            AssetLibraryDialog,
            ImportLibraryAssetsCommand,
        )

        if self.document.project is None:
            self.statusBar().showMessage("Open a project to import library assets")
            return ()
        dialog = AssetLibraryDialog(self, root=root)
        accepted = dialog_hook(dialog) if dialog_hook is not None else dialog.exec()
        picks = dialog.picks()
        if not accepted or not picks:
            return ()
        command = ImportLibraryAssetsCommand(
            self.document.project, project_root(self.document), picks
        )
        self.document.execute(command)
        self.refresh_asset_list()
        count = len(command.records)
        self.statusBar().showMessage(f"Imported {count} picture(s) from the library")
        return tuple(command.records)

    def auto_fix_selected_image(self, *, dialog_hook=None):
        """AST-11: preview a safe fix on the selected image and apply it (original kept as
        .bak)."""
        from asteria.editor.assets.image_tools import ImageFixDialog

        images = self.selected_asset_images()
        if len(images) != 1:
            self.statusBar().showMessage("Select one PNG image in Assets to auto-fix")
            return None
        dialog = ImageFixDialog(images[0], self)
        if dialog_hook is not None:
            dialog_hook(dialog)
        else:
            dialog.exec()
        if dialog.applied is not None:
            self.refresh_asset_list()
            self.statusBar().showMessage(
                f"Fixed {images[0].name}; original kept as {images[0].stem}.bak.png"
            )
        return dialog.applied

    def pack_selected_images(self, output=None):
        """AST-11: pack the selected images into one atlas PNG plus a JSON of named regions."""
        from asteria.editor.assets.image_tools import pack_atlas, project_root

        images = self.selected_asset_images()
        if not images:
            self.statusBar().showMessage("Select PNG images in Assets to pack")
            return None
        if output is None:
            output, _ = QFileDialog.getSaveFileName(
                self,
                "Pack into Atlas",
                str(project_root(self.document) / "atlas.png"),
                "PNG (*.png)",
            )
            if not output:
                return None
        try:
            image, meta, report = pack_atlas(images, output)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Pack into Atlas", str(error))
            return None
        size = report.after_size
        self.statusBar().showMessage(
            f"Packed {len(images)} images into {image.name} ({size[0]}x{size[1]})"
        )
        return image, meta
