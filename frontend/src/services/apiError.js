export function handleApiError(error, t = (key) => key) {
  const status = error?.response?.status ?? 0
  let key = 'error.request'
  if (!status) key = 'error.network'
  else if (status === 400) key = 'error.badRequest'
  else if (status === 404) key = 'error.notFound'
  else if (status === 413 && error?.response?.data?.detail === 'analysis_payload_too_large') key = 'error.analysisPayloadTooLarge'
  else if (status === 413) key = 'error.fileTooLarge'
  else if (status === 415) key = 'error.fileType'
  else if (status === 422) key = 'error.invalidData'
  else if (status === 502) key = 'error.localAi'
  else if (status >= 500) key = 'error.server'
  return { ok: false, status, key, detail: t(key) }
}
