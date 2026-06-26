#!/usr/bin/env bash
# deploy.sh — Deploy c2-broker completo a una VM.
#
# Uso:
#   ./scripts/deploy.sh user@1.2.3.4
#
# Requisitos:
#   - Tener acceso SSH a la VM (con key, no password)
#   - Tener rsync instalado localmente
#
# La VM debe ser una máquina limpia con Ubuntu 22.04+.
# El script instala Docker, copia los archivos, y levanta todo.

set -euo pipefail
shopt -s inherit_errexit

TARGET="${1:?Uso: ./scripts/deploy.sh user@hostname}"

# ── Colores (si el terminal lo soporta) ──
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; NC=''
fi
ok()  { echo -e "${GREEN}✅${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠️${NC} $*"; }
fail(){ echo -e "${RED}❌${NC} $*"; exit 1; }

# ── Pre-flight ──
echo -e "\n${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}  C2 Broker — Deploy Automático${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}\n"

# Verificar herramientas locales
command -v rsync &>/dev/null  || fail "Falta rsync. Instalalo con: apt install rsync"
command -v ssh   &>/dev/null  || fail "Falta ssh."
command -v ssh-keygen &>/dev/null || warn "ssh-keygen no encontrado (no crítico)"

# Verificar que SSH alcanza al target
echo "🔍 Verificando SSH a $TARGET ..."
ssh -o ConnectTimeout=5 -o BatchMode=yes "$TARGET" "echo OK" &>/dev/null \
  || fail "No se puede conectar por SSH a $TARGET (¿usás key? ¿está la VM encendida?)"
ok "SSH OK"

# ── Rsync (subir archivos) ──
echo -e "\n📦 Subiendo archivos a $TARGET ..."
rsync -avz --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='log/*' \
  --exclude='data/*' \
  --exclude='.gitignore' \
  "$(dirname "$0")/.."/* "$TARGET:~/c2-broker/"
ok "Archivos sincronizados"

# ── Setup remoto ──
echo -e "\n🔧 Configurando VM ..."
ssh "$TARGET" bash -s << 'REMOTESCRIPT'
set -euo pipefail

# Colores para output remoto
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()  { echo -e "${GREEN}✅${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠️${NC} $*"; }

cd ~/c2-broker

# ── 1. Docker ──
if ! command -v docker &>/dev/null; then
  echo "  Instalando Docker ..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  ok "Docker instalado"
else
  ok "Docker ya instalado"
fi

# Docker Compose plugin (v2)
if ! docker compose version &>/dev/null; then
  echo "  Instalando docker compose plugin ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq docker-compose-v2
  ok "Docker Compose instalado"
else
  ok "Docker Compose ya instalado"
fi

# ── 2. Directorios de datos ──
mkdir -p data log

# ── 3. PSK (generar si no existe) ──
if [ ! -f crypto_lib/psk.key ]; then
  echo "  Generando PSK ..."
  python3 crypto_lib/cipher.py genkey crypto_lib/psk.key
  ok "PSK generado"
else
  ok "PSK existe"
fi

# ── 4. Verificar que los certificados existen ──
for f in config/certs/ca.crt config/certs/server.crt config/certs/server.key \
         config/certs/bridge.crt config/certs/bridge.key; do
  if [ ! -f "$f" ]; then
    warn "Falta $f — regenerando certificados ..."
    bash scripts/gen-certs.sh
    ok "Certificados regenerados"
    break
  fi
done
ok "Certificados OK"

# ── 5. Verificar que el ACL existe ──
if [ ! -f config/acl.conf ]; then
  warn "Falta acl.conf"
  ls config/ 2>/dev/null
fi

# ── 6. Levantar servicios ──
echo -e "\n🚀 Levantando servicios ..."
docker compose up -d --build

echo ""
docker compose ps

# ── 7. Verificación rápida ──
echo -e "\n⏳ Esperando que los servicios respondan ..."
sleep 3

# Verificar broker (MQTT)
if docker compose exec broker mosquitto_sub -h localhost -p 8883 -t '$SYS/broker/version' -C 1 &>/dev/null; then
  ok "Broker MQTT respondiendo"
else
  warn "No se pudo verificar el broker (puede necesitar clientes mosquitto)"
fi

# Verificar bridge (HTTP)
if curl -sf http://localhost:5000/api/health >/dev/null 2>&1; then
  ok "Bridge HTTP respondiendo en localhost:5000"
else
  warn "Bridge no responde aún — revisá con: docker compose logs bridge"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  Deploy completado${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo "  Bridge HTTP : http://<IP_VM>:5000/api/health"
echo "  Broker MQTT : <IP_VM>:8883 (MQTTS con certificados)"
echo ""
echo "  Para ver logs:"
echo "    docker compose logs -f"
echo "    docker compose logs -f broker"
echo "    docker compose logs -f bridge"
echo ""
echo "  Los agentes se conectan al puerto 8883 con TLS."
echo "  IMPORTANTE: el server cert tiene CN=c2-broker."
echo "  Si conectan por IP, necesitan tls_insecure_set(true)."
echo ""

REMOTESCRIPT

ok "Todo listo. Tus compañeros pueden conectar a:"
echo "   MQTT:   $TARGET:8883"
echo "   Bridge: http://$(echo "$TARGET" | cut -d@ -f2):5000"
echo ""
echo "Recordales: NO usan usuario/contraseña. Usan certificados."
