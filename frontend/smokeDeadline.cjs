function withTimeout(promise, timeoutMs, label, details = () => '') {
  let timeout
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      timeout = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms${details()}`)), timeoutMs)
    }),
  ]).finally(() => clearTimeout(timeout))
}

module.exports = { withTimeout }
