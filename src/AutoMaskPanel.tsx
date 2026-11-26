import {useId,useState} from 'react';
import type {FileCandidate,FileSelection} from './documentTypes';
import {applyAutoMask,autoChoicesToUndo,autoMaskPlan,undoAutoMask} from './autoMasking';

export function AutoMaskPanel({candidates,selection,locked,onChange,onNotice,scope='file'}:{candidates:FileCandidate[];selection:FileSelection;locked:boolean;onChange:(p:Partial<FileSelection>)=>void|boolean;onNotice:(text:string)=>void;scope?:'file'|'post'}){
  const [open,setOpen]=useState(false);
  const optionsId=useId();
  const plan=autoMaskPlan(candidates,selection),undoable=autoChoicesToUndo(selection);
  return <section className="auto-mask" aria-label="개인정보 자동 가림">
    <div className="file-bulk-actions"><button className="primary" disabled={locked} aria-expanded={open} aria-controls={optionsId} onClick={()=>setOpen(v=>!v)}>개인정보 자동 가림</button>
      {undoable.length>0&&<button className="secondary" disabled={locked} onClick={()=>{if(onChange(undoAutoMask(selection))===false)return;onNotice('자동 가림 직전 상태로 되돌렸습니다. 이후 개별 변경한 항목은 유지했습니다.');}}>자동 가림 되돌리기</button>}</div>
    {open&&<div id={optionsId} className="auto-mask-options">
      <strong>일부 정보 확인용</strong><p>이름·연락처 일부, 출생연도·연령대, 주소의 시·군·구를 남깁니다. 여권·운전면허번호와 인증정보는 전체를 가립니다. 남은 정보로 개인을 알아볼 수 있어 익명화를 보장하지 않습니다.</p>
      <p>적용 예정 <b>{plan.count}곳</b> · 기존 지정 유지 {plan.preserved}곳 · 직접 확인 필요 {plan.review}곳 · 영역 겹침 {plan.overlaps}곳</p>
      <div className="auto-mask-table"><table><thead><tr><th>유형</th><th>자동 가림 기준</th><th>위치 수</th><th>처리</th></tr></thead><tbody>{plan.rows.map((row,i)=><tr key={i}><td>{row.label}</td><td>{row.rule}</td><td>{row.count}</td><td>{row.status}</td></tr>)}</tbody></table></div>
      <p>검색·위험도 필터와 관계없이 {scope==='post'?'현재 게시글의 제목·본문':'현재 파일'}에만 적용합니다. 사용자가 지정한 처리·직접 수정·제외는 유지합니다. 초기 자동 기본값은 위 기준으로 바꿉니다.{scope==='file'&&' PDF·내장 이미지에서 문구 교체가 필요한 항목은 전체 영역 가림으로 처리합니다.'}</p>
      <p>대체 표시는 같은 값끼리만 연결하며 동일 인물임을 판정하지 않습니다.{scope==='file'&&' 이미지 문구 교체는 글꼴·공간에 따라 경고가 발생할 수 있습니다.'}</p>
      <button className="primary" disabled={locked||!plan.count} onClick={()=>{if(onChange(applyAutoMask(selection,plan.choices))===false)return;setOpen(false);onNotice(`일부 정보 확인용 자동 가림을 ${plan.count}곳에 지정했습니다. 직접 확인 ${plan.review+plan.overlaps}곳과 ${scope==='post'?'원문·처리 결과':'원본·적용 미리보기'}를 확인하세요. ${scope==='post'?'게시글은':'사본은'} 아직 저장하지 않았습니다.`);}}>기준대로 {plan.count}곳 적용</button>
    </div>}
  </section>;
}
