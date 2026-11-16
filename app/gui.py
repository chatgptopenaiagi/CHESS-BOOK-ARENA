import io, json, os, sys, threading
from pathlib import Path
import chess, chess.pgn, chess.svg
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import *
from app.catalog import Catalog, discover, FORMATS
from app.opponents import *

class Bus(QObject):
    done=Signal(object); error=Signal(str); progress=Signal(str)
class BoardWidget(QWidget):
    moved=Signal(object)
    def __init__(self):
        super().__init__(); self.board=chess.Board(); self.selected=None; self.flipped=False; self.setMinimumSize(360,360)
    def paintEvent(self,e):
        arrows=[]
        squares={m.to_square:'#baca44aa' for m in self.board.legal_moves if m.from_square==self.selected}
        svg=chess.svg.board(self.board,flipped=self.flipped,size=min(self.width(),self.height()),lastmove=self.board.peek() if self.board.move_stack else None,check=self.board.king(self.board.turn) if self.board.is_check() else None,squares=squares)
        p=QPainter(self); side=min(self.width(),self.height()); QSvgRenderer(svg.encode()).render(p, __import__('PySide6.QtCore',fromlist=['QRectF']).QRectF(0,0,side,side))
    def square(self,event):
        side=min(self.width(),self.height()); x=event.position().x()*400/side; y=event.position().y()*400/side
        col=int((x-20)/45); row=int((y-20)/45)
        if not(20<=x<380 and 20<=y<380): return None
        return chess.square(7-col if self.flipped else col,row if self.flipped else 7-row)
    def mousePressEvent(self,e):
        sq=self.square(e)
        if sq is None: return
        if self.selected is not None and self.attempt(self.selected,sq): return
        piece=self.board.piece_at(sq)
        self.selected=sq if piece and piece.color==self.board.turn else None; self.update()
    def mouseReleaseEvent(self,e):
        sq=self.square(e)
        if self.selected is not None and sq is not None and sq!=self.selected: self.attempt(self.selected,sq)
    def attempt(self,a,b):
        moves=[m for m in self.board.legal_moves if m.from_square==a and m.to_square==b]
        if not moves: return False
        m=moves[0]
        if len(moves)>1:
            name,ok=QInputDialog.getItem(self,'Promotion','Promote to',['Queen','Rook','Bishop','Knight'],0,False)
            if not ok: return False
            m=chess.Move(a,b,promotion={'Queen':chess.QUEEN,'Rook':chess.ROOK,'Bishop':chess.BISHOP,'Knight':chess.KNIGHT}[name])
        self.selected=None; self.moved.emit(m); self.update(); return True

