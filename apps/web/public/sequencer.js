// Orders overlapping generation requests so only the latest one may render.
// Each submission takes a token; a later submission supersedes earlier ones,
// and a stale (out-of-order) response is dropped instead of clobbering results.
export function createSequencer() {
  let latest = 0;
  return {
    next() {
      latest += 1;
      return latest;
    },
    isCurrent(token) {
      return token === latest;
    },
  };
}
