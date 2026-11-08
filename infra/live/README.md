# Live auto-hébergé (Jitsi)

Les classes live du SaaS peuvent tourner sur un Jitsi hébergé par l'école plutôt que sur JaaS (Jitsi hébergé et facturé par 8x8). Le protocole, l'API iframe et les jetons sont les mêmes : le SaaS change seulement de domaine et signe ses jetons avec une clé partagée (`LIVE_PROVIDER=jitsi`). JaaS reste disponible avec `LIVE_PROVIDER=jaas`.

## Architecture

```
Navigateur (page live du SaaS)
   │ HTTPS 443 : interface, signalisation (WebSocket XMPP)
   ▼
Serveur principal : web (nginx) · Prosody (XMPP) · Jicofo (chef d'orchestre) · relais vidéo jvb-1
   │ XMPP 5222, réseau privé seulement
   ▼
Relais vidéo supplémentaires : jvb-2, jvb-3… (vidéo UDP 10000 en direct avec les participants)
```

- **Accès :** seuls les jetons signés par le SaaS ouvrent une salle (`ENABLE_AUTH=1`, `AUTH_TYPE=jwt`, sans invités).
- **Modérateur :** le jeton donne ce rôle au professeur de la séance et à l'équipe de l'école. Les étudiants ne sont que membres. C'est le rôle du module officiel `mod_token_affiliation`, avec `ENABLE_AUTO_OWNER=0` pour que Jicofo ne promeuve personne d'autre.
- **Répartition :** Jicofo répartit les classes entre les relais connectés. Une classe reste entière sur un seul relais.

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
- **DNS :** un enregistrement A `live.votre-domaine` vers l'IP publique du serveur principal.
- **Pare-feu du serveur principal :** TCP 80 et 443, et UDP 10000 ouverts à tous. TCP 5222 n'est ouvert que sur l'IP privée, aux relais.
- **Pare-feu d'un relais :** UDP 10000 ouvert à tous. TCP 9090 n'est ouvert que sur l'IP privée, au serveur principal.

## Installer le serveur principal

```bash
git clone <dépôt du SaaS> && cd academie-des-creatifs-saas/infra/live
cp main.env.example main.env
openssl rand -hex 32   # à coller dans JWT_APP_SECRET
nano main.env          # domaine, e-mail Let's Encrypt, IP publique, secret
sudo ./install-main.sh
```

Le script :
- télécharge la version officielle de `docker-jitsi-meet`, figée sur `stable-11248-3` (modifiable avec `JITSI_RELEASE`) ;
- génère ses mots de passe internes et applique `main.env` ;
- copie `web/custom-config.js` (français, pas de pair-à-pair, vidéo limitée à 720p) ;
- installe le module `mod_token_affiliation` et démarre les conteneurs.

Le script peut être relancé : il conserve le `.env` et les mots de passe déjà générés.

## Sur un serveur géré par Coolify

Le proxy Traefik de Coolify garde les ports 80 et 443 et les certificats. Mettez `BEHIND_COOLIFY=1` dans `main.env`, puis lancez le même `install-main.sh` en SSH sur le serveur. Le script :
- **Ports :** il fait écouter Jitsi en local seulement (`127.0.0.1:8000`), sans son propre HTTPS ni Let's Encrypt.
- **Proxy :** il relie le conteneur web au réseau `coolify`.
- **Domaine :** il dépose la route dans `/data/coolify/proxy/dynamic/academie-live.yaml`. Traefik la recharge à chaud et obtient le certificat avec le résolveur `letsencrypt` de Coolify. Si ce dossier n'existe pas, ajoutez le fichier généré depuis Servers > votre serveur > Proxy > Dynamic Configurations.
- **Limites :** il plafonne le relais vidéo à 2,5 vCPU et 2,5 Go, et Jicofo à 0,5 vCPU et 1,25 Go, pour que le SaaS garde de quoi tourner pendant un cours.

Le port UDP 10000 reste publié directement sur le serveur : ouvrez-le dans le pare-feu de l'hébergeur, Coolify ne le gère pas. Pointez le DNS du domaine du live vers l'IP du serveur. Mettez les variables `LIVE_PROVIDER` et `JITSI_*` dans les variables d'environnement de l'application backend sur Coolify.

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
4. **Bande passante :** pendant un cours, l'API de statistiques du relais (`/colibri/stats` sur le port 8080 du conteneur `jvb`, non publié) donne le nombre de participants et le débit.

## Ajouter un relais vidéo

1. **Serveur principal :**
   - dans `main.env`, décommentez `XMPP_PRIVATE_IP` avec son IP privée, puis relancez `install-main.sh` ;
   - copiez `main/custom-meet.conf.example` dans `<CONFIG>/web/nginx/custom-meet.conf`, avec une section par relais, puis redémarrez le conteneur web.
2. **Nouveau serveur :** copiez `jvb-node/`, puis `cp jvb-node.env.example .env`.
   - Renseignez l'IP privée du serveur principal, `JVB_AUTH_PASSWORD` (celui du `.env` du serveur principal), ses IP publique et privée, et un nom unique `JVB_WS_SERVER_ID` (`jvb-2`, `jvb-3`…).
   - Lancez `docker compose up -d`.
3. **Contrôle :** le relais apparaît dans les journaux de Jicofo (`docker compose logs jicofo | grep -i bridge`).

**À valider au premier déploiement multi-relais :** la connexion XMPP d'un relais distant et le routage `/colibri-ws/<nom>/` suivent les déploiements publiés par d'autres projets, pas la documentation officielle de docker-jitsi-meet, qui ne décrit pas ce cas. Testez une classe sur chaque relais : la vidéo doit passer, et la console du navigateur ne doit pas signaler de canal de données fermé.

## Exploitation

- **Mise à jour :** changez `JITSI_RELEASE`, supprimez le dossier `docker-jitsi-meet` dans `/opt/academie-live` (le `.env` est à sauvegarder avant), puis relancez le script. Faites-le entre deux journées de cours.
- **Sauvegarde :** le `.env` du serveur principal et le dossier `CONFIG`.
- **Secrets :** ne publiez jamais 5222 ni 9090 sur une IP publique. Changer `JWT_APP_SECRET` impose de mettre à jour `JITSI_APP_SECRET` dans le SaaS au même moment.

## Replays (plus tard)

L'enregistrement passera par Jibri : un enregistreur par cours enregistré en même temps, soit environ 2 vCPU et 4 Go chacun. La vidéo sera envoyée sur le stockage privé R2. Il pourra s'ajouter sans toucher au reste de cette installation. Avec `LIVE_PROVIDER=jitsi`, le bouton d'enregistrement est désactivé dans les jetons.

## Sources

- [Guide officiel Docker de Jitsi](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker/)
- [Module `mod_token_affiliation`](https://github.com/jitsi/jitsi-meet/blob/master/resources/prosody-plugins/mod_token_affiliation.lua)
- [Versions de docker-jitsi-meet](https://github.com/jitsi/docker-jitsi-meet/releases)
- Relais multiples, exemples de déploiement : [matrix-docker-ansible-deploy](https://git.cqre.net/cqrenet/matrix-docker-ansible-deploy/commit/61f1357bfc56984d472762bd6da05a9b5b283993), [OpenDev](https://gitea09.opendev.org:3081/opendev/system-config/commit/fa9aca784dfa031f93fb5ee9dca222120ba05ad5)
