from __future__ import annotations

import math
import zlib
from copy import deepcopy

try:
    from PySide6.QtCore import Signal, Qt, QPointF, QRect, QRectF, QSize, QTimer
    from PySide6.QtGui import (
        QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
        QPixmap, QPolygonF,
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
    class QPixmap: pass
    class QIcon: pass
    class QRect: pass
    class QSize: pass
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

from .class_design_panel import ClassDesignPanel
from .qt_texture_renderer import QtTextureCache
from .record_editing import (
    MappingTable, RecordListTable, ScalarListTable, format_cell, parse_cell,
)


class AuthoringHubError(RuntimeError): pass

def _prettify_label(key):
    return str(key).replace("_", " ").strip().title()

_HIDDEN_RECORD_KEYS = frozenset({"schema", "version"})

_PREVIEW_ICON_SIZE = QSize(20, 30) if QT_AVAILABLE else None

# Field name -> catalog key. A field naming another record is far easier to fill
# from a list of what actually exists than by typing an id from memory.
_REFERENCE_FIELDS = {
    "class_id": "classes",
    "ability_id": "abilities",
    "abilities": "abilities",
    "granted_abilities": "abilities",
    "unlocked_passives": "passives",
    "source_ability_id": "abilities",
    "result_ability_id": "abilities",
    "actor_id": "units",
    "actor_ids": "units",
    "roster_actor_ids": "units",
    "active_actor_ids": "units",
    "passive_id": "passives",
    "item_id": "items",
    "equipment_id": "equipment",
    "growth_id": "growth",
    "progression_track_id": "tracks",
    "progression_track_ids": "tracks",
    "graph_id": "graphs",
    "enemy_id": "units",
    "formation_id": "formations",
    "ai_id": "ai",
}

# Fields with a closed set of values, offered as a plain dropdown.
_ENUM_FIELDS = {"kind": ("actor", "enemy")}

# Dict fields whose keys are project-defined stat/resource names rather than
# fixed engine fields — the table offers what the project already uses.
_STAT_FIELDS = {"base_stats": "stats", "stat_bonuses": "stats", "stats": "stats"}
_RESOURCE_FIELDS = {"base_resources": "resources", "resource_bonuses": "resources", "resources": "resources"}


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

    def __init__(self,parent=None,*,scrollable=True):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._data=None
        self._catalog={}
        self._primary_key=None
        outer=QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        if scrollable:
            self._scroll=QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setFrameShape(QFrame.NoFrame)
            self._content=QWidget()
            self._content.setObjectName("RecordForm")
            self._content_layout=QVBoxLayout(self._content)
            self._scroll.setWidget(self._content)
            outer.addWidget(self._scroll)
        else:
            # Used when a parent (AdapterFamilyWidget) wraps several panels —
            # this editor plus a category's custom panel (appearance/class
            # design) — in one shared scroll area of its own. A second,
            # independent scroll area nested inside that one starved every
            # panel of height and made tables need their own internal
            # scrollbar; one scroll region per page fixes that.
            self._scroll=None
            self._content=self
            self._content.setObjectName("RecordForm")
            self._content_layout=outer

    def set_catalog(self,catalog):
        """Known ids per family, used to offer reference fields as dropdowns."""
        self._catalog=dict(catalog or {})

    def clear(self):
        self._data=None
        self._primary_key=None
        self._clear_layout(self._content_layout)

    def set_record(self,data,*,primary_key=None):
        self._primary_key=primary_key
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
            # The macOS style centres a form in its available width, which
            # here floats every field in the middle of a wide panel and
            # pushes the rest of the row off past the left edge.
            form.setFormAlignment(Qt.AlignLeft|Qt.AlignTop)
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
            if value and not all(_is_scalar(v) for v in value.values()):
                self._populate_dict(group_layout,value)
            else:
                group_layout.addWidget(self._build_mapping_table(value,key))
        elif isinstance(value,list):
            self._populate_list(group_layout,mapping,key)
        else:
            group_layout.addWidget(QLabel(str(value)))
        return group

    def _catalog_options(self,key):
        family=_REFERENCE_FIELDS.get(str(key))
        return tuple(self._catalog.get(family,())) if family else ()

    def _build_mapping_table(self,mapping,key):
        """Name/Value table for a dict of scalars (stat or resource blocks)."""
        family=_STAT_FIELDS.get(str(key)) or _RESOURCE_FIELDS.get(str(key))
        header="Stat" if family=="stats" else ("Resource" if family=="resources" else "Name")
        return MappingTable(
            mapping,self.changed.emit,name_header=header,
            suggestions=self._catalog.get(family,()) if family else (),
        )

    def _build_reference_widget(self,mapping,key,options):
        """Editable combo: pick an existing id, or type one that does not exist yet."""
        value=mapping[key]
        combo=QComboBox()
        combo.setEditable(True)
        combo.addItem("")
        for option in options:
            combo.addItem(str(option))
        text="" if value is None else str(value)
        index=combo.findText(text)
        if index<0:
            combo.addItem(text) if text else None
            index=combo.findText(text)
        combo.setCurrentIndex(max(0,index))
        was_none=value is None
        def on_changed(new_text,m=mapping,k=key,was_none=was_none):
            self._set_value(m,k,None if (was_none and not new_text) else new_text)
        combo.currentTextChanged.connect(on_changed)
        return combo

    def _build_enum_widget(self,mapping,key,options):
        combo=QComboBox()
        for option in options:combo.addItem(str(option))
        index=combo.findText("" if mapping[key] is None else str(mapping[key]))
        combo.setCurrentIndex(max(0,index))
        combo.currentTextChanged.connect(
            lambda text,m=mapping,k=key: self._set_value(m,k,text)
        )
        return combo

    def _build_scalar_widget(self,mapping,key):
        value=mapping[key]
        if key==self._primary_key:
            # The record id is its identity in the database; `edit(key, value)`
            # cannot rename it, so editing this field silently did nothing.
            label=QLineEdit(str(value))
            label.setReadOnly(True)
            label.setObjectName("RecordIdField")
            label.setToolTip("Use Duplicate… to create a record under a different id.")
            return label
        if isinstance(value,(str,type(None))):
            enum=_ENUM_FIELDS.get(str(key))
            if enum:
                return self._build_enum_widget(mapping,key,enum)
            options=self._catalog_options(key)
            if options:
                return self._build_reference_widget(mapping,key,options)
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
        table=ScalarListTable(
            parent_mapping,key,self.changed.emit,header=_prettify_label(key),
        )
        layout.addWidget(table)

    def _populate_dict_list(self,layout,parent_mapping,key):
        table=RecordListTable(parent_mapping,key,self.changed.emit)
        layout.addWidget(table)

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
        split.setStyleSheet(_SPLITTER_STYLE)
        split.setStretchFactor(1,1)
        split.setSizes([_BROWSER_WIDTH,_BROWSER_WIDTH*4])

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
# Slack kept around the nodes on the graph canvas.
_CANVAS_MARGIN=60.0
# The graph canvas is a fixed logical size rather than "however big the view
# happens to be". Sizing it from the viewport meant every position derived
# from it depended on *when* it was measured, and the first build runs while
# the canvas is still hidden behind the list page at a size the layout has
# not settled yet — which is how a brand-new tree's root kept landing off to
# one side. A constant canvas makes "the middle" mean the same thing no
# matter when it is asked for.
_CANVAS_WIDTH=2400.0
_CANVAS_HEIGHT=1600.0

# Shape of a node added from the graph view, matching ProgressionNodeDefinition.
_GRAPH_NODE_TEMPLATE={
    "schema":"asteria.rpg.progression_node","version":1,
    "node_id":"","display_name":"","max_rank":1,"rank_costs":[{}],
    "rewards":[{"stat_bonuses":{},"resource_bonuses":{},"granted_tags":[],
                "granted_abilities":[],"unlocked_passives":[],"granted_capabilities":[]}],
    "prerequisites":[],"any_prerequisites":[],"exclusive_group":None,"tags":[],
}


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


# Nodes have no dedicated icon asset field, so a node's icon is stored as a
# plain tag ("icon:sword") on the node's existing `tags` list — no new
# engine field needed. Picked in the Add-Node dialog; a node with no such
# tag (e.g. one created before this existed) falls back to a stable hash of
# its node_id, so it still gets a consistent icon rather than a blank one.
# Drawn as vector paths rather than glyphs — font symbol coverage is
# inconsistent across platforms and rendered as broken shapes in testing.
_NODE_ICON_NAMES=("sword","shield","flame","bolt","gem","orb","book","leaf","star")
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
_ICON_TAG_PREFIX="icon:"
_ICON_BY_NAME=dict(zip(_NODE_ICON_NAMES,_NODE_ICONS))


def _icon_for(node):
    for tag in node.get("tags") or ():
        if isinstance(tag,str) and tag.startswith(_ICON_TAG_PREFIX):
            chosen=_ICON_BY_NAME.get(tag[len(_ICON_TAG_PREFIX):])
            if chosen is not None:return chosen
    return _NODE_ICONS[zlib.crc32(str(node["node_id"]).encode("utf-8"))%len(_NODE_ICONS)]


def _render_icon_pixmap(builder,color,size=20):
    pixmap=QPixmap(size,size)
    pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing,True)
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(color.darker(170),1))
    painter.drawPath(builder(QRectF(1,1,size-2,size-2)))
    painter.end()
    return pixmap


