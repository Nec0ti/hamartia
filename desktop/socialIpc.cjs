const net = require('node:net')

const CHANNEL = 'hamartia:social'
const PROFILE_PATH = '/social/me/profile'
const AVATAR_PRESETS = new Set(['sunrise', 'moon', 'leaf', 'star', 'book', 'mountain', 'wave', 'lantern'])
const FIELD_LIMITS = new Map([
  ['nickname', 80],
  ['school_grade', 80],
  ['school_class', 80],
  ['curriculum', 120],
  ['study_preferences', 2000],
  ['study_goals', 2000],
])
const PROFILE_FIELDS = new Set([
  ...FIELD_LIMITS.keys(),
  'age',
  'avatar_preset',
  'nickname_public',
  'age_public',
  'school_grade_public',
  'school_class_public',
  'curriculum_public',
  'study_preferences_public',
  'study_goals_public',
  'avatar_preset_public',
])

function isLoopbackIp(hostname) {
  const host = hostname.startsWith('[') && hostname.endsWith(']') ? hostname.slice(1, -1) : hostname
  return net.isIP(host) === 6 ? host === '::1' : net.isIP(host) === 4 && host.startsWith('127.')
}

function parseSocialApiOrigin(value, { allowLoopbackHttp = false } = {}) {
  if (typeof value !== 'string' || !value) return null
  try {
    const url = new URL(value)
    if (url.username || url.password || url.pathname !== '/' || url.search || url.hash) return null
    if (url.protocol === 'https:') return url.origin
    if (url.protocol === 'http:' && allowLoopbackHttp && isLoopbackIp(url.hostname)) return url.origin
    return null
  } catch {
    return null
  }
}

function validFirebaseIdToken(token) {
  return typeof token === 'string' && token.length <= 8192 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token)
}

function validateProfilePatch(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
    throw new Error('Invalid profile update.')
  }
  const patch = {}
  for (const [key, fieldValue] of Object.entries(value)) {
    if (!PROFILE_FIELDS.has(key)) throw new Error('Invalid profile update.')
    if (key.endsWith('_public')) {
      if (typeof fieldValue !== 'boolean') throw new Error('Invalid profile update.')
    } else if (key === 'age') {
      if (fieldValue !== null && (!Number.isInteger(fieldValue) || fieldValue < 5 || fieldValue > 120)) throw new Error('Invalid profile update.')
    } else if (key === 'avatar_preset') {
      if (fieldValue !== null && !AVATAR_PRESETS.has(fieldValue)) throw new Error('Invalid profile update.')
    } else if (FIELD_LIMITS.has(key)) {
      if (fieldValue !== null && (typeof fieldValue !== 'string' || fieldValue.length > FIELD_LIMITS.get(key))) {
        throw new Error('Invalid profile update.')
      }
    }
    patch[key] = fieldValue
  }
  return patch
}

function registerSocialIpc({ ipcMain, auth, getBackendUrl, apiOrigin, allowLoopbackHttp = false, fetchImpl = fetch }) {
  const trustedOrigin = parseSocialApiOrigin(apiOrigin, { allowLoopbackHttp })

  function isTrustedSender(event) {
    try {
      return Boolean(getBackendUrl() && event.senderFrame?.parent === null && new URL(event.senderFrame.url).origin === getBackendUrl())
    } catch {
      return false
    }
  }

  function trustedHandler(name, handler) {
    ipcMain.handle(`${CHANNEL}:${name}`, async (event, ...args) => {
      if (!isTrustedSender(event)) throw new Error('Untrusted app window.')
      return handler(...args)
    })
  }

  async function request(method, body) {
    if (!trustedOrigin) throw new Error('Social service is not configured.')
    const idToken = await auth.getIdToken()
    if (!validFirebaseIdToken(idToken)) throw new Error('Social identity is unavailable.')
    const response = await fetchImpl(`${trustedOrigin}${PROFILE_PATH}`, {
      method,
      headers: {
        authorization: `Bearer ${idToken}`,
        accept: 'application/json',
        ...(body ? { 'content-type': 'application/json' } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(15_000),
    })
    if (!response.ok) throw new Error('Social profile request failed.')
    try {
      return await response.json()
    } catch {
      throw new Error('Social profile response was invalid.')
    }
  }

  trustedHandler('sign-in', (...args) => {
    if (args.length) throw new Error('Invalid social request.')
    return auth.signIn()
  })
  trustedHandler('get-profile', (...args) => {
    if (args.length) throw new Error('Invalid social request.')
    return request('GET')
  })
  trustedHandler('patch-profile', (...args) => {
    if (args.length !== 1) throw new Error('Invalid social request.')
    return request('PATCH', validateProfilePatch(args[0]))
  })
  trustedHandler('sign-out', (...args) => {
    if (args.length) throw new Error('Invalid social request.')
    return auth.signOut()
  })
}

module.exports = { PROFILE_PATH, registerSocialIpc, parseSocialApiOrigin, validateProfilePatch, validFirebaseIdToken }
