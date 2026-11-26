import type {Candidate,Draft} from './types';
import type {MaskChoices} from './masking';
import {locationOf,validateCandidates} from './masking.ts';

export const POST_STATUSES=[
  {key:'unset',name:'미설정'}, {key:'partial',name:'부분 가림'}, {key:'full',name:'전체 가림'},
  {key:'custom',name:'직접 수정'}, {key:'keep',name:'원문 유지'},
] as const;
export type PostStatus=typeof POST_STATUSES[number]['key'];
export type PostFilter={query:string;risk:Candidate['risk']|'all';status:PostStatus|'all'};
export const EMPTY_POST_FILTER:PostFilter={query:'',risk:'all',status:'all'};
export const postStatus=(candidate:Candidate,choices:MaskChoices):PostStatus=>choices[candidate.id]?.mode||'unset';
export function postStatusCounts(candidates:Candidate[],choices:MaskChoices) {
  const counts:Record<PostStatus,number>={unset:0,partial:0,full:0,custom:0,keep:0};
  for(const candidate of candidates)counts[postStatus(candidate,choices)]++;
  return counts;
}
export function filterPostCandidates(draft:Draft,candidates:Candidate[],choices:MaskChoices,filter:PostFilter) {
  const query=filter.query.trim().toLocaleLowerCase();
  return candidates.filter(c=>(filter.risk==='all'||c.risk===filter.risk)&&(filter.status==='all'||postStatus(c,choices)===filter.status)&&
    (!query||`${c.text} ${c.labelName} ${c.label} ${locationOf(draft,c)} ${c.addedByUser?'사용자 추가':''}`.toLocaleLowerCase().includes(query)));
}

export type PostRange={source:'title'|'body';start:number;end:number};
export type PostMatch=PostRange&{id:string;text:string;blocked:boolean};
const segmenter=new Intl.Segmenter('ko',{granularity:'grapheme'});
const overlaps=(a:PostRange,b:PostRange)=>a.source===b.source&&a.start<b.end&&b.start<a.end;
const boundaries=(text:string)=>new Set([0,text.length,...Array.from(segmenter.segment(text),s=>s.index)]);

/** Expand browser UTF-16 selections to whole visible characters. */
export function normalizePostRange(draft:Draft,range:PostRange):PostRange|null {
  if(!['title','body'].includes(range.source)||![range.start,range.end].every(Number.isInteger))return null;
  const text=draft[range.source],lo=Math.min(range.start,range.end),hi=Math.max(range.start,range.end);
  if(lo<0||hi>text.length||lo===hi)return null;
  let start=lo,end=hi;
  for(const s of segmenter.segment(text)){
    if(s.index<lo&&lo<s.index+s.segment.length)start=s.index;
    if(s.index<hi&&hi<s.index+s.segment.length)end=s.index+s.segment.length;
  }
  return text.slice(start,end).trim()?{source:range.source,start,end}:null;
}

export function postRangeConflict(range:PostRange,candidates:Candidate[],replaceId?:string):boolean {
  return candidates.some(c=>c.id!==replaceId&&overlaps(range,c));
}

export function searchPost(draft:Draft,candidates:Candidate[],query:string):PostMatch[] {
  if(!query.trim())return [];
  const found:PostMatch[]=[];
  for(const source of ['title','body'] as const){
    const text=draft[source],edges=boundaries(text),active=candidates.filter(c=>c.source===source).sort((a,b)=>a.start-b.start);let at=0,index=0;
    while((at=text.indexOf(query,at))!==-1){
      const start=at,end=at+query.length;at=end;
      if(!edges.has(start)||!edges.has(end))continue;
      while(index<active.length&&active[index].end<=start)index++;
      found.push({source,start,end,id:`${source}:${start}:${end}`,text:query,blocked:!!active[index]&&active[index].start<end});
    }
  }
  return found;
}

/** All additions are checked against the current source and committed together. */
export function addPostRanges(draft:Draft,candidates:Candidate[],choices:MaskChoices,ranges:PostRange[],replaceId?:string) {
  validateCandidates(draft,candidates);
  if(!ranges.length||replaceId&&(!candidates.some(c=>c.id===replaceId)||ranges.length!==1))throw new Error('변경할 원문 위치를 다시 선택해 주세요.');
  const remaining=candidates.filter(c=>c.id!==replaceId),added:Candidate[]=[],edges={title:boundaries(draft.title),body:boundaries(draft.body)};
  for(const range of ranges){
    if(!['title','body'].includes(range.source)||!Number.isInteger(range.start)||!Number.isInteger(range.end)||range.start>=range.end||!edges[range.source].has(range.start)||!edges[range.source].has(range.end)||!draft[range.source].slice(range.start,range.end).trim())throw new Error('글자 경계와 원문 위치를 다시 확인해 주세요.');
    added.push({source:range.source,start:range.start,end:range.end,id:`user:${crypto.randomUUID()}`,text:draft[range.source].slice(range.start,range.end),
      label:'USER_DEFINED',labelName:'사용자 추가',risk:'INFO',addedByUser:true,
      autoMask:{choice:{mode:'full'},rule:'사용자가 추가한 범위 전체 가림'}});
  }
  const next=[...remaining,...added].sort((a,b)=>a.source===b.source?a.start-b.start:a.source==='title'?-1:1);
  for(let i=1;i<next.length;i++)if(overlaps(next[i-1],next[i]))throw new Error('다른 검토 후보와 겹칩니다. 범위를 조정하거나 겹치는 후보를 먼저 제외하세요.');
  validateCandidates(draft,next);
  const nextChoices={...choices};if(replaceId)delete nextChoices[replaceId];
  return {candidates:next,choices:nextChoices,added};
}

export function excludePostCandidates(candidates:Candidate[],choices:MaskChoices,ids:string[]) {
  const excluded=new Set(ids),nextChoices={...choices};
  for(const id of excluded)delete nextChoices[id];
  return {candidates:candidates.filter(c=>!excluded.has(c.id)),choices:nextChoices};
}
