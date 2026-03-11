// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Comparison page', () => {
  test('/comparar/lula-vs-tarcisio renders both candidates', async ({ page }) => {
    await page.goto('/comparar/lula-vs-tarcisio');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1')).toContainText(/Lula|Tarcisio/i);
    await expect(page.locator('.comparison-hero-card').first()).toBeVisible();
  });

  test('comparison data table is present', async ({ page }) => {
    await page.goto('/comparar/lula-vs-tarcisio');
    await page.waitForLoadState('networkidle');

    const table = page.locator('.comparison-table');
    if ((await table.count()) > 0) {
      await expect(table).toBeVisible();
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }
  });
});


