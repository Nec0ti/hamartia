function isDesktopBackendReady(response) {
  return response.status === 204 && response.headers.get('X-Hamartia-Control-Token-Verified') === 'true'
}

module.exports = { isDesktopBackendReady }
