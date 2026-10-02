import { Mail, MapPin, Phone } from 'lucide-react'
import { usePublicSchool } from '../public/SchoolPublicLayout'

export function SchoolContactPage(){
 const {school}=usePublicSchool()
 return <main className="school-section school-contact-page"><header className="school-page-heading"><span className="school-kicker">Contact</span><h1>Nous contacter</h1><p>Une question sur une formation ou une session ? Contactez directement l'école.</p></header><div className="school-contact-grid">{school.contact_email&&<a href={'mailto:'+school.contact_email}><Mail/><strong>Email</strong><span>{school.contact_email}</span></a>}{school.contact_phone&&<a href={'tel:'+school.contact_phone}><Phone/><strong>Téléphone</strong><span>{school.contact_phone}</span></a>}{school.contact_address&&<div><MapPin/><strong>Adresse</strong><span>{school.contact_address}</span></div>}</div></main>
}
