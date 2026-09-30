# Plateforme Machines Éphémères

Plateforme permettant de déployer et gérer des **machines éphémères** (conteneurs Docker)
à l'aide de Docker, Vagrant et Ansible — dans l'esprit d'un "lab hacker" automatisé.

## Architecture

- **API REST** (FastAPI) — points d'entrée utilisateur
- **Scheduler** — daemon qui alloue/libère les ressources
- **Worker Agent** — exécute les conteneurs sur chaque worker
- **PostgreSQL** — base de données
- **Traefik** — reverse proxy dynamique (HTTPS)
- **CLI** `labctl` — interface utilisateur en ligne de commande

## Prérequis

| Outil | Version minimale | Installation |
|---|---|---|
| Python | 3.11+ | https://python.org |
| Docker Desktop | 4.x | https://docker.com/products/docker-desktop |
| Vagrant | 2.4+ | https://vagrantup.com |
| VirtualBox | 7.x | https://virtualbox.org (pour Vagrant) |
| Git | 2.40+ | https://git-scm.com |

> **Note** : Ansible est installé automatiquement dans le `.venv` Python,
> pas besoin de l'installer globalement.

## Installation

### Étape 1 — Cloner le projet

```bash
git clone <repo-url>
cd plateforme-machines-ephemeres
```

### Étape 2 — Installer les outils système
Windows (PowerShell en Administrateur) :
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```
Linux / macOS :
```bash
chmod +x install.sh
./install.sh
```

### Étape 3 — Setup du projet

Windows :
```powershell
.\setup.ps1
```
Linux / macOS :
```bash
chmod +x setup.sh
./setup.sh
```

### Étape 4 — Lancer les services
Terminal 1 — API :
```
powershell
cd api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
Terminal 2 — Scheduler :

powershell
cd scheduler
.\.venv\Scripts\Activate.ps1
python -m app.main
```

### Étape 5 — Tester
API Swagger : http://localhost:8000/docs

Traefik Dashboard : http://localhost:8080

Un lab réservé : https://lab-1.lab.local

Comptes par défaut
Email	Mot de passe	Rôle
admin@lab.local	admin12345	Admin
user@lab.local	user12345	User

Commandes utiles
bash
# Démarrer l'infrastructure
docker compose up -d

# Arrêter
docker compose down

# Voir les logs
docker compose logs -f traefik
docker compose logs -f postgres

# Reset DB (⚠️ efface tout)
docker compose down -v
docker compose up -d
cd api && alembic upgrade head && python seed.py