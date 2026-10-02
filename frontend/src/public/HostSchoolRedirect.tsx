import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { resolveHostBranding } from '../lib/api'

type HostResolution =
  | { state: 'loading'; slug: null }
  | { state: 'resolved'; slug: string }
  | { state: 'unresolved'; slug: null }

export function HostSchoolRedirect({ fallback }: { fallback: ReactNode }) {
  const location = useLocation()
  const [resolution, setResolution] = useState<HostResolution>({
    state: 'loading',
    slug: null,
  })

  useEffect(() => {
    let active = true
    setResolution({ state: 'loading', slug: null })

    resolveHostBranding(window.location.hostname)
      .then((branding) => {
        if (active) {
          setResolution({ state: 'resolved', slug: branding.slug })
        }
      })
      .catch(() => {
        if (active) {
          setResolution({ state: 'unresolved', slug: null })
        }
      })

    return () => {
      active = false
    }
  }, [])

  if (resolution.state === 'loading') {
    return <div className="public-school-state">Chargement…</div>
  }

  if (resolution.state === 'unresolved') {
    return <>{fallback}</>
  }

  const suffix = location.pathname === '/' ? '' : location.pathname
  return (
    <Navigate
      replace
      to={
        '/school/'
        + encodeURIComponent(resolution.slug)
        + suffix
        + location.search
        + location.hash
      }
    />
  )
}
