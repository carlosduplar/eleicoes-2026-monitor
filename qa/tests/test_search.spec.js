// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Search feature', () => {
  test('search input is present on the homepage', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    await expect(searchInput).toBeVisible();
    await expect(searchInput).toHaveAttribute('aria-label', /.+/);
  });

  test('typing a query filters articles (local fallback)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    const initialCount = await page.locator('.feed-card').count();

    await searchInput.fill('lula');
    await page.waitForTimeout(500);

    const filteredCount = await page.locator('.feed-card').count();
    const noResultsVisible = await page
      .getByText(/Nenhum resultado encontrado para|No results found for/i)
      .isVisible();

    expect(filteredCount <= initialCount || noResultsVisible).toBeTruthy();
    await expect(page.getByText(/Busca local|Local search/)).toBeVisible();
  });

  test('empty query restores full article list', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    const initialCount = await page.locator('.feed-card').count();

    await searchInput.fill('lula');
    await page.waitForTimeout(500);

    await searchInput.fill('');
    await page.waitForTimeout(500);

    const restoredCount = await page.locator('.feed-card').count();
    if (initialCount > 0) {
      expect(restoredCount).toBe(initialCount);
    } else {
      await expect(page.locator('.feed-state-card')).toBeVisible();
    }

    await expect(page.getByText(/Busca local|Local search/)).toHaveCount(0);
    await expect(page.getByText(/Busca semantica|Semantic search/)).toHaveCount(0);
  });

  test('isVertexSearch false shows local badge when Vertex URL not set', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    await searchInput.fill('eleicoes');
    await page.waitForTimeout(500);

    await expect(page.getByText(/Busca local|Local search/)).toBeVisible();
    await expect(page.getByText(/Busca semantica|Semantic search/)).toHaveCount(0);
  });

  test('search input has correct placeholder text', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    await expect(searchInput).toHaveAttribute('placeholder', 'Buscar noticias...');

    await page.getByRole('button', { name: 'EN' }).click();
    await expect(searchInput).toHaveAttribute('placeholder', 'Search news...');
  });

  test('no results shows appropriate message', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[type="search"]');
    await searchInput.fill('xyznonexistent123');
    await page.waitForTimeout(500);

    const cardCount = await page.locator('.feed-card').count();
    const noResultsVisible = await page
      .getByText(/Nenhum resultado encontrado para|No results found for/i)
      .isVisible();

    expect(cardCount === 0 || noResultsVisible).toBeTruthy();
  });
});
