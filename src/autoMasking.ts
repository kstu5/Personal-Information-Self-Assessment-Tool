import {defaultChoices} from './masking.ts';
import type {MaskChoices} from './masking.ts';
import {EMPTY_SELECTION} from './documentTypes.ts';
import type {FileCandidate,FileSelection} from './documentTypes.ts';
import {bulkMaskTargets} from './documentDraft.ts';
import {previewView} from './filePreview.ts';

export function initialFileSelection(candidates:FileCandidate[],kind?:string):FileSelection {
  const choices=defaultChoices(candidates.filter(c=>c.editable!==false));
  return {...EMPTY_SELECTION,choices,initialChoices:choices,view:previewView(kind)};
}

export function autoMaskPlan(candidates:FileCandidate[],selection:FileSelection) {
  const available=new Set(bulkMaskTargets(candidates,{...selection,choices:{}}).ids);
  const choices:MaskChoices={},rows:{label:string;rule:string;count:number;status:string}[]=[];
  let preserved=0,review=0,overlaps=0;
  for(const c of candidates){
    let status='적용 예정';
    if(c.editable===false){review++;status='수정 저장 제한';}
    else if(c.part in selection.textEdits||selection.choices[c.id]&&selection.choices[c.id]!==selection.initialChoices[c.id]){preserved++;status='기존 지정 유지';}
    else if(!available.has(c.id)){overlaps++;status='영역 겹침 확인';}
    else if(!c.autoMask?.choice){review++;status='직접 확인 필요';}
    else choices[c.id]=c.autoMask.choice;
    const rule=c.autoMask?.rule||'가림 기준을 직접 확인해 주세요.';
    const row=rows.find(r=>r.label===c.labelName&&r.rule===rule&&r.status===status);
    if(row)row.count++;else rows.push({label:c.labelName,rule,count:1,status});
  }
  return {choices,rows,preserved,review,overlaps,count:Object.keys(choices).length};
}

export function applyAutoMask(selection:FileSelection,choices:MaskChoices):Partial<FileSelection> {
  const beforeAutoChoices:MaskChoices={};
  for(const key of Object.keys(choices))if(selection.choices[key])beforeAutoChoices[key]=selection.choices[key];
  return {choices:{...selection.choices,...choices},lastAutoChoices:choices,beforeAutoChoices};
}

export function autoChoicesToUndo(selection:FileSelection):string[] {
  return Object.keys(selection.lastAutoChoices).filter(id=>selection.choices[id]===selection.lastAutoChoices[id]);
}

export function undoAutoMask(selection:FileSelection):Partial<FileSelection> {
  const choices={...selection.choices};
  for(const key of autoChoicesToUndo(selection)){
    if(selection.beforeAutoChoices[key])choices[key]=selection.beforeAutoChoices[key];else delete choices[key];
  }
  return {choices,lastAutoChoices:{},beforeAutoChoices:{}};
}
