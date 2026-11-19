import { ArrowRight, Building2, CheckCircle2, CircleAlert, Eye, Globe2, LoaderCircle, LogIn, Mail, PanelLeft, PanelsTopLeft, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { OrganizationDangerZone } from '../components/OrganizationDangerZone'
import { DirectionAppearanceSettings } from './DirectionAppearanceSettings'
import { SchoolIdentityEditor } from './SchoolPublicSitePage'
import { SchoolSettingsPage } from './SchoolSettingsPage'
import { SchoolPublicationIllustration } from '../components/SchoolPublicationIllustration'
import { ApiError, getSchoolIdentity, updateSchoolIdentity, type SchoolIdentity } from '../lib/api'
import { getSchoolPublicationRequirements, type PublicationDestination, type SchoolPublicationRequirement } from '../lib/sitePublicationReadiness'

const identityTabs = [
  { id: 'school', label: 'École & marque', icon: Building2 },
  { id: 'site', label: 'Site public', icon: PanelsTopLeft },
  { id: 'auth', label: 'Connexion & inscription', icon: LogIn },
  { id: 'domains', label: 'Adresses web', icon: Globe2 },
  { id: 'legal', label: 'Légal & facturation', icon: ShieldCheck },
  { id: 'communications', label: 'Communications & certificats', icon: Mail },
  { id: 'direction', label: 'Espace Direction', icon: PanelLeft },
] as const

type IdentityTab = typeof identityTabs[number]['id']

function isIdentityTab(value: string | null): value is IdentityTab {
  return identityTabs.some((tab) => tab.id === value)
}

export function SchoolIdentityPage() {
  const { activeOrganization } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()
  const [publicationIdentity, setPublicationIdentity] = useState<SchoolIdentity | null>(null)
  const [publicationLoading, setPublicationLoading] = useState(true)
  const [publicationError, setPublicationError] = useState('')
  const [publicationActionError, setPublicationActionError] = useState('')
  const [publishing, setPublishing] = useState(false)
  const requestedTab = searchParams.get('tab')
  const activeTab: IdentityTab = isIdentityTab(requestedTab) ? requestedTab : 'school'
  const editorSection = activeTab === 'site' || activeTab === 'auth' || activeTab === 'legal' || activeTab === 'communications'
    ? activeTab
    : 'brand'
  const publicationRequirements = getSchoolPublicationRequirements(publicationIdentity, activeOrganization)

  useEffect(() => {
    if (!activeOrganization?.id) {
      setPublicationIdentity(null)
      setPublicationLoading(false)
      return
    }
    let current = true
    setPublicationIdentity(null)
    setPublicationLoading(true)
    setPublicationError('')
    setPublicationActionError('')
    getSchoolIdentity()
      .then((identity) => {
        if (current) setPublicationIdentity(identity)
      })
      .catch(() => {
        if (current) setPublicationError('Impossible de vérifier les prérequis de publication pour le moment.')
      })
      .finally(() => {
        if (current) setPublicationLoading(false)
      })
    return () => { current = false }
  }, [activeOrganization?.id])

  function selectTab(tab: IdentityTab) {
    setSearchParams({ tab })
  }

  async function publishSite() {
    if (!publicationIdentity || publicationRequirements.some((item) => !item.complete)) return
    setPublishing(true)
    setPublicationActionError('')
    try {
      const updated = await updateSchoolIdentity({
        ...publicationIdentity,
        public_site: { ...publicationIdentity.public_site, is_published: true },
      })
      setPublicationIdentity(updated)
    } catch (error) {
      setPublicationActionError(error instanceof ApiError ? error.message : 'Impossible de publier le site pour le moment.')
    } finally {
      setPublishing(false)
    }
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
          <a className="secondary-button compact-action" target="_blank" rel="noreferrer" href={activeOrganization.public_site_url || '/school/' + activeOrganization.slug}>
            <Eye size={15}/>Voir le site public
          </a>
        )}
      </header>

      {activeOrganization && (
        <SitePublicationGuide
          identity={publicationIdentity}
          requirements={publicationRequirements}
          loading={publicationLoading}
          error={publicationError}
          actionError={publicationActionError}
          publishing={publishing}
          onPublish={() => void publishSite()}
        />
      )}

      <nav id="school-identity-tabs" className="school-identity-tabs" role="tablist" aria-label="Réglages de l’identité de l’école">
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
          <SchoolIdentityEditor
            section={editorSection}
            isPublished={publicationIdentity?.public_site.is_published}
            onIdentitySaved={setPublicationIdentity}
          />
        </div>
        {activeTab === 'school' && <OrganizationDangerZone />}
        {activeTab === 'direction' && <DirectionAppearanceSettings />}
      </section>
    </main>
  )
}

