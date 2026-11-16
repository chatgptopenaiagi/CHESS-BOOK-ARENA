"""Persistent verified UCI profiles and bounded, explicit engine discovery."""
import json,os,uuid,struct,hashlib,urllib.request,zipfile,shutil
from pathlib import Path
import chess.engine
OFFICIAL={'Stockfish':'official-stockfish/Stockfish','Leela Chess Zero':'LeelaChessZero/lc0'}
def pe_arch(path):
    with open(path,'rb') as f:
        if f.read(2)!=b'MZ':raise ValueError('Not a Windows executable')
        f.seek(60);offset=struct.unpack('<I',f.read(4))[0]
        if offset>16*1024**2:raise ValueError('Invalid PE header')
        f.seek(offset)
        if f.read(4)!=b'PE\0\0':raise ValueError('Invalid PE signature')
        return struct.unpack('<H',f.read(2))[0]
class EngineRegistry:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        try:self.data=json.loads(self.path.read_text())
        except (OSError,ValueError):self.data={'profiles':[],'default':None}
    @property
    def profiles(self):return self.data['profiles']
    def save(self):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.data,indent=2));temp.replace(self.path)
    def verify(self,path):
        path=str(Path(path).resolve())
        if pe_arch(path)!=0x8664:raise ValueError('Select a Windows x64 engine executable')
        with chess.engine.SimpleEngine.popen_uci(path,timeout=5) as e:
            options={k:dict(type=o.type,default=o.default,min=o.min,max=o.max,var=o.var,managed=o.is_managed()) for k,o in e.options.items()}
            return dict(path=path,name=e.id.get('name',Path(path).stem),author=e.id.get('author',''),options=options,status='READY',sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
    def add(self,path,label=None):
        p=self.verify(path);p.update(id=str(uuid.uuid4()),label=label or p['name'],settings={},seconds=.3,depth=16,multipv=3)
        self.profiles.append(p)
        if not self.data['default']:self.data['default']=p['id']
        self.save();return p
    def default(self):return next((p for p in self.profiles if p['id']==self.data['default']),None)
    def remove(self,identifier):
        self.data['profiles']=[p for p in self.profiles if p['id']!=identifier]
        if self.data['default']==identifier:self.data['default']=self.profiles[0]['id'] if self.profiles else None
        self.save()
    def candidates(self,folders=()):
        result=[]
        for v in [os.environ.get('CHESS_ARENA_ENGINE'),shutil.which('stockfish'),shutil.which('lc0')]:
            if v and Path(v).is_file():result.append(Path(v))
        # Read existing machine inventory if present; execute only explicit chess-engine records.
        inventory=Path.home()/'.codex/machine-capabilities/software-capabilities.json'
        try:
            items=json.loads(inventory.read_text(encoding='utf-8-sig'))['software']
            if isinstance(items,dict):items=items.values()
            for item in items:
                name=str(item.get('name','')).lower();exe=item.get('executable_path','')
                if any(n in name for n in ['stockfish','leela chess zero']) and exe and Path(exe).is_file() and Path(exe).name.lower().startswith(('stockfish','lc0','leela')) and Path(exe).suffix.lower()=='.exe':result.append(Path(exe))
        except (OSError,KeyError,ValueError,AttributeError):pass
        roots=[self.path.parent/'engines',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Stockfish',*map(Path,folders)]
        for root in roots:
            if not root.is_dir():continue
            for p in root.rglob('*.exe'):
                if any(n in p.name.lower() for n in ['stockfish','lc0','leela','berserk','ethereal','komodo','dragon','crafty','demolito']):result.append(p)
                if len(result)>=100:break
        return list(dict.fromkeys(result))
    def releases(self,name):
        repo=OFFICIAL[name]
        req=urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/latest',headers={'User-Agent':'ChessBookArena/0.2.0'})
        with urllib.request.urlopen(req,timeout=30) as r:release=json.load(r)
        return [dict(name=a['name'],url=a['browser_download_url'],size=a['size'],digest=a.get('digest'),repository=repo,tag=release['tag_name']) for a in release.get('assets',[]) if a['name'].endswith('.zip') and ('windows' in a['name'].lower() or 'win64' in a['name'].lower()) and not any(x in a['name'].lower() for x in ['arm','android'])]
    def install(self,asset):
        repo=asset['repository'];url=asset['url']
        if repo not in OFFICIAL.values() or not url.startswith('https://github.com/'+repo+'/releases/download/'):raise ValueError('Only allowlisted official release assets can be installed')
        if asset['size']>1024**3:raise ValueError('Release exceeds 1 GiB download limit')
        root=self.path.parent/'engines'/uuid.uuid4().hex;root.mkdir(parents=True)
        archive=root/'download.zip';total=0
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ChessBookArena/0.2.0'}),timeout=60) as src,archive.open('wb') as dst:
            while block:=src.read(1024**2):
                total+=len(block)
                if total>1024**3:raise ValueError('Download exceeds size limit')
                dst.write(block)
        if asset.get('digest') and 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()!=asset['digest']:raise ValueError('Official asset checksum mismatch')
        with zipfile.ZipFile(archive) as z:
            if len(z.infolist())>2000 or sum(i.file_size for i in z.infolist())>2*1024**3:raise ValueError('Archive exceeds extraction limit')
            for info in z.infolist():
                target=(root/info.filename).resolve()
                if not target.is_relative_to(root.resolve()) or info.external_attr>>16&0o170000==0o120000:raise ValueError('Unsafe archive member')
            z.extractall(root)
        choices=[p for p in root.rglob('*.exe') if p.name.lower().startswith(('stockfish','lc0')) and pe_arch(p)==0x8664]
        if not choices:raise ValueError('No suitable x64 UCI engine found; nothing registered')
        archive.unlink();return choices
