import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  ArrowRight,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  FileText,
  Globe2,
  GraduationCap,
  Link2,
  Upload,
  UserRound,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../app/TenantContext'
import {
  acceptSchoolCharter,
  getPhoneCountries,
  getSchoolCharter,
  getTeacherProfessionalProfile,
  saveTeacherProfessionalProfile,
  uploadTeacherProfessionalDocument,
  type PhoneCountryOption,
  type SchoolCharter,
  type TeacherProfessionalProfile,
} from '../onboarding/workspaceOnboardingApi'
import '../teacher-contact-fields.css'

const OTHER_PROFESSION = '__other__'
const DEFAULT_PHONE_COUNTRY = 'CM'

const DIGITAL_PROFESSIONS = [
  'Graphiste / Designer graphique',
  'Motion Designer',
  'Développeur web',
  'Développeur mobile',
  'UX/UI Designer',
  'Photographe',
  'Vidéaste / Monteur vidéo',
  'Community Manager',
  'Social Media Manager / Content Creator',
  'Spécialiste marketing digital',
  'Data Analyst',
  'Artiste 3D / Animateur 3D',
  'DevOps / Cloud Engineer',
] as const

function toList(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function toText(values: string[]) {
  return values.join(', ')
}

function flagForCountry(code: string) {
  return code
    .toUpperCase()
    .replace(/[A-Z]/g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)))
}

function localPhoneValue(phone: string | null, dialCode: string) {
  if (!phone) return ''
  if (dialCode && phone.startsWith(dialCode)) return phone.slice(dialCode.length)
  return phone
}

function normalizeLanguageName(value: string) {
  return value.trim().toLocaleLowerCase('fr-FR')
}

