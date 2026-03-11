// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Quiz full flow', () => {
  test('complete quiz and see result', async ({ page }) => {
    await page.goto('/quiz');
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

      const options = page.locator('.quiz-option-card');
      if ((await options.count()) === 0) {
        break;
      }

      await options.first().click();
      const nextButton = page.locator('.quiz-next-btn');
      await expect(nextButton).toBeEnabled();
      await nextButton.click();
    }

    await expect(page.locator('.quiz-ranking-item').first()).toBeVisible();
    await expect(page.locator('.quiz-share-btn')).toBeVisible();
  });
});


