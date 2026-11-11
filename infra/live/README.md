# Live auto-hébergé (Jitsi)

Les classes live du SaaS peuvent tourner sur un Jitsi hébergé par l'école plutôt que sur JaaS (Jitsi hébergé et facturé par 8x8). Le protocole, l'API iframe et les jetons sont les mêmes : le SaaS change seulement de domaine et signe ses jetons avec une clé partagée (`LIVE_PROVIDER=jitsi`). JaaS reste disponible avec `LIVE_PROVIDER=jaas`.

## Architecture

```
Navigateur (page live du SaaS)
   │ HTTPS 443 : interface, signalisation (WebSocket XMPP)
   ▼
Serveur principal : web (nginx) · Prosody (XMPP) · Jicofo (chef d'orchestre) · premier relais vidéo
                    · relais TURN coturn (participants dont le réseau bloque l'UDP)
   │ XMPP 5222, réseau privé seulement
   ▼
Relais vidéo supplémentaires (vidéo et canal de données en UDP 10000, en direct avec les participants)
```

- **Accès :** seuls les jetons signés par le SaaS ouvrent une salle (`ENABLE_AUTH=1`, `AUTH_TYPE=jwt`, sans invités).
- **Modérateur :** le jeton donne ce rôle au professeur de la séance et à l'équipe de l'école. Les étudiants ne sont que membres. C'est le rôle du module officiel `mod_token_affiliation`, livré dans l'image Prosody, avec `ENABLE_AUTO_OWNER=0` pour que Jicofo ne promeuve personne d'autre.
- **Répartition :** Jicofo répartit les classes entre les relais connectés. Une classe reste entière sur un seul relais.
- **Canal de données :** dans la version figée, il passe en SCTP dans la connexion vidéo de chaque relais. Le serveur principal ne relaie donc rien vers les relais, à part XMPP.

## Dimensionnement de départ (plus de 10 classes simultanées)

Ce sont des ordres de grandeur, à confirmer par la mesure au premier mois.

- **Bande passante :** c'est elle qui limite, plus que le processeur. Un étudiant qui regarde surtout le professeur reçoit autour de 1 Mbit/s. Dix classes de 30 étudiants font donc environ 300 Mbit/s sortants.
- **Serveur principal :** 4 vCPU et 8 Go de RAM. Il porte aussi le premier relais.
- **Relais supplémentaire :** 4 à 8 vCPU, 8 Go de RAM, avec une liaison d'au moins 1 Gbit/s et un quota de trafic large. Comptez un relais pour 8 à 10 classes de 30 étudiants.
- **Trafic mensuel :** avec 300 étudiants connectés 2 h par jour, 22 jours par mois, il approche 6 To. Choisissez un hébergeur qui inclut ce volume.
- **Localisation :** un hébergement en Europe de l'Ouest (Paris, Francfort) donne une latence correcte depuis l'Afrique centrale.

Pour démarrer : un serveur principal et un relais supplémentaire, puis un relais de plus quand la charge des relais dépasse 70 %.

## Prérequis

