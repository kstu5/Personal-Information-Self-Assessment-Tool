"""Pinned, authenticated loopback-only Qwen CPU runtime. No document logging."""
from pathlib import Path
import atexit,hashlib,http.client,json,os,secrets,socket,subprocess,time,zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'.runtime/qwen-review'
MODEL_NAME='Qwen3.5-0.8B'


def selected_secondary():
    provider=os.environ.get('PII_SECONDARY_MODEL')
    config=ROOT/'.runtime/secondary-review.json'
    if provider is None and config.is_file():provider=json.loads(config.read_text(encoding='utf-8'))['provider']
    provider=provider or 'koelectra'
    if provider not in {'koelectra','qwen3.5-0.8b'}:raise ValueError('Unsupported secondary model')
    return provider


def _sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_assets():
    m=json.loads((ROOT/'models/qwen-review.json').read_text(encoding='utf-8'))
    model=DEST/m['filename'];archive=DEST/'runtime.zip'
    for path,info in ((model,m),(archive,m['runtime'])):
        if not path.is_file() or path.stat().st_size!=info['bytes'] or _sha(path)!=info['sha256']:
            raise ValueError('Qwen assets are missing or do not match the pinned version')
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir():continue
            path=(DEST/'runtime'/item.filename).resolve()
            if not path.is_relative_to((DEST/'runtime').resolve()) or not path.is_file():raise ValueError('Invalid Qwen runtime')
            with z.open(item) as f:expected=hashlib.file_digest(f,'sha256').hexdigest()
            if _sha(path)!=expected:raise ValueError('Qwen runtime hash mismatch')
    return model,DEST/'runtime/llama-server.exe'


class WindowsJob:
    """Kill the server if its model worker exits, including timeout termination."""
    def __init__(self,process):
        import ctypes as C
        from ctypes import wintypes as W
        class BASIC(C.Structure):
            _fields_=[('processTime',C.c_longlong),('jobTime',C.c_longlong),('flags',W.DWORD),
                      ('minWorking',C.c_size_t),('maxWorking',C.c_size_t),('active',W.DWORD),
                      ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
        class IO(C.Structure):_fields_=[(n,C.c_ulonglong) for n in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
        class LIMITS(C.Structure):
            _fields_=[('basic',BASIC),('io',IO),('processMemory',C.c_size_t),('jobMemory',C.c_size_t),('peakProcess',C.c_size_t),('peakJob',C.c_size_t)]
        self.kernel=C.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateJobObjectW.restype=W.HANDLE
        self.kernel.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR]
        self.kernel.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
        self.kernel.CloseHandle.argtypes=[W.HANDLE]
        self.handle=self.kernel.CreateJobObjectW(None,None)
        limits=LIMITS();limits.basic.flags=0x2000
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle,9,C.byref(limits),C.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(self.handle,W.HANDLE(int(process._handle))):
            self.close();process.terminate();raise RuntimeError('Cannot manage Qwen worker lifetime')
    def close(self):
        if getattr(self,'handle',None):self.kernel.CloseHandle(self.handle);self.handle=None


class QwenServer:
    def __init__(self):
        self.model,self.executable=verify_assets()
        self.process=None;self.job=None;self.port=None;self.token=secrets.token_urlsafe(32)
        self.stats={'requests':0,'seconds':0.,'promptTokens':0,'completionTokens':0}
        atexit.register(self.close)

    def _http(self,path,payload=None,timeout=120):
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=timeout)
        try:
            headers={'Authorization':'Bearer '+self.token}
            data=None
            if payload is not None:data=json.dumps(payload,ensure_ascii=False).encode('utf-8');headers['Content-Type']='application/json'
            connection.request('POST' if payload is not None else 'GET',path,data,headers)
            response=connection.getresponse();raw=response.read()
            if response.status!=200:raise RuntimeError('Qwen local request failed')
            return json.loads(raw)
        finally:connection.close()

    def start(self):
        if self.process is not None and self.process.poll() is None:return
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        args=[str(self.executable),'-m',self.model.name,'--host','127.0.0.1','--port',str(self.port),
              '-c','8192','-t','4','-tb','4','-np','1','-ngl','0','--no-warmup','--log-disable',
              '--jinja','--api-key',self.token]
        self.process=subprocess.Popen(args,cwd=DEST,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if os.name=='nt':self.job=WindowsJob(self.process)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if self.process.poll() is not None:self.close();raise RuntimeError('Qwen runtime exited during startup')
            try:
                if self._http('/health',timeout=1).get('status')=='ok':return
            except (OSError,RuntimeError,ValueError):pass
            time.sleep(.15)
        self.close();raise RuntimeError('Qwen startup timed out')

    def chat(self,system,user,schema):
        self.start();start=time.monotonic()
        result=self._http('/v1/chat/completions',{
            'model':'qwen-review','messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(user,ensure_ascii=False)}],
            'temperature':0,'seed':42,'max_tokens':512,'cache_prompt':False,
            'chat_template_kwargs':{'enable_thinking':False},
            'response_format':{'type':'json_schema','json_schema':{'name':'pii_verdict','strict':True,'schema':schema}}})
        self.stats['requests']+=1;self.stats['seconds']+=time.monotonic()-start
        usage=result.get('usage',{})
        self.stats['promptTokens']+=usage.get('prompt_tokens',0);self.stats['completionTokens']+=usage.get('completion_tokens',0)
        if result['choices'][0].get('finish_reason')!='stop':raise RuntimeError('Qwen returned an incomplete verdict')
        return json.loads(result['choices'][0]['message']['content'])

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            self.process=None
        if self.job is not None:self.job.close();self.job=None
