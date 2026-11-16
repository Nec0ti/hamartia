function configuredFirebase(environment) {
  const config = {
    apiKey: environment.VITE_FIREBASE_API_KEY,
    authDomain: environment.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: environment.VITE_FIREBASE_PROJECT_ID,
    appId: environment.VITE_FIREBASE_APP_ID,
  }
  if (Object.values(config).some((value) => typeof value !== 'string' || !value.trim())) return null
  return Object.freeze(config)
}

function validEmulatorUrl(value) {
  if (!value) return null
  try {
    const url = new URL(value)
    const hostname = url.hostname.startsWith('[') && url.hostname.endsWith(']')
      ? url.hostname.slice(1, -1)
      : url.hostname
    const loopback = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
    if (url.protocol !== 'http:' || !loopback || url.username || url.password || url.pathname !== '/' || url.search || url.hash) return null
    return url.origin
  } catch {
    return null
  }
}

export function createSocialClient({
  desktopBridge = globalThis.window?.hamartiaDesktop?.social,
  environment = import.meta.env || {},
  buildEnabled,
  browserBuildEnabled = typeof __HAMARTIA_BROWSER_SOCIAL_ENABLED__ === 'boolean' ? __HAMARTIA_BROWSER_SOCIAL_ENABLED__ : false,
  desktopBuildEnabled = typeof __HAMARTIA_DESKTOP_SOCIAL_ENABLED__ === 'boolean' ? __HAMARTIA_DESKTOP_SOCIAL_ENABLED__ : false,
  browserAgreementVersion = typeof __HAMARTIA_BROWSER_AGREEMENT_VERSION__ === 'string' ? __HAMARTIA_BROWSER_AGREEMENT_VERSION__ : '',
  desktopAgreementVersion = typeof __HAMARTIA_DESKTOP_AGREEMENT_VERSION__ === 'string' ? __HAMARTIA_DESKTOP_AGREEMENT_VERSION__ : '',
  loadSdk = loadFirebaseSdk,
  fetchImpl = globalThis.fetch,
} = {}) {
  const firebaseConfig = configuredFirebase(environment)
  const enabled = desktopBridge
    ? (buildEnabled ?? desktopBuildEnabled)
    : (buildEnabled ?? browserBuildEnabled) && Boolean(firebaseConfig)
  const emulatorUrl = validEmulatorUrl(environment.VITE_FIREBASE_AUTH_EMULATOR_URL)
  if (environment.VITE_FIREBASE_AUTH_EMULATOR_URL && !emulatorUrl) {
    throw new Error('Firebase Auth Emulator must use a loopback HTTP origin.')
  }
  let browserClientPromise
  let acceptedAgreementVersion = ''
  const configuredAgreementVersion = desktopBridge ? desktopAgreementVersion : browserAgreementVersion

  function hasAcceptedAgreement() {
    return Boolean(configuredAgreementVersion && acceptedAgreementVersion === configuredAgreementVersion)
  }

  async function getBrowserClient() {
    if (!firebaseConfig) throw new Error('Social sign-in is not configured.')
    if (!browserClientPromise) {
      browserClientPromise = loadSdk().then((sdk) => {
        const appName = 'hamartia-social-web'
        const app = sdk.getApps().find((item) => item.name === appName) || sdk.initializeApp(firebaseConfig, appName)
        let auth
        try {
          auth = sdk.initializeAuth(app, {
            persistence: sdk.inMemoryPersistence,
            popupRedirectResolver: sdk.browserPopupRedirectResolver,
          })
        } catch (error) {
          if (error?.code !== 'auth/already-initialized') throw error
          auth = sdk.getAuth(app)
        }
        if (emulatorUrl && !auth.emulatorConfig) {
          sdk.connectAuthEmulator(auth, emulatorUrl, { disableWarnings: false })
        }
        return { sdk, auth }
      }).catch((error) => {
        browserClientPromise = null
        throw error
      })
    }
    return browserClientPromise
  }

  async function signIn() {
    if (!enabled || !hasAcceptedAgreement()) return { status: 'disabled' }
    if (desktopBridge) return desktopBridge.signIn(acceptedAgreementVersion)
    try {
      const { sdk, auth } = await getBrowserClient()
      const provider = new sdk.GoogleAuthProvider()
      provider.setCustomParameters?.({ prompt: 'select_account' })
      await sdk.signInWithPopup(auth, provider)
      return { status: 'signedIn' }
    } catch (error) {
      if (error?.code === 'auth/popup-closed-by-user' || error?.code === 'auth/cancelled-popup-request') {
        return { status: 'cancelled' }
      }
      throw new Error('Google sign-in could not be completed.')
    }
  }

  async function requestProfile(method, patch) {
    if (!enabled || !hasAcceptedAgreement()) return { status: 'disabled' }
    if (desktopBridge) {
      const result = method === 'GET'
        ? await desktopBridge.getProfile(acceptedAgreementVersion)
        : await desktopBridge.patchProfile(patch, acceptedAgreementVersion)
      return result?.status ? result : { status: 'signedIn', profile: result }
    }
    const { auth } = await getBrowserClient()
    const user = auth.currentUser
    if (!user) return { status: 'signedOut' }
    const idToken = await user.getIdToken()
    const response = await fetchImpl('/social/me/profile', {
      method,
      headers: {
        authorization: `Bearer ${idToken}`,
        accept: 'application/json',
        ...(method === 'PATCH' ? { 'content-type': 'application/json' } : {}),
      },
      ...(method === 'PATCH' ? { body: JSON.stringify(patch) } : {}),
      cache: 'no-store',
      redirect: 'error',
    })
    if (response.status === 401) return { status: 'signedOut' }
    if (!response.ok) throw new Error('Social profile is unavailable.')
    try {
      return { status: 'signedIn', profile: await response.json() }
    } catch {
      throw new Error('Social profile response was invalid.')
    }
  }

  async function signOut() {
    if (desktopBridge) return desktopBridge.signOut()
    if (!firebaseConfig) return { status: 'signedOut' }
    const { sdk, auth } = await getBrowserClient()
    await sdk.signOut(auth)
    return { status: 'signedOut' }
  }

  return Object.freeze({
    isEnabled: () => enabled,
    setAgreementAccepted: (accepted) => {
      acceptedAgreementVersion = accepted ? configuredAgreementVersion : ''
    },
    clearAgreementAcceptance: () => { acceptedAgreementVersion = '' },
    signIn,
    getProfile: () => requestProfile('GET'),
    patchProfile: (patch) => requestProfile('PATCH', patch),
    signOut,
  })
}

async function loadFirebaseSdk() {
  const [app, auth] = await Promise.all([import('firebase/app'), import('firebase/auth')])
  return { ...app, ...auth }
}

const socialClient = createSocialClient()

export default socialClient
