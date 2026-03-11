import { useState, useMemo, useCallback } from 'react';

import { useData } from './useData';
import { calculateAffinity } from '../utils/affinity';

/**
 * Custom hook managing full quiz lifecycle.
 *
 * @returns {{
 *   quizData: Object|null,
 *   loading: boolean,
 *   error: Error|null,
 *   answers: Object.<string, {optionId: string, weight: number}>,
 *   currentTopicIndex: number,
 *   isComplete: boolean,
 *   results: Array<{slug: string, affinity: number, byTopic: Object.<string, number>}>|null,
 *   currentTopic: Object|null,
 *   orderedTopics: string[],
 *   totalTopics: number,
 *   handleAnswer: (topicId: string, optionId: string, weight: number) => void,
 *   reset: () => void
 * }}
 */
export function useQuiz() {
  const { data: quizData, loading, error } = useData('quiz');
  const [answers, setAnswers] = useState({});
  const [currentTopicIndex, setCurrentTopicIndex] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  const orderedTopics = useMemo(() => {
    if (!Array.isArray(quizData?.ordered_topics)) {
      return [];
    }
    return quizData.ordered_topics.filter((topicId) => typeof topicId === 'string');
  }, [quizData]);

  const totalTopics = orderedTopics.length;

  const currentTopic = useMemo(() => {
    if (!quizData || totalTopics === 0) {
      return null;
    }
    const currentTopicId = orderedTopics[currentTopicIndex];
    if (!currentTopicId) {
      return null;
    }
    return quizData?.topics?.[currentTopicId] ?? null;
  }, [currentTopicIndex, orderedTopics, quizData, totalTopics]);

  const results = useMemo(() => {
    if (!isComplete || !quizData) {
      return null;
    }
    return calculateAffinity(answers, quizData);
  }, [answers, isComplete, quizData]);

  const handleAnswer = useCallback(
    (topicId, optionId, weight) => {
      setAnswers((previous) => ({
        ...previous,
        [topicId]: { optionId, weight },
      }));

      const nextIndex = currentTopicIndex + 1;
      if (nextIndex >= totalTopics) {
        setIsComplete(true);
        return;
      }
      setCurrentTopicIndex(nextIndex);
    },
    [currentTopicIndex, totalTopics],
  );

  const reset = useCallback(() => {
    setAnswers({});
    setCurrentTopicIndex(0);
    setIsComplete(false);
  }, []);

  return {
    quizData,
    loading,
    error,
    answers,
    currentTopicIndex,
    isComplete,
    results,
    currentTopic,
    orderedTopics,
    totalTopics,
    handleAnswer,
    reset,
  };
}
