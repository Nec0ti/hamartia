import { useEffect, useRef, useState } from 'react'
import { Send, Square, LogIn, LogOut, ExternalLink, Sparkles } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import api from '../services/api'

const desktop = () => window.hamartiaDesktop?.chatgpt

function endpointWarning(baseUrl) {
  try {
    if (baseUrl !== baseUrl.trim() || /[\u0000-\u0020\u007f]/.test(baseUrl)) return 'invalid'
    const url = new URL(baseUrl)
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password || url.search || url.hash || baseUrl.includes('?') || baseUrl.includes('#')) return 'invalid'
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    return url.protocol === 'http:' && !loopback ? 'remote-http' : !loopback ? 'remote' : url.protocol === 'http:' ? 'http' : ''
  } catch {
    return 'invalid'
  }
}

export default function StudyAgentTab({ settings, settingsOpen, onOpenSettings }) {
  const { t, locale } = useI18n()
  const [connection, setConnection] = useState(null)
  const [models, setModels] = useState([])
  const [model, setModel] = useState('')
  const [message, setMessage] = useState('')
  const [answer, setAnswer] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [provider, setProvider] = useState('chatgpt')
  const requestId = useRef('')
  const consentedSettings = useRef(null)

  useEffect(() => {
    consentedSettings.current = null
    setConsent(false)
  }, [settings, settingsOpen])

  useEffect(() => {
    const chatgptApi = desktop()
    if (!chatgptApi) return
    chatgptApi.status().then(async (status) => {
      setConnection(status)
      if (status.connected) {
        try {
          const available = await chatgptApi.models()
          setModels(available)
          setModel(available[0]?.slug || '')
        } catch (e) {
          setError(e.message)
        }
      }
    }).catch((e) => setError(e.message))
    return chatgptApi.onDelta(({ requestId: id, delta }) => {
      if (id === requestId.current) setAnswer((text) => text + delta)
    })
  }, [t])

  async function refreshModels() {
    const available = await desktop().models()
    setModels(available)
    setModel((current) => available.some((item) => item.slug === current) ? current : available[0]?.slug || '')
  }

  async function signIn() {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      setConnection(await desktop().signIn())
      await refreshModels()
    } catch (e) {
      setError(e.message || t('agent.signInError'))
      setConnection(await desktop().status().catch(() => ({ connected: false })))
    } finally {
      setBusy(false)
    }
  }

  async function signOut() {
    setBusy(true)
    setError('')
    try {
      const result = await desktop().signOut()
      setConnection(result)
      setModels([])
      setModel('')
      setAnswer('')
      setNotice(result.revocationConfirmed ? t('agent.signedOut') : t('agent.revocationUnconfirmed'))
    } catch (e) {
      setError(e.message || t('agent.signOutError'))
    } finally {
      setBusy(false)
    }
  }

  async function forgetAccount() {
    if (!window.confirm(t('agent.confirmForgetAccount'))) return
    setError('')
    try {
      setConnection(await desktop().forgetAccount())
      setNotice(t('agent.accountForgotten'))
    } catch (e) {
      setError(e.message || t('agent.signOutError'))
    }
  }

  async function recoverUnreadableCredentials() {
    if (!window.confirm(t('agent.confirmRecoverCredentials'))) return
    setBusy(true)
    setError('')
    try {
      setConnection(await desktop().recoverUnreadableCredentials(true))
      setNotice(t('agent.credentialsRecovered'))
    } catch (e) {
      setError(e.message || t('agent.signOutError'))
    } finally {
      setBusy(false)
    }
  }

  async function send() {
    if (provider === 'local' && (settingsOpen || consentedSettings.current !== settings)) {
      consentedSettings.current = null
      setConsent(false)
      setError(t('agent.refreshConsent'))
      return
    }
    if (!consent || !message.trim() || (provider === 'chatgpt' && !model) || busy) return
    const id = window.crypto.randomUUID()
    requestId.current = id
    setAnswer('')
    setError('')
    setNotice('')
    setBusy(true)
    try {
      if (provider === 'local') {
        const [insights, sessions] = await Promise.all([api.questions.insights(), api.practice.insights()])
        const context = JSON.stringify({
          pending_questions: insights.pending_questions ?? 0,
          scheduled_questions: insights.scheduled_questions ?? 0,
          topics: (insights.topics || []).slice(0, 8).map(({ subject, topic, pending_count, tags }) => ({ subject, topic, pending_count, tags })),
          topic_practice: sessions.slice(0, 8).map(({ subject, topic, session_count, net, accuracy }) => ({ subject, topic, session_count, net, accuracy })),
        }).slice(0, 6000)
        const result = await api.studyAgent.local({
          consent: true,
          message: message.trim(),
          context,
          language: locale,
          endpoint: settings.litellm_base_url,
          model_name: settings.model_name,
          has_api_key: settings.has_api_key,
        })
        setAnswer(result.answer)
        setMessage('')
      } else {
        const result = await desktop().chat({ requestId: id, message: message.trim(), model, language: locale, consent: true })
        if (result.status === 'failed') setError(result.detail)
        if (result.status === 'cancelled') setNotice(t('agent.cancelled'))
        if (result.status === 'completed') setMessage('')
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
    } finally {
      requestId.current = ''
      setBusy(false)
      setConsent(false)
    }
  }

  async function cancel() {
    if (requestId.current) await desktop()?.cancel(requestId.current)
  }

  const chatgpt = desktop()
  const configuredEndpoint = settings?.litellm_base_url || ''
  const endpointRisk = endpointWarning(configuredEndpoint)
  const canSend = provider === 'chatgpt'
    ? Boolean(connection?.connected)
    : Boolean(settings && endpointRisk !== 'invalid')
  if (!chatgpt) return <section className="mx-auto max-w-3xl rounded-2xl border border-canvas-line bg-canvas-panel p-6">
    <h1 className="text-2xl font-bold text-canvas-text">{t('agent.title')}</h1>
    <p className="mt-3 text-sm text-canvas-muted">{t('agent.desktopOnly')}</p>
  </section>

  return (
    <section className="mx-auto max-w-3xl space-y-5">
      <header className="rounded-2xl border border-canvas-line bg-canvas-panel p-5">
        <div className="flex items-center gap-3">
          <Sparkles className="text-canvas-cyan" size={22} />
          <div><h1 className="text-2xl font-bold text-canvas-text">{t('agent.title')}</h1><p className="mt-1 text-sm text-canvas-muted">{t('agent.intro')}</p></div>
        </div>
        <label className="mt-5 block max-w-sm text-sm text-canvas-muted">{t('agent.provider')}<select value={provider} disabled={busy} onChange={(event) => { setProvider(event.target.value); consentedSettings.current = null; setConsent(false); setAnswer(''); setError('') }} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="chatgpt">{t('agent.chatgptProvider')}</option><option value="local">{t('agent.configuredProvider')}</option></select></label>
        {provider === 'chatgpt' && (!connection?.connected ? <div className="mt-5 flex flex-wrap gap-3"><button type="button" onClick={signIn} disabled={busy || !connection || connection?.unavailable || connection?.recoveryRequired} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2.5 font-semibold text-white disabled:opacity-50"><LogIn size={17} />{t('agent.signIn')}</button>{connection?.savedAccount && <button type="button" onClick={forgetAccount} disabled={busy} className="rounded-lg border border-canvas-line px-4 py-2.5 text-sm text-canvas-text disabled:opacity-50">{t('agent.useDifferentAccount')}</button>}</div> : <div className="mt-5 flex flex-wrap items-center gap-3">
          <span className="text-sm text-canvas-text">{connection.email || t('agent.connected')}</span>
          <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">{t('agent.planEnabled')}</span>
          <button type="button" onClick={() => desktop().openUsage()} className="inline-flex items-center gap-1 text-xs text-canvas-cyan underline">{t('agent.manageUsage')}<ExternalLink size={12} /></button>
          <button type="button" onClick={signOut} disabled={busy} className="ml-auto inline-flex items-center gap-1 text-xs text-canvas-muted underline"><LogOut size={14} />{t('agent.signOut')}</button>
        </div>)}
        {provider === 'chatgpt' && connection?.unavailable && <p className="mt-3 text-sm text-amber-300">{t('agent.secureStorageUnavailable')}</p>}
        {provider === 'chatgpt' && connection?.recoveryRequired && <div className="mt-4 rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-100"><p>{t('agent.credentialsUnreadable')}</p><button type="button" onClick={recoverUnreadableCredentials} disabled={busy} className="mt-3 rounded-lg border border-amber-200/40 px-3 py-2 text-sm disabled:opacity-50">{t('agent.recoverCredentials')}</button></div>}
        {provider === 'chatgpt' && connection?.connected && <p className="mt-3 text-xs text-canvas-muted">{t('agent.localAiSeparate')}</p>}
        {provider === 'local' && <div className="mt-4 space-y-2 text-sm text-canvas-muted"><p>{t('agent.endpointTarget')}: <code className="break-all text-canvas-text">{configuredEndpoint || t('agent.endpointNotSet')}</code></p><p>{t('agent.endpointModel')}: <code className="text-canvas-text">{settings?.model_name || t('agent.endpointNotSet')}</code></p>{(endpointRisk === 'remote' || endpointRisk === 'remote-http') && <p className="rounded-lg bg-amber-300/10 p-3 text-amber-200">{t('agent.endpointRemoteWarning')}</p>}{(endpointRisk === 'http' || endpointRisk === 'remote-http') && <p className="rounded-lg bg-amber-300/10 p-3 text-amber-200">{t('agent.endpointHttpWarning')}</p>}{endpointRisk === 'invalid' && configuredEndpoint && <p className="text-rose-300">{t('agent.endpointInvalid')}</p>}<button type="button" onClick={onOpenSettings} className="text-xs text-canvas-cyan underline">{t('agent.configureEndpoint')}</button></div>}
      </header>

      {canSend && <div className="space-y-4 rounded-2xl border border-canvas-line bg-canvas-panel p-5">
        {provider === 'chatgpt' && <label className="block text-sm text-canvas-muted">{t('agent.model')}<select value={model} onChange={(event) => setModel(event.target.value)} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text">{models.map((item) => <option key={item.slug} value={item.slug}>{item.display_name}</option>)}</select></label>}
        <label className="block text-sm text-canvas-muted">{t('agent.question')}<textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength={4000} rows={4} className="mt-1 w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text" placeholder={t('agent.questionPlaceholder')} /></label>
        <label className="flex items-start gap-2 text-xs leading-relaxed text-canvas-muted"><input type="checkbox" checked={consent} onChange={(event) => { const accepted = event.target.checked; consentedSettings.current = accepted && provider === 'local' ? settings : null; setConsent(accepted) }} className="mt-0.5 accent-canvas-accent" />{provider === 'chatgpt' ? t('agent.consent') : t('agent.localConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') })}</label>
        <div className="flex gap-2">{busy ? provider === 'chatgpt' ? <button type="button" onClick={cancel} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-text"><Square size={14} />{t('agent.cancel')}</button> : <p role="status" className="text-sm text-canvas-muted">{t('agent.working')}</p> : <button type="button" onClick={send} disabled={!consent || (provider === 'local' && (settingsOpen || consentedSettings.current !== settings)) || !message.trim() || (provider === 'chatgpt' && !model)} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Send size={14} />{t('agent.send')}</button>}</div>
        {answer && <div className="whitespace-pre-wrap rounded-lg bg-canvas-base p-4 text-sm leading-relaxed text-canvas-text" aria-live="polite">{answer}</div>}
      </div>}

      {notice && <p role="status" className="text-sm text-canvas-muted">{notice}</p>}
      {error && <p role="alert" className="rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
    </section>
  )
}
