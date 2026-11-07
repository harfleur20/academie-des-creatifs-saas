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
- Paiement : TaraMoney + mode démo local
- Email : Brevo
- WhatsApp : Wapino
- Live : JaaS
- Stockage : Cloudinary / Cloudflare R2

## Lancer le projet en local

Prérequis : Git, Node.js 22+, npm, Python 3.12+ et PostgreSQL 16 si vous utilisez la base cible. SQLite peut être utilisé pour un test local rapide.

### 1. Cloner le dépôt

```bash
git clone git@github.com:harfleur20/academie-des-creatifs-saas.git
cd academie-des-creatifs-saas
```

### 2. Préparer le backend

Depuis Git Bash sous Windows :

```bash
cd backend
py -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Éditez ensuite `backend/.env`.

Pour PostgreSQL, créez une base `academie_saas` et adaptez `DATABASE_URL`.

Pour un test rapide sans PostgreSQL, utilisez :

```env
DATABASE_URL=sqlite:///./academie_saas.db
```

Le mode de paiement local recommandé est déjà :

```env
APP_ENV=development
PAYMENT_MODE=demo
ALLOW_DEMO_PAYMENTS=true
```

Aucune clé TaraMoney réelle n'est nécessaire dans ce mode.

Appliquez les migrations puis démarrez l'API :

```bash
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Après chaque mise à jour du code, relancez `alembic upgrade head` depuis `backend` avant de consulter les pages. Une base en retard peut laisser `/health` répondre `200` alors que les onglets métier renvoient `500`. Vérifiez la version avec `alembic current` et comparez-la à `alembic heads`.

Vérifications :

- API : `http://localhost:8000/health`
- Documentation FastAPI : `http://localhost:8000/docs`

Les tâches horaires (abonnements, paiements étudiants, rappels de devoirs et envoi des emails) tournent en production via GitHub Actions. En local, lancez-les dans un second terminal depuis `backend` avec `python scripts/run_cron_jobs.py --every 15`. Voir [docs/BILLING_AUTOMATION.md](docs/BILLING_AUTOMATION.md).

### 3. Préparer le frontend

Dans un second terminal Git Bash :

```bash
cd academie-des-creatifs-saas/frontend
cp .env.example .env
npm install
npm run dev
```

Le frontend est disponible sur :

```
http://localhost:3000
```

En développement, Vite redirige automatiquement `/api` vers `http://localhost:8000`.

### 4. Tester le parcours SaaS

1. Ouvrez `http://localhost:3000`.
2. Créez un compte.
3. Créez votre première école.
4. Ouvrez **Abonnement**.
5. En mode démo, choisissez un forfait puis confirmez le paiement de test.
6. Testez ensuite **Équipe & accès** et **Paramètres**.

### 5. Tests et build

Backend :

```bash
cd backend
source .venv/Scripts/activate
pytest
```

Frontend :

```bash
cd frontend
npm run typecheck
npm run build
```

## Environnements

- `backend/.env.example` contient toutes les variables backend actuellement utilisées, y compris TaraMoney, mode démo et cycle d'abonnement.
- `frontend/.env.example` contient l'URL API locale / proxy Vite.
- Les vrais fichiers `.env` sont ignorés par Git.

### Mise à jour du commerce et des fichiers pédagogiques

Après la mise à jour, appliquez les migrations depuis `backend` avec `alembic upgrade head`. En production, définissez un `JWT_SECRET_KEY` unique d'au moins 32 caractères. Les notifications TaraMoney doivent être signées avec `TARAMONEY_WEBHOOK_SECRET` ou porter le secret dans l'en-tête configuré par `TARAMONEY_WEBHOOK_SECRET_HEADER` ; un `businessId` dans le corps ne suffit plus.

Pour les remises de devoirs sur R2, configurez `R2_PRIVATE_BUCKET_NAME` avec un bucket **distinct et non public**. Les nouveaux fichiers sont servis uniquement par l'API après vérification du compte et de l'école. Pour déplacer les anciennes remises publiques, exécutez depuis `backend` :

```bash
python -m scripts.migrate_legacy_submissions
python -m scripts.migrate_legacy_submissions --apply
```

La première commande affiche un aperçu. La seconde copie les fichiers, met à jour les URLs des remises et supprime les anciennes copies publiques. Si un CDN a mis ces objets en cache, purgez aussi ce cache. Configurez le routage `/api/v1` sur chaque domaine public d'école afin que la connexion et le retour de paiement utilisent la même origine que le site.

Les nouveaux supports téléversés par les professeurs utilisent aussi ce bucket privé et sont téléchargés via l'API selon l'affectation à la session ou l'inscription de l'étudiant. Les anciens supports restent lisibles par cette API, mais les objets déjà présents dans le bucket public R2 doivent encore être déplacés ou supprimés du bucket public pour rendre leur accès réellement privé.

Une commande sans premier paiement confirmé réserve sa place pendant `COMMERCE_RESERVATION_MINUTES` (30 minutes par défaut). Après expiration, la place est libérée. Un paiement TaraMoney confirmé ultérieurement passe au statut `payment_review` sans créer d'inscription ; l'école doit vérifier la transaction et décider de la suite, notamment d'un remboursement si la place a été revendue.

La comparaison des parcours avec le site mère est suivie dans [`docs/PARITE_SITE_MERE.md`](docs/PARITE_SITE_MERE.md). Les changements de mot de passe et la déconnexion révoquent toutes les sessions du compte. Les envois email et WhatsApp dont le résultat est incertain apparaissent dans Commerce pour une vérification avant renvoi.

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
