/** Convert elapsed timer milliseconds into the persisted PracticeSession duration fields. */
export function practiceDurationFromElapsedMilliseconds(elapsedMs) {
  const totalSeconds = Math.floor(Math.max(0, Number(elapsedMs) || 0) / 1000)
  return {
    duration_minutes: Math.floor(totalSeconds / 60),
    duration_seconds: totalSeconds % 60,
  }
}
