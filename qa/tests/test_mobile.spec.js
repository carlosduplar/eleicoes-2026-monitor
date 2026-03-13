// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Mobile layout (390px)', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('BottomNav is visible', async ({ page }) => {
    await page.goto('');
    await expect(page.locator('.bottom-nav')).toBeVisible();
  });

  test('slim mobile header is visible (logo + lang switcher, no nav links)', async ({ page }) => {
    await page.goto('');
    await expect(page.locator('.top-nav')).toBeVisible();
    await expect(page.locator('.top-nav-links')).toBeHidden();
    await expect(page.locator('.top-nav-logo')).toBeVisible();
    await expect(page.locator('.language-switcher')).toBeVisible();
  });

  test('quiz is immersive (no nav)', async ({ page }) => {
    await page.goto('quiz');
    await page.waitForLoadState('networkidle');

    const emptyState = page.getByText(/Quiz temporariamente indisponivel|Quiz temporarily unavailable/i);
    if ((await emptyState.count()) > 0 && (await emptyState.first().isVisible())) {
      await expect(emptyState.first()).toBeVisible();
      return;
    }

    await expect(page.locator('body')).toHaveClass(/quiz-immersive/);
    await expect(page.locator('.bottom-nav')).toBeHidden();
    await expect(page.locator('.top-nav')).toBeHidden();
  });
});


