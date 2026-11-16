import os,io,json,shutil,struct,time
from pathlib import Path
import chess,chess.pgn,pytest
from app.catalog import Catalog,discover
from app.database_readers.reader_registry import open_reader
from app.database_readers.format_detector import family,entrypoint
from app.database_readers.native_bridge import helper_path
from app.engine_manager import EngineRegistry,pe_arch
from app.opponents import HistoricalDatabaseOpponent,Engine

@pytest.fixture
def native(tmp_path):
    src=Path(__file__).parents[1]/'examples/native-fixture';target=tmp_path/'native';shutil.copytree(src,target)
    return target/'arena-fixture.cbh'
def test_native_companions(native):
    f=family(native);assert not f['missing'] and '.cbg' in [p.suffix for p in f['found']];assert entrypoint(native.with_suffix('.cbg'))==native
    assert discover(native.parent)==[native]
def test_incomplete(native):
    native.with_suffix('.cbg').unlink()
    assert '.cbg' in family(native)['missing']
    with pytest.raises(ValueError,match='Missing'):open_reader(native)
def test_real_decoding_and_framing(native):
    with open_reader(native) as r:
        info=r.metadata();assert info.records==2 and info.games==1
        with pytest.raises(ValueError,match='Text'):r.game(1)
        for _ in range(3):
            row=r.game(2);assert row['id']==2 and row['game'].end().board().is_checkmate();assert row['game'].comment=='Generated fixture comment'
        with pytest.raises(ValueError,match='out of range'):r.game(300)
def test_native_index_and_play(native,tmp_path):
    c=Catalog(tmp_path/'catalog.db');sid=c.open_native(native);c.index_native(sid,2);b=chess.Board();opp=HistoricalDatabaseOpponent(c,sid)
    for uci in ['f2f3','g2g4']:
        b.push_uci(uci);d=opp.choose(b);assert d.move in b.legal_moves and d.origin.startswith('database');b.push(d.move)
    assert b.is_checkmate();c.save(b,{'mode':'native database'});assert c.saves()
    with c.db() as conn:assert conn.execute('SELECT native_id FROM native_games').fetchone()[0]==2
    assert c.stats(sid)['entries']==4
    assert c.candidates(sid,chess.Board(),filters={'player':'absent'})==[]
    assert c.candidates(sid,chess.Board(),filters={'event':'Paris'})
def test_cancel_resume_native(native,tmp_path):
    c=Catalog(tmp_path/'catalog.db');sid=c.open_native(native);c.index_native(sid,2,cancel=lambda:True);assert c.sources()[0]['status']=='cancelled';c.index_native(sid,2);assert c.sources()[0]['games']==1
    c.index_native(sid,2);assert c.sources()[0]['games']==1

def test_companion_change(native,tmp_path):
    c=Catalog(tmp_path/'catalog.db');sid=c.open_native(native);c.index_native(sid,2);native.with_suffix('.cba').write_bytes(native.with_suffix('.cba').read_bytes()+b'x')
    with pytest.raises(ValueError,match='component changed'):c.candidates(sid,chess.Board())

def test_arena_abk(tmp_path):
    p=tmp_path/'generated.abk';data=bytearray(902*28)
    struct.pack_into('<BBBBIIIIii',data,900*28,chess.E2,chess.E4,0,1,10,0,0,0,901,-1)
    struct.pack_into('<BBBBIIIIii',data,901*28,chess.E7,chess.E5,0,1,8,0,0,0,-1,-1);p.write_bytes(data)
    c=Catalog(tmp_path/'catalog.db');sid=c.import_file(p);assert c.sources()[0]['status']=='ready'
    b=chess.Board();row=c.candidates(sid,b)[0];assert row['uci']=='e2e4' and row['n']==10;b.push_uci('e2e4');assert c.candidates(sid,b)[0]['uci']=='e7e5'

def test_abk_rejects_cycle(tmp_path):
    p=tmp_path/'bad.abk';data=bytearray(901*28);struct.pack_into('<BBBBIIIIii',data,900*28,chess.E2,chess.E4,0,1,10,0,0,0,-1,900);p.write_bytes(data)
    c=Catalog(tmp_path/'catalog.db');c.import_file(p);assert c.sources()[0]['status']=='error'

def test_standard_registry(tmp_path):
    from app.verification import fixtures
    fixtures(tmp_path)
    r=open_reader(tmp_path/'fixture.pgn');assert len(list(r.enumerate(1,3)))==3
    r=open_reader(tmp_path/'fixture.pgn.gz');assert r.game(1)['game']
    r=open_reader(tmp_path/'fixture.bin');assert r.continuations(chess.Board());r.close()
    assert len(list(open_reader(tmp_path/'fixture.fen').positions()))==1

def test_no_false_support():
    with pytest.raises(ValueError):open_reader('not-a-book.ctg')
    with pytest.raises(ValueError):open_reader('not-a-db.si4')
