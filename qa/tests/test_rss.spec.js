// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('RSS feeds', () => {
  test('feed.xml is valid XML', async ({ request }) => {
    const resp = await request.get('feed.xml');
    expect(resp.status()).toBe(200);
    expect((resp.headers()['content-type'] || '').toLowerCase()).toContain('xml');

    const body = await resp.text();
    expect(body).toMatch(/<\?xml|<rss/i);
    expect(body).toMatch(/<channel>/i);
  });

  test('feed-en.xml is valid XML', async ({ request }) => {
    const resp = await request.get('feed-en.xml');
    expect(resp.status()).toBe(200);
    expect((resp.headers()['content-type'] || '').toLowerCase()).toContain('xml');

    const body = await resp.text();
    expect(body).toMatch(/<\?xml|<rss/i);
    expect(body).toMatch(/<channel>/i);
  });
});


