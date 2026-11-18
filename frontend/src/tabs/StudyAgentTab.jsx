import { useEffect, useRef, useState } from 'react'
import { Send, Square, LogIn, LogOut, ExternalLink, Sparkles } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import api from '../services/api'
import { summarizeStudyAgentContext } from '../utils/studyAgentContext.js'

const desktop = () => window.hamartiaDesktop?.chatgpt
const LEGACY_PROFILE = { profile_id: 'legacy-yks', version: 1, display_name: 'YKS (legacy)', scoring_rule: { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' } }

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
  const [profiles, setProfiles] = useState([LEGACY_PROFILE])
  const [scoringProfileRef, setScoringProfileRef] = useState('')
  const [studentMessages, setStudentMessages] = useState([])
  const [expectedEvidenceField, setExpectedEvidenceField] = useState('activity')
  const [learningEvidenceStateToken, setLearningEvidenceStateToken] = useState(null)
  const [expectedQuestionField, setExpectedQuestionField] = useState('question_text')
  const [questionStateToken, setQuestionStateToken] = useState(null)
  const [expectedExamField, setExpectedExamField] = useState('date')
  const [examStateToken, setExamStateToken] = useState(null)
  const [expectedSectionedExamField, setExpectedSectionedExamField] = useState('exam_type')
  const [sectionedExamStateToken, setSectionedExamStateToken] = useState(null)
  const [expectedCustomExamField, setExpectedCustomExamField] = useState('format_name')
  const [customExamStateToken, setCustomExamStateToken] = useState(null)
  const [pendingPreview, setPendingPreview] = useState(null)
  const requestId = useRef('')
  const approvalRef = useRef(null)
  const workflowRef = useRef(workflow)
  workflowRef.current = workflow
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
        if (workflowRef.current !== 'practice-entry') setAnswer((text) => text + delta)
      }
    })
  }, [t])

  useEffect(() => {
    api.examProfiles.list().then((items) => {
      setProfiles(items)
      setScoringProfileRef((current) => items.some((item) => `${item.profile_id}@${item.version}` === current) ? current : '')
    }).catch(() => {})
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
    if (provider === 'local' && (settingsOpen || consentedSettings.current !== settings)) {
      consentedSettings.current = null
      setConsent(false)
      setError(t('agent.refreshConsent'))
      return
    }
    if (!consent || !message.trim() || (['practice-entry', 'exam-entry', 'sectioned-exam-entry', 'custom-sectioned-exam-entry'].includes(workflow) && !scoringProfileRef)
        || (provider === 'chatgpt' && !model) || busy) return
    const id = window.crypto.randomUUID()
    const evidenceWorkflow = workflow === 'practice-entry' || workflow === 'learning-evidence-entry' || workflow === 'question-entry' || workflow === 'exam-entry' || workflow === 'sectioned-exam-entry' || workflow === 'custom-sectioned-exam-entry'
    const nextMessages = evidenceWorkflow ? [...studentMessages, message.trim()] : null
    const profileSelection = ['practice-entry', 'exam-entry', 'sectioned-exam-entry', 'custom-sectioned-exam-entry'].includes(workflow)
      ? (() => {
          const [scoring_profile_id, version] = scoringProfileRef.split('@')
          return { scoring_profile_id, scoring_profile_version: Number(version) }
        })()
      : {}
    requestId.current = id
    setAnswer('')
    setError('')
    setNotice('')
    setBusy(true)
    try {
      if (provider === 'local') {
        let context = ''
        if (!evidenceWorkflow) {
          const [insights, sessions] = await Promise.all([api.questions.insights(), api.practice.insights()])
          context = summarizeStudyAgentContext(insights, sessions)
        }
        const result = await api.studyAgent.local({
          consent: true,
          message: message.trim(),
          context,
          language,
          workflow,
          ...(evidenceWorkflow ? { messages: nextMessages } : {}),
          ...(workflow === 'learning-evidence-entry' ? { expected_evidence_field: expectedEvidenceField, state_token: learningEvidenceStateToken } : {}),
          ...(workflow === 'question-entry' ? { expected_question_field: expectedQuestionField, question_state_token: questionStateToken } : {}),
          ...(workflow === 'exam-entry' ? { expected_exam_field: expectedExamField, exam_state_token: examStateToken } : {}),
          ...(workflow === 'sectioned-exam-entry' ? { expected_sectioned_exam_field: expectedSectionedExamField, sectioned_exam_state_token: sectionedExamStateToken } : {}),
          ...(workflow === 'custom-sectioned-exam-entry' ? { expected_custom_exam_field: expectedCustomExamField, custom_exam_state_token: customExamStateToken } : {}),
          ...profileSelection,
          endpoint: settings.litellm_base_url,
          model_name: settings.model_name,
          has_api_key: settings.has_api_key,
        })
        if (workflow === 'practice-entry') {
          displayPracticeDraft(nextMessages, result)
        } else if (workflow === 'learning-evidence-entry') {
          displayLearningEvidenceDraft(nextMessages, result)
        } else if (workflow === 'question-entry') {
          displayQuestionDraft(nextMessages, result)
        } else if (workflow === 'exam-entry') {
          displayExamDraft(nextMessages, result)
        } else if (workflow === 'sectioned-exam-entry') {
          displaySectionedExamDraft(nextMessages, result)
        } else if (workflow === 'custom-sectioned-exam-entry') {
          displayCustomSectionedExamDraft(nextMessages, result)
        } else {
          setAnswer(result.answer)
          setMessage('')
        }
      } else {
        const result = await desktop().chat({ requestId: id, message: message.trim(), model, language, workflow, messages: nextMessages || [], ...profileSelection, ...(workflow === 'learning-evidence-entry' ? { expected_evidence_field: expectedEvidenceField, state_token: learningEvidenceStateToken } : {}), ...(workflow === 'question-entry' ? { expected_question_field: expectedQuestionField, question_state_token: questionStateToken } : {}), ...(workflow === 'exam-entry' ? { expected_exam_field: expectedExamField, exam_state_token: examStateToken } : {}), ...(workflow === 'sectioned-exam-entry' ? { expected_sectioned_exam_field: expectedSectionedExamField, sectioned_exam_state_token: sectionedExamStateToken } : {}), ...(workflow === 'custom-sectioned-exam-entry' ? { expected_custom_exam_field: expectedCustomExamField, custom_exam_state_token: customExamStateToken } : {}), consent: true })
        if (result.status === 'failed') {
          if (workflow === 'learning-evidence-entry') {
            setStudentMessages([])
            setExpectedEvidenceField('activity')
            setLearningEvidenceStateToken(null)
          }
          if (workflow === 'question-entry') {
            setStudentMessages([])
            setExpectedQuestionField('question_text')
            setQuestionStateToken(null)
          }
          if (workflow === 'exam-entry') {
            setStudentMessages([])
            setExpectedExamField('date')
            setExamStateToken(null)
          }
          if (workflow === 'sectioned-exam-entry') { setStudentMessages([]); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null) }
          if (workflow === 'custom-sectioned-exam-entry') { setStudentMessages([]); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null) }
          setError(result.detail)
        }
        if (result.status === 'cancelled') {
          if (workflow === 'learning-evidence-entry') {
            setStudentMessages([])
            setExpectedEvidenceField('activity')
            setLearningEvidenceStateToken(null)
          }
          if (workflow === 'question-entry') {
            setStudentMessages([])
            setExpectedQuestionField('question_text')
            setQuestionStateToken(null)
          }
          if (workflow === 'exam-entry') {
            setStudentMessages([])
            setExpectedExamField('date')
            setExamStateToken(null)
          }
          if (workflow === 'sectioned-exam-entry') { setStudentMessages([]); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null) }
          if (workflow === 'custom-sectioned-exam-entry') { setStudentMessages([]); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null) }
          setNotice(t('agent.cancelled'))
        }
        if (result.status === 'completed' && workflow === 'practice-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.practiceProposalInvalid'))
          displayPracticeDraft(nextMessages, result.draft)
        } else if (result.status === 'completed' && workflow === 'learning-evidence-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.learningEvidenceInvalid'))
          displayLearningEvidenceDraft(nextMessages, result.draft)
        } else if (result.status === 'completed' && workflow === 'question-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.questionCaptureInvalid'))
          displayQuestionDraft(nextMessages, result.draft)
        } else if (result.status === 'completed' && workflow === 'exam-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.examCaptureInvalid'))
          displayExamDraft(nextMessages, result.draft)
        } else if (result.status === 'completed' && workflow === 'sectioned-exam-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.sectionedExamInvalid'))
          displaySectionedExamDraft(nextMessages, result.draft)
        } else if (result.status === 'completed' && workflow === 'custom-sectioned-exam-entry') {
          if (!result.draft || !Array.isArray(result.draft.questions)) throw new Error(t('agent.customExamInvalid'))
          displayCustomSectionedExamDraft(nextMessages, result.draft)
        } else if (result.status === 'completed') setMessage('')
      }
    } catch (e) {
      if (workflow === 'learning-evidence-entry') {
        setStudentMessages([])
        setExpectedEvidenceField('activity')
        setLearningEvidenceStateToken(null)
        setPendingPreview(null)
      }
      if (workflow === 'question-entry') {
        setStudentMessages([])
        setExpectedQuestionField('question_text')
        setQuestionStateToken(null)
        setPendingPreview(null)
      }
      if (workflow === 'exam-entry') {
        setStudentMessages([])
        setExpectedExamField('date')
        setExamStateToken(null)
        setPendingPreview(null)
      }
      if (workflow === 'sectioned-exam-entry') { setStudentMessages([]); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null); setPendingPreview(null) }
      if (workflow === 'custom-sectioned-exam-entry') { setStudentMessages([]); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null); setPendingPreview(null) }
      setError(workflow === 'practice-entry' ? t('agent.practiceProposalInvalid') : workflow === 'learning-evidence-entry' ? t('agent.learningEvidenceInvalid') : workflow === 'question-entry' ? t('agent.questionCaptureInvalid') : workflow === 'exam-entry' ? t('agent.examCaptureInvalid') : workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamInvalid') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamInvalid') : e.response?.data?.detail || e.message || t('agent.requestError'))
    } finally {
      requestId.current = ''
      setBusy(false)
      setConsent(false)
    }
  }

  function displayPracticeDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? draft : null)
    const response = [
      ...(draft.proposal_mismatch ? [t('agent.practiceProposalMismatch')] : []),
      ...(draft.questions || []),
      ...(!draft.questions?.length ? [draft.conflicts.length ? t('agent.practiceConflictReview') : t('agent.practicePreviewReady')] : []),
    ]
    setAnswer(response.join('\n'))
  }

  function displayLearningEvidenceDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? draft : null)
    setExpectedEvidenceField(draft.expected_field || 'activity')
    setLearningEvidenceStateToken(draft.state_token || null)
    setAnswer(draft.preview_digest ? t('agent.learningEvidencePreviewReady') : (draft.questions || []).join('\n'))
  }

  function displayQuestionDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? draft : null)
    setExpectedQuestionField(draft.expected_field || 'question_text')
    setQuestionStateToken(draft.state_token || null)
    setAnswer(draft.preview_digest ? t('agent.questionCapturePreviewReady') : (draft.questions || []).join('\n'))
  }

  function displayExamDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? { ...draft, language } : null)
    setExpectedExamField(draft.expected_field || 'date')
    setExamStateToken(draft.state_token || null)
    setAnswer(draft.preview_digest ? t('agent.examCapturePreviewReady') : (draft.questions || []).join('\n'))
  }

  function displaySectionedExamDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? { ...draft, language } : null)
    setExpectedSectionedExamField(draft.expected_field || 'exam_type')
    setSectionedExamStateToken(draft.state_token || null)
    setAnswer(draft.preview_digest ? t('agent.sectionedExamPreviewReady') : (draft.questions || []).join('\n'))
  }

  function displayCustomSectionedExamDraft(messages, draft) {
    approvalRef.current = null
    setStudentMessages(messages)
    setMessage('')
    setPendingPreview(draft.preview_digest ? { ...draft, language } : null)
    setExpectedCustomExamField(draft.expected_field || 'format_name')
    setCustomExamStateToken(draft.state_token || null)
    setAnswer(draft.preview_digest ? t('agent.customExamPreviewReady') : (draft.questions || []).join('\n'))
  }

  async function approvePractice(duplicateChoice = null) {
    if (!pendingPreview || !window.confirm(t('agent.confirmPracticeSave'))) return
    const approvalKey = `${pendingPreview.preview_digest}:${duplicateChoice || 'default'}`
    if (approvalRef.current?.key !== approvalKey) {
      approvalRef.current = { key: approvalKey, id: window.crypto.randomUUID() }
    }
    setBusy(true)
    setError('')
    try {
      await api.practice.agentCreate({
        messages: studentMessages,
        language,
        proposal: pendingPreview.proposal,
        fields: pendingPreview.fields,
        scoring_profile_id: pendingPreview.scoring_profile_id,
        scoring_profile_version: pendingPreview.scoring_profile_version,
        scoring_profile_snapshot: pendingPreview.scoring_profile_snapshot,
        evidence: pendingPreview.evidence,
        evidence_claims: pendingPreview.evidence_claims,
        preview_digest: pendingPreview.preview_digest,
        approval_id: approvalRef.current.id,
        duplicate_choice: duplicateChoice,
      })
      approvalRef.current = null
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

  async function approveLearningEvidence() {
    if (!pendingPreview || !window.confirm(t('agent.confirmLearningEvidenceSave'))) return
    if (approvalRef.current?.digest !== pendingPreview.preview_digest) {
      approvalRef.current = { digest: pendingPreview.preview_digest, id: window.crypto.randomUUID() }
    }
    setBusy(true)
    setError('')
    try {
      await api.learningEvidence.agentCreate({
        messages: studentMessages,
        language: pendingPreview.language,
        evidence_claims: pendingPreview.evidence_claims,
        fields: pendingPreview.fields,
        evidence: pendingPreview.verified_evidence,
        preview_digest: pendingPreview.preview_digest,
        approval_id: approvalRef.current.id,
      })
      approvalRef.current = null
      setPendingPreview(null)
      setStudentMessages([])
      setExpectedEvidenceField('activity')
      setLearningEvidenceStateToken(null)
      setAnswer(t('agent.learningEvidenceSaved'))
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
      if (e.response?.status === 409) {
        setPendingPreview(null)
        approvalRef.current = null
        setStudentMessages([])
        setExpectedEvidenceField('activity')
        setLearningEvidenceStateToken(null)
      }
    } finally {
      setBusy(false)
    }
  }

  async function approveQuestionCapture() {
    if (!pendingPreview || !window.confirm(t('agent.confirmQuestionCaptureSave'))) return
    if (approvalRef.current?.digest !== pendingPreview.preview_digest) {
      approvalRef.current = { digest: pendingPreview.preview_digest, id: window.crypto.randomUUID() }
    }
    setBusy(true)
    setError('')
    try {
      await api.questions.agentCreate({
        messages: studentMessages,
        language: pendingPreview.language,
        evidence_claims: pendingPreview.evidence_claims,
        fields: pendingPreview.fields,
        evidence: pendingPreview.verified_evidence,
        preview_digest: pendingPreview.preview_digest,
        approval_id: approvalRef.current.id,
      })
      approvalRef.current = null
      setPendingPreview(null)
      setStudentMessages([])
      setExpectedQuestionField('question_text')
      setQuestionStateToken(null)
      setAnswer(t('agent.questionCaptureSaved'))
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
      if (e.response?.status === 409) {
        setPendingPreview(null)
        approvalRef.current = null
        setStudentMessages([])
        setExpectedQuestionField('question_text')
        setQuestionStateToken(null)
      }
    } finally {
      setBusy(false)
    }
  }

  async function approveExamCapture() {
    if (!pendingPreview || !window.confirm(t('agent.confirmExamCaptureSave'))) return
    if (approvalRef.current?.digest !== pendingPreview.preview_digest) {
      approvalRef.current = { digest: pendingPreview.preview_digest, id: window.crypto.randomUUID() }
    }
    setBusy(true)
    setError('')
    try {
      await api.exams.agentCreate({
        messages: studentMessages,
        language: pendingPreview.language,
        expected_exam_field: pendingPreview.evidence_claims.at(-1)?.field || 'date',
        state_token: pendingPreview.state_token,
        scoring_profile_id: pendingPreview.scoring_profile_snapshot.profile_id,
        scoring_profile_version: pendingPreview.scoring_profile_snapshot.version,
        evidence_claims: pendingPreview.evidence_claims,
        fields: pendingPreview.fields,
        evidence: pendingPreview.verified_evidence,
        scoring_profile_snapshot: pendingPreview.scoring_profile_snapshot,
        derived: pendingPreview.derived,
        preview_digest: pendingPreview.preview_digest,
        approval_id: approvalRef.current.id,
      })
      approvalRef.current = null
      setPendingPreview(null)
      setStudentMessages([])
      setExpectedExamField('date')
      setExamStateToken(null)
      setAnswer(t('agent.examCaptureSaved'))
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
      if (e.response?.status === 409) {
        setPendingPreview(null)
        approvalRef.current = null
        setStudentMessages([])
        setExpectedExamField('date')
        setExamStateToken(null)
      }
    } finally {
      setBusy(false)
    }
  }

  async function approveSectionedExamCapture() {
    if (!pendingPreview || !window.confirm(t('agent.confirmSectionedExamSave'))) return
    if (approvalRef.current?.digest !== pendingPreview.preview_digest) approvalRef.current = { digest: pendingPreview.preview_digest, id: window.crypto.randomUUID() }
    setBusy(true)
    setError('')
    try {
      await api.exams.sectionedAgentCreate({
        messages: studentMessages, language: pendingPreview.language,
        expected_exam_field: pendingPreview.evidence_claims.at(-1)?.field || 'exam_type',
        state_token: null,
        scoring_profile_id: pendingPreview.scoring_profile_snapshot.profile_id,
        scoring_profile_version: pendingPreview.scoring_profile_snapshot.version,
        evidence_claims: pendingPreview.evidence_claims, fields: pendingPreview.fields,
        evidence: pendingPreview.verified_evidence, scoring_profile_snapshot: pendingPreview.scoring_profile_snapshot,
        derived: pendingPreview.derived, preview_digest: pendingPreview.preview_digest, approval_id: approvalRef.current.id,
      })
      approvalRef.current = null; setPendingPreview(null); setStudentMessages([])
      setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null); setAnswer(t('agent.sectionedExamSaved'))
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
      if (e.response?.status === 409) { setPendingPreview(null); approvalRef.current = null; setStudentMessages([]); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null) }
    } finally { setBusy(false) }
  }

  async function approveCustomSectionedExamCapture() {
    if (!pendingPreview || !window.confirm(t('agent.confirmCustomExamSave'))) return
    if (approvalRef.current?.digest !== pendingPreview.preview_digest) approvalRef.current = { digest: pendingPreview.preview_digest, id: window.crypto.randomUUID() }
    setBusy(true)
    setError('')
    try {
      await api.exams.customSectionedAgentCreate({
        messages: studentMessages, language: pendingPreview.language,
        expected_exam_field: pendingPreview.evidence_claims.at(-1)?.field || 'format_name', state_token: null,
        scoring_profile_id: pendingPreview.scoring_profile_snapshot.profile_id,
        scoring_profile_version: pendingPreview.scoring_profile_snapshot.version,
        evidence_claims: pendingPreview.evidence_claims, fields: pendingPreview.fields,
        evidence: pendingPreview.verified_evidence, scoring_profile_snapshot: pendingPreview.scoring_profile_snapshot,
        derived: pendingPreview.derived, preview_digest: pendingPreview.preview_digest, approval_id: approvalRef.current.id,
      })
      approvalRef.current = null; setPendingPreview(null); setStudentMessages([])
      setExpectedCustomExamField('format_name'); setCustomExamStateToken(null); setAnswer(t('agent.customExamSaved'))
    } catch (e) {
      setError(e.response?.data?.detail || e.message || t('agent.requestError'))
      if (e.response?.status === 409) { setPendingPreview(null); approvalRef.current = null; setStudentMessages([]); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null) }
    } finally { setBusy(false) }
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
        <label className="block text-sm text-canvas-muted">{t('agent.workflow')}<select value={workflow} disabled={busy} onChange={(event) => { setWorkflow(event.target.value); setStudentMessages([]); setExpectedEvidenceField('activity'); setLearningEvidenceStateToken(null); setExpectedQuestionField('question_text'); setQuestionStateToken(null); setExpectedExamField('date'); setExamStateToken(null); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null); setPendingPreview(null); approvalRef.current = null; setAnswer(''); setError('') }} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="chat">{t('agent.workflowChat')}</option><option value="practice-entry">{t('agent.workflowPractice')}</option><option value="learning-evidence-entry">{t('agent.workflowLearningEvidence')}</option><option value="question-entry">{t('agent.workflowQuestion')}</option><option value="exam-entry">{t('agent.workflowExam')}</option><option value="sectioned-exam-entry">{t('agent.workflowSectionedExam')}</option><option value="custom-sectioned-exam-entry">{t('agent.workflowCustomExam')}</option></select></label>
        </div>
        {workflow === 'practice-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.practiceEntryHint')}</p>}
        {workflow === 'learning-evidence-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.learningEvidenceHint')}</p>}
        {workflow === 'question-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.questionCaptureHint')}</p>}
        {workflow === 'exam-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.examCaptureHint')}</p>}
        {workflow === 'sectioned-exam-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.sectionedExamHint')}</p>}
        {workflow === 'custom-sectioned-exam-entry' && <p className="mt-3 text-sm leading-relaxed text-canvas-muted">{t('agent.customExamHint')}</p>}
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
        {workflow !== 'chat' && studentMessages.length > 0 && <ol className="max-h-48 space-y-2 overflow-auto rounded-lg bg-canvas-base p-3 text-sm text-canvas-muted" aria-label={workflow === 'practice-entry' ? t('agent.workflowPractice') : workflow === 'learning-evidence-entry' ? t('agent.workflowLearningEvidence') : workflow === 'question-entry' ? t('agent.workflowQuestion') : t('agent.workflowExam')}>{studentMessages.map((item, index) => <li key={index} className="whitespace-pre-wrap">{item}</li>)}</ol>}
        {['practice-entry', 'exam-entry', 'sectioned-exam-entry', 'custom-sectioned-exam-entry'].includes(workflow) && <label className="block text-sm text-canvas-muted">{t('study.scoringProfile')}<select aria-label={t('study.scoringProfile')} required value={scoringProfileRef} onChange={(event) => { setScoringProfileRef(event.target.value); setPendingPreview(null); approvalRef.current = null }} className="mt-1 w-full rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text"><option value="">{t('study.chooseScoringProfile')}</option>{profiles.map((item) => <option key={`${item.profile_id}@${item.version}`} value={`${item.profile_id}@${item.version}`}>{item.display_name} · v{item.version}</option>)}</select></label>}
        <label className="block text-sm text-canvas-muted">{workflow === 'practice-entry' ? t('agent.practiceEntryPrompt') : workflow === 'learning-evidence-entry' ? t('agent.learningEvidencePrompt') : workflow === 'question-entry' ? t('agent.questionCapturePrompt') : workflow === 'exam-entry' ? t('agent.examCapturePrompt') : workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamPrompt') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamPrompt') : t('agent.question')}<textarea value={message} onChange={(event) => { setMessage(event.target.value); if (workflow !== 'chat') { setPendingPreview(null); approvalRef.current = null } }} maxLength={4000} rows={4} className="mt-1 w-full resize-y rounded-lg border border-canvas-line bg-canvas-base px-3 py-2 text-canvas-text" placeholder={workflow === 'practice-entry' ? t('agent.practiceEntryPrompt') : workflow === 'learning-evidence-entry' ? t('agent.learningEvidencePrompt') : workflow === 'question-entry' ? t('agent.questionCapturePrompt') : workflow === 'exam-entry' ? t('agent.examCapturePrompt') : workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamPrompt') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamPrompt') : t('agent.questionPlaceholder')} /></label>
        <label className="flex items-start gap-2 text-xs leading-relaxed text-canvas-muted"><input type="checkbox" checked={consent} onChange={(event) => { const accepted = event.target.checked; consentedSettings.current = accepted && provider === 'local' ? settings : null; setConsent(accepted) }} className="mt-0.5 accent-canvas-accent" />{workflow === 'practice-entry' ? provider === 'chatgpt' ? t('agent.practiceEntryConsent') : t('agent.practiceEntryLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : workflow === 'learning-evidence-entry' ? provider === 'chatgpt' ? t('agent.learningEvidenceConsent') : t('agent.learningEvidenceLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : workflow === 'question-entry' ? provider === 'chatgpt' ? t('agent.questionCaptureConsent') : t('agent.questionCaptureLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : workflow === 'exam-entry' ? provider === 'chatgpt' ? t('agent.examCaptureConsent') : t('agent.examCaptureLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : workflow === 'sectioned-exam-entry' ? provider === 'chatgpt' ? t('agent.sectionedExamConsent') : t('agent.sectionedExamLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : workflow === 'custom-sectioned-exam-entry' ? provider === 'chatgpt' ? t('agent.customExamConsent') : t('agent.customExamLocalConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') }) : provider === 'chatgpt' ? t('agent.consent') : t('agent.localConsent', { endpoint: configuredEndpoint, key: settings?.has_api_key ? t('agent.localKeySent') : t('agent.localNoKey') })}</label>
        <div className="flex gap-2">{busy ? provider === 'chatgpt' ? <button type="button" onClick={cancel} className="inline-flex items-center gap-2 rounded-lg border border-canvas-line px-4 py-2 text-sm text-canvas-text"><Square size={14} />{t('agent.cancel')}</button> : <p role="status" className="text-sm text-canvas-muted">{t('agent.working')}</p> : <button type="button" onClick={send} disabled={!consent || (['practice-entry', 'exam-entry', 'sectioned-exam-entry', 'custom-sectioned-exam-entry'].includes(workflow) && !scoringProfileRef) || (provider === 'local' && (settingsOpen || consentedSettings.current !== settings)) || !message.trim() || (provider === 'chatgpt' && !model)} className="inline-flex items-center gap-2 rounded-lg bg-canvas-accent px-4 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50"><Send size={14} />{t('agent.send')}</button>}</div>
        {answer && <div className="whitespace-pre-wrap rounded-lg bg-canvas-base p-4 text-sm leading-relaxed text-canvas-text" aria-live="polite">{answer}</div>}
        {pendingPreview && <div className="space-y-3 rounded-xl border border-canvas-line bg-canvas-base p-4">
          {workflow === 'exam-entry' || workflow === 'sectioned-exam-entry' || workflow === 'custom-sectioned-exam-entry' ? <>
            <div><h2 className="font-semibold text-canvas-text">{workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamPreviewTitle') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamPreviewTitle') : t('agent.examCapturePreviewTitle')}</h2><p className="mt-1 text-xs text-canvas-muted">{workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamNoWrite') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamNoWrite') : t('agent.examCaptureNoWrite')}</p></div>
            <p className="rounded-lg bg-canvas-panel p-3 text-sm text-canvas-muted">{t('agent.examCaptureScoringRule', {
              profile: pendingPreview.scoring_profile_snapshot.display_name,
              version: pendingPreview.scoring_profile_snapshot.version,
              correct: pendingPreview.scoring_profile_snapshot.scoring_rule.correct_points,
              penalty: pendingPreview.scoring_profile_snapshot.scoring_rule.wrong_penalty,
              blank: pendingPreview.scoring_profile_snapshot.scoring_rule.blank_points,
            })}</p>
            <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(pendingPreview.fields).filter(([field]) => field !== 'sections' && field !== 'scoring_profile_id' && field !== 'scoring_profile_version').map(([field, value]) => <div key={field} className="rounded-lg bg-canvas-panel p-3"><dt className="text-xs text-canvas-muted">{t(`agent.examCapture.${field}`)}</dt><dd className="mt-1 break-words text-sm text-canvas-text">{value ?? t('agent.examCaptureOmitted')}</dd>{pendingPreview.verified_evidence[field] && <dd className="mt-2 border-t border-canvas-line pt-2 text-xs text-canvas-muted">{t('agent.provenance')}: “{pendingPreview.verified_evidence[field].quote}”</dd>}</div>)}</dl>
            {(workflow === 'sectioned-exam-entry' || workflow === 'custom-sectioned-exam-entry') && <ol className="space-y-2">{pendingPreview.fields.sections.map((section, index) => <li key={index} className="rounded-lg bg-canvas-panel p-3"><strong>{index + 1}. {section.subject}</strong><div className="mt-1 text-sm text-canvas-muted">{t('agent.sectionedExamCounts', { correct: section.correct, incorrect: section.incorrect, blank: section.blank })}</div>{['subject', 'correct', 'incorrect', 'blank'].map((field) => { const key = `section_${index + 1}_${field}`; const quote = pendingPreview.verified_evidence[key]?.quote; return quote ? <div key={key} className="mt-1 text-xs text-canvas-muted">{t(`agent.examCapture.${field}`)}: “{quote}”</div> : null })}</li>)}</ol>}
            <div className="rounded-lg bg-canvas-panel p-3 text-sm text-canvas-text">{t('agent.examCaptureDerived', { net: pendingPreview.derived.net, xp: pendingPreview.derived.xp })}</div>
            <div className="flex flex-wrap gap-2"><button type="button" onClick={workflow === 'sectioned-exam-entry' ? approveSectionedExamCapture : workflow === 'custom-sectioned-exam-entry' ? approveCustomSectionedExamCapture : approveExamCapture} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{workflow === 'sectioned-exam-entry' ? t('agent.sectionedExamSave') : workflow === 'custom-sectioned-exam-entry' ? t('agent.customExamSave') : t('agent.examCaptureSave')}</button><button type="button" onClick={() => { setPendingPreview(null); approvalRef.current = null; setStudentMessages([]); setExpectedExamField('date'); setExamStateToken(null); setExpectedSectionedExamField('exam_type'); setSectionedExamStateToken(null); setExpectedCustomExamField('format_name'); setCustomExamStateToken(null); setAnswer(t('agent.examCaptureCancelled')) }} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50">{t('agent.examCaptureCancel')}</button></div>
          </> : workflow === 'question-entry' ? <>
            <div><h2 className="font-semibold text-canvas-text">{t('agent.questionCapturePreviewTitle')}</h2><p className="mt-1 text-xs text-canvas-muted">{t('agent.questionCaptureNoWrite')}</p></div>
            <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(pendingPreview.fields).map(([field, value]) => <div key={field} className="rounded-lg bg-canvas-panel p-3"><dt className="text-xs text-canvas-muted">{t(`agent.questionCapture.${field}`)}</dt><dd className="mt-1 break-words whitespace-pre-wrap text-sm text-canvas-text">{value || t('agent.questionCaptureOmitted')}</dd>{pendingPreview.verified_evidence[field] && <dd className="mt-2 border-t border-canvas-line pt-2 text-xs text-canvas-muted">{t('agent.provenance')}: “{pendingPreview.verified_evidence[field].quote}”</dd>}</div>)}</dl>
            <div className="flex flex-wrap gap-2"><button type="button" onClick={approveQuestionCapture} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.questionCaptureSave')}</button><button type="button" onClick={() => { setPendingPreview(null); approvalRef.current = null; setStudentMessages([]); setExpectedQuestionField('question_text'); setQuestionStateToken(null); setAnswer(t('agent.questionCaptureCancelled')) }} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50">{t('agent.questionCaptureCancel')}</button></div>
          </> : workflow === 'learning-evidence-entry' ? <>
            <div><h2 className="font-semibold text-canvas-text">{t('agent.learningEvidencePreviewTitle')}</h2><p className="mt-1 text-xs text-canvas-muted">{t('agent.learningEvidenceNoWrite')}</p></div>
            <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(pendingPreview.fields).map(([field, value]) => <div key={field} className="rounded-lg bg-canvas-panel p-3"><dt className="text-xs text-canvas-muted">{t(`agent.learningEvidence.${field}`)}</dt><dd className="mt-1 break-words text-sm text-canvas-text">{value || t('agent.learningEvidenceOmitted')}</dd>{pendingPreview.verified_evidence[field] && <dd className="mt-2 border-t border-canvas-line pt-2 text-xs text-canvas-muted">{t('agent.provenance')}: “{pendingPreview.verified_evidence[field].quote}”</dd>}</div>)}</dl>
            <div className="flex flex-wrap gap-2"><button type="button" onClick={approveLearningEvidence} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.learningEvidenceSave')}</button><button type="button" onClick={() => { setPendingPreview(null); approvalRef.current = null; setStudentMessages([]); setExpectedEvidenceField('activity'); setLearningEvidenceStateToken(null); setAnswer(t('agent.learningEvidenceCancelled')) }} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50">{t('agent.learningEvidenceCancel')}</button></div>
          </> : <>
            <div><h2 className="font-semibold text-canvas-text">{t('agent.practicePreviewTitle')}</h2><p className="mt-1 text-xs text-canvas-muted">{t('agent.practiceNoWrite')}</p></div>
            <p className="rounded-lg bg-canvas-panel p-3 text-sm text-canvas-muted">{t('agent.practiceScoringRule', {
              profile: pendingPreview.scoring_profile_snapshot.display_name,
              version: pendingPreview.scoring_profile_snapshot.version,
              correct: pendingPreview.scoring_profile_snapshot.scoring_rule.correct_points,
              penalty: pendingPreview.scoring_profile_snapshot.scoring_rule.wrong_penalty,
              blank: pendingPreview.scoring_profile_snapshot.scoring_rule.blank_points,
            })}</p>
            <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(pendingPreview.fields).map(([field, value]) => <div key={field} className="rounded-lg bg-canvas-panel p-3"><dt className="text-xs text-canvas-muted">{t(`agent.practice.${field}`)}</dt><dd className="mt-1 break-words text-sm text-canvas-text">{value}</dd><dd className="mt-2 border-t border-canvas-line pt-2 text-xs text-canvas-muted">{t('agent.provenance')}: “{pendingPreview.evidence[field].quote}”</dd></div>)}</dl>
            {pendingPreview.conflicts.length > 0 && <div className="rounded-lg border border-canvas-line p-3"><h3 className="text-sm font-semibold text-canvas-text">{t('agent.practice.conflicts')}</h3><ul className="mt-2 space-y-1 text-xs text-canvas-muted">{pendingPreview.conflicts.map((item) => <li key={item.id}>{item.date} · {item.subject} / {item.topic} · {item.correct}/{item.incorrect}/{item.blank}</li>)}</ul></div>}
            <div className="flex flex-wrap gap-2">{pendingPreview.conflicts.length === 0 ? <button type="button" onClick={() => approvePractice()} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.practiceSave')}</button> : <button type="button" onClick={() => approvePractice('new')} disabled={busy} className="rounded-lg bg-canvas-accent px-3 py-2 text-sm font-semibold text-canvas-base disabled:opacity-50">{t('agent.practiceSaveNew')}</button>}<button type="button" onClick={() => setPendingPreview(null)} disabled={busy} className="rounded-lg border border-canvas-line px-3 py-2 text-sm text-canvas-text disabled:opacity-50">{t('agent.practiceCancel')}</button></div>
          </>}
        </div>}
      </div>}

      {notice && <p role="status" className="text-sm text-canvas-muted">{notice}</p>}
      {error && <p role="alert" className="rounded-lg border border-canvas-line bg-canvas-raise p-3 text-sm text-canvas-text">{error}</p>}
    </section>
  )
}
