import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import type {DocumentJob,FileCandidate,FileSelection} from './documentTypes';

type Match={id:string;part:string;start:number;end:number;text:string;location:string;before:string;after:string;reason:string;readingMethod:string};
type Props={job:DocumentJob;selection:FileSelection;locked:boolean;onLocate:(c:FileCandidate)=>void;onAdd:(query:string,ids:string[])=>Promise<void>};

export function FileKeywordSearch({job,selection,locked,onLocate,onAdd}:Props){
  const [query,setQuery]=useState(''),[searched,setSearched]=useState<string|null>(null),[matches,setMatches]=useState<Match[]>([]);
  const [selected,setSelected]=useState<string[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const request=useRef<AbortController|null>(null),generation=useRef(0),allBox=useRef<HTMLInputElement>(null),adding=useRef(false);
  function reset(){request.current?.abort();generation.current++;setBusy(false);setSearched(null);setMatches([]);setSelected([]);setError('');}
  useEffect(()=>{reset();return()=>{generation.current++;request.current?.abort();};},[job.id,job.revision]);
  const available=matches.filter(m=>!m.reason&&!(m.part in selection.textEdits));
  const ids=new Set(available.map(m=>m.id)),chosen=selected.filter(id=>ids.has(id));
  const allSelected=available.length>0&&chosen.length===available.length;
  useEffect(()=>{if(allBox.current)allBox.current.indeterminate=chosen.length>0&&!allSelected;},[chosen.length,allSelected]);
  async function search(){
    reset();const ticket=generation.current,abort=new AbortController();request.current=abort;setBusy(true);
    try{
      const result=await api<{matches:Match[]}>('documents/search',{id:job.id,revision:job.revision,query},abort.signal);
      if(ticket===generation.current){setMatches(result.matches);setSearched(query);}
    }catch(e){if(ticket===generation.current&&!abort.signal.aborted)setError(e instanceof Error?e.message:'원문을 검색하지 못했습니다.');}
    finally{if(ticket===generation.current)setBusy(false);}
  }
  async function add(){
    if(adding.current||!chosen.length||searched===null)return;
    adding.current=true;setError('');
    try{await onAdd(searched,chosen);}
    catch(e){setError(e instanceof Error?e.message:'항목을 추가하지 못했습니다.');}
    finally{adding.current=false;}
  }
  function locate(m:Match){
    const part=job.manifest?.parts.find(p=>p.id===m.part);
    onLocate({id:m.id,part:m.part,start:m.start,end:m.end,text:m.text,location:m.location,source:'body',label:'USER_DEFINED',labelName:'검색 위치',risk:'INFO',asset:part?.asset});
  }
  return <details className="file-keyword-search">
    <summary>원문에서 누락 항목 검색·추가</summary>
    <p>파일에서 읽은 원문을 검색합니다. 정확히 일치하는 문구를 위치별로 선택해 검토 대상에 추가하세요. 추가만으로 가림이 적용되지는 않습니다.</p>
    <form onSubmit={e=>{e.preventDefault();if(!locked&&query.trim())void search();}}>
      <label htmlFor="file-source-query">원문 키워드</label>
      <input id="file-source-query" value={query} maxLength={2000} disabled={locked} onChange={e=>{reset();setQuery(e.target.value);}} placeholder="자동 탐지가 놓친 이름·문구 등"/>
      <button className="secondary" disabled={locked||busy||!query.trim()}>원문 검색</button>
    </form>
    <p className="file-footer-note">대소문자·띄어쓰기가 같은 문구를 검색합니다. 문단·셀 경계를 넘는 문구와 OCR가 읽지 못한 글자는 검색되지 않습니다. 이미지는 영역 지정으로 보완하세요.</p>
    {error&&<p role="alert">{error}</p>}{busy&&<p role="status">원문 검색 중…</p>}
    {searched!==null&&<>
      <div className="keyword-selection">
        <label><input ref={allBox} type="checkbox" checked={allSelected} disabled={locked||!available.length} onChange={e=>setSelected(e.target.checked?available.map(m=>m.id):[])}/>추가 가능한 검색 결과 전체 선택</label>
        <span role="status">검색 {matches.length}곳 · 추가 가능 {available.length}곳 · 선택 {chosen.length}곳</span>
        <button className="primary" disabled={locked||!chosen.length} onClick={()=>void add()}>선택한 {chosen.length}곳 추가</button>
      </div>
      <ol className="keyword-results">{matches.map(m=>{
        const reason=m.reason||(m.part in selection.textEdits?'영역 직접 수정 중입니다. 해당 수정을 취소한 뒤 추가하세요.':'');
        return <li key={m.id}><input type="checkbox" aria-label={`${m.location} 검색 결과 선택`} checked={chosen.includes(m.id)} disabled={locked||!!reason} onChange={e=>setSelected(e.target.checked?[...selected,m.id]:selected.filter(id=>id!==m.id))}/>
          <div><small>{m.location} · {m.readingMethod==='ocr'?'이미지에서 읽음':'원문 텍스트'} · 글자 위치 {m.start+1}</small><p>{m.before}<mark>{m.text}</mark>{m.after}</p>{reason&&<small>{reason}</small>}</div>
          <button className="secondary" onClick={()=>locate(m)}>위치 보기</button>
        </li>;
      })}</ol>
      {!matches.length&&<p>읽은 원문에 일치하는 문구가 없습니다. 이미지·페이지도 직접 확인하세요.</p>}
    </>}
  </details>;
}
