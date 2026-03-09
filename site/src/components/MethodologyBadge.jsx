import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

function MethodologyBadge() {
  const { t } = useTranslation('common');

  return (
    <Link className="methodology-badge" to="/metodologia">
      <span aria-hidden="true">i</span>
      {t('methodology_badge')}
    </Link>
  );
}

export default MethodologyBadge;
