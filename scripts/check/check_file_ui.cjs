const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname, '..', '..'),out=path.join(root,'local-only/outputs','file-feature-validation');fs.mkdirSync(out,{recursive:true});
const url=JSON.parse(fs.readFileSync(path.join(root,'tmp','file-feature-ready.json'),'utf8')).url;
const report={checks:[],errors:[],external:[]};
const created=new Set();let context,token;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  const page=await context.newPage();page.setDefaultTimeout(20000);
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('response',async r=>{if(r.url().includes('/api/documents/upload')&&r.ok()){try{created.add((await r.json()).id);}catch{}}});
  page.on('request',r=>{if(!r.url().startsWith(url+'/')&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))report.external.push(r.url());});
  const pass=name=>{report.checks.push(name);console.log('PASS',name);};
  await page.goto(url);token=await page.evaluate(()=>JSON.parse(document.querySelector('meta[name=app-boot]').content).token);await page.getByRole('heading',{name:'무엇을 검사할까요?'}).waitFor();
  await page.screenshot({path:path.join(out,'home.png'),fullPage:true});
  await page.locator('.mode-nav').getByRole('button',{name:'파일 검사',exact:true}).click();
  await page.locator('input[type=file]').setInputFiles([
   {name:'동네 모임.txt',mimeType:'text/plain',buffer:Buffer.from('담당자 이름: 김민수\n연락처: 010-0000-1234\n두 번째 담당자: 이지은\n박하차를 마시며 책을 읽어요.','utf8')},
   {name:'행사 안내.txt',mimeType:'text/plain',buffer:Buffer.from('행사 담당 이지은입니다.\n연락처 010-0000-5678\n모임은 오후 2시에 시작합니다.','utf8')},
  ]);
  await page.getByRole('button',{name:'사본 생성 · 재검사',exact:true}).waitFor({timeout:90000});
  await page.waitForFunction(()=>{const b=document.querySelector('.file-export>.primary');return !!b&&!b.disabled;},{},{timeout:90000});
  assert.equal(await page.locator('.document-tab').count(),2);pass('Real A-model inspection, multiple file queue, and locations');
  const first=page.locator('.file-candidate').filter({hasText:'010-0000-1234'}).first();await first.locator('select').selectOption('partial');
  await page.locator('.document-tab').filter({hasText:'행사 안내.txt'}).locator('button').first().click();
  await page.waitForFunction(()=>{const b=document.querySelector('.file-export>.primary');return !!b&&!b.disabled;},{},{timeout:90000});
  await page.locator('.document-tab').filter({hasText:'동네 모임.txt'}).locator('button').first().click();
  assert.equal(await first.locator('select').inputValue(),'partial');pass('Switching files preserves masking choices');
  await first.getByRole('button',{name:'편집',exact:true}).click();
  assert.equal(await page.locator('.file-choice-editor input').inputValue(),'010-****-1234');
  await page.locator('.file-choice-editor input').fill('공개 연락처 없음');
  await page.locator('.file-choice-editor').getByRole('button',{name:'선택 편집 닫기'}).click();
  await page.getByRole('checkbox',{name:'현재 목록 전체 선택'}).check();
  await page.locator('.bulk-toolbar').getByRole('button',{name:'전체 가림',exact:true}).click();
  const allChoices=await page.locator('.file-candidate select').evaluateAll(xs=>xs.map(x=>x.value));assert.ok(allChoices.every(x=>x==='full'));pass('Visible bulk selection, direct edit, full masking');
  await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await page.screenshot({path:path.join(out,'file-review.png'),fullPage:true});
  await page.getByRole('button',{name:'사본 생성 · 재검사',exact:true}).click();
  await page.locator('.file-export-result').waitFor({timeout:90000});
  await page.getByRole('checkbox',{name:'남은 후보, 이미지 가림 범위, 지원 제한을 확인했습니다.'}).check();
  const event=page.waitForEvent('download');await page.getByRole('button',{name:'사본 다운로드',exact:true}).click();const download=await event;
  const dest=path.join(out,'ui-text-copy.txt');await download.saveAs(dest);const text=fs.readFileSync(dest,'utf8');
  assert.ok(!text.includes('010-0000-1234')&&!text.includes('김민수')&&text.includes('█████'));pass('Copy generation, rescan, review gate, and real download');
  page.once('dialog',d=>d.accept());await page.reload();
  await page.locator('.mode-nav').getByRole('button',{name:'파일 검사',exact:true}).click();
  await page.getByText('현재 앱에 열려 있던 파일을 다시 연결했습니다.',{exact:false}).waitFor();
  assert.equal(await page.locator('.document-tab').count(),2);
  await page.locator('.file-export-result').waitFor();
  assert.equal(await page.getByRole('checkbox',{name:'남은 후보, 이미지 가림 범위, 지원 제한을 확인했습니다.'}).isChecked(),false);
  assert.equal(await page.getByRole('button',{name:'사본 다운로드',exact:true}).isDisabled(),true);
  pass('Reload restores open files and generated copy, with review required again');
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,'file-review-mobile.png'),fullPage:true});pass('390px layout without horizontal overflow');
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('input[type=file]').setInputFiles(path.join(root,'research','document-followup-2026-10-24','originals','identity-image.png'));
  await page.waitForFunction(()=>document.querySelector('.document-title h2')?.textContent==='identity-image.png');
  await page.waitForFunction(()=>{const b=document.querySelector('.file-export>.primary');return !!b&&!b.disabled;},{},{timeout:90000});
  await page.locator('.segmented').getByRole('button',{name:/이미지 · 페이지/}).click();
  await page.locator('.image-canvas img').waitFor();
  await page.locator('.image-canvas').scrollIntoViewIfNeeded();const b=await page.locator('.image-canvas').boundingBox();await page.mouse.move(b.x+b.width*.05,b.y+b.height*.73);await page.mouse.down();await page.mouse.move(b.x+b.width*.9,b.y+b.height*.93);await page.mouse.up();
  await page.locator('.region-box.opaque').waitFor();assert.equal(await page.locator('.region-box.opaque').count(),1);pass('Manual image region selection for OCR misses');
  await page.screenshot({path:path.join(out,'image-review.png'),fullPage:true});
  await page.getByRole('button',{name:'사본 생성 · 재검사',exact:true}).click();await page.locator('.file-export-result').waitFor({timeout:90000});await page.locator('.image-canvas.readonly img').waitFor();
  await page.screenshot({path:path.join(out,'image-copy-preview.png'),fullPage:true});pass('Actual redacted image preview after rescan');
  await page.locator('.doc-remove').first().click();await page.getByRole('dialog').getByRole('button',{name:'계속 검토'}).click();assert.equal(await page.locator('.document-tab').count(),3);
  await page.locator('.doc-remove').first().click();await page.getByRole('dialog').getByRole('button',{name:'제거',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.document-tab').length===2);pass('Remove confirmation and per-file cleanup');
  // Explicitly remove the remaining synthetic jobs; browser close is not server shutdown.
  while(await page.locator('.doc-remove').count()){await page.locator('.doc-remove').first().click();await page.getByRole('dialog').getByRole('button',{name:'제거',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});}
  await page.locator('input[type=file]').setInputFiles(path.join(root,'research','document-followup-2026-10-24','originals','participants.xlsx'));
  await page.getByRole('button',{name:'시트 · 셀',exact:true}).waitFor({timeout:90000});
  await page.waitForFunction(()=>{const b=document.querySelector('.file-export>.primary');return !!b&&!b.disabled;},{},{timeout:90000});
  await page.getByRole('button',{name:'시트 · 셀',exact:true}).click();
  await page.locator('.asset-picker select').selectOption('배포표');
  assert.ok((await page.locator('.sheet-grid').innerText()).includes('24000'));
  await page.screenshot({path:path.join(out,'excel-review.png'),fullPage:true});
  const options=await page.locator('.asset-picker select option').allTextContents();assert.ok(options.length>1);
  await page.locator('.asset-picker select').selectOption(options[1]);
  assert.ok(await page.locator('.sheet-grid .hidden-cell').count()>0);pass('Excel sheet switching, cell addresses, forced calculation result, and hidden cells');
  await page.locator('.doc-remove').first().click();await page.getByRole('dialog').getByRole('button',{name:'제거',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);pass('No JavaScript errors or external requests');

 }finally{if(context&&token)for(const id of created){try{await context.request.post(url+'/api/documents/remove',{headers:{'X-App-Token':token},data:{id}});}catch{}}await browser.close();fs.writeFileSync(path.join(out,'ui-report.json'),JSON.stringify(report,null,2));}
})().catch(e=>{console.error(e);process.exit(1);});
