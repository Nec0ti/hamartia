// Valid 1x1 RGBA PNG used by the browser smoke's synthetic question record.
function dashboardExamHistory(count = 512) {
  const start = Date.UTC(2024, 0, 1)
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(start + index * 86_400_000).toISOString().slice(0, 10)
    return {
      id: `dashboard-benchmark-${String(index).padStart(4, '0')}`,
      date,
      exam_type: 'branch',
      subject: 'Mathematics',
      correct: (index * 13) % 61,
      incorrect: (index * 7 + 3) % 17,
      blank: (index * 5 + 1) % 21,
      duration_minutes: 45,
      duration_seconds: index % 60,
      created_at: `${date}T12:00:00.000Z`,
      sections: [],
      scoring_profile: {
        profile_id: 'legacy-yks',
        version: 1,
        display_name: 'YKS (legacy)',
        country_label: 'Türkiye',
        scoring_rule: { correct_points: '1/1', wrong_penalty: '1/4', blank_points: '0/1' },
      },
    }
  })
}

module.exports = {
  onePixelPng: Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==',
    'base64',
  ),
  dashboardExamHistory,
}
