const SOCIAL_DOCUMENT_PATHS = new Set([
  '/hamartia/user-agreement-v0.1-draft.html',
  '/hamartia/tr/user-agreement-v0.1-draft.html',
  '/hamartia/privacy-and-consent/',
  '/hamartia/tr/privacy-and-consent/',
])

function isAllowedSocialDocumentUrl(value) {
  try {
    const url = new URL(value)
    return url.origin === 'https://nec0ti.github.io'
      && SOCIAL_DOCUMENT_PATHS.has(url.pathname)
      && !url.search
      && !url.hash
  } catch {
    return false
  }
}

function handleSocialDocumentWindowOpen(details, shell) {
  if (isAllowedSocialDocumentUrl(details?.url)) {
    try {
      Promise.resolve(shell.openExternal(details.url)).catch(() => {})
    } catch {}
  }
  return { action: 'deny' }
}

module.exports = { handleSocialDocumentWindowOpen, isAllowedSocialDocumentUrl }
