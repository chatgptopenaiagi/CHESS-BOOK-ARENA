"""Streaming source adapters and transactional, resumable position catalog."""
import gzip, io, json, sqlite3, zipfile, hashlib, time
from pathlib import Path
import chess, chess.pgn, chess.polyglot

FORMATS={'.cbh':'READ-ONLY SUPPORTED','.2cbh':'PARTIAL SUPPORT','.cbv':'UNSUPPORTED','.cbz':'UNSUPPORTED','.abk':'PARTIAL SUPPORT','.pgn':'READ-ONLY SUPPORTED','.pgn.gz':'READ-ONLY SUPPORTED','.bin':'READ-ONLY SUPPORTED','.fen':'READ-ONLY SUPPORTED','.epd':'READ-ONLY SUPPORTED','.zip':'READ-ONLY SUPPORTED',**{x:'UNSUPPORTED' for x in ['.ctg','.si4','.sg4','.sn4','.scid4']}}
def format_of(path):
    s=str(path).lower()
    return next((x for x in FORMATS if s.endswith(x) and x=='.pgn.gz'),Path(s).suffix)
def key(board):
    # Full canonical legal position, including legal EP and castling; no hash collisions.
    return ' '.join(board.fen(en_passant='legal').split()[:4])
def discover(folder,recursive=False):
    from app.database_readers.format_detector import COMPONENTS
    return [p for p in (Path(folder).rglob('*') if recursive else Path(folder).glob('*')) if p.is_file() and format_of(p) in FORMATS and p.suffix.lower() not in COMPONENTS]

