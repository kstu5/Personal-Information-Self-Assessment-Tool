import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'../..'),out=path.join(root,'test/shared-document-examples'),qa=path.join(root,'test/qa/shared-documents');
await fs.mkdir(out,{recursive:true});await fs.mkdir(qa,{recursive:true});
const data=JSON.parse(await fs.readFile(path.join(import.meta.dirname,'shared_data.json'),'utf8'));
const w=Workbook.create();const publicSheet=w.worksheets.add('공유용_명단'),internal=w.worksheets.add('내부_배송정보');
publicSheet.getRange('A2').values=[['가을 독서 행사 추첨 당첨자 명단']];
publicSheet.getRange('A4:E14').values=[['번호','성명','휴대전화','당첨 상품','발표일'],...data.people.map(p=>[p.number,p.name,p.phone,p.prize,new Date('2026-10-25T00:00:00Z')])];
publicSheet.getRange('E5:E14').setNumberFormat('yyyy-mm-dd');
publicSheet.getRange('A16').values=[['모든 인적사항은 파일 검사 연습용 가상 정보입니다.']];
internal.getRange('A2').values=[['내부 배송정보']];
internal.getRange('A4:E7').values=[['번호','성명','휴대전화','이메일','배송 주소'],...data.people.slice(0,3).map(p=>[p.number,p.name,p.phone,p.email,p.address])];
internal.getRange('A9').values=[['발송 대상 3명의 연락처와 배송 주소를 보관한 내부 시트입니다.']];
for(const s of [publicSheet,internal]) {
  s.showGridLines=false;s.getRange('A1:E16').format.font={name:'Malgun Gothic',size:11};
  s.getRange('A2:E2').format.font={name:'Malgun Gothic',size:16,bold:true};
  s.getRange('A2:E2').format.rowHeight=34;s.getRange('A2:E2').format.verticalAlignment='center';
  const end=s===publicSheet?14:7;
  s.getRange(`A4:E${end}`).format.rowHeight=28;s.getRange(`A4:E${end}`).format.verticalAlignment='center';
  s.getRange('A4:E4').format.fill='#203B55';s.getRange('A4:E4').format.font={name:'Malgun Gothic',size:11,bold:true,color:'#FFFFFF'};
  s.getRange('A1:A16').format.columnWidth=8;s.getRange('B1:B16').format.columnWidth=14;s.getRange('C1:C16').format.columnWidth=23;
  s.getRange('D1:D16').format.columnWidth=s===publicSheet?24:37;s.getRange('E1:E16').format.columnWidth=s===publicSheet?18:62;
  for(let row=5;row<=end;row++)if(row%2===0)s.getRange(`A${row}:E${row}`).format.fill='#F0F4F8';
  s.getRange('A16').format.font.size=9;s.freezePanes.freezeRows(4);
}
w.recalculate();
const inspection=await w.inspect({kind:'table',range:'공유용_명단!A4:E14',include:'values,formulas',tableMaxRows:11,tableMaxCols:5,maxChars:6000});
await fs.writeFile(path.join(qa,'workbook-inspection.ndjson'),inspection.ndjson);
for(const s of [publicSheet,internal]) {
  const blob=await w.render({sheetName:s.name,range:s===publicSheet?'A1:E16':'A1:E10',scale:1.5});
  await fs.writeFile(path.join(qa,s.name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(w)).save(path.join(out,'추첨당첨자_명단예시.xlsx'));
console.log('Created synthetic winners workbook');
