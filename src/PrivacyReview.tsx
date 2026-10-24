import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import type { Candidate, CheckResult, Draft } from './types';
import { boot } from './api';
import { locationOf, maskedDraft, MODE_NAMES, replacement, RISKS } from './masking';
import type { MaskChoices, MaskMode } from './masking';
import './review.css';

type Props = {
  draft:Draft; result:CheckResult; choices:MaskChoices; disabled:boolean;
  onChange:(choices:MaskChoices)=>void; onWrite:()=>void;
};
type Pages = Record<'partial'|'full',number>;
const PAGE_SIZE=6;
const riskName=(c:Candidate)=>RISKS.find(r=>r.key===c.risk)!.name;

export function PrivacyReview({draft,result,choices,disabled,onChange,onWrite}:Props) {
  const candidates=useMemo(()=>[...result.candidates].sort((a,b)=>
    a.source===b.source?a.start-b.start:a.source==='title'?-1:1),[result]);
  const [selection,setSelection]=useState(()=>new Set(candidates.slice(0,1).map(c=>c.id)));
  const [multiple,setMultiple]=useState(false);
  const [display,setDisplay]=useState<'original'|'result'>('original');
  const [editing,setEditing]=useState<string|null>(null);
  const [customText,setCustomText]=useState<Record<string,string>>({});
  const [history,setHistory]=useState<{choices:MaskChoices;pages:Pages}[]>([]);
  const [pages,setPages]=useState<Pages>({partial:1,full:1});
  const [message,setMessage]=useState('');
  const [otherOpen,setOtherOpen]=useState(false);
  const [tip,setTip]=useState<{text:string;left:number;top:number}|null>(null);
  const editor=useRef<HTMLElement>(null);
  const customInput=useRef<HTMLTextAreaElement>(null);
  const undoButton=useRef<HTMLButtonElement>(null);
  const selected=candidates.filter(c=>selection.has(c.id));
  const single=selected.length===1?selected[0]:null;
  const customOpen=single && editing===single.id;
  const processed=useMemo(()=>maskedDraft(draft,candidates,choices),[draft,candidates,choices]);
  const appliedCount=candidates.filter(c=>choices[c.id] && replacement(c,choices[c.id])!==c.text).length;
  const counts=Object.fromEntries(RISKS.map(r=>[r.key,candidates.filter(c=>c.risk===r.key).length]));
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
      return;
    }
    setHistory(h=>[...h,{choices,pages}].slice(-20));
    onChange(next);setEditing(null);setMessage(text);
    if (nextPages) setPages(nextPages);
  }
  function undo() {
    const last=history.at(-1);
    if (!last || disabled) return;
    onChange(last.choices);setPages(last.pages);setHistory(h=>h.slice(0,-1));
    setEditing(null);setMessage('바로 전 변경을 되돌렸어요.');
  }
  function choose(c:Candidate,additive=false) {
    if (disabled) return;
    if (!multiple && !additive) setSelection(new Set([c.id]));
    else setSelection(old=>{const next=new Set(old);next.has(c.id)?next.delete(c.id):next.add(c.id);return next;});
    if (additive) setMultiple(true);
    setEditing(null);
  }
  function openCustom(c:Candidate,fromList=false) {
    if (disabled) return;
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
  function marked(text:string,source:'title'|'body') {
    let end=0;
    return <>{candidates.filter(c=>c.source===source).map(c=>{
      const before=text.slice(end,c.start);end=c.end;
      return <Fragment key={c.id}>{before}<span className="rv-mark-wrap">
        <button type="button" id={`candidate-${c.id}`} data-candidate-id={c.id}
          className={`marker rv-mark risk-${c.risk}`} aria-pressed={selection.has(c.id)}
          aria-label={`${c.labelName} · ${riskName(c)} · ${locationOf(draft,c)} · ${c.text}`}
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
        <span className="rv-row-change">{mode==='keep'?<span>{c.text}</span>:<s>{c.text}</s>}<span aria-hidden="true">→</span><strong>{replacement(c,choices[c.id])}</strong></span>
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
  return <fieldset className="privacy-review" disabled={disabled} aria-label="개인정보 검토와 수정">
    {tip&&<div className="rv-tooltip" role="tooltip" style={{left:tip.left,top:tip.top}}>{tip.text}</div>}
    <div className="page-heading"><div><span className="eyebrow">검사 결과</span><h1>게시 전 개인정보 검토</h1><p>본문을 읽고, 표시된 항목을 직접 선택해 수정하세요.</p></div><div className="rv-continue"><button className="secondary" onClick={onWrite}>수정한 글로 이어쓰기</button><span>적용한 가림·수정을 가져갑니다.</span></div></div>
    <p className="review-notice result-notice">자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다. 게시 전, 표시되지 않은 부분까지 직접 한 번 더 확인해 주세요.</p>
    <section className="dashboard rv-dashboard" aria-label="개인정보 후보 대시보드">
      <div className="rv-dash-head"><h2>검출된 개인정보</h2><span>위험도는 처리 전 검출 기준 · 같은 값도 위치별 집계</span></div>
      <div className="rv-metrics"><div className="rv-metric"><span>전체 검출</span><div className="total"><strong>{candidates.length.toLocaleString()}</strong><span>곳</span></div></div>
        {RISKS.map(r=><div className="rv-metric" key={r.key}><span className={`rv-risk risk-${r.key}`}><i/>{r.name}</span><strong>{counts[r.key]}<small>곳</small></strong></div>)}</div>
      {candidates.length===0&&<div className="empty-results"><strong>탐지된 후보가 없습니다</strong><p>표시되지 않은 부분도 직접 한 번 더 확인해 주세요.</p></div>}
    </section>
    <article className="post rv-post" aria-label="전체 본문 미리보기">
      <div className="rv-document-head"><h2>전체 본문 미리보기</h2><div className="rv-view" role="group" aria-label="본문 표시 방식">
        <button aria-pressed={display==='original'} onClick={()=>setDisplay('original')}>원문</button>
        <button aria-pressed={display==='result'} onClick={()=>setDisplay('result')}>처리 결과</button>
      </div></div>
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
      <div className="post-inner"><h2>{draft.title?marked(draft.title,'title'):'제목 없음'}</h2>
        <div className="post-body">{marked(draft.body,'body')}</div></div>
      <div className="rv-legend">{RISKS.map(r=><span className={`rv-risk risk-${r.key}`} key={r.key}><i/>{r.name}</span>)}<span>마우스를 올리거나 키보드로 이동하면 유형을 확인할 수 있어요.</span></div>
    </article>
    <section className="rv-editor" ref={editor} aria-label="선택한 개인정보 편집">
      {!selected.length?<p className="rv-list-empty">본문에서 색칠된 항목을 선택해 주세요.</p>:<>
        <div className="rv-editor-meta"><span>{single?<>{single.labelName} · {locationOf(draft,single)} {badge(single)}</>:`${selected.length}곳 선택 · 선택한 항목에 함께 적용`}</span><span>{customOpen?'직접 수정 작성 중':common?MODE_NAMES[common]:single?'미설정':'미설정 또는 여러 처리 방식'}</span></div>
        <div className="rv-original">{single?single.text:selected.slice(0,3).map(c=>c.text).join(' · ')+(selected.length>3?` 외 ${selected.length-3}곳`:'')}</div>
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
        <div className="rv-editor-bottom"><div>미리보기 <span aria-hidden="true">→</span> <strong>{single?preview:`${selected.length}곳에 선택한 방식 적용`}</strong></div><button onClick={undo} disabled={!history.length}>↶ 되돌리기</button></div>
        <p className="rv-help">{single?'이 항목만 개별적으로 수정합니다.':'직접 수정은 항목을 하나만 선택했을 때 사용할 수 있어요.'}</p>
      </>}
    </section>
    <div className="rv-list-toolbar"><span role="status" aria-live="polite">{message||'항목 오른쪽에서 가림 방식을 변경하거나 취소하세요.'}</span><button ref={undoButton} onClick={undo} disabled={!history.length}>↶ 되돌리기</button></div>
    <div className="rv-lists">{listPanel('partial')}{listPanel('full')}</div>
    <details className="rv-other" open={otherOpen} onToggle={e=>setOtherOpen(e.currentTarget.open)}>
      <summary>그 외 처리 · 가리지 않음 {others.filter(c=>choices[c.id].mode==='keep').length}곳 · 직접 수정 {others.filter(c=>choices[c.id].mode==='custom').length}곳</summary>
      {otherOpen&&(others.length?<ol>{others.map(listRow)}</ol>:<p className="rv-list-empty">원문 유지 또는 직접 수정한 항목이 여기에 표시돼요.</p>)}
    </details>
    <div className="rv-finish"><p><strong>{appliedCount}곳에 가림·수정 반영</strong><span>저장하면 처리 결과의 제목·본문이 저장돼요. 다시 불러오면 재검사합니다.</span></p><button className="secondary" onClick={onWrite}>수정한 글로 이어쓰기 →</button></div>
    <p className="rv-engine">{result.engine} · {(result.elapsedMs/1000).toFixed(1)}초 · 처리 결과 {Array.from(processed.title).length+Array.from(processed.body).length}자</p>
  </fieldset>;
}
