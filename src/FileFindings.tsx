import { useEffect, useRef } from 'react';
import { MODE_NAMES, RISKS } from './masking';
import type { MaskChoice, MaskMode } from './masking';
import type { FileCandidate, FileSelection } from './documentTypes';
import './file-findings.css';
import {draftStatus} from './documentDraft';

const GUIDANCE: Record<string, string> = {
  CRITICAL: '가장 먼저 확인', HIGH: '우선 확인', MEDIUM: '공유 전 확인',
  LOW: '문맥에 따라 확인', INFO: '공개 범위 확인',
};

type Props = {
  candidates: FileCandidate[];
  selection: FileSelection;
  locked: boolean;
  onState: (patch: Partial<FileSelection>) => void;
  onSelect: (candidate: FileCandidate, editor?: boolean) => void;
  onApply: (mode: MaskMode, ids: string[]) => void;
  formatReplacement: (candidate: FileCandidate, choice?: MaskChoice) => string;
  overview?: 'only' | 'hidden';
  output?: boolean;
};

export function FileFindings({ candidates, selection: s, locked, onState, onSelect, onApply, formatReplacement,overview,output=false }: Props) {
  const search = s.search.trim().toLocaleLowerCase('ko');
  const filtered = candidates.filter(c => (s.filter === 'all' || c.risk === s.filter)
    && (!search || `${c.text} ${c.labelName} ${c.location}`.toLocaleLowerCase('ko').includes(search)));
  const groups = RISKS.map(r => ({ ...r, all: candidates.filter(c => c.risk === r.key), items: filtered.filter(c => c.risk === r.key) }));
  const selected = new Set(s.selected);
  const selectedHere = filtered.filter(c => selected.has(c.id)).length;
  const outside = s.selected.length - selectedHere;
  const allSelected = filtered.length > 0 && selectedHere === filtered.length;
  const selectAll = useRef<HTMLInputElement>(null);
  const applied = candidates.filter(c => s.choices[c.id] && s.choices[c.id].mode !== 'keep').length;
  const assigned = candidates.filter(c => draftStatus(c,s)!=='unset').length;
  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = selectedHere > 0 && !allSelected;
  }, [selectedHere, allSelected]);
  const reset = () => onState({ filter: 'all', search: '' });

  return <section className="file-findings" aria-label="위험도별 개인정보 검토">
    {overview!=='hidden'&&<div className="file-risk-overview">
      <div className="file-risk-overview-head">
        <div><strong>{candidates.length}</strong><span>{output?'개 사본의 남은 후보':'개 개인정보 후보'}</span></div>
        <p>{output?'수정 사본의 재검사 결과':<>처리 지정 <b>{assigned}/{candidates.length}개</b><span>가림·수정 {applied}개 · 영역 수정 {Object.keys(s.textEdits).length}곳 · 영역 가림 {s.regions.length}곳</span></>}</p>
      </div>
      <div className="file-risk-cards" role="group" aria-label="위험도별 목록 필터">
        {groups.map(r => <button key={r.key} className={`file-risk-card risk-${r.key} ${!r.all.length ? 'is-empty' : ''}`}
          aria-pressed={s.filter === r.key} aria-label={`${r.name} 위험도 ${r.all.length}개 보기`}
          onClick={() => onState({ filter: s.filter === r.key ? 'all' : r.key })}>
          <span className="file-risk-card-name"><i aria-hidden="true"/>{r.name}<span aria-hidden="true">{s.filter === r.key ? '✓' : '↗'}</span></span>
          <strong>{r.all.length}<small>개</small></strong><span className="file-risk-guidance">{GUIDANCE[r.key]}</span>
          <span className="file-risk-meter" aria-hidden="true"><span style={{ width: `${candidates.length ? r.all.length / candidates.length * 100 : 0}%` }}/></span>
        </button>)}
      </div>
    </div>}

    {overview!=='only'&&<section className="file-findings-panel" aria-labelledby="file-findings-title">
      <div className="file-findings-heading">
        <div><h3 id="file-findings-title">{output?'사본의 남은 후보':'검출 목록'} <span>{filtered.length}<small> / {candidates.length}개</small></span></h3><p>{output?'수정 사본에서 다시 찾은 후보입니다. 유지한 정보·부분 가림·오탐이 포함될 수 있어요.':'원본에서 찾은 후보를 위험도가 높은 순서로 보여줍니다. 항목을 누르면 원문 위치로 이동해요.'}</p></div>
        <label className="file-findings-search"><span className="sr-only">검출 목록 검색</span><input value={s.search} onChange={e => onState({ search: e.target.value })} placeholder="내용·유형·위치 검색"/></label>
      </div>
      <div className="file-findings-filter"><span>{s.filter === 'all' ? '전체 위험도' : `${RISKS.find(r => r.key === s.filter)?.name} 위험도`}{s.search.trim() ? ` · “${s.search.trim()}” 검색` : ''}</span><button onClick={reset} disabled={s.filter === 'all' && !s.search}>전체 목록 보기</button></div>
      {!output&&<div className="file-findings-bulk">
        <label><input ref={selectAll} type="checkbox" disabled={locked || !filtered.length} checked={allSelected} aria-checked={selectedHere > 0 && !allSelected ? 'mixed' : allSelected}
          onChange={e => onState({ selected: e.target.checked ? Array.from(new Set([...s.selected, ...filtered.map(c => c.id)])) : s.selected.filter(key => !filtered.some(c => c.id === key)) })}/>현재 목록 일괄 선택</label>
        <span>{s.selected.length}개 일괄 선택{outside > 0 && <small> · 목록 밖 {outside}개 포함</small>}</span>
        <div>{(['partial', 'full', 'keep'] as const).map(mode => <button key={mode} disabled={locked || !s.selected.length} onClick={() => onApply(mode, s.selected)}>{MODE_NAMES[mode]}</button>)}</div>
      </div>}
      <div className="file-findings-groups">
        {groups.filter(r => r.items.length).map(r => <details className={`file-findings-group risk-${r.key}`} key={`${r.key}:${s.filter}:${search}`} open>
          <summary><span className="file-findings-group-name"><i aria-hidden="true"/>{r.name}<b>{r.items.length}개</b><small>{GUIDANCE[r.key]}</small></span><span className="file-findings-pending">{output?'재검사 결과':`미설정 ${r.items.filter(c => !s.choices[c.id] && !(c.part in s.textEdits)).length}개`} <span aria-hidden="true">⌄</span></span></summary>
          <ol>{r.items.map(c => {
            const choice = s.choices[c.id], edited = c.part in s.textEdits;
            const changed = edited || !!choice && choice.mode !== 'keep';
            return <li className={`file-finding ${s.focus === c.id ? 'is-focused' : ''} ${!output&&(edited||choice)?choice?.mode==='keep'&&!edited?'is-kept':'is-assigned':''}`} key={c.id}>
              <input type="checkbox" aria-label={`${c.location} ${c.text} 선택`} disabled={locked} checked={selected.has(c.id)} onChange={e => onState({ selected: e.target.checked ? [...s.selected, c.id] : s.selected.filter(key => key !== c.id) })}/>
              <button className="file-finding-content" aria-label={`${c.labelName} ${c.text} 원문 위치 확인`} onClick={() => onSelect(c)}>
                <span className="file-finding-meta"><span className="file-finding-type">{c.labelName}</span><span className={`file-finding-status ${changed||choice ? 'has-choice' : ''}`}>{output?'재검출':edited ? '✓ 영역 직접 수정' : choice ? `✓ ${MODE_NAMES[choice.mode]} 지정` : '미설정'}</span></span>
                <strong>{c.text}</strong><span className="file-finding-location">{c.location}</span>
                {choice && choice.mode !== 'keep' && !edited && <span className="file-finding-result">변경 예정 <b>{c.asset&&!c.imageTextEditable ? '선택한 이미지 영역 가림' : formatReplacement(c, choice) || '(빈 내용)'}</b></span>}
              </button>
              <div className="file-finding-actions">{!output&&<select aria-label={`${c.text} 가림 방법`} disabled={locked || edited} value={choice?.mode || ''} onChange={e => onApply(e.target.value as MaskMode, [c.id])}>
                <option value="" disabled>처리 방법 선택</option>{(['keep', 'partial', 'full', 'custom'] as MaskMode[]).map(mode => <option key={mode} value={mode} disabled={!!c.asset && !c.imageTextEditable && mode === 'custom'}>{c.imageTextEditable&&mode==='full'?'비공개 표시':MODE_NAMES[mode]}</option>)}
              </select>}<button onClick={() => onSelect(c)}>{output?'사본 위치':'원문 위치'} <span aria-hidden="true">↗</span></button></div>
            </li>;
          })}</ol>
        </details>)}
        {!filtered.length && <div className="file-findings-empty"><strong>{candidates.length ? '조건에 맞는 후보가 없습니다' : '검출된 개인정보 후보가 없습니다'}</strong><p>{candidates.length ? '다른 위험도를 선택하거나 검색어를 바꿔 보세요.' : '미검토 영역과 이미지도 직접 확인해 주세요.'}</p>{candidates.length > 0 && <button className="secondary" onClick={reset}>전체 목록 보기</button>}</div>}
      </div>
    </section>}
  </section>;
}
