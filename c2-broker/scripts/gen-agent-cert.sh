#!/bin/bash
# ============================================================
# Generar certificado para un nuevo agente
# Uso: ./gen-agent-cert.sh AG002
# ============================================================
set -e

if [ -z "$1" ]; then
    echo "Uso: $0 <AGENT_ID>"
    echo "Ej:  $0 AG002"
    exit 1
fi

AGENT_ID="$1"
CA_DIR="$(dirname "$0")/../config/certs"
OUT_DIR="${2:-$CA_DIR}"

if [ ! -f "$CA_DIR/ca.crt" ] || [ ! -f "$CA_DIR/ca.key" ]; then
    echo "[!] CA no encontrada en $CA_DIR"
    echo "    Ejecutá primero gen-certs.sh"
    exit 1
fi

echo "[+] Generando certificado para $AGENT_ID..."

openssl req -new -nodes -newkey rsa:2048 \
    -keyout "$OUT_DIR/$AGENT_ID.key" -out "$OUT_DIR/$AGENT_ID.csr" \
    -subj "/CN=$AGENT_ID/O=Sarabhel/C=UY"

openssl x509 -req -in "$OUT_DIR/$AGENT_ID.csr" \
    -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
    -out "$OUT_DIR/$AGENT_ID.crt" -days 365

rm -f "$OUT_DIR/$AGENT_ID.csr"
chmod 600 "$OUT_DIR/$AGENT_ID.key"

echo "[+] OK: $OUT_DIR/$AGENT_ID.crt + $OUT_DIR/$AGENT_ID.key"
echo "    CN=$AGENT_ID"
