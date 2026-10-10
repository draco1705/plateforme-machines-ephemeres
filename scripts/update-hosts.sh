#!/usr/bin/env bash
set -e
MARKER="# === LAB HACKER ==="
END_MARKER="# === END LAB HACKER ==="

sudo sed -i "/$MARKER/,/$END_MARKER/d" /etc/hosts 2>/dev/null || true

{
    echo "$MARKER"
    for i in $(seq 1 50); do
        echo "127.0.0.1  lab-$i.lab.local"
    done
    echo "$END_MARKER"
} | sudo tee -a /etc/hosts > /dev/null

echo "Fichier /etc/hosts mis à jour avec lab-1 -> lab-50"
