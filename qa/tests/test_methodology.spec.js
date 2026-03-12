// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Methodology page', () => {
  test('all 5 sections present', async ({ page }) => {
    await page.goto('metodologia');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /Coleta|Collection/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Sumariza[cç][aã]o|Summarization/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Sentimento|Sentiment/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Quiz de Afinidade|Affinity Quiz/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Reportar erros|Report errors/i })).toBeVisible();
  });

  test('language toggle works', async ({ page }) => {
    await page.goto('metodologia');

    await page.getByRole('button', { name: 'EN' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', /en(-US)?/i);
    await expect(page.getByRole('heading', { name: /Methodology/i })).toBeVisible();
  });
});


