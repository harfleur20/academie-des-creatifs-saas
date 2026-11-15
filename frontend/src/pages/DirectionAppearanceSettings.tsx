import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { Check, PanelLeft, Save } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useTenant } from '../app/TenantContext'
import { DirectionWordmark } from '../brand/DirectionWordmark'
import { ApiError, updateCurrentOrganization } from '../lib/api'

const accentPresets = [
  { color: '#18A7A3', label: 'Turquoise' },
  { color: '#E58A12', label: 'Orange' },
  { color: '#3974D8', label: 'Bleu' },
  { color: '#7953C7', label: 'Violet' },
  { color: '#D14F78', label: 'Rose' },
]

export function DirectionAppearanceSettings() {
  const { activeOrganization, refreshOrganizations } = useTenant()
  const { supportMode } = useAuth()
  const [accentColor, setAccentColor] = useState('#18A7A3')
  const [followSchoolAccent, setFollowSchoolAccent] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [supportsCompactSidebar, setSupportsCompactSidebar] = useState(() => window.matchMedia('(min-width: 1024px)').matches)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const inheritedAccent = activeOrganization?.secondary_color || '#18A7A3'
    setFollowSchoolAccent(activeOrganization?.direction_accent_color == null)
    setAccentColor(activeOrganization?.direction_accent_color || inheritedAccent)
    setSidebarCollapsed(activeOrganization?.direction_sidebar_collapsed ?? false)
    setMessage('')
    setError('')
  }, [activeOrganization?.id, activeOrganization?.secondary_color, activeOrganization?.direction_accent_color, activeOrganization?.direction_sidebar_collapsed])

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)')
    const updateViewport = () => setSupportsCompactSidebar(media.matches)
    media.addEventListener('change', updateViewport)
    return () => media.removeEventListener('change', updateViewport)
  }, [])

  if (!activeOrganization) return <div className="page-state">Créez d’abord une école.</div>

  async function saveSettings(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    setError('')
    try {
      await updateCurrentOrganization({
        direction_accent_color: followSchoolAccent ? null : accentColor.toUpperCase(),
        direction_sidebar_collapsed: sidebarCollapsed,
      })
      await refreshOrganizations()
      setMessage('Les préférences de l’espace Direction ont été enregistrées.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="settings-stack direction-appearance-settings" onSubmit={saveSettings}>
      <section className="app-card settings-form direction-appearance-card">
        <div className="settings-section-heading">
          <div>
            <span className="page-kicker">Personnalisation</span>
            <h2>Votre espace Direction</h2>
            <p>Ces réglages s’appliquent uniquement à l’interface de gestion de cette école.</p>
          </div>
        </div>

        <div className="direction-appearance-grid">
          <section className="direction-setting-block">
            <h3>Couleur d’accent</h3>
            <p>Par défaut, la Direction suit la couleur secondaire de l’identité de l’école. Vous pouvez choisir un accent différent pour cet espace.</p>
            <label className="direction-collapse-option direction-accent-inherit-option">
              <input
                type="checkbox"
                checked={followSchoolAccent}
                onChange={(event) => {
                  const shouldFollow = event.target.checked
                  setFollowSchoolAccent(shouldFollow)
                  if (shouldFollow) setAccentColor(activeOrganization.secondary_color || '#18A7A3')
                }}
                disabled={Boolean(supportMode)}
              />
              <span>
                <strong>Suivre la couleur de l’identité de l’école</strong>
                <small>La couleur de la Direction et la teinte du favicon suivront la couleur secondaire de l’école.</small>
              </span>
            </label>
            <div className="direction-accent-control">
              <input
                type="color"
                value={/^#[0-9a-f]{6}$/i.test(accentColor) ? accentColor : '#18A7A3'}
                onChange={(event) => {
                  setFollowSchoolAccent(false)
                  setAccentColor(event.target.value.toUpperCase())
                }}
                aria-label="Choisir la couleur d’accent"
                disabled={Boolean(supportMode) || followSchoolAccent}
              />
              <code>{accentColor.toUpperCase()}</code>
            </div>
            <div className="direction-accent-presets" aria-label="Couleurs proposées">
              {accentPresets.map(({ color, label }) => (
                <button
                  key={color}
                  type="button"
                  className={accentColor.toUpperCase() === color ? 'is-selected' : ''}
                  style={{ '--swatch-color': color } as CSSProperties}
                  onClick={() => {
                    setFollowSchoolAccent(false)
                    setAccentColor(color)
                  }}
                  aria-label={label}
                  aria-pressed={accentColor.toUpperCase() === color}
                  disabled={Boolean(supportMode) || followSchoolAccent}
                >
                  {accentColor.toUpperCase() === color && <Check size={15} />}
                </button>
              ))}
            </div>
            <div className="direction-accent-preview" style={{ '--direction-accent': accentColor } as CSSProperties}>
              <DirectionWordmark accentColor={accentColor} />
              <div className="direction-preview-progress"><span /></div>
              <span className="direction-preview-label">Aperçu de l’accent</span>
            </div>
          </section>

          <section className="direction-setting-block">
            <h3>Barre latérale</h3>
            <p>Gardez la navigation complète ou réduisez-la à une colonne d’icônes.</p>
            <label className="direction-collapse-option">
              <input
                type="checkbox"
                checked={sidebarCollapsed}
                onChange={(event) => setSidebarCollapsed(event.target.checked)}
                disabled={Boolean(supportMode) || !supportsCompactSidebar}
              />
              <span>
                <strong>Activer la barre latérale compacte</strong>
                <small>Les libellés sont masqués. Le nom de l’école devient son initiale dans un cercle blanc.</small>
              </span>
            </label>
            {!supportsCompactSidebar && (
              <p className="direction-collapse-availability">Disponible sur les tablettes larges et les ordinateurs (écran de 1024 px ou plus).</p>
            )}
            <div className={`direction-sidebar-preview${sidebarCollapsed ? ' is-collapsed' : ''}`} aria-hidden="true">
              <div className="direction-sidebar-preview__brand"><PanelLeft size={18} /></div>
              <div className="direction-sidebar-preview__school">{activeOrganization.name.trim().charAt(0).toUpperCase() || '?'}</div>
              <div className="direction-sidebar-preview__items"><i /><i /><i /><i /></div>
              <span>{sidebarCollapsed ? 'Navigation compacte' : 'Navigation complète'}</span>
            </div>
          </section>
        </div>

        {error && <p className="form-error" role="alert">{error}</p>}
        {message && <p className="form-success" role="status">{message}</p>}
        <div className="settings-actions direction-appearance-actions">
          <button className="primary-button" type="submit" disabled={saving || Boolean(supportMode)}>
            <Save size={16} />{saving ? 'Enregistrement…' : 'Enregistrer les préférences'}
          </button>
        </div>
        {supportMode && <p className="direction-readonly-note">Les préférences ne peuvent pas être modifiées pendant une session de support en lecture seule.</p>}
      </section>
    </form>
  )
}
