import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { Camera, Check, Eye, EyeOff, Lock, Mail, Phone, Shield, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  changeMyPassword,
  updateMyProfile,
  uploadMyAvatar,
} from '../lib/api'

export function ProfilePage({ roleLabel }: { roleLabel: 'Professeur' | 'Étudiant' }) {
  const { user, refreshUser, signOut } = useAuth()
  const fileRef = useRef<HTMLInputElement>(null)
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    setFullName(user?.full_name ?? '')
    setPhone(user?.phone ?? '')
  }, [user?.full_name, user?.phone])

  async function saveProfile(event: FormEvent) {
    event.preventDefault()
    setWorking(true)
    setError('')
    setProfileMessage('')
    try {
      await updateMyProfile({
        full_name: fullName.trim(),
        phone: phone.trim() || null,
      })
      await refreshUser()
      setProfileMessage('Informations mises à jour.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Mise à jour impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function uploadAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    try {
      await uploadMyAvatar(file)
      await refreshUser()
      setProfileMessage('Photo de profil mise à jour.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault()
    setError('')
    setPasswordMessage('')
    if (newPassword.length < 8) {
      setError('Le nouveau mot de passe doit contenir au moins 8 caractères.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Les nouveaux mots de passe ne correspondent pas.')
      return
    }
    setWorking(true)
    try {
      await changeMyPassword(currentPassword, newPassword)
      signOut()
      window.location.assign('/login')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Modification impossible.')
    } finally {
      setWorking(false)
    }
  }

  const initials = (user?.full_name || '?')
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()

  return (
    <main className="app-page profile-page">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">{roleLabel}</span>
          <h1>Mon profil</h1>
          <p>Gérez votre identité de compte et votre sécurité.</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <section className="profile-layout">
        <aside className="app-card profile-summary-card">
          <div className="profile-avatar-wrap">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.full_name} />
            ) : (
              <span>{initials}</span>
            )}
            <button
              type="button"
              aria-label="Changer la photo"
              disabled={working}
              onClick={() => fileRef.current?.click()}
            >
              <Camera size={14} />
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => void uploadAvatar(event)}
            />
          </div>
          <h2>{user?.full_name}</h2>
          <p>{roleLabel}</p>
          <small>PNG, JPG ou WebP · 2 Mo max.</small>
          <dl>
            <div><dt>Rôle</dt><dd>{roleLabel}</dd></div>
            <div><dt>Statut</dt><dd>{user?.status === 'active' ? 'Actif' : user?.status}</dd></div>
          </dl>
        </aside>

        <div className="profile-main">
          <form className="app-card profile-form-card" onSubmit={saveProfile}>
            <div className="settings-section-heading">
              <div>
                <span className="section-label">Compte</span>
                <h2>Informations personnelles</h2>
              </div>
              <UserRound size={18} />
            </div>
            {profileMessage && <div className="form-success"><Check size={14} /> {profileMessage}</div>}
            <label>
              Nom complet
              <div className="profile-input-wrap">
                <UserRound size={14} />
                <input value={fullName} onChange={(event) => setFullName(event.target.value)} required minLength={2} />
              </div>
            </label>
            <label>
              Adresse e-mail
              <div className="profile-input-wrap is-readonly">
                <Mail size={14} />
                <input value={user?.email ?? ''} readOnly />
              </div>
              <small>L’adresse e-mail du compte n’est pas modifiable ici.</small>
            </label>
            <label>
              Téléphone
              <div className="profile-input-wrap">
                <Phone size={14} />
                <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+33 6 00 00 00 00" />
              </div>
            </label>
            <button className="primary-button" disabled={working || fullName.trim().length < 2}>
              <Check size={14} /> Enregistrer
            </button>
          </form>

          <form className="app-card profile-form-card" onSubmit={savePassword}>
            <div className="settings-section-heading">
              <div>
                <span className="section-label">Sécurité</span>
                <h2>Changer le mot de passe</h2>
              </div>
              <Shield size={18} />
            </div>
            {passwordMessage && <div className="form-success"><Check size={14} /> {passwordMessage}</div>}
            <label>
              Mot de passe actuel
              <div className="profile-input-wrap">
                <Lock size={14} />
                <input
                  type={showCurrent ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                />
                <button type="button" onClick={() => setShowCurrent((value) => !value)}>
                  {showCurrent ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </label>
            <label>
              Nouveau mot de passe
              <div className="profile-input-wrap">
                <Lock size={14} />
                <input
                  type={showNew ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  minLength={8}
                />
                <button type="button" onClick={() => setShowNew((value) => !value)}>
                  {showNew ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </label>
            <label>
              Confirmer le nouveau mot de passe
              <div className="profile-input-wrap">
                <Lock size={14} />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </div>
            </label>
            <button className="primary-button" disabled={working || !currentPassword || newPassword.length < 8}>
              <Shield size={14} /> Modifier le mot de passe
            </button>
          </form>
        </div>
      </section>
    </main>
  )
}

export function TeacherProfilePage() {
  return <ProfilePage roleLabel="Professeur" />
}

export function StudentProfilePage() {
  return <ProfilePage roleLabel="Étudiant" />
}
