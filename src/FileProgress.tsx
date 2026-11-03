import {useState} from 'react';
import type {DocumentJob} from './documentTypes';
import './file-progress.css';

export function fileProgressStatus(job:Pick<DocumentJob,'state'|'progress'>){
  const exporting=job.state==='exporting';
  const step=exporting?(job.progress.includes('수정 사본 재검사')?2:1):job.state==='checking'?2:job.state==='reading'?1:0;
  const steps=exporting?['대기','수정 적용','재검사','완료']:['대기','내용 읽기','개인정보 검사','검토 준비'];
  const titles=exporting?['처리 순서를 기다리고 있어요','선택한 내용을 사본에 적용하고 있어요','수정 사본을 다시 검사하고 있어요']:['검사 순서를 기다리고 있어요','문서와 이미지를 읽고 있어요','개인정보 후보를 찾고 있어요'];
  const descriptions=exporting?['차례가 되면 새 사본을 만들기 시작합니다.','지정한 가림과 수정 내용을 새 파일에 반영하고 확인합니다.','사본에 남아 있는 개인정보 후보를 확인합니다.']:['앞선 파일의 처리가 끝나면 이 파일의 검사를 시작합니다.','본문과 지원하는 부가 정보, 이미지 속 글자를 함께 읽습니다.','이름과 번호, 주변 문맥을 함께 살펴봅니다.'];
  const batch=job.progress.match(/·\s*(\d+)\/(\d+)\s*구간/);
  const secondary=job.progress.includes('주변 문맥 2차 검토')||job.progress.includes('유형별 주변 문맥 검토');
  const credential=job.progress.includes('API 키·인증 토큰');
  return {exporting,step,steps,title:secondary?'주변 문맥을 한 번 더 검토하고 있어요':credential?'API 키·토큰·비밀번호를 찾고 있어요':titles[step],description:secondary?'검출된 후보를 문장·표 항목과 함께 유형별 기준으로 검토합니다.':credential?'알려진 키 형식과 인증정보 항목을 확인합니다.':descriptions[step],batch:step===2&&batch?`검사 구간 ${batch[1]} / ${batch[2]}`:null};
}

export function FileProgress({job,onCancel}:{job:DocumentJob;onCancel:()=>Promise<void>}){
  const [cancelling,setCancelling]=useState(false);
  const status=fileProgressStatus(job);
  async function cancel(){
    if(cancelling)return;
    setCancelling(true);
    try{await onCancel();}finally{setCancelling(false);}
  }
  return <section className="file-progress-card" aria-label={status.exporting?'수정 사본 처리 진행 상태':'파일 검사 진행 상태'}>
    <div className="file-progress-heading">
      <div className="file-progress-symbol" aria-hidden="true"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M7 3H4a1 1 0 0 0-1 1v3m14-4h3a1 1 0 0 1 1 1v3M3 17v3a1 1 0 0 0 1 1h3m10 0h3a1 1 0 0 0 1-1v-3M7 8h10M7 12h10M7 16h6"/></svg><span className="file-progress-spinner"/></div>
      <div className="file-progress-copy" role="status" aria-live="polite" aria-atomic="true"><span className="file-progress-caption">진행 단계 {status.step+1} / {status.steps.length}</span><h3>{cancelling?'작업을 취소하고 있어요':status.title}</h3><p>{cancelling?'처리를 멈추고 임시 사본을 정리합니다.':status.description}</p>{status.batch&&!cancelling&&<span className="file-progress-batch">{status.batch}</span>}</div>
    </div>
    <ol className="file-progress-steps" aria-label={status.exporting?'사본 처리 단계':'검사 단계'}>{status.steps.map((label,index)=>{
      const done=index<status.step,current=index===status.step;
      return <li key={label} className={done?'done':current?'current':''} aria-current={current?'step':undefined}><span className="file-progress-dot" aria-hidden="true">{done?'✓':index+1}</span><span>{label}</span><small>{done?'완료':current?cancelling?'취소 중':'진행 중':'대기'}</small></li>;
    })}</ol>
    <div className="file-progress-help"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 10v7m0-11v1"/></svg><span>문서가 길거나 이미지가 많으면 시간이 더 걸릴 수 있어요.</span></div>
    <footer className="file-progress-footer"><span><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/></svg>원본 파일은 변경하지 않습니다.</span><button type="button" className="secondary" disabled={cancelling} onClick={()=>void cancel()}>{cancelling?'취소 중…':'작업 취소'}</button></footer>
  </section>;
}
