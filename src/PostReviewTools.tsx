import {useEffect,useMemo,useRef,useState} from 'react';
import type {Candidate,Draft} from './types';
import {candidateSummary,locationOf,MODE_NAMES,replacement,RISKS} from './masking';
import type {MaskChoices,MaskMode} from './masking';
import {filterPostCandidates,POST_STATUSES,postStatus,searchPost} from './postReview';
import type {PostFilter,PostRange} from './postReview';
import {ManualTypeSelect} from './ManualTypeSelect';

const SIZE=30;
function Pager({page,total,onPage}:{page:number;total:number;onPage:(page:number)=>void}){
  const last=Math.max(0,Math.ceil(total/SIZE)-1);
  return <div className="rv-pager"><span>{total?`${page*SIZE+1}–${Math.min((page+1)*SIZE,total)} / ${total}곳`:'0곳'}</span><div><button disabled={!page} onClick={()=>onPage(page-1)}>이전</button><span>{page+1} / {last+1}</span><button disabled={page>=last} onClick={()=>onPage(page+1)}>다음</button></div></div>;
}
function SelectAll({checked,partial,disabled,onChange,label}:{checked:boolean;partial:boolean;disabled:boolean;onChange:(v:boolean)=>void;label:string}){
  const ref=useRef<HTMLInputElement>(null);
  useEffect(()=>{if(ref.current)ref.current.indeterminate=partial&&!checked;},[checked,partial]);
  return <label><input ref={ref} type="checkbox" disabled={disabled} checked={checked} onChange={e=>onChange(e.target.checked)}/>{label}</label>;
}

export function PostFindings({draft,candidates,choices,selected,disabled,filter,onFilter,onSelection,onLocate,onExclude,onApply}:{draft:Draft;candidates:Candidate[];choices:MaskChoices;selected:Set<string>;disabled:boolean;filter:PostFilter;onFilter:(filter:PostFilter)=>void;onSelection:(ids:Set<string>)=>void;onLocate:(c:Candidate)=>void;onExclude:(ids:string[])=>void;onApply:(c:Candidate,mode:MaskMode)=>void}){
  const [page,setPage]=useState(0);
  useEffect(()=>setPage(0),[filter.query,filter.risk,filter.status]);
  const filtered=filterPostCandidates(draft,candidates,choices,filter).sort((a,b)=>RISKS.findIndex(r=>r.key===a.risk)-RISKS.findIndex(r=>r.key===b.risk));
  const picked=filtered.filter(c=>selected.has(c.id)),current=Math.min(page,Math.max(0,Math.ceil(filtered.length/SIZE)-1));
  function toggle(id:string,value:boolean){const next=new Set(selected);if(value)next.add(id);else next.delete(id);onSelection(next);}
  return <section className="rv-tools rv-post-findings file-findings-panel" aria-label="게시글 검출 목록 정리">
    <div className="rv-tools-head"><h2>검출 목록 <small>{filtered.length} / {candidates.length}곳</small></h2><button onClick={()=>onFilter({query:'',risk:'all',status:'all'})} disabled={!filter.query&&filter.risk==='all'&&filter.status==='all'}>필터 해제</button><label>목록 검색<input value={filter.query} onChange={e=>onFilter({...filter,query:e.target.value})} placeholder="내용·유형·위치 검색"/></label><div className="rv-finding-filters"><label>위험도<select aria-label="위험도" value={filter.risk} onChange={e=>onFilter({...filter,risk:e.target.value as PostFilter['risk']})}><option value="all">전체 위험도</option>{RISKS.map(r=><option key={r.key} value={r.key}>{r.name}</option>)}</select></label><label>처리 상태<select aria-label="처리 상태" value={filter.status} onChange={e=>onFilter({...filter,status:e.target.value as PostFilter['status']})}><option value="all">전체 상태</option>{POST_STATUSES.map(s=><option key={s.key} value={s.key}>{s.name}</option>)}</select></label></div></div>
    <p>위험도는 원문 기준입니다. 제외하면 이 위치의 원문은 유지됩니다.</p>
    <div className="rv-tools-actions"><SelectAll checked={!!filtered.length&&picked.length===filtered.length} partial={!!picked.length} disabled={disabled||!filtered.length} label="검색·필터 결과 전체 선택" onChange={value=>{const next=new Set(selected);for(const c of filtered){if(value)next.add(c.id);else next.delete(c.id);}onSelection(next);}}/><span>{picked.length}곳 선택</span><button className="secondary" disabled={disabled||!picked.length} onClick={()=>onExclude(picked.map(c=>c.id))}>선택 후보 제외</button></div>
    <div className="rv-finding-scroll">{RISKS.map(r=>{
      const items=filtered.slice(current*SIZE,(current+1)*SIZE).filter(c=>c.risk===r.key);
      return items.length>0&&<details className={`rv-finding-group risk-${r.key}`} key={r.key} open><summary><span><i/>{r.name}</span><span>{filtered.filter(c=>c.risk===r.key).length}곳 <span aria-hidden="true">⌄</span></span></summary>
      <ol className="rv-findings">{items.map(c=><li key={c.id} data-selected={selected.has(c.id)} data-state={postStatus(c,choices)}>
        <input type="checkbox" aria-label={`${c.labelName} ${locationOf(draft,c)} 후보 선택`} checked={selected.has(c.id)} disabled={disabled} onChange={e=>toggle(c.id,e.target.checked)}/>
        <div className="rv-finding-card"><button className="rv-finding-main" onClick={()=>onLocate(c)} aria-label={`${c.labelName} ${candidateSummary(c)} 원문 위치`}><span className="rv-finding-meta"><b>{c.labelName}</b><span className={`rv-state state-${postStatus(c,choices)}`}>{POST_STATUSES.find(s=>s.key===postStatus(c,choices))?.name}</span></span><strong>{candidateSummary(c)}</strong><small>{locationOf(draft,c)}{c.addedByUser?c.label==='USER_DEFINED'?' · 사용자 추가 · 유형 미지정':' · 사용자 지정 유형 · 기본 위험도':''}</small>
          {choices[c.id]&&choices[c.id].mode!=='keep'&&<span className="rv-finding-change">변경 예정 <b>{replacement(c,choices[c.id])||'(빈 내용)'}</b></span>}
        </button><div className="rv-finding-actions"><select aria-label={`${c.labelName} ${locationOf(draft,c)} 처리 방법`} disabled={disabled} value={choices[c.id]?.mode||''} onChange={e=>onApply(c,e.target.value as MaskMode)}><option value="" disabled>처리 방법 선택</option>{(['partial','full','keep','custom'] as MaskMode[]).map(mode=><option key={mode} value={mode}>{MODE_NAMES[mode]}</option>)}</select><button disabled={disabled} onClick={()=>onExclude([c.id])}>제외</button></div></div>
      </li>)}</ol></details>;
    })}</div>
    {!filtered.length&&<p className="rv-list-empty">{candidates.length?'조건에 맞는 후보가 없습니다. 검색어와 위험도를 확인하세요.':'남은 검토 후보가 없습니다. 원문 검색·드래그로 누락된 내용을 추가할 수 있습니다.'}</p>}
    {filtered.length>SIZE&&<Pager page={current} total={filtered.length} onPage={setPage}/>}
  </section>;
}

