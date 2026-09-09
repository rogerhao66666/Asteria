try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QWidget,QVBoxLayout,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,
        QLabel,QAbstractItemView,QHeaderView
    )
    QT_AVAILABLE=True
except Exception:
    Qt=None; QT_AVAILABLE=False
    class QWidget: pass

class ProjectTreeWidget(QWidget):
    def __init__(self, document, parent=None):
        if not QT_AVAILABLE: raise RuntimeError('PySide6 is required for editor UI')
        super().__init__(parent); self.document=document
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(['Project']); self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(self.tree)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed); self.refresh()

    def _on_selection_changed(self):
        items=self.tree.selectedItems()
        if not items:
            self.document.selection.set_many("none",())
            return
        payloads=[i.data(0,Qt.UserRole) for i in items]
        payloads=[p for p in payloads if p]
        if not payloads:
            return
        kinds={p[0] for p in payloads}
        if len(kinds)==1:
            kind=payloads[0][0]
            values=[p[1] for p in payloads]
            self.document.selection.set_many(kind,values)
        else:
            kind,value=payloads[0]
            self.document.selection.set_single(kind,value)
        window=self.window()
        if hasattr(window,"refresh_inspector"):
            window.refresh_inspector()
        if hasattr(window,"_refresh_actions"):
            window._refresh_actions()

    def refresh(self):
        self.tree.clear(); project=self.document.project
        if project is None:return
        root=QTreeWidgetItem([project.name]); root.setData(0,Qt.UserRole,('project',project)); self.tree.addTopLevelItem(root)
        scenes=QTreeWidgetItem(['Scenes']); root.addChild(scenes)
        for scene in project.scenes():
            sitem=QTreeWidgetItem([scene.name]); sitem.setData(0,Qt.UserRole,('scene',scene)); scenes.addChild(sitem)
            for entity in scene.entities():
                eitem=QTreeWidgetItem([entity.name]); eitem.setData(0,Qt.UserRole,('entity',entity)); sitem.addChild(eitem)
                for component in entity.components():
                    citem=QTreeWidgetItem([type(component).__name__]); citem.setData(0,Qt.UserRole,('component',component)); eitem.addChild(citem)
        assets=QTreeWidgetItem(['Assets']); root.addChild(assets)
        for record in project.assets.records():
            item=QTreeWidgetItem([record.source_path]); item.setData(0,Qt.UserRole,('asset',record)); assets.addChild(item)
        root.setExpanded(True); scenes.setExpanded(True)

class InspectorWidget(QWidget):
    def __init__(self, document, parent=None):
        if not QT_AVAILABLE: raise RuntimeError('PySide6 is required for editor UI')
        super().__init__(parent); self.document=document; self._refreshing=False; self._field_models={}
        self.title=QLabel('Nothing selected')
        self.error=QLabel('')
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Property','Value','Type'])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._item_changed)
        layout=QVBoxLayout(self); layout.addWidget(self.title); layout.addWidget(self.error); layout.addWidget(self.table)
    def show_message(self,message):
        self._refreshing=True
        try:
            self.title.setText(message); self.error.setText(''); self.table.setRowCount(0); self._field_models={}
        finally:self._refreshing=False
    def show_properties(self,title,rows):
        self._refreshing=True
        try:
            self.title.setText(title); self.error.setText(''); self._field_models={}; self.table.setRowCount(len(rows))
            for i,(name,value,type_name) in enumerate(rows):
                n=QTableWidgetItem(str(name)); n.setFlags(n.flags() & ~Qt.ItemIsEditable)
                v=QTableWidgetItem(str(value)); v.setFlags(v.flags() & ~Qt.ItemIsEditable)
                t=QTableWidgetItem(str(type_name)); t.setFlags(t.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i,0,n); self.table.setItem(i,1,v); self.table.setItem(i,2,t)
        finally:self._refreshing=False
    def show_component(self,title,fields):
        self._refreshing=True
        try:
            self.title.setText(title); self.error.setText(''); self.table.setRowCount(len(fields)); self._field_models={}
            for row,f in enumerate(fields):
                self._field_models[row]=f
                n=QTableWidgetItem(f.label); n.setFlags(n.flags() & ~Qt.ItemIsEditable)
                v=QTableWidgetItem(str(f.value))
                if not f.editable: v.setFlags(v.flags() & ~Qt.ItemIsEditable)
                t=QTableWidgetItem(f.type_name); t.setFlags(t.flags() & ~Qt.ItemIsEditable)
                if f.tooltip:
                    n.setToolTip(f.tooltip); v.setToolTip(f.tooltip)
                self.table.setItem(row,0,n); self.table.setItem(row,1,v); self.table.setItem(row,2,t)
        finally:self._refreshing=False
    def _item_changed(self,item):
        if self._refreshing or item.column()!=1:return
        field=self._field_models.get(item.row())
        if field is None or not field.editable:return
        window=self.window()
        if not hasattr(window,'edit_selected_component_field'):return
        ok,error=window.edit_selected_component_field(field.name,item.text())
        if ok:
            self.error.setText('')
            self._refreshing=True
            try:item.setText(str(getattr(self.document.selection.value,field.name)))
            finally:self._refreshing=False
        else:
            self.error.setText(error or 'Invalid value')
            self._refreshing=True
            try:item.setText(str(getattr(self.document.selection.value,field.name)))
            finally:self._refreshing=False

class SceneViewportPlaceholder(QWidget):
    def __init__(self,parent=None):
        if not QT_AVAILABLE: raise RuntimeError('PySide6 is required for editor UI')
        super().__init__(parent); layout=QVBoxLayout(self)
        label=QLabel('Scene Viewport\n(runtime renderer integration comes next)'); label.setAlignment(Qt.AlignCenter); layout.addWidget(label)
