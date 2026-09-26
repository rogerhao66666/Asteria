"""Optional PySide6 shell. No canonical state lives here."""
try:
 from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QLabel,QStackedWidget
except Exception: QWidget=None

if QWidget:
 class PresentationWorkspace(QWidget):
  def __init__(self,model,parent=None):
   super().__init__(parent);self.model=model
   root=QVBoxLayout(self);top=QHBoxLayout()
   self.search=QLineEdit();self.search.setPlaceholderText("Search presentation…")
   self.hierarchy=QPushButton("Hierarchy");self.timeline=QPushButton("Timeline")
   top.addWidget(self.search);top.addWidget(self.hierarchy);top.addWidget(self.timeline);root.addLayout(top)
   self.body=QStackedWidget();self.body.addWidget(QLabel("Hierarchy authoring view"));self.body.addWidget(QLabel("Timeline authoring view"));root.addWidget(self.body)
   self.status=QLabel("Ready");root.addWidget(self.status)
   self.hierarchy.clicked.connect(lambda:self._mode("hierarchy",0))
   self.timeline.clicked.connect(lambda:self._mode("timeline",1))
   self.search.textChanged.connect(lambda q:self.model.search(q))
  def _mode(self,name,index):self.model.set_mode(name);self.body.setCurrentIndex(index)
else:
 class PresentationWorkspace:
  def __init__(self,*a,**k):raise RuntimeError("PySide6 unavailable")