- **Serveurs :** un VPS Linux avec Docker et le plugin Compose par serveur.
- **Réseau privé :** les serveurs sont reliés par un réseau privé (réseau privé de l'hébergeur ou WireGuard).
- **DNS :** deux enregistrements A vers l'IP publique du serveur principal, `live.votre-domaine` et `turn.votre-domaine`.
- **Pare-feu du serveur principal :** TCP 80, 443 et 3478, et UDP 10000 ouverts à tous. TCP 5222 n'est ouvert que sur l'IP privée, aux relais. Avec des relais supplémentaires, ouvrez aussi UDP 49160 à 49359 à leurs IP publiques (relais TURN).
- **Pare-feu d'un relais :** UDP 10000 ouvert à tous, rien d'autre. Le relais se connecte lui-même au serveur principal.

## Installer le serveur principal

```bash
git clone <dépôt du SaaS> && cd academie-des-creatifs-saas/infra/live
cp main.env.example main.env
openssl rand -hex 32   # à coller dans JWT_APP_SECRET
nano main.env          # domaines du live et du TURN, e-mail Let's Encrypt, IP publique, secret
sudo ./install-main.sh
```

Le script :
- télécharge la version officielle de `docker-jitsi-meet`, figée sur `stable-11248-3` (modifiable avec `JITSI_RELEASE`) ;
- génère ses mots de passe internes et applique `main.env` ;
- copie `web/custom-config.js` (français, pas de pair-à-pair, vidéo limitée à 720p) ;
- génère le secret et la configuration du relais TURN (section suivante) ;
- démarre les conteneurs.

Le script peut être relancé : il conserve le `.env` et les mots de passe déjà générés.

## Relais TURN (réseaux qui bloquent l'UDP)

La vidéo passe normalement en UDP 10000. Certains réseaux le bloquent : réseaux d'entreprise, wifi publics, certains opérateurs. Sans relais TURN, l'étudiant entre bien dans la salle, mais sans son ni image. Le script installe donc coturn sur le serveur principal (image `coturn/coturn:4.18.0-r0`).

- **Accès :** Prosody donne à chaque participant un accès temporaire, signé avec `TURN_CREDENTIALS`. Ce secret est généré dans le `.env` de Jitsi et y reste. Le SaaS n'a rien à configurer.
- **Ports :** coturn accepte le TCP sur 3478. Derrière Coolify, `turn.votre-domaine` est aussi servi en TLS sur 443 : Traefik déchiffre la connexion et la transmet à coturn. C'est ce qui passe presque partout, parce que le trafic ressemble à du HTTPS. Sans Coolify, le port 443 est pris par Jitsi et seul le TCP 3478 est proposé.
- **Sécurité :** coturn refuse de relayer vers les adresses privées. Un participant ne peut donc pas s'en servir pour atteindre la base de données ou Coolify.
- **Réseau :** coturn utilise le réseau de l'hôte, comme le recommande son image. Il joint le relais vidéo du même serveur par l'IP publique de ce serveur. Vérifiez que cette IP est bien portée par sa carte réseau (`ip addr`) : c'est le cas chez la plupart des hébergeurs de VPS.

## Sur un serveur géré par Coolify

Le proxy Traefik de Coolify garde les ports 80 et 443 et les certificats. Mettez `BEHIND_COOLIFY=1` dans `main.env`, puis lancez le même `install-main.sh` en SSH sur le serveur. Le script :
- **Ports :** le conteneur web de Jitsi ne publie aucun port, et tourne sans son propre HTTPS ni Let's Encrypt. Les ports 8000 (tableau de bord de Coolify) et 8080 (tableau de bord de Traefik) restent libres : les statistiques du relais vidéo passent sur `127.0.0.1:18080`.
- **Proxy :** il relie le conteneur web au réseau `coolify`, par lequel Traefik le joint en HTTP.
- **Domaines :** il dépose les routes du live et du TURN dans `/data/coolify/proxy/dynamic/academie-live.yaml`. Traefik les recharge à chaud et obtient les deux certificats avec le résolveur `letsencrypt` de Coolify. Il joint coturn par `host.docker.internal`, que Coolify déclare dans son proxy. Si ce dossier n'existe pas, ajoutez le fichier généré depuis Servers > votre serveur > Proxy > Dynamic Configurations.
- **Limites :** il plafonne le relais vidéo à 2,5 vCPU et 2,5 Go, et Jicofo à 0,5 vCPU et 1,25 Go, pour que le SaaS garde de quoi tourner pendant un cours.

Les ports UDP 10000 et TCP 3478 restent publiés directement sur le serveur : ouvrez-les dans le pare-feu de l'hébergeur, Coolify ne les gère pas. Pointez le DNS du domaine du live vers l'IP du serveur. Mettez les variables `LIVE_PROVIDER` et `JITSI_*` dans les variables d'environnement de l'application backend sur Coolify.

**Capacité d'un serveur partagé avec le SaaS (4 vCPU dédiés, 8 Go) :** de l'ordre de 3 à 5 classes de 30 étudiants en même temps, à confirmer en mesurant. Le débit du port compte aussi : environ 80 étudiants connectés à 100 Mbit/s, bien plus à 1 Gbit/s. Au-delà, ajoutez un relais vidéo sur un second serveur (section suivante).

Si une route n'apparaît pas, vérifiez les noms des points d'entrée (`http`, `https`) dans la configuration du proxy de Coolify, et ses journaux (Servers > Proxy > Logs).

## Raccorder le SaaS

Dans `backend/.env`, puis redémarrez le backend :

```env
LIVE_PROVIDER=jitsi
JITSI_DOMAIN=live.votre-domaine
JITSI_APP_ID=academie-live
JITSI_APP_SECRET=<même valeur que JWT_APP_SECRET>
JITSI_XMPP_DOMAIN=meet.jitsi
```

En production, le backend refuse de démarrer si le secret fait moins de 32 caractères.

## Vérifications au premier lancement

1. **Ouverture :** ouvrez une séance live comme professeur. La salle s'ouvre et vous êtes modérateur (vous pouvez couper le micro d'un participant).
2. **Rôle étudiant :** rejoignez-la comme étudiant dans un autre navigateur. L'étudiant n'est pas modérateur, même s'il entre avant le professeur.
3. **Sans jeton :** `https://live.votre-domaine/une-salle` doit refuser l'accès.
4. **Bande passante :** pendant un cours, l'API de statistiques du relais donne le nombre de participants et le débit. Elle n'est joignable que depuis le serveur du relais : `curl -s http://127.0.0.1:8080/colibri/stats` (port 18080 sur un serveur Coolify).
5. **Relais TURN :** sur le serveur, créez un accès de test valable une heure :

   ```bash
   SECRET=$(grep '^TURN_CREDENTIALS=' /opt/academie-live/docker-jitsi-meet/.env | cut -d= -f2)
   USERNAME="$(( $(date +%s) + 3600 )):test"
   echo "$USERNAME"
   printf %s "$USERNAME" | openssl dgst -sha1 -hmac "$SECRET" -binary | base64
   ```

   Ouvrez la page [Trickle ICE](https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/). Ajoutez `turns:turn.votre-domaine:443?transport=tcp` avec ce nom et ce mot de passe, puis lancez la collecte : une ligne de type `relay` doit apparaître. Refaites le test avec `turn:turn.votre-domaine:3478?transport=tcp`.