class Catalog:
    def __init__(self,path):
        self.path=str(path); Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,path TEXT UNIQUE,format TEXT,size INTEGER,stamp INTEGER,status TEXT,games INTEGER DEFAULT 0,error TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS coverage(source INTEGER PRIMARY KEY,positions INTEGER,entries INTEGER);
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY,source INTEGER,ordinal INTEGER,digest TEXT,headers TEXT,pgn TEXT,UNIQUE(source,ordinal),UNIQUE(source,digest));
CREATE TABLE IF NOT EXISTS moves(source INTEGER,game INTEGER,pos TEXT,uci TEXT,player TEXT,result TEXT);
CREATE INDEX IF NOT EXISTS pos_lookup ON moves(source,pos,player);
CREATE INDEX IF NOT EXISTS game_lookup ON moves(game);
CREATE TABLE IF NOT EXISTS positions(source INTEGER,fen TEXT,label TEXT);
CREATE TABLE IF NOT EXISTS book_moves(source INTEGER,pos TEXT,uci TEXT,weight INTEGER,PRIMARY KEY(source,pos,uci));
CREATE TABLE IF NOT EXISTS native_state(source INTEGER PRIMARY KEY,info TEXT,signature TEXT,next_id INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS decode_errors(source INTEGER,native_id INTEGER,error TEXT,PRIMARY KEY(source,native_id));
CREATE TABLE IF NOT EXISTS native_games(source INTEGER,native_id INTEGER,game_id INTEGER,PRIMARY KEY(source,native_id));
CREATE TABLE IF NOT EXISTS saved(id INTEGER PRIMARY KEY,date TEXT,title TEXT,pgn TEXT,meta TEXT);
''')
    def db(self):
        c=sqlite3.connect(self.path,timeout=30); c.row_factory=sqlite3.Row; return c
    def sources(self):
        with self.db() as c: return [dict(r) for r in c.execute('SELECT * FROM sources ORDER BY id DESC')]
    def register(self,path):
        p=Path(path).resolve(); st=p.stat(); fmt=format_of(p)
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO sources(path,format,size,stamp,status) VALUES(?,?,?,?,?)',(str(p),fmt,st.st_size,st.st_mtime_ns,'pending' if FORMATS.get(fmt) in ['READ-ONLY SUPPORTED','PARTIAL SUPPORT'] else 'UNSUPPORTED'))
            r=c.execute('SELECT * FROM sources WHERE path=?',(str(p),)).fetchone()
            if r['size']!=st.st_size or r['stamp']!=st.st_mtime_ns:
                c.execute('DELETE FROM moves WHERE source=?',(r['id'],)); c.execute('DELETE FROM games WHERE source=?',(r['id'],)); c.execute('DELETE FROM positions WHERE source=?',(r['id'],))
                c.execute("UPDATE sources SET size=?,stamp=?,status='changed',games=0,error='' WHERE id=?",(st.st_size,st.st_mtime_ns,r['id']))
            return r['id']
    def import_file(self,path,cancel=lambda:False,progress=lambda n:None):
        if format_of(path) in ['.cbh','.2cbh']:return self.open_native(path)
        if format_of(path)=='.abk':return self.import_abk(path,cancel,progress)
        sid=self.register(path); fmt=format_of(path)
        if FORMATS.get(fmt) not in ['READ-ONLY SUPPORTED','PARTIAL SUPPORT']: return sid
        try:
            with self.db() as c: c.execute("UPDATE sources SET status='indexing',error='' WHERE id=?",(sid,))
            if fmt=='.bin':
                last=-1; count=0; unique=0
                with chess.polyglot.open_reader(str(path)) as book:
                    for entry in book:
                        if entry.key<last: raise ValueError('Polyglot entries are not sorted')
                        if entry.key!=last: unique+=1
                        last=entry.key; count+=1
                        if cancel(): raise InterruptedError('Cancelled')
                if not count: raise ValueError('Empty Polyglot book')
                with self.db() as c:
                    c.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?)',(sid,unique,count))
            elif fmt=='.zip':
                members=0
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if format_of(info.filename)=='.bin':
                            target=Path(self.path).parent/'archive-books'/str(sid)/Path(info.filename).name
                            target.parent.mkdir(parents=True,exist_ok=True)
                            if info.file_size>2*1024**3: raise ValueError('Book archive member exceeds 2 GiB limit')
                            import shutil
                            with z.open(info) as src, open(target,'wb') as dst: shutil.copyfileobj(src,dst,1024*1024)
                            self.import_file(target,cancel,progress)
                            members+=1
                            continue
                        if format_of(info.filename) not in ['.pgn','.pgn.gz','.fen','.epd']: continue
                        if info.file_size>2*1024**3: raise ValueError('Archive member exceeds 2 GiB safety limit; extract manually')
                        members+=1
                        with z.open(info) as raw:
                            stream=gzip.GzipFile(fileobj=raw) if info.filename.lower().endswith('.gz') else raw
                            self._stream(sid,io.TextIOWrapper(stream,encoding='utf-8-sig',errors='replace'),format_of(info.filename),cancel,progress,info.filename)
                if not members: raise ValueError('No supported archive members')
            else:
                op=gzip.open if fmt=='.pgn.gz' else open
                with op(path,'rt',encoding='utf-8-sig',errors='replace') as f: self._stream(sid,f,fmt,cancel,progress)
            with self.db() as c:
                n=c.execute('SELECT COUNT(*) FROM games WHERE source=?',(sid,)).fetchone()[0]
                pos=c.execute('SELECT COUNT(*) FROM positions WHERE source=?',(sid,)).fetchone()[0]
                if fmt not in ['.bin','.zip'] and not n and not pos: raise ValueError('No valid chess content found')
                if fmt!='.bin':
                    stats=self.stats(sid); c.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?)',(sid,stats['positions'] or pos,stats['entries']))
                c.execute("UPDATE sources SET status='ready',games=? WHERE id=?",(n,sid))
        except Exception as e:
            with self.db() as c: c.execute('UPDATE sources SET status=?,error=? WHERE id=?',('cancelled' if isinstance(e,InterruptedError) else 'error',str(e),sid))
        return sid
    def _stream(self,sid,f,fmt,cancel,progress,member=''):
        if fmt in ['.fen','.epd']:
            with self.db() as c:
                for line in f:
                    if cancel(): raise InterruptedError('Cancelled')
                    if not line.strip(): continue
                    b=chess.Board(); b.set_epd(line.strip()) if fmt=='.epd' else b.set_fen(line.strip())
                    if not b.is_valid(): raise ValueError('Invalid position')
                    c.execute('INSERT INTO positions SELECT ?,?,? WHERE NOT EXISTS(SELECT 1 FROM positions WHERE source=? AND fen=?)',(sid,b.fen(),line.strip(),sid,b.fen()))
            return
        ordinal=0
        while True:
            if cancel(): raise InterruptedError('Cancelled; import again to resume')
            g=chess.pgn.read_game(f)
            if g is None: break
            ordinal+=1
            if g.errors: raise ValueError(f'Invalid PGN game {ordinal}: {g.errors[0]}')
            if not any(g.mainline_moves()): continue
            pgn=str(g); digest=hashlib.sha256(pgn.encode()).hexdigest()
            with self.db() as c:
                cur=c.execute('INSERT OR IGNORE INTO games(source,ordinal,digest,headers,pgn) VALUES(?,?,?,?,?)',(sid,member+':'+str(ordinal),digest,json.dumps(dict(g.headers)),pgn))
                if cur.rowcount:
                    gid=cur.lastrowid; b=g.board(); rows=[]
                    for m in g.mainline_moves():
                        if m not in b.legal_moves: raise ValueError('Illegal PGN continuation')
                        rows.append((sid,gid,key(b),m.uci(),g.headers.get('White' if b.turn else 'Black','?'),g.headers.get('Result','*'))); b.push(m)
                    c.executemany('INSERT INTO moves VALUES(?,?,?,?,?,?)',rows)
            if ordinal%50==0: progress(ordinal)
        progress(ordinal)
    def import_abk(self,path,cancel=lambda:False,progress=lambda n:None):
        from app.database_readers.arena_abk_reader import ArenaBookReader
        sid=self.register(path)
        try:
            with self.db() as c:
                c.execute('DELETE FROM book_moves WHERE source=?',(sid,));n=0
                for entry in ArenaBookReader(path).entries(cancel):
                    c.execute('INSERT INTO book_moves VALUES(?,?,?,?) ON CONFLICT(source,pos,uci) DO UPDATE SET weight=weight+excluded.weight',(sid,key(entry['board']),entry['move'].uci(),entry['weight']));n+=1
                    if n%1000==0:progress(n)
                if not n:raise ValueError('No legal ABK entries')
                positions=c.execute('SELECT COUNT(DISTINCT pos) FROM book_moves WHERE source=?',(sid,)).fetchone()[0]
                c.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?)',(sid,positions,n));c.execute("UPDATE sources SET status='ready',error='' WHERE id=?",(sid,))
        except Exception as e:
            with self.db() as c:c.execute('UPDATE sources SET status=?,error=? WHERE id=?',('cancelled' if isinstance(e,InterruptedError) else 'error',str(e),sid))
        return sid
    def open_native(self,path):
        from dataclasses import asdict
        from app.database_readers.reader_registry import open_reader
        from app.database_readers.format_detector import family
        sid=self.register(path)
        try:
            with open_reader(path) as reader: info=asdict(reader.metadata())
            signature=json.dumps(family(path)['signature'])
            with self.db() as c:
                old=c.execute('SELECT signature FROM native_state WHERE source=?',(sid,)).fetchone()
                if old and old[0]!=signature:
                    for table in ['moves','games','native_games','decode_errors','native_state','coverage']:c.execute('DELETE FROM '+table+' WHERE source=?',(sid,))
                c.execute('INSERT INTO native_state(source,info,signature) VALUES(?,?,?) ON CONFLICT(source) DO UPDATE SET info=excluded.info,signature=excluded.signature',(sid,json.dumps(info),signature))
                c.execute("UPDATE sources SET status='native open',error='' WHERE id=?",(sid,))
        except Exception as e:
            with self.db() as c:c.execute("UPDATE sources SET status='error',error=? WHERE id=?",(str(e),sid))
        return sid
    def native_info(self,sid):
        with self.db() as c:
            row=c.execute('SELECT * FROM native_state WHERE source=?',(sid,)).fetchone()
            return dict(row) if row else None
    def native_game(self,sid,identifier):
        from app.database_readers.reader_registry import open_reader
        source=next(s for s in self.sources() if s['id']==sid)
        self.assert_native_unchanged(source)
        with open_reader(source['path']) as r:return r.game(identifier)
    def assert_native_unchanged(self,source):
        from app.database_readers.format_detector import family
        state=self.native_info(source['id'])
        if not state:raise ValueError('Open the native database first')
        if json.dumps(family(source['path'])['signature'])!=state['signature']:raise ValueError('A database component changed; reopen and rebuild its index')
    def index_native(self,sid,count=1000,cancel=lambda:False,progress=lambda n:None):
        from app.database_readers.reader_registry import open_reader
        import shutil
        source=next(s for s in self.sources() if s['id']==sid); self.assert_native_unchanged(source)
        state=self.native_info(sid); first=state['next_id']; info=json.loads(state['info'])
        if first>info['records']:return sid
        estimate=count*20000
        if shutil.disk_usage(Path(self.path).parent).free<estimate+100*1024**2:raise ValueError('Insufficient cache space for requested segment; choose another cache location')
        with self.db() as c:c.execute("UPDATE sources SET status='indexing' WHERE id=?",(sid,))
        try:
            with open_reader(source['path']) as r:
                for row in r.enumerate(first,count):
                    if cancel():raise InterruptedError('Cancelled; next segment resumes after last committed record')
                    with self.db() as c:
                        if row.get('error'):c.execute('INSERT OR REPLACE INTO decode_errors VALUES(?,?,?)',(sid,row['id'],row['error']))
                        elif 'game' in row:
                            g=row['game']; pgn=row['pgn']; digest=hashlib.sha256((str(row['id'])+pgn).encode()).hexdigest()
                            cur=c.execute('INSERT OR IGNORE INTO games(source,ordinal,digest,headers,pgn) VALUES(?,?,?,?,?)',(sid,'native:'+str(row['id']),digest,json.dumps(dict(g.headers)),pgn))
                            if cur.rowcount:
                                gid=cur.lastrowid;c.execute('INSERT OR REPLACE INTO native_games VALUES(?,?,?)',(sid,row['id'],gid));b=g.board();rows=[]
                                if row.get('analysis_null_mainline'):
                                    c.execute('INSERT OR REPLACE INTO decode_errors VALUES(?,?,?)',(sid,row['id'],'Analysis null markers on mainline: PGN preserved; excluded from historical move statistics'))
                                for m in ([] if row.get('analysis_null_mainline') else g.mainline_moves()):
                                    rows.append((sid,gid,key(b),m.uci(),g.headers.get('White' if b.turn else 'Black','?'),g.headers.get('Result','*')));b.push(m)
                                c.executemany('INSERT INTO moves VALUES(?,?,?,?,?,?)',rows)
                        c.execute('UPDATE native_state SET next_id=? WHERE source=?',(row['id']+1,sid))
                    if row['id']%25==0:progress(row['id'])
            status='indexed' if first+count>info['records'] else 'partial index'
        except InterruptedError:status='cancelled'
        except Exception as e:
            with self.db() as c:c.execute("UPDATE sources SET status='error',error=? WHERE id=?",(str(e),sid))
            raise
        with self.db() as c:
            n=c.execute('SELECT COUNT(*) FROM games WHERE source=?',(sid,)).fetchone()[0];c.execute('UPDATE sources SET status=?,games=? WHERE id=?',(status,n,sid))
        stats=self.stats(sid)
        with self.db() as c:c.execute('INSERT OR REPLACE INTO coverage VALUES(?,?,?)',(sid,stats['positions'],stats['entries']))
        return sid
    def candidates(self,sid,board,player='',filters=None):
        with self.db() as c:
            src=c.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
            if not src: return []
            if src['format'] in ['.cbh','.2cbh']:self.assert_native_unchanged(dict(src))
            stat=Path(src['path']).stat()
            if stat.st_size!=src['size'] or stat.st_mtime_ns!=src['stamp']: raise ValueError('Source changed; reindex before using this repertoire')
            if src['format']=='.abk':
                return [dict(uci=r['uci'],n=r['weight'],w=0,d=0,l=0,source='ABK book') for r in c.execute('SELECT uci,weight FROM book_moves WHERE source=? AND pos=?',(sid,key(board))) if chess.Move.from_uci(r['uci']) in board.legal_moves]
            if src['format']=='.bin':
                with chess.polyglot.open_reader(src['path']) as book:
                    return [dict(uci=e.move.uci(),n=e.weight,w=0,d=0,l=0,source='book') for e in book.find_all(board) if e.move in board.legal_moves]
            sql='SELECT m.uci,m.result,COUNT(DISTINCT m.game) n FROM moves m JOIN games g ON g.id=m.game WHERE m.source=? AND m.pos=?'
            args=[sid,key(board)]
            if player:sql+=' AND m.player=?';args.append(player)
            filters=filters or {}
            for field,tag in [('player','White'),('event','Event'),('opening','Opening')]:
                value=filters.get(field,'').strip()
                if value:
                    if field=='player':sql+=" AND (json_extract(g.headers,'$.White') LIKE ? OR json_extract(g.headers,'$.Black') LIKE ?)";args.extend(['%'+value+'%']*2)
                    elif field=='opening':sql+=" AND (json_extract(g.headers,'$.Opening') LIKE ? OR json_extract(g.headers,'$.ECO') LIKE ?)";args.extend(['%'+value+'%']*2)
                    else:sql+=" AND json_extract(g.headers,'$.Event') LIKE ?";args.append('%'+value+'%')
            if filters.get('year'):sql+=" AND substr(json_extract(g.headers,'$.Date'),1,4)=?";args.append(filters['year'])
            if filters.get('result'):sql+=" AND json_extract(g.headers,'$.Result')=?";args.append(filters['result'])
            if filters.get('elo'):
                sql+=" AND max(CAST(COALESCE(json_extract(g.headers,'$.WhiteElo'),'0') AS INTEGER),CAST(COALESCE(json_extract(g.headers,'$.BlackElo'),'0') AS INTEGER))>=?";args.append(int(filters['elo']))
            rows=c.execute(sql+' GROUP BY m.uci,m.result',args)
            out={}
            for r in rows:
                if chess.Move.from_uci(r['uci']) not in board.legal_moves: continue
                v=out.setdefault(r['uci'],dict(uci=r['uci'],n=0,w=0,d=0,l=0,source='database')); v['n']+=r['n']
                result=r['result']; win='1-0' if board.turn else '0-1'
                if result!='*': v['w' if result==win else 'd' if result=='1/2-1/2' else 'l']+=r['n']
            return sorted(out.values(),key=lambda x:-x['n'])
    def players(self,sid):
        with self.db() as c: return [r[0] for r in c.execute('SELECT DISTINCT player FROM moves WHERE source=? ORDER BY player',(sid,))]
    def games(self,sid,query='',year='',result='',position=None):
        with self.db() as c:
            rows=c.execute('SELECT * FROM games WHERE source=?'+(' AND id IN (SELECT game FROM moves WHERE source=? AND pos=?)' if position else ''),(sid,sid,key(position)) if position else (sid,))
            out=[]
            for r in rows:
                h=json.loads(r['headers'])
                if query.lower() not in ' '.join(h.values()).lower() or (year and not h.get('Date','').startswith(year)) or (result and h.get('Result')!=result): continue
                out.append(dict(r))
                if len(out)>=500: break
            return out
    def stats(self,sid):
        with self.db() as c:
            return dict(positions=c.execute('SELECT COUNT(DISTINCT pos) FROM moves WHERE source=?',(sid,)).fetchone()[0],entries=c.execute('SELECT COUNT(*) FROM moves WHERE source=?',(sid,)).fetchone()[0])
    def save(self,board,meta):
        g=chess.pgn.Game.from_board(board)
        g.headers['Event']='CHESS BOOK ARENA'; g.headers['Result']=meta.get('result',board.result()); g.headers['Date']=time.strftime('%Y.%m.%d')
        for k,v in meta.items(): g.headers['Arena'+k.title().replace('_','')]=str(v)
        for node,origin in zip(g.mainline(),meta.get('origins',[])): node.comment=origin
        with self.db() as c: return c.execute('INSERT INTO saved(date,title,pgn,meta) VALUES(?,?,?,?)',(time.strftime('%Y-%m-%d %H:%M'),meta.get('mode','Game'),str(g),json.dumps(meta))).lastrowid
    def saves(self):
        with self.db() as c: return [dict(r) for r in c.execute('SELECT * FROM saved ORDER BY id DESC')]
