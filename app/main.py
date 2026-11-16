import sys, os, json, tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.gui import Window

def main():
    app=QApplication(sys.argv); app.setApplicationName('CHESS BOOK ARENA'); app.setOrganizationName('ChessBookArena')
    data=None
    if '--self-test' in sys.argv:data=tempfile.mkdtemp(prefix='arena-smoke-')
    w=Window(data); w.show()
    if '--self-test' in sys.argv:
        from app.verification import fixtures
        from app.catalog import discover
        import chess
        fixtures(Path(data))
        paths=discover(data)
        w.import_paths([str(p) for p in paths if p.suffix=='.pgn'])
        phase=[0]; ticks=[0]
        def smoke():
            ticks[0]+=1
            try:
                if ticks[0]>200: raise RuntimeError('Packaged acceptance timeout')
                if w.busy:return
                if phase[0]==0:
                    assert len(paths)>=6
                    w.sid=w.catalog.sources()[0]['id']; assert w.catalog.sources()[0]['status']=='ready'
                    w.refresh_library(); w.select_source(); w.mode.setCurrentIndex(0); w.human=True; w.active=True; w.forced_result=None
                    w.human_move(chess.Move.from_uci('f2f3')); phase[0]=1
                elif phase[0]==1:
                    assert w.board.board.peek().uci()=='e7e5'
                    assert w.origins[-1].startswith('database')
                    w.human_move(chess.Move.from_uci('g2g4')); phase[0]=2
                else:
                    assert w.board.board.is_checkmate()
                    trace=list(w.origins); w.save(); assert w.catalog.saves()
                    pgn=w.catalog.saves()[0]['pgn']; w.load_pgn(pgn); w.board.board=w.replay_boards[-1].copy(); assert w.board.board.is_checkmate(); w.refresh()
                    result={'status':'PASS','checks':['folder discovery','background PGN import','library selection','legal human moves','sourced database replies','checkmate','save','reload PGN','rendered desktop'],'origins':trace,'result':w.board.board.result(),'packaged':bool(getattr(sys,'frozen',False))}
                    out=Path(sys.argv[sys.argv.index('--self-test')+1]); w.grab().save(str(out.with_suffix('.png'))); out.write_text(json.dumps(result,indent=2)); timer.stop(); app.exit(0)
            except Exception as e:
                Path(sys.argv[sys.argv.index('--self-test')+1]).write_text(json.dumps({'error':str(e)})); timer.stop(); app.exit(1)
        timer=QTimer(); timer.timeout.connect(smoke); timer.start(150)
    return app.exec()
if __name__=='__main__':sys.exit(main())
