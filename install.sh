#!/bin/bash

set -e

echo "=========================================="
echo " Project Environment Installer - Linux"
echo "=========================================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

------------------------------------------
Check sudo
------------------------------------------

if ! command -v sudo >/dev/null 2>&1; then
echo "ERROR: sudo is required."
exit 1
fi

------------------------------------------
Update system
------------------------------------------

echo ""
echo "[1/5] Updating system..."

sudo apt update

------------------------------------------
Install basic dependencies
------------------------------------------

echo ""
echo "[2/5] Installing basic packages..."

sudo apt install -y
python3
python3-pip
python3-venv
curl
ca-certificates
gnupg
lsb-release
vagrant

------------------------------------------
Install Docker
------------------------------------------

echo ""
echo "[3/5] Installing Docker..."

if ! command -v docker >/dev/null 2>&1; then

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL \
    https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
    https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

sudo apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin


else

echo "Docker is already installed."


fi

------------------------------------------
Docker permissions
------------------------------------------

sudo usermod -aG docker "$USER"

------------------------------------------
Python virtual environment
------------------------------------------

echo ""
echo "[4/5] Creating Python virtual environment..."

if [ ! -d ".venv" ]; then

python3 -m venv .venv


else

echo ".venv already exists."


fi

------------------------------------------
Python dependencies
------------------------------------------

echo ""
echo "[5/5] Installing Python dependencies..."

.venv/bin/python -m pip install --upgrade pip

if [ -f "requirements.txt" ]; then

.venv/bin/python -m pip install -r requirements.txt


else

echo "WARNING: requirements.txt not found."


fi

------------------------------------------
Verification
------------------------------------------

echo ""
echo "=========================================="
echo " Installation completed!"
echo "=========================================="

echo ""
echo "Python:"
.venv/bin/python --version

echo ""
echo "Python packages:"
.venv/bin/python -m pip list

echo ""
echo "Docker:"
docker --version

echo ""
echo "Docker Compose:"
docker compose version

echo ""
echo "Vagrant:"
vagrant --version

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="

echo ""
echo "IMPORTANT:"
echo "Log out and log back in for Docker permissions."