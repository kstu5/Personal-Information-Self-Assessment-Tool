const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname, '..', '..'),out=path.join(root,'output','ocr-fix-validation');
const url=JSON.parse(fs.readFileSync(path.join(root,'tmp','ocr-fix-ready.json'),'utf8')).url;
const report={checks:[],errors:[]};let context,token,id;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();page.setDefaultTimeout(20000);
  page.on('pageerror',e=>report.errors.push(e.message));const pass=name=>{report.checks.push(name);console.log('PASS',name);};
  await page.goto(url);token=await page.evaluate(()=>JSON.parse(document.querySelector('meta[name=app-boot]').content).token);
  await page.locator('.mode-nav').getByRole('button',{name:'파일 검사',exact:true}).click();
  const uploaded=page.waitForResponse(r=>r.url().includes('/api/documents/upload')&&r.ok());
  await page.locator('input[type=file]').setInputFiles(path.join(root,'research','document-followup-2026-10-24','originals','identity-image.png'));
  id=(await (await uploaded).json()).id;
  await page.waitForFunction(()=>{const b=document.querySelector('.file-export>.primary');return !!b&&!b.disabled;},{},{timeout:90000});
  const phone=page.locator('.file-candidate').filter({hasText:'010-0000-1234'}).first();await phone.locator('select').selectOption('full');
  await phone.locator('.candidate-location').click();await page.locator('.image-canvas img').waitFor();
  const job=await (await context.request.post(url+'/api/documents/status',{headers:{'X-App-Token':token},data:{id}})).json();
  const candidate=job.candidates.find(c=>c.text==='010-0000-1234');const asset=job.manifest.assets.find(a=>a.id===candidate.asset),box=candidate.maskBoxes.full[0];
  const preview=await page.locator('.region-box.suggested').first().evaluate(e=>({left:e.style.left,top:e.style.top,width:e.style.width,height:e.style.height,color:getComputedStyle(e).backgroundColor}));
  assert.ok(Math.abs(parseFloat(preview.left)-box[0]/asset.width*100)<.001);assert.ok(Math.abs(parseFloat(preview.width)-(box[2]-box[0])/asset.width*100)<.001);assert.equal(preview.color,'rgb(0, 0, 0)');pass('Opaque preview uses the exact exporter rectangle');
  await page.getByText('이미지에서 읽은 글자입니다.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'가림 범위 직접 다시 지정',exact:true}).click();assert.equal(await phone.locator('select').inputValue(),'keep');assert.equal(await page.locator('.region-box.suggested').count(),0);pass('Reset automatic masking before manual range correction');
  await phone.locator('select').selectOption('full');
  await page.getByRole('button',{name:'사본 생성 · 재검사',exact:true}).click();await page.locator('.file-export-result').waitFor({timeout:90000});await page.locator('.image-canvas.readonly img').waitFor();
  const response=await context.request.get(url+`/api/documents/${id}/download`,{headers:{'X-App-Token':token}});assert.ok(response.ok());fs.writeFileSync(path.join(out,'phone-masked.png'),await response.body());
  fs.writeFileSync(path.join(out,'phone-mask-geometry.json'),JSON.stringify({box,asset}));pass('Generated PNG is rescanned and its actual preview is shown');
  assert.deepEqual(report.errors,[]);pass('No browser errors');
 }finally{if(context&&token&&id)await context.request.post(url+'/api/documents/remove',{headers:{'X-App-Token':token},data:{id}});await browser.close();fs.writeFileSync(path.join(out,'ui-report.json'),JSON.stringify(report,null,2));}
})().catch(e=>{console.error(e);process.exit(1);});
