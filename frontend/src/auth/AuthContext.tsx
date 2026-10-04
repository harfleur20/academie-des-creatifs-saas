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
  getAccessToken,
  getMe,
  getSupportMode,
  login as apiLogin,
  logoutSession,
  register as apiRegister,
  type AuthUser,
  type SupportModeState,
} from '../lib/api'

type AuthContextValue = {
  user: AuthUser | null
  supportMode: SupportModeState | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (fullName: string, email: string, password: string) => Promise<void>
  signOut: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [supportMode, setSupportMode] = useState<SupportModeState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const activeSupportMode = getSupportMode()
    setSupportMode(activeSupportMode)

    const token = getAccessToken()
    if (!token) {
      setLoading(false)
      return
    }

    getMe()
      .then(setUser)
      .catch(() => {
        clearSession()
        setSupportMode(null)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const refreshUser = useCallback(async () => {
    const nextUser = await getMe()
    setUser(nextUser)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password)
    setSupportMode(null)
    setUser(response.user)
  }, [])

  const signUp = useCallback(
    async (fullName: string, email: string, password: string) => {
      const response = await apiRegister(fullName, email, password)
      setSupportMode(null)
      setUser(response.user)
    },
    [],
  )

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
      signOut,
      refreshUser,
    }),
    [user, supportMode, loading, signIn, signUp, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