## Ajouter un relais vidéo

1. **Serveur principal :** dans `main.env`, décommentez `XMPP_PRIVATE_IP` avec son IP privée, puis relancez `install-main.sh`.
2. **Nouveau serveur :** copiez `jvb-node/`, puis `cp jvb-node.env.example .env`.
   - Renseignez l'IP privée du serveur principal, `JVB_AUTH_PASSWORD` (celui du `.env` du serveur principal) et l'IP publique du relais.
   - Lancez `docker compose up -d`.
3. **Contrôle :** le relais apparaît dans les journaux de Jicofo (`docker compose logs jicofo | grep -i bridge`).

**À valider au premier déploiement multi-relais :** cette configuration n'a pas encore tourné. Testez une classe sur chaque relais : la vidéo doit passer, et la console du navigateur ne doit pas signaler de canal de données fermé.

## Exploitation

- **Commandes :** lancez les commandes `docker compose` (journaux, redémarrage) depuis `/opt/academie-live/docker-jitsi-meet`. Le `.env` de ce dossier désigne les bons fichiers (`COMPOSE_FILE`), y compris ceux de Coolify et du TURN.
- **Mise à jour :** changez `JITSI_RELEASE`, supprimez le dossier `docker-jitsi-meet` dans `/opt/academie-live` (le `.env` est à sauvegarder avant), puis relancez le script. Mettez la même version dans `JITSI_IMAGE_VERSION` sur chaque relais. Faites-le entre deux journées de cours.
- **Sauvegarde :** le `.env` du serveur principal (il contient aussi le secret TURN) et le dossier `CONFIG`.
- **Retrait :** remettez `LIVE_PROVIDER=jaas` dans le backend, puis lancez `docker compose down` dans `/opt/academie-live/docker-jitsi-meet` et supprimez `/data/coolify/proxy/dynamic/academie-live.yaml`. Le SaaS et Coolify ne sont pas touchés.
- **Secrets :** ne publiez jamais 5222 sur une IP publique. Changer `JWT_APP_SECRET` impose de mettre à jour `JITSI_APP_SECRET` dans le SaaS au même moment.

## Replays (plus tard)

L'enregistrement passera par Jibri : un enregistreur par cours enregistré en même temps, soit environ 2 vCPU et 4 Go chacun. La vidéo sera envoyée sur le stockage privé R2. Il pourra s'ajouter sans toucher au reste de cette installation. Avec `LIVE_PROVIDER=jitsi`, le bouton d'enregistrement est désactivé dans les jetons.

## Sources

- [Guide officiel Docker de Jitsi](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker/)
- [Module `mod_token_affiliation` de la version figée](https://github.com/jitsi/jitsi-meet/blob/stable/jitsi-meet_11248/resources/prosody-plugins/mod_token_affiliation.lua)
- [Versions de docker-jitsi-meet](https://github.com/jitsi/docker-jitsi-meet/releases), et son [journal des changements](https://github.com/jitsi/docker-jitsi-meet/blob/stable-11248-3/CHANGELOG.md) (canal de données en SCTP par défaut)
- [Image Docker de coturn](https://github.com/coturn/coturn/blob/docker/4.18.0-r0/docker/coturn/README.md) (réseau de l'hôte recommandé) et [son fichier de configuration commenté](https://github.com/coturn/coturn/blob/4.18.0/examples/etc/turnserver.conf)
- [`useTurnUdp` dans la configuration de Jitsi Meet](https://github.com/jitsi/jitsi-meet/blob/stable/jitsi-meet_11248/config.js) : le TURN en UDP n'est pas utilisé pour joindre le relais vidéo
