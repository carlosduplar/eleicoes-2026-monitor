// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Home page', () => {
  test('feed renders article cards', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const cards = page.locator('.feed-card');
    if ((await cards.count()) > 0) {
      await expect(cards.first()).toBeVisible();
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }
  });

  test('language toggle switches to English', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'EN' }).click();

    await expect(page.locator('html')).toHaveAttribute('lang', /en(-US)?/i);
    await expect(page.getByRole('link', { name: /News|Noticias/i }).first()).toBeVisible();
  });

  test('countdown timer is visible', async ({ page }) => {
    await page.goto('/');

    await expect(page.locator('.countdown-bar')).toBeVisible();
    await expect(page.locator('.countdown-bar')).toContainText('2026');
  });

  test('source filter buttons are present', async ({ page }) => {
    await page.goto('/');

    const filters = page.locator('.source-filter-button');
    await expect(filters.first()).toBeVisible();
    expect(await filters.count()).toBeGreaterThanOrEqual(3);
  });
});


