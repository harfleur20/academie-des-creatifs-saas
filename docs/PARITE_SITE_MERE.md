# Parité avec le site mère

Référence examinée le 4 octobre 2026 : `harfleur20/academie-des-creatifs-front`, copie locale dans `../AcademieCreatif-Vrai_siteweb`, commit `fbf0b3f`. Son arbre de travail contient aussi des modifications non commitées. Pour chaque reprise, comparer le comportement avec le code du site mère et préserver l'isolation par école. Les parcours n'ont pas encore été vérifiés écran par écran dans un navigateur.

## Règle de reprise

Le site mère définit les parcours et les règles métier de l'école. Le SaaS reprend ces comportements pour chaque école, sans concevoir une autre pédagogie. Les adaptations nécessaires concernent l'identité de l'école, ses utilisateurs, ses données et son domaine. Une route ou une table présente dans le SaaS ne suffit pas à déclarer un parcours équivalent : il faut comparer les états, les droits, les calculs et l'interface.

| Parcours | Site mère | SaaS multi-écoles | Suite à donner |
| --- | --- | --- | --- |
| Catalogue, commande et paiement étudiant | Présents | Présents, avec séparation par école et paiement en plusieurs échéances | Vérifier les parcours complets sur mobile et sur domaine d'école. |
| Cours, ressources, quiz, devoirs et résultats | Présents | Cours publiés filtrés ; leçons vidéo suivies ; quiz et devoirs guidés verrouillés jusqu'à leur ouverture | Reprendre les liens entre leçon et évaluation, les tentatives différées et les calculs complets du site mère. |
| Classe, présence et certificats | Présents | Routes et modèles présents | Vérifier les écarts de calcul, d'émission et de téléchargement. |
| Parcours classique et guidé | `ligne` ouvre le parcours `classic` ; `live` et `presentiel` ouvrent le parcours `guided` | Routes par inscription et cartes séparées ; le lecteur reste commun | Reprendre l'interface complète du lecteur classique et du suivi guidé du site mère. |
| Messagerie entre utilisateurs | Conversations et destinataires autorisés selon les rôles et les inscriptions | Pas de messagerie interne équivalente repérée | Porter ce parcours avec isolation par école, session et participants. |
| Notifications dans l'application | Boîte et indicateur de notifications | Envois email et WhatsApp, sans boîte dans l'interface | Porter la boîte et ses événements pour chaque école. |
| Favoris des formations | Présents | Aucun parcours équivalent repéré | Reprendre le comportement du catalogue du site mère. |
| Classes en direct et enregistrements | Présents | Aucun parcours équivalent repéré dans le SaaS | Porter les accès et enregistrements utilisés par les formations `live` de chaque école. |

Les fonctions d'événements et de billetterie du site mère sont dans un espace organisateur distinct de l'école. La comparaison de l'école se concentre d'abord sur les parcours public, administration, professeur et étudiant.

## Écart pédagogique vérifié dans le code

- Le site mère n'expose que les cours et leçons publiés aux étudiants (`backend/app/api/routes/me.py`). Le SaaS exposait aussi les cours `draft`. Le premier correctif de reprise filtre désormais les cours publiés dans le lecteur, le compteur étudiant et le calcul de progression ; une leçon d'un cours brouillon ne peut plus être validée.
- Le site mère valide une vidéo à partir d'un suivi de lecture (seuil de 80 %) (`backend/app/api/routes/me.py`). Le SaaS suit maintenant les plages lues par inscription et retire la validation manuelle des vidéos. Les lecteurs directs, YouTube et Vimeo transmettent la progression ; le lecteur intégré Bunny reste à raccorder.
- Le site mère verrouille les activités guidées selon le début de session, le créneau et la publication (`backend/app/services/pedagogy_access.py`). Le SaaS reprend le début de session pour les cours, quiz et devoirs, le créneau pour les activités liées, et l'exception des ressources préparatoires. Les leçons du SaaS n'ont pas encore les liens et dates de disponibilité du modèle du site mère.
- Le site mère lie les quiz, PDF de validation et devoirs à certaines leçons ; leurs résultats terminent ces leçons automatiquement. Le SaaS possède actuellement des quiz et devoirs séparés des leçons. La tentative à trois essais existe, mais le délai de réessai du site mère n'est pas encore repris. Le lecteur du SaaS ne doit donc pas être présenté comme un parcours pédagogique entièrement équivalent.

Ordre de reprise : parcours étudiant classique et guidé, règles de progression et d'évaluation, suivi professeur/administration, puis messagerie, notifications et fonctions de catalogue. Chaque étape doit être testée sur deux écoles pour vérifier qu'aucune donnée ne traverse la frontière entre elles.

## Sécurité et exploitation

- Les jetons d'accès du SaaS portent une version de session ; mot de passe et déconnexion révoquent toutes les sessions de ce compte. Les jetons du navigateur sont en `sessionStorage`, qui reste accessible aux scripts. Le passage à des sessions serveur par cookie `HttpOnly` avec protection CSRF reste à concevoir.
- Les messages sortants sont réclamés en base avant l'appel fournisseur. Un résultat incertain reste en revue manuelle dans l'écran Commerce. La clé d'idempotence Brevo aide pour les nouvelles tentatives dans sa fenêtre de validité ; SMTP et WhatsApp ne garantissent pas la déduplication côté fournisseur.
- Les tests de concurrence PostgreSQL sont exécutés par la CI. La validation locale utilise SQLite tant qu'un serveur PostgreSQL local n'est pas disponible.
