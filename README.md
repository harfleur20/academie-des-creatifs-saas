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

Vérifications :

- API : `http://localhost:8000/health`
- Documentation FastAPI : `http://localhost:8000/docs`

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
