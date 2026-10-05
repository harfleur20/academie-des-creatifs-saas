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
const recentMessages = new Map<string, number>()
let nextToastId = 1

function publish(kind: ToastKind, message: string, options: ToastOptions = {}) {
  const normalizedMessage = message.trim()
  if (!normalizedMessage) return 0

  const duplicateKey = `${kind}:${normalizedMessage}`
  const now = Date.now()
  const lastPublishedAt = recentMessages.get(duplicateKey) ?? 0
  if (now - lastPublishedAt < 700) return 0
  recentMessages.set(duplicateKey, now)

  const item: ToastItem = {
    id: nextToastId++,
    kind,
    message: normalizedMessage,
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

  useEffect(() => {
    document.body.classList.add('toast-feedback-enabled')
    const previousText = new WeakMap<Element, string>()

    const bridgeFeedback = () => {
      document.querySelectorAll('.form-success, .form-error').forEach((element) => {
        const message = element.textContent?.trim() ?? ''
        if (!message || previousText.get(element) === message) return
        previousText.set(element, message)
        if (element.classList.contains('form-error')) toast.error(message)
        else toast.success(message)
      })
    }

    bridgeFeedback()
    const observer = new MutationObserver(bridgeFeedback)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    })

    return () => {
      observer.disconnect()
      document.body.classList.remove('toast-feedback-enabled')
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
