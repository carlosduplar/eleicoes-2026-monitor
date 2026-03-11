// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Candidate page', () => {
  test('/candidato/lula renders profile', async ({ page }) => {
    await page.goto('/candidato/lula');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1')).toContainText(/Lula/i);
  });

  test('JSON-LD structured data present', async ({ page }) => {
    await page.goto('/candidato/lula');
    await page.waitForLoadState('networkidle');

    const jsonLdScripts = page.locator('script[type="application/ld+json"]');
    expect(await jsonLdScripts.count()).toBeGreaterThan(0);

    const scriptContents = await jsonLdScripts.allTextContents();
    expect(
      scriptContents.some(
        (content) => content.includes('"@type"') && (content.includes('Person') || content.includes('ProfilePage')),
      ),
    ).toBeTruthy();
  });

  test('methodology badge is present', async ({ page }) => {
    await page.goto('/candidato/lula');
    await expect(page.locator('.methodology-badge').first()).toBeVisible();
  });
});


