type Props={page:number;labels:string[];onChange:(page:number)=>void;noun?:'페이지'|'이미지'};

export function PageNavigation({page,labels,onChange,noun='페이지'}:Props){
  if(!labels.length)return null;
  const current=Math.max(0,Math.min(page,labels.length-1));
  return <nav className="office-page-navigation" aria-label={`${noun==='페이지'?'문서 페이지':'이미지'} 이동`}>
    <button type="button" className="secondary" aria-label={`이전 ${noun}`} disabled={current===0} onClick={()=>onChange(current-1)}>‹ 이전</button>
    <span className="office-page-position" role="status" aria-live="polite" aria-atomic="true">{current+1} / {labels.length}{noun==='페이지'?'쪽':'개'}</span>
    <button type="button" className="secondary" aria-label={`다음 ${noun}`} disabled={current===labels.length-1} onClick={()=>onChange(current+1)}>다음 ›</button>
    <label>바로 이동<select aria-label={noun==='페이지'?'문서 페이지':'확인할 이미지'} value={current} onChange={e=>onChange(Number(e.target.value))}>{labels.map((label,index)=><option key={index} value={index}>{label}</option>)}</select></label>
  </nav>;
}
