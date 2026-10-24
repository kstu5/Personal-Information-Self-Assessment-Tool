const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('assert/strict');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname, '..', '..'),out=path.join(root,'tmp','masking-ui');
fs.mkdirSync(out,{recursive:true});
const url=JSON.parse(fs.readFileSync(path.join(root,'tmp','app-ready.json'),'utf8')).url;
const filename='masking-check.piipost',disk=path.join(out,filename);
const report={checks:[],errors:[],externalRequests:[]};
const draft={
 title:'김하늘 모임 안내',
 body:'😀 é 준비 담당은 김하늘입니다.\n\n개인 연락: 010-0000-0000\n재등장: 010-0000-0000\n\n문의: haneul@example.com\n\n장소: 서울특별시 마포구 예시로 12, 302호\n\n김하늘과 박하차를 준비합니다. 29세 운영진.\n\n주민등록번호: 990101-1000000\n\n'+
 Array.from({length:11},(_,i)=>`추가 연락 ${i+1}: 010-0000-${String(i+1).padStart(4,'0')}`).join('\n'),
};
function detected(d){
 const specs=[['PERSON','성명','HIGH',/김하늘|박하/g],['PHONE','전화번호','HIGH',/010-0000-\d{4}/g],
 ['EMAIL','이메일','HIGH',/haneul@example\.com/g],['ADDRESS','주소','MEDIUM',/서울특별시 마포구 예시로 12, 302호/g],
 ['AGE','나이','LOW',/29세/g],['POSITION','직책','INFO',/운영진/g],['RRN','주민등록번호','CRITICAL',/990101-1000000/g]];
 const candidates=[];
 for(const source of ['title','body'])for(const [label,labelName,risk,re] of specs){
  for(const m of d[source].matchAll(re))candidates.push({id:`${source}-${m.index}-${label}`,source,start:m.index,end:m.index+m[0].length,text:m[0],label,labelName,risk});
 }
 return candidates.sort((a,b)=>a.source===b.source?a.start-b.start:a.source==='title'?-1:1);
}
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:1000}});
  await context.exposeBinding('maskTestFile',async(_,{action,content})=>{
   if(action==='write')fs.writeFileSync(disk,content,'utf8');
   if(action==='read')return fs.readFileSync(disk,'utf8');
  });
  await context.addInitScript(name=>{
   const handle={name,async getFile(){return new File([await window.maskTestFile({action:'read'})],name);},
    async createWritable(){let content;return {async write(v){content=v;},async close(){await window.maskTestFile({action:'write',content});},async abort(){}};}};
   window.showSaveFilePicker=async()=>handle;window.showOpenFilePicker=async()=>[handle];
  },filename);
  const page=await context.newPage();
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('request',r=>{if(!r.url().startsWith(url+'/')&&!r.url().startsWith('data:'))report.externalRequests.push(r.url());});
  await page.route('**/api/check',route=>{
   const d=route.request().postDataJSON();
   return route.fulfill({contentType:'application/json',body:JSON.stringify({revision:d.revision,candidates:detected(d),engine:'UI 검증용 고정 후보',elapsedMs:1})});
  });
  const pass=name=>{report.checks.push(name);console.log('PASS',name);};
  const c=detected(draft),title=c.find(x=>x.source==='title'),phones=c.filter(x=>x.label==='PHONE'),email=c.find(x=>x.label==='EMAIL'),tea=c.find(x=>x.text==='박하');
  const mark=x=>page.locator(`.marker[data-candidate-id="${x.id}"]`);
  const mode=x=>page.locator(`.rv-methods [data-mode="${x}"]`).click();
  const row=x=>page.locator(`.rv-row[data-id="${x.id}"]`);
  const listUndo=()=>page.locator('.rv-list-toolbar button').click();
  const save=async()=>{await page.getByRole('button',{name:'저장',exact:true}).click();if(await page.locator('dialog').count())await page.getByRole('button',{name:'위치 선택하고 저장'}).click();await page.locator('.unsaved').waitFor({state:'hidden'});};
  await page.goto(url);await page.locator('.mode-nav').getByRole('button',{name:'게시글 검사',exact:true}).click();await page.getByRole('button',{name:/새 글 작성/}).click();
  await page.locator('#post-title').fill(draft.title);await page.locator('#post-body').fill(draft.body);
  await save();
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.locator('.dashboard').waitFor();
  assert.equal(await page.locator('.marker').count(),c.length);
  assert.equal(await page.locator('.rv-row').count(),0);
  assert.equal(await page.locator('.post-body').innerText(),draft.body);
  const multipleMode=page.getByRole('button',{name:'여러 개 선택',exact:true});
  const singleMode=page.getByRole('button',{name:'한 개씩 선택',exact:true});
  await multipleMode.click();
  assert((await page.locator('.rv-selection-hint').innerText()).includes('Ctrl 없이'));
  await mark(phones[0]).click();await mark(phones[1]).click();
  assert.equal(await page.locator('.marker[aria-pressed=true]').count(),3);
  await mark(phones[0]).click();
  assert.equal(await page.locator('.marker[aria-pressed=true]').count(),2);
  await singleMode.click();assert.equal(await page.locator('.marker[aria-pressed=true]').count(),1);
  await mark(phones[0]).click({modifiers:['Control']});
  assert.equal(await multipleMode.getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('.marker[aria-pressed=true]').count(),2);
  await mark(phones[0]).click({modifiers:['Control']});
  assert.equal(await page.locator('.marker[aria-pressed=true]').count(),1);
  await singleMode.click();
  pass('Visible single/multiple modes, plain-click toggling, selected count and optional Ctrl shortcut');
  await mark(phones[0]).hover();assert((await page.getByRole('tooltip').innerText()).includes('높음 · 전화번호'));
  await mark(phones[0]).click();assert.equal(await page.locator('.rv-original').innerText(),phones[0].text);
  await mode('partial');assert(await page.locator('.unsaved').isVisible());
  await page.getByRole('button',{name:'처리 결과',exact:true}).click();
  assert.equal(await mark(phones[0]).innerText(),'010-****-0000');
  assert.equal(await mark(phones[1]).innerText(),'010-0000-0000');
  await mark(title).click();await mode('full');
  assert.equal(await mark(title).innerText(),'█████');
  pass('Full body, five risks, hover, initial no masking, and repeated occurrence/field isolation');
  await multipleMode.click();
  await row(phones[0]).locator('[data-action="switch"]').click();
  assert.equal(await mark(phones[0]).innerText(),'█████');
  assert.equal(await page.locator('.marker[aria-pressed=true]').count(),1);
  await row(phones[0]).locator('[data-action="switch"]').click();
  await row(phones[0]).locator('[data-action="cancel"]').click();
  assert.equal(await mark(phones[0]).innerText(),phones[0].text);
  assert.equal(await row(phones[0]).count(),0);
  assert.equal(await page.locator('.marker').count(),c.length);
  await listUndo();assert.equal(await mark(phones[0]).innerText(),'010-****-0000');
  await mark(tea).click();await mode('keep');assert.equal(await mark(tea).innerText(),'박하');
  await mark(email).click();await mode('custom');
  const input=page.locator('#replacement-text');
  await input.evaluate(e=>e.dataset.stable='true');
  await input.dispatchEvent('compositionstart');await input.fill('게시판 <쪽지> & 문의');await input.dispatchEvent('compositionend');
  assert.equal(await input.getAttribute('data-stable'),'true');
  assert.equal(await mark(email).innerText(),email.text);
  await input.fill(' ');assert(await page.getByRole('button',{name:'수정 내용 반영'}).isDisabled());
  await input.fill('게시판 <쪽지> & 문의');await page.getByRole('button',{name:'수정 내용 반영'}).click();
  assert.equal(await mark(email).innerText(),'게시판 <쪽지> & 문의');
  assert.equal(await mark(email).locator('*').count(),0);
  pass('One-click row switch, cancellation, undo, false-positive keep and literal Korean custom input');
  await page.getByRole('button',{name:'원문',exact:true}).click();
  assert.equal(await mark(title).innerText(),title.text);
  await save();
  const saved=JSON.parse(fs.readFileSync(disk,'utf8'));
  assert.equal(saved.title,'█████ 모임 안내');
  assert(saved.body.includes('010-****-0000\n재등장: 010-0000-0000'));
  assert(saved.body.includes('게시판 <쪽지> & 문의'));
  assert.equal(saved.format,'before-post-document');assert.equal(saved.version,1);
  assert.equal(saved.body.includes('haneul@example.com'),false);
  await row(title).locator('[data-action="cancel"]').click();
  assert(await page.locator('.unsaved').isVisible());
  await page.getByRole('button',{name:'새 글',exact:true}).click();
  await page.getByRole('dialog').waitFor();await page.getByRole('button',{name:'취소',exact:true}).click();
  await listUndo();await page.locator('.unsaved').waitFor({state:'hidden'});
  pass('Saving in original view writes processed title/body; cancellation marks dirty and undo restores saved state');
  await page.getByRole('button',{name:`전체 ${c.length}곳 선택`,exact:true}).click();await mode('full');
  assert.equal(await page.locator('[data-list="full"] .rv-row').count(),6);
  const next=()=>page.locator('[data-list="full"]').getByRole('button',{name:'다음',exact:true}).click();
  await next();await next();
  const targetId=await page.locator('[data-list="full"] .rv-row').first().getAttribute('data-id');
  const target=c.find(x=>x.id===targetId);
  await row(target).locator('[data-action="switch"]').click();assert.equal(await row(target).locator('[data-action="switch"]').innerText(),'⇄ 전체로');
  await listUndo();assert.equal(await page.locator('[data-list="full"] .rv-row').first().getAttribute('data-id'),targetId);
  await listUndo();await page.locator('.unsaved').waitFor({state:'hidden'});
  await row(title).locator('.rv-row-main').click();
  assert.equal(await input.inputValue(),'█████');
  assert.equal(await input.evaluate(e=>e===document.activeElement),true);
  await row(phones[0]).locator('.rv-row-main').click();
  assert.equal(await page.locator('.rv-original').innerText(),phones[0].text);
  assert.equal(await input.inputValue(),'010-****-0000');
  assert.equal(await input.evaluate(e=>e===document.activeElement),true);
  await input.fill('010-0000-****');
  assert.equal(await row(phones[0]).locator('.rv-row-change strong').innerText(),'010-****-0000');
  await page.getByRole('button',{name:'수정 내용 반영'}).click();
  assert.equal(await page.locator('[data-list="partial"] .rv-row').count(),0);
  await listUndo();assert.equal(await row(phones[0]).locator('.rv-row-change strong').innerText(),'010-****-0000');
  await page.locator('.unsaved').waitFor({state:'hidden'});
  pass('Whole-document selection, six-row paging, cross-list movement and undo restores page and decisions');
  await page.screenshot({path:path.join(out,'masking-desktop.png'),fullPage:true});
  for(const width of [1024,736,390,320]){
   await page.setViewportSize({width,height:900});
   await mark(email).scrollIntoViewIfNeeded();
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   await mark(email).hover();
   await page.getByRole('tooltip').waitFor({state:'visible'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);
   const tooltip=await page.getByRole('tooltip').boundingBox();if(tooltip)assert(tooltip.x>=0&&tooltip.x+tooltip.width<=width);
   await page.mouse.move(0,0);
   if(width===390)await page.screenshot({path:path.join(out,'masking-mobile.png'),fullPage:true});
  }
  await page.setViewportSize({width:1280,height:1000});
  await page.getByRole('button',{name:'수정한 글로 이어쓰기',exact:true}).click();
  assert.equal(await page.locator('#post-title').inputValue(),saved.title);
  assert.equal(await page.locator('#post-body').inputValue(),saved.body);
  assert.equal(await page.locator('.dashboard').count(),0);
  await page.reload();await page.locator('.mode-nav').getByRole('button',{name:'게시글 검사',exact:true}).click();await page.getByRole('button',{name:'저장한 글 불러오기'}).click();
  assert.equal(await page.locator('#post-title').inputValue(),saved.title);
  assert.equal(await page.locator('#post-body').inputValue(),saved.body);
  pass('Responsive layout and bounded tooltips; continue writing and real-file reopen retain processed text');
  // A one-character occurrence expands to five blocks: reject overflowing the existing title limit.
  await page.locator('#post-title').fill('가'.repeat(299)+'박');
  await page.unroute('**/api/check');
  await page.route('**/api/check',route=>{
   const d=route.request().postDataJSON();
   return route.fulfill({contentType:'application/json',body:JSON.stringify({revision:d.revision,engine:'한도 검증',elapsedMs:1,
    candidates:[{id:'limit',source:'title',start:299,end:300,text:'박',label:'PERSON',labelName:'성명',risk:'HIGH'}]})});
  });
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.locator('.dashboard').waitFor();await mode('full');
  assert((await page.locator('.rv-list-toolbar').innerText()).includes('한도를 넘습니다'));
  assert.equal(await page.locator('.rv-row').count(),0);
  await mode('custom');await page.locator('#replacement-text').fill('두 글자');
  assert(await page.getByRole('button',{name:'수정 내용 반영'}).isDisabled());
  pass('Full and custom replacement cannot exceed file limits');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.externalRequests,[]);
  pass('No JavaScript errors or external network requests');
 }finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
