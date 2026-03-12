const { chromium } = require('playwright');

const BASE_URL = 'http://127.0.0.1:4174/eleicoes-2026-monitor/';

async function runTests() {
  let browser;
  let page;
  const results = [];
  const consoleErrors = [];

  try {
    browser = await chromium.launch();
    page = await browser.newPage();

    // Capture console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Test 1: Home loads without Minified React errors
    console.log('Test 1: Checking home page loads without React errors...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    const reactErrors = consoleErrors.filter(e => e.includes('React') || e.includes('Minified'));
    results.push({
      test: '1. Home loads without Minified React errors',
      pass: reactErrors.length === 0,
      details: reactErrors.length > 0 ? reactErrors : 'No React errors'
    });

    // Test 2: Top nav click on Sentimento changes content
    console.log('Test 2: Checking top nav Sentimento click...');
    const homeContent = await page.textContent('body');
    await page.click('a:has-text("Sentimento"), button:has-text("Sentimento"), [data-testid="sentimento-nav"], nav a:nth-of-type(2)');
    await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(500);
    const sentimentoContent = await page.textContent('body');
    const contentChanged = homeContent !== sentimentoContent;
    results.push({
      test: '2. Sentimento nav changes page content',
      pass: contentChanged,
      details: contentChanged ? 'Content changed' : 'Content unchanged'
    });

    // Go back to home
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    // Test 3: Footer Pesquisas link clickable and polls page renders
    console.log('Test 3: Checking footer Pesquisas link...');
    try {
      await page.click('footer a:has-text("Pesquisas"), a[href*="pesquisas"], a[href*="polls"]');
      await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
      await page.waitForTimeout(500);
      const pesquisasContent = await page.textContent('body');
      const pesquisasLoaded = pesquisasContent && pesquisasContent.length > 0;
      results.push({
        test: '3. Footer Pesquisas link clickable and polls page renders',
        pass: pesquisasLoaded,
        details: pesquisasLoaded ? 'Polls page loaded' : 'Failed to load'
      });
    } catch (e) {
      results.push({
        test: '3. Footer Pesquisas link clickable and polls page renders',
        pass: false,
        details: `Error: ${e.message}`
      });
    }

    // Test 4: Favicon URL returns 200
    console.log('Test 4: Checking favicon URL...');
    const faviconUrl = `${BASE_URL}favicon.ico`;
    const faviconRes = await page.request.head(faviconUrl).catch(() => null);
    results.push({
      test: '4. Favicon URL /eleicoes-2026-monitor/favicon.ico returns 200',
      pass: faviconRes && faviconRes.status() === 200,
      details: faviconRes ? `Status: ${faviconRes.status()}` : 'Request failed'
    });

    // Test 5: Data URL returns 200
    console.log('Test 5: Checking data URL...');
    const dataUrl = `${BASE_URL}data/articles.json`;
    const dataRes = await page.request.get(dataUrl).catch(() => null);
    results.push({
      test: '5. Data URL /eleicoes-2026-monitor/data/articles.json returns 200',
      pass: dataRes && dataRes.status() === 200,
      details: dataRes ? `Status: ${dataRes.status()}` : 'Request failed'
    });

    // Test 6: Home does not contain old phase stub text
    console.log('Test 6: Checking for old phase stub text...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    const pageText = await page.textContent('body');
    const hasOldPhase = /Phase\s*8|Phase\s*11|Phase\s*12|Fase\s*8|Fase\s*11|Fase\s*12/.test(pageText);
    results.push({
      test: '6. Home does not contain old phase stub text',
      pass: !hasOldPhase,
      details: hasOldPhase ? 'Found old phase text' : 'No old phase text found'
    });

    // Print results
    console.log('\n' + '='.repeat(60));
    console.log('VERIFICATION RESULTS');
    console.log('='.repeat(60));
    results.forEach((r) => {
      const status = r.pass ? '✓ PASS' : '✗ FAIL';
      console.log(`${status}: ${r.test}`);
      console.log(`       ${r.details}`);
    });

    // Print any console errors
    if (consoleErrors.length > 0) {
      console.log('\n' + '='.repeat(60));
      console.log('CONSOLE ERRORS DETECTED');
      console.log('='.repeat(60));
      consoleErrors.forEach(e => console.log(`  - ${e}`));
    }

    // Summary
    const passed = results.filter(r => r.pass).length;
    const total = results.length;
    console.log('\n' + '='.repeat(60));
    console.log(`SUMMARY: ${passed}/${total} tests passed`);
    console.log('='.repeat(60));

  } finally {
    if (browser) await browser.close();
  }
}

runTests().catch(console.error);
