import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { api, boot } from './api';
import { candidateSummary, defaultChoices, MODE_NAMES, RISKS, partialMask } from './masking';
import type { MaskChoice, MaskChoices, MaskMode } from './masking';
import type { Box, DocumentJob, DocumentPreview, FileAsset, FileCandidate, FilePart, FileSelection, Region, TableSize } from './documentTypes';
import { EMPTY_SELECTION } from './documentTypes';
import { FileFindings } from './FileFindings';
import { FileKeywordSearch } from './FileKeywordSearch';
import {OfficePreview,CandidateOverlay} from './OfficePreview';
import {PageNavigation} from './PageNavigation';
import {FileProgress,fileProgressStatus} from './FileProgress';
import {bulkChoicesToUndo,bulkMaskTargets,draftChunks,draftStatus,fileReplacement as replacement} from './documentDraft';
import {readSourceRange,rangeConflict,sourceCaret,showSourceRange} from './sourceSelection';
import type {SourceRange} from './sourceSelection';
import {previewView,readingParts,contentPage} from './filePreview';
import {revealFileEditor} from './fileEditor';
import {createFileDropHandlers} from './fileDrop';
import {pickInspectionFiles} from './filePicker';
import './file-review.css';
import './document-preview.css';

const ACTIVE=new Set(['queued','reading','checking','exporting']);
const accept='.hwp,.hwpx,.docx,.xlsx,.pptx,.pdf,.csv,.tsv,.txt,.png,.jpg,.jpeg';
const riskName=(risk:string)=>RISKS.find(r=>r.key===risk)?.name||risk;
const message=(e:unknown)=>e instanceof Error?e.message:'파일 작업을 완료하지 못했습니다.';
async function binary(path:string,options:RequestInit={}) {
  const r=await fetch(`/api/documents/${path}`,{...options,cache:'no-store',headers:{'X-App-Token':boot.token,...options.headers}});
  if(!r.ok){let m='파일을 읽지 못했습니다.';try{m=(await r.json()).message||m;}catch{/* no source data in error */}throw new Error(m);}
  return r;
}

function ImageReview({job,asset,regions,onRegion,onOriginal,output,selectedBoxes,locked,candidates,selection,onSelect}:{job:DocumentJob;asset:FileAsset;regions:Region[];onRegion:(box:Box)=>void;onOriginal:()=>void;output:boolean;selectedBoxes:Box[];locked:boolean;candidates:FileCandidate[];selection:FileSelection;onSelect:(c:FileCandidate)=>void}) {
  const [url,setUrl]=useState(''),[error,setError]=useState(''),[drag,setDrag]=useState<Box|null>(null);
  const [warnings,setWarnings]=useState<{box:Box;message:string}[]>([]);
  const [loading,setLoading]=useState(true);
  const [drawing,setDrawing]=useState(false),[markers,setMarkers]=useState(false);
  const [pending,setPending]=useState<Box|null>(null);
  const resizing=useRef<{corner:number;box:Box}|null>(null);
  const start=useRef<[number,number]|null>(null);
  const applied=!output&&selection.draftView==='applied';
  const natural=['.png','.jpg','.jpeg'].includes(job.manifest?.kind||'');
  const draftKey=natural&&applied?JSON.stringify([selection.choices,regions]):'';
  const identity=`${job.id}:${asset.id}:${output}:${applied}`,previousIdentity=useRef(identity);
  useEffect(()=>()=>{if(url)URL.revokeObjectURL(url);},[url]);
  useEffect(()=>{let stop=false;const controller=new AbortController();setLoading(true);setError('');setWarnings([]);
    if(previousIdentity.current!==identity){setUrl('');previousIdentity.current=identity;}
    async function show(path:string){
      const b=await (await binary(path,{signal:controller.signal})).blob();
      const local=URL.createObjectURL(b);if(!stop){setUrl(local);setLoading(false);}else URL.revokeObjectURL(local);
    }
    async function load(){
      let path=`${job.id}/assets/${asset.id}?output=${output}`;
      if(natural&&applied){
        if(job.state!=='ready')return;
        const [choices,manual]=JSON.parse(draftKey);
        const deadline=Date.now()+60000;
        while(!stop){
          const result=await api<{state:string;version:string;message?:string;warnings?:{box:Box;message:string}[]}>('documents/image-preview',{id:job.id,revision:job.revision,choices,regions:manual},controller.signal);
          if(stop)return;
          if(result.state==='error')throw new Error(result.message||'이미지 미리보기를 만들지 못했습니다.');
          if(result.state==='ready'){path=`${job.id}/image-preview/${result.version}`;setWarnings(result.warnings||[]);break;}
          if(Date.now()>deadline)throw new Error('미리보기 준비가 지연됩니다. 원본으로 전환한 뒤 다시 확인해 주세요.');
          await new Promise(resolve=>setTimeout(resolve,300));
        }
      }
      if(stop)return;
      await show(path);
    }
    const timer=setTimeout(()=>{void load().catch(async e=>{
      if(stop)return;
      setError(message(e)+(natural&&applied?' 적용 결과 대신 원본을 표시합니다. 문구를 수정한 뒤 다시 확인해 주세요.':''));
      if(natural&&applied)try{await show(`${job.id}/assets/${asset.id}?output=false`);}catch{if(!stop){setUrl('');setLoading(false);}}
      else setLoading(false);
    });},natural&&applied?300:0);
    return()=>{stop=true;clearTimeout(timer);controller.abort();};
  },[job.id,asset.id,output,job.exportResult?.sha256,job.revision,job.state,applied,natural,draftKey,identity]);
  function point(e:PointerEvent<HTMLDivElement>):[number,number]{const r=e.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(asset.width,(e.clientX-r.left)*asset.width/r.width)),Math.max(0,Math.min(asset.height,(e.clientY-r.top)*asset.height/r.height))];}
  function rectangle(b:Box,key:string,kind:string){return <span key={key} className={`region-box ${kind}`} style={{left:`${b[0]/asset.width*100}%`,top:`${b[1]/asset.height*100}%`,width:`${(b[2]-b[0])/asset.width*100}%`,height:`${(b[3]-b[1])/asset.height*100}%`}}/>;}
  return <div className="image-review" id={`file-asset-${asset.id}`}>
    <p>{error&&natural&&applied?'수정을 적용하지 못해 원본을 표시합니다.':output?'저장할 사본의 실제 이미지입니다.':applied?natural?'원문 영역을 지우고 선택한 문구를 다시 쓴 모습입니다. 경고가 없는 결과는 저장 사본에도 같은 방식으로 적용합니다.':'적용 미리보기입니다. 선택한 가림과 직접 지정한 영역을 검게 표시합니다.':'원본 이미지입니다. 체크는 처리 지정, 점선은 직접 지정한 가림 영역입니다.'}</p>
    {(applied||output)&&<label><input type="checkbox" checked={markers} onChange={e=>setMarkers(e.target.checked)}/>검출 표시 보기</label>}
    {!output&&<button className="secondary image-draw-toggle" disabled={locked||loading} aria-pressed={drawing} onClick={()=>{if(!drawing)onOriginal();setDrawing(v=>!v);setPending(null);}}>{drawing?'영역 지정 취소':'직접 영역 가리기'}</button>}
    {!output&&pending&&<section className="pending-region" aria-label="선택한 이미지 영역"><strong>선택한 영역 확인</strong><p>모서리를 드래그해 범위를 조정하세요. 확정 전에는 가림에 포함되지 않습니다.</p><svg role="img" aria-label="선택 영역 확대" viewBox={`${pending[0]} ${pending[1]} ${pending[2]-pending[0]} ${pending[3]-pending[1]}`} style={{aspectRatio:`${pending[2]-pending[0]}/${pending[3]-pending[1]}`}}><image href={url} width={asset.width} height={asset.height}/></svg><div className="source-range-actions"><button className="primary" disabled={locked||loading} onClick={()=>{onRegion(pending);setPending(null);setDrawing(false);}}>이 영역 가림 적용</button><button disabled={locked} onClick={()=>setPending(null)}>다시 선택</button><button disabled={locked} onClick={()=>{setPending(null);setDrawing(false);}}>취소</button></div></section>}
    {error&&<p role="alert">{error}</p>}
    {!!warnings.length&&<div className="image-edit-warnings" role="alert"><strong>일부 문구를 적용하지 못했습니다.</strong><p>빨간 테두리의 항목은 원문을 보여줍니다. 문구를 바꾸기 전에는 수정 사본을 생성할 수 없습니다.</p><ul>{warnings.map((w,i)=><li key={i}>{w.message}</li>)}</ul></div>}
    {loading&&!error&&<p role="status">{url?'변경 사항을 적용하는 중입니다. 아래는 갱신 전 미리보기입니다.':'미리보기 준비 중…'}</p>}
    {(url||loading)&&<div className={`image-canvas ${output||!drawing?'readonly':''}`} aria-busy={loading} style={{aspectRatio:`${asset.width}/${asset.height}`}}
      onPointerDown={e=>{if(output||locked||loading||!url||!drawing)return;e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);setPending(null);start.current=point(e);setDrag([...start.current,...start.current]);}}
      onPointerMove={e=>{const p=point(e);if(resizing.current){const {corner,box}=resizing.current,b:Box=[...box];if(corner%2===0)b[0]=Math.min(p[0],b[2]-3);else b[2]=Math.max(p[0],b[0]+3);if(corner<2)b[1]=Math.min(p[1],b[3]-3);else b[3]=Math.max(p[1],b[1]+3);setPending(b);return;}if(!start.current)return;const s=start.current;setDrag([Math.min(s[0],p[0]),Math.min(s[1],p[1]),Math.max(s[0],p[0]),Math.max(s[1],p[1])]);}}
      onPointerUp={e=>{if(resizing.current){resizing.current=null;return;}if(output||locked||!drawing){start.current=null;setDrag(null);return;}if(!start.current)return;const p=point(e),s=start.current;const b:Box=[Math.min(s[0],p[0]),Math.min(s[1],p[1]),Math.max(s[0],p[0]),Math.max(s[1],p[1])];start.current=null;setDrag(null);if(b[2]-b[0]>2&&b[3]-b[1]>2)setPending(b);}}
      onPointerCancel={()=>{start.current=null;resizing.current=null;setDrag(null);}}>
      {url&&<img src={url} alt={`${asset.location} ${loading?'갱신 전 미리보기':error&&natural&&applied?'수정 실패 · 원본':output?'수정 사본':applied?'적용 미리보기':'원본 사본'}`} draggable={false}/>}
      {url&&!drawing&&(!(applied||output)||markers)&&<CandidateOverlay asset={asset} candidates={candidates.filter(c=>c.asset===asset.id)} selection={selection} boxes={c=>({boxes:c.maskBoxes?.full||c.boxes||[]})} onSelect={onSelect}/>}
      {applied&&!natural&&selectedBoxes.map((b,i)=>rectangle(b,`candidate-${i}`,'opaque'))}
      {!output&&!(applied&&natural)&&regions.filter(r=>r.asset===asset.id).map((r,i)=>rectangle(r.box,`manual-${i}`,applied?'opaque':'region-outline'))}
      {drag&&rectangle(drag,'drag','drawing')}
      {pending&&rectangle(pending,'pending','drawing')}
      {pending&&[0,1,2,3].map(corner=><button key={corner} type="button" className="region-resize" disabled={locked||loading} aria-label={`영역 ${['왼쪽 위','오른쪽 위','왼쪽 아래','오른쪽 아래'][corner]} 모서리 조정`} style={{left:`${pending[corner%2===0?0:2]/asset.width*100}%`,top:`${pending[corner<2?1:3]/asset.height*100}%`}} onPointerDown={e=>{e.stopPropagation();e.preventDefault();resizing.current={corner,box:pending};e.currentTarget.parentElement!.setPointerCapture(e.pointerId);}} onKeyDown={e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)||locked)return;e.preventDefault();const b:Box=[...pending],step=e.shiftKey?10:1;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){const i=corner%2===0?0:2;b[i]=Math.max(i===0?0:b[0]+3,Math.min(i===0?b[2]-3:asset.width,b[i]+(e.key==='ArrowLeft'?-step:step)));}else{const i=corner<2?1:3;b[i]=Math.max(i===1?0:b[1]+3,Math.min(i===1?b[3]-3:asset.height,b[i]+(e.key==='ArrowUp'?-step:step)));}setPending(b);}}/>)}
      {warnings.map((w,i)=>rectangle(w.box,`warning-${i}`,'edit-warning'))}
    </div>}
  </div>;
}