def _slugify(text):
    slug=[]
    prev_underscore=False
    for ch in str(text).strip().lower():
        if ch.isalnum():
            slug.append(ch);prev_underscore=False
        elif not prev_underscore:
            slug.append("_");prev_underscore=True
    return "".join(slug).strip("_") or "node"


# Edge appearance is the author's call, not the editor's: a talent tree can
# want square "bus" routing (WoW/Terraria style), plain straight drops, or
# direct diagonals. Stored per graph as editor-only tags on the graph record,
# the same convention node icons use.
# Starting width of the record-id list beside each editor.
_BROWSER_WIDTH=190

_SPLITTER_STYLE="""
QSplitter::handle{background:palette(mid);}
QSplitter::handle:horizontal{width:1px;}
QSplitter::handle:vertical{height:1px;}
"""

_EDGE_STYLE_TAG="edge_style:"
_EDGE_ARROW_TAG="edge_arrow:"
_EDGE_STYLES=("elbow","straight","diagonal")
_DEFAULT_EDGE_STYLE="elbow"

# Where a brand-new node lands when the author didn't right-click a spot:
# packed left-to-right in rows, so nodes never stack on top of each other.
_NEW_NODE_COLUMNS=5


_ALIGN_SNAP_DISTANCE=6.0

class _GraphNodeItem(QGraphicsPathItem):
    """Node plate that reports its own moves so connections can follow it.

    Without this the edges were drawn once from the positions at build time
    and then stayed put while the node was dragged away from them, which
    read as "the connection broke".
    """

    def __init__(self,path,node_id,view):
        super().__init__(path)
        self.node_id=node_id
        self._view=view
        self.setFlag(QGraphicsItem.ItemIsMovable,True)
        self.setFlag(QGraphicsItem.ItemIsSelectable,True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges,True)

    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and self._view is not None:
            # Only snap an interactive drag, never a programmatic setPos() —
            # _rebuild_scene() places every node this same way on load/undo,
            # and snapping there would silently drag a saved layout's nodes
            # together just because they happened to load a few pixels apart.
            if not self._view._building:
                return self._view._snap_position(self,value)
        if change==QGraphicsItem.ItemPositionHasChanged and self._view is not None:
            self._view._node_moved()
        elif change==QGraphicsItem.ItemSelectedHasChanged:
            self.setPen(QPen(_GRAPH_NODE_BORDER_SELECTED if value else _GRAPH_NODE_BORDER,2))
        return super().itemChange(change,value)


