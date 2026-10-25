const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..', '..');
const output = path.join(root,'tmp','ui-check');
fs.mkdirSync(output,{recursive:true});
const url = JSON.parse(fs.readFileSync(path.join(root,'tmp','app-ready.json'),'utf8')).url;
const report={checks:[],errors:[],externalRequests:[]};
const disk = path.join(output,'selected-folder');fs.mkdirSync(disk,{recursive:true});
let filename='작업 파일.piipost', failWrite=false, cancelPicker=false, cancelWrite=false;

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try {
  const context=await browser.newContext({viewport:{width:1280,height:960},deviceScaleFactor:1});
  await context.exposeBinding('testFile',async(_,{operation,name,content})=>{
   if(name && path.basename(name)!==name)throw new Error('Invalid test path');
   if(operation==='pickSave'){if(cancelPicker)return {cancelled:true};filename=name;return {name};}
   if(operation==='pickOpen'){if(cancelPicker)return {cancelled:true};return {name:filename};}
   if(operation==='beginWrite')return {cancelled:cancelWrite};
   const target=path.join(disk,name);
   if(operation==='read')return {content:fs.readFileSync(target,'utf8')};
   if(operation==='write'){if(failWrite)throw new Error('Simulated disk failure');fs.writeFileSync(target,content,'utf8');return {};}
  });
  // Only OS pickers are substituted. Reads/writes use real temporary disk files.
  // Detection and the complete production UI run against the actual local server.
  await context.addInitScript(()=>{
   function handle(name){return {name, async getFile(){const d=await window.testFile({operation:'read',name});return new File([d.content],name);},async createWritable(){const state=await window.testFile({operation:'beginWrite'});if(state.cancelled)throw new DOMException('Cancelled','AbortError');let pending='';return {async write(s){pending=s;},async close(){await window.testFile({operation:'write',name,content:pending});},async abort(){}};}};}
   window.showSaveFilePicker=async options=>{const d=await window.testFile({operation:'pickSave',name:options.suggestedName});if(d.cancelled)throw new DOMException('Cancelled','AbortError');return handle(d.name);};
   window.showOpenFilePicker=async()=>{const d=await window.testFile({operation:'pickOpen'});if(d.cancelled)throw new DOMException('Cancelled','AbortError');return [handle(d.name)];};
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('request',r=>{if(!r.url().startsWith(url+'/')&&!r.url().startsWith('data:'))report.externalRequests.push(r.url());});
  await page.route('https://**',route=>route.abort());
  const screenshot=async name=>{await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});};
  const check=name=>{report.checks.push(name);console.log('PASS',name);};
  await page.goto(url);await page.locator('.mode-nav').getByRole('button',{name:'게시글 검사',exact:true}).click();await page.getByRole('heading',{name:'올리기 전, 한 번 살펴볼까요?'}).waitFor();await screenshot('start');
  await page.getByRole('button',{name:'가상 예시 글로 살펴보기'}).click();
  const originalTitle=await page.locator('#post-title').inputValue();
  await screenshot('write');
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.locator('.dashboard').waitFor({timeout:90000});
  assert.ok(await page.getByText(/ko-pii 1.16.0 \+ atonlee\/koelectra-ko-pii-ner/).isVisible());
  const count=await page.locator('.marker').count();assert.ok(count>0);assert.equal(Number(await page.locator('.total>strong').textContent()),count);
  assert.ok((await page.locator('.post-inner h2').textContent()).includes(originalTitle));
  const firstText=await page.locator('.marker').first().innerText();
  await page.locator('.marker').first().click();assert.equal(await page.locator('.rv-original').innerText(),firstText);
  await screenshot('results');check('Actual ko-pii + atonlee/koelectra-ko-pii-ner, full original text, counts, and individual marker selection');
  await page.getByRole('button',{name:'수정한 글로 이어쓰기',exact:true}).click();
  await page.getByRole('button',{name:'저장',exact:true}).click();await page.getByRole('dialog').waitFor();await screenshot('save');
  assert.equal(await page.locator('#filename').inputValue(),'10월 독서 모임 함께 읽을 분을 찾습니다');
  cancelPicker=true;await page.getByRole('button',{name:'위치 선택하고 저장'}).click();await page.getByRole('button',{name:'취소',exact:true}).click();assert.ok(await page.locator('.unsaved').isVisible());cancelPicker=false;
  await page.getByRole('button',{name:'저장',exact:true}).click();await page.getByRole('button',{name:'위치 선택하고 저장'}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  const savedName=filename;let saved=JSON.parse(fs.readFileSync(path.join(disk,savedName),'utf8'));assert.equal(saved.title,originalTitle);
  await page.locator('#post-title').fill('제목을 수정해도 파일 이름은 그대로');await page.keyboard.press('Control+s');await page.locator('.unsaved').waitFor({state:'hidden'});assert.equal(filename,savedName);assert.equal(JSON.parse(fs.readFileSync(path.join(disk,savedName),'utf8')).title,'제목을 수정해도 파일 이름은 그대로');
  await page.reload();await page.locator('.mode-nav').getByRole('button',{name:'게시글 검사',exact:true}).click();await page.getByRole('button',{name:'저장한 글 불러오기'}).click();assert.equal(await page.locator('#post-title').inputValue(),'제목을 수정해도 파일 이름은 그대로');assert.equal(await page.locator('.dashboard').count(),0);check('Real disk save, title sanitization, Ctrl+S stable filename, reload and reopen');
  await page.locator('#post-title').fill('취소한 이동은 다시 실행하지 않기');cancelWrite=true;await page.getByRole('button',{name:'새 글',exact:true}).click();await page.getByRole('button',{name:'저장하고 계속'}).click();await page.getByRole('button',{name:'저장',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('.file-actions .save-button').disabled);cancelWrite=false;await page.getByRole('button',{name:'저장',exact:true}).click();await page.locator('.unsaved').waitFor({state:'hidden'});assert.equal(await page.locator('#post-title').inputValue(),'취소한 이동은 다시 실행하지 않기');check('Cancelled save-and-continue does not replay an old navigation request');
  await page.locator('#post-body').fill('😀 é 전화: 010-0000-0001\n반복: 010-0000-0001\n<img src="https://example.com/leak" onerror="window.hacked=true">');
  await page.locator('#post-title').fill('연락처: 010-0000-0000');
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.locator('.dashboard').waitFor({timeout:30000});
  const numbers=await page.locator('.marker').allTextContents();assert.ok(numbers.includes('010-0000-0000'));assert.equal(numbers.filter(x=>x==='010-0000-0001').length,2);assert.equal(await page.locator('.post img').count(),0);assert.equal(await page.evaluate(()=>window.hacked),undefined);check('Emoji and combining-mark offsets, repeated values, literal HTML');
  await page.setViewportSize({width:390,height:844});await screenshot('results-narrow');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.setViewportSize({width:1280,height:960});
  await page.getByRole('button',{name:'수정한 글로 이어쓰기',exact:true}).click();await page.getByRole('button',{name:'새 글',exact:true}).click();await page.getByRole('dialog').waitFor();await page.getByRole('button',{name:'취소',exact:true}).click();assert.equal(await page.locator('#post-title').inputValue(),'연락처: 010-0000-0000');check('Unsaved draft guard cancel preserves text');
  failWrite=true;const before=fs.readFileSync(path.join(disk,savedName),'utf8');await page.getByRole('button',{name:'저장',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(fs.readFileSync(path.join(disk,savedName),'utf8'),before);assert.ok(await page.locator('.unsaved').isVisible());failWrite=false;check('Failed save preserves disk file and unsaved draft');
  fs.writeFileSync(path.join(disk,savedName),'broken','utf8');await page.getByRole('button',{name:'불러오기',exact:true}).click();await page.getByRole('button',{name:'저장하지 않고 계속'}).click();await page.getByRole('alert').waitFor();assert.equal(await page.locator('#post-title').inputValue(),'연락처: 010-0000-0000');check('Corrupt-file open preserves current text');
  await page.getByRole('button',{name:'새 글',exact:true}).click();await page.getByRole('button',{name:'저장하지 않고 계속'}).click();await page.locator('#post-body').fill('안녕하세요.');
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.locator('.dashboard').waitFor({timeout:30000});assert.equal(await page.locator('.total>strong').textContent(),'0');assert.ok(await page.getByText('탐지된 후보가 없습니다').isVisible());assert.ok(await page.getByText(/자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다/).isVisible());check('Zero candidates keeps the review notice');
  await page.getByRole('button',{name:'수정한 글로 이어쓰기',exact:true}).click();await page.locator('#post-body').fill('전화: 010-0000-0000');
  let release;const barrier=new Promise(r=>release=r);let seen;const requested=new Promise(r=>seen=r);
  await page.route('**/api/check',async route=>{const response=await route.fetch();seen();await barrier;await route.fulfill({response});});
  await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await requested;await page.locator('#post-body').fill('검사 중 수정한 글');release();await page.getByText('검사 중 글이 변경되었습니다. 현재 내용을 다시 검사해 주세요.').waitFor();assert.equal(await page.locator('.dashboard').count(),0);await page.unroute('**/api/check');check('Late responses cannot replace edited text');
  await page.route('**/api/check',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({message:'시험용 검사 실패'})}));await page.getByRole('button',{name:'개인정보 검사',exact:true}).click();await page.getByText('시험용 검사 실패').waitFor();assert.equal(await page.locator('.dashboard').count(),0);await page.unroute('**/api/check');check('Check failure is not displayed as zero candidates');
  await page.locator('#post-title').fill('');await page.getByRole('button',{name:'파일 메뉴'}).count().catch(()=>0);
  await page.locator('.file-menu summary').click();await page.getByRole('button',{name:'다른 이름으로 저장'}).click();assert.equal(await page.locator('#filename').inputValue(),'제목 없음');await page.setViewportSize({width:320,height:800});await screenshot('save-narrow');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.keyboard.press('Escape');assert.equal(await page.locator('dialog').count(),0);check('Blank filename, narrow viewport, modal Escape');
  assert.deepEqual(report.externalRequests,[]);assert.deepEqual(report.errors,[]);check('No external requests or JavaScript errors');
 }finally {fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