function Highlight({part,candidates,selection,onSelect,output=false}:{part:FilePart;candidates:FileCandidate[];selection:FileSelection;onSelect:(c:FileCandidate)=>void;output?:boolean}) {
  return <div className="file-part-text" data-source-part={part.id} data-source-selectable={!output&&selection.draftView==='original'&&!(part.id in selection.textEdits)}>{draftChunks(part,candidates,selection,!output&&selection.draftView==='applied').map((chunk,i)=>{
    const c=chunk.candidate;if(!c)return chunk.text;
    const assigned=!output&&draftStatus(c,selection)!=='unset';
    return <mark key={`${c.id}:${i}`} role="button" tabIndex={0} aria-label={`${c.labelName} ${c.text} 편집`} className={`file-highlight risk-${c.risk} ${selection.focus===c.id?'focused':''} ${assigned?'has-draft-choice':''}`} title={`${riskName(c.risk)} · ${c.labelName} · ${c.location}`} onClick={()=>onSelect(c)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(c);}}}>{chunk.text}</mark>;
  })}</div>;
}

function ContentReview({job,parts,candidates,selection,onChange,onSelect,onText,output}:{job:DocumentJob;parts:FilePart[];candidates:FileCandidate[];selection:FileSelection;onChange:(p:Partial<FileSelection>)=>void;onSelect:(c:FileCandidate)=>void;onText:()=>void;output:boolean}) {
  const body=readingParts(parts),pages=Math.max(1,Math.ceil(body.length/30)),page=Math.min(selection.page,pages-1),other=parts.length-body.length;
  return <section className="document-preview content-preview" aria-label="문서 내용 미리보기"><div className="content-preview-heading"><strong>내용 미리보기 · {output?'실제 수정 사본':selection.draftView==='applied'?'적용 예정':'원본 내용'}</strong><span>{job.manifest?.kind==='.hwp'?'추출 본문 · 읽기 전용':'읽어낸 본문 순서'}</span></div><p className="content-preview-note">읽어낸 내용을 보기 좋게 재구성했습니다. 원래 문서의 페이지·표 배치·글꼴과 다릅니다.{job.manifest?.kind==='.hwp'?' HWP는 수정 사본을 저장할 수 없습니다.':''}{other>0&&` 본문 밖 ${other}개 영역도 확인하세요.`} <button onClick={onText}>전체 위치·부가 정보 확인</button></p>
    {!body.length?<p>본문의 위치 정보가 없습니다. 파일을 다시 검사하거나 텍스트 · 위치에서 확인해 주세요. <button onClick={onText}>텍스트로 보기</button></p>:<div className="content-paper">{body.slice(page*30,(page+1)*30).map((p,i,shown)=>{const gap=p.flow?.line&&shown[i-1]?.flow?.line?Math.min(4,p.flow.line-shown[i-1].flow!.line!-1):0;return <article id={`file-part-${p.id}`} key={p.id} className={`${i===0&&page===0?'content-first':''} ${selection.focus&&candidates.some(c=>c.id===selection.focus&&c.part===p.id)?'content-focused':''}`} style={{marginTop:gap?`${gap}em`:undefined}}><span className="content-location">{p.location}</span><Highlight part={p} candidates={candidates} selection={selection} output={output} onSelect={onSelect}/></article>;})}</div>}
    <div className="preview-pagination"><button disabled={!page} onClick={()=>onChange({page:page-1})}>이전 구간</button><span>내용 구간 {page+1}/{pages}</span><button disabled={page+1>=pages} onClick={()=>onChange({page:page+1})}>다음 구간</button></div></section>;
}

