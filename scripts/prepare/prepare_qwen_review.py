"""Explicit optional download. The application itself never downloads models."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile,argparse,os,platform
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'models/qwen-review.json'
DEST=ROOT/'.runtime/qwen-review'


def matches(path,size,digest):
    if not path.is_file() or path.stat().st_size!=size:return False
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()==digest


def download(url,path,size,digest):
    if matches(path,size,digest):return
    partial=path.with_suffix(path.suffix+'.partial')
    request=urllib.request.Request(url,headers={'User-Agent':'PrivacySelfAssessmentTool-model-setup'})
    with urllib.request.urlopen(request,timeout=120) as response,partial.open('wb') as target:
        while block:=response.read(4*1024*1024):target.write(block)
    if not matches(partial,size,digest):raise ValueError('Downloaded asset hash mismatch')
    partial.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');args=p.parse_args()
    if os.name!='nt' or platform.machine().lower() not in {'amd64','x86_64'}:
        raise RuntimeError('This optional runtime requires Windows x64.')
    m=json.loads(MANIFEST.read_text(encoding='utf-8'));DEST.mkdir(parents=True,exist_ok=True)
    print('Downloading pinned Qwen3.5-0.8B Q4_K_M (533 MB)...',flush=True)
    download(f"https://huggingface.co/{m['repo']}/resolve/{m['revision']}/{m['filename']}",DEST/m['filename'],m['bytes'],m['sha256'])
    r=m['runtime'];archive=DEST/'runtime.zip'
    print('Downloading pinned Windows CPU runtime...',flush=True)
    download(r['url'],archive,r['bytes'],r['sha256'])
    runtime=DEST/'runtime';runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            out=(runtime/member.filename).resolve()
            if not out.is_relative_to(runtime.resolve()):raise ValueError('Unsafe runtime archive')
        z.extractall(runtime)
    files=[]
    for path in sorted(runtime.rglob('*')):
        if path.is_file():
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            files.append({'file':path.relative_to(runtime).as_posix(),'bytes':path.stat().st_size,'sha256':digest})
    (DEST/'runtime-files.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    if args.enable:
        (ROOT/'.runtime/secondary-review.json').write_text(json.dumps({'provider':'qwen3.5-0.8b'}),encoding='utf-8')
    print('Verified model and runtime. '+('Qwen enabled.' if args.enable else 'Use --enable to make Qwen the local default.'),flush=True)


if __name__=='__main__':main()
