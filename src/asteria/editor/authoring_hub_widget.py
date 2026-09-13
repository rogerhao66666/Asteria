from __future__ import annotations

import math
import zlib
from copy import deepcopy

try:
    from PySide6.QtCore import Signal, Qt, QPointF, QRectF
    from PySide6.QtGui import (
        QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
    )
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
        QScrollArea, QSpinBox, QSplitter, QToolButton,
        QVBoxLayout, QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem,
        QGraphicsPathItem, QGraphicsTextItem, QStackedWidget,
    )
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False
    class QPointF: pass
    class QRectF: pass
    class QPolygonF: pass
    class QBrush: pass
    class QColor: pass
    class QLinearGradient: pass
    class QPainter: pass
    class QPainterPath: pass
    class QPen: pass
    class QWidget: pass
    class QCheckBox: pass
    class QComboBox: pass
    class QDoubleSpinBox: pass
    class QFormLayout: pass
    class QFrame: pass
    class QGroupBox: pass
    class QHBoxLayout: pass
    class QLabel: pass
    class QLineEdit: pass
    class QListWidget: pass
    class QListWidgetItem: pass
    class QPushButton: pass
    class QScrollArea: pass
    class QSpinBox: pass
    class QSplitter: pass
    class QToolButton: pass
    class QVBoxLayout: pass
    class QGraphicsView: pass
    class QGraphicsScene: pass
    class QGraphicsItem: pass
    class QGraphicsPathItem: pass
    class QGraphicsTextItem: pass
    class QStackedWidget: pass
    class Signal:
        def __init__(self,*args,**kwargs): pass

class AuthoringHubError(RuntimeError): pass

def _prettify_label(key):
    return str(key).replace("_", " ").strip().title()

_HIDDEN_RECORD_KEYS = frozenset({"schema", "version"})


def _is_scalar(value):
    return value is None or isinstance(value, (bool, int, float, str))


