import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import NewsFeed from '@/components/NewsFeed';
import SourceFilter from '@/components/SourceFilter';

function Home() {
  const { t } = useTranslation('common');
  const [selectedCategory, setSelectedCategory] = useState('all');

  return (
    <div className="home-grid">
      <section>
        <SourceFilter selectedCategory={selectedCategory} onSelectCategory={setSelectedCategory} />
        <NewsFeed selectedCategory={selectedCategory} />
      </section>
      <aside className="home-sidebar">
        <article className="sidebar-card">
          <h3>{t('home.sidebar.latest_poll.title')}</h3>
          <p>{t('home.sidebar.latest_poll.body')}</p>
        </article>
        <article className="sidebar-card">
          <h3>{t('home.sidebar.quiz.title')}</h3>
          <p>{t('home.sidebar.quiz.body')}</p>
        </article>
        <article className="sidebar-card">
          <h3>{t('home.sidebar.candidates.title')}</h3>
          <p>{t('home.sidebar.candidates.body')}</p>
        </article>
      </aside>
    </div>
  );
}

export default Home;
