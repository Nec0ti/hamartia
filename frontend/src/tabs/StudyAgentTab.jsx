import { useEffect, useRef, useState } from 'react'
import { Send, Square, LogIn, LogOut, ExternalLink, Sparkles } from 'lucide-react'
import { useI18n } from '../i18n.jsx'

const desktop = () => window.hamartiaDesktop?.chatgpt

export default function StudyAgentTab() {
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
  const requestId = useRef('')

  useEffect(() => {
    const api = desktop()
    if (!api) return
    api.status().then(async (status) => {
      setConnection(status)
      if (status.connected) {
        try {
          const available = await api.models()
          setModels(available)
          setModel(available[0]?.slug || '')
        } catch (e) {
          setError(e.message)
        }
      }
    }).catch((e) => setError(e.message))
    return api.onDelta(({ requestId: id, delta }) => {
      if (id === requestId.current) setAnswer((text) => text + delta)
    })
  }, [])

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
    if (!consent || !message.trim() || !model || busy) return
    const id = window.crypto.randomUUID()
    requestId.current = id
    setAnswer('')
    setError('')
    setNotice('')
    setBusy(true)
    try {
      const result = await desktop().chat({ requestId: id, message: message.trim(), model, language: locale, consent: true })
      if (result.status === 'failed') setError(result.detail)
      if (result.status === 'cancelled') setNotice(t('agent.cancelled'))
      if (result.status === 'completed') setMessage('')
    } catch (e) {
      setError(e.message || t('agent.requestError'))
    } finally {
      requestId.current = ''
      setBusy(false)
      setConsent(false)
    }
  }

  async function cancel() {
    if (!requestId.current) return
    await desktop()?.cancel(requestId.current)
  }

  const chatgpt = desktop()
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
        {!connection?.connected ? <div className="mt-5 flex flex-wrap gap-3"><button type="button" onClick={signIn} disabled={busy || !connection || connection?.unavailable || connection?.recoveryRequired} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2.5 font-semibold text-white disabled:opacity-50"><LogIn size={17} />{t('agent.signIn')}</button>{connection?.savedAccount && <button type="button" onClick={forgetAccount} disabled={busy} className="rounded-lg border border-canvas-line px-4 py-2.5 text-sm text-canvas-text disabled:opacity-50">{t('agent.useDifferentAccount')}</button>}</div> : <div className="mt-5 flex flex-wrap items-center gap-3">
          <span className="text-sm text-canvas-text">{connection.email || t('agent.connected')}</span>
          <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">{t('agent.planEnabled')}</span>
          <button type="button" onClick={() => desktop().openUsage()} className="inline-flex items-center gap-1 text-xs text-canvas-cyan underline">{t('agent.manageUsage')}<ExternalLink size={12} /></button>
          <button type="button" onClick={signOut} disabled={busy} className="ml-auto inline-flex items-center gap-1 text-xs text-canvas-muted underline"><LogOut size={14} />{t('agent.signOut')}</button>
        </div>}
        {connection?.unavailable && <p className="mt-3 text-sm text-amber-300">{t('agent.secureStorageUnavailable')}</p>}
        {connection?.recoveryRequired && <div className="mt-4 rounded-lg border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-100"><p>{t('agent.credentialsUnreadable')}</p><button type="button" onClick={recoverUnreadableCredentials} disabled={busy} className="mt-3 rounded-lg border border-amber-200/40 px-3 py-2 text-sm disabled:opacity-50">{t('agent.recoverCredentials')}</button></div>}
        {connection?.connected && <p className="mt-3 text-xs text-canvas-muted">{t('agent.localAiSeparate')}</p>}
      </header>

      {connection?.connected && <div className="space-y-4 rounded-2xl border border-canvas-line bg-canvas-panel p-5">
        <label className="block text-sm text-canvas-muted">{t('agent.model')}<select value={model} onChange={(event) => setModel(event.target.value)} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text">{models.map((item) => <option key={item.slug} value={item.slug}>{item.display_name}</option>)}</select></label>
        <label className="block text-sm text-canvas-muted">{t('agent.question')}<textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength={4000} rows={4} className="mt-1 w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text" placeholder={t('agent.questionPlaceholder')} /></label>
        <label className="flex items-start gap-2 text-xs leading-relaxed text-canvas-muted"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-0.5 accent-canvas-accent" />{t('agent.consent')}</label>
        <div className="flex gap-2">{busy ? <button type="button" onClick={cancel} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-text"><Square size={14} />{t('agent.cancel')}</button> : <button type="button" onClick={send} disabled={!consent || !message.trim() || !model} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Send size={14} />{t('agent.send')}</button>}</div>
        {answer && <div className="whitespace-pre-wrap rounded-lg bg-canvas-base p-4 text-sm leading-relaxed text-canvas-text" aria-live="polite">{answer}</div>}
      </div>}

      {notice && <p role="status" className="text-sm text-canvas-muted">{notice}</p>}
      {error && <p role="alert" className="rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
    </section>
  )
}
