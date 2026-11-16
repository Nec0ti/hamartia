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

function settingsRoutePattern(expectedOrigin) {
  const origin = new URL(expectedOrigin).origin
  const escapedOrigin = origin.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`^${escapedOrigin}/settings/?(?:\\?.*)?$`)
}

function diagnosticRequests(requests) {
  return requests.map(({ method, origin, path }) => ({ method, origin, path }))
}

function withDeadline(operation, timeoutMs, describe, cleanup) {
  let timer
  let timeoutError
  let cleanupPromise = Promise.resolve()
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => {
      timeoutError = new Error(`Browser smoke exceeded ${timeoutMs}ms${describe()}`)
      cleanupPromise = withTimeout(Promise.resolve().then(() => cleanup(timeoutError)), 15_000, 'Browser smoke timeout cleanup')
        .catch((cleanupError) => { timeoutError.cleanupError = cleanupError })
      cleanupPromise.then(() => reject(timeoutError))
    }, timeoutMs)
  })
  const work = Promise.resolve().then(operation).then(
    (result) => timeoutError
      ? cleanupPromise.then(() => { throw timeoutError })
      : result,
    (error) => timeoutError
      ? cleanupPromise.then(() => { throw timeoutError })
      : Promise.reject(error),
  )
  return Promise.race([work, deadline]).finally(() => clearTimeout(timer))
}

module.exports = { diagnosticRequests, withTimeout, isSettingsRequestUrl, settingsRoutePattern, withDeadline }
