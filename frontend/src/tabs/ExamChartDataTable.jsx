import { examChartSummaryRows } from '../utils/examSections.js'

export default function ExamChartDataTable({ id, title, data, locale, t }) {
  const rows = examChartSummaryRows(data, locale, t)
  return <table id={id} className="sr-only">
    <caption>{t(title)} · {t('dashboard.chartDataSummary')}</caption>
    <thead><tr>
      <th scope="col">{t('exams.date')}</th>
      <th scope="col">{t('dashboard.chartExam')}</th>
      <th scope="col">{t('exams.net')}</th>
      <th scope="col">{t('dashboard.netChange')}</th>
    </tr></thead>
    <tbody>{rows.map((exam) => <tr key={exam.id}>
      <td>{exam.date}</td>
      <td>{exam.subject}</td>
      <td>{exam.net}</td>
      <td>{exam.change}</td>
    </tr>)}</tbody>
  </table>
}
