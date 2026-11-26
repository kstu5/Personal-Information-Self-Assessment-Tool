import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import type { Candidate, CheckResult, Draft } from './types';
import { api,boot } from './api';
import { candidateSummary, isCredential, locationOf, maskedDraft, MODE_NAMES, replacement, RISKS } from './masking';
import type { MaskChoices, MaskMode } from './masking';
import {AutoMaskPanel} from './AutoMaskPanel';
import {FileFindings} from './FileFindings';
import {EMPTY_SELECTION} from './documentTypes';
import {PostFindings,PostKeywordSearch} from './PostReviewTools';
import {addPostRanges,EMPTY_POST_FILTER,excludePostCandidates,normalizePostRange,POST_STATUSES,postRangeConflict,postStatus,postStatusCounts} from './postReview';
import type {PostFilter,PostRange} from './postReview';
import {readSourceRange,showSourceRange,sourceCaret} from './sourceSelection';
import {DEFAULT_MANUAL_TYPE,ManualTypeSelect} from './ManualTypeSelect';
import type {ManualAlias,ManualClassification} from './ManualTypeSelect';
import './review.css';

type Props = {
  draft:Draft; result:CheckResult; choices:MaskChoices; disabled:boolean;
  onChange:(choices:MaskChoices)=>void; onWrite:()=>void;
  onReviewChange:(candidates:Candidate[],choices:MaskChoices)=>boolean;
  onBusyChange:(busy:boolean)=>void;
};
type Pages = Record<'partial'|'full',number>;
const PAGE_SIZE=6;
const riskName=(c:Candidate)=>RISKS.find(r=>r.key===c.risk)!.name;

