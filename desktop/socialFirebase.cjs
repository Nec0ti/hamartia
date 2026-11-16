function firebaseConfigFromEnvironment(environment) {
  const config = {
    apiKey: environment.HAMARTIA_FIREBASE_API_KEY,
    authDomain: environment.HAMARTIA_FIREBASE_AUTH_DOMAIN,
    projectId: environment.HAMARTIA_FIREBASE_PROJECT_ID,
    appId: environment.HAMARTIA_FIREBASE_APP_ID,
  }
  if (Object.values(config).some((value) => typeof value !== 'string' || !value.trim())) return null
  return Object.freeze(config)
}

function createSocialFirebaseAuth({ environment = process.env, oauth, loadSdk = loadFirebaseSdk }) {
  const config = firebaseConfigFromEnvironment(environment)
  let clientPromise

  async function getClient() {
    if (!config) throw new Error('Social sign-in is not configured.')
    if (!clientPromise) {
      clientPromise = loadSdk().then((sdk) => {
        const app = sdk.initializeApp(config, 'hamartia-social')
        const auth = sdk.initializeAuth(app, {
          persistence: sdk.inMemoryPersistence,
          popupRedirectResolver: undefined,
        })
        return { sdk, auth }
      }).catch((error) => {
        clientPromise = null
        throw error
      })
    }
    return clientPromise
  }

  async function signIn() {
    const { sdk, auth } = await getClient()
    const googleIdToken = await oauth.signIn()
    if (!googleIdToken) return { status: 'cancelled' }
    const credential = sdk.GoogleAuthProvider.credential(googleIdToken)
    const result = await sdk.signInWithCredential(auth, credential)
    if (!result?.user) throw new Error('Firebase sign-in could not be completed.')
    return { status: 'signedIn' }
  }

  async function getIdToken() {
    const { auth } = await getClient()
    if (!auth.currentUser) return null
    return auth.currentUser.getIdToken()
  }

  async function signOut() {
    oauth.cancel()
    if (!clientPromise) return { status: 'signedOut' }
    const { sdk, auth } = await clientPromise
    await sdk.signOut(auth)
    return { status: 'signedOut' }
  }

  return Object.freeze({ signIn, getIdToken, signOut })
}

async function loadFirebaseSdk() {
  const [app, auth] = await Promise.all([import('firebase/app'), import('firebase/auth')])
  return { ...app, ...auth }
}

module.exports = { createSocialFirebaseAuth, firebaseConfigFromEnvironment, loadFirebaseSdk }
