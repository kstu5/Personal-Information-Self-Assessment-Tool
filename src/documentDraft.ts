import type {MaskChoice,MaskMode} from './masking.ts';
import {partialMask,replacement} from './masking.ts';
import type {FileCandidate,FilePart,FileSelection} from './documentTypes.ts';

export function fileReplacement(candidate:FileCandidate,choice?:MaskChoice):string {
  return choice?.mode==='partial'?(candidate.partialText??partialMask(candidate)):replacement(candidate,choice);
}

export function draftStatus(candidate:FileCandidate,selection:FileSelection):MaskMode|'text'|'unset' {
  return candidate.part in selection.textEdits?'text':selection.choices[candidate.id]?.mode||'unset';
}

export function draftChunks(part:FilePart,candidates:FileCandidate[],selection:FileSelection,applied:boolean):{text:string;candidate?:FileCandidate}[] {
  if(applied&&part.id in selection.textEdits)return [{text:selection.textEdits[part.id]}];
  const chunks:{text:string;candidate?:FileCandidate}[]=[];let pos=0;
  for(const candidate of candidates.filter(c=>c.part===part.id).sort((a,b)=>a.start-b.start)){
    chunks.push({text:part.text.slice(pos,candidate.start)});
    chunks.push({text:applied?fileReplacement(candidate,selection.choices[candidate.id]):candidate.text,candidate});
    pos=candidate.end;
  }
  chunks.push({text:part.text.slice(pos)});
  return chunks;
}
