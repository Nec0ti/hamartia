async function restoreWithRestart({ stop, restore, restart }) {
  let status = 'failed'
  try {
    await stop()
    status = (await restore()) === 'success' ? 'success' : 'failed'
  } catch {
    status = 'failed'
  }

  try {
    await restart()
  } catch {
    return 'restartFailed'
  }
  return status
}

module.exports = { restoreWithRestart }
