// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

const CANDIDATE_SLUGS = [
  'lula',
  'flavio-bolsonaro',
  'renan-santos',
  'caiado',
  'augusto-cury',
  'zema',
  'edmilson-costa',
  'hertz-dias',
  'samara-martins',
  'wilson-grassi',
  'clariana-barao',
  'rui-costa-pimenta',
  'pablo-marcal',
];

test.describe('Quiz neutrality', () => {
  test('no candidate slug visible during questions', async ({ page }) => {
    await page.goto('quiz');
    await page.waitForLoadState('networkidle');

    const emptyState = page.getByText(/Quiz temporariamente indisponivel|Quiz temporarily unavailable/i);
    if ((await emptyState.count()) > 0 && (await emptyState.first().isVisible())) {
      await expect(emptyState.first()).toBeVisible();
      return;
    }

    for (let step = 0; step < 20; step += 1) {
      if ((await page.locator('.quiz-ranking-item').count()) > 0) {
        break;
      }

      const questionText = (await page.locator('main').innerText()).toLowerCase();

      for (const slug of CANDIDATE_SLUGS) {
        expect(questionText).not.toContain(slug);
      }
      expect(questionText).not.toMatch(/\bsource_pt\b|\bsource_en\b/i);
      expect(questionText).not.toMatch(/\btrecho\s*\d+\b|\bsnippet\s*\d+\b/i);

      const options = page.locator('.quiz-option-card');
      if ((await options.count()) === 0) {
        break;
      }
      await options.first().click();
      await page.locator('.quiz-next-btn').click();
    }
  });

  test('options carry no identity leaks or template tells', async ({ page }) => {
    await page.goto('quiz');
    await page.waitForLoadState('networkidle');

    const emptyState = page.getByText(/Quiz temporariamente indisponivel|Quiz temporarily unavailable/i);
    if ((await emptyState.count()) > 0 && (await emptyState.first().isVisible())) {
      return;
    }

    const firstNames = [
      'ronaldo',
      'flávio',
      'flavio',
      'romeu',
      'renan',
      'augusto',
      'edmilson',
      'hertz',
      'samara',
      'wilson',
      'clariana',
      'pimenta',
      'pablo',
      'marçal',
      'marcal',
    ];
    const bioTerms = [
      'ibama',
      'fundo amaz',
      'prouni',
      'fies',
      'cop30',
      'excludente de ilicitude',
      'maioridade penal',
      'pena de morte',
    ];

    for (let step = 0; step < 20; step += 1) {
      if ((await page.locator('.quiz-ranking-item').count()) > 0) {
        break;
      }
      const options = page.locator('.quiz-option-card');
      const count = await options.count();
      if (count === 0) {
        break;
      }
      const texts = await options.allInnerTexts();
      const joined = texts.join('\n').toLowerCase();

      for (const name of firstNames) {
        expect(joined).not.toContain(name);
      }
      for (const term of bioTerms) {
        expect(joined).not.toContain(term);
      }
      expect(joined).not.toMatch(/ponto central|central point/);
      expect(joined).not.toMatch(/o pol.tico|the politician/);
      expect(joined).not.toMatch(/n.o h. informa..es suficientes|not enough information/);
      expect(joined).not.toMatch(/como promulgado|como governador/);

      const tailHits = texts.filter((text) =>
        /metas transparentes e revis.o peri.dica|transparent goals and periodic review/i.test(text),
      );
      expect(tailHits.length).toBeLessThanOrEqual(1);

      await options.first().click();
      await page.locator('.quiz-next-btn').click();
    }
  });
});


