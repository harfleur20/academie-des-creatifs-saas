/**
 * A table as a CSV file Excel opens directly in French: semicolons, and a BOM so accents stay right.
 */
export function downloadCsv(fileName: string, header: string[], rows: Array<Array<string | number | null>>) {
  const cell = (value: string | number | null) => {
    const text = value === null ? '' : String(value)
    return /[;"\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const content = [header, ...rows].map((row) => row.map(cell).join(';')).join('\r\n')
  const blob = new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
