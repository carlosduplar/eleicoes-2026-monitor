import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = 'http://localhost:4173';
const tmpDir = path.join(process.cwd(), '..', 'tmp_test_manual');

if (!fs.existsSync(tmpDir)) {
  fs.mkdirSync(tmpDir, { recursive: true });
}

async function runTests() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const results = [];
  
  try {
    // Test 1: /sobre/caso-de-uso - Layout verification
    console.log('\n=== TEST 1: /sobre/caso-de-uso Layout ===');
    await page.goto(`${BASE_URL}/sobre/caso-de-uso`);
    await page.waitForLoadState('networkidle');
    
    // Take screenshot
    const screenshotPath1 = path.join(tmpDir, 'after-caso-de-uso.png');
    await page.screenshot({ path: screenshotPath1 });
    console.log(`Screenshot saved: ${screenshotPath1}`);
    
    // Inspect page structure
    const layout = await page.evaluate(() => {
      // Look for main content and sidebar
      const main = document.querySelector('main');
      const aside = document.querySelector('aside');
      const container = document.querySelector('[class*="container"]') || document.querySelector('[class*="grid"]');
      
      return {
        main: main ? { width: main.offsetWidth, class: main.className } : null,
        aside: aside ? { width: aside.offsetWidth, class: aside.className } : null,
        container: container ? { width: container.offsetWidth, class: container.className } : null,
        bodyContent: document.body.innerHTML.substring(0, 500)
      };
    });
    
    console.log('Layout analysis:', JSON.stringify(layout, null, 2));
    
    // Check for content/toc pattern more broadly
    const layoutMetrics = await page.evaluate(() => {
      const columns = document.querySelectorAll('div[class*="col"], div[class*="column"], div[class*="grid"], section, article');
      const metrics = [];
      columns.forEach(col => {
        if (col.offsetWidth > 100) {
          metrics.push({
            selector: col.className || col.tagName,
            width: col.offsetWidth,
            display: window.getComputedStyle(col).display
          });
        }
      });
      return metrics;
    });
    
    console.log('Column metrics:', JSON.stringify(layoutMetrics, null, 2));
    
    const layoutPass = layoutMetrics.length > 0;
    results.push({
      test: 'Layout - /sobre/caso-de-uso',
      pass: layoutPass,
      evidence: `Columns detected: ${layoutMetrics.length}, largest: ${layoutMetrics[0]?.width || 'none'}px`
    });
    
    // Test 2: /quiz - Navigation and footer visibility
    console.log('\n=== TEST 2: /quiz Visibility ===');
    await page.goto(`${BASE_URL}/quiz`);
    await page.waitForLoadState('networkidle');
    
    const screenshotPath2 = path.join(tmpDir, 'after-quiz.png');
    await page.screenshot({ path: screenshotPath2 });
    console.log(`Screenshot saved: ${screenshotPath2}`);
    
    const navElements = await page.evaluate(() => {
      return {
        topNav: {
          found: !!document.querySelector('.top-nav'),
          display: document.querySelector('.top-nav')?.style?.display || window.getComputedStyle(document.querySelector('.top-nav') || {}).display,
          alternatives: [
            !!document.querySelector('nav'),
            !!document.querySelector('header nav'),
            !!document.querySelector('[role="navigation"]')
          ].filter(Boolean).length
        },
        footer: {
          found: !!document.querySelector('.site-footer'),
          display: document.querySelector('.site-footer')?.style?.display || window.getComputedStyle(document.querySelector('.site-footer') || {}).display,
          alternatives: [
            !!document.querySelector('footer'),
            !!document.querySelector('[role="contentinfo"]')
          ].filter(Boolean).length
        }
      };
    });
    
    console.log('Nav elements:', JSON.stringify(navElements, null, 2));
    
    // Check for generic nav/footer
    const navFooter = await page.evaluate(() => {
      const nav = document.querySelector('nav') || document.querySelector('[role="navigation"]');
      const footer = document.querySelector('footer') || document.querySelector('[role="contentinfo"]');
      return {
        navVisible: nav ? window.getComputedStyle(nav).display !== 'none' : false,
        footerVisible: footer ? window.getComputedStyle(footer).display !== 'none' : false,
        navDisplay: nav ? window.getComputedStyle(nav).display : 'not-found',
        footerDisplay: footer ? window.getComputedStyle(footer).display : 'not-found'
      };
    });
    
    console.log('Generic nav/footer:', JSON.stringify(navFooter, null, 2));
    
    const visibilityPass = navFooter.navVisible && navFooter.footerVisible;
    results.push({
      test: 'Visibility - /quiz',
      pass: visibilityPass,
      evidence: `nav: ${navFooter.navDisplay}, footer: ${navFooter.footerDisplay}`
    });
    
    // Test 3: /candidato/lula - pt-BR bio with accented words
    console.log('\n=== TEST 3: /candidato/lula pt-BR Bio ===');
    await page.goto(`${BASE_URL}/candidato/lula`);
    await page.waitForLoadState('networkidle');
    
    const screenshotPath3 = path.join(tmpDir, 'after-candidato-lula.png');
    await page.screenshot({ path: screenshotPath3 });
    console.log(`Screenshot saved: ${screenshotPath3}`);
    
    const bioContent = await page.evaluate(() => {
      const body = document.body.textContent || '';
      return {
        hasExercicio: body.includes('exercício'),
        hasPreCandidato: body.includes('pré-candidato'),
        hasEleicao: body.includes('eleição'),
        preview: body.substring(0, 500)
      };
    });
    
    console.log('Bio content check:', JSON.stringify(bioContent, null, 2));
    
    const bioPass = bioContent.hasExercicio && bioContent.hasPreCandidato && bioContent.hasEleicao;
    results.push({
      test: 'Content - /candidato/lula pt-BR',
      pass: bioPass,
      evidence: `exercício: ${bioContent.hasExercicio ? '✓' : '✗'}, pré-candidato: ${bioContent.hasPreCandidato ? '✓' : '✗'}, eleição: ${bioContent.hasEleicao ? '✓' : '✗'}`
    });
    
  } catch (error) {
    console.error('Test error:', error);
    results.push({
      test: 'Error',
      pass: false,
      evidence: error.message
    });
  } finally {
    await browser.close();
  }
  
  // Print summary
  console.log('\n=== TEST SUMMARY ===');
  const allPass = results.every(r => r.pass);
  console.log(`Overall: ${allPass ? '✓ ALL PASS' : '✗ SOME FAILED'}`);
  console.log('\nDetails:');
  results.forEach(r => {
    console.log(`${r.pass ? '✓' : '✗'} ${r.test}`);
    console.log(`  Evidence: ${r.evidence}`);
  });
  
  process.exit(allPass ? 0 : 1);
}

runTests().catch(console.error);
