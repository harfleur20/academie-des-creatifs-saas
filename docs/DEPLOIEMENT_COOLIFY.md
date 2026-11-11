# Déployer le SaaS sur Coolify

Le SaaS tourne dans **un seul conteneur** : le backend FastAPI sert aussi le frontend compilé. Chaque domaine d'école a ainsi une seule origine, comme l'exigent la connexion et le retour de paiement. L'image est construite par le `Dockerfile` à la racine du dépôt.

## Adresses

| Adresse | Rôle | Routage |
|---|---|---|
| `ecoles.academiecreatif.com` | Le SaaS : inscription des écoles, administration | Domaine de l'application dans Coolify |
| `ecole.academiecreatif.com` | Le site et l'espace de chaque école | Étiquettes Traefik génériques, en priorité minimale |
| `www.academiecreatif.com` | Le site mère | Inchangé |
| `live.` et `turn.academiecreatif.com` | Classes live et relais TURN | `infra/live` |

L'école choisit son sous-domaine dans sa mise en route. Le backend la retrouve à partir de l'adresse demandée (`SAAS_BASE_DOMAIN`). Un seul niveau est accepté : `ecole.academiecreatif.com`, pas `a.b.academiecreatif.com`. Les noms `www`, `api`, `app`, `admin`, `ecoles`, `live`, `turn` et quelques autres sont réservés. Ajoutez dans `SAAS_RESERVED_SUBDOMAINS` les autres sous-domaines déjà utilisés par le site mère.

La route générique a la priorité la plus basse de Traefik : `www`, `live`, `ecoles` et toute autre route explicite passent toujours avant elle.

## 1. Cloudflare

Dans **DNS > Records**, tous en **DNS only (nuage gris)** :

| Type | Nom | Valeur |
|---|---|---|
| A | `ecoles` | IP du serveur Coolify |
| A | `*` | IP du serveur Coolify |
| A | `live`, `turn` | IP du serveur Coolify (déjà créés : vérifiez le nuage gris) |

Le proxy de Cloudflare ne laisse passer ni le TURN ni les longues connexions du live, et Traefik doit présenter ses propres certificats.

Créez ensuite un jeton API : **My Profile > API Tokens > Create Token**, modèle **Edit zone DNS**, zone `academiecreatif.com`. Traefik s'en sert pour prouver à Let's Encrypt qu'il contrôle le domaine, seule façon d'obtenir le certificat générique `*.academiecreatif.com`.

## 2. Proxy Coolify : un second résolveur de certificats

Le résolveur `letsencrypt` de Coolify, qui sert le site mère, reste tel quel. On en ajoute un second, par DNS, réservé au certificat générique.

Dans **Servers > votre serveur > Proxy > Configuration**, ajoutez à la liste `command` de Traefik :

```yaml
      - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge=true'
      - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge.provider=cloudflare'
      - '--certificatesresolvers.letsencrypt-dns.acme.storage=/traefik/acme-dns.json'
```

