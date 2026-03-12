import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = 'http://localhost:4173';
const tmpDir = path.join(process.cwd(), '..', 'tmp_test_manual');

// Ensure tmp_test_manual directory exists
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
    
    // Get content column and toc widths
    const contentWidth = await page.evaluate(() => {
      const elem = document.querySelector('main') || document.querySelector('[role="main"]');
      if (elem) return elem.offsetWidth;
      return null;
    });
    
    const tocWidth = await page.evaluate(() => {
      const elem = document.querySelector('aside') || document.querySelector('[role="complementary"]');
      if (elem) return elem.offsetWidth;
      return null;
    });
    
    console.log(`Content width: ${contentWidth}px`);
    console.log(`TOC/Aside width: ${tocWidth}px`);
    
    const layoutPass = contentWidth > tocWidth || (contentWidth && contentWidth > 600);
    console.log(`Layout test: ${layoutPass ? '✓ PASS' : '✗ FAIL'} (content > toc)`);
    
    results.push({
      test: 'Layout - /sobre/caso-de-uso',
      pass: layoutPass,
      evidence: `Content: ${contentWidth}px, TOC: ${tocWidth}px`
    });
    
    // Test 2: /quiz - Navigation and footer visibility
    console.log('\n=== TEST 2: /quiz Visibility ===');
    await page.goto(`${BASE_URL}/quiz`);
    await page.waitForLoadState('networkidle');
    
    const screenshotPath2 = path.join(tmpDir, 'after-quiz.png');
    await page.screenshot({ path: screenshotPath2 });
    console.log(`Screenshot saved: ${screenshotPath2}`);
    
    const topNavDisplay = await page.evaluate(() => {
      const elem = document.querySelector('.top-nav');
      if (!elem) return 'not-found';
      return window.getComputedStyle(elem).display;
    });
    
    const footerDisplay = await page.evaluate(() => {
      const elem = document.querySelector('.site-footer');
      if (!elem) return 'not-found';
      return window.getComputedStyle(elem).display;
    });
    
    console.log(`.top-nav display: ${topNavDisplay}`);
    console.log(`.site-footer display: ${footerDisplay}`);
    
    const topNavPass = topNavDisplay !== 'none' && topNavDisplay !== 'not-found';
    const footerPass = footerDisplay !== 'none' && footerDisplay !== 'not-found';
    const visibilityPass = topNavPass && footerPass;
    
    console.log(`.top-nav visible: ${topNavPass ? '✓' : '✗'}`);
    console.log(`.site-footer visible: ${footerPass ? '✓' : '✗'}`);
    console.log(`Visibility test: ${visibilityPass ? '✓ PASS' : '✗ FAIL'}`);
    
    results.push({
      test: 'Visibility - /quiz',
      pass: visibilityPass,
      evidence: `.top-nav: ${topNavDisplay}, .site-footer: ${footerDisplay}`
    });
    
    // Test 3: /candidato/lula - pt-BR bio with accented words
    console.log('\n=== TEST 3: /candidato/lula pt-BR Bio ===');
    await page.goto(`${BASE_URL}/candidato/lula`);
    await page.waitForLoadState('networkidle');
    
    const screenshotPath3 = path.join(tmpDir, 'after-candidato-lula.png');
    await page.screenshot({ path: screenshotPath3 });
    console.log(`Screenshot saved: ${screenshotPath3}`);
    
    const bioText = await page.evaluate(() => {
      // Try to find bio content
      const bioElements = document.querySelectorAll('p, div[class*="bio"], div[class*="description"]');
      let text = '';
      for (let elem of bioElements) {
        text += elem.textContent + ' ';
      }
      return text;
    });
    
    console.log(`Bio text preview: ${bioText.substring(0, 200)}...`);
    
    const hasExercicio = bioText.includes('exercício');
    const hasPreCandidato = bioText.includes('pré-candidato');
    const hasEleicao = bioText.includes('eleição');
    
    console.log(`Contains "exercício": ${hasExercicio ? '✓' : '✗'}`);
    console.log(`Contains "pré-candidato": ${hasPreCandidato ? '✓' : '✗'}`);
    console.log(`Contains "eleição": ${hasEleicao ? '✓' : '✗'}`);
    
    const bioPass = hasExercicio && hasPreCandidato && hasEleicao;
    console.log(`Bio content test: ${bioPass ? '✓ PASS' : '✗ FAIL'}`);
    
    results.push({
      test: 'Content - /candidato/lula pt-BR',
      pass: bioPass,
      evidence: `exercício: ${hasExercicio ? '✓' : '✗'}, pré-candidato: ${hasPreCandidato ? '✓' : '✗'}, eleição: ${hasEleicao ? '✓' : '✗'}`
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
