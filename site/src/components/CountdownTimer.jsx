import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const TARGET_DATE_UTC = Date.UTC(2026, 9, 4);

function getDaysUntilElection() {
  const now = new Date();
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const difference = TARGET_DATE_UTC - todayUtc;
  return Math.max(0, Math.ceil(difference / (1000 * 60 * 60 * 24)));
}

function CountdownTimer() {
  const { t } = useTranslation('common');
  const [days, setDays] = useState(null);

  useEffect(() => {
    setDays(getDaysUntilElection());
  }, []);

  const daysValue = days === null ? '--' : days;

  return (
    <div className="countdown-bar">
      <span>
        {'\u{1F4C5} '}
        {t('countdown.days_to_first_round', { days: daysValue })} {'\u00B7'} {t('countdown.date')}
      </span>
    </div>
  );
}

export default CountdownTimer;
