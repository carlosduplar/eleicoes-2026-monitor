import { useEffect, useMemo, useState } from 'react';
import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { marked } from 'marked';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

function escapeHtmlAttr(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function sanitizeUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return '';
  }
  if (rawUrl.startsWith('#') || rawUrl.startsWith('/')) {
    return rawUrl;
  }
  try {
    const parsed = new URL(rawUrl, 'https://eleicoes2026.com.br');
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'mailto:' || parsed.protocol === 'tel:') {
      return rawUrl;
    }
  } catch {
    return '';
  }
  return '';
}

const markedRenderer = new marked.Renderer();
markedRenderer.heading = function heading({ tokens, depth }) {
  const text = this.parser.parseInline(tokens);
  if (depth === 2 || depth === 3) {
    const id = slugify(text);
    return `<h${depth} id="${id}">${text}</h${depth}>`;
  }
  return `<h${depth}>${text}</h${depth}>`;
};
markedRenderer.html = function html() {
  return '';
};
markedRenderer.link = function link({ href, title, tokens }) {
  const safeHref = sanitizeUrl(href);
  const text = this.parser.parseInline(tokens);
  if (!safeHref) {
    return text;
  }
  const titleAttr = title ? ` title="${escapeHtmlAttr(title)}"` : '';
  const isExternal = /^https?:\/\//i.test(safeHref);
  const relAttr = isExternal ? ' rel="noopener noreferrer"' : '';
  const targetAttr = isExternal ? ' target="_blank"' : '';
  return `<a href="${escapeHtmlAttr(safeHref)}"${titleAttr}${relAttr}${targetAttr}>${text}</a>`;
};
markedRenderer.image = function image({ href, title, text }) {
  const safeSrc = sanitizeUrl(href);
  if (!safeSrc) {
    return '';
  }
  const titleAttr = title ? ` title="${escapeHtmlAttr(title)}"` : '';
  const altText = escapeHtmlAttr(text || '');
  return `<img src="${escapeHtmlAttr(safeSrc)}" alt="${altText}"${titleAttr} loading="lazy" />`;
};
marked.use({ renderer: markedRenderer });

function extractHeadings(markdown) {
  const headingRegex = /^##\s+(.+)$/gm;
  const headings = [];
  let match = headingRegex.exec(markdown);
  while (match) {
    const text = match[1].trim();
    headings.push({
      id: slugify(text),
      text,
      level: 2,
    });
    match = headingRegex.exec(markdown);
  }
  return headings;
}

function useMarkdownContent(language) {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}case-study/${language}.md`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const markdown = await response.text();
        setContent(markdown);
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        setError(fetchError);
        setContent(null);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      controller.abort();
    };
  }, [language]);

  return { content, loading, error };
}

function calculateReadingTime(text) {
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(wordCount / 200));
}

function CaseStudyPage() {
  const { t, i18n } = useTranslation('case-study');
  const { t: tCommon } = useTranslation('common');
  const language = i18n.language === 'en-US' ? 'en-US' : 'pt-BR';
  const { content, loading, error } = useMarkdownContent(language);

  const headings = useMemo(() => {
    if (!content) {
      return [];
    }
    return extractHeadings(content);
  }, [content]);

  const fallbackHeadings = useMemo(() => {
    const sectionNames = t('sections', { returnObjects: true });
    if (!sectionNames || Array.isArray(sectionNames) || typeof sectionNames !== 'object') {
      return [];
    }
    return Object.values(sectionNames).map((section) => ({
      id: slugify(section),
      text: section,
      level: 2,
    }));
  }, [t, i18n.language]);

  const tocItems = headings.length > 0 ? headings : fallbackHeadings;
  const html = useMemo(() => (content ? String(marked.parse(content)) : ''), [content]);
  const readingMinutes = useMemo(() => (content ? calculateReadingTime(content) : 0), [content]);
  const [updatedDate, setUpdatedDate] = useState('');

  useEffect(() => {
    setUpdatedDate(new Date().toLocaleDateString(language));
  }, [language]);
  const caseStudyJsonLd = useMemo(
    () => ({
      '@context': 'https://schema.org',
      '@type': 'TechArticle',
      headline: t('title'),
      description: t('subtitle'),
      url: 'https://eleicoes2026.com.br/sobre/caso-de-uso',
      author: { '@type': 'Organization', name: 'carlosduplar' },
      inLanguage: i18n.language,
    }),
    [i18n.language, t],
  );
  const jsonLdText = JSON.stringify(caseStudyJsonLd);

  return (
    <article className="case-study-page">
      <Helmet>
        <title>{`${t('title')} | ${tCommon('brand')}`}</title>
        <script type="application/ld+json">{jsonLdText}</script>
      </Helmet>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdText }} />

      <nav className="case-study-breadcrumb" aria-label={t('breadcrumb_case_study')}>
        <Link to="/">{t('breadcrumb_home')}</Link>
        <span>&gt;</span>
        <span>{t('breadcrumb_about')}</span>
        <span>&gt;</span>
        <span>{t('breadcrumb_case_study')}</span>
      </nav>

      <header className="case-study-header">
        <h1>{t('title')}</h1>
        <p className="case-study-subtitle">{t('subtitle')}</p>
        <div className="case-study-meta">
          {!loading && !error && <span>{t('reading_time', { minutes: readingMinutes })}</span>}
          <span>{t('last_updated', { date: updatedDate || '--' })}</span>
          <span>{t('share')}</span>
        </div>
        <Link to="/">{t('back_to_home')}</Link>
      </header>

      <div className="case-study-layout">
        <aside className="case-study-toc" aria-label={t('toc_label')}>
          <h2>{t('toc_label')}</h2>
          <ul>
            {tocItems.map((heading) => (
              <li key={heading.id}>
                <a href={`#${heading.id}`}>{heading.text}</a>
              </li>
            ))}
          </ul>
        </aside>

        <div className="case-study-content">
          {loading && (
            <div className="case-study-skeleton" aria-live="polite">
              <p>{t('loading')}</p>
              {Array.from({ length: 8 }).map((_, index) => (
                <div key={`skeleton-${index}`}>
                  <div className="case-study-skeleton-heading" />
                  <div className="case-study-skeleton-line" />
                  <div className="case-study-skeleton-line" />
                </div>
              ))}
            </div>
          )}

          {!loading && error && <div className="case-study-error">{t('error')}</div>}

          {!loading && !error && (
            <div dangerouslySetInnerHTML={{ __html: html }} />
          )}
        </div>
      </div>
    </article>
  );
}

export default CaseStudyPage;