export function PrivacyReview({draft,result,choices,disabled,onChange,onWrite,onReviewChange,onBusyChange}:Props) {
  const candidates=useMemo(()=>[...result.candidates].sort((a,b)=>
    a.source===b.source?a.start-b.start:a.source==='title'?-1:1),[result]);
  const [selection,setSelection]=useState<Set<string>>(()=>new Set());
  const [multiple,setMultiple]=useState(false);
  const [display,setDisplay]=useState<'original'|'result'>('original');
  const [editing,setEditing]=useState<string|null>(null);
  const [customText,setCustomText]=useState<Record<string,string>>({});
  const [history,setHistory]=useState<{choices:MaskChoices;pages:Pages}[]>([]);
  const [pages,setPages]=useState<Pages>({partial:1,full:1});
  const [message,setMessage]=useState('');
  const [otherOpen,setOtherOpen]=useState(false);
  const [findingFilter,setFindingFilter]=useState<PostFilter>(EMPTY_POST_FILTER);
  const [sourceRange,setSourceRange]=useState<PostRange|null>(null);
  const [rangeTarget,setRangeTarget]=useState<Candidate|null>(null);
  const [rangeLabel,setRangeLabel]=useState('USER_DEFINED'),[mutationBusy,setMutationBusy]=useState(false);
  const mutationLock=useRef(false);
  useEffect(()=>()=>onBusyChange(false),[onBusyChange]);
  function processing(value:boolean){setMutationBusy(value);onBusyChange(value);}
  const manualAliases=useRef<ManualAlias[]>(Array.from(new Map(result.candidates.filter(c=>['VEHICLE','EMPLOYEE_ID','MEDICAL_INSURANCE','PRESCRIPTION_ID'].includes(c.label)&&c.autoMask?.choice?.mode==='custom').map(c=>[`${c.label}:${c.text}`,{label:c.label,text:c.text,alias:c.autoMask!.choice!.mode==='custom'?c.autoMask!.choice!.text:''}])).values()));
  const initialChoices=useRef(choices);
  const [autoState,setAutoState]=useState({lastAutoChoices:{} as MaskChoices,beforeAutoChoices:{} as MaskChoices});
  const sourceRoot=useRef<HTMLDivElement>(null);
  const sourceAnchor=useRef<{node:Node;offset:number;x:number;y:number}|null>(null);
  const suppressClick=useRef(0);
  const [tip,setTip]=useState<{text:string;left:number;top:number}|null>(null);
  const editor=useRef<HTMLElement>(null);
  const customInput=useRef<HTMLTextAreaElement>(null);
  const undoButton=useRef<HTMLButtonElement>(null);
  const selected=candidates.filter(c=>selection.has(c.id));
  const single=selected.length===1?selected[0]:null;
  const customOpen=single && editing===single.id;
  const processed=useMemo(()=>maskedDraft(draft,candidates,choices),[draft,candidates,choices]);
  const appliedCount=candidates.filter(c=>choices[c.id] && replacement(c,choices[c.id])!==c.text).length;
  const statusCounts=postStatusCounts(candidates,choices),assignedCount=candidates.length-statusCounts.unset;
  const automaticCandidates=useMemo(()=>candidates.map(c=>({...c,part:c.source,location:locationOf(draft,c)})),[candidates,draft]);
  const automaticSelection={...EMPTY_SELECTION,choices,initialChoices:initialChoices.current,...autoState};
  const rangeBlocked=!!sourceRange&&postRangeConflict(sourceRange,candidates,rangeTarget?.id);
  useEffect(()=>{
    const hide=()=>setTip(null);
    window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
    return()=>{window.removeEventListener('scroll',hide,true);window.removeEventListener('resize',hide);};
  },[]);
  const common=selected.length && selected.every(c=>choices[c.id]?.mode===choices[selected[0].id]?.mode)
    ? choices[selected[0].id]?.mode : undefined;
  const preview=single?(customOpen?customText[single.id]??single.text:replacement(single,choices[single.id])):'';
  let customError='';
  if (customOpen) {
    if (!preview.trim()) customError='바꿀 내용을 입력해 주세요.';
    else {
      const proposed=maskedDraft(draft,candidates,{...choices,[single.id]:{mode:'custom',text:preview}});
      if (Array.from(proposed.title).length>boot.maxTitle || Array.from(proposed.body).length>boot.maxBody)
        customError='수정 후 제목은 300자, 본문은 30,000자 이하여야 합니다.';
    }
  }

  function change(next:MaskChoices,text:string,nextPages?:Pages) {
    if (disabled) return;
    const proposed=maskedDraft(draft,candidates,next);
    if (Array.from(proposed.title).length>boot.maxTitle || Array.from(proposed.body).length>boot.maxBody) {
      setMessage('변경 후 글자 수가 한도를 넘습니다. 제목 300자·본문 30,000자 이내로 수정해 주세요.');
      return false;
    }
    setHistory(h=>[...h,{choices,pages}].slice(-20));
    onChange(next);setEditing(null);setMessage(text);
    if (nextPages) setPages(nextPages);
    return true;
  }
  function undo() {
    const last=history.at(-1);
    if (!last || disabled) return;
    onChange(last.choices);setPages(last.pages);setHistory(h=>h.slice(0,-1));
    setEditing(null);setMessage('바로 전 변경을 되돌렸어요.');
  }
  function choose(c:Candidate,additive=false) {
    if (disabled||performance.now()<suppressClick.current) return;
    setSourceRange(null);setRangeTarget(null);

    revealSidebar();
    if (!multiple && !additive) setSelection(new Set([c.id]));
    else setSelection(old=>{const next=new Set(old);next.has(c.id)?next.delete(c.id):next.add(c.id);return next;});
    if (additive) setMultiple(true);
    setEditing(null);
  }
  function openCustom(c:Candidate,fromList=false) {
    if (disabled) return;
    setSourceRange(null);setRangeTarget(null);

    setSelection(new Set([c.id]));setMultiple(false);setEditing(c.id);
    const current=choices[c.id];
    setCustomText(old=>({...old,[c.id]:old[c.id] ??
      (current?.mode==='custom'?current.text:replacement(c,current))}));
    requestAnimationFrame(()=>{
      if (fromList) editor.current?.scrollIntoView({block:'center',behavior:'instant'});
      customInput.current?.focus({preventScroll:true});
      const length=customInput.current?.value.length || 0;
      customInput.current?.setSelectionRange(length,length);
    });
  }
  function revealSidebar(){
    if(window.matchMedia('(max-width:1000px)').matches)requestAnimationFrame(()=>requestAnimationFrame(()=>document.getElementById('post-edit-panel')?.scrollIntoView({block:'start',behavior:'instant'})));
  }
  function selectionMode(next:boolean) {
    setMultiple(next);setEditing(null);
    if (!next) setSelection(new Set(selected.slice(0,1).map(c=>c.id)));
  }
  function applyMode(mode:MaskMode) {
    if (!selected.length || disabled) return;
    if (mode==='custom') {
      if (!single) return;
      openCustom(single);
      return;
    }
    const next={...choices};
    for (const c of selected) next[c.id]={mode};
    change(next,`${selected.length}곳에 ${MODE_NAMES[mode]}을 적용했어요.`,{partial:1,full:1});
  }
  function switchRow(c:Candidate,mode:'partial'|'full') {
    const next={...choices,[c.id]:{mode}};
    const index=candidates.filter(x=>next[x.id]?.mode===mode).findIndex(x=>x.id===c.id);
    setMultiple(false);setSelection(new Set([c.id]));
    change(next,`${c.labelName} · ${locationOf(draft,c)}을 ${MODE_NAMES[mode]} 목록으로 옮겼어요.`,
      {...pages,[mode]:Math.floor(index/PAGE_SIZE)+1});
    requestAnimationFrame(()=>document.getElementById(`switch-${c.id}`)?.focus({preventScroll:true}));
  }
  function cancelRow(c:Candidate) {
    const next={...choices};delete next[c.id];
    setMultiple(false);setSelection(new Set([c.id]));
    change(next,`${c.labelName} · ${locationOf(draft,c)} 적용 취소 · 원문 복원`);
    requestAnimationFrame(()=>undoButton.current?.focus({preventScroll:true}));
  }
  function badge(c:Candidate) {
    return <span className={`rv-risk risk-${c.risk}`}><i/>{riskName(c)}</span>;
  }
  function showTip(c:Candidate,element:HTMLButtonElement) {
    const box=element.getBoundingClientRect();
    setTip({text:`${riskName(c)} · ${c.labelName} · ${choices[c.id]?MODE_NAMES[choices[c.id].mode]:'미설정'}`,
      left:Math.max(8,Math.min(box.left,window.innerWidth-218)),
      top:box.top>70?box.top-58:box.bottom+7});
  }
  function mutate(next:{candidates:Candidate[];choices:MaskChoices},text:string){
    const proposed=maskedDraft(draft,next.candidates,next.choices);
    if(Array.from(proposed.title).length>boot.maxTitle||Array.from(proposed.body).length>boot.maxBody){setMessage('변경 후 글자 수가 한도를 넘습니다. 먼저 직접 수정 문구의 길이를 줄여 주세요.');return false;}
    if(!onReviewChange(next.candidates,next.choices)){setMessage('게시글이 변경되었습니다. 현재 원문에서 다시 추가해 주세요.');return false;}setHistory([]);setEditing(null);setPages({partial:1,full:1});
    setSelection(new Set());setSourceRange(null);setRangeTarget(null);setMessage(text);

    window.getSelection()?.removeAllRanges();
    return true;
  }
  function exclude(ids:string[]){
    if(disabled||!ids.length)return;
    mutate(excludePostCandidates(candidates,choices,ids),`${ids.length}곳을 검토 목록에서 제외했습니다. 해당 위치의 원문은 유지됩니다.`);
  }
  async function classifyManual(label:string,text:string){
    const value=label==='USER_DEFINED'?DEFAULT_MANUAL_TYPE:await api<ManualClassification>('manual-type',{label,text,aliases:manualAliases.current});
    if(value.aliases)manualAliases.current=value.aliases;
    return {label:value.label,labelName:value.labelName,risk:value.risk,autoMask:value.autoMask};
  }
  async function setManualType(candidate:Candidate,label:string){
    if(disabled||mutationLock.current||!candidate.addedByUser)return;
    mutationLock.current=true;processing(true);
    try{const metadata=await classifyManual(label,candidate.text);if(mutate({candidates:candidates.map(c=>c.id===candidate.id?{...c,...metadata}:c),choices},'사용자가 지정한 유형과 기본 위험도로 변경했습니다. 기존 처리 선택은 유지합니다.')){setSelection(new Set([candidate.id]));}}
    catch(e){setMessage(e instanceof Error?e.message:'유형을 변경하지 못했습니다.');}
    finally{mutationLock.current=false;processing(false);}
  }
  async function addRanges(ranges:PostRange[],replaceId?:string,mode?:MaskMode,label='USER_DEFINED'):Promise<boolean> {
    if(disabled||mutationLock.current)return false;
    mutationLock.current=true;processing(true);
    try{
      const types=new Map<string,Awaited<ReturnType<typeof classifyManual>>>();
      for(const range of ranges){const text=draft[range.source].slice(range.start,range.end);if(!types.has(text))types.set(text,await classifyManual(label,text));}
      const next=addPostRanges(draft,candidates,choices,ranges,replaceId);
      for(const candidate of next.added)Object.assign(candidate,types.get(candidate.text));
      if(mode&&next.added.length===1)next.choices[next.added[0].id]=mode==='custom'?{mode,text:next.added[0].text}:{mode};
      if(!mutate(next,replaceId?'선택한 글자 범위로 변경했습니다. 이전 처리 설정은 가져오지 않습니다.':`사용자 후보 ${next.added.length}곳을 추가했습니다. 처리 방법을 확인하세요.`))return false;
      setSelection(new Set(next.added.map(c=>c.id)));setMultiple(next.added.length>1);

      setDisplay('original');
      if(mode==='custom')openCustom(next.added[0]);
      requestAnimationFrame(()=>editor.current?.scrollIntoView({block:'center',behavior:'instant'}));
      return true;
    }catch(e){setMessage(e instanceof Error?e.message:'원문 위치를 다시 선택해 주세요.');return false;}
    finally{mutationLock.current=false;processing(false);}
  }
  function beginAdd(){
    setDisplay('original');setSourceRange(null);setRangeTarget(null);setSelection(new Set());setEditing(null);setRangeLabel('USER_DEFINED');
    sourceAnchor.current=null;window.getSelection()?.removeAllRanges();setMessage('원본에서 원하는 문구를 드래그해 계속 추가하세요.');
    requestAnimationFrame(()=>sourceRoot.current?.scrollIntoView({block:'center',behavior:'instant'}));
  }
  function locateRange(range:PostRange){

    setDisplay('original');setSourceRange(range);setRangeTarget(null);setEditing(null);setSelection(new Set());
    requestAnimationFrame(()=>{
      const element=sourceRoot.current?.querySelector<HTMLElement>(`[data-source-part="${range.source}"]`);
      if(element){element.scrollIntoView({block:'center',behavior:'instant'});showSourceRange(element,range.start,range.end);}
    });
  }
  function locateCandidate(c:Candidate){

    setSelection(new Set([c.id]));setMultiple(false);setEditing(null);setSourceRange(null);setRangeTarget(null);
    setDisplay('original');requestAnimationFrame(()=>document.getElementById(`candidate-${c.id}`)?.scrollIntoView({block:'center',behavior:'instant'}));
  }
  function adjustRange(c:Candidate){
    setRangeLabel(c.addedByUser?c.label:'USER_DEFINED');
    locateRange(c);setRangeTarget(c);setMessage('원문의 글자를 다시 드래그해 원하는 범위로 조정한 뒤 추가하세요.');
  }
  function extendSource(root:HTMLElement,x:number,y:number){
    const anchor=sourceAnchor.current;
    if(!anchor||Math.hypot(x-anchor.x,y-anchor.y)<4)return;
    const end=sourceCaret(root,x,y);if(end)window.getSelection()?.setBaseAndExtent(anchor.node,anchor.offset,end.startContainer,end.startOffset);
  }
  function selectSource(root:HTMLElement){
    if(disabled||display!=='original')return;
    const range=readSourceRange(root,window.getSelection());
    if(!range||!['title','body'].includes(range.part))return;
    const next=normalizePostRange(draft,{source:range.part as 'title'|'body',start:range.start,end:range.end});
    if(!next)return;
    suppressClick.current=performance.now()+250;
    if(rangeTarget&&rangeTarget.source!==next.source){setMessage('범위를 변경할 후보와 같은 제목 또는 본문에서 선택하세요.');return;}
    setSourceRange(next);setEditing(null);setSelection(new Set());

    revealSidebar();
  }
  function marked(text:string,source:'title'|'body') {
    let end=0;
    return <>{candidates.filter(c=>c.source===source).map(c=>{
      const before=text.slice(end,c.start);end=c.end;
      return <Fragment key={c.id}>{before}<span className="rv-mark-wrap">
        <button type="button" id={`candidate-${c.id}`} data-candidate-id={c.id}
          className={`marker rv-mark risk-${c.risk}`} aria-pressed={selection.has(c.id)} data-state={postStatus(c,choices)}
          aria-label={`${c.labelName} · ${riskName(c)} · ${locationOf(draft,c)} · ${c.text} · ${POST_STATUSES.find(s=>s.key===postStatus(c,choices))?.name}`}
          onMouseEnter={e=>showTip(c,e.currentTarget)} onMouseLeave={()=>setTip(null)}
          onFocus={e=>showTip(c,e.currentTarget)} onBlur={()=>setTip(null)}
          onKeyDown={e=>{if(e.key==='Escape')setTip(null);}} onClick={e=>{setTip(null);choose(c,e.ctrlKey||e.metaKey);}}>
          {display==='original'?c.text:replacement(c,choices[c.id])}
        </button>
      </span></Fragment>;
    })}{text.slice(end)}</>;
  }
  function listRow(c:Candidate) {
    const mode=choices[c.id].mode;
    return <li className="rv-row" data-id={c.id} data-selected={selection.has(c.id)} key={c.id}>
      <button className="rv-row-main" onClick={()=>openCustom(c,true)} aria-pressed={selection.has(c.id)}
        aria-label={`${c.labelName} · ${locationOf(draft,c)} · ${c.text} 직접 수정`}>
        <span className="rv-row-meta">{badge(c)}<span>{c.labelName} · {locationOf(draft,c)}</span><span>직접 수정 ↗</span></span>
        <span className="rv-row-change">{mode==='keep'?<span>{candidateSummary(c)}</span>:<s>{candidateSummary(c)}</s>}<span aria-hidden="true">→</span><strong>{isCredential(c)&&mode==='keep'?'원문 유지':replacement(c,choices[c.id])}</strong></span>
        {(mode==='keep'||mode==='custom')&&<span className="rv-row-mode">{MODE_NAMES[mode]}</span>}
      </button>
      <div className="rv-row-actions">
        {(mode==='partial'||mode==='full')&&<button className="rv-small" id={`switch-${c.id}`} data-action="switch"
          aria-label={`${c.labelName} · ${locationOf(draft,c)} · ${mode==='partial'?'전체':'부분'} 가림으로 전환`}
          onClick={()=>switchRow(c,mode==='partial'?'full':'partial')}>⇄ {mode==='partial'?'전체로':'부분으로'}</button>}
        <button className="rv-small rv-cancel" data-action="cancel" aria-label={`${c.labelName} · ${locationOf(draft,c)} · 적용 취소`}
          onClick={()=>cancelRow(c)}>× 취소</button>
      </div>
    </li>;
  }
  function listPanel(mode:'partial'|'full') {
    const items=candidates.filter(c=>choices[c.id]?.mode===mode);
    const totalPages=Math.max(1,Math.ceil(items.length/PAGE_SIZE));
    const page=Math.max(1,Math.min(pages[mode],totalPages));
    return <section className="rv-list" data-list={mode} aria-label={`${MODE_NAMES[mode]} 적용 목록`}>
      <div className="rv-list-head"><h2>{MODE_NAMES[mode]} 적용 목록</h2><span>{items.length}곳</span></div>
      {items.length?<ol>{items.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE).map(listRow)}</ol>:
        <p className="rv-list-empty">{MODE_NAMES[mode]}한 항목이 여기에 표시돼요.</p>}
      <div className="rv-pager"><span>{items.length?`${(page-1)*PAGE_SIZE+1}–${Math.min(page*PAGE_SIZE,items.length)} / ${items.length}곳`:'0곳'}</span>
        {totalPages>1?<div><button className="rv-small" disabled={page===1} onClick={()=>setPages(p=>({...p,[mode]:page-1}))}>이전</button><span>{page} / {totalPages}</span><button className="rv-small" disabled={page===totalPages} onClick={()=>setPages(p=>({...p,[mode]:page+1}))}>다음</button></div>:<span>항목을 눌러 직접 수정</span>}
      </div>
    </section>;
  }
  const others=candidates.filter(c=>['keep','custom'].includes(choices[c.id]?.mode));
  return <fieldset className="privacy-review post-file-unified" disabled={disabled||mutationBusy} aria-busy={mutationBusy} aria-label="개인정보 검토와 수정">
    {tip&&<div className="rv-tooltip" role="tooltip" style={{left:tip.left,top:tip.top}}>{tip.text}</div>}
    <div className="page-heading"><div><span className="eyebrow">게시글 개인정보 검토</span><h1>원문을 보면서, 필요한 부분만 가리세요.</h1><p>오탐은 제외하고 누락은 추가한 뒤 처리 결과를 비교하세요.</p></div><div className="rv-continue"><button className="secondary" onClick={onWrite}>수정한 글로 이어쓰기</button><span>적용한 가림·수정을 가져갑니다.</span></div></div>
    <p className="review-notice result-notice">자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다. 게시 전, 표시되지 않은 부분까지 직접 한 번 더 확인해 주세요.</p>
    <section className="post-shared-overview" aria-label="개인정보 후보 대시보드">
      <FileFindings overview="only" candidates={automaticCandidates} selection={{...automaticSelection,filter:findingFilter.risk,search:findingFilter.query,selected:[...selection]}} locked={disabled||mutationBusy} onState={patch=>setFindingFilter(current=>({...current,...(patch.filter?{risk:patch.filter as PostFilter['risk']}:{}),...(patch.search!==undefined?{query:patch.search}:{})}))} onSelect={locateCandidate} onApply={(mode,ids)=>{const next={...choices};for(const id of ids)next[id]=mode==='custom'?{mode,text:candidates.find(c=>c.id===id)?.text||''}:{mode};change(next,'선택한 항목의 처리 방법을 지정했습니다.');}} formatReplacement={replacement}/>
      <div className="rv-status-overview"><div className="rv-status-title"><strong>처리 지정 <b>{assignedCount}</b> / {candidates.length}곳</strong><span>미설정 {statusCounts.unset}곳 · 저장 전 원문과 비교하세요</span></div>
        <div className="rv-status-meter" role="img" aria-label={POST_STATUSES.map(s=>`${s.name} ${statusCounts[s.key]}곳`).join(', ')}>{POST_STATUSES.map(s=>statusCounts[s.key]>0&&<span key={s.key} className={`state-${s.key}`} style={{width:`${statusCounts[s.key]/candidates.length*100}%`}}/>)}</div>
        <div className="rv-status-chips">{POST_STATUSES.map(s=><button className={`state-${s.key}`} key={s.key} aria-pressed={findingFilter.status===s.key} onClick={()=>{setFindingFilter({...findingFilter,status:findingFilter.status===s.key?'all':s.key});}}><i/>{s.name} <b>{statusCounts[s.key]}</b></button>)}</div>
      </div>
      <button className="post-reset-filter" onClick={()=>setFindingFilter(EMPTY_POST_FILTER)}>전체 목록 보기</button>
      {candidates.length===0&&<p className="rv-list-empty">현재 검토 후보가 없습니다. 원문 검색·드래그로 누락을 추가할 수 있습니다.</p>}
    </section>
    {candidates.some(isCredential)&&<p className="review-notice">인증정보는 전체 가림을 기본 지정했습니다. 부분 가림을 선택해도 전체를 가립니다. 실제 유효성·권한은 확인하지 않으며, 이미 공유한 키는 폐기·재발급하고 비밀번호는 변경하세요.</p>}
    <div className="rv-workspace-toolbar"><div className="rv-workflow"><span><b>1</b>목록 정리</span><i>→</i><span><b>2</b>가림·수정</span><i>→</i><span><b>3</b>원문과 비교</span></div>
    <AutoMaskPanel scope="post" candidates={automaticCandidates} selection={automaticSelection} locked={disabled} onNotice={setMessage} onChange={patch=>{
      if(!patch.choices||!change(patch.choices,'자동 가림 설정을 변경했습니다.'))return false;
      setAutoState({lastAutoChoices:patch.lastAutoChoices||{},beforeAutoChoices:patch.beforeAutoChoices||{}});setDisplay('result');return true;
    }}/>
    </div>
    <PostKeywordSearch draft={draft} candidates={candidates} disabled={disabled||mutationBusy} onLocate={(range,label)=>{setRangeLabel(label);locateRange(range);}} onAdd={(ranges,label)=>addRanges(ranges,undefined,undefined,label)}/>
    <div className="rv-workspace"><div className="rv-document-column">
    <article className="post rv-post" aria-label="전체 본문 미리보기">
      <div className="rv-document-head document-preview-head"><div><span className="eyebrow">제목 · 본문</span><h2>전체 본문 미리보기</h2></div><div className="rv-view segmented" role="group" aria-label="본문 표시 방식">
        <button aria-pressed={display==='original'} onClick={()=>setDisplay('original')}>원본</button>
        <button aria-pressed={display==='result'} onClick={()=>setDisplay('result')}>적용 미리보기</button>
      </div><button className="secondary post-add-range" onClick={beginAdd}>누락 항목 추가</button></div>
      <div className="rv-selection" data-multiple={multiple}>
        <div className="rv-selection-bar"><div className="rv-selection-mode" role="group" aria-label="항목 선택 방법">
          <button aria-pressed={!multiple} onClick={()=>selectionMode(false)}>한 개씩 선택</button>
          <button aria-pressed={multiple} onClick={()=>selectionMode(true)}>여러 개 선택</button>
        </div><div className="rv-selection-actions"><strong className="rv-selection-count" role="status" aria-live="polite">{selection.size}곳 선택</strong>
          <button disabled={!candidates.length} onClick={()=>{setMultiple(true);setSelection(new Set(candidates.map(c=>c.id)));setEditing(null);}}>전체 {candidates.length}곳 선택</button>
          <button disabled={!selection.size} onClick={()=>{setSelection(new Set());setEditing(null);}}>선택 해제</button>
        </div></div>
        <p className="rv-selection-hint">{multiple?'Ctrl 없이 항목을 차례로 누르세요. 다시 누르면 선택이 해제됩니다.':'여러 항목을 함께 처리하려면 ‘여러 개 선택’을 누른 뒤 본문에서 골라 주세요.'}</p>
      </div>
      <p className="rv-source-hint">{display==='original'?'후보를 클릭하거나 글자를 드래그해 범위를 지정하세요. 추가 후에도 원본에서 계속 선택할 수 있습니다.':<>적용 미리보기입니다. 새 내용을 추가하려면 <button onClick={beginAdd}>원본에서 계속 추가</button>를 누르세요.</>}</p>
      <div ref={sourceRoot} data-display={display} className={`post-inner rv-source ${display==='original'?'selectable':''}`}
        onPointerDown={e=>{sourceAnchor.current=null;suppressClick.current=0;if(disabled||display!=='original'||e.button!==0)return;const caret=sourceCaret(e.currentTarget,e.clientX,e.clientY);if(caret){e.preventDefault();sourceAnchor.current={node:caret.startContainer,offset:caret.startOffset,x:e.clientX,y:e.clientY};window.getSelection()?.removeAllRanges();}}}
        onPointerMove={e=>{if(e.buttons!==1){sourceAnchor.current=null;return;}extendSource(e.currentTarget,e.clientX,e.clientY);}}
        onPointerUp={e=>{extendSource(e.currentTarget,e.clientX,e.clientY);sourceAnchor.current=null;selectSource(e.currentTarget);}}
        onPointerCancel={()=>{sourceAnchor.current=null;}} onKeyUp={e=>{if(e.shiftKey)selectSource(e.currentTarget);}}>
        <h2 data-source-part="title" data-source-selectable={display==='original'}>{draft.title?marked(draft.title,'title'):display==='result'?'제목 없음':null}</h2>
        <div className="post-body" data-source-part="body" data-source-selectable={display==='original'}>{marked(draft.body,'body')}</div></div>
      <div className="rv-legend"><span><i className="rv-legend-unset"/>미설정 후보</span><span><i className="rv-legend-assigned"/>✓ 처리 지정</span><span><i className="rv-legend-kept"/>원문 유지</span><span>{display==='original'?'위험도는 강조 색으로 구분합니다.':'원문에서 위험도 색을 확인할 수 있습니다.'}</span></div>
    </article>
    </div><aside className="rv-sidebar file-controls" aria-label="게시글 검토 도구">
      <div id="post-edit-panel">
    {sourceRange&&display==='original'&&<section className="rv-editor source-range-editor" id="post-source-range-editor" aria-label="선택한 원문 범위">
      <h2>{rangeTarget?'글자 범위 변경':'선택한 원문'}</h2><p>{locationOf(draft,sourceRange)}</p><blockquote>{draft[sourceRange.source].slice(sourceRange.start,sourceRange.end)}</blockquote>
      <p>{rangeBlocked?'다른 검토 후보와 겹칩니다. 범위를 조정하거나 겹치는 후보를 먼저 제외하세요.':'사용자 후보로 추가합니다. 원문을 다시 드래그해 범위를 조정할 수 있습니다.'}</p>
      <ManualTypeSelect value={rangeLabel} onChange={setRangeLabel} disabled={disabled||mutationBusy}/>
      <div className="rv-tools-actions"><button className="primary" disabled={disabled||rangeBlocked} onClick={()=>void addRanges([sourceRange],rangeTarget?.id,undefined,rangeLabel)}>목록에만 추가</button>{(['partial','full','custom'] as const).map(mode=><button key={mode} disabled={disabled||rangeBlocked} onClick={()=>void addRanges([sourceRange],rangeTarget?.id,mode,rangeLabel)}>{MODE_NAMES[mode]}</button>)}<button onClick={()=>{setSourceRange(null);setRangeTarget(null);window.getSelection()?.removeAllRanges();}}>취소</button></div>
    </section>}
    <section className="rv-editor file-choice-editor" ref={editor} aria-label="선택한 개인정보 편집" hidden={!selected.length||!!sourceRange&&display==='original'}>
      {!selected.length?<div className="rv-editor-empty"><span aria-hidden="true">↖</span><h2>원문에서 항목을 선택하세요</h2><p>후보를 누르면 처리 방법이 보입니다.<br/>글자를 드래그해 새 범위를 추가할 수도 있습니다.</p><button className="secondary" onClick={()=>document.querySelector('.rv-post-findings')?.scrollIntoView({block:'start',behavior:'instant'})}>검출 목록 보기</button></div>:<>
        <div className="rv-editor-heading"><h2>{single?'선택한 항목':'선택 항목 함께 처리'}</h2>{single&&<span className={`rv-state state-${postStatus(single,choices)}`}>{POST_STATUSES.find(s=>s.key===postStatus(single,choices))?.name}</span>}</div>
        <div className="rv-editor-meta"><span>{single?<>{single.labelName} · {locationOf(draft,single)} {badge(single)}</>:`${selected.length}곳 선택 · 선택한 항목에 함께 적용`}</span><span>{customOpen?'직접 수정 작성 중':common?MODE_NAMES[common]:single?'미설정':'미설정 또는 여러 처리 방식'}</span></div>
        <div className="rv-original"><span className="eyebrow">원문</span>{single?single.text:selected.slice(0,3).map(c=>c.text).join(' · ')+(selected.length>3?` 외 ${selected.length-3}곳`:'')}</div>
        {single?.addedByUser&&<ManualTypeSelect caption="사용자 추가 유형" value={single.label} onChange={label=>void setManualType(single,label)} disabled={disabled||mutationBusy}/>}
        {single?.credential&&<p className="rv-help">인증정보 · {single.credential.provider} · {single.credential.reason}</p>}
        <div className="rv-methods" role="group" aria-label="선택한 항목 처리 방법">
          {(['partial','full','keep','custom'] as const).map(mode=><button data-mode={mode} key={mode}
            aria-pressed={(customOpen?'custom':common)===mode} disabled={mode==='custom'&&!single}
            onClick={()=>applyMode(mode)}>{mode==='partial'?'*** ':mode==='full'?'██ ':''}{MODE_NAMES[mode]}</button>)}
        </div>
        {customOpen&&<div className="rv-custom"><label htmlFor="replacement-text">바꿀 내용</label><textarea ref={customInput} id="replacement-text" value={customText[single.id]??single.text}
          onChange={e=>setCustomText(old=>({...old,[single.id]:e.target.value}))}
          aria-describedby="replacement-help" aria-invalid={!!customError} rows={2} autoFocus spellCheck={false}/>
          <div><span id="replacement-help" className={customError?'rv-error':''}>{customError||'입력 후 ‘수정 내용 반영’을 누르면 적용돼요.'}</span>
            <button className="primary" disabled={!!customError} onClick={()=>change({...choices,[single.id]:{mode:'custom',text:preview}},'입력한 내용으로 수정했어요.')}>수정 내용 반영</button></div></div>}
        <div className="rv-editor-bottom"><div><span>변경 예정</span><strong>{single?preview:`${selected.length}곳에 선택한 방식 적용`}</strong></div><button onClick={undo} disabled={!history.length}>↶ 되돌리기</button></div>
        <p className="rv-help">{single?'이 항목만 개별적으로 수정합니다.':'직접 수정은 항목을 하나만 선택했을 때 사용할 수 있어요.'}</p>
        <div className="rv-tools-actions">{single&&<button onClick={()=>adjustRange(single)}>글자 범위 변경</button>}<button onClick={()=>exclude(selected.map(c=>c.id))}>선택 후보 제외</button></div>
      </>}
    </section>
    </div>
      <PostFindings draft={draft} candidates={candidates} choices={choices} selected={selection} disabled={disabled} filter={findingFilter} onFilter={setFindingFilter} onSelection={ids=>{setSelection(ids);setMultiple(true);setEditing(null);setSourceRange(null);setRangeTarget(null);}} onLocate={locateCandidate} onExclude={exclude} onApply={(c,mode)=>{setSelection(new Set([c.id]));setMultiple(false);if(mode==='custom')openCustom(c);else change({...choices,[c.id]:{mode}},`${c.labelName}에 ${MODE_NAMES[mode]}을 지정했습니다.`);}}/>
    </aside></div>
    <div className="rv-list-toolbar"><span role="status" aria-live="polite">{message||'항목 오른쪽에서 가림 방식을 변경하거나 취소하세요.'}</span><button ref={undoButton} onClick={undo} disabled={!history.length}>↶ 되돌리기</button></div>
    <details className="rv-treatment-history"><summary>처리 지정 내역 <span>부분 가림 {statusCounts.partial} · 전체 가림 {statusCounts.full} · 직접 수정 {statusCounts.custom} · 원문 유지 {statusCounts.keep}</span></summary>
    <div className="rv-lists">{listPanel('partial')}{listPanel('full')}</div>
    <details className="rv-other" open={otherOpen} onToggle={e=>setOtherOpen(e.currentTarget.open)}>
      <summary>그 외 처리 · 가리지 않음 {others.filter(c=>choices[c.id].mode==='keep').length}곳 · 직접 수정 {others.filter(c=>choices[c.id].mode==='custom').length}곳</summary>
      {otherOpen&&(others.length?<ol>{others.map(listRow)}</ol>:<p className="rv-list-empty">원문 유지 또는 직접 수정한 항목이 여기에 표시돼요.</p>)}
    </details>
    </details>
    <div className="rv-finish"><p><strong>{appliedCount}곳에 가림·수정 반영</strong><span>저장하면 처리 결과의 제목·본문이 저장돼요. 다시 불러오면 재검사합니다.</span></p><button className="secondary" onClick={onWrite}>수정한 글로 이어쓰기 →</button></div>
    <p className="rv-engine">{result.engine} · {(result.elapsedMs/1000).toFixed(1)}초 · 처리 결과 {Array.from(processed.title).length+Array.from(processed.body).length}자</p>
  </fieldset>;
}
