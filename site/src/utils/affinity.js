/**
 * @typedef {Object} AffinityResult
 * @property {string} slug
 * @property {number} affinity
 * @property {Object.<string, number>} byTopic
 */

/**
 * Calculate affinity scores for all candidates based on user answers.
 *
 * @param {Object.<string, {optionId: string, weight: number}>} answers
 *   Keys are topic IDs. Each value has the optionId chosen and its weight.
 * @param {Object} quizData - full quiz.json data
 * @returns {AffinityResult[]} sorted descending by affinity
 */
export function calculateAffinity(answers, quizData) {
  const topics = quizData?.topics && typeof quizData.topics === 'object' ? quizData.topics : {};
  const candidateSet = new Set();

  Object.values(topics).forEach((topic) => {
    if (!topic || typeof topic !== 'object' || !Array.isArray(topic.options)) {
      return;
    }
    topic.options.forEach((option) => {
      if (option && typeof option === 'object' && typeof option.candidate_slug === 'string') {
        candidateSet.add(option.candidate_slug);
      }
    });
  });

  /** @type {AffinityResult[]} */
  const results = Array.from(candidateSet).map((candidateSlug) => {
    let sum = 0;
    let count = 0;
    /** @type {Object.<string, number>} */
    const byTopic = {};

    Object.entries(answers || {}).forEach(([topicId, answer]) => {
      if (!answer || typeof answer !== 'object' || typeof answer.weight !== 'number') {
        return;
      }

      const topic = topics?.[topicId];
      if (!topic || !Array.isArray(topic.options)) {
        return;
      }

      const candidateOption = topic.options.find(
        (option) =>
          option &&
          typeof option === 'object' &&
          option.candidate_slug === candidateSlug &&
          typeof option.weight === 'number',
      );

      if (!candidateOption) {
        return;
      }

      const similarity = 1 - Math.abs(answer.weight - candidateOption.weight) / 4;
      byTopic[topicId] = similarity;
      sum += similarity;
      count += 1;
    });

    return {
      slug: candidateSlug,
      affinity: count > 0 ? (sum / count) * 100 : 0,
      byTopic,
    };
  });

  results.sort((a, b) => b.affinity - a.affinity);
  return results;
}

/**
 * Determine if early-exit is possible (margin already decisive).
 *
 * @param {AffinityResult[]} results - current sorted results
 * @param {number} answeredCount - questions answered so far
 * @param {number} totalQuestions - total questions in quiz
 * @returns {boolean} true if quiz should continue
 */
export function shouldContinueQuiz(results, answeredCount, totalQuestions) {
  if (!Array.isArray(results) || results.length < 2 || totalQuestions <= 0) {
    return true;
  }

  const minAnsweredToStop = Math.ceil(totalQuestions * 0.6);
  const leaderGap = results[0].affinity - results[1].affinity;

  if (answeredCount >= minAnsweredToStop && leaderGap >= 20) {
    return false;
  }

  return true;
}
