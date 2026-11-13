import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { LandingNavbar } from '../components/LandingNavbar'
import '../platform-legal.css'

type LegalPageId = 'mentions' | 'confidentialite' | 'cgv' | 'cgu'
type LegalSection = { title: string; paragraphs: string[] }

const documents: Record<LegalPageId, { title: string; introduction: string; sections: LegalSection[] }> = {
  mentions: {
    title: 'Mentions légales',
    introduction: 'Les informations ci-dessous identifient l’éditeur et les prestataires du site Académie des Créatifs.',
    sections: [
      {
        title: 'Éditeur du site',
        paragraphs: [
          'Nom commercial : Académie des Créatifs.',
          'Raison sociale, forme juridique, adresse du siège, numéro d’immatriculation et pays d’établissement : à compléter par l’éditeur.',
          'Directeur ou directrice de la publication : à renseigner.',
          'Contact : adresse électronique et coordonnées à renseigner.',
        ],
      },
      {
        title: 'Hébergement',
        paragraphs: [
          'Nom et coordonnées de l’hébergeur, localisation des serveurs et pays d’hébergement : à renseigner avant la mise en ligne.',
        ],
      },
      {
        title: 'Propriété intellectuelle',
        paragraphs: [
          'Les éléments originaux du site et du service (notamment les textes, marques, interfaces et éléments graphiques) sont protégés par les droits applicables. Toute réutilisation non autorisée est interdite.',
          'Les contenus publiés par les écoles et leurs utilisateurs restent soumis aux droits de leurs auteurs et aux autorisations nécessaires.',
        ],
      },
    ],
  },
  confidentialite: {
    title: 'Politique de confidentialité',
    introduction: 'Cette politique décrit, sous forme de projet, les traitements de données susceptibles d’être réalisés par la plateforme.',
    sections: [
      {
        title: 'Données traitées',
        paragraphs: [
          'Selon les fonctionnalités utilisées, le service peut traiter des données de compte et de contact, des informations sur les écoles et formations, des données de scolarité et de progression, des échanges effectués dans la plateforme ainsi que des données techniques et de sécurité.',
          'Les données de paiement et les informations relatives aux prestataires concernés doivent être précisées en fonction de la configuration effectivement déployée.',
        ],
      },
      {
        title: 'Finalités et rôles',
        paragraphs: [
          'Les données peuvent être utilisées pour créer et administrer les comptes, fournir les espaces de gestion et d’apprentissage, assurer le suivi pédagogique, traiter les demandes de support, sécuriser le service et gérer la facturation.',
          'Le rôle de l’Académie des Créatifs et de chaque école (responsable du traitement ou sous-traitant selon les opérations) doit être défini dans les contrats et pour chaque usage.',
        ],
      },
      {
        title: 'Base légale, destinataires et transferts',
        paragraphs: [
          'Les bases légales applicables, les catégories de destinataires, les prestataires techniques et de paiement ainsi que les éventuels transferts internationaux doivent être documentés avant publication.',
        ],
      },
      {
        title: 'Conservation et droits',
        paragraphs: [
          'Les durées de conservation doivent être fixées selon les finalités et les obligations applicables. Les personnes concernées peuvent exercer les droits prévus par la législation applicable en contactant le responsable du traitement, dont les coordonnées restent à renseigner.',
        ],
      },
      {
        title: 'Cookies et traceurs',
        paragraphs: [
          'Les cookies ou traceurs utilisés, leurs finalités, leur durée et les moyens de gérer les préférences doivent être décrits conformément aux outils activés sur le site.',
        ],
      },
    ],
  },
  cgv: {
    title: 'Conditions générales de vente',
    introduction: 'Projet de conditions encadrant la souscription et l’utilisation payante du service Académie des Créatifs par les écoles.',
    sections: [
      {
        title: 'Offres et souscription',
        paragraphs: [
          'Les fonctionnalités, limites, prix, taxes, période de facturation, éventuelle période d’essai et conditions de renouvellement sont ceux présentés avant la souscription et dans l’espace de facturation du client.',
          'L’identité du vendeur, les pays desservis et les règles applicables aux clients professionnels ou consommateurs sont à préciser.',
        ],
      },
      {
        title: 'Facturation et paiement',
        paragraphs: [
          'Les modalités de paiement, la devise, les échéances, les taxes et le rôle du prestataire de paiement doivent être indiqués conformément au parcours de souscription effectivement proposé.',
          'Toute évolution de prix et ses modalités de notification doivent être précisées dans la version définitive de ces conditions.',
        ],
      },
      {
        title: 'Durée, résiliation et remboursements',
        paragraphs: [
          'La durée de l’abonnement, ses modalités de renouvellement, les moyens de résiliation, leur date d’effet et les règles de remboursement doivent être renseignés selon les offres disponibles.',
        ],
      },
      {
        title: 'Disponibilité et responsabilité',
        paragraphs: [
          'Le service est fourni dans les limites décrites dans l’offre souscrite. Les engagements de disponibilité, les exclusions, les modalités de support et les limites de responsabilité doivent être adaptés au service et au droit applicable.',
        ],
      },
    ],
  },
  cgu: {
    title: 'Conditions générales d’utilisation',
    introduction: 'Ces règles de fonctionnement s’adressent aux écoles, enseignants et étudiants utilisant les espaces de la plateforme.',
    sections: [
      {
        title: 'Comptes et accès',
        paragraphs: [
          'Chaque utilisateur doit fournir des informations exactes, préserver la confidentialité de ses identifiants et signaler tout accès non autorisé. L’école est responsable de la gestion des accès qu’elle crée ou administre.',
        ],
      },
      {
        title: 'Utilisation autorisée',
        paragraphs: [
          'La plateforme doit être utilisée conformément à sa destination pédagogique et de gestion, aux lois applicables et aux droits des tiers. Il est interdit de tenter de compromettre le service, d’en perturber le fonctionnement ou d’utiliser les comptes sans autorisation.',
        ],
      },
      {
        title: 'Contenus et responsabilités',
        paragraphs: [
          'Les utilisateurs conservent leurs droits sur les contenus qu’ils publient et doivent disposer des autorisations nécessaires. Ils accordent à la plateforme les droits techniques strictement nécessaires à l’hébergement et à l’affichage de ces contenus pour fournir le service.',
          'L’école reste responsable des informations qu’elle publie et des données qu’elle renseigne dans ses espaces, sous réserve des rôles et obligations définis par les contrats applicables.',
        ],
      },
      {
        title: 'Sécurité et évolution du service',
        paragraphs: [
          'Des mesures raisonnables de sécurité sont mises en œuvre. Les accès peuvent être suspendus en cas d’incident de sécurité, d’utilisation illicite ou de manquement grave, selon une procédure à préciser dans la version définitive.',
          'Les modalités de maintenance, d’évolution du service et de notification des changements doivent être définies dans les conditions contractuelles applicables.',
        ],
      },
    ],
  },
}

