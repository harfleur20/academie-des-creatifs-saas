# Déployer le SaaS sur Coolify

Le SaaS se déploie comme le site mère : **une seule ressource Coolify en Docker Compose**, décrite par [docker-compose.coolify.yml](../docker-compose.coolify.yml). L'application tourne dans un seul conteneur : le backend FastAPI sert aussi le frontend compilé. Chaque domaine d'école a ainsi une seule origine, comme l'exigent la connexion et le retour de paiement. À côté, la ressource comprend sa base PostgreSQL et sa sauvegarde quotidienne.

## Adresses

| Adresse | Rôle | Routage |
|---|---|---|
| `ecoles.academiecreatif.com` | Le SaaS : inscription des écoles, administration | Domaine du service `app` dans Coolify |
| `ecole.academiecreatif.com` | Le site et l'espace de chaque école | Étiquettes Traefik génériques du fichier Compose, en priorité minimale |
| `www.academiecreatif.com` | Le site mère | Inchangé |
| `live.` et `turn.academiecreatif.com` | Classes live et relais TURN | `infra/live` |

L'école choisit son sous-domaine dans sa mise en route. Le backend la retrouve à partir de l'adresse demandée (`SAAS_BASE_DOMAIN`). Un seul niveau est accepté : `ecole.academiecreatif.com`, pas `a.b.academiecreatif.com`. Les noms `www`, `api`, `app`, `admin`, `ecoles`, `live`, `turn` et quelques autres sont réservés. `SAAS_RESERVED_SUBDOMAINS` réserve en plus les sous-domaines des autres sites du serveur : `coupe`, `ferrolink` et `media` par défaut.

La route générique a la priorité la plus basse de Traefik : `www`, `coupe`, `ferrolink`, `live`, `ecoles` et toute autre route explicite passent toujours avant elle.

## 1. Cloudflare

Dans **DNS > Records**, tous en **DNS only (nuage gris)** :

| Type | Nom | Valeur |
|---|---|---|
| A | `ecoles` | IP du serveur Coolify |
| A | `*` | IP du serveur Coolify |
| A | `live`, `turn` | IP du serveur Coolify (déjà créés : vérifiez le nuage gris) |

Le proxy de Cloudflare ne laisse passer ni le TURN ni les longues connexions du live, et Traefik doit présenter ses propres certificats.

