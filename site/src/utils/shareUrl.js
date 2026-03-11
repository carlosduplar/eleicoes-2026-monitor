/**
 * Encode answers object to URL-safe base64 string.
 * @param {Object} answers - {topicId: {optionId, weight}}
 * @returns {string} base64url-encoded string
 */
export function encodeResult(answers) {
  return btoa(JSON.stringify(answers))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

/**
 * Decode URL-safe base64 string back to answers object.
 * @param {string} r - base64url-encoded string
 * @returns {Object} answers - {topicId: {optionId, weight}}
 * @throws {Error} on invalid input
 */
export function decodeResult(r) {
  if (typeof r !== 'string' || r.trim() === '') {
    throw new Error('Invalid encoded result');
  }

  const normalized = r.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  return JSON.parse(atob(padded));
}