const publicationGroupDefinitions: {
  id: string
  title: string
  destination: PublicationDestination
  requirementIds: string[]
}[] = [
  { id: 'contact', title: 'Informations de l’école', destination: 'school', requirementIds: ['contact-email'] },
  { id: 'address', title: 'Adresse web', destination: 'domains', requirementIds: ['subdomain'] },
  { id: 'student-codes', title: 'Matricules', destination: 'school', requirementIds: ['student-code-prefix'] },
  {
    id: 'legal',
    title: 'Légal & facturation',
    destination: 'legal',
    requirementIds: ['legal-notice', 'sales-terms', 'privacy-policy', 'refund-policy', 'billing-name', 'billing-address', 'billing-email', 'billing-currency'],
  },
]

const identityTabPath: Record<PublicationDestination, string> = {
  school: '/app/manage/identity?tab=school',
  domains: '/app/manage/identity?tab=domains',
  legal: '/app/manage/identity?tab=legal',
}

function SitePublicationGuide({
  identity,
  requirements,
  loading,
  error,
  actionError,
  publishing,
  onPublish,
}: {
  identity: SchoolIdentity | null
  requirements: SchoolPublicationRequirement[]
  loading: boolean
  error: string
  actionError: string
  publishing: boolean
  onPublish: () => void
}) {
  const completedCount = requirements.filter((item) => item.complete).length
  const totalCount = requirements.length
  const remainingCount = totalCount - completedCount
  const firstIncompleteGroup = publicationGroupDefinitions.find((group) =>
    group.requirementIds.some((id) => requirements.find((item) => item.id === id)?.complete === false),
  )
  const groups = publicationGroupDefinitions.map((group) => ({
    ...group,
    items: group.requirementIds
      .map((id) => requirements.find((item) => item.id === id))
      .filter((item): item is SchoolPublicationRequirement => Boolean(item)),
  }))
  const scrollToSettings = () => {
    window.setTimeout(() => {
      document.getElementById('school-identity-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 0)
  }

  return (
    <section className={`school-publication-guide${remainingCount === 0 && !loading && !error ? ' is-ready' : ''}`} aria-labelledby="school-publication-guide-title">
      <div className="school-publication-guide__header">
        <div className="school-publication-guide__header-copy">
          <span className="section-label">Publication du site public</span>
          <h2 id="school-publication-guide-title">Préparez la mise en ligne de votre site</h2>
          <p>Chaque étape indique ce qui manque et ouvre les réglages correspondants.</p>
        </div>
        <SchoolPublicationIllustration />
        {!loading && !error && totalCount > 0 && (
          <span className="school-publication-guide__counter">{completedCount}/{totalCount}<small> éléments prêts</small></span>
        )}
      </div>

      {loading ? (
        <p className="school-publication-guide__notice">Vérification des éléments nécessaires…</p>
      ) : error ? (
        <p className="school-publication-guide__notice is-error">{error}</p>
      ) : (
        <>
          <div className="school-publication-guide__progress" role="progressbar" aria-label="Progression avant publication" aria-valuemin={0} aria-valuemax={totalCount} aria-valuenow={completedCount}>
            <span style={{ width: `${totalCount ? (completedCount / totalCount) * 100 : 0}%` }} />
          </div>
          <div className="school-publication-guide__groups">
            {groups.map((group) => {
              const missing = group.items.filter((item) => !item.complete)
              const done = missing.length === 0
              return (
                <article className={`school-publication-guide__group${done ? ' is-done' : ''}`} key={group.id}>
                  <div className="school-publication-guide__group-heading">
                    {done ? <CheckCircle2 size={18} aria-hidden="true" /> : <CircleAlert size={18} aria-hidden="true" />}
                    <strong>{group.title}</strong>
                    <span>{done ? 'Terminé' : `${missing.length} à compléter`}</span>
                  </div>
                  {done ? (
                    <p>Cette étape est complète.</p>
                  ) : (
                    <>
                      <ul>{missing.map((item) => <li key={item.id}>{item.label}</li>)}</ul>
                      <Link
                        className="school-publication-guide__group-link"
                        to={identityTabPath[group.destination]}
                        onClick={(event) => {
                          if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) scrollToSettings()
                        }}
                      >
                        Compléter cette étape <ArrowRight size={15} aria-hidden="true" />
                      </Link>
                    </>
                  )}
                </article>
              )
            })}
          </div>
          <div className="school-publication-guide__action">
            {remainingCount > 0 && firstIncompleteGroup ? (
              <Link
                className="primary-button compact-action"
                to={identityTabPath[firstIncompleteGroup.destination]}
                onClick={(event) => {
                  if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) scrollToSettings()
                }}
              >
                Continuer la configuration <ArrowRight size={16} aria-hidden="true" />
              </Link>
            ) : identity?.public_site.is_published ? (
              <span className="school-publication-guide__published"><CheckCircle2 size={17} aria-hidden="true" /> Votre site est publié.</span>
            ) : (
              <button className="primary-button compact-action" type="button" disabled={publishing || !identity} onClick={onPublish}>
                {publishing ? <><LoaderCircle size={16} className="button-spinner" aria-hidden="true" /> Publication…</> : <>Publier le site <ArrowRight size={16} aria-hidden="true" /></>}
              </button>
            )}
          </div>
          {actionError && <p className="school-publication-guide__notice is-error" role="alert">{actionError}</p>}
        </>
      )}
    </section>
  )
}
