#!/bin/bash
# ============================================================
# Regenerar certificados con CN para Sarabhel C2
# Los CN son críticos: Mosquitto usa use_identity_as_username
# y el CN se convierte en el username del cliente.
# ============================================================
set -e

CA_DIR="$(dirname "$0")/../config/certs"
mkdir -p "$CA_DIR"
cd "$CA_DIR"

echo "[+] Regenerando CA (si no existe)..."
if [ ! -f ca.key ]; then
    openssl req -new -x509 -days 365 -nodes \
        -out ca.crt -keyout ca.key \
        -subj "/CN=SarabhelCA/O=Sarabhel/C=UY"
    echo "   CA: ca.crt + ca.key"
else
    echo "   CA ya existe, usando existente"
fi

echo ""
echo "[+] Regenerando certificado del SERVER..."
openssl req -new -nodes -newkey rsa:2048 \
    -keyout server.key -out server.csr \
    -subj "/CN=c2-broker/O=Sarabhel/C=UY"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365
rm -f server.csr
echo "   Server CN=c2-broker"
chmod 600 server.key

echo ""
echo "[+] Regenerando certificado del AGENTE de ejemplo..."
openssl req -new -nodes -newkey rsa:2048 \
    -keyout agent.key -out agent.csr \
    -subj "/CN=AG001/O=Sarabhel/C=UY"
openssl x509 -req -in agent.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out agent.crt -days 365
rm -f agent.csr
echo "   Agent CN=AG001"
chmod 600 agent.key

echo ""
echo "[+] Regenerando certificado para el BRIDGE..."
openssl req -new -nodes -newkey rsa:2048 \
    -keyout bridge.key -out bridge.csr \
    -subj "/CN=crypto-bridge/O=Sarabhel/C=UY"
openssl x509 -req -in bridge.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out bridge.crt -days 365
rm -f bridge.csr
echo "   Bridge CN=crypto-bridge"
chmod 600 bridge.key

echo ""
echo "========================================"
echo "✅ Certificados regenerados"
echo "========================================"
echo "CA:     ca.crt (distribuir a todos)"
echo "Server: server.crt (para Mosquitto)"
echo "Agent:  agent.crt + agent.key (CN=AG001)"
echo "Bridge: bridge.crt + bridge.key (CN=crypto-bridge)"
echo ""
echo "Para generar certs de más agentes:"
echo "  ./gen-agent-cert.sh AG002"
