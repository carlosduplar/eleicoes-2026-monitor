import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { encodeResult } from '../utils/shareUrl';

/**
 * @param {{ answers: Object }} props
 */
function ShareButton({ answers }) {
  const { t } = useTranslation('common');
  const [copied, setCopied] = useState(false);

  const handleClick = useCallback(async () => {
    const shareUrl = `${window.location.origin}/quiz/resultado?r=${encodeResult(answers)}`;
    try {
      if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
        throw new Error('Clipboard API unavailable');
      }
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout(() => {
        setCopied(false);
      }, 3000);
    } catch {
      window.prompt(t('quiz.share'), shareUrl);
    }
  }, [answers, t]);

  return (
    <button
      className={`quiz-share-btn ${copied ? 'quiz-share-btn--copied' : ''}`}
      onClick={handleClick}
      type="button"
    >
      {copied ? t('quiz.link_copied') : t('quiz.share')}
    </button>
  );
}

export default ShareButton;
