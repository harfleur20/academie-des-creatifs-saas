# Audit de réutilisation du produit actuel

## Principe

Le SaaS ne repart pas de zéro. Le dépôt actuel `academie-des-creatifs-front` reste la référence fonctionnelle du produit en production, tandis que les briques utiles sont reprises et adaptées dans le nouveau dépôt.

On évite cependant une copie aveugle de toute l'application : certaines parties sont fortement liées à la marque Académie des Créatifs ou à la boutique publique et ne doivent pas devenir des dépendances du cœur multi-tenant.

## Briques existantes à réutiliser

### Backend — forte réutilisation

Les services existants fournissent déjà une grande partie du moteur métier :

- authentification et sécurité ;
- formations et sessions ;
- professeurs et affectations ;
- pédagogie et accès aux cours ;
- badges et certificats ;
- lives et salles JaaS ;
- replays ;
- notifications ;
- emails ;
- WhatsApp / Wapino ;
- stockage Cloudinary / R2 ;
- optimisation des images ;
- paiements Tara ;
- échéanciers ;
- PDF pédagogiques et certificats ;
- planification et automatisations.

Ces services seront portés vers le SaaS en ajoutant progressivement le contexte `organization_id` et les règles d'autorisation multi-tenant.

### Frontend — forte réutilisation

Les interfaces existantes couvrent déjà :

- dashboard étudiant ;
- espace étudiant guidé ;
- dashboard professeur ;
- espace session professeur ;
- authentification ;
- invitations ;
- formations ;
- lives ;
- notifications ;
- messagerie ;
- certificats ;
- paramètres.

Le SaaS conservera ces parcours mais les rendra dépendants de l'organisation active et de son branding.

## Briques à adapter fortement

Les éléments suivants ne doivent pas être copiés sans transformation :

- administration globale actuelle ;
- gestion des utilisateurs ;
- formations et sessions ;
- paiements ;
- événements ;
- certificats ;
- notifications ;
- statistiques.

La raison principale est l'isolation : chaque lecture et écriture devra être contrainte par l'organisation active.

## Nouvelles briques SaaS

À créer spécifiquement :

- `organizations` ;
- `organization_members` ;
- rôles par organisation ;
- contexte de tenant ;
- plans SaaS ;
- abonnements SaaS ;
- quotas et compteurs d'usage ;
- fonctionnalités activées par plan ;
- branding ;
- sous-domaines ;
- domaines personnalisés ;
- dashboard propriétaire d'école ;
- super-admin plateforme ;
- onboarding autonome.

## Modules non prioritaires pour le noyau SaaS

Les fonctionnalités de boutique, panier, favoris et blog public ne sont pas nécessaires pour sécuriser le cœur multi-écoles.

Elles pourront être reprises plus tard comme modules optionnels si elles apportent une valeur commerciale aux écoles clientes.

## Stratégie de migration

1. Garder le dépôt actuel intact.
2. Construire le shell SaaS et la landing page.
3. Créer le modèle Organization et le contexte multi-tenant.
4. Porter en priorité l'authentification, les utilisateurs, formations, sessions, professeurs et étudiants.
5. Ajouter les tests d'isolation inter-écoles avant de porter les modules secondaires.
6. Porter ensuite planning, pédagogie, évaluations, live, certificats et automatisations.
7. Brancher les abonnements SaaS et les quotas.
8. Ajouter le white-label et les domaines personnalisés.

Cette approche permet de réutiliser le produit existant sans importer ses hypothèses mono-école dans la nouvelle architecture.
