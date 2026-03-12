// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Sentiment Dashboard', () => {
  test('heatmap grid renders', async ({ page }) => {
    await page.goto('sentimento');
    await page.waitForLoadState('networkidle');

    const table = page.locator('.sentiment-table');
    if ((await table.count()) > 0) {
      await expect(table).toBeVisible();
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }
  });

  test('toggle between Por Tema and Por Fonte', async ({ page }) => {
    await page.goto('sentimento');
    await page.waitForLoadState('networkidle');

    const byTopic = page.getByRole('button', { name: /Por Tema|By Topic/i });
    const bySource = page.getByRole('button', { name: /Por Fonte|By Source/i });

    if ((await bySource.count()) === 0) {
      await expect(page.locator('.feed-state-card')).toBeVisible();
      return;
    }

    await bySource.click();
    await expect(bySource).toHaveClass(/active/);
    await byTopic.click();
    await expect(byTopic).toHaveClass(/active/);
  });

  test('methodology badge is present', async ({ page }) => {
    await page.goto('sentimento');
    await expect(page.locator('.methodology-badge').first()).toBeVisible();     
  });
});


