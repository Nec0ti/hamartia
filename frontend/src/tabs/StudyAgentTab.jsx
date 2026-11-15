import { useEffect, useRef, useState } from 'react'
import { Send, Square, LogIn, LogOut, ExternalLink, Sparkles } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import api from '../services/api'
import { summarizeStudyAgentContext } from '../utils/studyAgentContext.js'

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
  const { t, language, locale } = useI18n()
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
  const [workflow, setWorkflow] = useState('chat')
  const [studentMessages, setStudentMessages] = useState([])
  const [pendingPreview, setPendingPreview] = useState(null)
  const requestId = useRef('')
  const responseText = useRef('')
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
      if (id === requestId.current) {
        responseText.current += delta
        setAnswer((text) => text + delta)
      }
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
    const nextMessages = workflow === 'practice-entry' ? [...studentMessages, message.trim()] : null
    requestId.current = id
    responseText.current = ''
    setAnswer('')
    setError('')
    setNotice('')
    setBusy(true)
    try {
      if (provider === 'local') {
        let context = ''
        if (workflow === 'chat') {
          const [insights, sessions] = await Promise.all([api.questions.insights(), api.practice.insights()])
          context = summarizeStudyAgentContext(insights, sessions)
        }
        const result = await api.studyAgent.local({
          consent: true,
          message: message.trim(),
          context,
          language,
          workflow,
          ...(workflow === 'practice-entry' ? { messages: nextMessages } : {}),
          endpoint: settings.litellm_base_url,
          model_name: settings.model_name,
          has_api_key: settings.has_api_key,
        })
        if (workflow === 'practice-entry') {
          await updatePracticeDraft(nextMessages, result.proposal)
        } else {
          setAnswer(result.answer)
          setMessage('')
        }
      } else {
        const result = await desktop().chat({ requestId: id, message: message.trim(), model, language, workflow, messages: nextMessages || [], consent: true })
        if (result.status === 'failed') setError(result.detail)
        if (result.status === 'cancelled') setNotice(t('agent.cancelled'))
        if (result.status === 'completed' && workflow === 'practice-entry') {
          let proposal
          try {
            proposal = JSON.parse(responseText.current)
          } catch {
            throw new Error(t('agent.practiceProposalInvalid'))
          }
          await updatePracticeDraft(nextMessages, proposal.fields)
        } else if (result.status === 'completed') setMessage('')
      }
    } catch (e) {
      setError(workflow === 'practice-entry' ? t('agent.practiceProposalInvalid') : e.response?.data?.detail || e.message || t('agent.requestError'))
    } finally {
      requestId.current = ''
      setBusy(false)
      setConsent(false)
    }
  }

  async function updatePracticeDraft(messages, proposal) {
    const draft = await api.practice.agentDraft({ messages, language, proposal })
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? { ...draft, proposal } : null)
    setAnswer(draft.questions.length ? draft.questions.join('\n') : draft.conflicts.length ? t('agent.practiceConflictReview') : t('agent.practicePreviewReady'))
  }

  async function approvePractice(duplicateChoice = null) {
    if (!pendingPreview || !window.confirm(t('agent.confirmPracticeSave'))) return
    setBusy(true)
    setError('')
    try {
      await api.practice.agentCreate({
        messages: studentMessages,
        language,
        proposal: pendingPreview.proposal,
        fields: pendingPreview.fields,
        evidence: pendingPreview.evidence,
        preview_digest: pendingPreview.preview_digest,
        duplicate_choice: duplicateChoice,
      })
      setPendingPreview(null)
      setStudentMessages([])
      setAnswer(t('agent.practiceSaved'))
    } catch (e) {
      if (e.response?.status === 409 && Array.isArray(e.response?.data?.detail?.conflicts)) {
        setPendingPreview((current) => current ? { ...current, conflicts: e.response.data.detail.conflicts } : current)
        setError(t('agent.practiceConflictReview'))
      } else {
        setError(e.response?.data?.detail?.message || e.response?.data?.detail || e.message || t('agent.requestError'))
      }
    } finally {
      setBusy(false)
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
          <Sparkles className="text-canvas-text" size={22} />
          <div><h1 className="text-2xl font-bold text-canvas-text">{t('agent.title')}</h1><p className="mt-1 text-sm text-canvas-muted">{t('agent.intro')}</p></div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm text-canvas-muted">{t('agent.provider')}<select value={provider} disabled={busy} onChange={(event) => { setProvider(event.target.value); consentedSettings.current = null; setConsent(false); setAnswer(''); setPendingPreview(null); setError('') }} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="chatgpt">{t('agent.chatgptProvider')}</option><option value="local">{t('agent.configuredProvider')}</option></select></label>
          <label className="block text-sm text-canvas-muted">{t('agent.workflow')}<select value={workflow} disabled={busy} onChange={(event) => { setWorkflow(event.target.value); setStudentMessages([]); setPendingPreview(null); setAnswer(''); setError('') }} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="chat">{t('agent.workflowChat')}</option><option value="practice-entry">{t('agent.workflowPractice')}</option></select></label>
        </div>
        {workflow === 'practice-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.practiceEntryHint')}</p>}
        {provider === 'local' && <p className="mt-2 max-w-3xl text-xs leading-relaxed text-canvas-muted">{t('agent.configuredProviderInfo')} <a href="https://nec0ti.github.io/hamartia/study-agent/#local-servers" target="_blank" rel="noopener noreferrer" className="text-canvas-text underline">{t('agent.configuredProviderGuide')}</a></p>}
        {provider === 'chatgpt' && (!connection?.connected ? <div className="mt-5 flex flex-wrap gap-3"><button type="button" onClick={signIn} disabled={busy || !connection || connection?.unavailable || connection?.recoveryRequired} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2.5 font-semibold text-canvas-base disabled:opacity-50"><LogIn size={17} />{t('agent.signIn')}</button>{connection?.savedAccount && <button type="button" onClick={forgetAccount} disabled={busy} className="rounded-lg border border-canvas-line px-4 py-2.5 text-sm text-canvas-text disabled:opacity-50">{t('agent.useDifferentAccount')}</button>}</div> : <div className="mt-5 flex flex-wrap items-center gap-3">
          <span className="text-sm text-canvas-text">{connection.email || t('agent.connected')}</span>
          <span className="rounded-full bg-canvas-raise px-3 py-1 text-xs text-canvas-text">{t('agent.planEnabled')}</span>
          <button type="button" onClick={() => desktop().openUsage()} className="inline-flex items-center gap-1 text-xs text-canvas-text underline">{t('agent.manageUsage')}<ExternalLink size={12} /></button>
          <button type="button" onClick={signOut} disabled={busy} className="ml-auto inline-flex items-center gap-1 text-xs text-canvas-muted underline"><LogOut size={14} />{t('agent.signOut')}</button>
        </div>)}
        {provider === 'chatgpt' && connection?.unavailable && <p className="mt-3 text-sm text-canvas-text">{t('agent.secureStorageUnavailable')}</p>}
        {provider === 'chatgpt' && connection?.recoveryRequired && <div className="mt-4 rounded-lg border border-canvas-line bg-canvas-raise p-3 text-sm text-canvas-text"><p>{t('agent.credentialsUnreadable')}</p><button type="button" onClick={recoverUnreadableCredentials} disabled={busy} className="mt-3 rounded-lg border border-canvas-line px-3 py-2 text-sm disabled:opacity-50">{t('agent.recoverCredentials')}</button></div>}
        {provider === 'chatgpt' && connection?.connected && <p className="mt-3 text-xs text-canvas-muted">{t('agent.localAiSeparate')}</p>}
        {provider === 'local' && <div className="mt-4 space-y-2 text-sm text-canvas-muted"><p>{t('agent.endpointTarget')}: <code className="break-all text-canvas-text">{configuredEndpoint || t('agent.endpointNotSet')}</code></p><p>{t('agent.endpointModel')}: <code className="text-canvas-text">{settings?.model_name || t('agent.endpointNotSet')}</code></p>{(endpointRisk === 'remote' || endpointRisk === 'remote-http') && <p className="rounded-lg bg-canvas-raise p-3 text-canvas-text">{t('agent.endpointRemoteWarning')}</p>}{(endpointRisk === 'http' || endpointRisk === 'remote-http') && <p className="rounded-lg bg-canvas-raise p-3 text-canvas-text">{t('agent.endpointHttpWarning')}</p>}{endpointRisk === 'invalid' && configuredEndpoint && <p className="text-canvas-text">{t('agent.endpointInvalid')}</p>}<button type="button" onClick={onOpenSettings} className="text-xs text-canvas-text underline">{t('agent.configureEndpoint')}</button></div>}
      </header>

      {canSend && <div className="space-y-4 rounded-2xl border border-canvas-line bg-canvas-panel p-5">
        {provider === 'chatgpt' && <label className="block text-sm text-canvas-muted">{t('agent.model')}<select value={model} onChange={(event) => setModel(event.target.value)} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text">{models.map((item) => <option key={item.slug} value={item.slug}>{item.display_name}</option>)}</select></label>}
        {workflow === 'practice-entry' && studentMessages.length > 0 && <ol className="max-h-48 space-y-2 overflow-auto rounded-lg bg-canvas-base p-3 text-sm text-canvas-muted" aria-label={t('agent.workflowPractice')}>{studentMessages.map((item, index) => <li key={index} className="whitespace-pre-wrap">{item}</li>)}</ol>}
        <label className="block text-sm text-canvas-muted">{workflow === 'practice-entry' ? t('agent.practiceEntryPrompt') : t('agent.question')}<textarea value={message} onChange={(event) => { setMessage(event.target.value); if (workflow === 'practice-entry') setPendingPreview(null) }} maxLength={4000} rows={4} className="mt-1 w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text" placeholder={workflow === 'practice-entry' ? t('agent.practiceEntryPrompt') : t('agent.questionPlaceholder')} /></label>
        <label className="flex items-start gap-2 text-xs leading-relaxed text-canvas-muted"><input type="checkbox" checked={consent} onChange={(event) => { const accepted = event.target.checked; consentedSettings.current = accepted && provider === 'local' ? settings : null; setConsent(accepted) }} className="mt-0.5 accent-canvas-accent" />{workflow === 'practice-entry' ? provider === 'chatgpt' ? t('agent.practiceEntryConsent') : t('agent.practiceEntryLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : provider === 'chatgpt' ? t('agent.consent') : t('agent.localConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') })}</label>
        <div className="flex gap-2">{busy ? provider === 'chatgpt' ? <button type="button" onClick={cancel} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-text"><Square size={14} />{t('agent.cancel')}</button> : <p role="status" className="text-sm text-canvas-muted">{t('agent.working')}</p> : <button type="button" onClick={send} disabled={!consent || (provider === 'local' && (settingsOpen || consentedSettings.current !== settings)) || !message.trim() || (provider === 'chatgpt' && !model)} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Send size={14} />{t('agent.send')}</button>}</div>
        {answer && <div className="whitespace-pre-wrap rounded-lg bg-canvas-base p-4 text-sm leading-relaxed text-canvas-text" aria-live="polite">{answer}</div>}
        {pendingPreview && <div className="space-y-3 rounded-xl border border-canvas-line bg-canvas-base p-4">
          <div><h2 className="font-semibold text-canvas-text">{t('agent.practicePreviewTitle')}</h2><p className="mt-1 text-xs text-canvas-muted">{t('agent.practiceNoWrite')}</p></div>
          <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(pendingPreview.fields).map(([field, value]) => <div key={field} className="rounded-lg bg-canvas-panel p-3"><dt className="text-xs text-canvas-muted">{t(`agent.practice.${field}`)}</dt><dd className="mt-1 break-words text-sm text-canvas-text">{value}</dd><dd className="mt-2 border-t border-canvas-line pt-2 text-xs text-canvas-muted">{t('agent.provenance')}: “{pendingPreview.evidence[field].quote}”</dd></div>)}</dl>
          {pendingPreview.conflicts.length > 0 && <div className="rounded-lg border border-canvas-line p-3"><h3 className="text-sm font-semibold text-canvas-text">{t('agent.practice.conflicts')}</h3><ul className="mt-2 space-y-1 text-xs text-canvas-muted">{pendingPreview.conflicts.map((item) => <li key={item.id}>{item.date} · {item.subject} / {item.topic} · {item.correct}/{item.incorrect}/{item.blank}</li>)}</ul></div>}
          <div className="flex flex-wrap gap-2">{pendingPreview.conflicts.length === 0 ? <button type="button" onClick={() => approvePractice()} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.practiceSave')}</button> : <button type="button" onClick={() => approvePractice('new')} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.practiceSaveNew')}</button>}<button type="button" onClick={() => setPendingPreview(null)} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50">{t('agent.practiceCancel')}</button></div>
        </div>}
      </div>}

      {notice && <p role="status" className="text-sm text-canvas-muted">{notice}</p>}
      {error && <p role="alert" className="rounded-lg border border-canvas-line bg-canvas-raise p-3 text-sm text-canvas-text">{error}</p>}
    </section>
  )
}
