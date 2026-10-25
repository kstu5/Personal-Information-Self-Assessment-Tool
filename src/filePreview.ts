import type {FilePart,FileSelection} from './documentTypes.ts';

export function previewView(kind?:string):FileSelection['view'] {
  if(['.xlsx','.csv','.tsv'].includes(kind||''))return 'sheet';
  if(['.docx','.pptx'].includes(kind||''))return 'pages';
  if(['.pdf','.png','.jpg','.jpeg'].includes(kind||''))return 'images';
  if(['.txt','.hwpx','.hwp'].includes(kind||''))return 'content';
  return 'text';
}

export function readingParts(parts:FilePart[]) {
  const section=(p:FilePart)=>Number(p.flow?.section?.match(/section(\d+)\.xml$/)?.[1]||0);
  return parts.filter(p=>p.flow).sort((a,b)=>section(a)-section(b)||(a.flow?.line??a.flow?.order??0)-(b.flow?.line??b.flow?.order??0));
}

export function contentPage(parts:FilePart[],part:string) {
  return Math.max(0,Math.floor(readingParts(parts).findIndex(p=>p.id===part)/30));
}
