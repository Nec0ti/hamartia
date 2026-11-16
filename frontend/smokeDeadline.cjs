function withTimeout(promise, timeoutMs, label, details = () => '') {
  let timeout
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      timeout = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms${details()}`)), timeoutMs)
    }),
  ]).finally(() => clearTimeout(timeout))
}

function isSettingsRequestUrl(value, expectedOrigin) {
  try {
    const url = value instanceof URL ? value : new URL(value)
    return url.origin === expectedOrigin && (url.pathname === '/settings' || url.pathname === '/settings/')
  } catch {
    return false
  }
}

function createSmokeDeadline(timeoutMs, describe, onExpire) {
  let error = null
  const timer = setTimeout(() => {
    error = new Error(`Browser smoke exceeded ${timeoutMs}ms${describe()}`)
    Promise.resolve().then(() => onExpire(error)).catch(() => {})
  }, timeoutMs)
  return {
    error: () => error,
    clear: () => clearTimeout(timer),
  }
}

module.exports = { withTimeout, isSettingsRequestUrl, createSmokeDeadline }
