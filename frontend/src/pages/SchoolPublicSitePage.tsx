import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { Fingerprint, ImagePlus, Save, ShieldCheck } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { SchoolLogo } from '../brand/SchoolLogo'
import { schoolFontFamily, schoolFontOptions } from '../brand/schoolTypography'
import { SchoolAnnouncementBanner } from '../public/SchoolAnnouncementBanner'
import { POPULAR_CURRENCIES } from '../public/currencyRates'
import { SchoolCertificatePreview, SchoolInvoicePreview } from './SchoolDocumentPreviews'
import {
  ApiError,
  getSchoolIdentity,
  updateSchoolIdentity,
  uploadSchoolAsset,
  type SchoolIdentity,
} from '../lib/api'

type IdentityEditorSection = 'brand' | 'site' | 'auth' | 'legal' | 'communications'

const SIZE_SLIDERS = [
  { key: 'heading_size_scale', label: 'Titres', hint: 'Titres des pages, formations et sections.' },
  { key: 'subtitle_size_scale', label: 'Sous-titres', hint: 'Textes d’accroche et introductions.' },
  { key: 'font_size_scale', label: 'Texte', hint: 'Descriptions, cartes, menus et pied de page.' },
] as const

const supportedFont = (name: string) => schoolFontOptions.some((option) => option.name === name) ? name : 'Inter'

const identityEditorFields: Record<IdentityEditorSection, {
  publicSite: (keyof SchoolIdentity['public_site'])[]
  legal?: (keyof SchoolIdentity['legal'])[]
  communications?: (keyof SchoolIdentity['communications'])[]
  certification?: (keyof SchoolIdentity['certification'])[]
}> = {
  brand: {
    publicSite: ['site_name', 'logo_url', 'favicon_url', 'primary_color', 'secondary_color', 'accent_color', 'font_heading', 'font_body', 'font_size_scale', 'heading_size_scale', 'subtitle_size_scale', 'student_code_prefix', 'student_code_prefix_confirmed'],
  },
  site: {
    publicSite: ['tagline', 'seo_description', 'hero_title', 'hero_subtitle', 'hero_cta_label', 'hero_image_url', 'announcement_enabled', 'announcement_text', 'announcement_background_color', 'announcement_text_color', 'about_title', 'about_text', 'contact_phone', 'contact_email', 'contact_address', 'footer_text', 'is_published'],
  },
  auth: {
    publicSite: ['auth_background_image_url', 'auth_show_school_name'],
  },
  legal: {
    publicSite: ['legal_notice', 'sales_terms', 'privacy_policy', 'refund_policy'],
    legal: ['legal_name', 'legal_address', 'registration_number', 'tax_number', 'invoice_email', 'invoice_phone', 'default_currency', 'invoice_footer'],
  },
  communications: {
    publicSite: [],
    communications: ['sender_name', 'reply_to_email', 'email_signature', 'whatsapp_signature', 'whatsapp_phone'],
    certification: ['signer_name', 'signer_title', 'signature_url', 'stamp_url', 'certificate_footer'],
  },
}

function mergeChangedFields<T extends object>(latest: T, original: T, current: T, keys: (keyof T)[]): T {
  const merged = { ...latest }
  for (const key of keys) {
    if (current[key] !== original[key]) Object.assign(merged, { [key]: current[key] })
  }
  return merged
}

function rebaseDraft<T extends object>(original: T, current: T, latest: T): T {
  const rebased = { ...latest }
  for (const key of Object.keys(current) as (keyof T)[]) {
    if (current[key] !== original[key]) Object.assign(rebased, { [key]: current[key] })
  }
  return rebased
}

function rebaseIdentityDraft(original: SchoolIdentity, current: SchoolIdentity, latest: SchoolIdentity): SchoolIdentity {
  return {
    ...latest,
    public_site: rebaseDraft(original.public_site, current.public_site, latest.public_site),
    legal: rebaseDraft(original.legal, current.legal, latest.legal),
    communications: rebaseDraft(original.communications, current.communications, latest.communications),
    certification: rebaseDraft(original.certification, current.certification, latest.certification),
  }
}