class Window(QMainWindow):
    MODES=['Human vs historical database','Human vs opening book','Historical player repertoire simulation','Human vs Stockfish','Human vs book + engine','Opening book exploration','Database game replay','Position training','Human vs human local']
    def __init__(self,data=None):
        super().__init__(); self.setWindowTitle('CHESS BOOK ARENA • 0.1.0'); self.resize(1450,950)
        self.data=Path(data or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'ChessBookArena'); self.data.mkdir(parents=True,exist_ok=True)
        self.catalog=Catalog(self.data/'catalog.sqlite'); self.settings_path=self.data/'settings.json'
        try: self.settings=json.loads(self.settings_path.read_text())
        except Exception: self.settings={}
        self.sid=None; self.origins=[]; self.active=False; self.busy=False; self.cancel=threading.Event(); self.generation=0; self.workers=[]; self.replay_boards=[]
        self.bus=Bus(); self.bus.done.connect(self.finished); self.bus.error.connect(self.failure); self.bus.progress.connect(lambda s:self.statusBar().showMessage(s))
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        title=QLabel('CHESS BOOK ARENA     /     YOUR KNOWLEDGE. YOUR OPPONENT.'); title.setStyleSheet('font-size:21px;color:#e2bc75;padding:14px'); outer.addWidget(title)
        split=QSplitter(); outer.addWidget(split,1)
        left=QWidget(); l=QVBoxLayout(left); split.addWidget(left); l.addWidget(QLabel('DATABASE LIBRARY'))
        self.search=QLineEdit(); self.search.setPlaceholderText('Filter library'); self.search.textChanged.connect(self.refresh_library); l.addWidget(self.search)
        self.library=QTreeWidget(); self.library.setHeaderLabels(['Source / status','Games','Format']); self.library.itemSelectionChanged.connect(self.select_source); l.addWidget(self.library)
        for label,func in [('Import files',self.import_files),('Scan folder',self.scan_folder),('Index selected / resume',self.index_selected),('Cancel indexing',lambda:self.cancel.set())]: self.button(l,label,func)
        row=QHBoxLayout(); l.addLayout(row)
        for label,func in [('Play',self.library_play),('Explore',lambda:self.mode.setCurrentIndex(5))]: self.button(row,label,func)
        self.source_info=QLabel(); self.source_info.setWordWrap(True); l.addWidget(self.source_info)
        self.button(l,'Browse imported positions',self.browse_positions)
        self.button(l,'Format compatibility',self.compatibility)
        center=QWidget(); cl=QVBoxLayout(center); split.addWidget(center)
        self.board=BoardWidget(); self.board.moved.connect(self.human_move); cl.addWidget(self.board,1)
        nav=QHBoxLayout(); cl.addLayout(nav)
        for label,func in [('Flip',self.flip),('Undo',self.undo),('Replay ◀',lambda:self.navigate(-1)),('Replay ▶',lambda:self.navigate(1))]: self.button(nav,label,func)
        self.state=QLabel('Ready — import a database or start local chess'); cl.addWidget(self.state)
        right=QWidget(); r=QVBoxLayout(right); split.addWidget(right); r.addWidget(QLabel('OPPONENT & POSITION COVERAGE'))
        self.mode=QComboBox(); self.mode.addItems(self.MODES); r.addWidget(self.mode)
        self.color=QComboBox(); self.color.addItems(['Play White','Play Black']); r.addWidget(self.color)
        self.strategy=QComboBox(); self.strategy.addItems(['Frequency','Performance','Weighted random','Exploration','Engine assisted']); r.addWidget(self.strategy)
        self.player=QComboBox(); self.player.setEditable(True); self.player.setInsertPolicy(QComboBox.NoInsert); r.addWidget(self.player)
        self.fallback=QComboBox(); self.fallback.addItems(['Stop','Engine','Alternate','Return to earlier position']); r.addWidget(QLabel('When repertoire ends')); r.addWidget(self.fallback)
        self.alternate=QComboBox(); r.addWidget(self.alternate)
        self.button(r,'Start selected mode',self.start)
        self.button(r,'Continue from current position',self.continue_game)
        self.candidates=QTreeWidget(); self.candidates.setHeaderLabels(['Move','Count / weight','%','W / D / L']); self.candidates.itemDoubleClicked.connect(self.explore_move); r.addWidget(self.candidates)
        self.source_label=QLabel('Move source: —'); self.source_label.setWordWrap(True); r.addWidget(self.source_label)
        self.button(r,'Compare coverage across library',self.compare)
        self.button(r,'Configure / verify UCI engine',self.engine_dialog)
        self.button(r,'Analyze position',self.analyze)
        self.evaluation=QPlainTextEdit(); self.evaluation.setReadOnly(True); self.evaluation.setMaximumHeight(140); r.addWidget(self.evaluation)
        split.setSizes([310,640,420])
        bottom=QTabWidget(); outer.addWidget(bottom)
        game=QWidget(); gl=QVBoxLayout(game); self.history=QListWidget(); self.history.setMaximumHeight(120); gl.addWidget(self.history)
        controls=QHBoxLayout(); gl.addLayout(controls)
        for label,func in [('Save game',self.save),('Resume saved',self.resume),('Export PGN',self.export),('Resign',self.resign),('Claim draw',self.claim),('Offer draw',self.offer_draw),('Load FEN / EPD position',self.load_position)]: self.button(controls,label,func)
        bottom.addTab(game,'Moves & game history')
        browser=QWidget(); bl=QVBoxLayout(browser); filters=QHBoxLayout(); bl.addLayout(filters)
        self.query=QLineEdit(); self.query.setPlaceholderText('Player, event, ECO, opening'); filters.addWidget(self.query)
        self.year=QLineEdit(); self.year.setPlaceholderText('Year'); filters.addWidget(self.year)
        self.result=QComboBox(); self.result.addItems(['','1-0','0-1','1/2-1/2','*']); filters.addWidget(self.result)
        self.position_filter=QCheckBox('Current position'); filters.addWidget(self.position_filter); self.button(filters,'Search',self.search_games); self.button(filters,'Export selected',self.export_selected); self.button(filters,'Browse variations',self.variations)
        self.game_list=QListWidget(); self.game_list.setMaximumHeight(100); self.game_list.itemDoubleClicked.connect(self.replay_game); bl.addWidget(self.game_list); bottom.addTab(browser,'Historical game explorer')
        self.setStyleSheet('QWidget{background:#16212b;color:#e2e8ed;font-family:Segoe UI;font-size:12px} QTreeWidget,QListWidget,QLineEdit,QPlainTextEdit,QComboBox{background:#202f3c;border:1px solid #3b4d5b;padding:5px} QPushButton{background:#304858;border:1px solid #51677a;padding:7px;border-radius:4px} QPushButton:hover{background:#456575} QHeaderView::section{background:#304858;padding:5px} QTabBar::tab{padding:8px;background:#304858}')
        self.engine_path=self.settings.get('engine',discover_engine()); self.engine_opts=self.settings.get('engine_opts',{})
        self.clock=QTimer(self); self.clock.timeout.connect(self.tick); self.clock.start(1000); self.remaining=[0,0]; self.clock_enabled=False
        self.refresh_library(); self.refresh()
    def button(self,layout,label,func):
        b=QPushButton(label); b.clicked.connect(func); layout.addWidget(b); return b
    def failure(self,s): self.mode.setEnabled(True); self.library.setEnabled(True); self.busy=False; self.active=False; self.statusBar().showMessage(s); QMessageBox.warning(self,'Operation stopped',s)
    def job(self,fn):
        if self.busy: return
        self.busy=True; self.mode.setEnabled(False); self.library.setEnabled(False)
        def work():
            try: self.bus.done.emit(fn())
            except Exception as e: self.bus.error.emit(str(e))
        t=threading.Thread(target=work,daemon=True); self.workers.append(t); t.start()
    def finished(self,result):
        self.busy=False; self.mode.setEnabled(True); self.library.setEnabled(True)
        if isinstance(result,Decision):
            if getattr(self,'forced_result',None):return
            if result.move:
                if result.move not in self.board.board.legal_moves: return self.failure('Rejected illegal or stale opponent move')
                self.push(result.move,result.origin+' • '+result.reason)
            else:
                self.active=False; self.state.setText('REPERTOIRE ENDED — '+result.reason); QMessageBox.information(self,'Coverage ended',result.reason+'\nUndo to return to an earlier position, or choose a configured engine fallback.')
        elif isinstance(result,list): self.evaluation.setPlainText('\n'.join(result))
        else: self.refresh_library(); self.refresh(); self.statusBar().showMessage('Import finished; inspect source status for errors')
    def refresh_library(self):
        selected=self.sid; self.library.blockSignals(True); self.library.clear(); self.alternate.clear()
        for s in self.catalog.sources():
            self.alternate.addItem(Path(s['path']).name,s['id'])
            if self.search.text().lower() not in s['path'].lower(): continue
            item=QTreeWidgetItem([Path(s['path']).name+'\n'+s['status'],str(s['games']),s['format']]); item.setData(0,Qt.UserRole,s); self.library.addTopLevelItem(item)
            if s['id']==selected: self.library.setCurrentItem(item)
        self.library.blockSignals(False)
    def select_source(self):
        item=self.library.currentItem()
        if not item:return
        s=item.data(0,Qt.UserRole); self.sid=s['id']; self.player.clear(); self.player.addItems(['']+self.catalog.players(self.sid))
        self.source_info.setText(f"{Path(s['path']).name}\n{s['size']:,} bytes • {FORMATS.get(s['format'],'UNSUPPORTED')}\n{s['error']}")
        with self.catalog.db() as c: coverage=c.execute('SELECT * FROM coverage WHERE source=?',(self.sid,)).fetchone()
        if coverage:self.source_info.setText(self.source_info.text()+f"\n{coverage['positions']:,} distinct positions • {coverage['entries']:,} move entries")
        self.refresh()
    def import_files(self):
        files,_=QFileDialog.getOpenFileNames(self,'Import chess data','','Chess data (*.pgn *.gz *.bin *.fen *.epd *.zip *.cbh *.ctg *.abk *.si4);;All files (*)')
        if files:self.import_paths(files)
    def import_paths(self,files):
        self.cancel.clear()
        def run():
            for f in files:
                if self.cancel.is_set():break
                self.catalog.import_file(f,self.cancel.is_set,lambda n:self.bus.progress.emit(f'{Path(f).name}: {n} games indexed'))
        self.job(run)
    def scan_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Select chess database folder',self.settings.get('folder',''))
        if not folder:return
        recursive=QMessageBox.question(self,'Folder discovery','Include subfolders?')==QMessageBox.Yes
        self.settings['folder']=folder
        def run():
            for p in discover(folder,recursive): self.catalog.register(p)
        self.job(run)
    def index_selected(self):
        if self.sid:
            s=next(x for x in self.catalog.sources() if x['id']==self.sid); self.import_paths([s['path']])
    def compatibility(self): QMessageBox.information(self,'Compatibility','\n'.join(f'{x}: {y}' for x,y in FORMATS.items())+'\nProprietary/Scid: export to PGN using the originating application. No converter integration is verified. ZIP reads PGN, PGN.GZ, FEN, EPD and BIN members. Books are extracted to the derived-data directory.')
    def browse_positions(self):
        with self.catalog.db() as c: rows=c.execute('SELECT fen,label FROM positions WHERE source=? LIMIT 1000',(self.sid,)).fetchall()
        if not rows:return QMessageBox.information(self,'Positions','No imported FEN/EPD positions for this source')
        text,ok=QInputDialog.getItem(self,'Imported positions','Select training position',[r['fen'] for r in rows],0,False)
        if ok and not self.busy:self.active=False; self.board.board=chess.Board(text); self.origins=[]; self.refresh()
    def engine(self): return Engine(self.engine_path,**self.engine_opts)
    def opponent(self):
        if self.mode.currentIndex()==3:return EngineOpponent(self.engine())
        cls=HistoricalPlayerOpponent if self.mode.currentIndex()==2 else OpeningBookOpponent if self.mode.currentIndex() in [1,4] else HistoricalDatabaseOpponent
        base=cls(self.catalog,self.sid,self.strategy.currentText(),self.player.currentText() if self.mode.currentIndex()==2 else '',self.engine())
        fallback='Engine' if self.mode.currentIndex()==4 else self.fallback.currentText()
        alt=HistoricalDatabaseOpponent(self.catalog,self.alternate.currentData(),self.strategy.currentText(),engine=self.engine()) if self.alternate.currentData()!=self.sid else None
        return HybridBookEngineOpponent(base,self.engine(),fallback,alt)
    def library_play(self):
        if self.busy:return
        source=next((s for s in self.catalog.sources() if s['id']==self.sid),None)
        if source:self.mode.setCurrentIndex(1 if source['format']=='.bin' else 0); self.start()
    def start(self):
        if self.busy:return
        idx=self.mode.currentIndex()
        if idx in [0,1,2,4,5] and not self.sid:return self.failure('Select an imported source first')
        if idx==2 and not self.player.currentText():return self.failure('Select a recorded player')
        self.active=idx<5; self.human=self.color.currentIndex()==0; self.board.board=chess.Board(); self.origins=[]; self.replay_boards=[]; self.forced_result=None
        if idx<5 or idx==8:
            minutes,ok=QInputDialog.getInt(self,'Game clock','Minutes per side (0 disables)',0,0,180)
            self.remaining=[minutes*60,minutes*60]; self.clock_enabled=ok and minutes>0
        self.refresh(); self.maybe_reply()
    def human_move(self,m):
        if self.busy or getattr(self,'forced_result',None):return
        if self.active and self.board.board.turn!=self.human:return
        if self.board.board.is_game_over():return
        self.push(m,'human' if self.active else 'exploration / local'); self.maybe_reply()
    def push(self,m,origin):
        self.board.board.push(m); self.origins.append(origin); self.source_label.setText('Move source: '+origin); self.refresh()
    def maybe_reply(self):
        if self.active and self.board.board.turn!=self.human and not self.board.board.is_game_over():
            b=self.board.board.copy(); opponent=self.opponent(); self.statusBar().showMessage('Computer thinking…'); self.job(lambda:opponent.choose(b))
    def refresh(self):
        b=self.board.board; self.board.update(); self.history.clear(); temp=b.root()
        for i,m in enumerate(b.move_stack):
            self.history.addItem(f'{i//2+1}{"." if temp.turn else "…"} {temp.san(m)}   [{self.origins[i] if i<len(self.origins) else "replay"}]'); temp.push(m)
        self.history.scrollToBottom(); outcome=b.outcome()
        self.state.setText(f'{"White" if b.turn else "Black"} to move'+(f' • {outcome.termination.name} {outcome.result()}' if outcome else ''))
        if outcome:self.active=False
        self.candidates.clear()
        if self.sid:
            try: rows=self.catalog.candidates(self.sid,b,self.player.currentText() if self.mode.currentIndex()==2 else '')
            except Exception as e: self.statusBar().showMessage(str(e)); return
            total=sum(r['n'] for r in rows)
            for r in rows:
                it=QTreeWidgetItem([b.san(chess.Move.from_uci(r['uci'])),str(r['n']),f'{100*r["n"]/max(1,total):.1f}',f'{r["w"]}/{r["d"]}/{r["l"]}']); it.setData(0,Qt.UserRole,r['uci']); self.candidates.addTopLevelItem(it)
    def explore_move(self,item):
        if not self.active and not self.busy:self.human_move(chess.Move.from_uci(item.data(0,Qt.UserRole)))
    def flip(self): self.board.flipped=not self.board.flipped; self.board.update()
    def undo(self):
        if self.busy:return
        self.active=False; self.forced_result=None
        if self.board.board.move_stack:self.board.board.pop(); self.origins=self.origins[:-1]
        self.refresh()
    def navigate(self,delta):
        if self.busy or not self.replay_boards:return
        self.replay_index=max(0,min(len(self.replay_boards)-1,self.replay_index+delta)); self.board.board=self.replay_boards[self.replay_index].copy(); self.refresh()
    def search_games(self):
        self.game_list.clear()
        for g in self.catalog.games(self.sid,self.query.text(),self.year.text(),self.result.currentText(),self.board.board if self.position_filter.isChecked() else None):
            h=json.loads(g['headers']); it=QListWidgetItem(' • '.join(h.get(k,'?') for k in ['White','Black','Event','Date','Result','ECO','Opening'])); it.setData(Qt.UserRole,g['pgn']); self.game_list.addItem(it)
    def export_selected(self):
        item=self.game_list.currentItem()
        if not item:return
        path,_=QFileDialog.getSaveFileName(self,'Export selected historical game','','PGN (*.pgn)')
        if path:Path(path).write_text(item.data(Qt.UserRole),encoding='utf-8')
    def variations(self):
        item=self.game_list.currentItem()
        if not item or self.busy:return
        game=chess.pgn.read_game(io.StringIO(item.data(Qt.UserRole)))
        d=QDialog(self); d.setWindowTitle('Historical game variations'); d.resize(600,650); layout=QVBoxLayout(d); tree=QTreeWidget(); tree.setHeaderLabels(['Move / variation','Annotation']); layout.addWidget(tree)
        def add(node,parent):
            for child in node.variations:
                it=QTreeWidgetItem([node.board().san(child.move),child.comment]); it.setData(0,Qt.UserRole,child.board().fen()); parent.addChild(it); add(child,it)
        add(game,tree.invisibleRootItem()); tree.expandToDepth(2)
        def selected(it):
            self.active=False; self.board.board=chess.Board(it.data(0,Qt.UserRole)); self.origins=[]; self.refresh()
        tree.itemDoubleClicked.connect(selected); d.exec()
    def continue_game(self):
        if self.busy or self.mode.currentIndex()>=5:return
        if self.mode.currentIndex()!=3 and not self.sid:return
        self.forced_result=None; self.human=self.color.currentIndex()==0; self.active=True; self.maybe_reply()
    def replay_game(self,item): self.load_pgn(item.data(Qt.UserRole))
    def load_pgn(self,pgn):
        if self.busy:return
        g=chess.pgn.read_game(io.StringIO(pgn)); b=g.board(); self.forced_result=None; self.active=False; self.replay_boards=[b.copy()]
        for m in g.mainline_moves():b.push(m); self.replay_boards.append(b.copy())
        self.replay_index=0; self.board.board=self.replay_boards[0].copy(); self.origins=[]; self.refresh()
        self.evaluation.setPlainText(str(g))
    def meta(self):return dict(mode=self.mode.currentText(),source=self.sid,player=self.player.currentText(),strategy=self.strategy.currentText(),color=self.color.currentText(),fallback=self.fallback.currentText(),origins=self.origins,time_control=self.remaining,result=getattr(self,'forced_result',None) or self.board.board.result())
    def save(self): self.catalog.save(self.board.board,self.meta()); self.statusBar().showMessage('Game saved')
    def resume(self):
        if self.busy:return
        rows=self.catalog.saves()
        if not rows:return
        label,ok=QInputDialog.getItem(self,'Resume saved game','Game',[f"{x['id']} • {x['date']} • {x['title']}" for x in rows],0,False)
        if not ok:return
        r=next(x for x in rows if x['id']==int(label.split(' • ')[0])); meta=json.loads(r['meta']); self.load_pgn(r['pgn']); self.board.board=self.replay_boards[-1].copy(); self.origins=meta.get('origins',[])
        self.mode.setCurrentText(meta.get('mode','')); self.sid=meta.get('source'); self.color.setCurrentText(meta.get('color','Play White')); self.strategy.setCurrentText(meta.get('strategy','Frequency')); self.fallback.setCurrentText(meta.get('fallback','Stop')); self.refresh_library(); self.select_source(); self.player.setCurrentText(meta.get('player','')); self.remaining=meta.get('time_control',[0,0]); self.human=self.color.currentIndex()==0; self.active=self.mode.currentIndex()<5 and meta.get('result','*')=='*'; self.refresh(); self.maybe_reply()
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Export current game','','PGN (*.pgn)')
        if path:
            gid=self.catalog.save(self.board.board,self.meta()); r=next(x for x in self.catalog.saves() if x['id']==gid); Path(path).write_text(r['pgn'],encoding='utf-8')
    def resign(self): self.active=False; self.forced_result='0-1' if self.color.currentIndex()==0 else '1-0'; self.state.setText('Resigned • '+self.forced_result)
    def claim(self):
        if self.board.board.can_claim_draw(): self.active=False; self.forced_result='1/2-1/2'; self.state.setText('Draw claimed')
        else:QMessageBox.information(self,'Draw claim','No legal repetition or fifty-move claim available')
    def offer_draw(self):
        if self.mode.currentIndex()!=8:return QMessageBox.information(self,'Draw offer','Database and engine opponents do not accept negotiated draws.')
        if QMessageBox.question(self,'Draw offer','Other player: accept draw?')==QMessageBox.Yes:self.active=False; self.forced_result='1/2-1/2'; self.state.setText('Draw agreed')
    def load_position(self):
        if self.busy:return
        text,ok=QInputDialog.getText(self,'Position training','FEN or EPD')
        if ok:
            try:
                b=chess.Board()
                try:b.set_fen(text)
                except ValueError:b.set_epd(text)
                if not b.is_valid():raise ValueError('Invalid position')
                self.active=False; self.board.board=b; self.origins=[]; self.refresh()
            except Exception as e:self.failure(str(e))
    def compare(self):
        lines=[]
        for s in self.catalog.sources():
            if s['status']!='ready':continue
            rows=self.catalog.candidates(s['id'],self.board.board); lines.append(Path(s['path']).name+': '+', '.join(f'{self.board.board.san(chess.Move.from_uci(r["uci"]))} ({r["n"]})' for r in rows))
        self.evaluation.setPlainText('\n'.join(lines))
    def engine_dialog(self):
        d=QDialog(self); d.setWindowTitle('UCI engine configuration'); form=QFormLayout(d); path=QLineEdit(self.engine_path); form.addRow('Executable',path)
        pick=QPushButton('Browse'); form.addRow(pick); pick.clicked.connect(lambda:path.setText(QFileDialog.getOpenFileName(d,'UCI executable','','Executables (*.exe)')[0]))
        widgets={}
        for k,v,lo,hi in [('seconds',.3,.05,60),('depth',16,1,99),('threads',1,1,64),('hash_mb',64,1,4096),('elo',0,0,4000),('multipv',3,1,20)]:
            w=QDoubleSpinBox() if k=='seconds' else QSpinBox(); w.setRange(lo,hi); w.setValue(self.engine_opts.get(k,v)); widgets[k]=w; form.addRow(k,w)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); form.addRow(buttons)
        if d.exec():
            self.engine_path=path.text(); self.engine_opts={k:w.value() for k,w in widgets.items()}
            def verify():
                with self.engine().open() as e:return [str(e.id), 'Supported UCI options: '+', '.join(e.options)]
            self.job(verify)
    def analyze(self):
        if self.board.board.is_game_over():return
        b=self.board.board.copy(); engine=self.engine()
        def run():
            out=[]
            for info in engine.analyse(b):
                temp=b.copy(); pv=[]
                for m in info.get('pv',[]):pv.append(temp.san(m)); temp.push(m)
                out.append(str(info.get('score'))+'  '+' '.join(pv))
            return out
        self.job(run)
    def tick(self):
        if self.clock_enabled and not getattr(self,'forced_result',None) and (self.active or self.mode.currentIndex()==8) and not self.board.board.is_game_over():
            i=0 if self.board.board.turn else 1; self.remaining[i]-=1
            self.statusBar().showMessage(f'Clock White {self.remaining[0]}s • Black {self.remaining[1]}s')
            if self.remaining[i]<=0:self.active=False; self.clock_enabled=False; self.forced_result='1/2-1/2' if self.board.board.has_insufficient_material(not self.board.board.turn) else ('0-1' if self.board.board.turn else '1-0'); self.state.setText('Time expired • '+self.forced_result)
    def closeEvent(self,e):
        if self.busy:
            self.cancel.set(); e.ignore(); self.statusBar().showMessage('Waiting for background work to finish; close again afterward'); return
        self.settings.update(engine=self.engine_path,engine_opts=self.engine_opts); self.settings_path.write_text(json.dumps(self.settings)); e.accept()
