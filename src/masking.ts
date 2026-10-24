import type { Candidate, Draft, Risk } from './types';

export const RISKS: {key:Risk; name:string}[] = [
  {key:'CRITICAL',name:'심각'}, {key:'HIGH',name:'높음'}, {key:'MEDIUM',name:'보통'},
  {key:'LOW',name:'낮음'}, {key:'INFO',name:'참고'},
];
export type MaskMode = 'partial'|'full'|'keep'|'custom';
export type MaskChoice = {mode:'partial'} | {mode:'full'} | {mode:'keep'} | {mode:'custom'; text:string};
export type MaskChoices = Record<string, MaskChoice>;
export const MODE_NAMES: Record<MaskMode,string> = {
  partial:'부분 가림', full:'전체 가림', keep:'가리지 않음', custom:'직접 수정',
};
const segments = new Intl.Segmenter('ko', {granularity:'grapheme'});
const chars = (s:string) => Array.from(segments.segment(s), x=>x.segment);

/** Every partial mask hides at least one character; full masking has a fixed length. */
export function partialMask(candidate: Pick<Candidate,'text'|'label'>): string {
  const {text,label}=candidate;
  const digitCount=(text.match(/\d/g)||[]).length;
  function digits(keepStart:number,keepEnd:number) {
    let i=0;
    return text.replace(/\d/g, d=>{const n=i++;return n<keepStart||n>=digitCount-keepEnd?d:'*';});
  }
  if (['PHONE','FAX'].includes(label) && digitCount>=8) {
    const prefix=text.startsWith('+82')?2:text.startsWith('02')?2:digitCount>=10?3:0;
    return digits(prefix,4);
  }
  if (['RRN','FRN'].includes(label) && digitCount===13) return digits(6,0);
  if (['CARD','ACCOUNT'].includes(label) && digitCount>4) return digits(0,4);
  if (label==='EMAIL' && text.includes('@')) {
    const at=text.lastIndexOf('@'),local=chars(text.slice(0,at));
    return (local.length>1?local[0]+'*'.repeat(local.length-1):'*')+text.slice(at);
  }
  if (label==='ADDRESS') {
    const area=text.match(/^(.+?(?:시|군|구))\s+(.+)$/s);
    if (area) return area[1]+' ***';
  }
  if (['AGE','HEIGHT','WEIGHT','DT_BIRTH','POSTAL_CODE'].includes(label) && digitCount) return digits(0,0);
  const units=chars(text);
  return units.length>1?units[0]+'*'.repeat(units.length-1):'*';
}

export function replacement(candidate:Candidate, choice?:MaskChoice):string {
  if (!choice || choice.mode==='keep') return candidate.text;
  if (choice.mode==='full') return '█████';
  if (choice.mode==='partial') return partialMask(candidate);
  return choice.text;
}

/** Reject mismatched/overlapping offsets before any editing UI is opened. */
export function validateCandidates(draft:Draft, candidates:Candidate[]):void {
  const ids=new Set<string>();
  for (const source of ['title','body'] as const) {
    let end=0;
    for (const c of candidates.filter(c=>c.source===source).sort((a,b)=>a.start-b.start)) {
      if (ids.has(c.id) || !Number.isInteger(c.start) || !Number.isInteger(c.end) ||
          c.start<end || c.start>=c.end || c.end>draft[source].length ||
          draft[source].slice(c.start,c.end)!==c.text || !RISKS.some(r=>r.key===c.risk)) {
        throw new Error('검출 위치와 원문이 일치하지 않습니다. 다시 검사해 주세요.');
      }
      ids.add(c.id);end=c.end;
    }
  }
  if (ids.size!==candidates.length) throw new Error('검출 위치를 확인할 수 없습니다. 다시 검사해 주세요.');
}

export function maskedDraft(draft:Draft, candidates:Candidate[], choices:MaskChoices):Draft {
  const next={...draft};
  for (const source of ['title','body'] as const) {
    let end=0;const parts:string[]=[];
    for (const c of candidates.filter(c=>c.source===source).sort((a,b)=>a.start-b.start)) {
      parts.push(draft[source].slice(end,c.start),replacement(c,choices[c.id]));end=c.end;
    }
    parts.push(draft[source].slice(end));next[source]=parts.join('');
  }
  return next;
}

export function locationOf(draft:Draft, c:Candidate):string {
  return c.source==='title'?'제목':`본문 ${draft.body.slice(0,c.start).split(/\n[ \t]*\n+/).length}번 문단`;
}