class TypedRecordEditor(QWidget):
    """Structured-data editor with a per-field-type widget, not a raw JSON tree.

    Field widgets are chosen from the *already-decoded* Python value at each
    key (bool/int/float/str/list/dict) — there is no separate schema, so a
    reserved-key convention (`_HIDDEN_RECORD_KEYS`) hides bookkeeping fields
    like "schema"/"version" rather than the editor needing type metadata.
    Reconstruction still goes through each canonical type's deserializer, so
    domain validation remains authoritative — this only changes presentation.

    Structure is deliberately kept plain/semantic (QGroupBox sections, one
    QFormLayout per level of scalar fields, objectName hooks like
    "RecordFieldGroup"/"RecordFieldLabel"/"RecordListButton" on every custom
    piece) so a later visual pass can restyle it entirely through QSS without
    touching this layout code.
    """
    if QT_AVAILABLE:
        changed=Signal()

    def __init__(self,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._data=None
        outer=QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        self._scroll=QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._content=QWidget()
        self._content.setObjectName("RecordForm")
        self._content_layout=QVBoxLayout(self._content)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

    def clear(self):
        self._data=None
        self._clear_layout(self._content_layout)

    def set_record(self,data):
        self._data=deepcopy(data)
        self._clear_layout(self._content_layout)
        if isinstance(self._data,dict):
            self._populate_dict(self._content_layout,self._data)
        self._content_layout.addStretch(1)

    def record(self):
        return deepcopy(self._data) if self._data is not None else None

    def _clear_layout(self,layout):
        while layout.count():
            item=layout.takeAt(0)
            widget=item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            else:
                child_layout=item.layout()
                if child_layout is not None:
                    self._clear_layout(child_layout)

    def _set_value(self,mapping,key,value):
        mapping[key]=value
        self.changed.emit()

    def _populate_dict(self,layout,mapping):
        keys=[k for k in mapping if k not in _HIDDEN_RECORD_KEYS]
        simple_keys=[k for k in keys if _is_scalar(mapping[k])]
        complex_keys=[k for k in keys if k not in simple_keys]
        if simple_keys:
            form_widget=QWidget()
            form=QFormLayout(form_widget)
            form.setLabelAlignment(Qt.AlignRight)
            for key in simple_keys:
                label=QLabel(_prettify_label(key))
                label.setObjectName("RecordFieldLabel")
                form.addRow(label,self._build_scalar_widget(mapping,key))
            layout.addWidget(form_widget)
        for key in complex_keys:
            layout.addWidget(self._build_group(mapping,key))

    def _build_group(self,mapping,key):
        value=mapping[key]
        group=QGroupBox(_prettify_label(key))
        group.setObjectName("RecordFieldGroup")
        group_layout=QVBoxLayout(group)
        if isinstance(value,dict):
            self._populate_dict(group_layout,value)
        elif isinstance(value,list):
            self._populate_list(group_layout,mapping,key)
        else:
            group_layout.addWidget(QLabel(str(value)))
        return group

    def _build_scalar_widget(self,mapping,key):
        value=mapping[key]
        if isinstance(value,bool):
            box=QCheckBox()
            box.setChecked(value)
            box.toggled.connect(lambda checked,m=mapping,k=key: self._set_value(m,k,checked))
            return box
        if isinstance(value,int):
            spin=QSpinBox()
            spin.setRange(-2_000_000_000,2_000_000_000)
            spin.setValue(value)
            spin.valueChanged.connect(lambda v,m=mapping,k=key: self._set_value(m,k,v))
            return spin
        if isinstance(value,float):
            spin=QDoubleSpinBox()
            spin.setRange(-1e12,1e12)
            spin.setDecimals(4)
            spin.setValue(value)
            spin.valueChanged.connect(lambda v,m=mapping,k=key: self._set_value(m,k,v))
            return spin
        was_none=value is None
        edit=QLineEdit("" if was_none else str(value))
        def on_edited(text,m=mapping,k=key,was_none=was_none):
            self._set_value(m,k,None if (was_none and text=="") else text)
        edit.textEdited.connect(on_edited)
        return edit

    def _populate_list(self,layout,parent_mapping,key):
        items=parent_mapping[key]
        if not items or all(_is_scalar(v) for v in items):
            self._populate_scalar_list(layout,parent_mapping,key)
        else:
            self._populate_dict_list(layout,parent_mapping,key)

    def _populate_scalar_list(self,layout,parent_mapping,key):
        items=parent_mapping[key]
        list_widget=QListWidget()
        list_widget.setObjectName("RecordTagList")
        for value in items:
            entry=QListWidgetItem(str(value))
            entry.setFlags(entry.flags()|Qt.ItemIsEditable)
            list_widget.addItem(entry)

        def sync():
            parent_mapping[key]=[list_widget.item(i).text() for i in range(list_widget.count())]
            self.changed.emit()

        list_widget.itemChanged.connect(lambda _item: sync())

        controls=QWidget()
        controls.setObjectName("RecordListRow")
        controls_layout=QHBoxLayout(controls)
        controls_layout.setContentsMargins(0,0,0,0)
        add_button=QToolButton()
        add_button.setObjectName("RecordListButton")
        add_button.setText("+")
        remove_button=QToolButton()
        remove_button.setObjectName("RecordListButton")
        remove_button.setText("−")

        def add_entry():
            entry=QListWidgetItem("")
            entry.setFlags(entry.flags()|Qt.ItemIsEditable)
            list_widget.addItem(entry)
            list_widget.setCurrentItem(entry)
            list_widget.editItem(entry)
            sync()

        def remove_entry():
            row=list_widget.currentRow()
            if row>=0:
                list_widget.takeItem(row)
                sync()

        add_button.clicked.connect(add_entry)
        remove_button.clicked.connect(remove_entry)
        controls_layout.addWidget(add_button)
        controls_layout.addWidget(remove_button)
        controls_layout.addStretch(1)

        layout.addWidget(list_widget)
        layout.addWidget(controls)

    def _populate_dict_list(self,layout,parent_mapping,key):
        items=parent_mapping[key]

        def rebuild():
            self._clear_layout(layout)
            for index,item in enumerate(items):
                entry_group=QGroupBox(f"{_prettify_label(key)} #{index+1}")
                entry_group.setObjectName("RecordFieldGroup")
                entry_layout=QVBoxLayout(entry_group)
                if isinstance(item,dict):
                    self._populate_dict(entry_layout,item)
                else:
                    entry_layout.addWidget(QLabel(str(item)))
                remove_button=QToolButton()
                remove_button.setObjectName("RecordListButton")
                remove_button.setText("Remove")
                def remove(_checked=False,i=index):
                    del items[i]
                    self.changed.emit()
                    rebuild()
                remove_button.clicked.connect(remove)
                entry_layout.addWidget(remove_button)
                layout.addWidget(entry_group)
            add_button=QToolButton()
            add_button.setObjectName("RecordListButton")
            add_button.setText(f"+ Add {_prettify_label(key)}")
            add_button.setEnabled(bool(items))
            def add(_checked=False):
                if items:
                    items.append(deepcopy(items[-1]))
                    self.changed.emit()
                    rebuild()
            add_button.clicked.connect(add)
            layout.addWidget(add_button)

        rebuild()

class AuthoringHubWidget(QWidget):
    """Reusable shell surface for one canonical authoring family.

    The hub owns navigation/presentation only. All mutations route through the
    supplied canonical controller; no parallel editor-side domain model exists.
    """
    if QT_AVAILABLE:
        changed=Signal()

    def __init__(self,title,controller,categories,*,encode,decode,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title=str(title); self.controller=controller
        self.categories=tuple(categories); self.encode=encode; self.decode=decode
        self._ids=[]

        header=QHBoxLayout()
        heading=QLabel(self.title); heading.setObjectName("SectionLabel")
        self.category=QComboBox()
        for key,label in self.categories: self.category.addItem(label,key)
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(heading); header.addStretch(1); header.addWidget(self.category)

        self.browser=QListWidget()
        self.browser.currentRowChanged.connect(self._selection_changed)
        self.editor=TypedRecordEditor()
        split=QSplitter(); split.addWidget(self.browser); split.addWidget(self.editor)
        split.setStretchFactor(1,1)

        buttons=QHBoxLayout()
        self.apply_button=QPushButton("Apply Changes")
        self.delete_button=QPushButton("Delete")
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        buttons.addStretch(1); buttons.addWidget(self.apply_button); buttons.addWidget(self.delete_button)

        layout=QVBoxLayout(self); layout.addLayout(header); layout.addWidget(split,1); layout.addLayout(buttons)
        self.refresh()

    @property
    def category_id(self):
        return self.category.currentData()

    @property
    def selected_id(self):
        row=self.browser.currentRow()
        return self._ids[row] if 0<=row<len(self._ids) else None

    def refresh(self):
        category=self.category_id
        self.browser.clear(); self.editor.clear(); self._ids=[]
        if category is None or self.controller.project is None: return
        self._ids=list(self._list_ids(category))
        self.browser.addItems(self._ids)
        if self._ids: self.browser.setCurrentRow(0)

    def _list_ids(self,category):
        # Controller families use either library ids or definitions().
        if hasattr(self.controller,"library") and category in getattr(self.controller,"CATEGORIES",()):
            return self.controller.library.ids(category)
        if hasattr(self.controller,"library") and category in self.controller.library.categories():
            return self.controller.library.ids(category)
        kind=getattr(getattr(self.controller,"information_architecture",None),"kind",lambda x:None)(category)
        if kind is not None:
            return tuple(str(getattr(x,kind.key_attr)) for x in self.controller.definitions(category))
        # RPG authoring controllers expose canonical database mappings. Adapter encode
        # supplies mapping lookup and may expose an ids callback.
        ids=getattr(self.encode,"ids",None)
        return ids(category,self.controller) if ids else ()

    def _selection_changed(self,row):
        key=self.selected_id
        if key is None: self.editor.clear(); return
        data=self.encode(self.category_id,key,self.controller)
        self.editor.set_record(data)

    def apply_selected(self):
        key=self.selected_id
        if key is None: return False
        data=self.editor.record()
        value=self.decode(self.category_id,data,self.controller)
        self.controller.edit(self.category_id,key,value)
        self.changed.emit(); self.refresh()
        if key in self._ids: self.browser.setCurrentRow(self._ids.index(key))
        return True

    def delete_selected(self):
        key=self.selected_id
        if key is None: return False
        self.controller.delete(self.category_id,key)
        self.changed.emit(); self.refresh(); return True



# QGraphicsItem painting ignores the app-wide dark QSS entirely (it isn't a
# QWidget), so SkillTreeGraphView must set its own colors explicitly or the
# default black-on-black rendering is invisible against the dark theme.
# Kept as plain constants here rather than in theme.py so a later visual pass
# can retune them without touching this file's layout/logic.
_GRAPH_BACKGROUND=QColor("#1b1e23")
_GRAPH_NODE_FILL_TOP=QColor("#3a5171")
_GRAPH_NODE_FILL_BOTTOM=QColor("#1f2b3d")
_GRAPH_NODE_BORDER=QColor("#8d7a45")
_GRAPH_NODE_BORDER_SELECTED=QColor("#e0c063")
_GRAPH_LINE=QColor("#6c8199")
_GRAPH_BADGE_FILL=QColor("#12161c")
_GRAPH_BADGE_BORDER=QColor("#8d7a45")
_GRAPH_BADGE_TEXT=QColor("#f4e3b0")

# Talent-tree style node: a framed icon plate, no permanent name label (the
# name is a hover tooltip plus a pinned label on click), and a rank-count
# badge in the corner for multi-rank skills.
_NODE_SIZE=48
_NODE_COLUMN_SPACING=78
_NODE_ROW_SPACING=86
_NODE_ICON_INSET=9
_NODE_BADGE_WIDTH=18
_NODE_BADGE_HEIGHT=15
_NODE_ARROW_SIZE=5


def _pt(rect,fx,fy):
    return QPointF(rect.x()+fx*rect.width(),rect.y()+fy*rect.height())


def _poly_path(rect,points):
    path=QPainterPath()
    path.moveTo(_pt(rect,*points[0]))
    for fx,fy in points[1:]:
        path.lineTo(_pt(rect,fx,fy))
    path.closeSubpath()
    return path


def _icon_sword(rect):
    path=_poly_path(rect,[(0.5,0.02),(0.64,0.22),(0.59,0.58),(0.41,0.58),(0.36,0.22)])
    path.addRect(QRectF(_pt(rect,0.22,0.56),_pt(rect,0.78,0.66)))
    path.addRect(QRectF(_pt(rect,0.44,0.66),_pt(rect,0.56,0.88)))
    path.addEllipse(_pt(rect,0.5,0.92),rect.width()*0.09,rect.height()*0.09)
    return path


def _icon_shield(rect):
    return _poly_path(rect,[(0.5,0.03),(0.9,0.19),(0.84,0.62),(0.5,0.97),(0.16,0.62),(0.1,0.19)])


def _icon_flame(rect):
    path=QPainterPath()
    path.moveTo(_pt(rect,0.5,0.02))
    path.cubicTo(_pt(rect,0.96,0.38),_pt(rect,0.86,0.8),_pt(rect,0.5,0.97))
    path.cubicTo(_pt(rect,0.14,0.8),_pt(rect,0.04,0.38),_pt(rect,0.5,0.02))
    path.closeSubpath()
    return path


def _icon_bolt(rect):
    return _poly_path(rect,[(0.62,0.02),(0.2,0.56),(0.44,0.56),(0.34,0.98),(0.8,0.4),(0.53,0.4)])


def _icon_gem(rect):
    return _poly_path(rect,[(0.5,0.03),(0.89,0.35),(0.72,0.95),(0.28,0.95),(0.11,0.35)])


def _icon_orb(rect):
    path=QPainterPath()
    path.addEllipse(rect.adjusted(rect.width()*0.08,rect.height()*0.08,-rect.width()*0.08,-rect.height()*0.08))
    return path


def _icon_book(rect):
    path=QPainterPath()
    path.addRoundedRect(QRectF(_pt(rect,0.1,0.16),_pt(rect,0.9,0.88)),3.0,3.0)
    return path


def _icon_leaf(rect):
    path=QPainterPath()
    path.moveTo(_pt(rect,0.52,0.02))
    path.cubicTo(_pt(rect,0.99,0.3),_pt(rect,0.84,0.86),_pt(rect,0.42,0.98))
    path.cubicTo(_pt(rect,0.06,0.72),_pt(rect,0.12,0.24),_pt(rect,0.52,0.02))
    path.closeSubpath()
    return path


def _icon_star(rect):
    cx=rect.x()+rect.width()/2; cy=rect.y()+rect.height()/2
    outer=min(rect.width(),rect.height())/2; inner=outer*0.44
    poly=QPolygonF()
    for i in range(10):
        angle=math.pi/5*i-math.pi/2
        r=outer if i%2==0 else inner
        poly.append(QPointF(cx+r*math.cos(angle),cy+r*math.sin(angle)))
    path=QPainterPath()
    path.addPolygon(poly)
    path.closeSubpath()
    return path


# Nodes have no icon/art asset field yet, so the icon is picked from this set
# by a stable hash of the node id: varied enough to tell skills apart at a
# glance, and deterministic so a node keeps the same icon between sessions.
# Drawn as vector paths rather than glyphs — font symbol coverage is
# inconsistent across platforms and rendered as broken shapes in testing.
_NODE_ICONS=(
    (_icon_sword,QColor("#d6dfeb")),
    (_icon_shield,QColor("#c98f4a")),
    (_icon_flame,QColor("#e8743b")),
    (_icon_bolt,QColor("#f2c744")),
    (_icon_gem,QColor("#a874d8")),
    (_icon_orb,QColor("#4fb8d8")),
    (_icon_book,QColor("#e0cfa0")),
    (_icon_leaf,QColor("#6fbf73")),
    (_icon_star,QColor("#e3a857")),
)


def _icon_for(node_id):
    return _NODE_ICONS[zlib.crc32(str(node_id).encode("utf-8"))%len(_NODE_ICONS)]


class SkillTreeGraphView(QGraphicsView):
    """Icon-grid graph view for canonical progression prerequisites.

    Nodes are framed icon plates, not name-labeled boxes: there is no
    per-node icon asset field yet, so a vector icon picked by a stable hash
    of the node id stands in for real art. The name shows as a hover tooltip
    and — since a node is clicked far more deliberately than merely brushed
    over while panning — also as a label pinned to the corner of the view
    while that node stays selected, rather than a permanent per-node label.
    A multi-rank skill gets a rank-count badge in the corner, and edges are
    routed as right-angle segments ending in an arrow, matching a talent-tree
    UI (e.g. WoW) rather than a plain data-tree diagram.
    """
    def __init__(self,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent); self.scene_graph=QGraphicsScene(self); self.setScene(self.scene_graph)
        self.scene_graph.setBackgroundBrush(QBrush(_GRAPH_BACKGROUND))
        self.setRenderHint(QPainter.Antialiasing,True)
        self.node_items={}
        self._node_decorations=[]
        self.name_label=QLabel(self)
        self.name_label.setObjectName("GraphSelectedNodeLabel")
        self.name_label.setStyleSheet(
            f"background-color:{_GRAPH_BADGE_FILL.name()};"
            f"color:{_GRAPH_BADGE_TEXT.name()};"
            f"border:1px solid {_GRAPH_NODE_BORDER.name()};"
            "border-radius:3px;padding:4px 8px;"
        )
        self.name_label.move(8,8)
        self.name_label.hide()
        self.scene_graph.selectionChanged.connect(self._update_name_label)

    def _update_name_label(self):
        selected=self.scene_graph.selectedItems()
        if not selected:
            self.name_label.hide()
            return
        self.name_label.setText(selected[0].toolTip())
        self.name_label.adjustSize()
        self.name_label.show()
        self.name_label.raise_()
    def set_graph_data(self,data):
        self.scene_graph.clear(); self.node_items={}
        self.name_label.hide()
        # QGraphicsItem (unlike QWidget) is not a QObject, so PySide6 does not
        # keep a child alive on Python's behalf just because it has a C++
        # parent — an unreferenced loop-local decoration item gets garbage
        # collected (and vanishes from the scene) as soon as the loop moves
        # on. Keep an explicit list so they actually stay on screen.
        self._node_decorations=[]
        if not data:return
        positions=data.get("node_positions",{})
        nodes=data.get("nodes",[])
        # Deterministic fallback layout by prerequisite depth.
        depths={}
        def depth(node):
            nid=node["node_id"]
            if nid in depths:return depths[nid]
            req=node.get("prerequisites",[])+node.get("any_prerequisites",[])
            depths[nid]=0 if not req else 1+max((depth(next(x for x in nodes if x["node_id"]==r["node_id"])) for r in req),default=0)
            return depths[nid]
        rows={}
        for node in nodes:
            d=depth(node); idx=rows.get(d,0); rows[d]=idx+1
            # Depth progresses downward (row); siblings at the same depth
            # branch sideways (column) — a top-to-bottom talent-tree layout.
            x,y=positions.get(node["node_id"],[idx*_NODE_COLUMN_SPACING,d*_NODE_ROW_SPACING])
            frame_path=QPainterPath()
            frame_path.addRoundedRect(QRectF(0,0,_NODE_SIZE,_NODE_SIZE),7.0,7.0)
            frame=QGraphicsPathItem(frame_path)
            gradient=QLinearGradient(0,0,0,_NODE_SIZE)
            gradient.setColorAt(0.0,_GRAPH_NODE_FILL_TOP)
            gradient.setColorAt(1.0,_GRAPH_NODE_FILL_BOTTOM)
            frame.setBrush(QBrush(gradient))
            frame.setPen(QPen(_GRAPH_NODE_BORDER,2))
            frame.setFlag(QGraphicsItem.ItemIsMovable,True); frame.setFlag(QGraphicsItem.ItemIsSelectable,True); frame.setPos(float(x),float(y))
            frame.setToolTip(str(node.get("display_name") or node["node_id"]))
            self.scene_graph.addItem(frame)

            builder,icon_color=_icon_for(node["node_id"])
            icon_rect=QRectF(
                _NODE_ICON_INSET,_NODE_ICON_INSET,
                _NODE_SIZE-2*_NODE_ICON_INSET,_NODE_SIZE-2*_NODE_ICON_INSET,
            )
            icon=QGraphicsPathItem(builder(icon_rect),frame)
            icon.setBrush(QBrush(icon_color))
            icon.setPen(QPen(icon_color.darker(170),1))
            self._node_decorations.append(icon)

            max_rank=int(node.get("max_rank",1) or 1)
            if max_rank>1:
                bw=_NODE_BADGE_WIDTH; bh=_NODE_BADGE_HEIGHT
                bx=_NODE_SIZE-bw+4; by=_NODE_SIZE-bh+3
                badge_path=QPainterPath()
                badge_path.addRoundedRect(QRectF(bx,by,bw,bh),3.0,3.0)
                badge=QGraphicsPathItem(badge_path,frame)
                badge.setPen(QPen(_GRAPH_BADGE_BORDER,1))
                badge.setBrush(QBrush(_GRAPH_BADGE_FILL))
                self._node_decorations.append(badge)
                label=QGraphicsTextItem(str(max_rank),frame)
                font=label.font(); font.setPointSize(8); font.setBold(True); label.setFont(font)
                label.setDefaultTextColor(_GRAPH_BADGE_TEXT)
                lr=label.boundingRect()
                label.setPos(bx+(bw-lr.width())/2,by+(bh-lr.height())/2)
                self._node_decorations.append(label)

            self.node_items[node["node_id"]]=frame
        # Lines intentionally follow current saved positions; refresh after dragging/saving.
        # Prerequisite depth strictly increases along an edge, so the source is
        # always above the target: route each edge as right-angle segments
        # (down, across, down) ending in an arrow, instead of one diagonal
        # line, so an edge never cuts across a node or its neighbours.
        line_pen=QPen(_GRAPH_LINE,2)
        for node in nodes:
            target=self.node_items[node["node_id"]]
            for req in node.get("prerequisites",[])+node.get("any_prerequisites",[]):
                source=self.node_items.get(req["node_id"])
                if source is not None:
                    self._add_connector(source,target,line_pen)
        self.scene_graph.setSceneRect(self.scene_graph.itemsBoundingRect().adjusted(-40,-40,40,40))

    def _add_connector(self,source,target,pen):
        # Anchor on the node's own geometry rather than sceneBoundingRect(),
        # which a corner rank badge would inflate.
        sx=source.pos().x()+_NODE_SIZE/2; sy=source.pos().y()+_NODE_SIZE
        tx=target.pos().x()+_NODE_SIZE/2; ty=target.pos().y()
        path=QPainterPath(QPointF(sx,sy))
        if abs(sx-tx)<0.5:
            path.lineTo(tx,ty)
        else:
            mid=sy+(ty-sy)/2
            path.lineTo(sx,mid); path.lineTo(tx,mid); path.lineTo(tx,ty)
        edge=self.scene_graph.addPath(path,pen)
        edge.setZValue(-1)
        a=_NODE_ARROW_SIZE
        head=QPolygonF([QPointF(tx,ty),QPointF(tx-a,ty-a*1.4),QPointF(tx+a,ty-a*1.4)])
        arrow=self.scene_graph.addPolygon(head,QPen(_GRAPH_LINE,1),QBrush(_GRAPH_LINE))
        arrow.setZValue(-1)
    def positions(self):
        return {key:[item.pos().x(),item.pos().y()] for key,item in self.node_items.items()}

class AdapterFamilyWidget(QWidget):
    """Qt authoring surface over a set of AuthoringCategoryAdapter objects."""

    if QT_AVAILABLE:
        changed=Signal()

    def __init__(self,title,adapters,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title=str(title)
        self.adapters={x.category_id:x for x in adapters}
        self._ids=[]

        header=QHBoxLayout()
        heading=QLabel(self.title); heading.setObjectName("SectionLabel")
        self.category=QComboBox()
        for adapter in adapters:self.category.addItem(adapter.label,adapter.category_id)
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(heading); header.addStretch(1); header.addWidget(self.category)

        self.browser=QListWidget()
        self.browser.currentRowChanged.connect(self._selection_changed)
        self.editor=TypedRecordEditor()
        self.graph_view=SkillTreeGraphView()
        self.detail_stack=QStackedWidget(); self.detail_stack.addWidget(self.editor); self.detail_stack.addWidget(self.graph_view)
        split=QSplitter(); split.addWidget(self.browser); split.addWidget(self.detail_stack)
        split.setStretchFactor(1,1)

        actions=QHBoxLayout()
        self.view_button=QPushButton("Graph View")
        self.view_button.clicked.connect(self.toggle_skill_tree_view)
        self.save_layout_button=QPushButton("Save Graph Layout")
        self.save_layout_button.clicked.connect(self.save_graph_layout)
        self.reset_layout_button=QPushButton("Reset Layout")
        self.reset_layout_button.clicked.connect(self.reset_graph_layout)
        self.duplicate_button=QPushButton("Duplicate…")
        self.apply_button=QPushButton("Apply Changes")
        self.delete_button=QPushButton("Delete")
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        actions.addWidget(self.view_button); actions.addWidget(self.save_layout_button)
        actions.addWidget(self.reset_layout_button); actions.addStretch(1); actions.addWidget(self.duplicate_button)
        actions.addWidget(self.apply_button); actions.addWidget(self.delete_button)

        layout=QVBoxLayout(self)
        layout.addLayout(header); layout.addWidget(split,1); layout.addLayout(actions)
        self.refresh()

    @property
    def category_id(self): return self.category.currentData()
    @property
    def adapter(self): return self.adapters.get(self.category_id)
    @property
    def selected_id(self):
        row=self.browser.currentRow()
        return self._ids[row] if 0<=row<len(self._ids) else None

    def refresh(self):
        adapter=self.adapter
        self.browser.clear(); self.editor.clear(); self._ids=[]
        if adapter is None:return
        self._ids=list(adapter.ids())
        self.browser.addItems(self._ids)
        self.duplicate_button.setEnabled(adapter.duplicate is not None and bool(self._ids))
        is_graph=self.category_id=="graphs"
        self.view_button.setVisible(is_graph); self.save_layout_button.setVisible(is_graph)
        self.reset_layout_button.setVisible(is_graph)
        if not is_graph:self.detail_stack.setCurrentWidget(self.editor)
        if self._ids:self.browser.setCurrentRow(0)

    def _selection_changed(self,row):
        key=self.selected_id
        if key is None:self.editor.clear(); return
        data=self.adapter.encode(self.adapter.get(key)); self.editor.set_record(data)
        if self.category_id=="graphs":
            self.graph_view.set_graph_data(data)
            if data.get("editor_view")=="graph":self.detail_stack.setCurrentWidget(self.graph_view)

    def toggle_skill_tree_view(self):
        if self.category_id!="graphs":return False
        graph=self.detail_stack.currentWidget() is self.graph_view
        self.detail_stack.setCurrentWidget(self.editor if graph else self.graph_view)
        self.view_button.setText("Graph View" if graph else "List / Data View")
        return True

    def save_graph_layout(self):
        if self.category_id!="graphs" or self.selected_id is None:return False
        data=self.editor.record(); data["node_positions"]=self.graph_view.positions(); data["editor_view"]="graph"
        value=self.adapter.decode(data); self.adapter.edit(self.selected_id,value); self.changed.emit(); self.refresh(); return True

    def reset_graph_layout(self):
        # Once a layout is saved, positions are fixed data — a fresh default
        # (e.g. after SkillTreeGraphView's arrangement logic changes) never
        # applies on its own. This clears the saved positions so the next
        # render recomputes the default top-to-bottom layout.
        if self.category_id!="graphs" or self.selected_id is None:return False
        key=self.selected_id
        data=self.editor.record(); data["node_positions"]={}
        value=self.adapter.decode(data); self.adapter.edit(key,value)
        self.changed.emit(); self.refresh()
        if key in self._ids:self.browser.setCurrentRow(self._ids.index(key))
        self.detail_stack.setCurrentWidget(self.graph_view)
        return True

    def apply_selected(self):
        key=self.selected_id
        if key is None:return False
        value=self.adapter.decode(self.editor.record())
        self.adapter.edit(key,value)
        self.changed.emit()
        current=key; self.refresh()
        if current in self._ids:self.browser.setCurrentRow(self._ids.index(current))
        return True

    def delete_selected(self):
        key=self.selected_id
        if key is None:return False
        self.adapter.delete(key); self.changed.emit(); self.refresh(); return True

    def duplicate_selected_as(self,new_id):
        key=self.selected_id
        if key is None:return False
        if self.adapter.duplicate is None:
            raise AuthoringHubError("current category does not support direct duplication")
        self.adapter.duplicate(key,str(new_id))
        self.changed.emit(); self.refresh()
        if str(new_id) in self._ids:self.browser.setCurrentRow(self._ids.index(str(new_id)))
        return True

    def duplicate_selected(self):
        if self.selected_id is None or self.adapter.duplicate is None:return False
        from PySide6.QtWidgets import QInputDialog
        value,ok=QInputDialog.getText(self,"Duplicate", "New ID:")
        if not ok or not value.strip():return False
        return self.duplicate_selected_as(value.strip())


class FamilyHostWidget(QWidget):
    """Rebuildable host so opening another Project never leaves stale adapters."""

    if QT_AVAILABLE:
        changed=Signal()

    def __init__(self,title,builder,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title=str(title); self.builder=builder; self.child=None; self.project_id=None
        self.layout=QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        self.rebuild()

    def rebuild(self):
        project=getattr(getattr(self.builder,"__self__",None),"project",None)
        pid=getattr(project,"id",None)
        if self.child is not None and pid==self.project_id:
            refresh = getattr(self.child, "refresh", None)
            if callable(refresh):
                refresh()
            return
        if self.child is not None:
            self.layout.removeWidget(self.child); self.child.deleteLater(); self.child=None
        self.project_id=pid
        if project is None:
            self.child=QLabel("Open a Project to use this authoring workspace.")
        else:
            self.child=AdapterFamilyWidget(self.title,self.builder())
            self.child.changed.connect(self.changed.emit)
        self.layout.addWidget(self.child)