et, dans `environment` (créez la clé si elle n'existe pas) :

```yaml
    environment:
      - CF_DNS_API_TOKEN=<jeton Cloudflare>
```

Enregistrez puis redémarrez le proxy. Le site mère est coupé quelques secondes : faites-le en heure creuse.

## 3. Base PostgreSQL

**New Resource > Database > PostgreSQL 16**, dans le même projet que l'application. Copiez son URL interne et remplacez le préfixe `postgres://` par `postgresql+psycopg://`. C'est la valeur de `DATABASE_URL`. Activez les sauvegardes planifiées de la base dans Coolify.

## 4. Application

**New Resource > Application**, depuis le dépôt GitHub :

- **Build Pack :** Dockerfile (celui de la racine).
- **Branche :** celle à tester.
- **Ports Exposes :** `8000`.
- **Domains :** `https://ecoles.academiecreatif.com`.
- **Health Check :** chemin `/health`, port `8000`.
- **Persistent Storage :** deux volumes, `/app/backend/uploads` et `/app/backend/private_uploads` (fichiers téléversés tant que `STORAGE_PROVIDER=local`).
- **Resource Limits :** 1 Go de mémoire et 1 CPU pour commencer. Le serveur est partagé avec le site mère et le live.
- **Build arguments :** `VITE_GOOGLE_CLIENT_ID` seulement si la connexion Google est activée.

### Étiquettes du domaine générique

Dans **Container Labels**, décochez « Readonly labels », puis ajoutez à la fin :

```
traefik.http.middlewares.ecoles-https.redirectscheme.scheme=https
traefik.http.routers.ecoles-wildcard-http.rule=HostRegexp(`^[a-z0-9-]+\.academiecreatif\.com$`)
traefik.http.routers.ecoles-wildcard-http.entryPoints=http
traefik.http.routers.ecoles-wildcard-http.priority=1
traefik.http.routers.ecoles-wildcard-http.middlewares=ecoles-https
traefik.http.routers.ecoles-wildcard-http.service=ecoles-wildcard
traefik.http.routers.ecoles-wildcard.rule=HostRegexp(`^[a-z0-9-]+\.academiecreatif\.com$`)
traefik.http.routers.ecoles-wildcard.entryPoints=https
traefik.http.routers.ecoles-wildcard.priority=1
traefik.http.routers.ecoles-wildcard.tls=true
traefik.http.routers.ecoles-wildcard.tls.certresolver=letsencrypt-dns
traefik.http.routers.ecoles-wildcard.tls.domains[0].main=academiecreatif.com
traefik.http.routers.ecoles-wildcard.tls.domains[0].sans=*.academiecreatif.com
traefik.http.routers.ecoles-wildcard.service=ecoles-wildcard
traefik.http.services.ecoles-wildcard.loadbalancer.server.port=8000
```

Coolify écrit ses domaines en `Host(...)`, que Traefik ne sait pas faire correspondre à un joker : un domaine `*.academiecreatif.com` saisi dans **Domains** ne suffirait pas.

### Variables d'environnement

Indispensables :

| Variable | Valeur |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | URL interne de la base, en `postgresql+psycopg://` |
| `FRONTEND_URL` | `https://ecoles.academiecreatif.com` |
| `BACKEND_PUBLIC_URL` | `https://ecoles.academiecreatif.com` |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `INTEGRATION_ENCRYPTION_KEY` | `openssl rand -base64 32 \| tr '+/' '-_'` (clé Fernet) |
| `AUTH_COOKIE_SECURE` | `true` |
| `SAAS_BASE_DOMAIN` | `academiecreatif.com` |
| `SAAS_CNAME_TARGET` | `ecoles.academiecreatif.com` |
| `SAAS_RESERVED_SUBDOMAINS` | Autres sous-domaines du site mère, séparés par des virgules |
| `BILLING_CRON_SECRET` | `openssl rand -hex 32` |

Le cookie de connexion est alors posé sur `.academiecreatif.com` et partagé par les écoles. Le site mère le reçoit aussi mais l'ignore : il utilise `ac_session`, le SaaS `academie_saas_session`.

Selon ce que vous testez :

- **Live :** `LIVE_PROVIDER=jitsi`, `JITSI_DOMAIN=live.academiecreatif.com`, `JITSI_APP_ID=academie-live`, `JITSI_APP_SECRET` (le `JWT_APP_SECRET` d'`infra/live`), `JITSI_XMPP_DOMAIN=meet.jitsi`. Voir [infra/live/README.md](../infra/live/README.md).
- **Emails :** `BREVO_API_KEY`, `SMTP_FROM` (adresse d'expédition validée dans Brevo), `SMTP_FROM_NAME`, `SUPPORT_EMAIL`.
- **Paiements :** les variables `TARAMONEY_*`. Le mode démo est refusé en production.
- **Connexion Google :** `GOOGLE_CLIENT_ID`, avec le même identifiant en argument de build `VITE_GOOGLE_CLIENT_ID`.
- **Stockage R2 :** `STORAGE_PROVIDER=r2` et les variables `R2_*`, au lieu des volumes.

## 5. Premier lancement

1. **Deploy.** Le conteneur applique les migrations avant de démarrer l'API.
2. Ouvrez `https://ecoles.academiecreatif.com` et inscrivez-vous avec l'email du futur super-administrateur. Utilisez une adresse dédiée, pas celle d'une école.
3. Dans **Terminal** (conteneur de l'application) :

   ```bash
   python -m scripts.promote_super_admin admin@votre-domaine
   ```

4. Dans GitHub, **Settings > Secrets and variables > Actions**, renseignez `BILLING_CRON_URL=https://ecoles.academiecreatif.com` et `BILLING_CRON_SECRET` (même valeur que dans Coolify). Les tâches horaires démarrent alors (voir [BILLING_AUTOMATION.md](BILLING_AUTOMATION.md)).

## 6. Vérifications

1. `https://ecoles.academiecreatif.com` affiche le SaaS, avec un certificat valide.
2. Créez une école et choisissez son sous-domaine. `https://<sous-domaine>.academiecreatif.com` affiche son site, avec le certificat générique.
3. Un sous-domaine sans école affiche « Aucune école n'est associée à ce domaine ».
4. `https://www.academiecreatif.com` affiche toujours le site mère, et `https://live.academiecreatif.com` toujours Jitsi.
5. Une école ne peut pas choisir `live`, `turn` ou `ecoles` comme sous-domaine.

## 7. Mémoire du serveur partagé

Le site mère, Coolify, le SaaS et le live se partagent 4 cœurs et 7,8 Go. Avant d'ouvrir des classes live, relevez sur le serveur `free -h` et `docker stats --no-stream`, puis refaites ces mesures pendant une classe de test. Les plafonds de mémoire du SaaS et du live servent à ce qu'un pic de charge arrête l'un de leurs conteneurs plutôt que le site mère.

## 8. Retrait

Arrêtez l'application dans Coolify, puis supprimez l'enregistrement `*` dans Cloudflare. Le site mère et ses certificats ne dépendent ni de l'un ni de l'autre. Le second résolveur peut rester en place.