def engine_path():
    from app.opponents import discover_engine
    p=discover_engine()
    if not p:pytest.skip('No actual UCI engine configured')
    return p

def test_engine_profiles(tmp_path):
    p=engine_path();r=EngineRegistry(tmp_path/'engines.json');a=r.add(p,'Full');b=r.add(p,'Beginner');assert len(r.profiles)==2 and a['status']=='READY';assert pe_arch(p)==0x8664
    r.data['default']=b['id'];r.save();assert EngineRegistry(r.path).default()['label']=='Beginner';r.remove(a['id']);assert len(r.profiles)==1 and Path(p).exists()

def test_engine_discovery(tmp_path):
    r=EngineRegistry(tmp_path/'engines.json');found=r.candidates();assert any('stockfish' in p.name.lower() for p in found);assert all('croissant' not in p.name.lower() for p in found)

def test_engine_crash_graceful(tmp_path):
    r=EngineRegistry(tmp_path/'engines.json')
    with pytest.raises(Exception):r.verify(helper_path())
    assert not r.profiles

def test_install_rejects_unofficial(tmp_path):
    r=EngineRegistry(tmp_path/'engines.json')
    with pytest.raises(ValueError,match='official'):r.install({'repository':'someone/unknown','url':'https://example.com/a.exe','size':10})

def test_native_full_header_search(native):
    with open_reader(native) as r:
        v=r.search_headers('Morphy');assert v['matches']==1 and v['ids']==[2]

def test_engine_assisted_native(native,tmp_path):
    p=engine_path();c=Catalog(tmp_path/'catalog.db');sid=c.open_native(native);c.index_native(sid,2);b=chess.Board();b.push_uci('f2f3');d=HistoricalDatabaseOpponent(c,sid,'Engine assisted',engine=Engine(p,seconds=.02,depth=2)).choose(b);assert d.move.uci()=='e7e5' and d.origin.startswith('database')

def test_actual_second_engine():
    path=Path('private/engine-download/engines.json')
    if not path.exists():pytest.skip('Optional real Lc0 CPU runtime unavailable')
    p=EngineRegistry(path).default();b=chess.Board();m=Engine(p['path'],seconds=.05,depth=2).move(b);assert m in b.legal_moves

def test_actual_cbh_samples():
    entry=os.environ.get('CBA_TEST_DATABASE')
    if not entry:pytest.skip('Private real CBH test is opt-in')
    with open_reader(entry) as r:
        info=r.metadata();assert info.games>1000000
        for identifier in [3,114,info.records//2,info.records-1,info.records,10856403]:
            row=r.game(identifier);assert row['id']==identifier and row['game']
        assert r.game(114)['game'].headers.get('SetUp')=='1'
        v=r.search_headers('Kasparov');assert v['matches']>0

def test_engine_manager_dialog(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.gui import Window
    from app.engine_manager_gui import EngineManagerDialog
    app=QApplication.instance() or QApplication([]);w=Window(tmp_path);d=EngineManagerDialog(w.engines,w);d.show();app.processEvents();assert d.windowTitle()=='CHESS ENGINE MANAGER';assert d.grab().width()>0;d.accept();w.close()

def test_engine_vs_engine_runs(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication,QInputDialog
    from PySide6.QtTest import QTest
    from app.gui import Window
    app=QApplication.instance() or QApplication([]);w=Window(tmp_path)
    a=w.engines.add(engine_path(),'White UCI');a.update(seconds=.02,depth=2)
    b=w.engines.add(engine_path(),'Black UCI');b.update(seconds=.02,depth=2);w.engines.save()
    monkeypatch.setattr(QInputDialog,'getItem',lambda *args:('Black UCI',True));w.mode.setCurrentIndex(9);w.start()
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.02)
        if len(w.board.board.move_stack)>=4:break
    w.active=False
    for _ in range(100):
        if not w.busy:break
        app.processEvents();time.sleep(.02)
    assert len(w.board.board.move_stack)>=4 and all(o.startswith('engine') for o in w.origins);w.close()

def test_stockfish_mode_keeps_engine_identity(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.gui import Window
    app=QApplication.instance() or QApplication([]);w=Window(tmp_path);sf=w.engines.add(engine_path());other=dict(sf,id='other',name='Different UCI',path='other-engine.exe');w.engines.profiles.append(other);w.engines.data['default']='other'
    w.mode.setCurrentIndex(3);assert w.opponent().engine.path==sf['path'];w.mode.setCurrentIndex(11);assert w.opponent().engine.path=='other-engine.exe';w.close()

def test_unconfigured_stockfish_is_gui_error(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from app.gui import Window
    app=QApplication.instance() or QApplication([]);w=Window(tmp_path);w.engine_path='';w.engines.data['profiles']=[];w.mode.setCurrentIndex(3);w.human=False;w.active=True;messages=[];monkeypatch.setattr(QMessageBox,'warning',lambda *args:messages.append(args[2]));w.maybe_reply();assert messages and not w.active;w.close()