function SheetReview({parts,candidates,selection,onChange,onSelect,onEdit,output,locked,size,kind}:{parts:FilePart[];candidates:FileCandidate[];selection:FileSelection;onChange:(p:Partial<FileSelection>)=>void;onSelect:(c:FileCandidate)=>void;onEdit:(p:FilePart)=>void;output:boolean;locked:boolean;size?:TableSize|null;kind:string}) {
  const sheets=Array.from(new Set(parts.filter(p=>p.sheet).map(p=>p.sheet!)));
  const sheet=sheets.includes(selection.sheet)?selection.sheet:sheets[0];
  const cells=parts.filter(p=>p.sheet===sheet&&p.row&&p.column);
  const rows=Math.max(1,size?.rows||0,...cells.map(p=>p.row!)),columns=Math.max(1,size?.columns||0,...cells.map(p=>p.column!));
  const rowPage=Math.min(selection.gridRow,Math.floor((rows-1)/30)),colPage=Math.min(selection.gridColumn,Math.floor((columns-1)/10));
  const byCell=new Map(cells.map(p=>[`${p.row}:${p.column}`,p]));
  const letter=(n:number)=>{let v='';while(n>0){n--;v=String.fromCharCode(65+n%26)+v;n=Math.floor(n/26);}return v;};
  return <section className="document-preview"><label className="asset-picker">시트 선택<select value={sheet||''} onChange={e=>onChange({sheet:e.target.value,gridRow:0,gridColumn:0})}>{sheets.map(sh=><option key={sh}>{sh}</option>)}</select></label><p className="sheet-note">{kind==='.xlsx'?'계산 결과와 셀 위치를 보여줍니다. 숨김 셀도 표시하며, 메모·작성자·문서 속성은 텍스트 · 위치 탭에서 확인하세요.':'행·열과 빈 셀 위치를 유지한 표입니다. 첫 행도 원본 데이터로 표시합니다. 수정할 셀이나 개인정보 표시를 선택하세요.'}</p><div className="sheet-grid"><table><thead><tr><th aria-label="행 번호"/>{Array.from({length:Math.min(10,columns-colPage*10)},(_,i)=><th key={i}>{letter(colPage*10+i+1)}</th>)}</tr></thead><tbody>{Array.from({length:Math.min(30,rows-rowPage*30)},(_,i)=>{const row=rowPage*30+i+1;return <tr key={row}><th>{row}</th>{Array.from({length:Math.min(10,columns-colPage*10)},(_,j)=>{const column=colPage*10+j+1,p=byCell.get(`${row}:${column}`);return <td key={column} id={p?`file-part-${p.id}`:undefined} className={p?.hidden?'hidden-cell':''}>{p&&<><span className="cell-address">{p.cell}{p.hidden?' · 숨김':''}</span><Highlight part={p} candidates={candidates} selection={selection} output={output} onSelect={onSelect}/>{!output&&<button disabled={locked} className="cell-edit" onClick={()=>onEdit(p)} aria-label={`${p.cell} 직접 수정`}>수정</button>}</>}</td>;})}</tr>;})}</tbody></table></div><div className="preview-pagination"><button disabled={!rowPage} onClick={()=>onChange({gridRow:rowPage-1})}>이전 행</button><span>{rowPage*30+1}–{Math.min(rows,(rowPage+1)*30)}행</span><button disabled={(rowPage+1)*30>=rows} onClick={()=>onChange({gridRow:rowPage+1})}>다음 행</button><button disabled={!colPage} onClick={()=>onChange({gridColumn:colPage-1})}>이전 열</button><button disabled={(colPage+1)*10>=columns} onClick={()=>onChange({gridColumn:colPage+1})}>다음 열</button></div></section>;
}

