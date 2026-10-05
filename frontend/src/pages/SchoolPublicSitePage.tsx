import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { ExternalLink, ImagePlus, Palette, Save, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import { SchoolLogo } from '../brand/SchoolLogo'
import { schoolFontFamily, schoolFontOptions } from '../brand/schoolTypography'

const supportedFont = (name: string) => schoolFontOptions.some((option) => option.name === name) ? name : 'Inter'
import {
  ApiError,
  getSchoolIdentity,
  updateSchoolIdentity,
  uploadSchoolAsset,
  type SchoolIdentity,
} from '../lib/api'

export function SchoolPublicSitePage() {
  const { activeOrganization, refreshOrganizations } = useTenant()
  const [data, setData] = useState<SchoolIdentity | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)

  useEffect(() => {
    if (!activeOrganization) return
    getSchoolIdentity()
      .then((identity) => setData({
        ...identity,
        public_site: {
          ...identity.public_site,
          font_heading: supportedFont(identity.public_site.font_heading),
          font_body: supportedFont(identity.public_site.font_body),
        },
      }))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Chargement impossible.'))
  }, [activeOrganization?.id])

  function site<K extends keyof SchoolIdentity['public_site']>(key: K, value: SchoolIdentity['public_site'][K]) {
    setData((current) => current ? {
      ...current,
      public_site: { ...current.public_site, [key]: value },
    } : current)
  }

  function legal<K extends keyof SchoolIdentity['legal']>(key: K, value: SchoolIdentity['legal'][K]) {
    setData((current) => current ? { ...current, legal: { ...current.legal, [key]: value } } : current)
  }

  function comm<K extends keyof SchoolIdentity['communications']>(key: K, value: SchoolIdentity['communications'][K]) {
    setData((current) => current ? { ...current, communications: { ...current.communications, [key]: value } } : current)
  }

  function cert<K extends keyof SchoolIdentity['certification']>(key: K, value: SchoolIdentity['certification'][K]) {
    setData((current) => current ? { ...current, certification: { ...current.certification, [key]: value } } : current)
  }

  async function upload(
    event: ChangeEvent<HTMLInputElement>,
    target: 'logo' | 'favicon' | 'hero' | 'signature' | 'stamp',
  ) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setWorking(true)
    setError('')
    try {
      const asset = await uploadSchoolAsset(file)
      if (target === 'logo') site('logo_url', asset.public_url)
      if (target === 'favicon') site('favicon_url', asset.public_url)
      if (target === 'hero') site('hero_image_url', asset.public_url)
      if (target === 'signature') cert('signature_url', asset.public_url)
      if (target === 'stamp') cert('stamp_url', asset.public_url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload impossible.')
    } finally {
      setWorking(false)
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!data) return
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const moveToDraft = data.public_site.is_published && publicationIssues.length > 0
      const updated = await updateSchoolIdentity({
        ...data,
        public_site: { ...data.public_site, is_published: moveToDraft ? false : data.public_site.is_published },
      })
      setData(updated)
      await refreshOrganizations()
      setMessage(moveToDraft
        ? 'Identité enregistrée. Le site est passé en brouillon jusqu’à la fin de sa configuration.'
        : 'Identité et site public enregistrés.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.')
    } finally {
      setWorking(false)
    }
  }

  if (!activeOrganization) return <div className="page-state">Créez d’abord une école.</div>
  if (!data) return <div className="page-state">{error || 'Chargement de l’identité de l’école…'}</div>
  const publicationIssues = [
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
    !/^[A-Za-z]{3}$/.test(data.legal.default_currency.trim()) && 'Devise de facturation',
  ].filter((issue): issue is string => Boolean(issue))

  return <main className="app-page school-site-admin">
    <header className="app-page-header">
      <div>
        <span className="page-kicker">Identité & site public</span>
        <h1>Votre école, votre marque</h1>
        <p>Ces réglages s’appliquent au site public, aux espaces étudiant/professeur et aux communications de l’école.</p>
      </div>
      <Link className="secondary-button compact-action" target="_blank" to={'/school/' + data.slug}>
        <ExternalLink size={15}/> Voir le site public
      </Link>
    </header>

    {error && <div className="form-error">{error}</div>}
    {message && <div className="form-success">{message}</div>}
    {publicationIssues.length > 0 && <div className="app-card formation-readiness"><strong>À compléter avant de publier le site</strong>{data.public_site.is_published && <p>Ce site est déjà inaccessible au public. Son prochain enregistrement le passera en brouillon pour vous laisser terminer les étapes.</p>}<ul>{publicationIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}

    <form className="school-site-admin-form" onSubmit={save}>
      <section className="app-card school-site-section">
        <div className="settings-section-heading"><div><span className="section-label">Marque</span><h2>Logo & couleurs</h2></div><Palette size={19}/></div>
        <div className="brand-assets-grid">
          <AssetPicker label="Logo de l’école" value={data.public_site.logo_url} onUpload={(e)=>void upload(e,'logo')} schoolLogo />
          <AssetPicker label="Favicon" value={data.public_site.favicon_url} onUpload={(e)=>void upload(e,'favicon')} />
          <AssetPicker label="Image de couverture" value={data.public_site.hero_image_url} onUpload={(e)=>void upload(e,'hero')} wide />
        </div>
        <div className="school-site-form-grid">
          <label>Nom public<input value={data.public_site.site_name} onChange={(e)=>site('site_name',e.target.value)}/></label>
          <label>Préfixe matricule<input value={data.public_site.student_code_prefix} maxLength={8} onChange={(e)=>site('student_code_prefix',e.target.value.toUpperCase())} placeholder="SB"/></label>
          <label>Couleur principale<input type="color" value={data.public_site.primary_color} onChange={(e)=>site('primary_color',e.target.value)}/></label>
          <label>Couleur secondaire<input type="color" value={data.public_site.secondary_color} onChange={(e)=>site('secondary_color',e.target.value)}/></label>
          <label>Couleur accent<input type="color" value={data.public_site.accent_color} onChange={(e)=>site('accent_color',e.target.value)}/></label>
          <label>Police des titres<select value={schoolFontOptions.some((option) => option.name === data.public_site.font_heading) ? data.public_site.font_heading : 'Inter'} onChange={(e)=>site('font_heading',e.target.value)}>{schoolFontOptions.map((option) => <option key={option.name} value={option.name}>{option.name}</option>)}</select></label>
          <label>Police du texte<select value={schoolFontOptions.some((option) => option.name === data.public_site.font_body) ? data.public_site.font_body : 'Inter'} onChange={(e)=>site('font_body',e.target.value)}>{schoolFontOptions.map((option) => <option key={option.name} value={option.name}>{option.name}</option>)}</select></label>
        </div>
        <div className="school-typography-controls">
          <label htmlFor="school-font-size">Taille des textes <strong>{data.public_site.font_size_scale}%</strong></label>
          <input id="school-font-size" type="range" min="85" max="125" step="5" value={data.public_site.font_size_scale} onChange={(e)=>site('font_size_scale',Number(e.target.value))}/>
          <button className="secondary-button compact-action" type="button" onClick={()=>site('font_size_scale',100)}>Taille normale</button>
        </div>
        <div className="school-typography-preview" aria-label="Aperçu de la typographie">
          <strong style={{ fontFamily: schoolFontFamily(data.public_site.font_heading), fontSize: `${Math.round(28 * data.public_site.font_size_scale / 100)}px` }}>Découvrez nos formations</strong>
          <p style={{ fontFamily: schoolFontFamily(data.public_site.font_body), fontSize: `${Math.round(15 * data.public_site.font_size_scale / 100)}px` }}>Un aperçu immédiat des titres et des textes de votre école.</p>
        </div>
        <label className="school-prefix-confirmation">
          <input type="checkbox" checked={data.public_site.student_code_prefix_confirmed} disabled={data.public_site.student_code_prefix_confirmed || !activeOrganization.contact_email || !activeOrganization.subdomain} onChange={(e)=>site('student_code_prefix_confirmed',e.target.checked)}/>
          <span>{data.public_site.student_code_prefix_confirmed ? 'Préfixe confirmé pour cette école' : 'Je confirme ce préfixe pour les matricules des professeurs et étudiants.'}</span>
        </label>
        {(!activeOrganization.contact_email || !activeOrganization.subdomain) && !data.public_site.student_code_prefix_confirmed && <p className="muted-note">Renseignez d’abord l’email de contact et l’adresse de l’école dans <Link to="/app/manage/settings">Paramètres</Link>.</p>}
        <p className="muted-note">La valeur proposée est provisoire jusqu’à votre confirmation. Les matricules déjà attribués ne changent pas.</p>
      </section>

      <section className="app-card school-site-section">
        <div className="settings-section-heading"><div><span className="section-label">Accueil</span><h2>Hero & présentation</h2></div><ImagePlus size={19}/></div>
        <label>Slogan<input value={data.public_site.tagline} onChange={(e)=>site('tagline',e.target.value)}/></label>
        <label>Titre du hero<input value={data.public_site.hero_title} onChange={(e)=>site('hero_title',e.target.value)}/></label>
        <label>Sous-titre du hero<textarea value={data.public_site.hero_subtitle} onChange={(e)=>site('hero_subtitle',e.target.value)}/></label>
        <label>Texte du bouton principal<input value={data.public_site.hero_cta_label} onChange={(e)=>site('hero_cta_label',e.target.value)}/></label>
        <label>Titre présentation<input value={data.public_site.about_title} onChange={(e)=>site('about_title',e.target.value)}/></label>
        <label>Présentation de l’école<textarea value={data.public_site.about_text} onChange={(e)=>site('about_text',e.target.value)}/></label>
        <label>Description SEO<textarea value={data.public_site.seo_description} onChange={(e)=>site('seo_description',e.target.value)}/></label>
      </section>

      <section className="app-card school-site-section">
        <div className="settings-section-heading"><div><span className="section-label">Contact & footer</span><h2>Coordonnées publiques</h2></div></div>
        <div className="school-site-form-grid">
          <label>Email<input type="email" value={data.public_site.contact_email || ''} onChange={(e)=>site('contact_email',e.target.value || null)}/></label>
          <label>Téléphone<input value={data.public_site.contact_phone || ''} onChange={(e)=>site('contact_phone',e.target.value || null)}/></label>
        </div>
        <label>Adresse<input value={data.public_site.contact_address || ''} onChange={(e)=>site('contact_address',e.target.value || null)}/></label>
        <label>Texte du footer<textarea value={data.public_site.footer_text} onChange={(e)=>site('footer_text',e.target.value)}/></label>
      </section>

      <section className="app-card school-site-section">
        <div className="settings-section-heading"><div><span className="section-label">Documents</span><h2>Identité légale & facturation</h2><p>Ces quatre informations sont nécessaires avant toute publication et émission de facture. Les numéros d'enregistrement et fiscaux sont à renseigner selon votre situation.</p></div><ShieldCheck size={19}/></div>
        <div className="school-site-form-grid">
          <label>Raison sociale<input value={data.legal.legal_name} onChange={(e)=>legal('legal_name',e.target.value)}/></label>
          <label>N° registre / RCCM / SIRET<input value={data.legal.registration_number} onChange={(e)=>legal('registration_number',e.target.value)}/></label>
          <label>Identifiant fiscal<input value={data.legal.tax_number} onChange={(e)=>legal('tax_number',e.target.value)}/></label>
          <label>Devise par défaut<input value={data.legal.default_currency} maxLength={3} onChange={(e)=>legal('default_currency',e.target.value.toUpperCase())}/></label>
          <label>Email facturation<input type="email" value={data.legal.invoice_email || ''} onChange={(e)=>legal('invoice_email',e.target.value || null)}/></label>
          <label>Téléphone facturation<input value={data.legal.invoice_phone || ''} onChange={(e)=>legal('invoice_phone',e.target.value || null)}/></label>
        </div>
        <label>Adresse légale<textarea value={data.legal.legal_address} onChange={(e)=>legal('legal_address',e.target.value)}/></label>
        <label>Pied de facture<textarea value={data.legal.invoice_footer} onChange={(e)=>legal('invoice_footer',e.target.value)}/></label>
      </section>

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
        <div className="settings-section-heading"><div><span className="section-label">Certification</span><h2>Signature des certificats</h2></div></div>
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

      <section className="app-card school-site-section">
        <div className="settings-section-heading"><div><span className="section-label">Juridique</span><h2>Pages du footer</h2></div></div>
        <label>Mentions légales<textarea value={data.public_site.legal_notice} onChange={(e)=>site('legal_notice',e.target.value)}/></label>
        <label>Conditions générales de vente<textarea value={data.public_site.sales_terms} onChange={(e)=>site('sales_terms',e.target.value)}/></label>
        <label>Politique de confidentialité<textarea value={data.public_site.privacy_policy} onChange={(e)=>site('privacy_policy',e.target.value)}/></label>
        <label>Remboursement / annulation<textarea value={data.public_site.refund_policy} onChange={(e)=>site('refund_policy',e.target.value)}/></label>
      </section>

      <div className="school-site-savebar">
        <label className="school-site-publish"><input type="checkbox" checked={data.public_site.is_published} disabled={!data.public_site.is_published && publicationIssues.length > 0} onChange={(e)=>site('is_published',e.target.checked)}/> Site public publié</label>
        <button className="primary-button" disabled={working}><Save size={15}/>{working?'Enregistrement…':'Enregistrer'}</button>
      </div>
    </form>
  </main>
}

function AssetPicker({label,value,onUpload,wide=false,schoolLogo=false}:{label:string;value:string|null;onUpload:(e:ChangeEvent<HTMLInputElement>)=>void;wide?:boolean;schoolLogo?:boolean}){
 return <label className={'brand-asset-picker '+(wide?'is-wide':'')}>{schoolLogo?<SchoolLogo logoUrl={value} alt={label}/>:value?<img src={value} alt={label}/>:<span><ImagePlus size={22}/></span>}<strong>{label}</strong><input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={onUpload}/><small>Cliquer pour remplacer</small></label>
}
