import sys,os,json,tempfile,time,io
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.gui import Window

def main():
    app=QApplication(sys.argv);app.setApplicationName('CHESS BOOK ARENA');app.setOrganizationName('ChessBookArena')
    testing='--self-test' in sys.argv or '--reopen-test' in sys.argv
    flag='--reopen-test' if '--reopen-test' in sys.argv else '--self-test'
    data=(sys.argv[sys.argv.index('--acceptance-data')+1] if '--acceptance-data' in sys.argv else tempfile.mkdtemp(prefix='arena-smoke-')) if testing else None
    w=Window(data);w.show()
    if testing:
        import chess,chess.pgn
        from app.catalog import discover
        from app.verification import fixtures
        from app.engine_manager import EngineRegistry
        out=Path(sys.argv[sys.argv.index(flag)+1]);phase=[0];ticks=[0];begin=time.perf_counter()
        external=os.environ.get('CBA_ACCEPTANCE_DATABASE')
        bundled=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'examples'/'native-fixture'/'arena-fixture.cbh'
        source=Path(external) if external else bundled
        if flag=='--self-test':
            fixtures(Path(data));paths=discover(source.parent)
            def prepare():
                sid=w.catalog.open_native(source)
                if not w.catalog.native_info(sid):raise ValueError('Native source failed to open')
                w.catalog.index_native(sid,1000 if external else 2,progress=lambda n:w.bus.progress.emit(f'Native record {n}'))
                if not w.engines.profiles:
                    for candidate in w.engines.candidates():
                        try:w.engines.add(candidate);break
                        except Exception:continue
            w.job(prepare)
        def done(result):
            w.grab().save(str(out.with_suffix('.png')));out.write_text(json.dumps(result,indent=2));timer.stop();app.exit(0)
        def smoke():
            ticks[0]+=1
            try:
                if ticks[0]>3000:raise RuntimeError('Packaged acceptance timeout')
                if w.busy:return
                if flag=='--reopen-test':
                    rows=w.catalog.saves();assert rows
                    w.load_pgn(rows[0]['pgn']);w.board.board=w.replay_boards[-1].copy();assert w.board.board.move_stack;w.refresh()
                    return done(dict(status='PASS',checks=['second process reopened persistent catalog','saved game PGN reloaded and replayed'],plies=len(w.board.board.move_stack),packaged=bool(getattr(sys,'frozen',False))))
                if phase[0]==0:
                    w.sid=w.catalog.sources()[0]['id'];assert w.catalog.sources()[0]['status'] not in ['error','UNSUPPORTED']
                    w.refresh_library();w.select_source();w.mode.setCurrentIndex(0);w.human=True;w.active=True;w.forced_result=None
                    w.human_move(chess.Move.from_uci('e2e4' if external else 'f2f3'));phase[0]=1
                elif phase[0]==1:
                    assert len(w.board.board.move_stack)==2 and w.origins[-1].startswith('database')
                    if external:
                        candidates=w.catalog.candidates(w.sid,w.board.board);assert candidates
                        move=chess.Move.from_uci(candidates[0]['uci'])
                    else:move=chess.Move.from_uci('g2g4')
                    w.human_move(move);phase[0]=2
                else:
                    assert len(w.board.board.move_stack)==4 and w.origins[-1].startswith('database')
                    if not external:assert w.board.board.is_checkmate()
                    w.save();assert w.catalog.saves();state=w.catalog.native_info(w.sid);info=json.loads(state['info'])
                    candidates=w.catalog.candidates(w.sid,w.board.board.root());engines=[p.name for p in w.engines.candidates()]
                    result=dict(status='PASS',checks=['grouped native folder discovery','native metadata and real game count','background native indexing','library selection','legal human moves','historical sourced replies','save','rendered desktop'],backend=info['backend'],eligible_games=info['games'],indexed_games=w.catalog.sources()[0]['games'],plies=4,origins=w.origins,initial_candidate_count=len(candidates),seconds=time.perf_counter()-begin,engine_candidates=engines,packaged=bool(getattr(sys,'frozen',False)),real_database=bool(external))
                    if external:w.source_info.setText(f"CBH reference collection • {info['games']:,} eligible records\nStatistics: indexed subset only\nBackend: cbvault 0.1.7");w.library.currentItem().setText(0,'CBH reference collection / partial index')
                    from app.engine_manager_gui import EngineManagerDialog
                    manager=EngineManagerDialog(w.engines,w);manager.show();app.processEvents();manager.grab().save(str(out.with_name(out.stem+'-engine-manager.png')));manager.accept()
                    result['verified_uci_engines']=[dict(name=p['name'],status=p['status']) for p in w.engines.profiles]
                    done(result)
            except Exception as e:
                out.write_text(json.dumps(dict(status='FAIL',error=str(e))));timer.stop();app.exit(1)
        timer=QTimer();timer.timeout.connect(smoke);timer.start(150)
    return app.exec()
if __name__=='__main__':sys.exit(main())
