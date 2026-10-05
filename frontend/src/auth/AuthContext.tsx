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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [supportMode, setSupportMode] = useState<SupportModeState | null>(null)
  const [loading, setLoading] = useState(true)

  const syncFromServer = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true)

    if (!isCurrentBrowserSession()) {
      clearSession()
      setSupportMode(null)
    }

    let token = getAccessToken()
    setSupportMode(token ? getSupportMode() : null)

    try {
      const nextUser = await getMe()
      setUser(nextUser)
      token = getAccessToken()
      setSupportMode(token ? getSupportMode() : null)
    } catch {
      // A stale tab-local bearer token must not hide a still-valid shared cookie.
      // Clear that local state once and retry the server session cookie.
      if (token) {
        clearSession()
        setSupportMode(null)
        try {
          const nextUser = await getMe()
          setUser(nextUser)
          return
        } catch {
          // No valid browser cookie either.
        }
      }
      setSupportMode(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

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
    setUser(nextUser)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    setSupportMode(null)
    setUser(response.user)
    announceAuthChange()
  }, [])

  const signUp = useCallback(
    async (fullName: string, email: string, password: string) => {
      const response = await apiRegister(fullName, email, password)
      if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
      setSupportMode(null)
      setUser(response.user)
      announceAuthChange()
    },
    [],
  )

  const signInWithGoogle = useCallback(async (credential: string) => {
    const response = await authenticateWithGoogle(credential)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    setSupportMode(null)
    setUser(response.user)
    announceAuthChange()
  }, [])

  const signOut = useCallback(() => {
    const logout = logoutSession().catch(() => {})
    clearSession()
    setSupportMode(null)
    setUser(null)
    void logout.finally(() => announceAuthChange())
  }, [])

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
