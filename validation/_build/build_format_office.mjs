import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Workbook, SpreadsheetFile, Presentation, PresentationFile, FileBlob } from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'../..');
const out=path.join(root,'examples/formats/files');
const qa=path.join(root,'validation/qa/format-documents');
const {people:p,fake}=JSON.parse(await fs.readFile(path.join(qa,'office-data.json'),'utf8'));
const font='Malgun Gothic';
const wb=Workbook.create();
const s=wb.worksheets.add('배송요청');
const c=wb.worksheets.add('운영연락처');
const h=wb.worksheets.add('이전연락처');
s.getRange('A2').values=[['기념품 배송 요청 명단']];
s.getRange('A3').values=[[fake]];
s.getRange('A5:F13').values=[['번호','수령인','연락처','배송 주소','품목','발송 예정일'],
  ...p.map((v,i)=>[i+1,v.name,v.phone,v.address,'도서 기념품',new Date('2026-11-02T00:00:00Z')])];
s.getRange('F6:F13').setNumberFormat('yyyy-mm-dd');
s.getRange('C6:C13').setNumberFormat('@');
const columns=[8,13,23,59,19,21];
for(let i=0;i<columns.length;i++)s.getRange(`${'ABCDEF'[i]}1:${'ABCDEF'[i]}13`).format.columnWidth=columns[i];
for(const [sh,title,head,row] of [
  [c,'발송 운영 연락처',['담당자','연락처','이메일'],[p[2].name,p[2].phone,p[2].email]],
  [h,'이전 연락처 보관',['담당자','이전 연락처','자료구분'],[p[3].name,p[3].phone,'가상정보']],
]){
  sh.getRange('A2').values=[[title]];sh.getRange('A3').values=[[fake]];
  sh.getRange('A4:C5').values=[head,row];
  sh.getRange('A1:A5').format.columnWidth=22;
  sh.getRange('B1:B5').format.columnWidth=26;
  sh.getRange('C1:C5').format.columnWidth=48;
}
for(const sh of wb.worksheets.items){
  const last=sh===s?13:5,end=sh===s?'F':'C',header=sh===s?5:4;
  sh.showGridLines=false;
  sh.getRange(`A1:${end}${last}`).format.font={name:font,size:11,color:'#17202A'};
  sh.getRange(`A1:${end}${last}`).format.rowHeight=28;
  sh.getRange(`A1:${end}${last}`).format.verticalAlignment='center';
  sh.getRange('A2').format.font={name:font,size:16,bold:true};
  sh.getRange('A3').format.font={name:font,size:10,color:'#556575'};
  const r=sh.getRange(`A${header}:${end}${header}`);
  r.format.fill='#243F5C';r.format.font={name:font,size:11,bold:true,color:'#FFFFFF'};
  r.format.horizontalAlignment='center';
  for(let row=header+1;row<=last;row++)if(row%2===0)sh.getRange(`A${row}:${end}${row}`).format.fill='#F0F4F8';
  if(sh===s)sh.freezePanes.freezeRows(5);
}
wb.recalculate();
for(const sh of wb.worksheets.items){
  const end=sh===s?'F13':'C5';
  const b=await wb.render({sheetName:sh.name,range:`A1:${end}`,scale:1.5});
  await fs.writeFile(path.join(qa,`xlsx-${sh.name}.png`),new Uint8Array(await b.arrayBuffer()));
}
await fs.writeFile(path.join(qa,'xlsx-inspect.ndjson'),(await wb.inspect({kind:'table',range:'배송요청!A5:F13',include:'values,formulas',maxChars:4000,tableMaxRows:10,tableMaxCols:6})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'08_기념품_배송요청명단.xlsx'));
console.log('XLSX exported');

const deck=Presentation.create({slideSize:{width:1280,height:720}});
deck.theme.defaultFont=font;
function text(slide,value,y,size=30,height=65,color='#17202A'){
  const box=slide.shapes.add({geometry:'textbox',position:{left:80,top:y,width:1120,height},fill:'none',line:{fill:'none',width:0}});
  box.text=value;box.text.style={typeface:font,fontSize:size,color};return box;
}
function slide(title){
  const s=deck.slides.add();s.background.fill='#FFFFFF';text(s,title,65,46,90);return s;
}
let z=slide('가을 독서 행사 운영 브리핑');
text(z,'2026년 11월 14일 09시부터 12시까지',225,34);
text(z,'접수와 현장 안내를 맡은 운영진에게 배포합니다.',325,30);
text(z,'가상문화연구회',435,30);
text(z,fake,600,23,60,'#596979');
z=slide('운영 일정과 담당자');
text(z,`09:00  접수 시작\n담당자 ${p[0].name}   ${p[0].phone}\n회신 ${p[0].email}`,195,31,175);
text(z,`10:00  독서 모임 진행\n현장 안내 ${p[1].name}   ${p[1].phone}`,410,31,125);
text(z,'12:00  행사 종료 및 장소 정리',575,29,60);
z.speakerNotes.text=`현장 지원 담당자 ${p[3].name}, 전화 ${p[3].phone}. 장비 문제 발생 시 먼저 연락합니다. 모든 연락처는 검사 연습용 가상 정보입니다.`;
z=slide('참가 변경과 자료 회신');
text(z,'참가 변경 사항은 행사 전날 18시까지 회신해 주세요.',200,31,90);
text(z,`운영 담당자 ${p[2].name}\n전화 ${p[2].phone}\n이메일 ${p[2].email}`,330,31,170);
text(z,'작성일 2026년 10월 25일',580,27,60);
const skill=path.join(process.env.USERPROFILE,'.codex/plugins/cache/openai-primary-runtime/presentations/26.1022.11436/skills/presentations');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies');
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const draft=path.join(qa,'briefing-draft.pptx');
await (await PresentationFile.exportPptx(deck)).save(draft);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const final=path.join(out,'05_행사운영_사전브리핑.pptx');
const validatedDir=path.join(qa,'finalized');
await fs.mkdir(validatedDir,{recursive:true});
const validatedPath=path.join(validatedDir,`briefing-${Date.now()}.pptx`);
await finalizePresentation({workspaceDir:root,candidatePath:draft,finalPath:validatedPath,
  pythonExecutable:path.join(runtime,'python/python.exe'),
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
  fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
  receiptPath:path.join(qa,'pptx-validation.json')});
await fs.copyFile(validatedPath,final);
const finalDeck=await PresentationFile.importPptx(await FileBlob.load(final));
for(const [i,sl] of finalDeck.slides.items.entries()){
  const b=await finalDeck.export({slide:sl,format:'png',scale:1});
  await fs.writeFile(path.join(qa,`pptx-slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log('PPTX finalized and rendered');
