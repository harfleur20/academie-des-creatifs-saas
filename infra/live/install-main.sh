#!/usr/bin/env bash
# Installe ou met à jour le serveur principal du live sur un VPS Linux avec Docker.
# Usage : sudo ./install-main.sh   (depuis infra/live, après avoir rempli main.env)
set -euo pipefail

JITSI_RELEASE="${JITSI_RELEASE:-stable-11248-3}"
TARGET="${TARGET:-/opt/academie-live}"
COOLIFY_DYNAMIC_DIR="${COOLIFY_DYNAMIC_DIR:-/data/coolify/proxy/dynamic}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$HERE/main.env" ]; then
  echo "Copiez main.env.example en main.env et remplissez-le avant l'installation." >&2
  exit 1
fi
if grep -q '^JWT_APP_SECRET=change-me' "$HERE/main.env"; then
  echo "JWT_APP_SECRET n'est pas défini dans main.env (openssl rand -hex 32)." >&2
  exit 1
fi
if ! grep -q '^TURN_DOMAIN=.' "$HERE/main.env"; then
  echo "TURN_DOMAIN n'est pas défini dans main.env (domaine du relais TURN)." >&2
  exit 1
fi

# Applique un fichier de réglages : chaque clé remplace sa ligne (même commentée) ou s'ajoute.
apply_env() {
  awk '
    NR == FNR {
      if ($0 ~ /^[[:space:]]*(#|$)/) next
      key = $0; sub(/=.*/, "", key)
      value = $0; sub(/^[^=]*=/, "", value)
      wanted[key] = value
      next
    }
    {
      key = $0; sub(/^#/, "", key); sub(/=.*/, "", key)
      if ($0 ~ /^#?[A-Z0-9_]+=/ && (key in wanted)) {
        if (!(key in written)) { print key "=" wanted[key]; written[key] = 1 }
        next
      }
      print
    }
    END { for (key in wanted) if (!(key in written)) print key "=" wanted[key] }
  ' "$1" .env > .env.new
  mv .env.new .env
}

env_value() { grep "^$1=" .env | tail -n 1 | cut -d= -f2-; }

mkdir -p "$TARGET"
cd "$TARGET"
if [ ! -d docker-jitsi-meet ]; then
  curl -fsSL "https://github.com/jitsi/docker-jitsi-meet/archive/refs/tags/${JITSI_RELEASE}.tar.gz" | tar xz
  mv "docker-jitsi-meet-${JITSI_RELEASE}" docker-jitsi-meet
fi
cd docker-jitsi-meet

if [ ! -f .env ]; then
  cp env.example .env
  ./gen-passwords.sh
fi
apply_env "$HERE/main.env"
grep -q "^JITSI_IMAGE_VERSION=" .env || echo "JITSI_IMAGE_VERSION=${JITSI_RELEASE}" >> .env

COMPOSE_FILES=(docker-compose.yml)
BEHIND_COOLIFY="$(env_value BEHIND_COOLIFY)"
if [ "$BEHIND_COOLIFY" = "1" ]; then
  # Le proxy de Coolify garde 80/443 et le certificat : il joint Jitsi en HTTP par le réseau coolify.
  # Les statistiques du relais vidéo quittent le port 8080, pris par le tableau de bord de Traefik.
  cat > .env.coolify <<'COOLIFY'
DISABLE_HTTPS=1
ENABLE_LETSENCRYPT=0
ENABLE_HTTP_REDIRECT=0
JVB_COLIBRI_PORT=18080
COOLIFY
  grep -q '^VIDEOBRIDGE_MAX_MEMORY=' .env || echo "VIDEOBRIDGE_MAX_MEMORY=2048m" >> .env.coolify
  grep -q '^JICOFO_MAX_MEMORY=' .env || echo "JICOFO_MAX_MEMORY=1024m" >> .env.coolify
  apply_env .env.coolify
  rm -f .env.coolify
  cp "$HERE/coolify/docker-compose.coolify.yml" docker-compose.coolify.yml
  COMPOSE_FILES+=(docker-compose.coolify.yml)
fi
# Relais TURN : les participants dont le réseau bloque l'UDP passent par TCP 3478, ou par TLS sur 443
# derrière Coolify. Prosody leur donne des accès temporaires signés avec TURN_CREDENTIALS.
TURN_DOMAIN="$(env_value TURN_DOMAIN)"
if ! grep -q '^TURN_CREDENTIALS=.' .env; then
  echo "TURN_CREDENTIALS=$(openssl rand -hex 32)" > .env.turn
  apply_env .env.turn
fi
# TLS sur 443 seulement derrière Coolify : sans lui, ce port est pris par le serveur web de Jitsi.
TURNS_HOST=""
if [ "$BEHIND_COOLIFY" = "1" ]; then TURNS_HOST="$TURN_DOMAIN"; fi
cat > .env.turn <<TURN
TURN_HOST=$TURN_DOMAIN
TURN_PORT=3478
TURN_TRANSPORT=tcp
TURNS_HOST=$TURNS_HOST
TURNS_PORT=443
TURN
apply_env .env.turn
rm -f .env.turn
PUBLIC_IP="$(env_value JVB_ADVERTISE_IPS)"
PUBLIC_IP="${PUBLIC_IP%%,*}"
PUBLIC_IP="${PUBLIC_IP%%#*}"
mkdir -p "$TARGET/turn"
chmod 700 "$TARGET/turn"
sed -e "s/__TURN_DOMAIN__/${TURN_DOMAIN}/g" \
    -e "s/__PUBLIC_IP__/${PUBLIC_IP}/g" \
    -e "s/__TURN_SECRET__/$(env_value TURN_CREDENTIALS)/g" \
    "$HERE/turn/turnserver.conf.template" > "$TARGET/turn/turnserver.conf"
# Lisible par l'utilisateur nobody du conteneur ; le dossier reste fermé aux autres comptes du serveur.
chmod 644 "$TARGET/turn/turnserver.conf"
cp "$HERE/turn/docker-compose.turn.yml" docker-compose.turn.yml
COMPOSE_FILES+=(docker-compose.turn.yml)

if [ -f "$HERE/main/docker-compose.override.yml" ] && [ -n "$(env_value XMPP_PRIVATE_IP)" ]; then
  # Des relais vidéo supplémentaires rejoignent Prosody par le réseau privé.
  cp "$HERE/main/docker-compose.override.yml" docker-compose.override.yml
  COMPOSE_FILES+=(docker-compose.override.yml)
fi
# Les commandes docker compose lancées à la main dans ce dossier utilisent les mêmes fichiers.
# Sans cela, un « docker compose up -d » oublierait le réseau de Coolify et ses ports réservés.
(IFS=:; echo "COMPOSE_FILE=${COMPOSE_FILES[*]}") > .env.files
apply_env .env.files
rm -f .env.files

CONFIG_DIR="$(env_value CONFIG)"
CONFIG_DIR="${CONFIG_DIR/#\~/$HOME}"
mkdir -p "$CONFIG_DIR"/{web,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}
cp "$HERE/web/custom-config.js" "$CONFIG_DIR/web/custom-config.js"
# L'adresse du live seule renvoie vers le SaaS (LIVE_HOME_URL), sinon elle ouvrirait une salle au hasard.
LIVE_HOME_URL="$(env_value LIVE_HOME_URL)"
mkdir -p "$CONFIG_DIR/web/nginx-custom"
if [ -n "$LIVE_HOME_URL" ]; then
  sed "s|__LIVE_HOME_URL__|${LIVE_HOME_URL}|g" "$HERE/web/nginx-custom/academie-root.conf.template" \
    > "$CONFIG_DIR/web/nginx-custom/academie-root.conf"
else
  rm -f "$CONFIG_DIR/web/nginx-custom/academie-root.conf"
fi
# mod_token_affiliation (modérateur seulement si le jeton le demande) est livré dans l'image
# Prosody de la même version : main.env l'active, rien à télécharger.

docker compose pull
docker compose up -d
# Le serveur web ne relit custom-config.js et nginx-custom qu'au démarrage.
docker compose restart web

PUBLIC_URL="$(env_value PUBLIC_URL)"
if [ "$BEHIND_COOLIFY" = "1" ]; then
  DOMAIN="${PUBLIC_URL#https://}"
  DOMAIN="${DOMAIN%%/*}"
  ROUTE="$TARGET/academie-live.traefik.yaml"
  sed -e "s/__TURN_DOMAIN__/${TURN_DOMAIN}/g" -e "s/__DOMAIN__/${DOMAIN}/g" \
    "$HERE/coolify/academie-live.traefik.yaml.template" > "$ROUTE"
  if [ -d "$COOLIFY_DYNAMIC_DIR" ]; then
    cp "$ROUTE" "$COOLIFY_DYNAMIC_DIR/academie-live.yaml"
    echo "Route ajoutée au proxy de Coolify : $COOLIFY_DYNAMIC_DIR/academie-live.yaml"
  else
    echo "Ajoutez $ROUTE dans Coolify : Servers > votre serveur > Proxy > Dynamic Configurations."
  fi
fi
echo "Live démarré sur ${PUBLIC_URL}"
