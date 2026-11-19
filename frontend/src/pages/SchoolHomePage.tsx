import { ArrowRight, BookOpen, CalendarDays, GraduationCap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getPublicSchoolHome, type PublicFormationCard } from '../lib/api'
import { usePublicSchool } from '../public/SchoolPublicLayout'
import { formatSchoolMoney } from '../public/publicHelpers'
import { SchoolFavoriteButton } from '../public/SchoolFavoriteButton'
import { schoolPath } from '../public/schoolHost'
import { useSchoolSlug } from '../public/useSchoolHost'

export function SchoolHomePage() {
  const schoolSlug = useSchoolSlug()
  const { school } = usePublicSchool()
  const [formations, setFormations] = useState<PublicFormationCard[]>([])
  const [loadError, setLoadError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setLoadError('')
    getPublicSchoolHome(schoolSlug)
      .then((data) => { if (active) setFormations(data.featured_formations) })
      .catch(() => { if (active) setLoadError('Impossible de charger les formations à la une.') })
    return () => { active = false }
  }, [schoolSlug, retry])

  return <main>
    <section className="school-hero" style={school.hero_image_url ? { backgroundImage: 'linear-gradient(90deg, rgba(8,22,43,.82), rgba(8,22,43,.32)), url(' + school.hero_image_url + ')' } : undefined}>
      <div>
        <span data-no-translate>{school.tagline}</span>
        <h1 data-no-translate>{school.hero_title}</h1>
        <p data-no-translate>{school.hero_subtitle}</p>
        <Link to={schoolPath(schoolSlug, 'formations')}><span data-no-translate>{school.hero_cta_label}</span><ArrowRight size={16}/></Link>
      </div>
    </section>

    <section className="school-section school-about">
      <div><span className="school-kicker">Notre école</span><h2 data-no-translate>{school.about_title}</h2><p data-no-translate>{school.about_text || school.tagline}</p></div>
      <div className="school-about-values"><article><GraduationCap/><strong>Formations structurées</strong><span>Des parcours organisés par sessions.</span></article><article><CalendarDays/><strong>Planning clair</strong><span>Suivez vos cours, devoirs et évaluations.</span></article><article><BookOpen/><strong>Espace pédagogique</strong><span>Tout votre apprentissage au même endroit.</span></article></div>
    </section>

    <section className="school-section">
      <header className="school-section-heading school-home-featured-heading"><div><span className="school-kicker">À découvrir</span><h2>Nos formations à la une</h2></div><Link className="school-home-featured-link" to={schoolPath(schoolSlug, 'formations')}><span className="school-home-featured-link__desktop">Voir toutes les formations</span><span className="school-home-featured-link__mobile">Voir plus</span><ArrowRight size={15}/></Link></header>
      <div className="school-formation-grid">
        {formations.map((formation) => <FormationCard key={formation.id} schoolSlug={schoolSlug} formation={formation}/>)}
      </div>
      {loadError && <div className="school-empty">{loadError} <button type="button" onClick={() => setRetry((value) => value + 1)}>Réessayer</button></div>}
    </section>
  </main>
}

export function FormationCard({ schoolSlug, formation }: { schoolSlug: string; formation: PublicFormationCard }) {
  const { school, currencyRates } = usePublicSchool()
  return <article className="school-formation-card">
    <SchoolFavoriteButton slug={formation.slug} title={formation.title}/>
    <Link className="school-formation-image" to={schoolPath(schoolSlug, 'formations/' + formation.slug)}>
      {formation.cover_image_url ? <img src={formation.cover_image_url} alt={formation.title}/> : <div><GraduationCap size={34}/></div>}
      {formation.promotion_label && <span className="school-promo-badge" data-no-translate>{formation.promotion_label}</span>}
    </Link>
    <div className="school-formation-card-body">
      <div className="school-formation-meta"><span data-no-translate>{formation.category || 'Formation'}</span><span data-no-translate>{formation.level}</span></div>
      <h3><Link data-no-translate to={schoolPath(schoolSlug, 'formations/' + formation.slug)}>{formation.title}</Link></h3>
      <p data-no-translate>{formation.short_description}</p>
      <div className="school-formation-price">{formation.promotion_discount_cents > 0 && <del>{formatSchoolMoney(formation.price_cents, formation.currency, school.default_currency, currencyRates)}</del>}<strong>{formatSchoolMoney(formation.current_price_cents, formation.currency, school.default_currency, currencyRates)}</strong></div>
      <div className="school-formation-foot"><span>{formation.format_type === 'ligne' ? (formation.can_purchase ? 'Disponible en ligne' : 'Indisponible') : formation.available_session_count > 0 ? formation.available_session_count + ' session(s) disponible(s)' : 'Aucune session disponible'}</span><Link to={schoolPath(schoolSlug, 'formations/' + formation.slug)}>Voir la formation <ArrowRight size={14}/></Link></div>
    </div>
  </article>
}
