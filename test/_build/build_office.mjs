import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile, Presentation, PresentationFile } from '@oai/artifact-tool';
const base=path.resolve(import.meta.dirname,'..');
const fixtures=path.join(base,'fixtures'), qa=path.join(base,'qa');
await fs.mkdir(fixtures,{recursive:true}); await fs.mkdir(qa,{recursive:true});
for (const kind of ['values','formulas','blocked']) {
  const w=Workbook.create(); const s=w.worksheets.add('참가자');
  s.getRange('A1:D4').values=[['항목','값','비고','확인'],['성명','김민수','가상 예시','검토'],['전화','010-0000-1234','가상 연락처','검토'],['메일','sample@example.invalid','예약 도메인','검토']];
  s.getRange('A1:D4').format.font={name:'Malgun Gothic',size:11};
  s.getRange('A1:D1').format.fill='#E8EEF5';s.getRange('A1:D1').format.font.bold=true;
  s.getRange('A1:A4').format.columnWidth=14;s.getRange('B1:B4').format.columnWidth=35;s.getRange('C1:D4').format.columnWidth=20;
  s.getRange('A1:D4').format.rowHeight=26;
  s.showGridLines=false;
  if(kind==='values') {
    const h=w.worksheets.add('비공개');h.getRange('A1:B2').values=[['성명','이지은'],['전화','010-0000-5678']];
    h.getRange('A1:B2').format.columnWidth=25;h.getRange('A1:B2').format.font={name:'Malgun Gothic',size:11};
    w.comments.setSelf({displayName:'김민수'});
    w.notes.add({id:'참가자:B2',target:{cell:{sheetName:s.name,sheetId:s.sheetId,address:'B2'}},authorId:'',createdAt:'',body:{plainText:'담당 이지은 연락 010-0000-5678'}});
  }
  if(kind==='formulas') {
    s.getRange('A6:B7').values=[['파생 성명',null],['파생 전화',null]];
    s.getRange('B6').formulas=[['=LEFT(B2,1)&"민수"']];
    s.getRange('B7').formulas=[['=CONCATENATE("010-0000-","5678")']];
  }
  if(kind==='blocked')s.getRange('D2').dataValidation={rule:{type:'list',values:['김민수','이지은']}};
  w.recalculate();
  await (await SpreadsheetFile.exportXlsx(w)).save(path.join(fixtures,`xlsx_${kind}.xlsx`));
  for (const sh of w.worksheets.items) {
    try { const blob=await w.render({sheetName:sh.name,range:kind==='formulas'?'A1:D8':'A1:D4',scale:1.5});await fs.writeFile(path.join(qa,`xlsx_${kind}_${sh.name}.png`),new Uint8Array(await blob.arrayBuffer())); }
    catch(e){console.log('render warning',String(e).slice(0,100));}
  }
  console.log('XLSX',kind);
}
const p=Presentation.create({slideSize:{width:1280,height:720}});
for (const [i,text] of ['문서 개인정보 검토 예시\n담당자 김민수\n전화 010-0000-1234\nsample@example.invalid','내부 검토 기록\n담당자 이지은\n전화 010-0000-5678'].entries()) {
  const s=p.slides.add();s.background.fill='#FFFFFF';
  const t=s.shapes.add({geometry:'textbox',position:{left:80,top:70,width:1120,height:560},fill:'none',line:{fill:'none',width:0}});
  t.text=text;t.text.style={fontFamily:'Malgun Gothic',fontSize:36,color:'#111111'};
  if(i===0)s.speakerNotes.text='발표자 이지은 연락 010-0000-5678';
  const blob=await p.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(qa,`pptx-slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await (await PresentationFile.exportPptx(p)).save(path.join(fixtures,'pptx_body.pptx'));
console.log('PPTX ready');
