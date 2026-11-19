import { useSyncExternalStore } from 'react'
import { useParams } from 'react-router-dom'
import { readSchoolHost, subscribeSchoolHost, type SchoolHost } from './schoolHost'

export function useSchoolHost(): SchoolHost {
  return useSyncExternalStore(subscribeSchoolHost, readSchoolHost)
}

/** The school of the site being shown: from "/school/<slug>/…", or from the address. */
export function useSchoolSlug(): string {
  const { schoolSlug } = useParams()
  const host = useSchoolHost()
  return schoolSlug ?? (host.status === 'resolved' ? host.slug ?? '' : '')
}
