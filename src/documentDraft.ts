import type {MaskChoice,MaskMode} from './masking.ts';
import {isCredential,partialMask,replacement} from './masking.ts';
import type {FileCandidate,FilePart,FileSelection} from './documentTypes.ts';

export function fileReplacement(candidate:FileCandidate,choice?:MaskChoice):string {
  if(candidate.imageTextEditable&&(choice?.mode==='full'||choice?.mode==='partial'&&isCredential(candidate)))return '비공개';
  return choice?.mode==='partial'?(candidate.partialText??partialMask(candidate)):replacement(candidate,choice);
}

export function draftStatus(candidate:FileCandidate,selection:FileSelection):MaskMode|'text'|'unset' {
  return candidate.part in selection.textEdits?'text':selection.choices[candidate.id]?.mode||'unset';
}

export function bulkMaskTargets(candidates:FileCandidate[],selection:FileSelection) {
  const ids:string[]=[];
  let overlaps=0;
  for(const candidate of candidates){
    if(draftStatus(candidate,selection)!=='unset')continue;
    const boxes=candidate.maskBoxes?.full??candidate.boxes??[];
    const intersects=candidate.asset&&selection.regions.some(({asset,box})=>
      asset===candidate.asset&&boxes.some(([left,top,right,bottom])=>
        left<box[2]&&right>box[0]&&top<box[3]&&bottom>box[1]));
    if(intersects)overlaps++;
    else ids.push(candidate.id);
  }
  return {ids,overlaps};
}

export function bulkChoicesToUndo(selection:FileSelection):string[] {
  // Individual edits replace their choice objects, even when the mode matches.
  return Object.keys(selection.lastBulkChoices).filter(id=>selection.choices[id]===selection.lastBulkChoices[id]);
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
