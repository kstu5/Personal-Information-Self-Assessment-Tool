import {boot} from './api';
import {RISKS} from './masking';
import type {Risk} from './types';

export type ManualType={label:string;labelName:string;risk:Risk};
export type ManualAlias={label:string;text:string;alias:string};
export type ManualClassification=ManualType&{autoMask:import('./types').Candidate['autoMask'];aliases?:ManualAlias[]};
export const DEFAULT_MANUAL_TYPE:ManualClassification={label:'USER_DEFINED',labelName:'사용자 추가',risk:'INFO',autoMask:{choice:{mode:'full'},rule:'사용자가 추가한 범위 전체 가림'}};

export function ManualTypeSelect({value,onChange,disabled=false,caption='추가할 정보 유형'}:{value:string;onChange:(label:string)=>void;disabled?:boolean;caption?:string}){
  const types=boot.manualTypes||[DEFAULT_MANUAL_TYPE],selected=types.find(t=>t.label===value);
  return <label className="manual-type-select"><span>{caption}</span><select aria-label={caption} value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}>{types.map(t=><option key={t.label} value={t.label}>{t.label==='USER_DEFINED'?'기타 · 유형 미지정':t.labelName}</option>)}</select><small>{value==='USER_DEFINED'?'유형 미지정 항목은 참고에 표시합니다.':`사용자 지정 · 기본 위험도 ${RISKS.find(r=>r.key===selected?.risk)?.name||'참고'}`}</small></label>;
}
