#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$DIR/certs"
if [ -f "$DIR/certs/lab.local.crt" ] && [ -f "$DIR/certs/lab.local.key" ]; then
    echo "Certificats déjà présents dans certs/"
    exit 0
fi
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$DIR/certs/lab.local.key" \
    -out "$DIR/certs/lab.local.crt" \
    -subj "/CN=*.lab.local" \
    -addext "subjectAltName=DNS:*.lab.local,DNS:lab.local"
echo "Certificats générés dans certs/"
