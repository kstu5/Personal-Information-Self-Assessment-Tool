"""Session-scoped queue for file inspection; clients only receive opaque ids."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from backend.documents import DocumentError
from backend.model_assets import MODEL_REPO

ROOT=Path(__file__).resolve().parents[1]
MAX_UPLOAD=20*1024*1024
SUFFIXES={'.txt','.csv','.tsv','.docx','.pptx','.hwpx','.hwp','.xlsx','.pdf','.png','.jpg','.jpeg'}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utf16(value): return len(value.encode('utf-16-le'))//2
def py_offset(value, offset):
    try: return len(value.encode('utf-16-le')[:offset*2].decode('utf-16-le'))
    except UnicodeError: raise DocumentError('글자 위치가 올바르지 않습니다.')


def replacement(text,label,choice):
    mode=choice.get('mode','keep')
    if mode=='keep': return text
    if mode=='full': return '█████'
    if mode=='custom':
        value=choice.get('text')
        if not isinstance(value,str) or len(value)>2000 or any(0xd800<=ord(c)<=0xdfff or ord(c)<32 and c not in '\n\t\r' for c in value): raise DocumentError('직접 수정 내용은 2,000자 이하의 텍스트여야 합니다.')
        return value
    if mode!='partial': raise DocumentError('올바른 가림 방법을 선택해 주세요.')
    digits=[i for i,c in enumerate(text) if c.isascii() and c.isdigit()]
    start,end=0,0
    if label in {'PHONE','FAX'} and len(digits)>=8:
        start=2 if text.startswith(('+82','02')) else 3 if len(digits)>=10 else 0;end=4
    elif label in {'RRN','FRN'} and len(digits)==13:start=6
    elif label in {'CARD','ACCOUNT'} and len(digits)>4:end=4
    elif label in {'AGE','HEIGHT','WEIGHT','DT_BIRTH','POSTAL_CODE'} and digits: pass
    elif label=='EMAIL' and '@' in text:
        at=text.rfind('@');return (text[0]+'*'*(at-1) if at>1 else '*')+text[at:]
    else:return text[:1]+'*'*(len(text)-1) if len(text)>1 else '*'
    hidden=set(digits[start:len(digits)-end if end else None])
    return ''.join('*' if i in hidden else c for i,c in enumerate(text))


def image_mask_boxes(candidate,mode,asset):
    """The preview and exporter share these exact source-pixel rectangles."""
    masked=replacement(candidate['text'],candidate['label'],{'mode':mode})
    groups=[];current=[]
    for i,box in enumerate(candidate['boxes']):
        hide=mode=='full' or i<len(masked) and masked[i]!=candidate['text'][i]
        if hide:
            if box[2]>box[0] and box[3]>box[1]:current.append(box)
        elif current:groups.append(current);current=[]
    if current:groups.append(current)
    result=[]
    for group in groups:
        margin=max(2,min(6,max(b[3]-b[1] for b in group)*.06))
        result.append([max(0,math.floor(min(b[0] for b in group)-margin)),max(0,math.floor(min(b[1] for b in group)-margin)),
                       min(asset['width'],math.ceil(max(b[2] for b in group)+margin)),min(asset['height'],math.ceil(max(b[3] for b in group)+margin))])
    return result


class FileReviewStore:
    def __init__(self,detector):
        self.detector=detector
        self.root=Path(tempfile.mkdtemp(prefix='before-post-review-'))
        self.jobs={};self.lock=threading.RLock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='document-review')
        self.closed=False

    def upload(self,name,data,original=None):
        if not isinstance(name,str) or len(name)>240 or any(c in name for c in '/\\:*?"<>|') or any(ord(c)<32 for c in name) or Path(name).suffix.lower() not in SUFFIXES:
            raise DocumentError('지원하는 문서·이미지 파일을 선택해 주세요.')
        if not data or len(data)>MAX_UPLOAD: raise DocumentError('파일당 20MB까지 검사할 수 있습니다.')
        with self.lock:
            if self.closed or len(self.jobs)>=8: raise DocumentError('한 번에 8개 파일까지 열 수 있습니다. 검토가 끝난 파일을 목록에서 제거해 주세요.')
            ident=secrets.token_urlsafe(18);work=self.root/ident;work.mkdir()
            source='source'+Path(name).suffix.lower();(work/source).write_bytes(data)
            job={'id':ident,'name':name,'state':'queued','progress':'검사 대기 중','work':work,'source':source,
                 'hash':hashlib.sha256(data).hexdigest(),'original':Path(original).resolve() if original else None,
                 'revision':secrets.token_urlsafe(12),'cancel':threading.Event(),'process':None,'manifest':None,'candidates':[],
                 'output':None,'exportResult':None,'error':None}
            job['previews']={}
            self.jobs[ident]=job
            self.pool.submit(self._inspect,job)
            return self._public(job)

    def open_paths(self,paths):
        results=[]
        for path in paths:
            p=Path(path)
            try:
                if not p.is_file() or p.stat().st_size>MAX_UPLOAD: raise DocumentError('파일당 20MB까지 검사할 수 있습니다.')
                results.append(self.upload(p.name,p.read_bytes(),p))
            except (OSError,DocumentError) as e:
                results.append({'name':p.name,'state':'rejected','error':str(e) if isinstance(e,DocumentError) else '파일을 읽지 못했습니다.'})
        return results

    def _job(self,ident):
        with self.lock:
            if ident not in self.jobs: raise DocumentError('작업이 만료되었거나 제거되었습니다.')
            return self.jobs[ident]

    def _update(self,job,**fields):
        with self.lock:job.update(fields)

    def _check_cancel(self,job):
        if self.closed or job['cancel'].is_set(): raise DocumentError('작업을 취소했습니다.','cancelled')

    def _unchanged(self,job):
        if digest(job['work']/job['source'])!=job['hash']: raise DocumentError('작업 사본이 변경되어 다시 검사가 필요합니다.')
        if job['original']:
            try: same=digest(job['original'])==job['hash']
            except OSError:same=False
            if not same:raise DocumentError('검사 후 원본이 변경되거나 이동되었습니다. 파일을 다시 열어 검사해 주세요.','file_changed')

    def _adapter(self,job,action,**fields):
        self._check_cancel(job)
        response=f'{action}-result.json';spec={'action':action,'source':job['source'],'response':response,**fields}
        request=job['work']/f'{action}-request.json';request.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
        cwd=ROOT/'.runtime'/'file-tools'
        if not cwd.exists():cwd.mkdir(parents=True)
        process=subprocess.Popen([sys.executable,str(ROOT/'backend'/'file_worker.py'),str(request)],cwd=cwd,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self._update(job,process=process);deadline=time.monotonic()+180
        try:
            while process.poll() is None:
                self._check_cancel(job)
                if time.monotonic()>deadline:raise DocumentError('문서 처리 시간이 3분을 넘었습니다. 문서를 나누어 검사해 주세요.','timeout')
                job['cancel'].wait(.2)
            result=job['work']/response
            if process.returncode or not result.exists():raise DocumentError('문서 읽기 도구를 실행하지 못했습니다. 설치 상태를 확인해 주세요.')
            content=json.loads(result.read_text(encoding='utf-8'))
            if not content.get('ok'):raise DocumentError(content['message'])
            return content['manifest']
        finally:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
                else:process.kill()
                process.wait(timeout=10)
            self._update(job,process=None)

    def _scan(self,job,manifest,phase):
        found=[];parts=manifest['parts']; batches=[];current=[];count=0
        # Batch short cells/paragraphs to avoid one model call per cell. Offsets are mapped back exactly.
        for p in parts:
            if current and count+len(p['text'])+2>6000:batches.append(current);current=[];count=0
            if len(p['text'])>12000:
                raise DocumentError('한 문단이 너무 깁니다. 12,000자 이하로 문단을 나누어 주세요.')
            current.append(p);count+=len(p['text'])+2
        if current:batches.append(current)
        for index,batch in enumerate(batches):
            self._check_cancel(job)
            self._update(job,progress=f'{phase} · {index+1}/{len(batches)} 구간 ({MODEL_REPO})')
            text='\n\n'.join(p['text'] for p in batch)
            # A post inspection may already own the shared model. Wait without switching detectors.
            deadline=time.monotonic()+90
            while True:
                self._check_cancel(job)
                try:result=self.detector.check('',text);break
                except DocumentError as e:
                    if e.code!='busy' or time.monotonic()>deadline:raise
                    job['cancel'].wait(.25)
            offsets=[];pos=0
            for p in batch:offsets.append((pos,pos+utf16(p['text']),p));pos+=utf16(p['text'])+2
            if any(not any(a<=c['start']<c['end']<=b for a,b,p in offsets) for c in result['candidates']):
                # Context across independent cells/metadata can produce a single span. Reinspect each
                # original target, rather than drop/clip the span or apply it across unrelated nodes.
                safe=[]
                for offset,_,part in offsets:
                    self._check_cancel(job)
                    deadline=time.monotonic()+90
                    while True:
                        try:single=self.detector.check('',part['text']);break
                        except DocumentError as e:
                            if e.code!='busy' or time.monotonic()>deadline:raise
                            self._check_cancel(job);job['cancel'].wait(.25)
                    safe.extend({**c,'start':offset+c['start'],'end':offset+c['end']} for c in single['candidates'])
                result={'candidates':safe}
            for c in result['candidates']:
                for a,b,p in offsets:
                    if a<=c['start']<c['end']<=b:
                        start,end=c['start']-a,c['end']-a
                        lo,hi=py_offset(p['text'],start),py_offset(p['text'],end)
                        if p['text'][lo:hi]!=c['text']:raise DocumentError('검출 위치가 원문과 일치하지 않습니다.')
                        item={**c,'id':f"{p['id']}:{start}:{end}:{c['label']}",'part':p['id'],'start':start,'end':end,'location':p['location']}
                        item['partialText']=replacement(c['text'],c['label'],{'mode':'partial'})
                        if p.get('asset'):
                            item['asset']=p['asset'];item['boxes']=p['boxes'][lo:hi]
                            asset=next(v for v in manifest['assets'] if v['id']==p['asset'])
                            item['maskBoxes']={mode:image_mask_boxes(item,mode,asset) for mode in ('full','partial')}
                            if 'ocrConfidences' in p:
                                values=[v for v in p['ocrConfidences'][lo:hi] if v is not None]
                                item['ocrConfidence']=round(min(values),1) if values else 0
                        found.append(item);break
                else:
                    # A model span may not be allowed to bridge independent document targets.
                    raise DocumentError('독립된 문서 영역 사이에 걸친 검출이 있어 안전하게 위치를 지정하지 못했습니다. 문서를 나누어 검사해 주세요.')
            if len(found)>6000:raise DocumentError('검출 후보가 6천 개를 넘었습니다. 문서를 나누어 검사해 주세요.')
        return found

    def _inspect(self,job):
        try:
            self._update(job,state='reading',progress='작업 사본에서 문서·기록·이미지 읽는 중')
            manifest=self._adapter(job,'read')
            self._update(job,state='checking',manifest=manifest)
            candidates=self._scan(job,manifest,'개인정보 검사')
            self._check_cancel(job)
            self._update(job,state='ready',candidates=candidates,progress='검토할 준비가 되었어요.')
        except Exception as e:self._failed(job,e)

    def _failed(self,job,e):
        self._update(job,state='cancelled' if job['cancel'].is_set() else 'error',error=str(e) if isinstance(e,DocumentError) else '파일 작업을 완료하지 못했습니다. 원본은 변경되지 않았습니다.',progress='')
        if job['cancel'].is_set():self._cleanup(job)

    def status(self,ident):
        with self.lock:return self._public(self._job(ident))

    def list_jobs(self):
        with self.lock:return [self._public(job) for job in self.jobs.values()]

    def _public(self,job):
        m=job['manifest']
        return {'id':job['id'],'name':job['name'],'state':job['state'],'progress':job['progress'],'revision':job['revision'],
            'error':job['error'],'candidates':copy.deepcopy(job['candidates']),
            'manifest':None if m is None else {**{k:copy.deepcopy(v) for k,v in m.items() if k not in {'parts','assets'}},
                'parts':[{k:v for k,v in p.items() if k not in {'target','boxes','ocrConfidences'}} for p in m['parts']],
                'assets':[{k:v for k,v in a.items() if k not in {'target','file'}} for a in m['assets']]},
            'exportResult':copy.deepcopy(job['exportResult'])}

    def asset(self,ident,asset_id,output=False):
        job=self._job(ident);manifest=job.get('outputManifest') if output else job['manifest']
        if not manifest:raise DocumentError('미리보기가 아직 준비되지 않았습니다.')
        a=next((a for a in manifest['assets'] if a['id']==asset_id),None)
        if not a:raise DocumentError('미리보기 위치를 찾을 수 없습니다.')
        return job['work']/('verification' if output else '')/a['file']

    def preview(self,ident,output=False,retry=False):
        job=self._job(ident);key='output' if output else 'source'
        self._check_cancel(job)
        self._unchanged(job)
        if output and job.get('exportResult'):self.output(ident)
        with self.lock:
            version=(job.get('exportResult') or {}).get('sha256') if output else job['hash']
            cached=job['previews'].get(key)
            if cached and cached['version']==version and not (retry and cached['state']=='error'):
                return self._public_preview(cached)
            if not version or job['state']!='ready':raise DocumentError('검사와 사본 생성이 끝난 뒤 문서 화면을 열어 주세요.')
            if not job['manifest'] or job['manifest']['kind'] not in {'.docx','.pptx'}:
                raise DocumentError('이 형식은 텍스트·셀 또는 이미지 화면에서 확인해 주세요.')
            self._unchanged(job)
            if cached and cached['state'] in {'ready','error'}:
                previous=(job['work']/cached['directory']).resolve()
                if previous.is_relative_to(job['work'].resolve()) and previous.name.startswith('preview-'):
                    shutil.rmtree(previous,ignore_errors=True)
            directory='preview-'+key+'-'+secrets.token_hex(6)
            cached={'state':'queued','version':version,'directory':directory,'pages':[],'links':{},'warnings':[]}
            job['previews'][key]=cached
            self.pool.submit(self._preview,job,key,cached)
            return self._public_preview(cached)

    @staticmethod
    def _public_preview(value):
        return {k:copy.deepcopy(v) for k,v in value.items() if k not in {'directory'}} | {
            'pages':[{k:v for k,v in p.items() if k!='file'} for p in value['pages']]}

    def _preview(self,job,key,cached):
        try:
            self._check_cancel(job);self._unchanged(job)
            output=key=='output'
            if output and (job.get('exportResult') or {}).get('sha256')!=cached['version']:return
            if output:self.output(job['id'])
            manifest=job.get('outputManifest') if output else job['manifest']
            candidates=job['exportResult']['candidates'] if output else job['candidates']
            with self.lock:cached['state']='rendering'
            value=self._adapter(job,'preview',source=job['output'] if output else job['source'],
                previewDirectory=cached['directory'],parts=manifest['parts'],candidates=candidates)
            self._check_cancel(job);self._unchanged(job)
            if output:self.output(job['id'])
            with self.lock:
                if job['previews'].get(key) is cached:cached.update(value)
        except Exception as e:
            with self.lock:
                cached.update(state='error',message=str(e) if isinstance(e,DocumentError) else '문서 화면을 만들지 못했습니다. 텍스트 · 위치에서 계속 검토해 주세요.')
            if job['cancel'].is_set():self._cleanup(job)

    def preview_asset(self,ident,page,output=False):
        job=self._job(ident);self._check_cancel(job);self._unchanged(job)
        if output:self.output(ident)
        value=job['previews'].get('output' if output else 'source')
        version=(job.get('exportResult') or {}).get('sha256') if output else job['hash']
        if not value or value['state']!='ready' or value['version']!=version or type(page) is not int or not 0<=page<len(value['pages']):
            raise DocumentError('문서 화면이 아직 준비되지 않았거나 바뀌었습니다. 다시 열어 주세요.')
        return job['work']/value['directory']/value['pages'][page]['file']

    def export(self,ident,revision,choices,manual,text_edits=None):
        job=self._job(ident)
        with self.lock:
            if job['state']!='ready' or revision!=job['revision']:raise DocumentError('현재 검사 결과와 일치하지 않습니다. 준비가 끝난 뒤 다시 시도해 주세요.')
            if job['manifest']['blockers']:raise DocumentError(job['manifest']['blockers'][0])
            if not isinstance(choices,dict) or len(choices)>6000 or not isinstance(manual,list) or len(manual)>1000:raise DocumentError('선택한 항목 수가 올바르지 않습니다.')
            known={c['id']:c for c in job['candidates']}
            if any(k not in known for k in choices):raise DocumentError('검사 결과에 없는 항목입니다.')
            edits={};regions=[]; parts={p['id']:p for p in job['manifest']['parts']}
            for p in parts.values():
                selected=[c for c in job['candidates'] if c['part']==p['id'] and choices.get(c['id'],{}).get('mode','keep')!='keep']
                if not selected:continue
                value=p['text'];is_image=bool(p.get('asset'))
                for c in sorted(selected,key=lambda c:c['start'],reverse=True):
                    choice=choices[c['id']]
                    if not isinstance(choice,dict):raise DocumentError('가림 선택이 올바르지 않습니다.')
                    new=replacement(c['text'],c['label'],choice)
                    if is_image:
                        if choice.get('mode')=='custom':raise DocumentError('PDF·이미지는 영역 가림을 이용해 주세요.')
                        regions.extend({'asset':p['asset'],'box':b} for b in c['maskBoxes'][choice['mode']])
                    else:
                        lo,hi=py_offset(value,c['start']),py_offset(value,c['end'])
                        if value[lo:hi]!=c['text']:raise DocumentError('수정할 위치가 원문과 일치하지 않습니다.')
                        value=value[:lo]+new+value[hi:]
                if not is_image:edits[p['id']]=value
            for pid,value in (text_edits or {}).items():
                part=parts.get(pid)
                if not part or part.get('asset') or part['target']['kind']=='readonly':raise DocumentError('직접 수정할 수 없는 영역입니다.')
                if not isinstance(value,str) or len(value)>12000 or any(0xd800<=ord(c)<=0xdfff or ord(c)<32 and c not in '\n\t\r' for c in value):raise DocumentError('직접 수정은 영역당 12,000자 이하로 입력해 주세요.')
                edits[pid]=value
            assets={a['id']:a for a in job['manifest']['assets']}
            for r in manual:
                if not isinstance(r,dict) or r.get('asset') not in assets or not isinstance(r.get('box'),list):raise DocumentError('직접 지정한 영역이 올바르지 않습니다.')
                b=r['box'];a=assets[r['asset']]
                if len(b)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in b) or not(0<=b[0]<b[2]<=a['width'] and 0<=b[1]<b[3]<=a['height']):raise DocumentError('직접 지정한 영역이 이미지 밖에 있습니다.')
                regions.append({'asset':r['asset'],'box':b})
            if len(regions)>20000:raise DocumentError('가림 영역이 너무 많습니다. 문서를 나누어 처리해 주세요.')
            job.update(state='exporting',progress='선택한 내용을 새 사본에 적용하는 중',exportResult=None,output=None,error=None)
            self.pool.submit(self._export,job,edits,regions)
            return self._public(job)

    def _export(self,job,edits,regions):
        try:
            self._unchanged(job)
            output='reviewed'+job['manifest']['outputSuffix']
            manifest=self._adapter(job,'export',output=output,edits=edits,regions=regions)
            candidates=self._scan(job,manifest,'수정 사본 재검사')
            self._check_cancel(job);self._unchanged(job)
            filename=Path(job['name']).stem[:80]+'_개인정보처리본_'+time.strftime('%Y%m%d_%H%M%S')+job['manifest']['outputSuffix']
            self._update(job,state='ready',progress='수정 사본을 다시 열어 검사했습니다. 결과를 확인한 뒤 저장해 주세요.',output=output,outputManifest=manifest,
                exportResult={'filename':filename,'candidates':candidates,'parts':[{k:v for k,v in p.items() if k not in {'target','boxes','ocrConfidences'}} for p in manifest['parts']],
                              'assets':[{k:v for k,v in a.items() if k not in {'target','file'}} for a in manifest['assets']],
                              'warnings':manifest['warnings'],'tableSize':manifest.get('tableSize'),'sha256':digest(job['work']/output)})
        except Exception as e:
            self._failed(job,e)
            if not job['cancel'].is_set():self._update(job,state='ready',output=None)

    def output(self,ident):
        job=self._job(ident)
        if job['state']!='ready' or not job['output'] or not job['exportResult']:raise DocumentError('검증된 수정 사본이 없습니다.')
        self._unchanged(job)
        path=job['work']/job['output']
        if digest(path)!=job['exportResult']['sha256']:raise DocumentError('수정 사본이 변경되었습니다. 다시 생성해 주세요.')
        return path,job['exportResult']['filename']

    def save_new(self,ident,destination):
        source,name=self.output(ident);dest=Path(destination).resolve()
        if dest.suffix.lower()!=source.suffix.lower():raise DocumentError('파일 확장자를 바꾸지 말고 저장해 주세요.')
        temp=None
        # Stage a complete file beside the destination. Publish without replacing any existing path.
        try:
            if dest.exists():raise FileExistsError()
            with tempfile.NamedTemporaryFile(dir=dest.parent,prefix='.before-post-copy-',suffix='.tmp',delete=False) as f:
                temp=Path(f.name);f.write(source.read_bytes());f.flush();os.fsync(f.fileno())
            if os.name=='nt':os.rename(temp,dest)  # Windows rename fails when the destination exists.
            else:os.link(temp,dest)
        except FileExistsError:raise DocumentError('기존 파일에는 덮어쓰지 않습니다. 새 파일 이름을 선택해 주세요.')
        except OSError:raise DocumentError('선택한 위치에 사본을 저장하지 못했습니다.')
        finally:
            if temp is not None:temp.unlink(missing_ok=True)
        return {'saved':True,'name':dest.name}

    def cancel(self,ident):
        job=self._job(ident);job['cancel'].set()
        if job['state'] in {'ready','error','cancelled','queued'}:
            self._update(job,state='cancelled');self._cleanup(job)
        return {'cancelled':True}

    def remove(self,ident):
        self.cancel(ident)
        with self.lock:self.jobs.pop(ident,None)
        return {'removed':True}

    def _cleanup(self,job):
        if not job.get('process'):shutil.rmtree(job['work'],ignore_errors=True)

    def close(self):
        self.closed=True
        with self.lock:
            for job in self.jobs.values():job['cancel'].set()
        self.pool.shutdown(wait=True,cancel_futures=True)
        shutil.rmtree(self.root,ignore_errors=True)
