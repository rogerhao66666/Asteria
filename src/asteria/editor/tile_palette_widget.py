try:
    from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QToolButton,QListWidget,QLabel
    from PySide6.QtCore import Signal,Qt
except Exception:
    QWidget=object;Signal=None;Qt=None

from .tile_palette import build_tile_palette

class TilePaletteWidget(QWidget):
    if Signal is not None:
        tileSelected=Signal(int)
        modeChanged=Signal(str)

    def __init__(self,parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._tileset=None
        layout=QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(6)

        tools=QHBoxLayout()
        self.select_button=QToolButton();self.select_button.setText("Select")
        self.paint_button=QToolButton();self.paint_button.setText("Paint")
        self.erase_button=QToolButton();self.erase_button.setText("Erase")
        self.fill_button=QToolButton();self.fill_button.setText("Fill")
        self.rect_button=QToolButton();self.rect_button.setText("Rect")
        for button in (self.select_button,self.paint_button,self.erase_button,self.fill_button,self.rect_button):
            button.setCheckable(True);tools.addWidget(button)
        self.select_button.setChecked(True)
        layout.addLayout(tools)

        self.layer_label=QLabel("Layer: —")
        self.layer_label.setObjectName("MutedLabel")
        layout.addWidget(self.layer_label)

        self.list=QListWidget()
        self.list.setObjectName("TilePaletteList")
        layout.addWidget(self.list,1)

        self.select_button.clicked.connect(lambda:self._set_mode("select"))
        self.paint_button.clicked.connect(lambda:self._set_mode("paint"))
        self.erase_button.clicked.connect(lambda:self._set_mode("erase"))
        self.fill_button.clicked.connect(lambda:self._set_mode("fill"))
        self.rect_button.clicked.connect(lambda:self._set_mode("rectangle"))
        self.list.currentRowChanged.connect(self._row_changed)

    def _set_mode(self,mode):
        mapping={"select":self.select_button,"paint":self.paint_button,"erase":self.erase_button,"fill":self.fill_button,"rectangle":self.rect_button}
        for name,button in mapping.items():
            button.setChecked(name==mode)
        self.modeChanged.emit(mode)

    def _row_changed(self,row):
        if self._tileset is None or row<0:return
        items=build_tile_palette(self._tileset)
        if row<len(items):
            self.tileSelected.emit(items[row].tile_id)

    def set_tileset(self,tileset):
        self._tileset=tileset
        self.list.clear()
        if tileset is None:return
        for item in build_tile_palette(tileset):
            suffix=[]
            if item.terrain:suffix.append(item.terrain)
            if item.collision!="none":suffix.append(item.collision)
            meta=f"  · {' / '.join(suffix)}" if suffix else ""
            self.list.addItem(f"Tile {item.tile_id}{meta}")

    def set_layer(self,layer):
        self.layer_label.setText(f"Layer: {layer.name}" if layer is not None else "Layer: —")