function mergeEditorChanges(latest: SchoolIdentity, original: SchoolIdentity, current: SchoolIdentity, section: IdentityEditorSection): SchoolIdentity {
  const fields = identityEditorFields[section]
  return {
    ...latest,
    public_site: mergeChangedFields(latest.public_site, original.public_site, current.public_site, fields.publicSite),
    ...(fields.legal ? { legal: mergeChangedFields(latest.legal, original.legal, current.legal, fields.legal) } : {}),
    ...(fields.communications ? { communications: mergeChangedFields(latest.communications, original.communications, current.communications, fields.communications) } : {}),
    ...(fields.certification ? { certification: mergeChangedFields(latest.certification, original.certification, current.certification, fields.certification) } : {}),
  }
}

/** Legacy route: the old Site public menu now opens the matching hub tab. */
export function SchoolPublicSitePage() {
  return <Navigate replace to="/app/manage/identity?tab=site" />
}

export function SchoolIdentityEditor({ section }: { section: IdentityEditorSection }) {
  const { activeOrganization, refreshOrganizations } = useTenant()
  const [data, setData] = useState<SchoolIdentity | null>(null)
  const originalData = useRef<SchoolIdentity | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    if (!activeOrganization) return
    let active = true
    getSchoolIdentity()
      .then((identity) => {
        if (!active) return
        const loaded = {
          ...identity,
          public_site: {
            ...identity.public_site,
            font_heading: supportedFont(identity.public_site.font_heading),
            font_body: supportedFont(identity.public_site.font_body),
          },
        }
        originalData.current = loaded
        setData(loaded)
        setError('')
      })
      .catch((err) => { if (active) setError(err instanceof ApiError ? err.message : 'Chargement impossible.') })
    return () => { active = false }
  }, [activeOrganization?.id])

  function site<K extends keyof SchoolIdentity['public_site']>(key: K, value: SchoolIdentity['public_site'][K]) {
    setData((current) => current ? { ...current, public_site: { ...current.public_site, [key]: value } } : current)
    setMessage('')
  }

  function legal<K extends keyof SchoolIdentity['legal']>(key: K, value: SchoolIdentity['legal'][K]) {
    setData((current) => current ? { ...current, legal: { ...current.legal, [key]: value } } : current)
    setMessage('')
  }

  function comm<K extends keyof SchoolIdentity['communications']>(key: K, value: SchoolIdentity['communications'][K]) {
    setData((current) => current ? { ...current, communications: { ...current.communications, [key]: value } } : current)
    setMessage('')
  }

  function cert<K extends keyof SchoolIdentity['certification']>(key: K, value: SchoolIdentity['certification'][K]) {
    setData((current) => current ? { ...current, certification: { ...current.certification, [key]: value } } : current)
    setMessage('')
  }

  async function upload(event: ChangeEvent<HTMLInputElement>, target: 'logo' | 'favicon' | 'hero' | 'auth-background' | 'signature' | 'stamp') {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const asset = await uploadSchoolAsset(file)
      if (target === 'logo') site('logo_url', asset.public_url)
      if (target === 'favicon') site('favicon_url', asset.public_url)
      if (target === 'hero') site('hero_image_url', asset.public_url)
      if (target === 'auth-background') site('auth_background_image_url', asset.public_url)
      if (target === 'signature') cert('signature_url', asset.public_url)
      if (target === 'stamp') cert('stamp_url', asset.public_url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload impossible.')
    } finally {
      setWorking(false)
    }
  }

  const publicationIssues = data && activeOrganization ? [
    !activeOrganization.contact_email?.trim() && 'Email de contact de l’école',
    !activeOrganization.subdomain?.trim() && 'Sous-domaine de l’école',
    !data.public_site.student_code_prefix_confirmed && 'Préfixe des matricules à confirmer',
    !data.public_site.legal_notice.trim() && 'Mentions légales',
    !data.public_site.sales_terms.trim() && 'Conditions générales de vente',
    !data.public_site.privacy_policy.trim() && 'Politique de confidentialité',
    !data.public_site.refund_policy.trim() && 'Politique de remboursement',
    !data.legal.legal_name.trim() && 'Raison sociale des factures',
    !data.legal.legal_address.trim() && 'Adresse légale des factures',
    !data.legal.invoice_email?.trim() && 'Email de facturation',
    !POPULAR_CURRENCIES.some(({ code }) => code === data.legal.default_currency) && 'Devise de facturation',
  ].filter((issue): issue is string => Boolean(issue)) : []

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!data) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const latest = await getSchoolIdentity()
      const original = originalData.current || latest
      const merged = mergeEditorChanges(latest, original, data, section)
      const moveToDraft = merged.public_site.is_published && publicationIssues.length > 0
      const updated = await updateSchoolIdentity({
        ...merged,
        public_site: { ...merged.public_site, is_published: moveToDraft ? false : merged.public_site.is_published },
      })
      originalData.current = updated
      setData((current) => current ? rebaseIdentityDraft(original, current, updated) : updated)
      await refreshOrganizations()
      setMessage(moveToDraft
        ? 'Identité enregistrée. Le site est passé en brouillon jusqu’à la fin de sa configuration.'
        : 'Modifications enregistrées.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (!activeOrganization) return <div className="page-state">Créez d’abord une école.</div>
  if (!data) return <div className="page-state">{error || 'Chargement de l’identité de l’école…'}</div>

  return (
    <div className="school-site-admin school-identity-tab-content">
      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-success">{message}</div>}
      {section === 'site' && publicationIssues.length > 0 && (
        <div className="app-card formation-readiness">
          <strong>À compléter avant de publier le site</strong>
          {data.public_site.is_published && <p>Le prochain enregistrement passera le site en brouillon pour vous laisser terminer sa configuration.</p>}
          <ul>{publicationIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
        </div>
      )}

      <form className="school-site-admin-form" onSubmit={save}>
        {section === 'brand' && <>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Identité visuelle</span><h2>Logo, couleurs et typographie</h2><p>Cette identité est reprise sur le site public et dans les espaces de l’école.</p></div><Fingerprint size={19}/></div>
            <div className="brand-assets-grid school-brand-assets-grid">
              <AssetPicker label="Logo de l’école" value={data.public_site.logo_url} onUpload={(e)=>void upload(e,'logo')} schoolLogo />
              <AssetPicker label="Favicon" value={data.public_site.favicon_url} onUpload={(e)=>void upload(e,'favicon')} />
            </div>
            <div className="school-site-form-grid">
              <label>Nom public<input value={data.public_site.site_name} onChange={(e)=>site('site_name',e.target.value)}/><small>Affiché sur le site. Il peut être différent du nom administratif.</small></label>
              <label>Couleur principale<input type="color" value={data.public_site.primary_color} onChange={(e)=>site('primary_color',e.target.value)}/></label>
              <label>Couleur secondaire<input type="color" value={data.public_site.secondary_color} onChange={(e)=>site('secondary_color',e.target.value)}/></label>
              <label>Couleur d’accent<input type="color" value={data.public_site.accent_color} onChange={(e)=>site('accent_color',e.target.value)}/></label>
              <label>Police des titres<select value={supportedFont(data.public_site.font_heading)} onChange={(e)=>site('font_heading',e.target.value)}>{schoolFontOptions.map((option) => <option key={option.name} value={option.name}>{option.name}</option>)}</select></label>
              <label>Police du texte<select value={supportedFont(data.public_site.font_body)} onChange={(e)=>site('font_body',e.target.value)}>{schoolFontOptions.map((option) => <option key={option.name} value={option.name}>{option.name}</option>)}</select></label>
            </div>
            <div className="school-typography-controls">
              {SIZE_SLIDERS.map(({ key, label, hint }) => (
                <label key={key} className="school-typography-slider">
                  <span>{label} <strong>{data.public_site[key] ?? 100}%</strong></span>
                  <input type="range" min="85" max="125" step="5" value={data.public_site[key] ?? 100} onChange={(e)=>site(key,Number(e.target.value))}/>
                  <small>{hint}</small>
                </label>
              ))}
              <button className="secondary-button compact-action" type="button" onClick={()=>{ site('heading_size_scale',100); site('subtitle_size_scale',100); site('font_size_scale',100) }}>Tailles normales</button>
            </div>
            <div className="school-typography-preview" aria-label="Aperçu de la typographie">
              <strong style={{ fontFamily: schoolFontFamily(data.public_site.font_heading), fontSize: `${Math.round(30 * (data.public_site.heading_size_scale ?? 100) / 100)}px` }}>Découvrez nos formations</strong>
              <p className="school-typography-preview__subtitle" style={{ fontFamily: schoolFontFamily(data.public_site.font_body), fontSize: `${Math.round(17 * (data.public_site.subtitle_size_scale ?? 100) / 100)}px` }}>Des parcours concrets pour apprendre un métier créatif.</p>
              <p style={{ fontFamily: schoolFontFamily(data.public_site.font_body), fontSize: `${Math.round(15 * data.public_site.font_size_scale / 100)}px` }}>Un aperçu immédiat des titres, sous-titres et textes de votre école.</p>
            </div>
          </section>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Matricules</span><h2>Préfixe de l’école</h2><p>Ce préfixe sera utilisé pour les matricules des professeurs et des étudiants.</p></div></div>
            <label>Préfixe matricule<input value={data.public_site.student_code_prefix} maxLength={8} onChange={(e)=>site('student_code_prefix',e.target.value.toUpperCase())} placeholder="SB"/></label>
            <label className="school-prefix-confirmation">
              <input type="checkbox" checked={data.public_site.student_code_prefix_confirmed} disabled={data.public_site.student_code_prefix_confirmed || !activeOrganization.contact_email || !activeOrganization.subdomain} onChange={(e)=>site('student_code_prefix_confirmed',e.target.checked)}/>
              <span>{data.public_site.student_code_prefix_confirmed ? 'Préfixe confirmé pour cette école' : 'Je confirme ce préfixe pour les matricules des professeurs et étudiants.'}</span>
            </label>
            {(!activeOrganization.contact_email || !activeOrganization.subdomain) && !data.public_site.student_code_prefix_confirmed && <p className="muted-note">Renseignez l’email de contact dans <Link to="/app/manage/identity?tab=school">École & marque</Link> et le sous-domaine dans <Link to="/app/manage/identity?tab=domains">Adresses web</Link>.</p>}
            <p className="muted-note">Les matricules déjà attribués ne changent pas.</p>
          </section>
        </>}

        {section === 'site' && <>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Accueil</span><h2>Hero & présentation</h2></div><ImagePlus size={19}/></div>
            <div className="brand-assets-grid"><AssetPicker label="Image de couverture" value={data.public_site.hero_image_url} onUpload={(e)=>void upload(e,'hero')} wide /></div>
            <div className="school-announcement-settings">
              <strong>Bandeau d’annonce</strong>
              <p>Un message défilant s’affiche en haut de toutes les pages publiques de l’école.</p>
              <label className="school-announcement-toggle"><input type="checkbox" checked={data.public_site.announcement_enabled} onChange={(e)=>site('announcement_enabled',e.target.checked)}/> Activer le bandeau</label>
              <label>Texte du bandeau<textarea maxLength={600} value={data.public_site.announcement_text} onChange={(e)=>site('announcement_text',e.target.value)} placeholder="Ex. Inscriptions ouvertes pour la prochaine session"/></label>
              <div className="school-announcement-colors">
                <label>Fond<input type="color" value={data.public_site.announcement_background_color} onChange={(e)=>site('announcement_background_color',e.target.value)}/></label>
                <label>Texte et icônes<input type="color" value={data.public_site.announcement_text_color} onChange={(e)=>site('announcement_text_color',e.target.value)}/></label>
              </div>
              {data.public_site.announcement_text.trim() && <div className="school-announcement-preview"><span>Aperçu</span><SchoolAnnouncementBanner text={data.public_site.announcement_text} backgroundColor={data.public_site.announcement_background_color} textColor={data.public_site.announcement_text_color}/></div>}
            </div>
            <label>Slogan<input value={data.public_site.tagline} onChange={(e)=>site('tagline',e.target.value)}/></label>
            <label>Titre du hero<input value={data.public_site.hero_title} onChange={(e)=>site('hero_title',e.target.value)}/></label>
            <label>Sous-titre du hero<textarea value={data.public_site.hero_subtitle} onChange={(e)=>site('hero_subtitle',e.target.value)}/></label>
            <label>Texte du bouton principal<input value={data.public_site.hero_cta_label} onChange={(e)=>site('hero_cta_label',e.target.value)}/></label>
            <label>Titre présentation<input value={data.public_site.about_title} onChange={(e)=>site('about_title',e.target.value)}/></label>
            <label>Présentation de l’école<textarea value={data.public_site.about_text} onChange={(e)=>site('about_text',e.target.value)}/></label>
            <label>Description SEO<textarea value={data.public_site.seo_description} onChange={(e)=>site('seo_description',e.target.value)}/></label>
          </section>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Coordonnées publiques</span><h2>Contact & pied de page</h2></div></div>
            <div className="school-site-form-grid">
              <label>Email<input type="email" value={data.public_site.contact_email || ''} onChange={(e)=>site('contact_email',e.target.value || null)}/></label>
              <label>Téléphone<input value={data.public_site.contact_phone || ''} onChange={(e)=>site('contact_phone',e.target.value || null)}/></label>
            </div>
            <label>Adresse<input value={data.public_site.contact_address || ''} onChange={(e)=>site('contact_address',e.target.value || null)}/></label>
            <label>Texte du footer<textarea value={data.public_site.footer_text} onChange={(e)=>site('footer_text',e.target.value)}/></label>
          </section>
        </>}

        {section === 'auth' && <>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Espace étudiant</span><h2>Connexion et inscription</h2><p>Ces réglages s’appliquent au panneau illustré des deux écrans, quand un étudiant se connecte ou crée son compte.</p></div></div>
            <div className="brand-assets-grid">
              <AssetPicker label="Photo d’arrière-plan" value={data.public_site.auth_background_image_url} onUpload={(e)=>void upload(e,'auth-background')} wide />
            </div>
            {data.public_site.auth_background_image_url && <button className="secondary-button compact-action" type="button" onClick={()=>site('auth_background_image_url',null)}>Rétablir l’image par défaut</button>}
            <label className="school-prefix-confirmation">
              <input type="checkbox" checked={data.public_site.auth_show_school_name} onChange={(e)=>site('auth_show_school_name',e.target.checked)}/>
              <span>Afficher le nom de l’école à côté du logo</span>
            </label>
            <p className="muted-note">Désactivez cette option pour n’afficher que le logo. Sans photo personnalisée, l’image actuelle reste utilisée.</p>
          </section>
          <section className="app-card school-site-section school-auth-brand-preview">
            <span className="section-label">Aperçu de l’en-tête</span>
            <div className="school-auth-brand-preview__sample" style={data.public_site.auth_background_image_url ? { backgroundImage: `linear-gradient(180deg, rgba(16, 35, 63, .72) 0%, rgba(16, 35, 63, .08) 30%, rgba(16, 35, 63, .16) 52%, rgba(16, 35, 63, .96) 100%), linear-gradient(145deg, rgba(16, 35, 63, .38), rgba(23, 63, 114, .20)), url("${data.public_site.auth_background_image_url.replaceAll('"', '%22')}")` } : undefined}>
              <SchoolLogo logoUrl={data.public_site.logo_url} alt={data.public_site.site_name || activeOrganization?.name || 'École'} className="platform-brand-logo" />
              {data.public_site.auth_show_school_name && <strong>{data.public_site.site_name || activeOrganization?.name}</strong>}
            </div>
            <small>Le même affichage est utilisé à gauche sur la connexion et l’inscription.</small>
          </section>
        </>}

        {section === 'legal' && <>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Facturation</span><h2>Identité légale & facturation</h2><p>Informations utilisées pour les factures et nécessaires avant publication du site.</p></div><ShieldCheck size={19}/></div>
            <div className="school-site-form-grid">
              <label>Raison sociale<input value={data.legal.legal_name} onChange={(e)=>legal('legal_name',e.target.value)}/></label>
              <label>N° registre / RCCM / SIRET<input value={data.legal.registration_number} onChange={(e)=>legal('registration_number',e.target.value)}/></label>
              <label>Identifiant fiscal<input value={data.legal.tax_number} onChange={(e)=>legal('tax_number',e.target.value)}/></label>
              <label>Devise par défaut
                <select value={data.legal.default_currency} onChange={(e)=>legal('default_currency',e.target.value)}>
                  {!POPULAR_CURRENCIES.some(({ code }) => code === data.legal.default_currency) && <option value={data.legal.default_currency}>{data.legal.default_currency} - devise actuelle non prise en charge</option>}
                  {POPULAR_CURRENCIES.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}
                </select>
                <small className="school-currency-help">Les tarifs publics seront convertis dans cette devise à titre indicatif. Le règlement reste demandé dans la devise de la formation.</small>
              </label>
              <label>Email facturation<input type="email" value={data.legal.invoice_email || ''} onChange={(e)=>legal('invoice_email',e.target.value || null)}/></label>
              <label>Téléphone facturation<input value={data.legal.invoice_phone || ''} onChange={(e)=>legal('invoice_phone',e.target.value || null)}/></label>
            </div>
            <label>Adresse légale<textarea value={data.legal.legal_address} onChange={(e)=>legal('legal_address',e.target.value)}/></label>
            <label>Pied de facture<textarea value={data.legal.invoice_footer} onChange={(e)=>legal('invoice_footer',e.target.value)}/></label>
          </section>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Pages juridiques</span><h2>Informations du footer</h2></div></div>
            <label>Mentions légales<textarea value={data.public_site.legal_notice} onChange={(e)=>site('legal_notice',e.target.value)}/></label>
            <label>Conditions générales de vente<textarea value={data.public_site.sales_terms} onChange={(e)=>site('sales_terms',e.target.value)}/></label>
            <label>Politique de confidentialité<textarea value={data.public_site.privacy_policy} onChange={(e)=>site('privacy_policy',e.target.value)}/></label>
            <label>Remboursement / annulation<textarea value={data.public_site.refund_policy} onChange={(e)=>site('refund_policy',e.target.value)}/></label>
          </section>
          <SchoolInvoicePreview identity={data} contactEmail={activeOrganization.contact_email} logoUrl={activeOrganization.logo_url}/>
        </>}

        {section === 'communications' && <>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Communications</span><h2>Email & WhatsApp</h2></div></div>
            <div className="school-site-form-grid">
              <label>Nom d’expéditeur<input value={data.communications.sender_name} onChange={(e)=>comm('sender_name',e.target.value)}/></label>
              <label>Reply-To<input type="email" value={data.communications.reply_to_email || ''} onChange={(e)=>comm('reply_to_email',e.target.value || null)}/></label>
              <label>Numéro WhatsApp<input value={data.communications.whatsapp_phone || ''} onChange={(e)=>comm('whatsapp_phone',e.target.value || null)}/></label>
            </div>
            <label>Signature email<textarea value={data.communications.email_signature} onChange={(e)=>comm('email_signature',e.target.value)}/></label>
            <label>Signature WhatsApp<textarea value={data.communications.whatsapp_signature} onChange={(e)=>comm('whatsapp_signature',e.target.value)}/></label>
          </section>
          <section className="app-card school-site-section">
            <div className="settings-section-heading"><div><span className="section-label">Documents</span><h2>Signature des certificats</h2></div></div>
            <div className="school-site-form-grid">
              <label>Nom du signataire<input value={data.certification.signer_name} onChange={(e)=>cert('signer_name',e.target.value)}/></label>
              <label>Fonction<input value={data.certification.signer_title} onChange={(e)=>cert('signer_title',e.target.value)}/></label>
            </div>
            <div className="brand-assets-grid">
              <AssetPicker label="Signature" value={data.certification.signature_url} onUpload={(e)=>void upload(e,'signature')}/>
              <AssetPicker label="Cachet" value={data.certification.stamp_url} onUpload={(e)=>void upload(e,'stamp')}/>
            </div>
            <label>Pied du certificat<textarea value={data.certification.certificate_footer} onChange={(e)=>cert('certificate_footer',e.target.value)}/></label>
          </section>
          <SchoolCertificatePreview identity={data} logoUrl={activeOrganization.logo_url}/>
        </>}

        <div className="school-site-savebar">
          {section === 'site' ? (
            <label className="school-site-publish"><input type="checkbox" checked={data.public_site.is_published} disabled={!data.public_site.is_published && publicationIssues.length > 0} onChange={(e)=>site('is_published',e.target.checked)}/> Site public publié</label>
          ) : <span className="school-site-savebar-label">Enregistrer cette section</span>}
          <button className="primary-button" disabled={working}><Save size={15}/>{working?'Enregistrement…':'Enregistrer'}</button>
        </div>
      </form>
    </div>
  )
}

function AssetPicker({label,value,onUpload,wide=false,schoolLogo=false}:{label:string;value:string|null;onUpload:(e:ChangeEvent<HTMLInputElement>)=>void;wide?:boolean;schoolLogo?:boolean}){
 return <label className={'brand-asset-picker '+(wide?'is-wide':'')}>{schoolLogo?<SchoolLogo logoUrl={value} alt={label}/>:value?<img src={value} alt={label}/>:<span><ImagePlus size={22}/></span>}<strong>{label}</strong><input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={onUpload}/><small>Cliquer pour remplacer</small></label>
}