Créez ensuite un jeton API : **My Profile > API Tokens > Create Token**, modèle **Edit zone DNS**, zone `academiecreatif.com`. Ajoutez la permission **Zone > Zone > Read** à côté de **DNS > Edit** : Traefik en a besoin pour retrouver la zone ([documentation de lego](https://go-acme.github.io/lego/dns/cloudflare/)). Ne mettez pas d'expiration, sinon le renouvellement du certificat échoue sans prévenir. Limitez plutôt le jeton aux adresses du serveur : son IPv4, et aussi son IPv6 s'il en a une (`ip -6 addr show scope global`), car le serveur joint alors Cloudflare en IPv6. Traefik s'en sert pour prouver à Let's Encrypt qu'il contrôle le domaine, seule façon d'obtenir le certificat générique `*.academiecreatif.com`.

Pour vérifier le jeton depuis le serveur, sans l'afficher ni le garder dans l'historique :

```bash
read -rsp "Jeton : " CF_TOKEN; echo
curl -s "https://api.cloudflare.com/client/v4/zones?name=academiecreatif.com" -H "Authorization: Bearer $CF_TOKEN" | grep -o '"count":[0-9]*\|"success":[a-z]*\|"errors":\[[^]]*\]'
unset CF_TOKEN
```

La réponse attendue est `"count":1` et `"success":true`. L'erreur 9109 (« Cannot use the access token from location ») signale une adresse du serveur absente du filtre.

## 2. Proxy Coolify : un second résolveur de certificats

Le résolveur `letsencrypt` de Coolify, qui sert le site mère, reste tel quel. On en ajoute un second, par DNS, réservé au certificat générique.

Sauvegardez d'abord le dossier du proxy, certificats du site mère compris : `cp -a /data/coolify/proxy /root/coolify-proxy-avant-ecoles`.

Dans **Servers > votre serveur > Proxy > Configuration**, ajoutez à la liste `command` de Traefik, après la ligne `letsencrypt.acme.storage` :

```yaml
      - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge=true'
      - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge.provider=cloudflare'
      - '--certificatesresolvers.letsencrypt-dns.acme.storage=/traefik/acme-dns.json'
      - '--certificatesresolvers.letsencrypt-dns.acme.dnschallenge.resolvers=1.1.1.1:53,8.8.8.8:53'
```

La dernière ligne compte. Sans elle, Traefik vérifie l'enregistrement TXT de Let's Encrypt avec le DNS interne de Docker (`127.0.0.11`). Celui-ci garde en mémoire l'absence de l'enregistrement, et la demande échoue avec « time limit exceeded … did not return the expected TXT record ».

et, sous `image:` (créez la clé si elle n'existe pas) :

```yaml
    environment:
      - CF_DNS_API_TOKEN=<jeton Cloudflare>
```

Enregistrez puis redémarrez le proxy (**Restart Proxy**). Les sites du serveur sont coupés quelques secondes : faites-le en heure creuse. Vérifiez ensuite que Traefik a reçu un jeton valide, toujours sans l'afficher :

```bash
curl -s "https://api.cloudflare.com/client/v4/zones?name=academiecreatif.com" -H "Authorization: Bearer $(docker exec coolify-proxy printenv CF_DNS_API_TOKEN)" | grep -o '"count":[0-9]*\|"success":[a-z]*'
```

Si cette page propose de choisir un proxy (Custom, Traefik, Caddy) alors que le proxy tourne et sert les sites, Coolify a perdu le type du proxy. Choisissez **Traefik** : Coolify régénère sa configuration par défaut et redémarre le proxy, avec quelques secondes de coupure. Comparez ensuite le fichier avec la sauvegarde (`diff`). Ne mettez pas à jour Traefik en même temps.

## 3. Application

**New Resource > Public/Private Repository**, le dépôt GitHub du SaaS :

- **Build Pack :** Docker Compose, fichier `/docker-compose.coolify.yml`.
- **Branche :** `main`.
- **Domains for app :** `https://ecoles.academiecreatif.com:8000`. `:8000` désigne le port du conteneur, pas celui de l'adresse publique. Coolify relie alors explicitement sa route à ce port, ce qu'il faut puisque le conteneur a aussi la route des écoles. Ne mettez de domaine ni à `saas-db` ni à `backup`.
- **Connect to Predefined Network :** laissez décoché. La base reste sur le réseau privé de la ressource, que le proxy rejoint seul.

Le fichier contient trois services :

| Service | Rôle |
|---|---|
| `app` | L'image du `Dockerfile` : l'API et le frontend compilé, port 8000. Les migrations passent avant le démarrage. Les volumes `uploads` et `private_uploads` gardent les fichiers téléversés tant que `STORAGE_PROVIDER=local`. |
| `saas-db` | PostgreSQL 16. Base `academie_saas`, utilisateur `saas`. Aucun port publié. |
| `backup` | Une sauvegarde PostgreSQL par jour, vérifiée en local puis copiée dans Backblaze B2 ([infra/backup](../infra/backup)). Voir la section 5. |

Les plafonds de ressources sont dans le fichier : 1 Go et 1 CPU pour `app`, 768 Mo pour la base, 256 Mo pour la sauvegarde. Le serveur est partagé avec le site mère et le live.

### Étiquettes du domaine générique

Elles sont dans le fichier Compose, sur le service `app` : rien à saisir dans Coolify. La route `HostRegexp` couvre `<nom>.academiecreatif.com`, sur un seul niveau, en priorité 1, avec le certificat `*.academiecreatif.com` du résolveur `letsencrypt-dns`. Coolify écrit ses domaines en `Host(...)`, que Traefik ne sait pas faire correspondre à un joker : un domaine `*.academiecreatif.com` saisi dans **Domains** ne suffirait pas. La fin de l'adresse s'écrit `\z` plutôt que `$`, que Compose prendrait pour une variable.

### Variables d'environnement

Coolify affiche les variables du fichier. Le déploiement s'arrête si l'une de celles-ci manque :

| Variable | Valeur |
|---|---|
| `POSTGRES_PASSWORD` | `openssl rand -hex 24`. En hexadécimal seulement : il entre tel quel dans l'adresse de la base. |
| `PUBLIC_URL` | `https://ecoles.academiecreatif.com` (devient `FRONTEND_URL` et `BACKEND_PUBLIC_URL`) |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `INTEGRATION_ENCRYPTION_KEY` | `openssl rand -base64 32 \| tr '+/' '-_'` (clé Fernet) |
| `BILLING_CRON_SECRET` | `openssl rand -hex 32` |

Gardez ces valeurs dans un gestionnaire de mots de passe. Changer `POSTGRES_PASSWORD` après le premier lancement ne change pas le mot de passe de la base, déjà créée : l'application ne s'y connecterait plus.

Déjà réglées dans le fichier, à changer seulement si besoin : `APP_ENV=production`, `AUTH_COOKIE_SECURE=true`, `SAAS_BASE_DOMAIN=academiecreatif.com`, `SAAS_CNAME_TARGET=ecoles.academiecreatif.com`, `SAAS_RESERVED_SUBDOMAINS=coupe,ferrolink,media`.

`DEMO_ORGANIZATION_SLUG` est facultatif : `studio-kora`, l'école montrée en lecture seule par « Voir la démo », créée par `python scripts/create_demo_school.py` ([DEMO.md](DEMO.md)).

Le cookie de connexion est posé sur `.academiecreatif.com` et partagé par les écoles. Le site mère le reçoit aussi mais l'ignore : il utilise `ac_session`, le SaaS `academie_saas_session`.

Selon ce que vous testez :

- **Live :** `LIVE_PROVIDER=jitsi`, `JITSI_DOMAIN=live.academiecreatif.com`, `JITSI_APP_SECRET` (le `JWT_APP_SECRET` d'`infra/live`). `JITSI_APP_ID=academie-live` et `JITSI_XMPP_DOMAIN=meet.jitsi` sont déjà les valeurs par défaut. `LIVE_PLATFORM_MAX_PARTICIPANTS` (100 par défaut) plafonne les étudiants en live en même temps, toutes écoles confondues : relevez-le de 300 à chaque relais vidéo ajouté ([FORFAITS.md](FORFAITS.md)). Dans le `main.env` d'`infra/live`, mettez `BRANDING_DATA_URL=https://ecoles.academiecreatif.com/api/v1/planning/live/room-branding` et `LIVE_HOME_URL=https://ecoles.academiecreatif.com`. Voir [infra/live/README.md](../infra/live/README.md).
- **Emails :** `BREVO_API_KEY`, `SMTP_FROM` (adresse d'expédition validée dans Brevo), `SMTP_FROM_NAME`, `SUPPORT_EMAIL`.
- **Paiements :** les variables `TARAMONEY_*`. Le mode démo est refusé en production.
- **Connexion Google :** `GOOGLE_CLIENT_ID`. Le fichier le passe aussi au build du frontend : redéployez après l'avoir changé.
- **Médias publics sur Cloudinary :** créez un compte Cloudinary et renseignez `PUBLIC_ASSET_PROVIDER=cloudinary`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` et `CLOUDINARY_API_SECRET` dans Coolify. Gardez la clé secrète uniquement côté serveur. Les PDFs publics sont limités à 10 Mo avec le plan Free ; dans les réglages Security de Cloudinary, activez **Allow delivery of PDF and ZIP files** pour pouvoir les afficher. Les images et vidéos de présentation publiques passent aussi par Cloudinary.
- **Fichiers privés sur Backblaze B2 :** `STORAGE_PROVIDER=b2`. Créez un bucket B2 privé réservé aux remises, ressources, PDF de cours et replays, puis une clé d'application limitée à ce seul bucket avec lecture, écriture et suppression. Renseignez `B2_ENDPOINT_URL` (endpoint S3 de la région du bucket), `B2_REGION`, `B2_PRIVATE_BUCKET_NAME`, `B2_ACCESS_KEY_ID` et `B2_SECRET_ACCESS_KEY`. Aucun bucket B2 public n'est nécessaire. `B2_BUCKET_NAME` et `B2_PUBLIC_BASE_URL` sont facultatifs et ne servent qu'à la migration ou à la lecture d'anciens fichiers publics B2. Gardez une clé distincte pour les sauvegardes PostgreSQL. L'application refuse de démarrer en production si B2 privé ou Cloudinary n'est pas configuré.
- **Sauvegardes PostgreSQL sur Backblaze B2 :** `BACKUP_B2_ENABLED` vaut `true` par défaut. Configurez dans Coolify `BACKUP_B2_ENDPOINT_URL` (endpoint S3 de la région du bucket), `BACKUP_B2_REGION`, `BACKUP_B2_BUCKET_NAME`, `BACKUP_B2_ACCESS_KEY_ID` et `BACKUP_B2_SECRET_ACCESS_KEY` (ID et clé d'application B2). Le préfixe par défaut `academie-saas/postgres` isole ces dumps dans un bucket partagé. La clé B2 doit pouvoir lister, lire, écrire et supprimer les objets de ce préfixe afin d'appliquer la rétention. `BACKUP_RETENTION_DAYS` s'applique aux copies locales et distantes.

## 4. Premier lancement

1. **Deploy.** Le premier build prend quelques minutes. La base démarre d'abord, puis l'application applique les migrations et démarre, puis la sauvegarde fait sa première copie.
2. Ouvrez `https://ecoles.academiecreatif.com` et inscrivez-vous avec l'email du futur super-administrateur. Utilisez une adresse dédiée, pas celle d'une école.
3. Dans **Terminal**, conteneur `app` :

   ```bash
   python -m scripts.promote_super_admin admin@votre-domaine
   ```

4. Dans GitHub, **Settings > Secrets and variables > Actions**, renseignez `BILLING_CRON_URL=https://ecoles.academiecreatif.com` et `BILLING_CRON_SECRET` (même valeur que dans Coolify). Les tâches horaires démarrent alors (voir [BILLING_AUTOMATION.md](BILLING_AUTOMATION.md)).

## 5. Sauvegardes et restauration

Le conteneur `backup` fait une copie au démarrage, puis toutes les 24 h (`BACKUP_INTERVAL_SECONDS`), dans le volume `postgres_backups`. Chaque dump est relu par `pg_restore`, envoyé sur Backblaze B2 via son API S3 compatible, puis vérifié par sa taille avant que la sauvegarde soit marquée comme réussie. Les copies de plus de 14 jours sont effacées localement et sur B2 (`BACKUP_RETENTION_DAYS`). Si B2 est inaccessible ou qu'aucune sauvegarde distante n'a réussi depuis 26 h, le conteneur passe en « unhealthy » dans Coolify.

- **Voir les copies locales :** Terminal, conteneur `backup`, `ls -lh /backups`. Les copies distantes se trouvent dans le bucket B2, sous `academie-saas/postgres`.
- **Restaurer :** arrêtez d'abord le conteneur `app` en SSH (`docker stop` suivi de son nom, donné par `docker ps`). Puis, dans le Terminal du conteneur `backup` :

  ```bash
  CONFIRM_RESTORE=academie_saas restore-postgres /backups/academie_saas-AAAAMMJJTHHMMSSZ.dump
  ```

  Redémarrez ensuite la ressource dans Coolify.
- **Restauration après perte du serveur :** téléchargez le dump choisi depuis le bucket B2 des sauvegardes dans `/backups`, puis utilisez la même commande `restore-postgres` ci-dessus. Les fichiers téléversés résident dans Cloudinary (médias publics) et le bucket privé B2 (fichiers privés) ; ils ne sont pas inclus dans le dump PostgreSQL.

## 6. Vérifications

1. Dans Coolify, `app`, `saas-db` et `backup` sont « healthy ».
2. `https://ecoles.academiecreatif.com` affiche le SaaS, avec un certificat valide.
3. Créez une école et choisissez son sous-domaine. `https://<sous-domaine>.academiecreatif.com` affiche son site, avec le certificat générique.
4. Un sous-domaine sans école affiche « Aucune école n'est associée à ce domaine ».
5. `https://www.academiecreatif.com`, `coupe` et `ferrolink` affichent toujours leurs sites, et `https://live.academiecreatif.com` toujours Jitsi.
6. Une école ne peut pas choisir `live`, `turn`, `ecoles`, `coupe` ou `ferrolink` comme sous-domaine.

## 7. Mémoire du serveur partagé

Le site mère, les autres sites, le SaaS et le live se partagent 4 cœurs et 7,8 Go. Coolify est installé ailleurs. Avant d'ouvrir des classes live, relevez sur le serveur `free -h` et `docker stats --no-stream`, puis refaites ces mesures pendant une classe de test. Les plafonds de mémoire du SaaS et du live servent à ce qu'un pic de charge arrête l'un de leurs conteneurs plutôt que le site mère.

## 8. Retrait

Arrêtez la ressource dans Coolify. Si vous la supprimez, ne cochez pas la suppression des volumes tant que vous n'avez pas gardé une copie de la base (`postgres_data`, `postgres_backups`). Supprimez ensuite l'enregistrement `*` dans Cloudflare. Le site mère et ses certificats ne dépendent ni de l'un ni de l'autre. Le second résolveur peut rester en place.
