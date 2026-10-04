# Parité avec le site mère

Référence examinée le 4 octobre 2026 : copie locale de `harfleur20/academie-des-creatifs-front` dans `../AcademieCreatif-Vrai_siteweb` (arbre de travail non figé). Comparaison des routes et modèles ; les parcours n'ont pas encore été vérifiés écran par écran dans un navigateur.

| Parcours | Site mère | SaaS multi-écoles | Suite à donner |
| --- | --- | --- | --- |
| Catalogue, commande et paiement étudiant | Présents | Présents, avec séparation par école et paiement en plusieurs échéances | Vérifier les parcours complets sur mobile et sur domaine d'école. |
| Cours, ressources, quiz, devoirs et résultats | Présents | Routes et modèles présents pour professeur et étudiant | Comparer les règles de progression, les cas de suspension et les données visibles par rôle. |
| Classe, présence et certificats | Présents | Routes et modèles présents | Vérifier les écarts de calcul, d'émission et de téléchargement. |
| Parcours classique et guidé | Deux espaces distincts dans le site mère | Pages communes par rôle dans le SaaS | Décider quelles différences de pédagogie doivent être conservées selon le format de formation. |
| Messagerie entre utilisateurs | Routes et modèles dédiés | Pas de messagerie interne équivalente repérée | Étudier une messagerie isolée par école, session et participants. |
| Notifications dans l'application | Routes et modèles dédiés | Envois email et WhatsApp, sans boîte de notifications dans l'interface | Ajouter une boîte par utilisateur si elle fait partie du fonctionnement attendu. |
| Favoris des formations | Présents | Aucun parcours équivalent repéré | Prioriser après les fonctions pédagogiques et le suivi. |
| Classes en direct et enregistrements | Présents dans le site mère | Aucun parcours équivalent repéré dans le SaaS | Définir le besoin par école avant de reprendre l'intégration vidéo. |

Les fonctions d'événements et de billetterie du site mère existent dans un espace organisateur distinct. Leur reprise dans le SaaS école n'est pas présumée : elle demande une décision de périmètre.

## Sécurité et exploitation

- Les jetons d'accès du SaaS portent une version de session ; mot de passe et déconnexion révoquent toutes les sessions de ce compte. Les jetons du navigateur sont en `sessionStorage`, qui reste accessible aux scripts. Le passage à des sessions serveur par cookie `HttpOnly` avec protection CSRF reste à concevoir.
- Les messages sortants sont réclamés en base avant l'appel fournisseur. Un résultat incertain reste en revue manuelle dans l'écran Commerce. La clé d'idempotence Brevo aide pour les nouvelles tentatives dans sa fenêtre de validité ; SMTP et WhatsApp ne garantissent pas la déduplication côté fournisseur.
- Les tests de concurrence PostgreSQL sont exécutés par la CI. La validation locale utilise SQLite tant qu'un serveur PostgreSQL local n'est pas disponible.
