import { useParams } from 'react-router-dom'
import { usePublicSchool } from '../public/SchoolPublicLayout'

export function SchoolLegalPage(){
 const {school}=usePublicSchool();const path=window.location.pathname;const page=path.endsWith('/cgv')?'cgv':path.endsWith('/confidentialite')?'confidentialite':path.endsWith('/remboursement')?'remboursement':'mentions'
 const values:Record<string,{title:string;content:string}>={mentions:{title:'Mentions légales',content:school.legal_notice},cgv:{title:'Conditions générales de vente',content:school.sales_terms},confidentialite:{title:'Politique de confidentialité',content:school.privacy_policy},remboursement:{title:'Politique de remboursement et annulation',content:school.refund_policy}}
 const current=values[page||'']||values.mentions
 return <main className="school-section school-legal-page"><header className="school-page-heading"><span className="school-kicker">Informations</span><h1>{current.title}</h1></header><article>{current.content?<p className="school-preline">{current.content}</p>:<p>Cette page sera complétée prochainement par l'école.</p>}</article></main>
}
