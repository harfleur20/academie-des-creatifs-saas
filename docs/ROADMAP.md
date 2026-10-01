# Roadmap SaaS

## Lot 0 — Socle SaaS

Objectifs :

- conserver la stack actuelle ;
- séparer le SaaS du produit en production ;
- poser le monorepo frontend/backend ;
- créer la landing page publique ;
- préparer la reprise progressive des modules existants.

## Lot 1 — Multi-tenant

Le cœur de l'industrialisation.

À introduire :

- `organizations` ;
- `organization_members` ;
- contexte de tenant sur chaque requête ;
- `organization_id` sur les ressources métier concernées ;
- isolation stricte des requêtes ;
- tests de non-fuite inter-organisations ;
- rôle plateforme `SUPER_ADMIN`.

## Lot 2 — Gestion des écoles

- création d'une école ;
- propriétaires et administrateurs ;
- professeurs et intervenants ;
- étudiants ;
- invitations ;
- paramètres de l'organisation.

## Lot 3 — Abonnements

- plans ;
- fonctionnalités par plan ;
- quotas ;
- essai ;
- abonnement actif / suspendu / résilié ;
- renouvellement ;
- factures et paiements ;
- intégration Tara via une couche de paiement indépendante.

## Lot 4 — White-label

- logo ;
- couleurs ;
- identité ;
- sous-domaines ;
- domaines personnalisés ;
- emails brandés ;
- certificats brandés.

## Lot 5 — Super-admin

- écoles clientes ;
- abonnements ;
- usages ;
- revenus ;
- incidents ;
- support ;
- suspension / réactivation contrôlée.

## Lot 6 — Onboarding

- création autonome de l'école ;
- assistant de configuration ;
- choix du plan ;
- branding ;
- invitation des équipes ;
- création de la première formation.
