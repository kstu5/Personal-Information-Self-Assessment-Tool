import {useEffect,useRef,useState} from 'react';
import {api,boot} from './api';
import type {Box,DocumentJob,DocumentPreview,FileAsset,FileCandidate,FileSelection} from './documentTypes';
import {RISKS} from './masking';
import {MODE_NAMES} from './masking';
import {draftStatus,fileReplacement} from './documentDraft';

export function CandidateOverlay({asset,candidates,selection,boxes,onSelect}:{asset:FileAsset;candidates:FileCandidate[];selection:FileSelection;boxes:(c:FileCandidate)=>{boxes:Box[];ambiguous?:boolean};onSelect:(c:FileCandidate)=>void}){
  const search=selection.search.trim().toLocaleLowerCase('ko');
  return <>{candidates.filter(c=>(selection.filter==='all'||selection.filter===c.risk)&&(!search||`${c.text} ${c.labelName} ${c.location}`.toLocaleLowerCase('ko').includes(search))).map(c=>{
    const hit=boxes(c),status=draftStatus(c,selection),assigned=status!=='unset';return hit.boxes.map((b,i)=><button key={`${c.id}:${i}`} type="button" className={`document-hit risk-${c.risk} ${selection.focus===c.id?'focused':''} ${hit.ambiguous?'uncertain':''} ${assigned?'planned':''} ${status==='keep'?'kept':''}`}
      style={{left:`${b[0]/asset.width*100}%`,top:`${b[1]/asset.height*100}%`,width:`${(b[2]-b[0])/asset.width*100}%`,height:`${(b[3]-b[1])/asset.height*100}%`}}
      aria-label={`${c.labelName} ${c.text} 문서에서 선택`} title={`${RISKS.find(r=>r.key===c.risk)?.name} · ${c.labelName} · ${c.text} · ${status==='unset'?'처리 미설정':status==='text'?'영역 직접 수정':MODE_NAMES[status]+' 지정'}${hit.ambiguous?' · 원문 위치 확인 필요':''}`}
      onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();onSelect(c);}}>{assigned&&i===0&&<span className="document-hit-check" aria-hidden="true">✓</span>}</button>);
  })}</>;
}

function DraftPageLayer({asset,page,preview,candidates,selection}:{asset:FileAsset;page:number;preview:DocumentPreview;candidates:FileCandidate[];selection:FileSelection}){
  return <div className="draft-page-layer" aria-label="가림·수정 적용 예상 표시">{candidates.map(c=>{
    const choice=selection.choices[c.id],link=preview.links[c.id];
    if(!choice||choice.mode==='keep'||c.part in selection.textEdits||link?.state!=='linked')return null;
    const boxes=link.hits.filter(h=>h.page===page).flatMap(h=>h.boxes);
    return boxes.map((b,i)=><span key={`${c.id}:${i}`} className={`draft-replacement ${choice.mode==='full'?'full':''}`} data-candidate={c.id}
      style={{left:`${b[0]/asset.width*100}%`,top:`${b[1]/asset.height*100}%`,width:`${(b[2]-b[0])/asset.width*100}%`,height:`${(b[3]-b[1])/asset.height*100}%`,fontSize:`${(b[3]-b[1])*.78/asset.width*100}cqw`}}
      title={`${MODE_NAMES[choice.mode]} → ${fileReplacement(c,choice)||'(빈 내용)'}`}><span>{i===0&&choice.mode!=='full'?fileReplacement(c,choice):''}</span></span>);
  })}</div>;
}

