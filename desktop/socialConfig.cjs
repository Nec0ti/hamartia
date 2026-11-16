const fs = require('node:fs')
const path = require('node:path')

const EMPTY_SOCIAL_CONFIG = Object.freeze({
  firebase: null,
  googleOAuthClientId: null,
  socialApiOrigin: null,
  agreementVersion: null,
})

function validateSocialPublicConfig(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return EMPTY_SOCIAL_CONFIG
  const firebase = value.firebase && typeof value.firebase === 'object' ? value.firebase : null
  const firebaseValues = firebase && {
    apiKey: firebase.apiKey,
    authDomain: firebase.authDomain,
    projectId: firebase.projectId,
    appId: firebase.appId,
  }
  const completeFirebase = firebaseValues && Object.values(firebaseValues).every((item) => typeof item === 'string' && item.trim())
    ? Object.freeze(firebaseValues)
    : null
  const googleOAuthClientId = typeof value.googleOAuthClientId === 'string'
    && /^[A-Za-z0-9._-]{10,255}\.apps\.googleusercontent\.com$/.test(value.googleOAuthClientId)
    ? value.googleOAuthClientId
    : null
  const agreementVersion = typeof value.agreementVersion === 'string'
    && /^[A-Za-z0-9._-]{1,40}$/.test(value.agreementVersion)
    ? value.agreementVersion
    : null
  let socialApiOrigin = null
  if (typeof value.socialApiOrigin === 'string') {
    try {
      const url = new URL(value.socialApiOrigin)
      if (url.protocol === 'https:' && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash) {
        socialApiOrigin = url.origin
      }
    } catch {}
  }
  if (!completeFirebase || !googleOAuthClientId || !socialApiOrigin || !agreementVersion) return EMPTY_SOCIAL_CONFIG
  return Object.freeze({ firebase: completeFirebase, googleOAuthClientId, socialApiOrigin, agreementVersion })
}

function loadSocialPublicConfig({ isPackaged, resourcesPath, desktopDir, readFile = fs.readFileSync }) {
  const file = isPackaged
    ? path.join(resourcesPath, 'social-public-config.json')
    : path.resolve(desktopDir, '../frontend/dist/social-public-config.json')
  try {
    return validateSocialPublicConfig(JSON.parse(readFile(file, 'utf8')))
  } catch {
    return EMPTY_SOCIAL_CONFIG
  }
}

module.exports = { EMPTY_SOCIAL_CONFIG, loadSocialPublicConfig, validateSocialPublicConfig }
