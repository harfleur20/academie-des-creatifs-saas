import { useOutletContext, useParams } from 'react-router-dom'
import type { PublicOutletContext } from '../public/SchoolPublicLayout'

export function SchoolLegalPage(){
 const {school}=useOutletContext<PublicOutletContext>();const {legalType}=useParams()
 const map:Record<string,{title:string;content:string}>={mentions:{title:'Mentions légales',content:school.site.legal_notice},cgv:{title:'Conditions générales de vente',content:school.site.terms_of_sale},confidentialite:{title:'Politique de confidentialité',content:school.site.privacy_policy},remboursement:{title:'Politique de remboursement et d’annulation',content:school.site.refund_policy}}
 const item=map[legalType||'mentions']||map.mentions
 return <main className="public-page public-legal"><header className="public-page-hero"><span className="public-kicker">Informations légales</span><h1>{item.title}</h1></header><article><p className="public-preline">{item.content||'Cette page n’a pas encore été renseignée par l’école.'}</p></article></main>
}
