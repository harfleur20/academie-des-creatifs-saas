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

COMPOSE_FILES=(-f docker-compose.yml)
BEHIND_COOLIFY="$(env_value BEHIND_COOLIFY)"
if [ "$BEHIND_COOLIFY" = "1" ]; then
  # Le proxy de Coolify garde 80/443 et le certificat : Jitsi n'écoute qu'en local, en HTTP.
  cat > .env.coolify <<'COOLIFY'
HTTP_PORT=127.0.0.1:8000
HTTPS_PORT=127.0.0.1:8443
DISABLE_HTTPS=1
ENABLE_LETSENCRYPT=0
ENABLE_HTTP_REDIRECT=0
COOLIFY
  grep -q '^VIDEOBRIDGE_MAX_MEMORY=' .env || echo "VIDEOBRIDGE_MAX_MEMORY=2048m" >> .env.coolify
  grep -q '^JICOFO_MAX_MEMORY=' .env || echo "JICOFO_MAX_MEMORY=1024m" >> .env.coolify
  apply_env .env.coolify
  rm -f .env.coolify
  cp "$HERE/coolify/docker-compose.coolify.yml" docker-compose.coolify.yml
  COMPOSE_FILES+=(-f docker-compose.coolify.yml)
fi
if [ -f "$HERE/main/docker-compose.override.yml" ] && [ -n "$(env_value XMPP_PRIVATE_IP)" ]; then
  # Des relais vidéo supplémentaires rejoignent Prosody par le réseau privé.
  cp "$HERE/main/docker-compose.override.yml" docker-compose.override.yml
  COMPOSE_FILES+=(-f docker-compose.override.yml)
fi

CONFIG_DIR="$(env_value CONFIG)"
CONFIG_DIR="${CONFIG_DIR/#\~/$HOME}"
mkdir -p "$CONFIG_DIR"/{web,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}
cp "$HERE/web/custom-config.js" "$CONFIG_DIR/web/custom-config.js"
# Module officiel de Jitsi : modérateur seulement si le jeton le demande.
curl -fsSL -o "$CONFIG_DIR/prosody/prosody-plugins-custom/mod_token_affiliation.lua" \
  "https://raw.githubusercontent.com/jitsi/jitsi-meet/master/resources/prosody-plugins/mod_token_affiliation.lua"

docker compose "${COMPOSE_FILES[@]}" pull
docker compose "${COMPOSE_FILES[@]}" up -d

PUBLIC_URL="$(env_value PUBLIC_URL)"
if [ "$BEHIND_COOLIFY" = "1" ]; then
  DOMAIN="${PUBLIC_URL#https://}"
  DOMAIN="${DOMAIN%%/*}"
  ROUTE="$TARGET/academie-live.traefik.yaml"
  sed "s/__DOMAIN__/${DOMAIN}/g" "$HERE/coolify/academie-live.traefik.yaml.template" > "$ROUTE"
  if [ -d "$COOLIFY_DYNAMIC_DIR" ]; then
    cp "$ROUTE" "$COOLIFY_DYNAMIC_DIR/academie-live.yaml"
    echo "Route ajoutée au proxy de Coolify : $COOLIFY_DYNAMIC_DIR/academie-live.yaml"
  else
    echo "Ajoutez $ROUTE dans Coolify : Servers > votre serveur > Proxy > Dynamic Configurations."
  fi
fi
echo "Live démarré sur ${PUBLIC_URL}"