export function TeacherSetupPage() {
  const navigate = useNavigate()
  const { activeOrganization } = useTenant()
  const [profile, setProfile] = useState<TeacherProfessionalProfile | null>(null)
  const [charter, setCharter] = useState<SchoolCharter | null>(null)
  const [phoneCountries, setPhoneCountries] = useState<PhoneCountryOption[]>([])
  const [professionalTitleChoice, setProfessionalTitleChoice] = useState('')
  const [customProfessionalTitle, setCustomProfessionalTitle] = useState('')
  const [experienceYears, setExperienceYears] = useState('')
  const [domains, setDomains] = useState('')
  const [bio, setBio] = useState('')
  const [skills, setSkills] = useState('')
  const [teachesFrench, setTeachesFrench] = useState(false)
  const [teachesEnglish, setTeachesEnglish] = useState(false)
  const [teachesOther, setTeachesOther] = useState(false)
  const [otherLanguages, setOtherLanguages] = useState('')
  const [whatsappCountry, setWhatsappCountry] = useState(DEFAULT_PHONE_COUNTRY)
  const [whatsappPhone, setWhatsappPhone] = useState('')
  const [portfolioUrl, setPortfolioUrl] = useState('')
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [behanceUrl, setBehanceUrl] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [city, setCity] = useState('')
  const [country, setCountry] = useState('')
  const [charterAccepted, setCharterAccepted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [uploading, setUploading] = useState<'portfolio' | 'cv' | null>(null)
  const [error, setError] = useState('')

  const regionNames = useMemo(() => new Intl.DisplayNames(['fr-FR'], { type: 'region' }), [])

  const sortedPhoneCountries = useMemo(() => (
    [...phoneCountries].sort((a, b) => (
      (regionNames.of(a.code) || a.code).localeCompare(regionNames.of(b.code) || b.code, 'fr-FR')
    ))
  ), [phoneCountries, regionNames])

  const selectedPhoneCountry = phoneCountries.find((item) => item.code === whatsappCountry)
    || phoneCountries.find((item) => item.code === DEFAULT_PHONE_COUNTRY)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.all([
      getTeacherProfessionalProfile(),
      getSchoolCharter('teacher'),
      getPhoneCountries(),
    ])
      .then(([nextProfile, nextCharter, countries]) => {
        if (!active) return
        setProfile(nextProfile)
        setCharter(nextCharter)
        setPhoneCountries(countries)

        if (DIGITAL_PROFESSIONS.some((title) => title === nextProfile.professional_title)) {
          setProfessionalTitleChoice(nextProfile.professional_title)
          setCustomProfessionalTitle('')
        } else if (nextProfile.professional_title) {
          setProfessionalTitleChoice(OTHER_PROFESSION)
          setCustomProfessionalTitle(nextProfile.professional_title)
        } else {
          setProfessionalTitleChoice('')
          setCustomProfessionalTitle('')
        }

        setExperienceYears(String(nextProfile.experience_years))
        setDomains(toText(nextProfile.activity_domains))
        setBio(nextProfile.bio)
        setSkills(toText(nextProfile.skills))

        const other = nextProfile.languages.filter((language) => {
          const normalized = normalizeLanguageName(language)
          return normalized !== 'français' && normalized !== 'francais' && normalized !== 'anglais'
        })
        setTeachesFrench(nextProfile.languages.some((language) => {
          const normalized = normalizeLanguageName(language)
          return normalized === 'français' || normalized === 'francais'
        }))
        setTeachesEnglish(nextProfile.languages.some((language) => normalizeLanguageName(language) === 'anglais'))
        setTeachesOther(other.length > 0)
        setOtherLanguages(toText(other))

        const phoneCountry = nextProfile.whatsapp_country || DEFAULT_PHONE_COUNTRY
        const phoneCountryRow = countries.find((item) => item.code === phoneCountry)
          || countries.find((item) => item.code === DEFAULT_PHONE_COUNTRY)
        setWhatsappCountry(phoneCountryRow?.code || DEFAULT_PHONE_COUNTRY)
        setWhatsappPhone(localPhoneValue(nextProfile.whatsapp_phone, phoneCountryRow?.dial_code || '+237'))

        setPortfolioUrl(nextProfile.portfolio_url || '')
        setLinkedinUrl(nextProfile.linkedin_url || '')
        setBehanceUrl(nextProfile.behance_url || '')
        setGithubUrl(nextProfile.github_url || '')
        setWebsiteUrl(nextProfile.website_url || '')
        setCity(nextProfile.city || '')
        setCountry(nextProfile.country || '')
        setCharterAccepted(nextCharter.accepted_current_version)
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Impossible de préparer votre fiche enseignant.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [activeOrganization?.id])

  const identityInitials = useMemo(() => (
    (profile?.full_name || '?')
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase()
  ), [profile?.full_name])

  async function upload(kind: 'portfolio' | 'cv', event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setUploading(kind)
    setError('')
    try {
      const next = await uploadTeacherProfessionalDocument(kind, file)
      setProfile(next)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Téléversement impossible.')
    } finally {
      setUploading(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')

    const professionalTitle = professionalTitleChoice === OTHER_PROFESSION
      ? customProfessionalTitle.trim()
      : professionalTitleChoice.trim()
    const experienceText = experienceYears.trim()
    const experienceNumber = Number(experienceText)
    const domainList = toList(domains)
    const skillList = toList(skills)
    const languageList = [
      ...(teachesFrench ? ['Français'] : []),
      ...(teachesEnglish ? ['Anglais'] : []),
      ...(teachesOther ? toList(otherLanguages) : []),
    ]

    if (!professionalTitle || domainList.length === 0 || skillList.length === 0 || bio.trim().length < 40) {
      setError('Complétez le métier, les domaines, les compétences et une bio d’au moins 40 caractères.')
      return
    }
    if (!experienceText || !Number.isInteger(experienceNumber) || experienceNumber < 0 || experienceNumber > 80) {
      setError('Renseignez un nombre d’années d’expérience compris entre 0 et 80.')
      return
    }
    if (languageList.length === 0) {
      setError('Choisissez au moins une langue d’enseignement.')
      return
    }
    if (teachesOther && toList(otherLanguages).length === 0) {
      setError('Précisez la ou les autres langues d’enseignement.')
      return
    }
    if (!whatsappCountry || !whatsappPhone.trim()) {
      setError('Renseignez votre numéro WhatsApp.')
      return
    }
    if (!portfolioUrl.trim() && !profile?.portfolio_file_name) {
      setError('Ajoutez votre portfolio avec une URL ou un fichier PDF.')
      return
    }
    if (charter?.is_enabled && !charterAccepted) {
      setError('Vous devez accepter la charte enseignant pour accéder à votre espace.')
      return
    }

    setWorking(true)
    try {
      const saved = await saveTeacherProfessionalProfile({
        professional_title: professionalTitle,
        experience_years: experienceNumber,
        activity_domains: domainList,
        bio: bio.trim(),
        skills: skillList,
        languages: languageList,
        whatsapp_phone: whatsappPhone.trim(),
        whatsapp_country: whatsappCountry,
        portfolio_url: portfolioUrl.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        behance_url: behanceUrl.trim() || null,
        github_url: githubUrl.trim() || null,
        website_url: websiteUrl.trim() || null,
        city: city.trim() || null,
        country: country.trim() || null,
      })
      setProfile(saved)
      if (!saved.is_complete) {
        setError('Votre fiche n’est pas encore complète. Vérifiez les informations obligatoires.')
        return
      }
      if (charter?.is_enabled && !charter.accepted_current_version) {
        await acceptSchoolCharter('teacher')
      }
      navigate('/app/teacher', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Impossible d’enregistrer votre fiche.')
    } finally {
      setWorking(false)
    }
  }

  if (loading) return <div className="app-loading">Préparation de votre fiche enseignant…</div>

  return (
    <main className="teacher-onboarding-page">
      <header className="teacher-onboarding-hero">
        <div>
          <span className="page-kicker">Bienvenue dans {profile?.organization_name || activeOrganization?.name}</span>
          <h1>Complétez votre fiche enseignant.</h1>
          <p>Ces informations doivent être finalisées avant de pouvoir commencer à donner cours.</p>
        </div>
        <div className="teacher-onboarding-progress">
          <span>1</span><i /> <span>2</span><i /> <span>3</span>
        </div>
      </header>

      {error && <div className="form-error teacher-onboarding-error">{error}</div>}

      <form className="teacher-onboarding-form" onSubmit={submit}>
        <section className="teacher-onboarding-card teacher-identity-card">
          <div className="teacher-onboarding-section-title">
            <div><span className="section-label">Étape 1</span><h2>Votre identité</h2></div>
            <UserRound size={21} />
          </div>
          <div className="teacher-identity-summary">
            <div className="teacher-identity-avatar">
              {profile?.avatar_url ? <img src={profile.avatar_url} alt={profile.full_name} /> : <span>{identityInitials}</span>}
            </div>
            <div><strong>{profile?.full_name}</strong><small>{profile?.email}</small></div>
            {profile?.teacher_code && <span className="teacher-code-chip">{profile.teacher_code}</span>}
          </div>
          <div className="teacher-onboarding-grid two">
            <label>Nom complet<input value={profile?.full_name || ''} readOnly /></label>
            <label>Adresse e-mail<input value={profile?.email || ''} readOnly /></label>

            <div className="span-two teacher-whatsapp-field">
              <span className="teacher-input-label">Numéro WhatsApp *</span>
              <div className="teacher-phone-control">
                <div className="teacher-country-picker" title={regionNames.of(whatsappCountry) || 'Pays du numéro WhatsApp'}>
                  <span className="teacher-country-flag" aria-hidden="true">
                    {flagForCountry(whatsappCountry || DEFAULT_PHONE_COUNTRY)}
                  </span>
                  <ChevronDown size={14} aria-hidden="true" />
                  <select
                    aria-label="Pays du numéro WhatsApp"
                    value={whatsappCountry}
                    onChange={(event) => setWhatsappCountry(event.target.value)}
                    required
                  >
                    {sortedPhoneCountries.map((item) => (
                      <option key={item.code} value={item.code}>
                        {flagForCountry(item.code)} {regionNames.of(item.code) || item.code} ({item.dial_code})
                      </option>
                    ))}
                  </select>
                </div>
                <span className="teacher-phone-dial-code">{selectedPhoneCountry?.dial_code || '+237'}</span>
                <input
                  aria-label="Numéro WhatsApp"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  value={whatsappPhone}
                  onChange={(event) => setWhatsappPhone(event.target.value)}
                  placeholder="6 77 12 34 56"
                  required
                />
              </div>
              <small className="teacher-field-help">
                Cameroun (+237) est sélectionné par défaut. Cliquez sur le drapeau pour changer de pays. Le format international est contrôlé automatiquement.
              </small>
              {profile?.whatsapp_phone_legacy && (
                <small className="teacher-legacy-phone-note">
                  Ancien format WhatsApp détecté : le numéro est conservé sans transformation arbitraire et devra être confirmé lors de la future vérification WhatsApp.
                </small>
              )}
            </div>

            <label className="span-two">École<input value={profile?.organization_name || ''} readOnly /></label>
          </div>
        </section>

        <section className="teacher-onboarding-card">
          <div className="teacher-onboarding-section-title">
            <div><span className="section-label">Étape 2</span><h2>Votre expertise</h2></div>
            <BriefcaseBusiness size={21} />
          </div>
          <div className="teacher-onboarding-grid two">
            <label>
              Intitulé professionnel *
              <select value={professionalTitleChoice} onChange={(event) => setProfessionalTitleChoice(event.target.value)} required>
                <option value="">Choisir un métier</option>
                {DIGITAL_PROFESSIONS.map((profession) => <option key={profession} value={profession}>{profession}</option>)}
                <option value={OTHER_PROFESSION}>Autre</option>
              </select>
            </label>
            <label>
              Années d’expérience *
              <input
                type="number"
                min={0}
                max={80}
                step={1}
                value={experienceYears}
                onChange={(event) => setExperienceYears(event.target.value)}
                placeholder="Ex. 5"
                required
              />
            </label>
            {professionalTitleChoice === OTHER_PROFESSION && (
              <label className="span-two">
                Précisez votre métier *
                <input
                  value={customProfessionalTitle}
                  onChange={(event) => setCustomProfessionalTitle(event.target.value)}
                  placeholder="Ex. Consultant SEO"
                  maxLength={180}
                  required
                />
              </label>
            )}
            <label className="span-two">Domaines d’activité *<input value={domains} onChange={(e) => setDomains(e.target.value)} placeholder="Motion design, Design graphique, 3D" /><small>Séparez les domaines par des virgules.</small></label>
            <label className="span-two">Compétences / spécialités *<input value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="After Effects, Blender, Figma" /><small>Séparez les compétences par des virgules.</small></label>
            <label className="span-two">Bio professionnelle *<textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={5} maxLength={2000} placeholder="Présentez votre parcours, votre manière d’enseigner et votre expertise…" /><small>{bio.length}/2000 · minimum 40 caractères</small></label>
            <label>Ville<input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Douala" /></label>
            <label>Pays<input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Cameroun" /></label>

            <fieldset className="span-two teacher-language-fieldset">
              <legend>Langues d’enseignement *</legend>
              <div className="teacher-language-options">
                <label className={teachesFrench ? 'is-selected' : ''}>
                  <input type="checkbox" checked={teachesFrench} onChange={(event) => setTeachesFrench(event.target.checked)} />
                  Français
                </label>
                <label className={teachesEnglish ? 'is-selected' : ''}>
                  <input type="checkbox" checked={teachesEnglish} onChange={(event) => setTeachesEnglish(event.target.checked)} />
                  Anglais
                </label>
                <label className={teachesOther ? 'is-selected' : ''}>
                  <input type="checkbox" checked={teachesOther} onChange={(event) => setTeachesOther(event.target.checked)} />
                  Autre
                </label>
              </div>
              {teachesOther && (
                <label className="teacher-other-language">
                  Précisez la ou les autres langues *
                  <input value={otherLanguages} onChange={(event) => setOtherLanguages(event.target.value)} placeholder="Ex. Espagnol, Allemand" required />
                  <small>Séparez plusieurs langues par des virgules.</small>
                </label>
              )}
            </fieldset>
          </div>

          <div className="teacher-documents-grid">
            <div className="teacher-document-box">
              <Globe2 size={20} />
              <div><strong>Portfolio *</strong><small>Ajoutez une URL ou un PDF.</small></div>
              <input type="url" value={portfolioUrl} onChange={(e) => setPortfolioUrl(e.target.value)} placeholder="https://monportfolio.com" />
              <label className="teacher-upload-button"><Upload size={15} /> {uploading === 'portfolio' ? 'Téléversement…' : profile?.portfolio_file_name || 'Importer un PDF'}<input type="file" accept="application/pdf" onChange={(e) => void upload('portfolio', e)} disabled={Boolean(uploading)} /></label>
            </div>
            <div className="teacher-document-box">
              <FileText size={20} />
              <div><strong>CV</strong><small>Facultatif · PDF · 10 Mo max.</small></div>
              <label className="teacher-upload-button"><Upload size={15} /> {uploading === 'cv' ? 'Téléversement…' : profile?.cv_file_name || 'Importer mon CV'}<input type="file" accept="application/pdf" onChange={(e) => void upload('cv', e)} disabled={Boolean(uploading)} /></label>
            </div>
          </div>

          <div className="teacher-onboarding-grid two professional-links-grid">
            <label><Link2 size={14} /> LinkedIn<input type="url" value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} placeholder="https://linkedin.com/in/..." /></label>
            <label><Link2 size={14} /> Behance<input type="url" value={behanceUrl} onChange={(e) => setBehanceUrl(e.target.value)} placeholder="https://behance.net/..." /></label>
            <label><Link2 size={14} /> GitHub<input type="url" value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} placeholder="https://github.com/..." /></label>
            <label><Link2 size={14} /> Site personnel<input type="url" value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)} placeholder="https://..." /></label>
          </div>
        </section>

        <section className="teacher-onboarding-card charter-validation-card">
          <div className="teacher-onboarding-section-title">
            <div><span className="section-label">Étape 3</span><h2>{charter?.title || 'Charte enseignant'}</h2></div>
            <GraduationCap size={21} />
          </div>
          {charter?.is_enabled ? (
            <>
              <div className="charter-scroll-box">{charter.content}</div>
              <label className="charter-accept-row">
                <input type="checkbox" checked={charterAccepted} onChange={(e) => setCharterAccepted(e.target.checked)} />
                <span><strong>J’ai lu et j’accepte cette charte.</strong><small>Version {charter.version}. Votre validation est enregistrée avec sa date.</small></span>
              </label>
            </>
          ) : (
            <div className="charter-disabled-note"><Check size={17} /> La validation de la charte enseignant est désactivée par l’école.</div>
          )}
        </section>

        <div className="teacher-onboarding-submit">
          <button className="primary-button" disabled={working || Boolean(uploading)}>
            {working ? 'Enregistrement…' : 'Terminer et accéder à mon espace'}
            {!working && <ArrowRight size={17} />}
          </button>
        </div>
      </form>
    </main>
  )
}
