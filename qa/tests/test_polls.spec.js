// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Polls page', () => {
  test('chart renders', async ({ page }) => {
    await page.goto('pesquisas');
    await page.waitForLoadState('networkidle');

    const chart = page.locator('.recharts-responsive-container');
    if ((await chart.count()) > 0) {
      await expect(chart.first()).toBeVisible();
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }
  });

  test('institute filter is present', async ({ page }) => {
    await page.goto('pesquisas');
    await page.waitForLoadState('networkidle');

    const filter = page.locator('#poll-institute-filter');
    if ((await filter.count()) > 0) {
      await expect(filter).toBeVisible();
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }
  });

  test('methodology badge is present', async ({ page }) => {
    await page.goto('pesquisas');
    await expect(page.locator('.methodology-badge').first()).toBeVisible();     
  });
});


