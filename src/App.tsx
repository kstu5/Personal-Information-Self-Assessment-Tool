import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api, boot } from './api';
import { cancelled, filenameFromTitle, openDocument, saveDocument } from './files';
import type { CheckResult, Draft, SavedFile } from './types';
import { PrivacyReview } from './PrivacyReview';
import { maskedDraft, validateCandidates } from './masking';
import type { MaskChoices } from './masking';
import { FileReview } from './FileReview';

const NOTICE = '자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다. 게시 전, 표시되지 않은 부분까지 직접 한 번 더 확인해 주세요.';
const EMPTY: Draft = {title:'',body:''};
const EXAMPLE: Draft = {
  title:'10월 독서 모임: 함께 읽을 분을 찾습니다?',
  body:'안녕하세요. 동네에서 작은 독서 모임을 준비하고 있는 김하늘입니다. 책을 좋아하는 분들과 편하게 이야기 나누고 싶어 글을 올려요.\n\n토요일 오후 2시에 만나요. 모임 장소는 서울특별시 마포구 예시로 12, 302호입니다. 처음 오시는 분도 환영합니다!\n\n참여를 원하시면 김하늘에게 010-0000-0000 또는 haneul@example.com으로 연락해 주세요. 저는 29세이고, 출판사에서 편집자로 일하고 있어요.\n\n함께 준비하는 박서윤의 연락처는 010-0000-0001입니다. 장소 관련 문의는 seoyun@example.com으로 보내 주세요.\n\n아래는 신청서에 적어 두었던 제 정보예요.\n주민등록번호: 990101-1000000\n주소: 서울특별시 마포구 예시로 12, 302호\n\n서로 좋아하는 책 한 권씩 가져오면 좋겠습니다. 부담 없이 함께해 주세요!',
};
type Intent = 'new'|'open'|'close'|'example';
type IconName = 'scan'|'file'|'folder'|'save'|'plus'|'arrow'|'back'|'check'|'info'|'close'|'download';
function Icon({name,size=18}: {name:IconName;size?:number}) {
  const shapes:Record<IconName,ReactNode> = {
    scan:<><path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3M7 8h10M7 12h10M7 16h6"/></>,
    file:<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
    folder:<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7h18"/>,
    save:<><path d="m19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2ZM7 3v6h9V3M7 21v-8h10v8"/></>,
    plus:<path d="M12 5v14M5 12h14"/>,arrow:<path d="M5 12h14m-6-6 6 6-6 6"/>,back:<path d="M19 12H5m6-6-6 6 6 6"/>,check:<path d="m5 12 4 4L19 6"/>,
    info:<><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.2"/></>,close:<path d="m6 6 12 12M6 18 18 6"/>,download:<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}
function Modal({title,children,onCancel}: {title:string;children:ReactNode;onCancel:()=>void}) {
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const dialog=ref.current!;dialog.showModal();return()=>dialog.close();},[]);
  return <dialog ref={ref} onCancel={e=>{e.preventDefault();onCancel();}} aria-labelledby="dialog-title">
    <div className="modal-head"><div><span className="eyebrow">작업 파일</span><h2 id="dialog-title">{title}</h2></div><button aria-label="창 닫기" className="icon-button" onClick={onCancel}><Icon name="close"/></button></div>{children}
  </dialog>;
}
export function App() {
  const [mode,setMode]=useState<'home'|'post'|'files'>('home');
  const [fileWork,setFileWork]=useState(false);
  const [fileClose,setFileClose]=useState(false);
  const [draft,setDraft]=useState<Draft>(EMPTY);
  const [savedText,setSavedText]=useState(JSON.stringify(EMPTY));
  const [file,setFile]=useState<SavedFile|null>(null);
  const [started,setStarted]=useState(false);
  const [view,setView]=useState<'write'|'results'>('write');
  const [result,setResult]=useState<CheckResult|null>(null);
  const [choices,setChoices]=useState<MaskChoices>({});
  const [checking,setChecking]=useState(false);
  const [io,setIO]=useState(false);
  const ioRef=useRef(false);
  const revision=useRef(0);
  const draftRef=useRef(draft);
  const [notice,setNotice]=useState('');
  const [error,setError]=useState('');
  const [pending,setPending]=useState<Intent|null>(null);
  const afterSave=useRef<Intent|null>(null);
  const [saveDialog,setSaveDialog]=useState(false);
  const [suggestion,setSuggestion]=useState('');
  const currentDraft=useMemo(()=>result?maskedDraft(draft,result.candidates,choices):draft,[draft,result,choices]);
  draftRef.current=currentDraft;
  const dirty=JSON.stringify(currentDraft)!==savedText;
  const titleCount=Array.from(currentDraft.title).length,bodyCount=Array.from(currentDraft.body).length;
  const valid=titleCount<=boot.maxTitle && bodyCount<=boot.maxBody;
  const busy=io || checking;
  const fail=(e:unknown)=>setError(e instanceof Error?e.message:'작업을 완료하지 못했습니다. 다시 시도해 주세요.');
  function working(value:boolean){ioRef.current=value;setIO(value);}
  function update(next:Draft){draftRef.current=next;setDraft(next);revision.current++;if(result)setNotice('글이 변경되었습니다. 현재 내용을 다시 검사해 주세요.');setResult(null);setChoices({});setView('write');}
  function resumeWriting(){
    if(ioRef.current)return;
    if(JSON.stringify(currentDraft)!==JSON.stringify(draft)){
      update(currentDraft);setNotice('가림·수정이 반영된 글입니다. 내용을 더 수정한 뒤 다시 검사할 수 있어요.');
    }else setView('write');
  }
  function replace(next:Draft,nextFile:SavedFile|null,isSaved:boolean){update(next);setSavedText(JSON.stringify(isSaved?next:EMPTY));setFile(nextFile);setStarted(true);setError('');}
  async function perform(intent:Intent){
    if(intent==='close'){if(boot.desktop)await api('window/close',{});return;}
    if(intent==='new'){replace(EMPTY,null,true);setNotice('새 글을 작성해 주세요.');return;}
    if(intent==='example'){replace(EXAMPLE,null,false);setNotice('가상의 예시 글입니다. 검사를 눌러 실제 탐지 결과를 확인해 보세요.');return;}
    working(true);setError('');
    try { const opened=await openDocument();if(opened){replace(opened.draft,opened.file,true);setNotice('저장한 글을 불러왔어요. 내용을 확인한 뒤 다시 검사해 주세요.');} }
    catch(e){if(!cancelled(e))fail(e);}
    finally{working(false);}
  }
  function request(intent:Intent){
    if(ioRef.current || checking){setNotice('진행 중인 작업이 끝난 뒤 다시 시도해 주세요.');return;}
    if(dirty)setPending(intent);else void perform(intent);
  }
  function cancelSave(){if(ioRef.current)return;setSaveDialog(false);afterSave.current=null;}
  async function commit(asNew:boolean){
    if(ioRef.current)return;
    working(true);setError('');const snapshot={...draftRef.current};
    try {
      const saved=await saveDocument(snapshot,file,asNew,suggestion || filenameFromTitle(snapshot.title));
      if(saved){
        setFile(saved);setSavedText(JSON.stringify(snapshot));setSaveDialog(false);setNotice('선택한 위치에 저장했어요. 다음 실행에서 이 파일을 불러오세요.');
        const next=afterSave.current;afterSave.current=null;
        working(false);if(next)await perform(next);
      }else if(!asNew){afterSave.current=null;}
    }catch(e){if(!cancelled(e)){setSaveDialog(false);afterSave.current=null;fail(e);}else if(!asNew){afterSave.current=null;}}
    finally{working(false);}
  }
  function beginSave(asNew=false){
    if(ioRef.current || !started)return;
    if(!valid){setError('제목은 300자, 본문은 30,000자까지 저장할 수 있습니다.');afterSave.current=null;return;}
    if(file && !asNew)void commit(false);
    else {setSuggestion(filenameFromTitle(currentDraft.title));setSaveDialog(true);}
  }
  async function check(){
    if(checking || ioRef.current || !valid)return;
    const current=revision.current;const snapshot={...draftRef.current};
    setChecking(true);setResult(null);setChoices({});setError('');setNotice('');
    // Allow the first model load (60s), inference (20s), and worker cleanup.
    const controller=new AbortController();const timer=window.setTimeout(()=>controller.abort(),90000);
    try {
      const next=await api<CheckResult>('check',{...snapshot,revision:current},controller.signal);
      if(revision.current!==current){setNotice('검사 중 글이 변경되었습니다. 현재 내용을 다시 검사해 주세요.');return;}
      if(next.revision!==current)throw new Error('검사 결과와 원문이 일치하지 않습니다. 다시 검사해 주세요.');
      validateCandidates(snapshot,next.candidates);
      setResult(next);setView('results');setNotice('');window.scrollTo({top:0});
    }catch(e){if(revision.current===current){setError(cancelled(e)?'검사 시간이 초과되었습니다. 잠시 후 다시 검사해 주세요.':e instanceof Error?e.message:'검사에 실패했습니다.');}}
    finally{clearTimeout(timer);setChecking(false);}
  }
  useEffect(()=>{
    const before=(e:BeforeUnloadEvent)=>{if(dirty && !boot.desktop){e.preventDefault();e.returnValue='';}};
    const keys=(e:KeyboardEvent)=>{if(mode==='post'&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();if(!saveDialog&&!pending)beginSave(e.shiftKey);}};
    window.addEventListener('beforeunload',before);window.addEventListener('keydown',keys);window.requestAppClose=()=>fileWork?setFileClose(true):request('close');
    return()=>{window.removeEventListener('beforeunload',before);window.removeEventListener('keydown',keys);delete window.requestAppClose;};
  });
  const savedTime=file ? new Date(file.savedAt).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}) : '';

  return <div className="app">
    <header className="topbar"><a className="brand" href="#" onClick={e=>{e.preventDefault();setMode('home');}}><span className="brand-icon"><Icon name="scan" size={23}/></span><span><strong>게시 전</strong><small>게시글과 파일, 한 번 더 살펴보기</small></span></a><nav className="mode-nav" aria-label="검사 종류"><button aria-current={mode==='post'?'page':undefined} onClick={()=>setMode('post')}>게시글 검사</button><button aria-current={mode==='files'?'page':undefined} onClick={()=>setMode('files')}>파일 검사</button></nav><span className="local-badge"><span/>내 PC에서 검사</span></header>
    {mode==='home'&&<main><section className="entry-home"><span className="eyebrow">공유하기 전에, 나와 다른 사람의 정보를 지켜요.</span><h1>무엇을 검사할까요?</h1><p>게시글도, 첨부할 문서도.<br/>내 컴퓨터에서 살펴보고 필요한 부분만 가려 보세요.</p><div className="entry-options"><button onClick={()=>setMode('post')}><Icon name="file" size={30}/><span className="eyebrow">POST REVIEW</span><strong>게시글 검사</strong><p>글을 작성하거나 붙여 넣고<br/>개인정보를 확인하세요.</p><span>작성한 글 이어서 보기 <Icon name="arrow"/></span></button><button onClick={()=>setMode('files')}><Icon name="folder" size={30}/><span className="eyebrow">FILE REVIEW</span><strong>파일 검사</strong><p>문서와 이미지를 확인하고<br/>가림을 적용한 사본을 만드세요.</p><span>파일 선택하고 검토하기 <Icon name="arrow"/></span></button></div><div className="entry-note"><span>문서를 외부 AI 서비스로 보내지 않습니다.</span><span>파일 검사는 원본을 보존하고 새 사본으로 제공합니다.</span></div></section></main>}
    <main hidden={mode!=='post'}>
      <nav className="steps" aria-label="작업 단계"><button disabled={io} aria-current={view==='write'?'step':undefined} onClick={resumeWriting}><b>1</b>게시글 작성</button><span className="step-line"/><button disabled={!result||io} aria-current={view==='results'?'step':undefined} onClick={()=>setView('results')}><b>2</b>검사 결과</button></nav>
      {started && <section className="filebar" aria-label="파일 도구 모음"><div className="file-status"><Icon name="file"/><div><strong title={file?.name}>{file?.name || '아직 저장하지 않은 글'}</strong><small className={dirty?'unsaved':''}>{io?'파일 작업 중…':dirty?'저장하지 않은 변경사항':file?`마지막 저장 ${savedTime}`:'새 글'}</small></div></div><div className="file-actions"><button disabled={busy} onClick={()=>request('new')}><Icon name="plus"/>새 글</button><button disabled={busy} onClick={()=>request('open')}><Icon name="folder"/>불러오기</button><button disabled={busy} className="save-button" onClick={()=>beginSave()}><Icon name="save"/>저장</button><details className="file-menu"><summary aria-label="파일 메뉴">•••</summary><div><button disabled={busy} onClick={e=>{e.currentTarget.closest('details')?.removeAttribute('open');beginSave(true);}}>다른 이름으로 저장</button>{boot.desktop&&<button disabled={busy} onClick={()=>request('close')}>프로그램 종료</button>}</div></details></div></section>}
      {notice&&<div className="notice" role="status"><Icon name="check"/><span>{notice}</span><button aria-label="안내 닫기" onClick={()=>setNotice('')}><Icon name="close" size={15}/></button></div>}
      {checking&&<div className="notice" role="status"><Icon name="info"/><span>내 PC에서 검사하고 있어요. 프로그램을 켠 뒤 첫 검사는 준비에 시간이 조금 더 걸릴 수 있어요.</span></div>}
      {error&&<div className="error" role="alert"><Icon name="info"/><div><strong>{error}</strong><p>현재 작성 중인 글은 그대로 유지됩니다.</p></div><button aria-label="오류 안내 닫기" onClick={()=>setError('')}><Icon name="close" size={16}/></button></div>}
      {!started ? <section className="welcome"><span className="welcome-symbol"><Icon name="scan" size={34}/></span><span className="eyebrow">게시 전 개인정보 검토</span><h1>올리기 전,<br/>한 번 살펴볼까요?</h1><p>게시글 속 개인정보 후보를 찾아<br/>어느 부분을 확인하면 좋을지 알려드려요.</p><div className="start-options"><button onClick={()=>request('new')}><Icon name="plus" size={25}/><strong>새 글 작성</strong><span>내용을 쓰거나 붙여넣기</span><Icon name="arrow"/></button><button disabled={io} onClick={()=>request('open')}><Icon name="folder" size={25}/><strong>저장한 글 불러오기</strong><span>작업 파일에서 이어서 작성</span><Icon name="arrow"/></button></div><button className="text-button" onClick={()=>request('example')}>가상 예시 글로 살펴보기 <Icon name="arrow" size={15}/></button><p className="welcome-note">저장할 때 파일 이름과 위치를 직접 선택할 수 있어요.</p></section>
      : view==='write' ? <>
        <div className="page-heading"><div><span className="eyebrow">게시글 작성</span><h1>올리기 전, 한 번 확인해요.</h1><p>게시글을 그대로 붙여 넣거나 작성해 주세요.</p></div><button className="text-button" disabled={busy} onClick={()=>request('example')}>예시 글</button></div>
        <section className="editor" aria-label="게시글 입력"><div className="card-top"><span><Icon name="file"/>내 게시글</span><span className="muted">텍스트 검사</span></div><div className="editor-inner"><label htmlFor="post-title">제목 <span>{titleCount.toLocaleString()} / 300</span></label><input id="post-title" value={draft.title} disabled={io} onChange={e=>update({...draft, title:e.target.value})} placeholder="게시글 제목을 입력해 주세요" autoComplete="off" spellCheck={false}/><div className="editor-divider"/><label htmlFor="post-body">본문 <span>{bodyCount.toLocaleString()} / 30,000</span></label><textarea id="post-body" value={draft.body} disabled={io} onChange={e=>update({...draft,body:e.target.value})} placeholder={'어떤 이야기를 올리시나요?\n게시할 글을 여기에 작성하거나 붙여넣어 주세요.'} spellCheck={false}/></div><div className="editor-bottom"><span>제목과 본문을 함께 검사합니다.</span><span>{(titleCount+bodyCount).toLocaleString()}자</span></div></section>
        {!valid&&<p className="limit-error" role="alert">제목은 300자, 본문은 30,000자까지 사용할 수 있어요. 내용을 줄여 주세요.</p>}
        <div className="write-footer"><p className="review-notice"><Icon name="info"/><span>{NOTICE}</span></p><button className="primary inspect" disabled={busy||!valid||!(draft.title.trim()||draft.body.trim())} onClick={()=>void check()}>{checking?<span className="spinner"/>:<Icon name="scan"/>}{checking?'검사 중…':'개인정보 검사'}{!checking&&<Icon name="arrow"/>}</button></div>
      </> : null}
      {started&&result&&<div hidden={view!=='results'}><PrivacyReview draft={draft} result={result} choices={choices} disabled={io} onChange={setChoices} onWrite={resumeWriting}/></div>}
      <footer className="app-footer"><span>게시 전 <b>·</b> 개인정보 검토 도구</span><span>직접 저장한 글만 파일로 보관합니다.</span></footer>
    </main>
    <FileReview active={mode==='files'} onWorkChange={setFileWork}/>
    {fileClose&&<Modal title="파일 검토를 마치고 종료할까요?" onCancel={()=>setFileClose(false)}><p className="modal-copy">진행 중인 파일 검사와 저장하지 않은 가림 선택을 종료하고 임시 사본을 정리합니다. 원본과 이미 저장한 사본은 유지됩니다.</p><div className="modal-actions"><button className="secondary" onClick={()=>setFileClose(false)}>계속 검토</button><button className="primary" onClick={()=>{setFileClose(false);request('close');}}>종료 계속</button></div></Modal>}
    {saveDialog&&<Modal title="글 저장하기" onCancel={cancelSave}><p className="modal-copy">제목을 바탕으로 파일명을 추천해요.<br/>다음 창에서 저장 위치를 직접 선택하세요.</p><label htmlFor="filename">파일명</label><div className="filename"><input id="filename" value={suggestion} disabled={io} onChange={e=>setSuggestion(e.target.value)} autoComplete="off"/><span>.piipost</span></div><p className="field-note">{filenameFromTitle(currentDraft.title)!==currentDraft.title?'파일명에 쓸 수 없는 문자와 길이를 정리했어요. ':''}현재 글 제목은 그대로 유지됩니다.</p><div className="filename-preview">저장할 파일 · {filenameFromTitle(suggestion)}.piipost</div><p className="field-note">적용한 가림·수정을 포함한 제목과 본문이 저장돼요. 불러온 뒤 다시 검사해 주세요.</p><div className="modal-actions"><button disabled={io} className="secondary" onClick={cancelSave}>취소</button><button disabled={io} className="primary" onClick={()=>void commit(true)}>{io?'저장 중…':'위치 선택하고 저장'}<Icon name="folder"/></button></div></Modal>}
    {pending&&<Modal title="작성 중인 글을 저장할까요?" onCancel={()=>setPending(null)}><p className="modal-copy">저장하지 않은 변경사항이 있어요.<br/>이어서 진행하기 전에 저장할 수 있습니다.</p><div className="modal-actions guard-actions"><button className="secondary" onClick={()=>setPending(null)}>취소</button><button className="secondary" onClick={()=>{const action=pending;setPending(null);void perform(action);}}>저장하지 않고 계속</button><button className="primary" onClick={()=>{afterSave.current=pending;setPending(null);beginSave();}}>저장하고 계속</button></div></Modal>}
  </div>;
}