export function PostKeywordSearch({draft,candidates,disabled,onLocate,onAdd}:{draft:Draft;candidates:Candidate[];disabled:boolean;onLocate:(range:PostRange,label:string)=>void;onAdd:(ranges:PostRange[],label:string)=>Promise<boolean>}){
  const [input,setInput]=useState(''),[query,setQuery]=useState(''),[selected,setSelected]=useState<string[]>([]),[page,setPage]=useState(0);
  const [label,setLabel]=useState('USER_DEFINED'),[adding,setAdding]=useState(false),addLock=useRef(false);
  const matches=useMemo(()=>searchPost(draft,candidates,query),[draft,candidates,query]),available=matches.filter(m=>!m.blocked),selectedIds=new Set(selected),chosen=available.filter(m=>selectedIds.has(m.id));
  const current=Math.min(page,Math.max(0,Math.ceil(matches.length/SIZE)-1));
  const stale=input!==query;
  return <details className="rv-tools rv-keywords"><summary>원문에서 누락 항목 검색·추가</summary>
    <p>제목·본문에서 대소문자·띄어쓰기가 같은 문구를 찾습니다. 한 개·여러 개·전체 위치를 선택해 추가하세요. 추가만으로 가림이 적용되지는 않습니다.</p>
    <form className="rv-tools-actions" onSubmit={e=>{e.preventDefault();setQuery(input);setSelected([]);setPage(0);}}><label>원문 키워드<input value={input} onChange={e=>setInput(e.target.value)} placeholder="찾을 문구 입력"/></label><button className="secondary" disabled={disabled||!input.trim()}>원문 검색</button></form>
    <ManualTypeSelect value={label} onChange={setLabel} disabled={disabled||adding}/>
    {query&&<><div className="rv-tools-actions"><SelectAll checked={!!available.length&&chosen.length===available.length} partial={!!chosen.length} disabled={disabled||stale||!available.length} label="추가 가능한 검색 결과 전체 선택" onChange={v=>setSelected(v?available.map(m=>m.id):[])}/><span>검색 {matches.length}곳 · 추가 가능 {available.length}곳 · 선택 {chosen.length}곳</span><button className="primary" disabled={disabled||adding||stale||!chosen.length} onClick={async()=>{if(addLock.current)return;addLock.current=true;setAdding(true);try{if(await onAdd(chosen,label))setSelected([]);}finally{addLock.current=false;setAdding(false);}}}>{adding?'추가 중…':`선택한 ${chosen.length}곳 추가`}</button></div>
    {stale&&<p role="status">검색어가 바뀌었습니다. 원문 검색을 다시 눌러 주세요.</p>}
    <ol className="rv-findings">{matches.slice(current*SIZE,(current+1)*SIZE).map(m=><li key={m.id}>
      <input type="checkbox" aria-label={`${locationOf(draft,m)} 검색 결과 선택`} disabled={disabled||stale||m.blocked} checked={!m.blocked&&selectedIds.has(m.id)} onChange={e=>setSelected(e.target.checked?[...selected,m.id]:selected.filter(id=>id!==m.id))}/>
      <div><small>{locationOf(draft,m)}</small><span className="rv-search-context">{draft[m.source].slice(Math.max(0,m.start-28),m.start)}<mark>{m.text}</mark>{draft[m.source].slice(m.end,m.end+36)}</span>{m.blocked&&<small>활성 후보와 겹치는 위치입니다. 기존 후보를 조정하거나 제외한 뒤 추가하세요.</small>}</div>
      <button disabled={disabled||stale} onClick={()=>onLocate(m,label)}>위치 보기·범위 조정</button>
    </li>)}</ol>
    {!matches.length&&<p className="rv-list-empty">일치하는 문구가 없습니다.</p>}
    {matches.length>SIZE&&<Pager page={current} total={matches.length} onPage={setPage}/>}</>}
  </details>;
}