class SkillTreeGraphView(QGraphicsView):
    """Talent-tree canvas over canonical progression prerequisites.

    Layout is entirely the author's: a node sits where it was dropped, and
    nothing re-flows it. (An earlier version auto-arranged nodes by
    prerequisite depth, which fought every manual drag.) Connections are
    drawn between whatever nodes the author linked, in the line style the
    graph is configured for, and follow their nodes as those are moved.

    Nodes are framed icon plates: a vector icon picked either from the
    node's `icon:` tag or a stable hash of its id, with the skill's maximum
    rank in the bottom-right corner the way a talent tree shows how many
    points a talent takes. The name shows as a hover tooltip and as a label
    pinned to the corner of the view while that node stays selected.
    """
    if QT_AVAILABLE:
        # Emitted after the view edits the node list itself (add/duplicate/
        # delete), so the hub can write the change back through the adapter.
        graphEdited=Signal()

    def __init__(self,parent=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent); self.scene_graph=QGraphicsScene(self); self.setScene(self.scene_graph)
        self.scene_graph.setBackgroundBrush(QBrush(_GRAPH_BACKGROUND))
        self.setRenderHint(QPainter.Antialiasing,True)
        # Dragging a node still moves it; dragging empty space sweeps out a
        # rubber band, so several nodes can be picked for copy/delete at once.
        self.setDragMode(QGraphicsView.RubberBandDrag)
        # The canvas is larger than the view, so resizing has to keep the
        # middle of what the author is looking at in the middle — anchoring
        # at the top-left instead would slide a centred tree off sideways
        # every time the window changed size.
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self._data=None
        self.node_items={}
        self._node_decorations=[]
        self._edge_map={}
        self._link_source_id=None
        self._link_preview=None
        self._connect_mode=False
        self._connect_pending_source=None
        self._edge_items=[]
        self._building=False
        self._drag_positions=None
        self._centered_graph_id=None
        self._align_guide_v=None
        self._align_guide_h=None
        self._scene_rect=None
        # Bug fixed here: this was `QLabel(text)` with no parent, which makes
        # it a separate top-level window rather than an overlay on the view —
        # it never actually rendered where the .move() calls thought it did.
        self.hint_label=QLabel(self)
        self.hint_label.setObjectName("MutedLabel")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(
            f"background-color:{_GRAPH_BADGE_FILL.name()};color:#9098a6;"
            "padding:3px 8px;"
        )
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
        self._update_hint_text()
        self.hint_label.show()
        self._reposition_hint_label()

    def set_connect_mode(self,enabled):
        """Click-to-connect: click a prerequisite node, then the node that
        needs it. Explicit toolbar-driven alternative to shift-dragging,
        which wasn't a discoverable gesture on its own."""
        self._connect_mode=bool(enabled)
        self._clear_connect_pending()
        # The viewport carries its own cursor (QGraphicsView sets one there
        # whenever the pointer is over an item that declares a cursor, such
        # as a connection line). Setting only the view's left the crosshair
        # showing after Connect was switched back off.
        cursor=Qt.CrossCursor if self._connect_mode else Qt.ArrowCursor
        self.setCursor(cursor)
        self.viewport().setCursor(cursor)
        self._update_hint_text()

    def _clear_connect_pending(self):
        if self._connect_pending_source is not None:
            item=self.node_items.get(self._connect_pending_source)
            if item is not None:item.setSelected(False)
        self._connect_pending_source=None

    def _update_hint_text(self):
        if self._connect_mode:
            if self._connect_pending_source is None:
                text="Connect: click the prerequisite skill (learned first)"
            else:
                node=next((n for n in self._nodes() if n["node_id"]==self._connect_pending_source),None)
                name=node.get("display_name") if node else self._connect_pending_source
                text=f"Connect: now click the skill that needs “{name}” — Esc to cancel"
        else:
            text="Drag a node to move · Right-click a node or connection for options"
        self.hint_label.setText(text)
        self._reposition_hint_label()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._reposition_hint_label()
        # The canvas floor is sized from the viewport, and the first build
        # runs before this view has been laid out — without this the floor
        # stays stuck at that placeholder size and only catches up on the
        # next rebuild, which is mid-drag-release and visibly shifts the
        # canvas. Settle it here, while nothing is being dragged.
        if self._data is not None:
            self._update_scene_rect()

    def _reposition_hint_label(self):
        self.hint_label.setFixedWidth(max(120,self.width()-16))
        self.hint_label.adjustSize()
        self.hint_label.move(8,self.height()-self.hint_label.height()-8)
        # QGraphicsView's own viewport child widget can end up stacked above
        # a plain QLabel(self) overlay once the view is actually shown/resized
        # (the same reason _update_name_label() raises name_label on every
        # selection change) — without this the hint silently renders behind
        # the viewport and never appears at all.
        self.hint_label.raise_()

    def _update_name_label(self):
        selected=self.scene_graph.selectedItems()
        if not selected:
            self.name_label.hide()
            return
        self.name_label.setText(selected[0].toolTip())
        self.name_label.adjustSize()
        self.name_label.show()
        self.name_label.raise_()
    def selected_node_ids(self):
        selected=set(self.scene_graph.selectedItems())
        return [nid for nid,item in self.node_items.items() if item in selected]

    def _nodes(self):
        return (self._data or {}).get("nodes") or []

    def _unique_node_id(self,base):
        existing={node["node_id"] for node in self._nodes()}
        candidate=base
        index=2
        while candidate in existing:
            candidate=f"{base}_{index}"
            index+=1
        return candidate

    def _commit(self):
        # Every node keeps the position it is actually sitting at: the layout
        # belongs to the author, so nothing here recomputes or discards it.
        previous=dict(self._data.get("node_positions") or {})
        previous.update(self.positions())
        node_ids={node["node_id"] for node in self._nodes()}
        self._data["node_positions"]={
            node_id:previous[node_id]
            for node_id in node_ids if node_id in previous
        }
        self._data["editor_view"]="graph"
        self.set_graph_data(self._data)
        self.graphEdited.emit()

    # ---- edge styling (stored as editor-only tags on the graph record) ----

    def _graph_tags(self):
        return (self._data or {}).get("tags") or []

    def edge_style(self):
        for tag in self._graph_tags():
            if isinstance(tag,str) and tag.startswith(_EDGE_STYLE_TAG):
                style=tag[len(_EDGE_STYLE_TAG):]
                if style in _EDGE_STYLES:return style
        return _DEFAULT_EDGE_STYLE

    def edge_arrows(self):
        for tag in self._graph_tags():
            if isinstance(tag,str) and tag.startswith(_EDGE_ARROW_TAG):
                return tag[len(_EDGE_ARROW_TAG):]!="off"
        return True

    def _set_graph_tag(self,prefix,value):
        if self._data is None:return False
        tags=[
            tag for tag in self._graph_tags()
            if not (isinstance(tag,str) and tag.startswith(prefix))
        ]
        tags.append(f"{prefix}{value}")
        self._data["tags"]=tags
        self._commit()
        return True

    def set_edge_style(self,style):
        if style not in _EDGE_STYLES:return False
        return self._set_graph_tag(_EDGE_STYLE_TAG,style)

    def set_edge_arrows(self,enabled):
        return self._set_graph_tag(_EDGE_ARROW_TAG,"on" if enabled else "off")

    def add_node(self,position=None,*,display_name=None,icon_name=None):
        if self._data is None:return False
        node_id=self._unique_node_id(_slugify(display_name) if display_name else "node")
        node=deepcopy(_GRAPH_NODE_TEMPLATE)
        node["node_id"]=node_id
        node["display_name"]=display_name or node_id
        if icon_name:
            node["tags"]=[f"{_ICON_TAG_PREFIX}{icon_name}"]
        self._nodes().append(node)
        if position is not None:
            pos=[position.x(),position.y()]
        else:
            # No explicit drop point (toolbar "Add Node…"): pack into the
            # nearest free grid slot instead of leaving it for _rebuild_scene
            # to place by list index, which drifts further down every time a
            # node is added and can land far below the visible nodes.
            pos=self._free_position()
        self._data.setdefault("node_positions",{})[node_id]=pos
        self._commit()
        item=self.node_items.get(node_id)
        if item is not None:
            self.centerOn(item.pos()+QPointF(_NODE_SIZE/2,_NODE_SIZE/2))
        return True

    def _prompt_new_node(self):
        """Ask for the two things a node needs to be recognizable at a
        glance in the graph; everything else (rank cost, rewards, exact
        prerequisites) is edited afterward in the list view, where it
        already has a proper table instead of a cramped dialog."""
        from PySide6.QtWidgets import QDialog,QDialogButtonBox,QLineEdit

        dialog=QDialog(self)
        dialog.setWindowTitle("Add Skill Node")
        form=QFormLayout(dialog)
        name_edit=QLineEdit()
        name_edit.setPlaceholderText("e.g. Fireball")
        icon_combo=QComboBox()
        icon_combo.setIconSize(QSize(20,20))
        for icon_name in _NODE_ICON_NAMES:
            builder,color=_ICON_BY_NAME[icon_name]
            icon_combo.addItem(QIcon(_render_icon_pixmap(builder,color)),icon_name.title(),icon_name)
        form.addRow("Name",name_edit)
        form.addRow("Icon",icon_combo)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        name_edit.setFocus()
        if dialog.exec()!=QDialog.Accepted:return None
        name=name_edit.text().strip()
        if not name:return None
        return name,icon_combo.currentData()

    def start_add_node(self,position=None):
        result=self._prompt_new_node()
        if result is None:return False
        name,icon_name=result
        return self.add_node(position,display_name=name,icon_name=icon_name)

    def _node_id_at(self,view_pos):
        item=self.itemAt(view_pos)
        while item is not None:
            for node_id,frame in self.node_items.items():
                if item is frame:return node_id
            item=item.parentItem()
        return None

    def _edge_at(self,view_pos):
        return self._edge_map.get(id(self.itemAt(view_pos)))

    def add_prerequisite(self,source_id,target_id):
        """Draw-a-connection equivalent of typing a Prerequisites row."""
        if self._data is None or source_id==target_id:return False
        nodes=self._nodes()
        target=next((n for n in nodes if n["node_id"]==target_id),None)
        if target is None or not any(n["node_id"]==source_id for n in nodes):
            return False
        existing={r.get("node_id") for r in (target.get("prerequisites") or [])}
        existing|={r.get("node_id") for r in (target.get("any_prerequisites") or [])}
        if source_id in existing:return False
        target.setdefault("prerequisites",[]).append({"node_id":source_id,"minimum_rank":1})
        self._commit()
        return True

    def remove_prerequisite(self,source_id,target_id):
        if self._data is None:return False
        target=next((n for n in self._nodes() if n["node_id"]==target_id),None)
        if target is None:return False
        changed=False
        for field in ("prerequisites","any_prerequisites"):
            before=target.get(field) or []
            after=[r for r in before if r.get("node_id")!=source_id]
            if len(after)!=len(before):
                target[field]=after;changed=True
        if changed:self._commit()
        return changed

    def duplicate_selected_nodes(self):
        if self._data is None:return False
        selected=self.selected_node_ids()
        if not selected:return False
        nodes=self._nodes()
        for node_id in selected:
            source=next((n for n in nodes if n["node_id"]==node_id),None)
            if source is None:continue
            copy=deepcopy(source)
            copy["node_id"]=self._unique_node_id(f"{node_id}_copy")
            copy["display_name"]=copy["node_id"]
            nodes.append(copy)
            origin=self.node_items.get(node_id)
            if origin is not None:
                self._data.setdefault("node_positions",{})[copy["node_id"]]=[
                    origin.pos().x()+_NODE_COLUMN_SPACING,origin.pos().y(),
                ]
        self._commit()
        return True

    def delete_selected_nodes(self,*,confirm=True):
        if self._data is None:return False
        selected=set(self.selected_node_ids())
        if not selected:return False
        if confirm:
            from PySide6.QtWidgets import QMessageBox

            names=[
                str(node.get("display_name") or node["node_id"])
                for node in self._nodes() if node["node_id"] in selected
            ]
            listed=", ".join(names[:4])+("…" if len(names)>4 else "")
            answer=QMessageBox.question(
                self,"Delete Skill Node",
                f"Delete {len(selected)} node(s)?\n\n{listed}\n\n"
                "Connections that point at them are removed too. "
                "This can be undone with Edit ▸ Undo.",
                QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel,
            )
            if answer!=QMessageBox.Yes:return False
        nodes=self._nodes()
        remaining=[node for node in nodes if node["node_id"] not in selected]
        # A prerequisite pointing at a deleted node would fail validation.
        for node in remaining:
            for field in ("prerequisites","any_prerequisites"):
                node[field]=[
                    req for req in node.get(field,[]) if req.get("node_id") not in selected
                ]
        nodes[:]=remaining
        self._commit()
        return True

    def contextMenuEvent(self,event):
        if self._data is None:return
        from PySide6.QtWidgets import QMenu
        edge=self._edge_at(event.pos())
        menu=QMenu(self)
        if edge is not None:
            remove_edge=menu.addAction("Remove Connection")
            if menu.exec(event.globalPos()) is remove_edge:
                self.remove_prerequisite(*edge)
            return
        add=menu.addAction("Add Node…")
        duplicate=menu.addAction("Duplicate Selected")
        delete=menu.addAction("Delete Selected")
        has_selection=bool(self.selected_node_ids())
        duplicate.setEnabled(has_selection)
        delete.setEnabled(has_selection)
        chosen=menu.exec(event.globalPos())
        if chosen is add:
            self.start_add_node(self.mapToScene(event.pos()))
        elif chosen is duplicate:
            self.duplicate_selected_nodes()
        elif chosen is delete:
            self.delete_selected_nodes()

    def mousePressEvent(self,event):
        if self._connect_mode and event.button()==Qt.LeftButton:
            node_id=self._node_id_at(event.pos())
            if node_id is None:
                self._clear_connect_pending();self._update_hint_text()
            elif self._connect_pending_source is None:
                self._connect_pending_source=node_id
                self.scene_graph.clearSelection()
                self.node_items[node_id].setSelected(True)
                self._update_hint_text()
            elif node_id==self._connect_pending_source:
                self._clear_connect_pending();self._update_hint_text()
            else:
                self.add_prerequisite(self._connect_pending_source,node_id)
                self._connect_pending_source=None
                self._update_hint_text()
            event.accept()
            return
        if event.button()==Qt.LeftButton and event.modifiers()&Qt.ShiftModifier:
            node_id=self._node_id_at(event.pos())
            if node_id is not None:
                self._link_source_id=node_id
                center=self.node_items[node_id].pos()+QPointF(_NODE_SIZE/2,_NODE_SIZE/2)
                self._link_preview=self.scene_graph.addLine(
                    center.x(),center.y(),center.x(),center.y(),
                    QPen(_GRAPH_NODE_BORDER_SELECTED,2,Qt.DashLine),
                )
                self._link_preview.setZValue(10)
                event.accept()
                return
        if event.button()==Qt.LeftButton:
            # Snapshot so the release can tell an actual drag from a click and
            # only then write (one undo step for the whole move, not one per
            # pixel of mouse travel).
            self._drag_positions=self.positions()
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._link_source_id is not None and self._link_preview is not None:
            start_item=self.node_items.get(self._link_source_id)
            if start_item is not None:
                start=start_item.pos()+QPointF(_NODE_SIZE/2,_NODE_SIZE/2)
                end=self.mapToScene(event.pos())
                self._link_preview.setLine(start.x(),start.y(),end.x(),end.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._link_source_id is not None:
            source_id=self._link_source_id
            # Remove the preview line before hit-testing for the drop target:
            # it sits above every node (zValue 10) and its own endpoint sits
            # exactly on the cursor, so itemAt() would find the line itself
            # instead of the node underneath it.
            if self._link_preview is not None:
                self.scene_graph.removeItem(self._link_preview)
            self._link_preview=None
            self._link_source_id=None
            target_id=self._node_id_at(event.pos())
            if target_id is not None and target_id!=source_id:
                self.add_prerequisite(source_id,target_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._clear_align_guides()
        before=self._drag_positions
        self._drag_positions=None
        if before is not None and self.positions()!=before:
            # A node actually moved — persist the new layout through the
            # adapter so it survives a refresh and lands on the undo stack.
            self._commit()

    def keyPressEvent(self,event):
        # Deliberately no Delete/Ctrl+D/Ctrl+N shortcuts here: on a canvas
        # this is one stray keypress away from silently destroying part of a
        # tree. Those actions live on the toolbar, where they are visible and
        # deletion asks first. Escape is safe — it only cancels.
        if event.key()==Qt.Key_Escape and self._connect_pending_source is not None:
            self._clear_connect_pending();self._update_hint_text();return
        super().keyPressEvent(event)

    def _default_position(self,index,count=1):
        """Grid slot for a node with no saved position yet, with the block
        centred on the canvas — a brand-new tree's auto-created root should
        land in the middle of the view, not tucked into the top-left corner.

        Floors the viewport size because the first build can run before this
        view has been laid out, and a position picked then is what gets
        saved the first time the tree is edited."""
        columns=min(max(1,count),_NEW_NODE_COLUMNS)
        rows=max(1,(max(1,count)+_NEW_NODE_COLUMNS-1)//_NEW_NODE_COLUMNS)
        block_w=(columns-1)*_NODE_COLUMN_SPACING+_NODE_SIZE
        block_h=(rows-1)*_NODE_ROW_SPACING+_NODE_SIZE
        origin_x=_CANVAS_WIDTH/2-block_w/2
        origin_y=_CANVAS_HEIGHT/2-block_h/2
        column=index%_NEW_NODE_COLUMNS
        row=index//_NEW_NODE_COLUMNS
        return [
            float(origin_x+column*_NODE_COLUMN_SPACING),
            float(origin_y+row*_NODE_ROW_SPACING),
        ]

    def _free_position(self):
        """First open slot in the packing grid, anchored to the existing
        nodes' own top-left corner rather than the scene's absolute origin.
        Nodes get dragged around by hand, so their saved positions are rarely
        grid-aligned — anchoring at (0,0) meant the collision check almost
        never matched them, and every new node landed at literal (0,0)
        regardless of where the author had actually moved the tree to."""
        positions=list((self._data.get("node_positions") or {}).values())
        if positions:
            origin_x=min(x for x,y in positions)
            origin_y=min(y for x,y in positions)
        else:
            origin_x=origin_y=0.0
        taken={(round(x),round(y)) for x,y in positions}
        index=0
        while True:
            column=index%_NEW_NODE_COLUMNS
            row=index//_NEW_NODE_COLUMNS
            candidate=[
                origin_x+float(column*_NODE_COLUMN_SPACING),
                origin_y+float(row*_NODE_ROW_SPACING),
            ]
            if (round(candidate[0]),round(candidate[1])) not in taken:
                return candidate
            index+=1

    def set_graph_data(self,data):
        self._data=data
        self._building=True
        try:
            self._rebuild_scene(data)
        finally:
            self._building=False

    def _rebuild_scene(self,data):
        self.scene_graph.clear(); self.node_items={}; self._edge_map={}
        self._edge_items=[]
        # scene_graph.clear() just deleted these at the C++ level — drop the
        # dangling Python references instead of letting a later drag call
        # _clear_align_guides() on an object that no longer exists.
        self._align_guide_v=None; self._align_guide_h=None
        self.name_label.hide()
        # QGraphicsItem (unlike QWidget) is not a QObject, so PySide6 does not
        # keep a child alive on Python's behalf just because it has a C++
        # parent — an unreferenced loop-local decoration item gets garbage
        # collected (and vanishes from the scene) as soon as the loop moves
        # on. Keep an explicit list so they actually stay on screen.
        self._node_decorations=[]
        if not data:return
        positions=dict(data.get("node_positions") or {})
        nodes=data.get("nodes",[])
        # A node with no recorded position gets one now and keeps it, rather
        # than being re-placed by a layout pass on every edit.
        for index,node in enumerate(nodes):
            node_id=node["node_id"]
            if node_id not in positions:
                positions[node_id]=self._default_position(index,len(nodes))
            x,y=positions[node_id]
            frame_path=QPainterPath()
            frame_path.addRoundedRect(QRectF(0,0,_NODE_SIZE,_NODE_SIZE),7.0,7.0)
            frame=_GraphNodeItem(frame_path,node_id,self)
            gradient=QLinearGradient(0,0,0,_NODE_SIZE)
            gradient.setColorAt(0.0,_GRAPH_NODE_FILL_TOP)
            gradient.setColorAt(1.0,_GRAPH_NODE_FILL_BOTTOM)
            frame.setBrush(QBrush(gradient))
            frame.setPen(QPen(_GRAPH_NODE_BORDER,2))
            frame.setPos(float(x),float(y))
            frame.setToolTip(str(node.get("display_name") or node_id))
            self.scene_graph.addItem(frame)

            builder,icon_color=_icon_for(node)
            icon_rect=QRectF(
                _NODE_ICON_INSET,_NODE_ICON_INSET,
                _NODE_SIZE-2*_NODE_ICON_INSET,_NODE_SIZE-2*_NODE_ICON_INSET,
            )
            icon=QGraphicsPathItem(builder(icon_rect),frame)
            icon.setBrush(QBrush(icon_color))
            icon.setPen(QPen(icon_color.darker(170),1))
            self._node_decorations.append(icon)

            # Always shown, the way a talent tree shows how many points a
            # talent can take — a "1" is information too, not noise.
            max_rank=max(1,int(node.get("max_rank",1) or 1))
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

            self.node_items[node_id]=frame
        data["node_positions"]=positions
        self._refresh_edges()
        if data.get("graph_id")!=self._centered_graph_id:
            # Different tree: start its canvas size over rather than
            # inheriting however far the previous tree's nodes reached.
            self._scene_rect=None
        self._update_scene_rect()
        # Scroll to the tree when a different one is opened, so nodes placed
        # far from the origin aren't off-screen. Deliberately not on every
        # rebuild: re-centring mid-edit would yank the canvas while dragging.
        graph_id=data.get("graph_id")
        if graph_id!=self._centered_graph_id:
            self._centered_graph_id=graph_id
            bounds=self.scene_graph.itemsBoundingRect()
            if not bounds.isNull():
                self.centerOn(bounds.center())

    def _snap_position(self,item,proposed):
        """PowerPoint-style smart guides: while dragging, pull the node onto
        another node's left edge or top edge once it's within a few pixels,
        independently on each axis, and show a dashed guide line for
        whichever axis is currently snapped."""
        x,y=proposed.x(),proposed.y()
        snap_x=snap_y=None
        for node_id,other in self.node_items.items():
            if other is item:continue
            ox,oy=other.pos().x(),other.pos().y()
            if snap_x is None and abs(x-ox)<=_ALIGN_SNAP_DISTANCE:snap_x=ox
            if snap_y is None and abs(y-oy)<=_ALIGN_SNAP_DISTANCE:snap_y=oy
            if snap_x is not None and snap_y is not None:break
        self._set_align_guide("v",snap_x+_NODE_SIZE/2 if snap_x is not None else None)
        self._set_align_guide("h",snap_y+_NODE_SIZE/2 if snap_y is not None else None)
        return QPointF(snap_x if snap_x is not None else x,snap_y if snap_y is not None else y)

    def _set_align_guide(self,axis,center):
        attr="_align_guide_v" if axis=="v" else "_align_guide_h"
        existing=getattr(self,attr)
        if center is None:
            if existing is not None:
                self.scene_graph.removeItem(existing)
                setattr(self,attr,None)
            return
        bounds=self.scene_graph.itemsBoundingRect().adjusted(-120,-120,120,120)
        pen=QPen(_GRAPH_NODE_BORDER_SELECTED,1,Qt.DashLine)
        if axis=="v":
            line=(center,bounds.top(),center,bounds.bottom())
        else:
            line=(bounds.left(),center,bounds.right(),center)
        if existing is None:
            existing=self.scene_graph.addLine(*line,pen)
            existing.setZValue(9)
            setattr(self,attr,existing)
        else:
            existing.setLine(*line)

    def _clear_align_guides(self):
        self._set_align_guide("v",None)
        self._set_align_guide("h",None)

    def _node_moved(self):
        """A node was dragged — redraw its connections so they follow it."""
        if not self._building:
            # Edges only: NOT _update_scene_rect(). Recomputing the scene
            # rect on every pixel of a live drag moves the rect's own
            # top-left origin as the dragged node's bounding box shifts,
            # which shifts the view's scroll offset out from under it —
            # every *other* node then visibly slides the opposite way on
            # screen even though its own scene position never changed. The
            # rect gets its next real recompute from _rebuild_scene once the
            # drag ends and the move is committed.
            self._refresh_edges()

    def _update_scene_rect(self):
        """Fixed logical canvas, grown only to fit nodes dragged past it.

        Two things depend on this staying still. A scene rect smaller than
        the viewport is *centred* in it by QGraphicsView, so a rect sized to
        the items alone would follow the one node a single-node tree has and
        re-centre it on every rebuild — the node then refuses to appear
        anywhere but the middle no matter where it is dropped. And a rect
        derived from the viewport changes size with the layout, which moves
        the scroll offset out from under whatever is being dragged."""
        bounds=self.scene_graph.itemsBoundingRect().adjusted(
            -_CANVAS_MARGIN,-_CANVAS_MARGIN,_CANVAS_MARGIN,_CANVAS_MARGIN,
        )
        rect=bounds.united(QRectF(0.0,0.0,_CANVAS_WIDTH,_CANVAS_HEIGHT))
        self._scene_rect=rect
        self.scene_graph.setSceneRect(rect)

    def _refresh_edges(self):
        for item in self._edge_items:
            if item.scene() is self.scene_graph:
                self.scene_graph.removeItem(item)
        self._edge_items=[]
        self._edge_map={}
        pen=QPen(_GRAPH_LINE,2)
        arrows=self.edge_arrows()
        style=self.edge_style()
        for node in self._nodes():
            target=self.node_items.get(node["node_id"])
            if target is None:continue
            for req in list(node.get("prerequisites") or [])+list(node.get("any_prerequisites") or []):
                source=self.node_items.get(req.get("node_id"))
                if source is not None:
                    self._add_connector(
                        source,target,pen,req["node_id"],node["node_id"],style,arrows,
                    )

    def _add_connector(self,source,target,pen,source_id,target_id,style,arrows):
        # Anchor on the node's own geometry rather than sceneBoundingRect(),
        # which the corner rank badge would inflate.
        sx=source.pos().x()+_NODE_SIZE/2; sy=source.pos().y()+_NODE_SIZE
        tx=target.pos().x()+_NODE_SIZE/2; ty=target.pos().y()
        if style=="diagonal":
            # Centre to centre, so the line reads as a direct link even when
            # the two nodes sit side by side rather than one above the other.
            sy=source.pos().y()+_NODE_SIZE/2
            ty=target.pos().y()+_NODE_SIZE/2
        path=QPainterPath(QPointF(sx,sy))
        if style=="elbow" and abs(sx-tx)>=0.5:
            mid=sy+(ty-sy)/2
            path.lineTo(sx,mid); path.lineTo(tx,mid); path.lineTo(tx,ty)
        else:
            path.lineTo(tx,ty)
        edge=self.scene_graph.addPath(path,pen)
        edge.setZValue(-1)
        edge.setCursor(Qt.PointingHandCursor)
        self._edge_items.append(edge)
        self._edge_map[id(edge)]=(source_id,target_id)
        if arrows:
            a=_NODE_ARROW_SIZE
            head=QPolygonF([QPointF(tx,ty),QPointF(tx-a,ty-a*1.4),QPointF(tx+a,ty-a*1.4)])
            arrow=self.scene_graph.addPolygon(head,QPen(_GRAPH_LINE,1),QBrush(_GRAPH_LINE))
            arrow.setZValue(-1)
            self._edge_items.append(arrow)
            self._edge_map[id(arrow)]=(source_id,target_id)

    def positions(self):
        return {key:[item.pos().x(),item.pos().y()] for key,item in self.node_items.items()}

_CURVE_COLORS = (
    "#6fb1e0", "#e0a15c", "#7fd48f", "#e07f9a", "#c9a3e0", "#e0d95c",
)


class ProgressionCurveChart(QWidget):
    """Read-only stat-vs-rank preview for a ProgressionTrackDefinition.

    Milestones only grant a bonus once their required_total is reached, so
    each stat's value is the running sum of every milestone's bonus up to
    and including that rank — the same rule ActorDefinition.effective_stats
    applies at runtime (asteria/rpg/actors.py: _progression_contributions).
    This widget only visualizes that; it never edits the record.
    """

    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._series = {}
        self._ranks = ()
        self.setMinimumHeight(150)

    def set_milestones(self, milestones):
        ranks = sorted({int(m.get("rank", 0)) for m in milestones})
        totals = {}
        for stat in sorted(
            {stat for m in milestones for stat in (m.get("stat_bonuses") or {})}
        ):
            running = 0.0
            points = []
            for rank in ranks:
                for m in milestones:
                    if int(m.get("rank", 0)) == rank:
                        running += float((m.get("stat_bonuses") or {}).get(stat, 0.0))
                points.append(running)
            totals[stat] = points
        self._ranks = tuple(ranks)
        self._series = totals
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1b1e23"))
        if not self._ranks or not self._series:
            painter.setPen(QColor("#6b7280"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No stat growth defined yet")
            painter.end()
            return

        left, top, right, bottom_legend = 44, 14, 14, 22
        legend_h = 20
        plot = QRectF(
            left, top + legend_h, self.width() - left - right,
            self.height() - top - legend_h - bottom_legend,
        )
        max_value = max((max(points, default=0.0) for points in self._series.values()), default=0.0)
        max_value = max(max_value, 1.0)

        painter.setPen(QColor("#292e36"))
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - fraction * plot.height()
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor("#7a828e"))
            painter.drawText(
                QRectF(0, y - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter,
                f"{max_value * fraction:.0f}",
            )
            painter.setPen(QColor("#292e36"))

        def point_at(index, value):
            x = plot.left() if len(self._ranks) == 1 else (
                plot.left() + plot.width() * index / (len(self._ranks) - 1)
            )
            y = plot.bottom() - plot.height() * (value / max_value)
            return QPointF(x, y)

        painter.setPen(QColor("#7a828e"))
        for index, rank in enumerate(self._ranks):
            x = point_at(index, 0).x()
            painter.drawText(
                QRectF(x - 20, plot.bottom() + 4, 40, bottom_legend),
                Qt.AlignCenter, str(rank),
            )

        legend_x = left
        for stat_index, (stat, points) in enumerate(sorted(self._series.items())):
            color = QColor(_CURVE_COLORS[stat_index % len(_CURVE_COLORS)])
            path = QPainterPath()
            for index, value in enumerate(points):
                p = point_at(index, value)
                path.moveTo(p) if index == 0 else path.lineTo(p)
            painter.setPen(QPen(color, 2))
            painter.drawPath(path)
            for index, value in enumerate(points):
                painter.setBrush(QBrush(color))
                p = point_at(index, value)
                painter.drawEllipse(p, 2.5, 2.5)

            painter.setPen(color)
            label_width = painter.fontMetrics().horizontalAdvance(stat) + 22
            painter.drawLine(
                QPointF(legend_x, top + legend_h / 2), QPointF(legend_x + 14, top + legend_h / 2)
            )
            painter.drawText(
                QRectF(legend_x + 18, top, label_width, legend_h),
                Qt.AlignVCenter | Qt.AlignLeft, stat,
            )
            legend_x += label_width
        painter.end()


def _sprite_sheet_records(document):
    if document is None or document.project is None:
        return ()
    return tuple(r for r in document.project.assets.records() if r.kind == "sprite_sheet")


class AdapterFamilyWidget(QWidget):
    """Qt authoring surface over a set of AuthoringCategoryAdapter objects."""

    if QT_AVAILABLE:
        changed=Signal()
        # Emitted when project asset files change, so the shell can re-resolve
        # resources and drop cached texture pixels for a path it already read.
        assetsChanged=Signal()

    def __init__(self,title,adapters,parent=None,*,document=None):
        if not QT_AVAILABLE: raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title=str(title)
        self.document=document
        self._texture_cache=QtTextureCache()
        self.adapters={x.category_id:x for x in adapters}
        self._ids=[]
        # Tracks which graph record Connect mode was last synced against, so
        # a refresh cycle that re-fires _selection_changed for the *same*
        # tree (any edit — add/duplicate/delete a node — triggers one) does
        # not stop a run of connect-mode clicks the user is still mid-way
        # through. Only an actual switch to a different tree should do that.
        self._connect_mode_key=None

        header=QHBoxLayout()
        # Heading names whatever the list below actually holds, not the
        # workspace family: browsing Items under the Character workspace read
        # "Character" over a list of items.
        self.heading=QLabel(self.title); self.heading.setObjectName("SectionLabel")
        self.category=QComboBox()
        for adapter in adapters:self.category.addItem(adapter.label,adapter.category_id)
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.heading); header.addStretch(1); header.addWidget(self.category)

        self.browser=QListWidget()
        self.browser.currentRowChanged.connect(self._selection_changed)
        # scrollable=False: this editor is one of several panels stacked on
        # one page (appearance/class-design panel above it, empty-state hint
        # above that). They share a single QScrollArea below instead of each
        # owning its own — a second independent scroll region nested inside
        # the page's only starved every panel of height and forced each
        # table into its own internal scrollbar instead of just showing its
        # rows.
        self.editor=TypedRecordEditor(scrollable=False)
        self.editor.changed.connect(self._refresh_curve_preview)
        self.curve_chart=ProgressionCurveChart()
        self.curve_chart.setVisible(False)
        self.appearance_panel=self._build_appearance_panel()
        self.appearance_panel.setVisible(False)
        self.class_panel=ClassDesignPanel(self.adapters)
        self.class_panel.setVisible(False)
        self.class_panel.changed.connect(self._class_design_changed)
        self.empty_hint=QLabel("")
        self.empty_hint.setObjectName("MutedLabel")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setWordWrap(True)
        self.editor_page=QWidget()
        editor_page_layout=QVBoxLayout(self.editor_page)
        editor_page_layout.setContentsMargins(0,0,0,0)
        self.editor_page_scroll=editor_page_scroll=QScrollArea()
        editor_page_scroll.setWidgetResizable(True)
        editor_page_scroll.setFrameShape(QFrame.NoFrame)
        editor_page_content=QWidget()
        editor_page_content.setObjectName("RecordForm")
        editor_page_content_layout=QVBoxLayout(editor_page_content)
        editor_page_content_layout.addWidget(self.empty_hint)
        editor_page_content_layout.addWidget(self.curve_chart)
        editor_page_content_layout.addWidget(self.appearance_panel)
        editor_page_content_layout.addWidget(self.class_panel)
        editor_page_content_layout.addWidget(self.editor)
        editor_page_scroll.setWidget(editor_page_content)
        editor_page_layout.addWidget(editor_page_scroll)
        self._syncing_graph_controls=False
        self.graph_view=SkillTreeGraphView()
        self.graph_view.graphEdited.connect(self._graph_edited)
        self.graph_page=self._build_graph_page()
        self.detail_stack=QStackedWidget(); self.detail_stack.addWidget(self.editor_page); self.detail_stack.addWidget(self.graph_page)
        split=QSplitter(); split.addWidget(self.browser); split.addWidget(self.detail_stack)
        split.setStyleSheet(_SPLITTER_STYLE)
        split.setStretchFactor(1,1)
        # The list only ever holds record ids, so it does not need half the
        # width — the editor beside it does. Still draggable from here.
        split.setSizes([_BROWSER_WIDTH,_BROWSER_WIDTH*4])

        actions=QHBoxLayout()
        self.view_button=QPushButton("Graph View")
        self.view_button.clicked.connect(self.toggle_skill_tree_view)
        self.save_layout_button=QPushButton("Save Graph Layout")
        self.save_layout_button.clicked.connect(self.save_graph_layout)
        self.reset_layout_button=QPushButton("Reset Layout")
        self.reset_layout_button.clicked.connect(self.reset_graph_layout)
        self.new_button=QPushButton("New…")
        self.duplicate_button=QPushButton("Duplicate…")
        self.apply_button=QPushButton("Apply Changes")
        self.delete_button=QPushButton("Delete")
        self.new_button.clicked.connect(self.create_record)
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        actions.addWidget(self.view_button); actions.addWidget(self.save_layout_button)
        actions.addWidget(self.reset_layout_button); actions.addStretch(1)
        actions.addWidget(self.new_button); actions.addWidget(self.duplicate_button)
        actions.addWidget(self.apply_button); actions.addWidget(self.delete_button)

        layout=QVBoxLayout(self)
        layout.addLayout(header); layout.addWidget(split,1); layout.addLayout(actions)
        self.refresh()

    def _build_graph_page(self):
        """Graph canvas plus an explicit action column beside it.

        Right-click and Shift+drag both still work, but neither is a gesture
        a first-time user would discover on their own — this puts the same
        actions as visible buttons next to the canvas, per the request to
        make the graph-editing controls obvious rather than hidden.
        """
        page=QWidget()
        layout=QHBoxLayout(page)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.graph_view,1)

        toolbar=QWidget()
        toolbar.setObjectName("RecordFieldGroup")
        toolbar_layout=QVBoxLayout(toolbar)
        toolbar_label=QLabel("Skill Tree")
        toolbar_label.setObjectName("RecordFieldLabel")
        self.graph_add_button=QPushButton("Add Node…")
        self.graph_add_button.clicked.connect(lambda:self.graph_view.start_add_node())
        self.graph_duplicate_button=QPushButton("Duplicate")
        self.graph_duplicate_button.clicked.connect(self.graph_view.duplicate_selected_nodes)
        self.graph_delete_button=QPushButton("Delete")
        self.graph_delete_button.clicked.connect(self.graph_view.delete_selected_nodes)
        self.graph_connect_button=QPushButton("Connect")
        self.graph_connect_button.setCheckable(True)
        self.graph_connect_button.setToolTip(
            "Click a prerequisite skill, then the skill that needs it. "
            "The connection is written into that skill's Prerequisites row."
        )
        self.graph_connect_button.toggled.connect(self.graph_view.set_connect_mode)
        connect_hint=QLabel("Click the skill learned first, then the one it unlocks.")
        connect_hint.setObjectName("MutedLabel")
        connect_hint.setWordWrap(True)

        style_label=QLabel("Connections")
        style_label.setObjectName("RecordFieldLabel")
        self.graph_style_combo=QComboBox()
        for style,label in (
            ("elbow","Branching"),("straight","Straight"),("diagonal","Diagonal"),
        ):
            self.graph_style_combo.addItem(label,style)
        self.graph_style_combo.currentIndexChanged.connect(self._graph_style_changed)
        self.graph_arrow_checkbox=QCheckBox("Arrow heads")
        self.graph_arrow_checkbox.setChecked(True)
        self.graph_arrow_checkbox.toggled.connect(self._graph_arrows_changed)

        for widget in (
            toolbar_label,self.graph_add_button,self.graph_duplicate_button,
            self.graph_delete_button,self.graph_connect_button,connect_hint,
            style_label,self.graph_style_combo,self.graph_arrow_checkbox,
        ):
            toolbar_layout.addWidget(widget)
        toolbar_layout.addStretch(1)
        toolbar.setFixedWidth(150)
        layout.addWidget(toolbar)
        return page

    def _graph_style_changed(self):
        if self._syncing_graph_controls:return
        self.graph_view.set_edge_style(self.graph_style_combo.currentData())

    def _graph_arrows_changed(self,checked):
        if self._syncing_graph_controls:return
        self.graph_view.set_edge_arrows(checked)

    def _sync_graph_controls(self):
        """Mirror the selected graph's own stored style onto the controls
        without the resulting signals writing it straight back."""
        self._syncing_graph_controls=True
        try:
            index=self.graph_style_combo.findData(self.graph_view.edge_style())
            if index>=0:self.graph_style_combo.setCurrentIndex(index)
            self.graph_arrow_checkbox.setChecked(self.graph_view.edge_arrows())
        finally:
            self._syncing_graph_controls=False

    def _set_graph_controls_enabled(self,enabled):
        for widget in (
            self.graph_add_button,self.graph_duplicate_button,self.graph_delete_button,
            self.graph_connect_button,self.graph_style_combo,self.graph_arrow_checkbox,
        ):
            widget.setEnabled(enabled)

    def _build_appearance_panel(self):
        """Image-first appearance block: what the Actor looks like, shown as a
        picture, next to the controls that change it."""
        panel=QGroupBox("Appearance")
        panel.setObjectName("RecordFieldGroup")
        row=QHBoxLayout(panel)

        self.appearance_preview=QLabel()
        self.appearance_preview.setObjectName("ActorPreview")
        self.appearance_preview.setFixedSize(80,110)
        self.appearance_preview.setAlignment(Qt.AlignCenter)
        row.addWidget(self.appearance_preview)

        controls=QWidget()
        form=QFormLayout(controls)
        # Left-aligned so the sprite preview beside it keeps its place: the
        # macOS style otherwise centres the form in the whole panel width.
        form.setFormAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.appearance_sheet_combo=QComboBox()
        self.appearance_sheet_combo.setIconSize(_PREVIEW_ICON_SIZE)
        self.appearance_frame_spin=QSpinBox()
        self.appearance_frame_spin.setRange(0,999)
        self.appearance_flip_checkbox=QCheckBox("Flip Horizontally")
        for signal in (
            self.appearance_sheet_combo.currentIndexChanged,
            self.appearance_frame_spin.valueChanged,
            self.appearance_flip_checkbox.toggled,
        ):
            signal.connect(self._refresh_preview)
        self.appearance_apply_button=QPushButton("Apply to Map")
        self.appearance_apply_button.clicked.connect(self._apply_appearance)
        self.appearance_generate_button=QPushButton("Generate Character…")
        self.appearance_generate_button.setToolTip(
            "Draw a sprite for this Actor and use it on the map."
        )
        self.appearance_generate_button.clicked.connect(self._generate_appearance)
        self.appearance_hint=QLabel("")
        self.appearance_hint.setObjectName("MutedLabel")
        self.appearance_hint.setWordWrap(True)
        buttons=QHBoxLayout()
        buttons.setContentsMargins(0,0,0,0)
        buttons.addWidget(self.appearance_generate_button)
        buttons.addWidget(self.appearance_apply_button)
        form.addRow("Sprite Sheet",self.appearance_sheet_combo)
        form.addRow("Frame",self.appearance_frame_spin)
        form.addRow("",self.appearance_flip_checkbox)
        form.addRow("",buttons)
        form.addRow("",self.appearance_hint)
        row.addWidget(controls,1)
        return panel

    def _frame_image(self,sheet_asset_id,frame_index):
        """Pixels for one sprite-sheet frame, or None when unavailable."""
        if self.document is None or self.document.project is None:return None
        from .resource_resolver import asset_source_path
        try:
            sheet=self.document.asset_views.sprite_sheet(sheet_asset_id)
            if sheet is None or not sheet.frames:return None
            frame=sheet.frames[min(max(0,frame_index),len(sheet.frames)-1)]
            record=self.document.project.assets.get(sheet.texture.asset_id)
            path=asset_source_path(self.document,record) if record else None
            image=self._texture_cache.get(path) if path else None
            if image is None or image.isNull():return None
            return image.copy(QRect(int(frame.x),int(frame.y),int(frame.width),int(frame.height)))
        except Exception:
            return None

    def _refresh_preview(self):
        sheet_id=self.appearance_sheet_combo.currentData()
        image=self._frame_image(sheet_id,self.appearance_frame_spin.value()) if sheet_id else None
        if image is None:
            self.appearance_preview.setPixmap(QPixmap())
            self.appearance_preview.setText("no sprite")
            return
        if self.appearance_flip_checkbox.isChecked():
            image=image.mirrored(True,False)
        self.appearance_preview.setText("")
        self.appearance_preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.appearance_preview.width()-8,self.appearance_preview.height()-8,
            Qt.KeepAspectRatio,Qt.FastTransformation,
        ))

    def _generate_appearance(self):
        actor_id=self.selected_id
        if actor_id is None or self.document is None:return False
        from PySide6.QtWidgets import QMessageBox
        from .character_generator import generate_actor_appearance
        try:
            sheet_id=generate_actor_appearance(self.document,actor_id)
        except Exception as exc:
            QMessageBox.warning(self,"Generate Character",str(exc))
            return False
        self._texture_cache.clear()
        self.assetsChanged.emit()
        self.changed.emit()
        self._refresh_appearance_panel()
        index=self.appearance_sheet_combo.findData(sheet_id)
        if index>=0:self.appearance_sheet_combo.setCurrentIndex(index)
        self._refresh_preview()
        return True

    def _refresh_appearance_panel(self):
        actor_id=self.selected_id
        sheets=_sprite_sheet_records(self.document)
        self.appearance_sheet_combo.blockSignals(True)
        self.appearance_sheet_combo.clear()
        for record in sheets:
            image=self._frame_image(record.id,0)
            icon=QIcon(QPixmap.fromImage(image)) if image is not None else QIcon()
            self.appearance_sheet_combo.addItem(icon,record.name,record.id)
        self.appearance_sheet_combo.blockSignals(False)
        usable=self.document is not None and self.document.project is not None
        from .actor_appearance import get_actor_appearance
        stored=get_actor_appearance(self.document,actor_id) if usable and actor_id else None
        if stored is not None:
            index=self.appearance_sheet_combo.findData(stored.sprite_sheet_asset_id)
            self.appearance_sheet_combo.setCurrentIndex(max(0,index))
            self.appearance_frame_spin.setValue(stored.frame_index)
            self.appearance_flip_checkbox.setChecked(stored.flip_x)
        else:
            self.appearance_frame_spin.setValue(0)
            self.appearance_flip_checkbox.setChecked(False)
        self.appearance_hint.setText(
            "" if sheets else "No sprite sheets yet — press Generate Character to draw one."
        )
        self.appearance_apply_button.setEnabled(usable and bool(sheets) and actor_id is not None)
        self.appearance_generate_button.setEnabled(usable and actor_id is not None)
        self._refresh_preview()

    def _apply_appearance(self):
        actor_id=self.selected_id
        if actor_id is None or self.document is None:return False
        sheet_id=self.appearance_sheet_combo.currentData()
        if sheet_id is None:return False
        from .actor_appearance import apply_actor_appearance
        from .storage import EditorStorageError
        try:
            apply_actor_appearance(
                self.document,actor_id,sheet_id,
                self.appearance_frame_spin.value(),
                self.appearance_flip_checkbox.isChecked(),
            )
        except EditorStorageError as exc:
            self.appearance_hint.setText(str(exc))
            return False
        self.appearance_hint.setText("Applied to every linked map entity.")
        self.changed.emit()
        return True

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
        # Refresh runs after any project change, including ones triggered from
        # this panel; losing the selected record each time would move the form
        # out from under whoever is editing it.
        previous=self.selected_id
        self.heading.setText(adapter.label if adapter is not None else self.title)
        self.browser.clear(); self.editor.clear(); self._ids=[]
        if adapter is None:return
        self._ids=list(adapter.ids())
        self.browser.addItems(self._ids)
        self.new_button.setEnabled(adapter.create is not None)
        self.duplicate_button.setEnabled(adapter.duplicate is not None and bool(self._ids))
        self.apply_button.setEnabled(bool(self._ids))
        self.delete_button.setEnabled(bool(self._ids))
        self.empty_hint.setVisible(not self._ids)
        self.empty_hint.setText(
            f"No {adapter.label} defined yet — press “New…” to add one."
            if adapter.create is not None
            else f"No {adapter.label} defined yet."
        )
        is_graph=self.category_id=="graphs"
        self.view_button.setVisible(is_graph); self.save_layout_button.setVisible(is_graph)
        self.reset_layout_button.setVisible(is_graph)
        # Graph editing needs a skill tree to edit: without one the canvas has
        # nothing to draw and every button would fail silently.
        self.view_button.setEnabled(bool(self._ids))
        self.save_layout_button.setEnabled(bool(self._ids))
        self.reset_layout_button.setEnabled(bool(self._ids))
        self._set_graph_controls_enabled(is_graph and bool(self._ids))
        if not is_graph and self.graph_connect_button.isChecked():
            self.graph_connect_button.setChecked(False)
        self.curve_chart.setVisible(self.category_id=="tracks")
        self.appearance_panel.setVisible(self.category_id=="units")
        self.class_panel.setVisible(self.category_id=="classes")
        if not is_graph:self.detail_stack.setCurrentWidget(self.editor_page)
        if self._ids:
            self.browser.setCurrentRow(
                self._ids.index(previous) if previous in self._ids else 0
            )
        elif self.category_id=="units":self._refresh_appearance_panel()

    def _id_catalog(self):
        """Ids per family, so reference fields can be picked instead of typed."""
        catalog={cid:tuple(adapter.ids()) for cid,adapter in self.adapters.items()}
        project=getattr(self.document,"project",None)
        db=getattr(project,"rpg_database",None)
        stats=set(); resources=set()
        if db is not None:
            for actor in db.actors.values():
                stats.update(actor.base_stats); resources.update(actor.base_resources)
            for unit in db.enemies.values():
                stats.update(unit.stats); resources.update(unit.resources)
            for definition in db.classes.values():
                stats.update(definition.stat_bonuses); resources.update(definition.resource_bonuses)
            for track in db.progression_tracks.values():
                for milestone in track.milestones:
                    stats.update(milestone.stat_bonuses)
        catalog["stats"]=tuple(sorted(stats))
        catalog["resources"]=tuple(sorted(resources))
        return catalog

    def create_record(self):
        """Add an empty record so a category that starts out empty is usable."""
        adapter=self.adapter
        if adapter is None or adapter.create is None:return False
        from PySide6.QtWidgets import QInputDialog,QMessageBox
        value,ok=QInputDialog.getText(self,f"New {adapter.label}","Id:")
        value=str(value).strip()
        if not ok or not value:return False
        try:
            adapter.create(value)
        except Exception as exc:
            QMessageBox.warning(self,f"New {adapter.label}",str(exc))
            return False
        self.changed.emit(); self.refresh()
        if value in self._ids:self.browser.setCurrentRow(self._ids.index(value))
        return True

    def _selection_changed(self,row):
        key=self.selected_id
        if key is None:
            self.editor.clear()
            if self.category_id=="tracks":self.curve_chart.set_milestones(())
            elif self.category_id=="units":self._refresh_appearance_panel()
            return
        # Opening a record must start at its left edge. Rebuilding the form
        # hands focus to one of its child widgets, and a QScrollArea scrolls
        # sideways to reveal whatever has focus — which pushes the leftmost
        # column (the Appearance heading and its sprite) out of view. Queued
        # rather than immediate because that focus scroll happens *after*
        # this slot returns; setting it here would simply be overridden.
        QTimer.singleShot(0,self._reset_page_scroll)
        data=self.adapter.encode(self.adapter.get(key))
        primary=next(
            (field for field,value in data.items()
             if field.endswith("_id") and value==key),
            None,
        )
        self.editor.set_catalog(self._id_catalog())
        self.editor.set_record(data,primary_key=primary)
        if self.category_id=="graphs":
            # A pending "click the skill learned first" gesture, or Connect
            # mode itself, belongs to the tree it was started in. Carrying
            # it into a *different* tree means clicking a node there tries
            # to complete/start a link instead of dragging it — which looks
            # exactly like "the node won't move" with no visible
            # explanation, especially in a tree with only one node and
            # nothing to connect to. But this slot also re-fires for the
            # *same* tree on every edit (add/duplicate/delete a node all
            # trigger a refresh), so only reset when the selected tree
            # itself actually changed — otherwise a user mid-way through
            # clicking several connections in a row gets interrupted after
            # every single click.
            if key!=self._connect_mode_key and self.graph_connect_button.isChecked():
                self.graph_connect_button.setChecked(False)
            self._connect_mode_key=key
            self.graph_view._clear_connect_pending()
            self.graph_view.set_graph_data(data)
            self._sync_graph_controls()
            if data.get("editor_view")=="graph":self.detail_stack.setCurrentWidget(self.graph_page)
        elif self.category_id=="tracks":
            self.curve_chart.set_milestones(data.get("milestones") or ())
        elif self.category_id=="units":
            self._refresh_appearance_panel()
        elif self.category_id=="classes":
            self.class_panel.set_class(key)

    def _reset_page_scroll(self):
        bar=self.editor_page_scroll.horizontalScrollBar()
        if bar is not None:bar.setValue(0)

    def _refresh_curve_preview(self):
        if self.category_id!="tracks" or self.selected_id is None:return
        self.curve_chart.set_milestones(self.editor.record().get("milestones") or ())

    def toggle_skill_tree_view(self):
        if self.category_id!="graphs":return False
        graph=self.detail_stack.currentWidget() is self.graph_page
        # `editor_page` is the actual page registered with detail_stack — the
        # raw `self.editor` widget lives nested inside it and was never added
        # to the stack directly, so setCurrentWidget(self.editor) silently did
        # nothing and "List / Data View" could never switch back off graph view.
        self.detail_stack.setCurrentWidget(self.editor_page if graph else self.graph_page)
        self.view_button.setText("Graph View" if graph else "List / Data View")
        return True

    def _class_design_changed(self):
        self.changed.emit()
        current=self.selected_id
        self.refresh()
        if current in self._ids:self.browser.setCurrentRow(self._ids.index(current))

    def _graph_edited(self):
        """Persist a node added/duplicated/deleted straight from the graph."""
        key=self.selected_id
        if self.category_id!="graphs" or key is None:return False
        from PySide6.QtWidgets import QMessageBox
        data=self.graph_view._data
        try:
            self.adapter.edit(key,self.adapter.decode(data))
        except Exception as exc:
            # The canvas must never keep showing something the database
            # refused: re-render from the stored record instead, or the node
            # (or connection) looks like it was added and then silently
            # vanishes on the next refresh.
            QMessageBox.warning(self,"Skill Tree",str(exc))
            stored=self.adapter.encode(self.adapter.get(key))
            self.graph_view.set_graph_data(stored)
            self.editor.set_record(stored,primary_key="graph_id")
            return False
        self.changed.emit()
        self.editor.set_record(data,primary_key="graph_id")
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
        self.detail_stack.setCurrentWidget(self.graph_page)
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
        assetsChanged=Signal()

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
            document=getattr(getattr(self.builder,"__self__",None),"document",None)
            self.child=AdapterFamilyWidget(self.title,self.builder(),document=document)
            self.child.changed.connect(self.changed.emit)
            self.child.assetsChanged.connect(self.assetsChanged.emit)
        self.layout.addWidget(self.child)
