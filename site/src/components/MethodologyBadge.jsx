import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

function MethodologyBadge() {
  const { t } = useTranslation('common');

  return (
    <Link className="methodology-badge" to="/metodologia">
      <span className="methodology-badge-icon" aria-hidden="true">
        {'\u24D8'}
      </span>
      <span>{t('methodology_badge')}</span>
    </Link>
  );
}

export default MethodologyBadge;
