/**
 * Central API client for the Hamartia frontend.
 *
 * The base URL points at the FastAPI backend (Phase 3). It is overridable via
 * the Vite env var VITE_API_BASE so the same code works in dev (where Vite
 * proxies to the backend) and after a production deploy. Endpoints mirror the
 * router mount paths on the backend exactly: /exams, /questions, /cosmos,
 * /settings, /healthcheck.
 */
import axios from 'axios'
import { handleApiError } from './apiError.js'
import { getApiBase } from './apiBase.js'

export const API_BASE = getApiBase(import.meta.env)

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

/* ----------------------------- exams ------------------------------------ */

export const exams = {
  list: () => client.get('/exams').then((r) => r.data),
  agentDraft: (payload) => client.post('/exams/agent-draft', payload).then((r) => r.data),
  agentCreate: (payload) => client.post('/exams/agent-create', payload).then((r) => r.data),
  sectionedAgentCreate: (payload) => client.post('/exams/sectioned-agent-create', payload).then((r) => r.data),
  customSectionedAgentCreate: (payload) => client.post('/exams/custom-sectioned-agent-create', payload).then((r) => r.data),
  get: (id) => client.get(`/exams/${id}`).then((r) => r.data),
  create: (payload) =>
    client.post('/exams', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/exams/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/exams/${id}`).then((r) => r.data),
}

export const examProfiles = {
  list: () => client.get('/exam-profiles').then((r) => r.data),
  create: (payload) => client.post('/exam-profiles', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/exam-profiles/${encodeURIComponent(id)}`, payload).then((r) => r.data),
}

export const practice = {
  list: () => client.get('/practice').then((r) => r.data),
  insights: () => client.get('/practice/insights').then((r) => r.data),
  agentDraft: (payload) => client.post('/practice/agent-draft', payload).then((r) => r.data),
  agentCreate: (payload) => client.post('/practice/agent-create', payload).then((r) => r.data),
  create: (payload, idempotencyKey = null) => client.post('/practice', payload, {
    ...(idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : {}),
  }).then((r) => r.data),
  update: (id, payload) => client.put(`/practice/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/practice/${id}`).then((r) => r.data),
}

export const learningEvidence = {
  list: () => client.get('/learning-evidence').then((r) => r.data),
  create: (payload) => client.post('/learning-evidence', payload).then((r) => r.data),
  agentDraft: (payload) => client.post('/learning-evidence/agent-draft', payload).then((r) => r.data),
  agentCreate: (payload) => client.post('/learning-evidence/agent-create', payload).then((r) => r.data),
  update: (id, payload) => client.put(`/learning-evidence/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/learning-evidence/${id}`).then((r) => r.data),
}

export const clock = {
  get: () => client.get('/clock').then((r) => r.data),
  update: (payload) => client.patch('/clock', payload).then((r) => r.data),
}

export const studentProfile = {
  get: () => client.get('/student-profile').then((r) => r.data),
  save: (payload) => client.put('/student-profile', payload).then((r) => r.data),
  reset: () => client.delete('/student-profile').then((r) => r.data),
}

/* ----------------------------- questions -------------------------------- */

export const questions = {
  list: () => client.get('/questions').then((r) => r.data),
  agentDraft: (payload) => client.post('/questions/agent-draft', payload).then((r) => r.data),
  agentCreate: (payload) => client.post('/questions/agent-create', payload).then((r) => r.data),
  insights: (today) => client.get('/questions/insights', { params: today ? { today } : {} }).then((r) => r.data),
  get: (id) => client.get(`/questions/${id}`).then((r) => r.data),
  upload: (file, ocrText, subject, topic, examContext = {}, curriculumReference = {}) => {
    const fd = new FormData()
    if (file) fd.append('file', file, file.name)
    fd.append('ocr_text', ocrText || '')
    fd.append('subject', subject || '')
    fd.append('topic', topic || '')
    if (examContext.examId) fd.append('exam_id', examContext.examId)
    if (examContext.questionNumber) fd.append('question_number', examContext.questionNumber)
    if (examContext.solveOrder) fd.append('solve_order', examContext.solveOrder)
    if (examContext.timeSpentSeconds) fd.append('time_spent_seconds', examContext.timeSpentSeconds)
    fd.append('curriculum_reference_json', JSON.stringify(curriculumReference))
    return client.post('/questions', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      transformRequest: [(d) => d],
    }).then((r) => r.data)
  },
  update: (id, payload) => client.patch(`/questions/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/questions/${id}`).then((r) => r.data),
  analysisPreview: (id) =>
    client.post(`/questions/${id}/analysis-preview`).then((r) => r.data),
  cancelAnalysisPreview: (id, consentId) =>
    client.delete(`/questions/${id}/analysis-preview/${encodeURIComponent(consentId)}`),
  analyze: (id, consentId) =>
    client.post(`/questions/${id}/analyze`, { consent_id: consentId }).then((r) => r.data),
  tag: (id, hamartiaTag) =>
    client
      .patch(`/questions/${id}/tag`, { hamartia_tag: hamartiaTag })
      .then((r) => r.data),
  review: (id, reviewed = true) => client.patch(`/questions/${id}/review`, { reviewed }).then((r) => r.data),
  attempt: (id, correct, attemptDay) => client.post(`/questions/${id}/attempt`, { correct, attempt_day: attemptDay }).then((r) => r.data),
}

/* -------------------------------- cosmos -------------------------------- */

export const cosmos = {
  get: () => client.get('/cosmos').then((r) => r.data),
  addNode: (subject, tag, errorCount) =>
    client
      .post('/cosmos/nodes', { subject, tag, error_count: errorCount })
      .then((r) => r.data),
  assault: (id) => client.post(`/cosmos/nodes/${id}/assault`).then((r) => r.data),
  unlockSector: (sector) =>
    client.post(`/cosmos/sectors/${sector}`).then((r) => r.data),
}

/* -------------------------------- user / profile ----------------------- */

export const user = {
  get: () => client.get('/user').then((r) => r.data),
  update: (payload) => client.patch('/user', payload).then((r) => r.data),
}

/* -------------------------------- settings ------------------------------- */

export const settings = {
  get: () => client.get('/settings').then((r) => r.data),
  update: (payload) =>
    client.patch('/settings', payload).then((r) => r.data),
}

export const studyAgent = {
  local: (payload) => client.post('/study-agent/local', payload).then((r) => r.data),
}

/* --------------------------- healthcheck / misc ------------------------- */

export const health = {
  health: () => client.get('/healthcheck/health').then((r) => r.data),
  ready: () => client.get('/healthcheck/ready').then((r) => r.data),
}

/**
 * Small helper to surface API errors without crashing the tab. Returns a
 * human-readable message plus the HTTP status code.
 */
export { handleApiError }

export default { exams, examProfiles, practice, learningEvidence, clock, studentProfile, questions, cosmos, user, settings, studyAgent, health }
