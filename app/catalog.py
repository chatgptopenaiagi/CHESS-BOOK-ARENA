"""Streaming source adapters and transactional, resumable position catalog."""
import gzip, io, json, sqlite3, zipfile, hashlib, time
from pathlib import Path
import chess, chess.pgn, chess.polyglot

FORMATS={'.pgn':'SUPPORTED','.pgn.gz':'SUPPORTED','.bin':'SUPPORTED','.fen':'SUPPORTED','.epd':'SUPPORTED','.zip':'SUPPORTED',**{x:'UNSUPPORTED' for x in ['.cbh','.cbv','.ctg','.abk','.si4','.sg4','.sn4','.scid4']}}
def format_of(path):
    s=str(path).lower()
    return next((x for x in FORMATS if s.endswith(x) and x=='.pgn.gz'),Path(s).suffix)
def key(board):
    # Full canonical legal position, including legal EP and castling; no hash collisions.
    return ' '.join(board.fen(en_passant='legal').split()[:4])
def discover(folder,recursive=False):
    return [p for p in (Path(folder).rglob('*') if recursive else Path(folder).glob('*')) if p.is_file() and format_of(p) in FORMATS]

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
CREATE TABLE IF NOT EXISTS saved(id INTEGER PRIMARY KEY,date TEXT,title TEXT,pgn TEXT,meta TEXT);
''')
    def db(self):
        c=sqlite3.connect(self.path,timeout=30); c.row_factory=sqlite3.Row; return c
    def sources(self):
        with self.db() as c: return [dict(r) for r in c.execute('SELECT * FROM sources ORDER BY id DESC')]
    def register(self,path):
        p=Path(path).resolve(); st=p.stat(); fmt=format_of(p)
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO sources(path,format,size,stamp,status) VALUES(?,?,?,?,?)',(str(p),fmt,st.st_size,st.st_mtime_ns,'pending' if FORMATS.get(fmt)=='SUPPORTED' else 'UNSUPPORTED'))
            r=c.execute('SELECT * FROM sources WHERE path=?',(str(p),)).fetchone()
            if r['size']!=st.st_size or r['stamp']!=st.st_mtime_ns:
                c.execute('DELETE FROM moves WHERE source=?',(r['id'],)); c.execute('DELETE FROM games WHERE source=?',(r['id'],)); c.execute('DELETE FROM positions WHERE source=?',(r['id'],))
                c.execute("UPDATE sources SET size=?,stamp=?,status='changed',games=0,error='' WHERE id=?",(st.st_size,st.st_mtime_ns,r['id']))
            return r['id']
    def import_file(self,path,cancel=lambda:False,progress=lambda n:None):
        sid=self.register(path); fmt=format_of(path)
        if FORMATS.get(fmt)!='SUPPORTED': return sid
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
    def candidates(self,sid,board,player=''):
        with self.db() as c:
            src=c.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
            if not src: return []
            stat=Path(src['path']).stat()
            if stat.st_size!=src['size'] or stat.st_mtime_ns!=src['stamp']: raise ValueError('Source changed; reindex before using this repertoire')
            if src['format']=='.bin':
                with chess.polyglot.open_reader(src['path']) as book:
                    return [dict(uci=e.move.uci(),n=e.weight,w=0,d=0,l=0,source='book') for e in book.find_all(board) if e.move in board.legal_moves]
            rows=c.execute('SELECT uci,result,COUNT(*) n FROM moves WHERE source=? AND pos=?'+(' AND player=?' if player else '')+' GROUP BY uci,result',(sid,key(board),player) if player else (sid,key(board)))
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
