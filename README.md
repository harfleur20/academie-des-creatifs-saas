# Académie des Créatifs SaaS

Plateforme SaaS multi-écoles dérivée de l'Académie des Créatifs.

## Vision

Permettre à une école, un centre de formation, un formateur ou un organisme de louer une école digitale complète avec son propre espace, ses administrateurs, ses professeurs, ses étudiants, ses formations et ses outils pédagogiques.

## Stack

- Frontend : React 19, TypeScript, Vite, Mantine
- Backend : FastAPI, Python
- Base de données : PostgreSQL 16
- ORM / migrations : SQLAlchemy, Alembic
- Déploiement : Docker, Coolify
- Paiement : Tara
- Email : Brevo
- WhatsApp : Wapino
- Live : JaaS
- Stockage : Cloudinary / Cloudflare R2

## Méthode

Le développement se fait lot par lot sur des branches dédiées.

- Lot 0 : socle SaaS + landing page
- Lot 1 : architecture multi-tenant et isolation des données
- Lot 2 : gestion des écoles, membres et rôles
- Lot 3 : abonnements, plans, quotas et facturation
- Lot 4 : branding, white-label, sous-domaines et domaines personnalisés
- Lot 5 : super-admin SaaS
- Lot 6 : onboarding et automatisations

Le produit existant reste séparé afin de ne pas perturber la production actuelle.
