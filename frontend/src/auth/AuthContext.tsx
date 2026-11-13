import { exitDemo } from '../lib/demo'
import { readDemoState } from '../lib/demoState'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  clearSession,
  browserSessionStorageKey,
  getAccessToken,
  getMe,
  getSupportMode,
  isCurrentBrowserSession,
  login as apiLogin,
  logoutSession,
  register as apiRegister,
  type AuthUser,
  type SupportModeState,
} from '../lib/api'
import { formatPersonName } from '../lib/personName'
import { consumeCustomDomainSsoHandoff, maybeStartCustomDomainSso } from './customDomainSso'
import { authenticateWithGoogle } from './googleApi'

type AuthContextValue = {
  user: AuthUser | null
  supportMode: SupportModeState | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (fullName: string, email: string, password: string) => Promise<void>
  signInWithGoogle: (credential: string) => Promise<void>
  signOut: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)
const AUTH_SYNC_EVENT_KEY = 'academie_saas_auth_sync_event'

function announceAuthChange() {
  localStorage.setItem(
    AUTH_SYNC_EVENT_KEY,
    `${Date.now()}:${crypto.randomUUID()}`,
  )
}

function sameUser(current: AuthUser | null, next: AuthUser | null) {
  return current?.id === next?.id
    && current?.full_name === next?.full_name
    && current?.email === next?.email
    && current?.phone === next?.phone
    && current?.avatar_url === next?.avatar_url
    && current?.status === next?.status
    && current?.platform_role === next?.platform_role
}

function sameSupportMode(current: SupportModeState | null, next: SupportModeState | null) {
  return current?.session_id === next?.session_id
    && current?.organization_id === next?.organization_id
    && current?.organization_name === next?.organization_name
    && current?.expires_at === next?.expires_at
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [supportMode, setSupportMode] = useState<SupportModeState | null>(null)
  const [loading, setLoading] = useState(true)

  const updateUser = useCallback((next: AuthUser | null) => {
    const normalized = next
      ? { ...next, full_name: formatPersonName(next.full_name) }
      : null
    setUser((current) => sameUser(current, normalized) ? current : normalized)
  }, [])

  const updateSupportMode = useCallback((next: SupportModeState | null) => {
    setSupportMode((current) => sameSupportMode(current, next) ? current : next)
  }, [])

  const syncFromServer = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true)

    try {
      const handoffUser = await consumeCustomDomainSsoHandoff()
      if (handoffUser) {
        updateSupportMode(null)
        updateUser(handoffUser)
        announceAuthChange()
        return
      }
    } catch {
      // The normal session lookup below remains the fallback.
    }

    if (!isCurrentBrowserSession()) {
      clearSession()
      updateSupportMode(null)
    }

    let token = getAccessToken()
    updateSupportMode(token ? getSupportMode() : null)

    try {
      const nextUser = await getMe()
      updateUser(nextUser)
      token = getAccessToken()
      updateSupportMode(token ? getSupportMode() : null)
    } catch {
      // A stale tab-local bearer token must not hide a still-valid shared cookie.
      // Clear that local state once and retry the server session cookie.
      if (token) {
        clearSession()
        updateSupportMode(null)
        try {
          const nextUser = await getMe()
          updateUser(nextUser)
          return
        } catch {
          // No valid browser cookie either.
        }
      }
      updateSupportMode(null)
      updateUser(null)
      await maybeStartCustomDomainSso()
    } finally {
      setLoading(false)
    }
  }, [updateSupportMode, updateUser])

  useEffect(() => {
    void syncFromServer(true)
  }, [syncFromServer])

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (
        event.key === browserSessionStorageKey()
        || event.key === AUTH_SYNC_EVENT_KEY
      ) {
        void syncFromServer(false)
      }
    }
    const onFocus = () => {
      void syncFromServer(false)
    }
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void syncFromServer(false)
    }

    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [syncFromServer])

  const refreshUser = useCallback(async () => {
    const nextUser = await getMe()
    updateUser(nextUser)
  }, [updateUser])

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    updateSupportMode(null)
    updateUser(response.user)
    announceAuthChange()
  }, [updateSupportMode, updateUser])

  const signUp = useCallback(
    async (fullName: string, email: string, password: string) => {
      const response = await apiRegister(fullName, email, password)
      if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
      updateSupportMode(null)
      updateUser(response.user)
      announceAuthChange()
    },
    [updateSupportMode, updateUser],
  )

  const signInWithGoogle = useCallback(async (credential: string) => {
    const response = await authenticateWithGoogle(credential)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    updateSupportMode(null)
    updateUser(response.user)
    announceAuthChange()
  }, [updateSupportMode, updateUser])

  const signOut = useCallback(() => {
    // Leaving the demo only forgets its token: the visitor's own session, if any, stays.
    if (readDemoState()) {
      exitDemo()
      return
    }
    const logout = logoutSession().catch(() => {})
    clearSession()
    updateSupportMode(null)
    updateUser(null)
    void logout.finally(() => announceAuthChange())
  }, [updateSupportMode, updateUser])

  const value = useMemo(
    () => ({
      user,
      supportMode,
      loading,
      signIn,
      signUp,
      signInWithGoogle,
      signOut,
      refreshUser,
    }),
    [user, supportMode, loading, signIn, signUp, signInWithGoogle, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
