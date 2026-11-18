export function questionOrderGroupKey(group) {
  return JSON.stringify([group.exam_type || '', group.format_name || '', group.subject || ''])
}
