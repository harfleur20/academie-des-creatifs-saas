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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [supportMode, setSupportMode] = useState<SupportModeState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const syncBrowserSession = () => {
      if (isCurrentBrowserSession()) return
      setSupportMode(null)
      setUser(null)
      setLoading(false)
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key === browserSessionStorageKey()) syncBrowserSession()
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', syncBrowserSession)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', syncBrowserSession)
    }
  }, [])

  useEffect(() => {
    const token = getAccessToken()
    setSupportMode(token ? getSupportMode() : null)
    if (!token) {
      setLoading(false)
      return
    }

    getMe()
      .then((nextUser) => {
        if (getAccessToken() === token) setUser(nextUser)
      })
      .catch(() => {
        if (getAccessToken() === token) {
          clearSession()
          setSupportMode(null)
          setUser(null)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const refreshUser = useCallback(async () => {
    const token = getAccessToken()
    const nextUser = await getMe()
    if (token && getAccessToken() === token) setUser(nextUser)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    setSupportMode(null)
    setUser(response.user)
  }, [])

  const signUp = useCallback(
    async (fullName: string, email: string, password: string) => {
      const response = await apiRegister(fullName, email, password)
      if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
      setSupportMode(null)
      setUser(response.user)
    },
    [],
  )

  const signInWithGoogle = useCallback(async (credential: string) => {
    const response = await authenticateWithGoogle(credential)
    if (getAccessToken() !== response.access_token) throw new Error('Une autre connexion a remplacé cette session.')
    setSupportMode(null)
    setUser(response.user)
  }, [])

  const signOut = useCallback(() => {
    if (getAccessToken()) void logoutSession().catch(() => {})
    clearSession()
    setSupportMode(null)
    setUser(null)
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
