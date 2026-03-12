import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = 'http://localhost:4173/eleicoes-2026-monitor';
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
    await page.goto(`${BASE_URL}/sobre/caso-de-uso`, { waitUntil: 'networkidle' });
    
    // Take screenshot
    const screenshotPath1 = path.join(tmpDir, 'after-caso-de-uso.png');
    await page.screenshot({ path: screenshotPath1 });
    console.log(`Screenshot saved: ${screenshotPath1}`);
    
    // Measure layout
    const layoutMetrics = await page.evaluate(() => {
      // Find main content area (usually the widest column)
      const columns = Array.from(document.querySelectorAll('[class*="col"], [class*="grid"], main, article, section'))
        .filter(el => {
          const style = window.getComputedStyle(el);
          return style.display !== 'none' && el.offsetWidth > 200;
        })
        .map(el => ({
          tag: el.tagName,
          class: el.className,
          width: el.offsetWidth,
          display: window.getComputedStyle(el).display
        }))
        .sort((a, b) => b.width - a.width);
      
      return {
        columns,
        bodyWidth: document.body.offsetWidth,
        documentElement: document.documentElement.offsetWidth
      };
    });
    
    console.log('Layout metrics:', JSON.stringify(layoutMetrics, null, 2));
    
    // Layout passes if we have visible columns with reasonable widths
    const mainContentWidth = layoutMetrics.columns[0]?.width || 0;
    const layoutPass = mainContentWidth > 400;
    
    console.log(`Main content width: ${mainContentWidth}px`);
    console.log(`Layout test: ${layoutPass ? '✓ PASS' : '✗ FAIL'}`);
    
    results.push({
      test: 'Layout - /sobre/caso-de-uso',
      pass: layoutPass,
      evidence: `Main content: ${mainContentWidth}px visible (expected >400px)`
    });
    
    // Test 2: /quiz - Navigation and footer visibility
    console.log('\n=== TEST 2: /quiz Visibility ===');
    await page.goto(`${BASE_URL}/quiz`, { waitUntil: 'networkidle' });
    
    const screenshotPath2 = path.join(tmpDir, 'after-quiz.png');
    await page.screenshot({ path: screenshotPath2 });
    console.log(`Screenshot saved: ${screenshotPath2}`);
    
    // Check for nav and footer elements
    const navFooterCheck = await page.evaluate(() => {
      const findNav = () => {
        const nav = document.querySelector('nav');
        const header = document.querySelector('header');
        const topNav = document.querySelector('.top-nav');
        return {
          nav: nav ? { visible: window.getComputedStyle(nav).display !== 'none', tag: 'nav' } : null,
          header: header ? { visible: window.getComputedStyle(header).display !== 'none', tag: 'header' } : null,
          topNav: topNav ? { visible: window.getComputedStyle(topNav).display !== 'none', class: '.top-nav' } : null
        };
      };
      
      const findFooter = () => {
        const footer = document.querySelector('footer');
        const siteFooter = document.querySelector('.site-footer');
        return {
          footer: footer ? { visible: window.getComputedStyle(footer).display !== 'none', tag: 'footer' } : null,
          siteFooter: siteFooter ? { visible: window.getComputedStyle(siteFooter).display !== 'none', class: '.site-footer' } : null
        };
      };
      
      return {
        nav: findNav(),
        footer: findFooter()
      };
    });
    
    console.log('Nav/Footer check:', JSON.stringify(navFooterCheck, null, 2));
    
    // Check if any nav element is visible
    const navVisible = Object.values(navFooterCheck.nav).some(el => el?.visible);
    const footerVisible = Object.values(navFooterCheck.footer).some(el => el?.visible);
    
    console.log(`Navigation visible: ${navVisible ? '✓' : '✗'}`);
    console.log(`Footer visible: ${footerVisible ? '✓' : '✗'}`);
    
    const visibilityPass = navVisible && footerVisible;
    results.push({
      test: 'Visibility - /quiz',
      pass: visibilityPass,
      evidence: `nav visible: ${navVisible}, footer visible: ${footerVisible}`
    });
    
    // Test 3: /candidato/lula - pt-BR bio with accented words
    console.log('\n=== TEST 3: /candidato/lula pt-BR Bio ===');
    await page.goto(`${BASE_URL}/candidato/lula`, { waitUntil: 'networkidle' });
    
    const screenshotPath3 = path.join(tmpDir, 'after-candidato-lula.png');
    await page.screenshot({ path: screenshotPath3 });
    console.log(`Screenshot saved: ${screenshotPath3}`);
    
    const bioContent = await page.evaluate(() => {
      const bodyText = document.body.textContent || '';
      return {
        hasExercicio: bodyText.includes('exercício'),
        hasPreCandidato: bodyText.includes('pré-candidato'),
        hasEleicao: bodyText.includes('eleição'),
        preview: bodyText.substring(0, 300)
      };
    });
    
    console.log('Bio content check:', {
      exercício: bioContent.hasExercicio ? '✓' : '✗',
      'pré-candidato': bioContent.hasPreCandidato ? '✓' : '✗',
      eleição: bioContent.hasEleicao ? '✓' : '✗'
    });
    
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
  console.log('\n' + '='.repeat(50));
  console.log('TEST SUMMARY');
  console.log('='.repeat(50));
  
  const allPass = results.every(r => r.pass);
  
  console.log(`\nOverall Result: ${allPass ? '✓ ALL TESTS PASSED' : '✗ SOME TESTS FAILED'}\n`);
  
  results.forEach((r, i) => {
    console.log(`${i + 1}. ${r.pass ? '✓ PASS' : '✗ FAIL'} - ${r.test}`);
    console.log(`   Evidence: ${r.evidence}\n`);
  });
  
  process.exit(allPass ? 0 : 1);
}

runTests().catch(console.error);
