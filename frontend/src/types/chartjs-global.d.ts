type AcademieChartInstance = {
  destroy: () => void
}

type AcademieChartConstructor = new (
  item: HTMLCanvasElement | CanvasRenderingContext2D,
  config: Record<string, unknown>,
) => AcademieChartInstance

interface Window {
  Chart?: AcademieChartConstructor
}
