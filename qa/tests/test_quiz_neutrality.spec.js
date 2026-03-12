// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

const CANDIDATE_SLUGS = [
  'lula',
  'flavio-bolsonaro',
  'tarcisio',
  'caiado',
  'zema',
  'ratinho-jr',
  'eduardo-leite',
  'aldo-rebelo',
  'renan-santos',
];

test.describe('Quiz neutrality', () => {
  test('no candidate slug visible during questions', async ({ page }) => {
    await page.goto('quiz');
    await page.waitForLoadState('networkidle');

    const emptyState = page.getByText(/Quiz temporariamente indisponivel|Quiz temporarily unavailable/i);
    if ((await emptyState.count()) > 0 && (await emptyState.first().isVisible())) {
      await expect(emptyState.first()).toBeVisible();
      return;
    }

    for (let step = 0; step < 20; step += 1) {
      if ((await page.locator('.quiz-ranking-item').count()) > 0) {
        break;
      }

      const questionText = (await page.locator('main').innerText()).toLowerCase();

      for (const slug of CANDIDATE_SLUGS) {
        expect(questionText).not.toContain(slug);
      }
      expect(questionText).not.toMatch(/\bsource_pt\b|\bsource_en\b/i);
      expect(questionText).not.toMatch(/\btrecho\s*\d+\b|\bsnippet\s*\d+\b/i);

      const options = page.locator('.quiz-option-card');
      if ((await options.count()) === 0) {
        break;
      }
      await options.first().click();
      await page.locator('.quiz-next-btn').click();
    }
  });
});


