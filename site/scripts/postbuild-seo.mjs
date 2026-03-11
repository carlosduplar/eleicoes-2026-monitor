import fs from 'node:fs';
import path from 'node:path';

const DIST_DIR = path.resolve(process.cwd(), 'dist');
const BRAND = 'Portal Eleicoes BR 2026';
const BASE_DESCRIPTION = 'Portal bilingue para monitoramento de noticias, sentimento e pesquisas das eleicoes BR 2026.';
const CANONICAL_BASE = 'https://eleicoes2026.com.br';

function collectHtmlFiles(dirPath) {
  /** @type {string[]} */
  const files = [];
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    const absolutePath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectHtmlFiles(absolutePath));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith('.html')) {
      files.push(absolutePath);
    }
  }
  return files;
}

function toNameFromSlug(value) {
  return value
    .split('-')
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

function toRoutePath(filePath) {
  const relative = path.relative(DIST_DIR, filePath).replace(/\\/g, '/');
  if (relative === 'index.html') {
    return '/';
  }
  return `/${relative.replace(/\/index\.html$/, '')}`;
}

function getSeoMeta(routePath) {
  const defaultMeta = {
    title: `${BRAND} | ${routePath}`,
    description: `${BRAND} - ${routePath}`,
  };

  if (routePath === '/') {
    return { title: BRAND, description: BASE_DESCRIPTION };
  }

  if (routePath === '/sentimento') {
    return {
      title: `Sentimento dos Candidatos | ${BRAND}`,
      description: `Sentimento dos Candidatos - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/pesquisas') {
    return {
      title: `Pesquisas Eleitorais | ${BRAND}`,
      description: `Pesquisas Eleitorais - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/quiz') {
    return {
      title: `Quiz de Afinidade Politica | ${BRAND}`,
      description: `Quiz de Afinidade Politica - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/quiz/resultado') {
    return {
      title: `Seu perfil politico | ${BRAND}`,
      description: `Seu perfil politico - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/metodologia') {
    return {
      title: `Metodologia | ${BRAND}`,
      description: `Metodologia - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/candidatos') {
    return {
      title: `Candidatos | ${BRAND}`,
      description: `Candidatos - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath === '/sobre/caso-de-uso') {
    return {
      title: `Caso de Uso | ${BRAND}`,
      description: `Caso de Uso - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath.startsWith('/candidato/')) {
    const slug = routePath.replace('/candidato/', '');
    const candidateName = toNameFromSlug(slug);
    return {
      title: `${candidateName} | Candidatos | ${BRAND}`,
      description: `${candidateName} - ${BASE_DESCRIPTION}`,
    };
  }

  if (routePath.startsWith('/comparar/')) {
    const pair = routePath.replace('/comparar/', '');
    const [left, right] = pair.split('-vs-');
    const leftName = toNameFromSlug(left || '');
    const rightName = toNameFromSlug(right || '');
    const label = leftName && rightName ? `${leftName} vs ${rightName}` : toNameFromSlug(pair);
    return {
      title: `${label} | Comparacao | ${BRAND}`,
      description: `${label} - ${BASE_DESCRIPTION}`,
    };
  }

  return defaultMeta;
}

function upsertTag(html, pattern, replacement, insertBefore) {
  if (pattern.test(html)) {
    return html.replace(pattern, replacement);
  }
  const marker = html.includes(insertBefore) ? insertBefore : '</head>';
  return html.replace(marker, `${replacement}\n${marker}`);
}

function applySeo(filePath) {
  const routePath = toRoutePath(filePath);
  const { title, description } = getSeoMeta(routePath);
  const canonicalUrl = `${CANONICAL_BASE}${routePath === '/' ? '' : routePath}`;
  let html = fs.readFileSync(filePath, 'utf8');

  html = upsertTag(html, /<title>[\s\S]*?<\/title>/i, `<title>${title}</title>`, '</head>');
  html = upsertTag(
    html,
    /<meta\s+name="description"\s+content="[^"]*"\s*\/?>/i,
    `<meta name="description" content="${description}" />`,
    '</head>',
  );
  html = upsertTag(
    html,
    /<link\s+rel="canonical"\s+href="[^"]*"\s*\/?>/i,
    `<link rel="canonical" href="${canonicalUrl}" />`,
    '</head>',
  );
  html = upsertTag(
    html,
    /<meta\s+property="og:title"\s+content="[^"]*"\s*\/?>/i,
    `<meta property="og:title" content="${title}" />`,
    '</head>',
  );
  html = upsertTag(
    html,
    /<meta\s+property="og:description"\s+content="[^"]*"\s*\/?>/i,
    `<meta property="og:description" content="${description}" />`,
    '</head>',
  );

  fs.writeFileSync(filePath, html, 'utf8');
}

if (fs.existsSync(DIST_DIR)) {
  for (const filePath of collectHtmlFiles(DIST_DIR)) {
    applySeo(filePath);
  }
}