const pageLinks: { id: LegalPageId; label: string; path: string }[] = [
  { id: 'mentions', label: 'Mentions légales', path: '/mentions-legales' },
  { id: 'confidentialite', label: 'Confidentialité', path: '/confidentialite' },
  { id: 'cgv', label: 'CGV', path: '/cgv' },
  { id: 'cgu', label: 'CGU', path: '/cgu' },
]

export function PlatformLegalPage({ page }: { page: LegalPageId }) {
  const document = documents[page]

  return (
    <div className="lp platform-legal">
      <LandingNavbar />
      <main className="platform-legal__main">
        <article className="platform-legal__document">
          <span className="platform-legal__eyebrow">Informations légales</span>
          <h1>{document.title}</h1>
          <p className="platform-legal__intro">{document.introduction}</p>
          <p className="platform-legal__notice" role="note">
            Document de travail : les informations propres à l’éditeur, aux prestataires, aux tarifs et au droit applicable sont à compléter et à faire valider avant publication.
          </p>

          <div className="platform-legal__sections">
            {document.sections.map((section) => (
              <section key={section.title}>
                <h2>{section.title}</h2>
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </section>
            ))}
          </div>

          <nav className="platform-legal__links" aria-label="Autres informations légales">
            {pageLinks.filter((link) => link.id !== page).map((link) => (
              <Link key={link.id} to={link.path}>{link.label}<ArrowRight size={14} /></Link>
            ))}
          </nav>
          <p className="platform-legal__footnote">
            Cette version est un projet de rédaction et ne remplace pas une validation juridique adaptée aux pays et activités concernés.
          </p>
        </article>
      </main>
    </div>
  )
}
