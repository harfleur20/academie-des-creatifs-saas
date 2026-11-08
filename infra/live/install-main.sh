#!/usr/bin/env bash
# Installe ou met à jour le serveur principal du live sur un VPS Linux avec Docker.
# Usage : sudo ./install-main.sh   (depuis infra/live, après avoir rempli main.env)
set -euo pipefail

JITSI_RELEASE="${JITSI_RELEASE:-stable-11248-3}"
TARGET="${TARGET:-/opt/academie-live}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$HERE/main.env" ]; then
  echo "Copiez main.env.example en main.env et remplissez-le avant l'installation." >&2
  exit 1
fi
if grep -q '^JWT_APP_SECRET=change-me' "$HERE/main.env"; then
  echo "JWT_APP_SECRET n'est pas défini dans main.env (openssl rand -hex 32)." >&2
  exit 1
fi

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

# Applique main.env : chaque clé remplace sa ligne (même commentée) ou s'ajoute en fin de fichier.
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
' "$HERE/main.env" .env > .env.new
mv .env.new .env
grep -q "^JITSI_IMAGE_VERSION=" .env || echo "JITSI_IMAGE_VERSION=${JITSI_RELEASE}" >> .env

CONFIG_DIR="$(grep '^CONFIG=' .env | cut -d= -f2-)"
CONFIG_DIR="${CONFIG_DIR/#\~/$HOME}"
mkdir -p "$CONFIG_DIR"/{web,transcripts,prosody/config,prosody/prosody-plugins-custom,jicofo,jvb,jigasi,jibri}
cp "$HERE/web/custom-config.js" "$CONFIG_DIR/web/custom-config.js"
# Module officiel de Jitsi : modérateur seulement si le jeton le demande.
curl -fsSL -o "$CONFIG_DIR/prosody/prosody-plugins-custom/mod_token_affiliation.lua" \
  "https://raw.githubusercontent.com/jitsi/jitsi-meet/master/resources/prosody-plugins/mod_token_affiliation.lua"

COMPOSE_FILES=(-f docker-compose.yml)
if [ -f "$HERE/main/docker-compose.override.yml" ] && grep -q '^XMPP_PRIVATE_IP=' "$HERE/main.env"; then
  # Des relais vidéo supplémentaires rejoignent Prosody par le réseau privé.
  cp "$HERE/main/docker-compose.override.yml" docker-compose.override.yml
  COMPOSE_FILES+=(-f docker-compose.override.yml)
fi
docker compose "${COMPOSE_FILES[@]}" pull
docker compose "${COMPOSE_FILES[@]}" up -d
echo "Live démarré sur $(grep '^PUBLIC_URL=' .env | cut -d= -f2-)"
