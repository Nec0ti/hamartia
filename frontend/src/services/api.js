/**
 * Central API client for the Hamartia frontend.
 *
 * The base URL points at the FastAPI backend (Phase 3). It is overridable via
 * the Vite env var VITE_API_BASE so the same code works in dev (where Vite
 * proxies to the backend) and after a production deploy. Endpoints mirror the
 * router mount paths on the backend exactly: /exams, /questions, /cosmos,
 * /agent, /settings, /healthcheck.
 */
import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

/* ----------------------------- exams ------------------------------------ */

export const exams = {
  list: () => client.get('/exams').then((r) => r.data),
  get: (id) => client.get(`/exams/${id}`).then((r) => r.data),
  create: (payload) =>
    client.post('/exams', payload).then((r) => r.data),
  remove: (id) => client.delete(`/exams/${id}`).then((r) => r.data),
}

/* ----------------------------- questions -------------------------------- */

export const questions = {
  list: () => client.get('/questions').then((r) => r.data),
  get: (id) => client.get(`/questions/${id}`).then((r) => r.data),
  upload: (file, ocrText) => {
    const fd = new FormData()
    fd.append('file', file, file.name)
    fd.append('ocr_text', ocrText || '')
    return client.post('/questions', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      transformRequest: [(d) => d],
    }).then((r) => r.data)
  },
  analyze: (id) =>
    client.patch(`/questions/${id}/analyze`).then((r) => r.data),
  tag: (id, hamartiaTag) =>
    client
      .patch(`/questions/${id}/tag`, { hamartia_tag: hamartiaTag })
      .then((r) => r.data),
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

/* -------------------------------- agent --------------------------------- */

export const agent = {
  chat: (message) =>
    client.post('/agent/chat', { message }).then((r) => r.data),
  ingest: (file) => {
    const fd = new FormData()
    fd.append('file', file, file.name)
    return client.post('/agent/documents', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      transformRequest: [(d) => d],
    }).then((r) => r.data)
  },
}

/* -------------------------------- settings ------------------------------- */

export const settings = {
  get: () => client.get('/settings').then((r) => r.data),
  update: (payload) =>
    client.patch('/settings', payload).then((r) => r.data),
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
export const handleApiError = (error) => {
  const status = error?.response?.status ?? 0
  const detail = error?.response?.data?.detail ?? error?.message ?? 'Request failed'
  return { ok: false, status, detail }
}

export default { exams, questions, cosmos, agent, settings, health }
