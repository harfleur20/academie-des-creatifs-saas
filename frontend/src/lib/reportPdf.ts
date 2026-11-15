const JSPDF_SRC = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js'

type PdfPageSize = {
  getWidth: () => number
  getHeight: () => number
}

type PdfDocument = {
  internal: { pageSize: PdfPageSize }
  setFont: (family: string, style?: string) => void
  setFontSize: (size: number) => void
  setTextColor: (r: number, g?: number, b?: number) => void
  setDrawColor: (r: number, g?: number, b?: number) => void
  setLineWidth: (width: number) => void
  text: (text: string | string[], x: number, y: number, options?: Record<string, unknown>) => void
  line: (x1: number, y1: number, x2: number, y2: number) => void
  roundedRect: (x: number, y: number, w: number, h: number, rx: number, ry: number, style?: string) => void
  setFillColor: (r: number, g?: number, b?: number) => void
  addImage: (imageData: string, format: string, x: number, y: number, w: number, h: number) => void
  splitTextToSize: (text: string, maxWidth: number) => string[]
  addPage: () => void
  getNumberOfPages: () => number
  setPage: (pageNumber: number) => void
  save: (filename: string) => void
}

type PdfConstructor = new (options?: Record<string, unknown>) => PdfDocument

type ReportPdfOptions = {
  schoolName: string
  schoolLogoUrl?: string | null
  title: string
  subtitle?: string
  filename: string
  sections: Array<{
    title: string
    rows: Array<{ label: string; value: string }>
  }>
}

let jspdfLoading: Promise<PdfConstructor> | null = null

function getPdfConstructor() {
  const namespace = (window as Window & { jspdf?: { jsPDF?: PdfConstructor } }).jspdf
  return namespace?.jsPDF ?? null
}

async function loadJsPdf(): Promise<PdfConstructor> {
  const existing = getPdfConstructor()
  if (existing) return existing
  if (jspdfLoading) return jspdfLoading

  jspdfLoading = new Promise<PdfConstructor>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = JSPDF_SRC
    script.async = true
    script.onload = () => {
      const constructor = getPdfConstructor()
      if (constructor) resolve(constructor)
      else reject(new Error('La bibliothèque PDF ne s’est pas initialisée.'))
    }
    script.onerror = () => reject(new Error('Impossible de charger la bibliothèque PDF.'))
    document.head.appendChild(script)
  }).catch((error) => {
    jspdfLoading = null
    throw error
  })

  return jspdfLoading
}

async function imageUrlToDataUrl(url?: string | null) {
  if (!url) return null
  try {
    const response = await fetch(url)
    if (!response.ok) return null
    const blob = await response.blob()
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
      reader.onerror = () => resolve(null)
      reader.readAsDataURL(blob)
    })
  } catch {
    return null
  }
}

function imageFormat(dataUrl: string) {
  if (dataUrl.startsWith('data:image/jpeg')) return 'JPEG'
  if (dataUrl.startsWith('data:image/webp')) return 'WEBP'
  return 'PNG'
}

function safeFilename(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
}

export async function downloadSchoolReportPdf(options: ReportPdfOptions) {
  const JsPdf = await loadJsPdf()
  const doc = new JsPdf({ unit: 'mm', format: 'a4' })
  const logo = await imageUrlToDataUrl(options.schoolLogoUrl)
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  const left = 16
  const right = 16
  const contentWidth = pageWidth - left - right
  const bottomLimit = pageHeight - 18
  const generatedAt = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date())

  function drawHeader() {
    if (logo) {
      try {
        doc.addImage(logo, imageFormat(logo), left, 10, 18, 18)
      } catch {
        // A malformed or unsupported school logo must not block report export.
      }
    }

    const textLeft = logo ? left + 24 : left
    doc.setTextColor(16, 33, 61)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(13)
    doc.text(options.schoolName, textLeft, 16)
    doc.setFontSize(9)
    doc.setTextColor(92, 108, 132)
    doc.text(options.title, textLeft, 22)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.text(generatedAt, pageWidth - right, 16, { align: 'right' })
    doc.setDrawColor(224, 230, 239)
    doc.setLineWidth(0.4)
    doc.line(left, 32, pageWidth - right, 32)
  }

  function addPage() {
    doc.addPage()
    drawHeader()
    return 42
  }

  function ensureSpace(y: number, required: number) {
    return y + required > bottomLimit ? addPage() : y
  }

  drawHeader()
  let y = 44

  if (options.subtitle) {
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(101, 116, 138)
    doc.setFontSize(9)
    const lines = doc.splitTextToSize(options.subtitle, contentWidth)
    doc.text(lines, left, y)
    y += lines.length * 4.5 + 7
  }

  options.sections.forEach((section) => {
    y = ensureSpace(y, 18)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(16, 33, 61)
    doc.setFontSize(11)
    doc.text(section.title, left, y)
    y += 6

    section.rows.forEach((row) => {
      const valueLines = doc.splitTextToSize(row.value || '-', contentWidth - 54)
      const rowHeight = Math.max(12, valueLines.length * 4.3 + 6)
      y = ensureSpace(y, rowHeight + 2)

      doc.setFillColor(247, 249, 252)
      doc.setDrawColor(230, 235, 242)
      doc.roundedRect(left, y, contentWidth, rowHeight, 2.5, 2.5, 'FD')

      doc.setFont('helvetica', 'bold')
      doc.setTextColor(64, 80, 103)
      doc.setFontSize(8.5)
      doc.text(row.label, left + 4, y + 7)

      doc.setFont('helvetica', 'normal')
      doc.setTextColor(91, 107, 130)
      doc.text(valueLines, left + 54, y + 7)
      y += rowHeight + 3
    })

    y += 5
  })

  const totalPages = doc.getNumberOfPages()
  for (let page = 1; page <= totalPages; page += 1) {
    doc.setPage(page)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(132, 144, 162)
    doc.text(`${page}/${totalPages}`, pageWidth - right, pageHeight - 8, { align: 'right' })
  }

  const datedFilename = `${safeFilename(options.filename)}-${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(datedFilename)
}