export function FileReview({active,onWorkChange}:{active:boolean;onWorkChange:(work:boolean)=>void}) {
  const [jobs,setJobs]=useState<DocumentJob[]>([]),[id,setId]=useState(''),[states,setStates]=useState<Record<string,FileSelection>>({});
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[uploading,setUploading]=useState(false),[removeId,setRemoveId]=useState('');
  const [partEdit,setPartEdit]=useState<{id:string;text:string}|null>(null);
  const [fileDragging,setFileDragging]=useState(false);
  const [picking,setPicking]=useState(false);
  const [bulkPanelFor,setBulkPanelFor]=useState('');
  const [keywordAdding,setKeywordAdding]=useState('');
  const mutationLock=useRef(false),sourceDrag=useRef(false);
  const sourceAnchor=useRef<{node:Node;offset:number;x:number;y:number}|null>(null);
  const [sourceRange,setSourceRange]=useState<(SourceRange&{job:string;revision:string;replaceId?:string})|null>(null);
  const [rangeTarget,setRangeTarget]=useState<{job:string;id:string;part:string}|null>(null);
  const [rangeText,setRangeText]=useState('');
  const appliedPreviewButton=useRef<HTMLButtonElement>(null);
  const pickerLock=useRef(false);
  const [previews,setPreviews]=useState<Record<string,DocumentPreview>>({});
  const input=useRef<HTMLInputElement>(null),polling=useRef(false),uploadLock=useRef(false),jobsRef=useRef(jobs);jobsRef.current=jobs;
  const job=jobs.find(j=>j.id===id),s=states[id]||EMPTY_SELECTION;
  useEffect(()=>{setSourceRange(null);setRangeTarget(null);},[id,job?.revision,s.showOutput]);
  const working=!!job&&ACTIVE.has(job.state),locked=working||!job||job.state!=='ready'||!!job.manifest?.blockers.length||keywordAdding===id&&!!id;
  function selectState(patch:Partial<FileSelection>){setStates(old=>({...old,[id]:{...(old[id]||EMPTY_SELECTION),...patch}}));}
  function changed(patch:Partial<FileSelection>){
    if(job?.state==='ready'&&job.error)setJobs(old=>old.map(j=>j.id===id?{...j,error:null}:j));
    selectState({draftView:'applied',...patch,verified:false,exportDirty:true,showOutput:false,saved:false});
  }
  const hasWork=jobs.some(j=>ACTIVE.has(j.state)||!(states[j.id]?.saved));
  useEffect(()=>{
    let stop=false;
    void api<{files:DocumentJob[]}>('documents/list',{}).then(result=>{
      if(stop||!result.files.length)return;
      setJobs(old=>[...old,...result.files.filter(j=>!old.some(v=>v.id===j.id))]);
      setId(old=>old||result.files[0].id);
      setStates(old=>{const next={...old};for(const j of result.files)if(!next[j.id])next[j.id]={...EMPTY_SELECTION,choices:defaultChoices(j.candidates),showOutput:!!j.exportResult,view:previewView(j.manifest?.kind)};return next;});
      setNotice('현재 앱에 열려 있던 파일을 다시 연결했습니다. 화면을 새로 열기 전의 저장하지 않은 가림 선택은 복원되지 않으므로 확인해 주세요.');
    }).catch(e=>{if(!stop)setError(message(e));});
    return()=>{stop=true;};
  },[]);
  useEffect(()=>{onWorkChange(hasWork);},[hasWork,onWorkChange]);
  useEffect(()=>{const before=(e:BeforeUnloadEvent)=>{if(hasWork&&!boot.desktop){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',before);return()=>window.removeEventListener('beforeunload',before);},[hasWork]);
  useEffect(()=>{
    let stop=false;
    async function poll(){if(polling.current)return;polling.current=true;
      try{for(const j of jobsRef.current.filter(j=>ACTIVE.has(j.state))){
        const next=await api<DocumentJob>('documents/status',{id:j.id});
        if(stop)return;
        if(!jobsRef.current.some(v=>v.id===j.id))continue;
        setJobs(old=>old.map(v=>v.id===j.id?next:v));
        if(next.state==='ready'&&ACTIVE.has(j.state)&&j.state!=='exporting')setStates(old=>({...old,[j.id]:{...(old[j.id]||EMPTY_SELECTION),choices:defaultChoices(next.candidates),view:previewView(next.manifest?.kind)}}));
        if(next.state==='ready'&&j.state==='exporting'&&next.exportResult)setStates(old=>({...old,[j.id]:{...(old[j.id]||EMPTY_SELECTION),view:previewView(next.manifest?.kind),showOutput:true,exportDirty:false,verified:false}}));
      }}catch(e){if(!stop)setError(message(e));}finally{polling.current=false;}}
    const timer=setInterval(()=>void poll(),1000);return()=>{stop=true;clearInterval(timer);};
  },[]);
  useEffect(()=>{
    if(!active)return;
    const drop=createFileDropHandlers({
      canAdd:()=>!uploadLock.current&&jobsRef.current.length<8,
      onFiles:files=>{void addFiles(files);},onHover:setFileDragging,
      onBlocked:()=>setError(uploadLock.current?'파일 추가가 끝난 뒤 다시 놓아 주세요.':'파일 8개까지 열 수 있습니다. 일부 파일을 제거하고 추가해 주세요.'),
      onEmpty:()=>setError('파일을 읽지 못했습니다. 폴더 대신 검사할 파일을 놓거나 파일 추가 버튼을 사용해 주세요.'),
    });
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')drop.reset();};
    window.addEventListener('dragenter',drop.enter);window.addEventListener('dragover',drop.over);
    window.addEventListener('dragleave',drop.leave);window.addEventListener('drop',drop.drop);
    window.addEventListener('dragend',drop.reset);window.addEventListener('blur',drop.reset);window.addEventListener('keydown',escape);
    return()=>{
      window.removeEventListener('dragenter',drop.enter);window.removeEventListener('dragover',drop.over);
      window.removeEventListener('dragleave',drop.leave);window.removeEventListener('drop',drop.drop);
      window.removeEventListener('dragend',drop.reset);window.removeEventListener('blur',drop.reset);window.removeEventListener('keydown',escape);drop.reset();
    };
  },[active]);
  async function chooseFiles(){
    if(pickerLock.current||uploadLock.current||jobsRef.current.length>=8)return;
    if(boot.desktop){await addFiles();return;}
    pickerLock.current=true;setPicking(true);setError('');
    try{
      const files=await pickInspectionFiles(window.showOpenFilePicker?.bind(window));
      if(files===undefined)input.current?.click();
      else if(files?.length)await addFiles(files);
    }catch(e){setError(message(e));}
    finally{pickerLock.current=false;setPicking(false);}
  }
  async function addFiles(files?:FileList|File[]|null){
    if(uploadLock.current){setError('파일 추가가 끝난 뒤 다시 시도해 주세요.');return;}
    if(jobsRef.current.length>=8){setError('파일 8개까지 열 수 있습니다. 일부 파일을 제거하고 추가해 주세요.');return;}
    uploadLock.current=true;setError('');setNotice('');setUploading(true);
    try{
      const added:DocumentJob[]=[];
      if(boot.desktop&&!files){const result=await api<{files:DocumentJob[]}>('documents/open',{});for(const j of result.files){if(j.state==='rejected')setError(`${j.name}: ${j.error}`);else added.push(j);}}
      else if(files){for(const f of Array.from(files)){
        if(jobsRef.current.length+added.length>=8){setError('파일 8개까지 열 수 있습니다. 일부 파일을 제거하고 추가해 주세요.');break;}
        if(!accept.split(',').some(ext=>f.name.toLowerCase().endsWith(ext))){setError(`${f.name}: 지원하지 않는 형식입니다. 폴더 대신 지원하는 문서·이미지 파일을 추가해 주세요.`);continue;}
        if(!f.size){setError(`${f.name}: 비어 있는 파일은 검사할 수 없습니다.`);continue;}
        if(f.size>20*1024*1024){setError(`${f.name}: 20MB를 넘는 파일입니다.`);continue;}
        try{const r=await binary(`upload?filename=${encodeURIComponent(f.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});added.push(await r.json());}catch(e){setError(`${f.name}: ${message(e)}`);}
      }}
      if(added.length){setJobs(old=>[...old,...added]);setId(added[0].id);setStates(old=>{const next={...old};for(const j of added)next[j.id]={...EMPTY_SELECTION,choices:defaultChoices(j.candidates),view:previewView(j.manifest?.kind)};return next;});}
    }catch(e){setError(message(e));}finally{uploadLock.current=false;setUploading(false);if(input.current)input.current.value='';}
  }
  async function remove(){if(!removeId)return;try{await api('documents/remove',{id:removeId});setJobs(old=>old.filter(j=>j.id!==removeId));if(id===removeId)setId(jobs.find(j=>j.id!==removeId)?.id||'');setStates(old=>{const n={...old};delete n[removeId];return n;});}catch(e){setError(message(e));}finally{setRemoveId('');}}
  function choose(c:FileCandidate,editor=false){const part=job?.manifest?.parts.find(p=>p.id===c.part),link=previews[`${id}:source`]?.links[c.id];const view=c.asset?'images':part?.sheet?'sheet':part?.flow?'content':c.part in s.textEdits?'text':link?.hits.length?'pages':'text';selectState({focus:c.id,showOutput:false,view,previewPage:link?.hits[0]?.page||0,asset:c.asset||s.asset,sheet:part?.sheet||s.sheet,gridRow:Math.floor(((part?.row||1)-1)/30),gridColumn:Math.floor(((part?.column||1)-1)/10),page:view==='content'?contentPage(job?.manifest?.parts||[],c.part):Math.floor((job?.manifest?.parts.findIndex(p=>p.id===c.part)||0)/25)});requestAnimationFrame(()=>{const custom=editor||s.choices[c.id]?.mode==='custom';if(custom||window.matchMedia('(max-width:800px)').matches)revealFileEditor(document.getElementById('file-choice-editor'),custom);else if(view==='text'||view==='content')document.getElementById(`file-part-${c.part}`)?.scrollIntoView({block:'nearest',behavior:'smooth'});});}
  function chooseShown(c:FileCandidate,editor=false){
    if(!s.showOutput){choose(c,editor);return;}
    const part=job?.exportResult?.parts.find(p=>p.id===c.part),link=previews[`${id}:${job?.exportResult?.sha256}`]?.links[c.id];
    selectState({focus:c.id,view:c.asset?'images':part?.sheet?'sheet':part?.flow?'content':link?.hits.length?'pages':'text',asset:c.asset||s.asset,previewPage:link?.hits[0]?.page||0,sheet:part?.sheet||s.sheet,gridRow:Math.floor(((part?.row||1)-1)/30),gridColumn:Math.floor(((part?.column||1)-1)/10),page:part?.flow?contentPage(job?.exportResult?.parts||[],c.part):Math.floor((job?.exportResult?.parts.findIndex(p=>p.id===c.part)||0)/25)});
  }
  function apply(mode:MaskMode,ids:string[]){if(!job||locked||job.manifest?.blockers.length)return;const next={...s.choices};for(const key of ids){const c=job.candidates.find(c=>c.id===key);if(c)next[key]=mode==='custom'?{mode,text:replacement(c,next[key])}:{mode} as MaskChoice;}changed({choices:next});if(mode==='custom'&&ids.length===1){const candidate=job.candidates.find(c=>c.id===ids[0]);if(candidate)choose(candidate,true);}}
  function clearChoice(key:string){if(locked)return;const next={...s.choices};delete next[key];changed({choices:next});}
  function acceptMutation(next:DocumentJob,options:{focus?:string;choice?:MaskChoice;applied?:boolean}={}){
    const allowed=new Set(next.candidates.map(c=>c.id));
    setJobs(old=>old.map(j=>j.id===next.id?next:j));
    setStates(old=>{
      const state=old[next.id];if(!state)return old;
      const choices=Object.fromEntries(Object.entries(state.choices).filter(([key])=>allowed.has(key)));
      if(options.focus&&options.choice)choices[options.focus]=options.choice;
      return {...old,[next.id]:{...state,choices,lastBulkChoices:Object.fromEntries(Object.entries(state.lastBulkChoices).filter(([key])=>allowed.has(key))),focus:options.focus??(state.focus&&allowed.has(state.focus)?state.focus:null),selected:state.selected.filter(key=>allowed.has(key)),verified:false,exportDirty:true,showOutput:false,saved:false,draftView:options.applied?'applied':'original'}};
    });
    setPreviews(old=>{const value={...old};delete value[`${next.id}:source`];return value;});
  }
  async function exclude(ids:string[]){
    if(!job||locked||s.showOutput||mutationLock.current)return;
    const candidates=ids.filter(key=>job.candidates.some(c=>c.id===key&&!(c.part in s.textEdits)));
    if(!candidates.length)return;
    mutationLock.current=true;setKeywordAdding(job.id);setError('');
    try{acceptMutation(await api<DocumentJob>('documents/exclude',{id:job.id,revision:job.revision,candidates}));setNotice(`선택한 ${candidates.length}곳을 제외했습니다. 원문은 유지됩니다.`);}
    catch(e){setError(message(e));}finally{mutationLock.current=false;setKeywordAdding('');}
  }
  function chooseInDocument(c:FileCandidate){
    if(sourceDrag.current)return;
    setSourceRange(null);setRangeTarget(null);selectState({focus:c.id});
    if(window.matchMedia('(max-width:800px)').matches)requestAnimationFrame(()=>revealFileEditor(document.getElementById('file-choice-editor'),false));
  }
  function selectSource(root:HTMLElement){
    if(!job||locked||s.showOutput||s.draftView!=='original')return;
    const range=readSourceRange(root,window.getSelection());
    if(!range)return;
    sourceDrag.current=true;setTimeout(()=>{sourceDrag.current=false;},0);
    const part=job.manifest?.parts.find(p=>p.id===range.part);if(!part||!part.text.slice(range.start,range.end).trim())return;
    const target=rangeTarget?.job===job.id?rangeTarget:null;
    if(target&&target.part!==range.part){setError('범위를 변경할 후보와 같은 문단·셀에서 선택하세요.');return;}
    setError('');setSourceRange({...range,job:job.id,revision:job.revision,replaceId:target?.id});setRangeText(part.text.slice(range.start,range.end));selectState({focus:null});
    if(window.matchMedia('(max-width:800px)').matches)requestAnimationFrame(()=>document.getElementById('source-range-editor')?.scrollIntoView({block:'center',behavior:'smooth'}));
  }
  function extendSource(root:HTMLElement,x:number,y:number){
    const anchor=sourceAnchor.current;
    if(!anchor||Math.hypot(x-anchor.x,y-anchor.y)<4)return;
    const end=sourceCaret(root,x,y);if(!end)return;
    // Some browsers lose native selection across focusable inline highlights.
    // Keep the same DOM text range without inserting or rewriting source text.
    window.getSelection()?.setBaseAndExtent(anchor.node,anchor.offset,end.startContainer,end.startOffset);
  }
  function adjustRange(c:FileCandidate){
    setSourceRange(null);setRangeTarget({job:id,id:c.id,part:c.part});
    const part=job?.manifest?.parts.find(p=>p.id===c.part);
    const view=part?.sheet?'sheet':part?.flow?'content':'text';
    selectState({draftView:'original',showOutput:false,focus:c.id,view,sheet:part?.sheet||s.sheet,gridRow:Math.floor(((part?.row||1)-1)/30),gridColumn:Math.floor(((part?.column||1)-1)/10),page:view==='content'?contentPage(job?.manifest?.parts||[],c.part):Math.floor((job?.manifest?.parts.findIndex(p=>p.id===c.part)||0)/25)});
    setNotice('같은 문단·셀에서 새 범위를 드래그하세요. 확정하면 기존 후보와 처리 지정이 새 항목으로 바뀝니다.');
    requestAnimationFrame(()=>document.getElementById(`file-part-${c.part}`)?.scrollIntoView({block:'center',behavior:'smooth'}));
  }
  function locateKeyword(c:FileCandidate){
    if(!job)return;
    choose(c);selectState({draftView:'original',filter:'all',search:''});setRangeTarget(null);
    setSourceRange({part:c.part,start:c.start,end:c.end,job:job.id,revision:job.revision});setRangeText(c.text);
    requestAnimationFrame(()=>{
      const element=document.getElementById(`file-part-${c.part}`)?.querySelector<HTMLElement>('[data-source-part]');
      if(element)showSourceRange(element,c.start,c.end);
    });
  }
  async function addSourceRange(mode?:'partial'|'full'|'custom'){
    const range=sourceRange;
    if(!job||locked||mutationLock.current||!range||range.job!==id||range.revision!==job.revision||range.part in s.textEdits)return;
    mutationLock.current=true;setKeywordAdding(job.id);setError('');
    try{
      const next=await api<DocumentJob>('documents/add-range',{id:job.id,revision:range.revision,part:range.part,start:range.start,end:range.end,replaceId:range.replaceId??null});
      const added=next.candidates.find(c=>!job.candidates.some(old=>old.id===c.id));
      acceptMutation(next,{focus:added?.id,choice:mode==='custom'?{mode,text:rangeText}:mode?{mode}:undefined,applied:!!mode});
      setSourceRange(null);setRangeTarget(null);window.getSelection()?.removeAllRanges();
      setNotice(range.replaceId?'선택한 범위로 후보를 변경했습니다.':'선택한 원문을 사용자 후보로 추가했습니다.');
      if(mode==='custom')requestAnimationFrame(()=>revealFileEditor(document.getElementById('file-choice-editor'),true));
    }catch(e){setError(message(e));}finally{mutationLock.current=false;setKeywordAdding('');}
  }
  async function addKeywords(query:string,matches:string[]){
    if(!job||locked||s.showOutput||mutationLock.current)return;
    mutationLock.current=true;
    const target=job.id;
    setKeywordAdding(target);
    try{
      const next=await api<DocumentJob>('documents/add-keywords',{id:target,revision:job.revision,query,matches});
      acceptMutation(next);
      setNotice(`${job.name}에 사용자 후보 ${matches.length}곳을 추가했습니다. 목록에서 처리 방법을 선택하세요.`);
    }finally{mutationLock.current=false;setKeywordAdding('');}
  }
  async function generate(){if(!job)return;setError('');setNotice('');try{const next=await api<DocumentJob>('documents/export',{id:job.id,revision:job.revision,choices:s.choices,regions:s.regions,textEdits:s.textEdits});setJobs(old=>old.map(j=>j.id===id?next:j));selectState({showOutput:false,verified:false,exportDirty:false,saved:false});}catch(e){setError(message(e));}}
  function previewOutput(){selectState({showOutput:true,page:0,view:previewView(job?.manifest?.kind)});requestAnimationFrame(()=>document.querySelector('.document-preview-head')?.scrollIntoView({block:'start',behavior:'smooth'}));}
  async function save(){if(!job?.exportResult||!s.verified||s.exportDirty)return;setError('');try{
    if(boot.desktop){const r=await api<{saved?:boolean;cancelled?:boolean;name?:string}>('documents/save',{id});if(r.cancelled)return;setNotice(`${r.name} 사본을 저장했어요.`);}
    else {const r=await binary(`${id}/download`),b=await r.blob(),url=URL.createObjectURL(b);const a=document.createElement('a');a.href=url;a.download=job.exportResult.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);setNotice('수정 사본 다운로드를 요청했어요. 브라우저 다운로드 목록에서 확인해 주세요.');}
    selectState({saved:true});
  }catch(e){setError(message(e));}}
  const all=job?.candidates||[],reviewCandidates=all,m=job?.manifest,focus=(s.showOutput?job?.exportResult?.candidates:reviewCandidates)?.find(c=>c.id===s.focus),exported=job?.exportResult;
  const shownParts=s.showOutput&&exported?exported.parts:m?.parts||[];
  const shownCandidates=s.showOutput&&exported?exported.candidates:reviewCandidates;
  const findingCandidates=s.showOutput&&exported?exported.candidates:all;
  const shownSelection=s.showOutput?{...s,choices:{},textEdits:{},selected:[]}:s;
  const range=sourceRange?.job===id&&sourceRange.revision===job?.revision?sourceRange:null;
  const rangePart=range?m?.parts.find(p=>p.id===range.part):null;
  const rangeOverlap=!!range&&rangeConflict(range,all,range.replaceId);
  const rangeBlocked=rangeOverlap||!!range&&range.part in s.textEdits;
  const assigned=reviewCandidates.filter(c=>draftStatus(c,s)!=='unset').length;
  const bulkTargets=bulkMaskTargets(reviewCandidates,s);
  const undoableBulkIds=bulkChoicesToUndo(s);
  const showBulkPanel=!!id&&bulkPanelFor===id;
  function applyBulk(mode:'full'|'partial'){
    if(locked||s.showOutput||!bulkTargets.ids.length)return;
    const lastBulkChoices:MaskChoices={};
    for(const key of bulkTargets.ids)lastBulkChoices[key]={mode};
    changed({choices:{...s.choices,...lastBulkChoices},lastBulkChoices});
    setBulkPanelFor('');
    appliedPreviewButton.current?.focus({preventScroll:true});
  }
  function undoBulk(){
    if(locked||s.showOutput||!undoableBulkIds.length)return;
    const choices={...s.choices};
    for(const key of undoableBulkIds)delete choices[key];
    changed({choices,lastBulkChoices:{}});
    setBulkPanelFor('');
    appliedPreviewButton.current?.focus({preventScroll:true});
  }
  function compare(view:FileSelection['draftView']){selectState({draftView:view,...(view==='applied'&&s.view==='pages'&&Object.keys(s.textEdits).length?{view:'text' as const}:{})});}
  const shownAssets=s.showOutput&&exported?exported.assets:m?.assets||[];
  const asset=shownAssets.find(a=>a.id===s.asset)||shownAssets[0];
  const totalPages=Math.max(1,Math.ceil(shownParts.length/25)),page=Math.min(s.page,totalPages-1);
  const changingBoxes:Box[]=[];
  if(asset)for(const c of all.filter(c=>c.asset===asset.id)){
    const mode=s.choices[c.id]?.mode;if(mode!=='partial'&&mode!=='full')continue;
    if(c.maskBoxes)changingBoxes.push(...c.maskBoxes[mode]);
    else {const masked=Array.from(c.partialText||partialMask(c)),original=Array.from(c.text);(c.boxes||[]).forEach((b,i)=>{if(mode==='full'||masked[i]!==original[i])changingBoxes.push(b);});}
  }
  return <main className="file-review" hidden={!active}>
    <div className="page-heading"><div><span className="eyebrow">파일 개인정보 검토</span><h1>원본은 그대로, 배포는 사본으로.</h1><p>문서와 이미지를 오가며 확인하고, 수정 사본을 다시 검사해 저장하세요.</p></div><button className="primary" disabled={uploading||picking||jobs.length>=8} onClick={()=>void chooseFiles()}>{picking?'파일 선택 중…':uploading?'파일 추가 중…':'+ 파일 추가'}</button><input ref={input} type="file" multiple accept={accept} hidden onChange={e=>void addFiles(e.target.files)}/></div>
    <section className={`file-dropzone ${fileDragging?'dragging':''} ${uploading||jobs.length>=8?'unavailable':''}`} aria-label="파일 드래그 앤 드롭">
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M12 16V3m-4 4 4-4 4 4M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/></svg>
      <div><strong role="status">{uploading?'파일을 추가하고 있어요':jobs.length>=8?'파일 8개가 열려 있어요':fileDragging?'여기에 놓으면 검사를 시작합니다':'검사할 파일을 이 화면에 끌어 놓으세요'}</strong><p>{jobs.length>=8?'목록에서 파일을 제거한 뒤 추가해 주세요.':uploading?'추가가 끝난 뒤 다른 파일을 놓아 주세요.':'문서·이미지 여러 개를 함께 추가할 수 있어요. 파일당 20MB · 최대 8개'}</p></div><span>{jobs.length}/8개</span>
    </section>
    <p className="file-model-attribution">이름·주소: <strong>{boot.model||'KoELECTRA 개인정보 인식 모델'}</strong> · 번호 등: ko-pii 규칙 · API 키·비밀번호: 형식·항목 규칙 · 최종 문맥 검토: <strong>{boot.secondaryModel||'KoELECTRA'}</strong> + 유형별 규칙</p>
    {error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')} aria-label="오류 닫기">×</button></div>}
    {notice&&<div className="notice" role="status">{notice}</div>}
    {!jobs.length?<section className="file-empty"><div className="file-empty-icon">▤</div><h2>검사할 파일을 추가해 주세요</h2><p>DOCX · HWPX · XLSX · PPTX · PDF · CSV · TXT<br/>PNG · JPG 이미지와 HWP 본문 검사도 지원해요.</p><div className="file-flow"><span>1. 사본에서 검사</span><b>→</b><span>2. 목록 정리·가림 선택</span><b>→</b><span>3. 재검사 후 저장</span></div><p className="muted">파일당 20MB · 최대 8개 · PDF 최대 40쪽 · 내장 이미지 최대 40개<br/>수식이 있는 엑셀은 지원 수식을 재계산한 값 전용 사본으로 제공합니다.</p></section>:
    <div className="document-layout"><aside className="document-rail" aria-label="열린 파일"><h2>열린 파일 <span>{jobs.length}/8</span></h2>{jobs.map(j=><div key={j.id} className={`document-tab ${j.id===id?'active':''}`}><button onClick={()=>setId(j.id)} aria-pressed={id===j.id}><span className="doc-extension">{j.name.split('.').pop()?.toUpperCase()}</span><strong>{j.name}</strong><small>{ACTIVE.has(j.state)?fileProgressStatus(j).title:j.state==='error'?'읽기 확인 필요':j.state==='cancelled'?'취소됨':`${j.candidates.length}개 후보 · ${states[j.id]?.saved?'사본 저장 요청 완료':'검토 중'}`}</small></button><button className="doc-remove" aria-label={`${j.name} 제거`} onClick={()=>setRemoveId(j.id)}>×</button></div>)}<p>파일을 전환해도 선택한 가림과 위치가 유지됩니다. 작업 목록은 앱 종료 시 정리됩니다.</p></aside>
    <section className="document-workspace" aria-label="선택한 파일 검토">
      {job&&<><div className="document-title"><div><span className="eyebrow">{m?.kind==='.xlsx'?'값 전용 배포 사본':'내 PC에서만 처리'}</span><h2>{job.name}</h2></div><span className="source-badge">원본 보존</span></div>
      {working&&<FileProgress key={job.id} job={job} onCancel={async()=>{try{await api('documents/cancel',{id});setJobs(old=>old.map(j=>j.id===id?{...j,state:'cancelled'}:j));}catch(e){setError(message(e));}}}/>}
      {job.error&&<div className="error" role="alert">{job.error}</div>}
      {job.state==='cancelled'&&<div className="notice">취소한 작업의 임시 사본을 정리합니다. 다시 검사하려면 파일을 새로 추가해 주세요.</div>}
      {m&&(job.state==='ready'||job.state==='exporting')&&<><details className="file-coverage" open={!!m.blockers.length}><summary>검사한 영역과 지원 범위 <span>{m.blockers.length?'저장 제한 있음':'반드시 확인'}</span></summary><ul>{m.coverage.map(v=><li key={v}>검사 범위 · {v}</li>)}</ul>{m.blockers.map(v=><p className="file-blocker" key={v}>{v}</p>)}{m.warnings.map(v=><p key={v}>{v}</p>)}{m.calculation&&<p><strong>{m.calculation.count}개 수식의 계산 결과를 확인했습니다.</strong><br/>{m.calculation.at} · {m.calculation.method}<br/>사본의 값은 이후에 다시 계산되지 않습니다.</p>}</details>
      {!s.showOutput&&<section className="file-list-preparation" aria-label="검출 목록 정리">
        <h3>1. 검사 → 2. 검출 목록 정리 → 3. 처리·비교 → 4. 사본 저장</h3>
        <p>검출 목록에서 오탐을 제외하고, 아래 원문 검색으로 누락된 항목을 추가하세요. 정리한 후보에 부분·전체 가림이나 직접 수정을 지정할 수 있습니다.</p>
        <FileKeywordSearch key={job.id} job={job} selection={s} locked={locked} onLocate={locateKeyword} onAdd={addKeywords}/>
      </section>}
      <FileFindings overview="only" output={s.showOutput} candidates={findingCandidates} selection={shownSelection} locked={locked||s.showOutput} onState={selectState} onSelect={chooseShown} onApply={apply} onExclude={exclude} formatReplacement={replacement}/>
      <div className="file-review-columns"><div className="file-document-pane" onPointerDown={e=>{sourceAnchor.current=null;if(e.button!==0||locked||s.showOutput||s.draftView!=='original')return;const caret=sourceCaret(e.currentTarget,e.clientX,e.clientY);if(caret){e.preventDefault();sourceAnchor.current={node:caret.startContainer,offset:caret.startOffset,x:e.clientX,y:e.clientY};window.getSelection()?.removeAllRanges();}}} onPointerMove={e=>{if(e.buttons!==1){sourceAnchor.current=null;return;}extendSource(e.currentTarget,e.clientX,e.clientY);}} onPointerUp={e=>{extendSource(e.currentTarget,e.clientX,e.clientY);sourceAnchor.current=null;selectSource(e.currentTarget);}} onPointerCancel={()=>{sourceAnchor.current=null;}}>
      <div className="document-preview-head"><h3>{s.showOutput?'수정 사본 확인':'문서 화면'}</h3><div className="segmented">{['.docx','.pptx'].includes(m.kind)&&<button aria-pressed={s.view==='pages'} onClick={()=>selectState({view:'pages'})}>문서 · 페이지</button>}{['.txt','.hwpx','.hwp'].includes(m.kind)&&<button aria-pressed={s.view==='content'} onClick={()=>selectState({view:'content',page:focus?contentPage(shownParts,focus.part):0})}>내용 미리보기</button>}{['.xlsx','.csv','.tsv'].includes(m.kind)&&<button aria-pressed={s.view==='sheet'} onClick={()=>selectState({view:'sheet'})}>{m.kind==='.xlsx'?'시트 · 셀':'표 · 셀'}</button>}<button aria-pressed={s.view==='text'} onClick={()=>selectState({view:'text'})}>텍스트 · 위치</button><button aria-pressed={s.view==='images'} disabled={!shownAssets.length} onClick={()=>selectState({view:'images'})}>이미지 · 페이지 {shownAssets.length}</button></div></div>
      {!s.showOutput&&<div className="draft-compare">
        <div className="draft-view-toggle" role="group" aria-label="원본과 적용 미리보기 전환">
          <button aria-pressed={s.draftView==='original'} onClick={()=>compare('original')}>원본</button>
          <button ref={appliedPreviewButton} aria-pressed={s.draftView==='applied'} onClick={()=>compare('applied')}>적용 미리보기</button>
        </div>
        <span role="status">처리 지정 <b>{assigned}/{reviewCandidates.length}</b>개 · 미설정 {reviewCandidates.length-assigned}개</span>
        <p>{s.draftView==='applied'?s.view==='pages'?'저장 전 간이 미리보기입니다. 긴 문구·줄바꿈·배경은 실제 사본과 다를 수 있습니다.':'저장 전 미리보기입니다. 지정하지 않은 항목은 원본 그대로 남습니다.':'원본 내용을 보여줍니다. ✓ 표시는 처리 방법을 지정한 항목입니다.'}</p>
        {reviewCandidates.length>0&&!m.blockers.length&&<div className="file-bulk-tools">
          <div className="file-bulk-actions">
            <button className="secondary" disabled={locked||!bulkTargets.ids.length}
              aria-expanded={showBulkPanel} aria-controls="file-bulk-options"
              onClick={()=>setBulkPanelFor(showBulkPanel?'':id)}>현재 파일 후보에 일괄 적용</button>
            {undoableBulkIds.length>0&&<button className="secondary" disabled={locked} onClick={undoBulk}>일괄 적용 되돌리기</button>}
          </div>
          <div id="file-bulk-options" className="file-bulk-options" hidden={!showBulkPanel}>
            <p><strong>미설정 후보 {bulkTargets.ids.length}개</strong>에 적용합니다. 검색·위험도 필터와 관계없이 현재 파일의 후보를 확인합니다.</p>
            <div className="file-bulk-actions">
              <button className="primary" disabled={locked||!bulkTargets.ids.length} onClick={()=>applyBulk('full')}>전체 가림 적용</button>
              <button className="secondary" disabled={locked||!bulkTargets.ids.length} onClick={()=>applyBulk('partial')}>부분 가림 적용</button>
            </div>
          </div>
          {bulkTargets.overlaps>0&&<p>직접 지정한 가림 영역과 겹치는 후보 {bulkTargets.overlaps}개는 개별로 확인하세요.</p>}
        </div>}
      </div>}
      {!s.showOutput&&<div className="source-review-guide">
        <strong>후보는 클릭, 원하는 글자는 드래그</strong>
        <p>{s.view==='pages'||s.view==='images'?'페이지의 후보를 눌러 처리하거나 제외하세요. 글자 범위는 원문 텍스트에서, 읽히지 않은 글자는 이미지 영역으로 지정하세요.':s.draftView==='applied'?'새 범위를 선택하려면 원본으로 전환하세요.':'원본의 한 문단·셀 안에서 글자를 드래그하면 검토 목록 추가와 가림·수정을 선택할 수 있습니다.'}</p>
        {(s.view==='pages'||s.view==='images')&&<button className="secondary" onClick={()=>selectState({view:'text',draftView:'original'})}>원문 글자 범위 선택</button>}
        {rangeTarget?.job===id&&<p role="status">범위 변경 중 · 같은 문단·셀에서 드래그하세요. <button onClick={()=>{setRangeTarget(null);setSourceRange(null);}}>범위 변경 취소</button></p>}
      </div>}
      {s.view==='text'&&['.docx','.hwpx','.pptx','.hwp'].includes(m.kind)&&<p className="preview-mode-note">문서에서 읽은 글자와 위치를 보여줍니다. 원래 페이지 배치와 서식은 표시하지 않습니다. 내장 이미지는 이미지 · 페이지 탭에서 확인하세요.</p>}
      {s.showOutput&&<div className="output-banner">재검사에서 {exported?.candidates.length}개 후보가 남았습니다. 유지한 정보·부분 가림·오탐이 포함될 수 있어요.<button onClick={()=>selectState({showOutput:false})}>가림 선택으로 돌아가기</button></div>}
      {s.view==='pages'?<OfficePreview job={job} output={s.showOutput} selection={shownSelection} candidates={shownCandidates} onState={selectState} onSelect={chooseInDocument} onReady={p=>setPreviews(old=>({...old,[`${id}:${s.showOutput?exported?.sha256:'source'}`]:p}))} onText={()=>selectState({view:'text',page:focus?Math.floor(shownParts.findIndex(p=>p.id===focus.part)/25):0})}/>:s.view==='content'?<ContentReview job={job} parts={shownParts} candidates={shownCandidates} selection={shownSelection} output={s.showOutput} onChange={selectState} onSelect={chooseInDocument} onText={()=>selectState({view:'text',page:focus?Math.floor(shownParts.findIndex(p=>p.id===focus.part)/25):0})}/>:s.view==='sheet'?<SheetReview kind={m.kind} size={s.showOutput?exported?.tableSize:m.tableSize} parts={shownParts} candidates={shownCandidates} selection={s} onChange={selectState} onSelect={chooseInDocument} onEdit={p=>setPartEdit({id:p.id,text:s.textEdits[p.id]??p.text})} output={s.showOutput} locked={locked||!!m.blockers.length}/>:s.view==='text'?<section className="document-preview" aria-label={s.showOutput?'수정 사본 텍스트':'문서 텍스트'}>
        {!shownParts.length?<p>읽을 수 있는 텍스트가 없습니다. 이미지·페이지 탭에서 직접 확인하세요.</p>:shownParts.slice(page*25,(page+1)*25).map(p=><article key={p.id} id={`file-part-${p.id}`}><h4>{p.location}{!s.showOutput&&!p.asset&&<button disabled={locked||!!m.blockers.length} onClick={()=>setPartEdit({id:p.id,text:s.textEdits[p.id]??p.text})}>이 영역 직접 수정</button>}{!s.showOutput&&p.id in s.textEdits&&<button disabled={locked} onClick={()=>{const next={...s.textEdits};delete next[p.id];changed({textEdits:next});}}>직접 수정 취소</button>}{p.asset&&<button onClick={()=>selectState({view:'images',asset:p.asset!})}>이미지에서 보기 ↗</button>}</h4><Highlight part={p} candidates={shownCandidates} selection={shownSelection} output={s.showOutput} onSelect={chooseInDocument}/></article>)}
        <div className="preview-pagination"><button disabled={page===0} onClick={()=>selectState({page:page-1})}>이전</button><span>{page+1} / {totalPages} · 전체 {shownParts.length}개 영역</span><button disabled={page+1>=totalPages} onClick={()=>selectState({page:page+1})}>다음</button></div>
      </section>:<section className="document-preview"><div className="office-preview-toolbar"><strong>{m.kind==='.pdf'?'PDF 페이지':'이미지'}</strong><PageNavigation page={Math.max(0,shownAssets.findIndex(a=>a.id===asset?.id))} labels={shownAssets.map(a=>a.location)} noun={m.kind==='.pdf'?'페이지':'이미지'} onChange={index=>selectState({asset:shownAssets[index].id})}/></div>{asset&&<ImageReview candidates={shownCandidates} selection={shownSelection} onSelect={chooseInDocument} key={`${id}-${asset.id}-${s.showOutput}`} job={job} asset={asset} regions={s.regions} selectedBoxes={changingBoxes} locked={locked} output={s.showOutput} onOriginal={()=>selectState({draftView:'original'})} onRegion={box=>changed({regions:[...s.regions,{asset:asset.id,box}]})}/>}
      {!s.showOutput&&s.regions.length>0&&<div className="manual-regions"><strong>직접 지정한 영역</strong>{s.regions.map((r,i)=><span key={i}>{m.assets.find(a=>a.id===r.asset)?.location} · {i+1}번<button disabled={locked} onClick={()=>changed({regions:s.regions.filter((_,n)=>n!==i)})} aria-label={`직접 지정 ${i+1}번 취소`}>취소</button></span>)}</div>}</section>}
      </div><aside className="file-controls" aria-label="개인정보 선택과 처리">
      {!s.showOutput&&range&&rangePart&&<section className="source-range-editor" id="source-range-editor" aria-label="선택한 원문 범위">
        <header><strong>{range.replaceId?'후보 범위 변경':'선택한 원문'}</strong><button aria-label="범위 선택 취소" disabled={locked} onClick={()=>{setSourceRange(null);setRangeTarget(null);window.getSelection()?.removeAllRanges();}}>×</button></header>
        <small>{rangePart.location} · 글자 {range.start+1}–{range.end}</small>
        <blockquote>{rangePart.text.slice(range.start,range.end)}</blockquote>
        {rangeBlocked?<p role="alert">{rangeOverlap?'다른 검토 후보와 겹칩니다. 범위를 줄이거나 겹치는 후보를 먼저 제외하세요.':'영역 직접 수정을 취소한 뒤 원문에서 다시 선택하세요.'}</p>:<p>이 위치를 사용자 후보로 {range.replaceId?'변경':'추가'}합니다. 원문을 다시 드래그하면 범위를 바꿀 수 있습니다.</p>}
        <div className="source-range-actions">
          <button className="primary" disabled={locked||rangeBlocked} onClick={()=>void addSourceRange()}>목록에만 추가</button>
          <button disabled={locked||rangeBlocked} onClick={()=>void addSourceRange('partial')}>부분 가림</button>
          <button disabled={locked||rangeBlocked} onClick={()=>void addSourceRange('full')}>전체 가림</button>
          <button disabled={locked||rangeBlocked||!!rangePart.asset&&!['.png','.jpg','.jpeg'].includes(m.kind)} onClick={()=>void addSourceRange('custom')}>직접 수정</button>
        </div>
      </section>}
      {!s.showOutput&&focus&&<section className="file-choice-editor" id="file-choice-editor" aria-label="선택한 개인정보 처리">
        <div><span className={`risk-${focus.risk}`}>{riskName(focus.risk)} · {focus.labelName}</span><small>{focus.location}</small><button aria-label="선택 편집 닫기" onClick={()=>selectState({focus:null})}>×</button></div><strong>{focus.text}</strong>
        {focus.credential&&<p>인증정보 · {focus.credential.provider} · {focus.credential.reason}</p>}
        {focus.ocrConfidence!==undefined&&<p className="ocr-reading-note">{focus.ocrConfidence<80?'글자 인식이 불확실합니다.':'이미지에서 읽은 글자입니다.'} 원문과 다르게 읽혔거나 개인정보가 아니면 ‘가리지 않음’을 선택하세요.</p>}
        <div className={`file-choice-state ${draftStatus(focus,s)!=='unset'?'assigned':''}`} role="status">{focus.part in s.textEdits?'✓ 영역 직접 수정 지정':s.choices[focus.id]?`✓ ${MODE_NAMES[s.choices[focus.id].mode]} 지정`:'처리 방법 미설정'}</div>
        <div className="file-choice-buttons">{(['partial','full','keep','custom'] as MaskMode[]).map(mode=><button key={mode} disabled={locked||focus.part in s.textEdits||!!focus.asset&&!focus.imageTextEditable&&mode==='custom'} aria-pressed={!(focus.part in s.textEdits)&&s.choices[focus.id]?.mode===mode} onClick={()=>apply(mode,[focus.id])}>{focus.imageTextEditable&&mode==='full'?'비공개 표시':MODE_NAMES[mode]}</button>)}</div>
        {s.choices[focus.id]?.mode==='custom'&&<label htmlFor="file-custom-input">바꿀 내용<input id="file-custom-input" maxLength={focus.imageTextEditable?80:2000} value={(s.choices[focus.id] as {text:string}).text} disabled={locked} onChange={e=>changed({choices:{...s.choices,[focus.id]:{mode:'custom',text:e.target.value}}})}/></label>}
        <p>{focus.part in s.textEdits?'이 영역의 직접 수정 내용이 우선합니다. 텍스트 · 위치에서 확인하거나 취소할 수 있습니다.':focus.asset&&!focus.imageTextEditable?'PDF·내장 이미지는 영역 가림을 지원합니다. 문구 교체는 PNG·JPG·JPEG 파일에서 지원합니다.':s.choices[focus.id]?'변경 예정 → '+replacement(focus,s.choices[focus.id]):'아직 처리 방법을 지정하지 않았습니다.'}</p>{focus.imageTextEditable&&<p>원래 글자 크기를 유지하고 같은 줄의 빈 공간까지 활용합니다. 한 줄 80자 이하로 입력하세요. 주변 글자·표 선과 겹치는 문구는 경고로 알려드립니다. 글꼴과 배경은 원본과 다를 수 있습니다.</p>}{!focus.asset&&<p>선택한 항목만 바꿉니다. 사본 생성 후 실제 문서 화면에서 결과를 확인해 주세요.</p>}
        {s.choices[focus.id]&&!(focus.part in s.textEdits)&&<button className="draft-clear-choice" disabled={locked} onClick={()=>clearChoice(focus.id)}>처리 선택 취소</button>}
        <div className="source-range-actions"><button className="secondary" disabled={locked||focus.part in s.textEdits} onClick={()=>adjustRange(focus)}>글자 범위 변경</button><button disabled={locked||focus.part in s.textEdits} onClick={()=>void exclude([focus.id])}>검토 목록에서 제외</button></div>
        {focus.asset&&<button className="secondary" disabled={locked} onClick={()=>{changed({choices:{...s.choices,[focus.id]:{mode:'keep'}},focus:null});setNotice('이 항목의 자동 가림을 해제했습니다. 이미지에서 원하는 범위를 드래그해 다시 지정하세요.');document.querySelector('.image-canvas')?.scrollIntoView({block:'center',behavior:'smooth'});}}>가림 범위 직접 다시 지정</button>}
      </section>}
      <FileFindings overview="hidden" output={s.showOutput} candidates={findingCandidates} selection={shownSelection} locked={locked||s.showOutput} onState={selectState} onSelect={chooseShown} onApply={apply} onExclude={exclude} formatReplacement={replacement}/>
      </aside></div>
      <div className="file-applied-columns">{(['partial','full','custom'] as const).map(mode=><section key={mode}><h3>{MODE_NAMES[mode]} 적용 목록 <small>{all.filter(c=>s.choices[c.id]?.mode===mode).length}곳</small></h3><div>{all.filter(c=>s.choices[c.id]?.mode===mode).map(c=><article key={c.id}><button onClick={()=>choose(c)}><small>{c.labelName} · {c.location}</small><span>{candidateSummary(c)} → {c.asset&&!c.imageTextEditable?'영역 가림':replacement(c,s.choices[c.id])}</span></button><select aria-label={`${c.text} 적용 변경`} disabled={locked} value={mode} onChange={e=>apply(e.target.value as MaskMode,[c.id])}><option value="partial">부분</option><option value="full">전체</option><option value="custom" disabled={!!c.asset&&!c.imageTextEditable}>수정</option></select><button disabled={locked||!!c.asset&&!c.imageTextEditable} onClick={()=>apply('custom',[c.id])}>편집</button><button disabled={locked} onClick={()=>clearChoice(c.id)}>취소</button></article>)}</div></section>)}</div>
      <section className="file-export"><div><h3>수정 사본 만들기</h3><p>선택한 위치를 처리한 뒤 새 파일을 다시 열어 검사합니다.<br/>원본에는 덮어쓰지 않으며, 선택하지 않은 정보는 그대로 남습니다.</p></div><button className="primary" disabled={locked||!!m.blockers.length} onClick={()=>void generate()}>{job.state==='exporting'?'사본 처리 중…':'사본 생성 · 재검사'}</button>
      {exported&&!s.exportDirty&&<div className="file-export-result"><strong>재검사 완료 · 남은 후보 {exported.candidates.length}개</strong><p>{exported.filename}</p>{exported.candidates.length>0&&<details className="residual-list"><summary>남은 후보 {exported.candidates.length}개 보기</summary>{exported.candidates.map(c=><button key={c.id} onClick={()=>selectState({showOutput:true,view:c.asset?'images':'text',asset:c.asset||s.asset,page:Math.floor(exported.parts.findIndex(p=>p.id===c.part)/25)})}><span className={`risk-${c.risk}`}>{c.labelName}</span> {c.text} <small>{c.location}</small></button>)}</details>}<button className="secondary" onClick={previewOutput}>실제 사본 확인</button><label><input type="checkbox" checked={s.verified} onChange={e=>selectState({verified:e.target.checked})}/>남은 후보, 이미지 가림 범위, 지원 제한을 확인했습니다.</label><button className="primary" disabled={!s.verified||working} onClick={()=>void save()}>{boot.desktop?'새 파일로 사본 저장':'사본 다운로드'}</button></div>}
      </section><p className="file-footer-note">자동 검사는 오탐과 누락이 있을 수 있습니다. OCR 재검사 0건도 이미지에 개인정보가 없다는 뜻은 아닙니다. 부분 가림은 일부 개인정보를 남깁니다. 사본을 원래 문서 프로그램에서 열어 배치와 내용도 확인해 주세요.</p>
      </>}
      </>}
    </section></div>}
    {partEdit&&<div className="file-dialog-shade"><section role="dialog" aria-modal="true" aria-labelledby="edit-part-title"><h2 id="edit-part-title">영역 직접 수정</h2><p>이 영역의 원문을 직접 바꿉니다. 이 영역에서 선택한 개별 가림보다 직접 수정 내용이 우선합니다.</p><textarea aria-label="영역 수정 내용" maxLength={12000} value={partEdit.text} onChange={e=>setPartEdit({...partEdit,text:e.target.value})}/><div><button className="secondary" onClick={()=>setPartEdit(null)}>취소</button><button className="primary" onClick={()=>{const next={...s.choices};for(const c of all.filter(c=>c.part===partEdit.id))delete next[c.id];changed({textEdits:{...s.textEdits,[partEdit.id]:partEdit.text},choices:next});setPartEdit(null);}}>수정 적용</button></div></section></div>}
    {removeId&&<div className="file-dialog-shade"><section role="dialog" aria-modal="true" aria-labelledby="remove-file-title"><h2 id="remove-file-title">작업 목록에서 제거할까요?</h2><p>진행 중인 검사를 취소하고 임시 사본과 가림 선택을 정리합니다. 원본과 이미 저장한 사본은 유지됩니다.</p><div><button className="secondary" onClick={()=>setRemoveId('')}>계속 검토</button><button className="primary" onClick={()=>void remove()}>제거</button></div></section></div>}
  </main>;
}
