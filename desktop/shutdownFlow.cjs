async function gracefulStop({ requestShutdown, waitForExit }) {
  const response = await requestShutdown()
  if (!response.ok) throw new Error(`Backend rejected graceful shutdown (${response.status})`)
  await waitForExit()
}

module.exports = { gracefulStop }
