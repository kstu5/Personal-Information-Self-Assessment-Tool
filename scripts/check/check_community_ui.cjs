const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..', '..');
const dir = path.join(root, 'output', 'community-review');
const report = JSON.parse(fs.readFileSync(path.join(dir, 'community-evaluation.json'), 'utf8'));
const url = JSON.parse(fs.readFileSync(path.join(root, 'tmp', 'community-ready.json'), 'utf8')).url;
const screenshots = path.join(root, 'tmp', 'community-ui');
fs.mkdirSync(screenshots, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
  const outcome = { cases: [], errors: [], externalRequests: [], scope: 'Production React build and actual local detector. Only the OS file chooser is replaced; file bytes are read from the provided .piipost files.' };
  try {
    for (const c of report.cases) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 1080 }, deviceScaleFactor: 1 });
      const content = fs.readFileSync(path.join(dir, c.inputFile), 'utf8');
      await context.addInitScript(({ content, name }) => {
        window.showOpenFilePicker = async () => [{ name, async getFile() { return new File([content], name); } }];
      }, { content, name: c.inputFile });
      const page = await context.newPage();
      page.on('pageerror', error => outcome.errors.push(error.message));
      page.on('request', request => { if (!request.url().startsWith(url + '/') && !request.url().startsWith('data:')) outcome.externalRequests.push(request.url()); });
      await page.goto(url);await page.locator('.mode-nav').getByRole('button',{name:'게시글 검사',exact:true}).click();
      await page.getByRole('button', { name: '저장한 글 불러오기' }).click();
      await page.locator('#post-title').waitFor();
      assert.equal(await page.locator('#post-title').inputValue(), c.title);
      assert.equal(await page.locator('#post-body').inputValue(), c.body);
      const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/check'));
      await page.getByRole('button', { name: '개인정보 검사', exact: true }).click();
      const apiResult = await (await responsePromise).json();
      await page.locator('.dashboard').waitFor({ timeout: 30000 });
      assert.deepEqual(apiResult.candidates, c.actual);
      assert.equal(await page.locator('.post h2').textContent(), c.title);
      assert.equal(await page.locator('.post-body').textContent(), c.body);
      assert.equal(await page.locator('.marker').count(), c.counts.candidates);
      assert.equal(await page.locator('.candidate-row').count(), c.counts.candidates);
      assert.equal(Number(await page.locator('.total>strong').textContent()), c.counts.candidates);
      for (const item of c.actual) {
        const marker = page.locator(`[id="candidate-${item.id}"]`);
        assert.equal(await marker.textContent(), item.text);
        assert.ok((await marker.getAttribute('class')).includes('risk-' + item.risk));
      }
      await page.screenshot({ path: path.join(screenshots, c.id + '.png'), fullPage: true });
      const lastRow = page.locator('.candidate-row').last();
      const originalIndex = Number(await lastRow.locator('.candidate-number').textContent()) - 1;
      await lastRow.click();
      assert.equal(await page.evaluate(() => document.activeElement.id), 'candidate-' + c.actual[originalIndex].id);
      assert.ok(await page.getByText(/자동 검사는 개인정보를 잘못 표시하거나 놓칠 수 있습니다/).isVisible());
      outcome.cases.push({ id: c.id, inputFile: c.inputFile, candidates: c.counts.candidates, fileContentsRestored: true, apiMatchesEvaluation: true, originalTextPreserved: true, markerListAndCountMatch: true, riskColorClassesMatch: true, candidateNavigation: true, reviewNoticeVisible: true });
      console.log('PASS', c.id, c.counts.candidates);
      await context.close();
    }
    assert.deepEqual(outcome.errors, []);
    assert.deepEqual(outcome.externalRequests, []);
  } catch (error) {
    outcome.errors.push(String(error));
    throw error;
  } finally {
    fs.writeFileSync(path.join(dir, 'ui-verification.json'), JSON.stringify(outcome, null, 2));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
