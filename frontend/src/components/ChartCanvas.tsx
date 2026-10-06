import { useEffect, useRef, useState } from 'react'

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

function cssColor(name: string, fallback: string) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
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
    const canvas = canvasRef.current
    const ChartConstructor = window.Chart
    if (!canvas || !ChartConstructor) {
      setLibraryReady(false)
      return
    }
    setLibraryReady(true)

    const primary = cssColor('--school-primary', '#16a34a')
    const secondary = cssColor('--school-secondary', '#0f172a')
    const accent = cssColor('--school-accent', '#22c55e')
    const palette = [primary, accent, secondary, '#64748b', '#94a3b8', '#0ea5e9']

    const instance = new ChartConstructor(canvas, {
      type,
      data: {
        labels,
        datasets: datasets.map((dataset, index) => ({
          ...dataset,
          borderColor: palette[index % palette.length],
          backgroundColor: palette[index % palette.length],
          borderWidth: type === 'line' ? 3 : 0,
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
          mode: 'index',
        },
        plugins: {
          legend: {
            display: showLegend && datasets.length > 1,
            position: 'bottom',
            labels: {
              usePointStyle: true,
              boxWidth: 8,
              padding: 16,
            },
          },
          tooltip: {
            enabled: !compact,
            displayColors: datasets.length > 1,
            callbacks: {
              label: (context: {
                dataset: { label?: string }
                parsed: number | { x?: number; y?: number }
              }) => {
                const numeric = typeof context.parsed === 'number'
                  ? context.parsed
                  : horizontal
                    ? context.parsed.x
                    : context.parsed.y
                const label = context.dataset.label ? `${context.dataset.label} : ` : ''
                return `${label}${numeric ?? 0}${valueSuffix}`
              },
            },
          },
        },
        cutout: type === 'doughnut' ? (compact ? '70%' : '72%') : undefined,
        scales: type === 'doughnut' ? undefined : {
          x: {
            display: !compact,
            grid: { display: false },
            ticks: {
              maxRotation: 0,
              autoSkip: !horizontal,
              color: '#64748b',
              font: { size: 11 },
            },
          },
          y: {
            display: !compact,
            beginAtZero: true,
            suggestedMax: max,
            max,
            grid: { color: 'rgba(148, 163, 184, 0.16)' },
            ticks: {
              color: '#64748b',
              font: { size: 11 },
              callback: (value: string | number) => `${value}${valueSuffix}`,
            },
          },
        },
      },
    })

    return () => instance.destroy()
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
