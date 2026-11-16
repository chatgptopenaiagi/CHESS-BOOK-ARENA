import sys,os,json,queue,threading,subprocess
from pathlib import Path

def helper_path():
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))
    options=[base/'native-bin'/'arena-reader.exe',Path(__file__).resolve().parents[2]/'native'/'arena-reader'/'target'/'release'/'arena-reader.exe']
    return next((p for p in options if p.exists()),options[0])
class NativeBridge:
    def __init__(self,path,timeout=120):
        self.timeout=timeout; self.q=queue.Queue(maxsize=64); self.closed=False
        self.p=subprocess.Popen([str(helper_path()),str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        def read():
            try:
                for line in self.p.stdout:
                    value=json.loads(line)
                    while not self.closed:
                        try:self.q.put(value,timeout=.2);break
                        except queue.Full:pass
                    if self.closed:break
            except Exception as e:
                if not self.closed:self.q.put({'error':str(e)})
            finally:
                if not self.closed:self.q.put(None)
        threading.Thread(target=read,daemon=True).start(); self.ready=self.receive()
        if not self.ready.get('ready'):self.close();raise ValueError(self.ready.get('error','Native reader could not open source'))
    def receive(self):
        try:r=self.q.get(timeout=self.timeout)
        except queue.Empty:self.close();raise TimeoutError('Native reader timed out; source not changed')
        if r is None:raise RuntimeError('Native reader exited unexpectedly')
        return r
    def request(self,cmd,**args):
        self.p.stdin.write(json.dumps(dict(cmd=cmd,**args))+'\n');self.p.stdin.flush()
        while True:
            r=self.receive()
            if r.get('end'):
                if r.get('error'):raise ValueError(r['error'])
                if len(r)>1:yield r
                break
            yield r
    def close(self):
        if self.closed:return
        self.closed=True
        if self.p.poll() is None:self.p.kill()
        self.p.wait(timeout=5)
        self.p.stdin.close();self.p.stdout.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
