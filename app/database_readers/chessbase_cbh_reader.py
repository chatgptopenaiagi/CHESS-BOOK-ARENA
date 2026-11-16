import io,re
import chess,chess.pgn
from .native_bridge import NativeBridge
from .reader_interface import Capabilities,DatabaseInfo
from .format_detector import family
class ChessBaseReader:
    capabilities=Capabilities(random_access=True,annotations=True,native_headers=True)
    def __init__(self,path):
        self.path=path;self.family=family(path)
        if self.family['missing']:raise ValueError('Missing required components: '+', '.join(self.family['missing']))
        self.bridge=NativeBridge(path)
    def metadata(self):
        info=list(self.bridge.request('info'))[-1]
        return DatabaseInfo(str(self.family['entry'].suffix),'cbvault 0.1.7','READ-ONLY SUPPORTED' if self.family['entry'].suffix.lower()=='.cbh' else 'PARTIAL SUPPORT',records=info['records'],games=info['games'],size=self.family['size'],found=[p.suffix for p in self.family['found']],detail='Native header counts; move/annotation decoding is verified per game. Only indexed subsets contribute position statistics.')
    def enumerate(self,first=1,count=100):
        for r in self.bridge.request('range',id=first,count=count):
            if 'pgn' in r:
                g=chess.pgn.read_game(io.StringIO(r['pgn']))
                if g is None or g.errors:yield dict(id=r['id'],error='PGN legality validation failed: '+str(g.errors if g else 'empty'));continue
                try:
                    def validate(node):
                        for child in node.variations:
                            if child.move and child.move not in node.board().legal_moves:raise ValueError('Illegal move in decoded variation')
                            validate(child)
                    validate(g)
                    adjustments=[]
                    for k,v in r.get('native_header',{}).items():
                        actual=g.headers.get(k,'')
                        if actual==v or (not v and actual=='?'):continue
                        normalized=v.translate(str.maketrans(dict(zip('\ue024\ue025\ue026\ue027\ue028\ue029','KQRBNP'))))
                        if k in ['White','Black'] and ', ' in normalized:
                            first=normalized.rsplit(', ',1)[1]
                            if 1<=len(first)<=2 and re.fullmatch(r'[A-Z0-9]+',first.strip()):normalized+='.'
                        if actual==normalized:adjustments.append(k+': documented PGN presentation normalization');continue
                        raise ValueError('Native header and PGN metadata disagree in '+k)
                    r['presentation_adjustments']=adjustments
                    r['analysis_null_mainline']=any(not move for move in g.mainline_moves())
                    r['game']=g;yield r
                except Exception as e:yield dict(id=r['id'],error=str(e))
            elif 'id' in r:yield r
    def game(self,identifier):
        rows=list(self.enumerate(identifier,1))
        if not rows:raise ValueError(f'Record {identifier}: no response from native reader')
        row=rows[0]
        if row.get('id')!=identifier:raise RuntimeError('Native reader returned a mismatched source identifier')
        if row.get('error') or row.get('skipped'):raise ValueError(f"Record {identifier}: {row.get('error',row.get('skipped'))}")
        return row
    def search_headers(self,player,year=None):
        args=dict(player=player)
        if year:args['year']=int(year)
        result=list(self.bridge.request('search',**args))[-1]
        return result
    def close(self):self.bridge.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
