import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleAlert, Info, TriangleAlert, X } from 'lucide-react'

type ToastKind = 'success' | 'error' | 'warning' | 'info'

type ToastOptions = {
  title?: string
  duration?: number
}

type ToastItem = {
  id: number
  kind: ToastKind
  message: string
  title?: string
  duration: number
}

type ToastListener = (toast: ToastItem) => void

const listeners = new Set<ToastListener>()
let nextToastId = 1

function publish(kind: ToastKind, message: string, options: ToastOptions = {}) {
  const item: ToastItem = {
    id: nextToastId++,
    kind,
    message,
    title: options.title,
    duration: options.duration ?? (kind === 'error' ? 5200 : 3600),
  }

  listeners.forEach((listener) => listener(item))
  return item.id
}

export const toast = {
  success: (message: string, options?: ToastOptions) => publish('success', message, options),
  error: (message: string, options?: ToastOptions) => publish('error', message, options),
  warning: (message: string, options?: ToastOptions) => publish('warning', message, options),
  info: (message: string, options?: ToastOptions) => publish('info', message, options),
}

function ToastIcon({ kind }: { kind: ToastKind }) {
  if (kind === 'success') return <CheckCircle2 size={20} />
  if (kind === 'error') return <CircleAlert size={20} />
  if (kind === 'warning') return <TriangleAlert size={20} />
  return <Info size={20} />
}

export function ToastViewport() {
  const [items, setItems] = useState<ToastItem[]>([])
  const timers = useRef(new Map<number, number>())

  function dismiss(id: number) {
    const timer = timers.current.get(id)
    if (timer) window.clearTimeout(timer)
    timers.current.delete(id)
    setItems((current) => current.filter((item) => item.id !== id))
  }

  useEffect(() => {
    const listener: ToastListener = (item) => {
      setItems((current) => [...current.slice(-3), item])
      const timer = window.setTimeout(() => {
        timers.current.delete(item.id)
        setItems((current) => current.filter((entry) => entry.id !== item.id))
      }, item.duration)
      timers.current.set(item.id, timer)
    }

    listeners.add(listener)
    return () => {
      listeners.delete(listener)
      timers.current.forEach((timer) => window.clearTimeout(timer))
      timers.current.clear()
    }
  }, [])

  return (
    <div className="toast-viewport" aria-live="polite" aria-atomic="false">
      {items.map((item) => (
        <div
          className={`app-toast app-toast-${item.kind}`}
          key={item.id}
          role={item.kind === 'error' ? 'alert' : 'status'}
        >
          <span className="app-toast-icon" aria-hidden="true">
            <ToastIcon kind={item.kind} />
          </span>
          <div className="app-toast-content">
            {item.title && <strong>{item.title}</strong>}
            <span>{item.message}</span>
          </div>
          <button type="button" className="app-toast-close" onClick={() => dismiss(item.id)} aria-label="Fermer la notification">
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}
