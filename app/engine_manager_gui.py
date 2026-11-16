from PySide6.QtWidgets import *
from app.gui import Bus
import threading
from app.engine_manager import EngineRegistry,OFFICIAL
class EngineManagerDialog(QDialog):
    def __init__(self,registry,parent=None):
        super().__init__(parent);self.registry=registry;self.setWindowTitle('CHESS ENGINE MANAGER');self.resize(900,620);self.running=False;self.bus=Bus();self.bus.done.connect(self.on_done);self.bus.error.connect(self.failed)
        layout=QVBoxLayout(self);self.list=QTreeWidget();self.list.setHeaderLabels(['Profile / engine','Status','Author']);self.list.setColumnWidth(0,250);self.list.setColumnWidth(1,90);layout.addWidget(self.list)
        row=QHBoxLayout();layout.addLayout(row)
        for text,fn in [('Scan known locations',self.scan),('Scan selected folder',self.scan_folder),('Add local engine',self.add),('Verify engine',self.verify),('Configure profile',self.configure),('Select default',self.select),('Remove from application',self.remove)]:
            b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b)
        self.info=QPlainTextEdit();self.info.setReadOnly(True);layout.addWidget(self.info);self.list.itemSelectionChanged.connect(self.details)
        download=QHBoxLayout();layout.addLayout(download);self.official=QComboBox();self.official.addItems(OFFICIAL);download.addWidget(self.official)
        b=QPushButton('Search official GitHub releases');b.clicked.connect(self.search);download.addWidget(b);self.assets=QComboBox();download.addWidget(self.assets)
        b=QPushButton('Download selected asset');b.clicked.connect(self.download);download.addWidget(b)
        layout.addWidget(QLabel('Leela may require external neural-network weights and backend dependencies. GPU availability is not assumed.'))
        b=QPushButton('Done');b.clicked.connect(self.accept);layout.addWidget(b);self.refresh()
    def selected(self):
        it=self.list.currentItem();return it.data(0,256) if it else None
    def refresh(self):
        self.list.clear()
        for p in self.registry.profiles:
            it=QTreeWidgetItem([p['label']+(' [DEFAULT]' if p['id']==self.registry.data['default'] else ''),p['status'] if __import__('pathlib').Path(p['path']).is_file() else 'MISSING',p.get('author','')]);it.setData(0,256,p);self.list.addTopLevelItem(it)
    def run(self,fn):
        if self.running:return
        self.running=True;self.info.setPlainText('Working in background…')
        def work():
            try:self.bus.done.emit(fn())
            except Exception as e:self.bus.error.emit(str(e))
        threading.Thread(target=work,daemon=True).start()
    def on_done(self,r):
        self.running=False
        if isinstance(r,dict) and 'assets' in r:
            self.assets.clear()
            for a in r['assets']:self.assets.addItem(a['name']+f" ({a['size']/1024**2:.1f} MiB)",a)
        self.refresh();self.info.setPlainText(str(r))
    def failed(self,s):self.running=False;self.info.setPlainText('Operation failed: '+s)
    def scan(self,folders=()):
        if isinstance(folders,bool):folders=()
        def run():
            found=[]
            for p in self.registry.candidates(folders):
                if any(x['path']==str(p.resolve()) for x in self.registry.profiles):continue
                try:found.append(self.registry.add(p)['name'])
                except Exception as e:found.append(p.name+': '+str(e))
            return found
        self.run(run)
    def scan_folder(self):
        p=QFileDialog.getExistingDirectory(self,'Select trusted engine directory')
        if p:self.scan([p])
    def add(self):
        p,_=QFileDialog.getOpenFileName(self,'Select trusted UCI executable','','Windows executable (*.exe)')
        if p:self.run(lambda:self.registry.add(p)['name'])
    def verify(self):
        p=self.selected()
        if not p:return
        def run():
            p.update(self.registry.verify(p['path']));self.registry.save();return p['name']+' verified'
        self.run(run)
    def details(self):
        p=self.selected()
        if p:self.info.setPlainText(p['name']+'\n'+p['path']+'\nSupported options: '+', '.join(p['options']))
    def configure(self):
        p=self.selected()
        if not p or self.running:return
        d=QDialog(self);d.setWindowTitle('UCI profile options');outer=QVBoxLayout(d);scroll=QScrollArea();scroll.setWidgetResizable(True);widget=QWidget();form=QFormLayout(widget);scroll.setWidget(widget);outer.addWidget(scroll);label=QLineEdit(p['label']);form.addRow('Profile name',label);widgets={}
        for k,o in p['options'].items():
            if o['managed'] or o['type']=='button':continue
            val=p['settings'].get(k,o['default'])
            if o['type']=='spin':w=QSpinBox();w.setRange(max(-2147483647,o['min'] or 0),min(2147483647,o['max'] or 2147483647));w.setValue(val)
            elif o['type']=='check':w=QCheckBox();w.setChecked(bool(val))
            elif o['type']=='combo':w=QComboBox();w.addItems(o['var'] or []);w.setCurrentText(str(val))
            else:w=QLineEdit(str(val or ''))
            widgets[k]=w;form.addRow(k,w)
        sec=QDoubleSpinBox();sec.setRange(.01,120);sec.setValue(p['seconds']);form.addRow('Thinking seconds',sec)
        depth=QSpinBox();depth.setRange(1,99);depth.setValue(p['depth']);form.addRow('Depth limit',depth)
        pv=QSpinBox();pv.setRange(1,min(100,p['options'].get('MultiPV',{}).get('max') or 1));pv.setValue(p['multipv']);pv.setEnabled('MultiPV' in p['options']);form.addRow('MultiPV',pv)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);outer.addWidget(buttons);d.resize(650,650)
        if d.exec():
            p.update(label=label.text(),seconds=sec.value(),depth=depth.value(),multipv=pv.value(),settings={k:w.isChecked() if isinstance(w,QCheckBox) else w.value() if isinstance(w,QSpinBox) else w.currentText() if isinstance(w,QComboBox) else w.text() for k,w in widgets.items()});self.registry.save();self.refresh()
    def select(self):
        p=self.selected()
        if p:self.registry.data['default']=p['id'];self.registry.save();self.refresh()
    def remove(self):
        p=self.selected()
        if p and not self.running:self.registry.remove(p['id']);self.refresh()
    def search(self):self.run(lambda:dict(assets=self.registry.releases(self.official.currentText())))
    def download(self):
        asset=self.assets.currentData()
        if asset:
            def run():
                paths=self.registry.install(asset);return [self.registry.add(p)['name'] for p in paths]
            self.run(run)
    def closeEvent(self,e):
        if self.running:e.ignore();self.info.appendPlainText('Wait for the current engine operation to finish.')
        else:e.accept()
    def reject(self):
        if not self.running:super().reject()
    def accept(self):
        if not self.running:super().accept()
