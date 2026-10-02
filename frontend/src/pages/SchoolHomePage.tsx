import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { Link, useOutletContext } from 'react-router-dom'
import type { PublicOutletContext } from '../public/SchoolPublicLayout'
import { PublicFormationCard } from '../public/PublicFormationCard'

export function SchoolHomePage(){
 const {school}=useOutletContext<PublicOutletContext>()
 return <main>
  <section className="public-hero" style={school.site.hero_image_url?{backgroundImage:'linear-gradient(90deg,rgba(6,16,30,.82),rgba(6,16,30,.35)),url('+school.site.hero_image_url+')'}:undefined}><div><span>Bienvenue chez {school.name}</span><h1>{school.site.hero_title||'Apprenez, pratiquez, progressez.'}</h1><p>{school.site.hero_subtitle}</p><Link to={'/schools/'+school.slug+'/formations'}>{school.site.hero_button_label||'Découvrir nos formations'}<ArrowRight size={16}/></Link></div></section>
  <section className="public-section"><header><div><span className="public-kicker">Nos programmes</span><h2>Formations à découvrir</h2><p>Une sélection choisie par {school.name}.</p></div><Link to={'/schools/'+school.slug+'/formations'}>Voir toutes les formations <ArrowRight size={14}/></Link></header><div className="public-formation-grid">{school.featured_formations.map((formation)=><PublicFormationCard key={formation.id} schoolSlug={school.slug} formation={formation}/>)}</div></section>
  <section className="public-about"><div>{school.site.about_image_url&&<img src={school.site.about_image_url} alt={school.site.about_title}/>}</div><div><span className="public-kicker">Notre école</span><h2>{school.site.about_title}</h2><p>{school.site.about_text}</p><ul><li><CheckCircle2 size={16}/>Apprentissage structuré par sessions</li><li><CheckCircle2 size={16}/>Suivi pédagogique et évaluations</li><li><CheckCircle2 size={16}/>Certificat de fin de formation</li></ul></div></section>
 </main>
}
