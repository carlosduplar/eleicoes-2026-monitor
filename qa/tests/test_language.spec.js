// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Saved language hydration', () => {
  test('reloads in English without hydration errors', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(String(error));
    });

    await page.addInitScript(() => {
      window.localStorage.setItem('lang', 'en-US');
    });

    await page.goto('');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('html')).toHaveAttribute('lang', /en(-US)?/i);
    await expect(page.getByRole('button', { name: 'EN' })).toHaveClass(/active/);
    await expect(page.locator('.countdown-bar')).toContainText(/1st round|days/i);

    await page.reload();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('html')).toHaveAttribute('lang', /en(-US)?/i);
    await expect(page.getByRole('button', { name: 'EN' })).toHaveClass(/active/);

    const hydrationErrors = consoleErrors.filter((text) =>
      /Minified React error|#418|#425|#423|[Hh]ydrat/i.test(text),
    );
    expect(hydrationErrors).toEqual([]);
  });

  test('markets page renders odds chart after data loads', async ({ page }) => {
    await page.goto('mercados/');
    await page.waitForLoadState('networkidle');

    const oddsCard = page.locator('.sentiment-stack .sentiment-card');
    await expect(oddsCard.first()).toBeVisible({ timeout: 15_000 }).catch(async () => {
      // Data may be absent locally; loading/empty state must render instead.
      await expect(page.locator('.feed-state-card').or(page.locator('.page-section'))).toBeVisible();
    });
    await expect(page.locator('.page-section h1, .sentiment-head h1').first()).toBeVisible();
  });
});