export function OfficePreview({job,output,selection,candidates,onState,onSelect,onReady,onText}:{job:DocumentJob;output:boolean;selection:FileSelection;candidates:FileCandidate[];onState:(p:Partial<FileSelection>)=>void;onSelect:(c:FileCandidate)=>void;onReady:(p:DocumentPreview)=>void;onText:()=>void}){
  const [preview,setPreview]=useState<DocumentPreview|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0),[url,setUrl]=useState('');
  const onReadyRef=useRef(onReady);onReadyRef.current=onReady;
  const version=output?job.exportResult?.sha256:'source',enabled=job.state==='ready';
  useEffect(()=>{
    const abort=new AbortController();let stopped=false,timer:ReturnType<typeof setTimeout>;
    setPreview(null);setError('');
    if(!enabled)return;
    async function poll(first=false){
      try{
        const p=await api<DocumentPreview>('documents/preview',{id:job.id,output,retry:first&&retry>0},abort.signal);
        if(stopped)return;setPreview(p);
        if(p.state==='ready')onReadyRef.current(p);
        else if(p.state==='queued'||p.state==='rendering')timer=setTimeout(()=>void poll(),800);
      }catch(e){if(!stopped)setError(e instanceof Error?e.message:'문서 화면을 만들지 못했습니다.');}
    }
    void poll(true);return()=>{stopped=true;abort.abort();clearTimeout(timer);};
  },[job.id,output,version,enabled,retry]);
  const page=Math.min(selection.previewPage,Math.max(0,(preview?.pages.length||1)-1)),asset=preview?.pages[page];
  useEffect(()=>{
    let stopped=false,local='';const abort=new AbortController();setUrl('');
    if(!asset||!preview||preview.state!=='ready')return;
    void fetch(`/api/documents/${job.id}/preview/${page}?output=${output}`,{signal:abort.signal,headers:{'X-App-Token':boot.token},cache:'no-store'}).then(async r=>{if(!r.ok)throw new Error('문서 페이지를 읽지 못했습니다.');return r.blob();}).then(blob=>{local=URL.createObjectURL(blob);if(!stopped)setUrl(local);else URL.revokeObjectURL(local);}).catch(e=>{if(!stopped)setError(e instanceof Error?e.message:'페이지를 읽지 못했습니다.');});
    return()=>{stopped=true;abort.abort();if(local)URL.revokeObjectURL(local);};
  },[job.id,page,output,preview?.version,preview?.state,asset?.id]);
  const focus=selection.focus?preview?.links[selection.focus]:null;
  const applied=!output&&selection.draftView==='applied';
  const outside=candidates.filter(c=>draftStatus(c,selection)!=='unset'&&draftStatus(c,selection)!=='keep'&&
    (c.part in selection.textEdits||preview?.links[c.id]?.state!=='linked')).length;
  return <section className="document-preview office-preview" aria-label={output?'수정 사본 문서 화면':'원본 문서 화면'}>
    <div className="office-preview-toolbar"><strong>{output?'실제 수정 사본':applied?'적용 미리보기 · 저장 전':'원본 문서 화면'}</strong>{preview?.state==='ready'&&<label>페이지<select aria-label="문서 페이지" value={page} onChange={e=>onState({previewPage:Number(e.target.value)})}>{preview.pages.map((p,i)=><option key={p.id} value={i}>{p.location}</option>)}</select></label>}</div>
    {(!enabled||!preview||preview.state==='queued'||preview.state==='rendering')&&!error&&<div className="office-preview-state" role="status"><span className="spinner"/>{enabled?'문서 화면을 준비하고 있습니다. 처음에는 잠시 걸릴 수 있어요.':'작업이 끝나면 문서 화면을 표시합니다.'}</div>}
    {(error||preview?.state==='error')&&<div className="office-preview-state" role="alert"><p>{error||preview?.message}</p><button className="secondary" onClick={onText}>텍스트로 계속 검토</button><button className="secondary" disabled={!enabled} onClick={()=>setRetry(n=>n+1)}>다시 만들기</button></div>}
    {asset&&preview?.state==='ready'&&<><div className="office-page-viewport"><div className="office-page" style={{aspectRatio:`${asset.width}/${asset.height}`}}>{url?<img src={url} alt={`${job.name} ${asset.location} ${output?'실제 수정 사본':'원본 미리보기'}`}/>:<p role="status">페이지를 읽는 중…</p>}
      {url&&applied&&<DraftPageLayer asset={asset} page={page} preview={preview} candidates={candidates} selection={selection}/>}
      {url&&<CandidateOverlay asset={asset} candidates={candidates} selection={selection} boxes={c=>{const link=preview.links[c.id];return {boxes:link?.hits.filter(h=>h.page===page).flatMap(h=>h.boxes)||[],ambiguous:link?.state==='ambiguous'};}} onSelect={onSelect}/>}</div></div>
      <p className="office-preview-note">{output?'저장할 수정 사본을 다시 열어 만든 화면입니다.':applied?'선택한 가림·수정을 원본 위치에 겹쳐 보여주는 간이 미리보기입니다. 긴 문구는 잘려 보이며 줄바꿈·배경·서식은 실제 사본과 다를 수 있습니다. 최종 결과는 사본 생성 후 확인하세요.':'원본 내용입니다. 체크 표시는 처리 방법을 지정한 항목입니다. 적용 미리보기로 전환해 변경 모습을 비교하세요.'} {applied&&outside>0&&<strong>페이지에 표시하지 못한 변경 {outside}개는 텍스트 · 위치에서 확인하세요. </strong>}{focus?.state==='ambiguous'&&<strong>같은 문구가 반복되거나 문단 연결이 불확실합니다. 원문 위치를 함께 확인하세요. </strong>}<button onClick={onText}>화면 밖 정보·원문 위치 확인</button></p>
      <details className="office-preview-limits"><summary>페이지 화면의 확인 범위</summary>{preview.warnings.map(v=><p key={v}>{v}</p>)}<p>실선은 문단 문맥과 연결한 위치이며, 점선은 추가 위치 확인이 필요한 문구입니다. 메모·발표자 노트·문서 속성은 검출 목록에서 계속 확인할 수 있습니다.</p></details>
    </>}
  </section>;
}
