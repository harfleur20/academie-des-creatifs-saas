import { Building2, ExternalLink, Globe2, LogIn, Mail, PanelsTopLeft, ShieldCheck } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { SchoolIdentityEditor } from './SchoolPublicSitePage'
import { SchoolSettingsPage } from './SchoolSettingsPage'

const identityTabs = [
  { id: 'school', label: 'École & marque', icon: Building2 },
  { id: 'site', label: 'Site public', icon: PanelsTopLeft },
  { id: 'auth', label: 'Connexion & inscription', icon: LogIn },
  { id: 'domains', label: 'Adresses web', icon: Globe2 },
  { id: 'legal', label: 'Légal & facturation', icon: ShieldCheck },
  { id: 'communications', label: 'Communications & certificats', icon: Mail },
] as const

type IdentityTab = typeof identityTabs[number]['id']

function isIdentityTab(value: string | null): value is IdentityTab {
  return identityTabs.some((tab) => tab.id === value)
}

export function SchoolIdentityPage() {
  const { activeOrganization } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab: IdentityTab = isIdentityTab(requestedTab) ? requestedTab : 'school'
  const editorSection = activeTab === 'site' || activeTab === 'auth' || activeTab === 'legal' || activeTab === 'communications'
    ? activeTab
    : 'brand'

  function selectTab(tab: IdentityTab) {
    setSearchParams({ tab })
  }

  return (
    <main className="app-page school-identity-hub">
      <header className="app-page-header">
        <div>
          <span className="page-kicker">École</span>
          <h1>Identité de l’école</h1>
          <p>Personnalisez la marque, le site public, les écrans de connexion et les documents de votre école depuis un seul endroit.</p>
        </div>
        {activeOrganization?.slug && (
          <Link className="secondary-button compact-action" target="_blank" rel="noreferrer" to={'/school/' + activeOrganization.slug}>
            <ExternalLink size={15}/>Voir le site public
          </Link>
        )}
      </header>

      <nav className="school-identity-tabs" role="tablist" aria-label="Réglages de l’identité de l’école">
        {identityTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            id={`school-identity-tab-${id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            aria-controls="school-identity-panel"
            className={activeTab === id ? 'is-active' : ''}
            onClick={() => selectTab(id)}
          >
            <Icon size={17}/><span>{label}</span>
          </button>
        ))}
      </nav>

      <section id="school-identity-panel" role="tabpanel" aria-labelledby={`school-identity-tab-${activeTab}`} className="school-identity-panel">
        <div style={{ display: activeTab === 'school' || activeTab === 'domains' ? 'block' : 'none' }}>
          <SchoolSettingsPage section={activeTab === 'domains' ? 'domains' : 'school'} />
        </div>
        <div style={{ display: activeTab === 'school' || activeTab === 'site' || activeTab === 'auth' || activeTab === 'legal' || activeTab === 'communications' ? 'block' : 'none' }}>
          <SchoolIdentityEditor section={editorSection} />
        </div>
      </section>
    </main>
  )
}
