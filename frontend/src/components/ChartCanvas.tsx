import { useEffect, useRef, useState } from 'react'
import '../chartjs-polish.css'

type ChartKind = 'bar' | 'line' | 'doughnut'

type ChartDataset = {
  label: string
  data: number[]
}

type ChartCanvasProps = {
  type: ChartKind
  labels: string[]
  datasets: ChartDataset[]
  height?: number
  compact?: boolean
  horizontal?: boolean
  showLegend?: boolean
  max?: number
  valueSuffix?: string
}

type ChartInstance = { destroy: () => void }

const CHART_JS_SOURCE = 'https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js'
let chartJsPromise: Promise<AcademieChartConstructor | null> | null = null

function ensureChartJs() {
  if (window.Chart) return Promise.resolve(window.Chart)
  if (chartJsPromise) return chartJsPromise

  chartJsPromise = new Promise((resolve) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-academie-chartjs]')
    const finish = () => resolve(window.Chart ?? null)
    const fail = () => resolve(null)

    if (existing) {
      existing.addEventListener('load', finish, { once: true })
      existing.addEventListener('error', fail, { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = CHART_JS_SOURCE
    script.async = true
    script.dataset.academieChartjs = 'true'
    script.addEventListener('load', finish, { once: true })
    script.addEventListener('error', fail, { once: true })
    document.head.appendChild(script)
  })

  return chartJsPromise
}

function cssColor(scope: Element, name: string, fallback: string) {
  const value = getComputedStyle(scope).getPropertyValue(name).trim()
  return value || fallback
}

export function ChartCanvas({
  type,
  labels,
  datasets,
  height = 280,
  compact = false,
  horizontal = false,
  showLegend = false,
  max,
  valueSuffix = '',
}: ChartCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [libraryReady, setLibraryReady] = useState(true)
  const labelsKey = JSON.stringify(labels)
  const datasetsKey = JSON.stringify(datasets)

  useEffect(() => {
    let active = true
    let instance: ChartInstance | null = null

    void ensureChartJs().then((ChartConstructor) => {
      const canvas = canvasRef.current
      if (!active) return
      if (!canvas || !ChartConstructor) {
        setLibraryReady(false)
        return
      }
      setLibraryReady(true)

      const scope = canvas.closest('.saas-app') ?? document.documentElement
      const primary = cssColor(scope, '--blue', '#25308f')
      const secondary = cssColor(scope, '--green', '#14a76c')
      const accent = cssColor(scope, '--tenant-accent', '#22c55e')
      const palette = [primary, secondary, accent, '#64748b', '#94a3b8', '#0ea5e9']

      instance = new ChartConstructor(canvas, {
        type,
        data: {
          labels,
          datasets: datasets.map((dataset, index) => ({
            ...dataset,
            borderColor: type === 'doughnut' ? '#ffffff' : palette[index % palette.length],
            backgroundColor: type === 'doughnut'
              ? labels.map((_, labelIndex) => palette[labelIndex % palette.length])
              : palette[index % palette.length],
            borderWidth: type === 'doughnut' ? 3 : type === 'line' ? 3 : 0,
            borderRadius: type === 'bar' ? 8 : undefined,
            borderSkipped: false,
            fill: false,
            tension: type === 'line' ? 0.38 : undefined,
            pointRadius: type === 'line' ? (compact ? 0 : 3) : undefined,
            pointHoverRadius: type === 'line' ? 5 : undefined,
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: horizontal ? 'y' : 'x',
          animation: {
            duration: compact ? 650 : 950,
            easing: 'easeOutQuart',
          },
          interaction: {
            intersect: false,
            mode: type === 'doughnut' ? 'nearest' : 'index',
          },
          plugins: {
            legend: {
              display: showLegend && (type === 'doughnut' || datasets.length > 1),
              position: 'bottom',
              labels: {
                usePointStyle: true,
                boxWidth: 8,
                padding: 16,
              },
            },
            tooltip: {
              enabled: !compact,
              displayColors: type === 'doughnut' || datasets.length > 1,
              callbacks: {
                label: (context: {
                  dataset: { label?: string }
                  label?: string
                  parsed: number | { x?: number; y?: number }
                }) => {
                  const numeric = typeof context.parsed === 'number'
                    ? context.parsed
                    : horizontal
                      ? context.parsed.x
                      : context.parsed.y
                  const label = type === 'doughnut'
                    ? context.label ? `${context.label} : ` : ''
                    : context.dataset.label ? `${context.dataset.label} : ` : ''
                  return `${label}${numeric ?? 0}${valueSuffix}`
                },
              },
            },
          },
          cutout: type === 'doughnut' ? (compact ? '70%' : '72%') : undefined,
          scales: type === 'doughnut' ? undefined : {
            x: {
              display: !compact,
              beginAtZero: horizontal,
              suggestedMax: horizontal ? max : undefined,
              max: horizontal ? max : undefined,
              grid: { display: false },
              ticks: {
                maxRotation: 0,
                autoSkip: !horizontal,
                color: '#64748b',
                font: { size: 11 },
                callback: horizontal
                  ? (value: string | number) => `${value}${valueSuffix}`
                  : undefined,
              },
            },
            y: {
              display: !compact,
              beginAtZero: !horizontal,
              suggestedMax: horizontal ? undefined : max,
              max: horizontal ? undefined : max,
              grid: { color: 'rgba(148, 163, 184, 0.16)' },
              ticks: {
                color: '#64748b',
                font: { size: 11 },
                callback: horizontal
                  ? undefined
                  : (value: string | number) => `${value}${valueSuffix}`,
              },
            },
          },
        },
      }) as ChartInstance
    })

    return () => {
      active = false
      instance?.destroy()
    }
  }, [type, labelsKey, datasetsKey, height, compact, horizontal, showLegend, max, valueSuffix])

  if (!libraryReady) {
    return <div className="chart-library-fallback">Graphique momentanément indisponible.</div>
  }

  return (
    <div className={`chart-canvas-wrap${compact ? ' is-compact' : ''}`} style={{ height }}>
      <canvas ref={canvasRef} />
    </div>
  )
}
