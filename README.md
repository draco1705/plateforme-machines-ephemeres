# Ephemeral Machines Platform (Lab Hacker)

A production-grade, secure platform for provisioning, scheduling, and routing ephemeral machines as isolated Docker containers with automated reverse proxying, dynamic TLS, and auto-healing.

---

## ⚡ Quick Start: 1-Command Demo Runner

You can boot up the entire demo stack with a single command:

### On Windows (PowerShell):
```powershell
.\demo.ps1
```

### On Linux / macOS:
```bash
chmod +x demo.sh && ./demo.sh
```

**What this does automatically:**
1. Starts **PostgreSQL** and **Traefik** in Docker.
2. Applies database migrations (`alembic upgrade head`) and seeds default templates/users.
3. Runs smoke tests.
4. Starts the **FastAPI REST API** (`http://localhost:8000`) and the **Scheduler Daemon**.

---

## 🌐 Web Dashboards & Default Credentials

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **Interactive API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Test all endpoints via Swagger UI |
| **Traefik Proxy Dashboard** | [http://localhost:8080/dashboard/](http://localhost:8080/dashboard/) | Real-time dynamic routing and TLS status |
| **Ephemeral Container Access** | `https://lab-<reservation_id>.lab.local` | Access reserved lab environments |

### Pre-seeded Demo Accounts:
- **Admin**: `admin@lab.local` / `admin12345`
- **User**: `user@lab.local` / `user12345`

---

## 🧪 Running Automated Tests

Run the full pytest suite across API, Scheduler, CLI, and Worker Agent:

```powershell
# Windows
.\api\.venv\Scripts\python.exe -m pytest -v

# Linux / macOS
pytest -v
```

### Complete Criteria Verification Suite:
Runs the comprehensive evaluation verifying database logic, Bcrypt hashing, Pydantic validations, API endpoints, worker heartbeats, and resource recovery:

```powershell
.\api\.venv\Scripts\python.exe test_all_criteria.py
```

### Traefik Dynamic TLS & Proxy Test:
Spawns an actual test container, verifies Traefik auto-discovery, checks HTTP-to-HTTPS redirects and TLS security headers, and tests cleanup:

```powershell
# Requires Docker running:
docker compose up -d
.\api\.venv\Scripts\python.exe test_traefik_proxy.py
```

---

## 💻 CLI Usage Guide (`labctl`)

The dedicated CLI is located at `cli/labctl.py`.

### 1. Authenticate
```bash
python cli/labctl.py login user@lab.local user12345
```

### 2. View Machine Catalog
```bash
python cli/labctl.py machines
```

### 3. Reserve an Ephemeral Machine
```bash
# Reserve predefined template (e.g., Kali Linux)
python cli/labctl.py reserve --machine kali --duration 30

# Or reserve by any standard Docker image
python cli/labctl.py reserve --image nginxdemos/hello --duration 15
```

### 4. Inspect & List Active Reservations
```bash
python cli/labctl.py list
python cli/labctl.py status <reservation_id>
```

### 5. Access and Execute Inside Containers
```bash
# Connect via Traefik HTTPS:
python cli/labctl.py connect <reservation_id> --wait

# Drop into an interactive bash shell inside the container:
python cli/labctl.py exec <reservation_id> /bin/bash

# SSH directly into the container:
python cli/labctl.py ssh <reservation_id> 
```

### 6. Stop and Release
```bash
# Release resources and purge container immediately:
python cli/labctl.py delete <reservation_id>
```

---

## 🏗️ Architecture & Deployment Modes

### Mode 1: Local Standalone (Default & Demo)
- **Postgres** & **Traefik** run via Docker Compose.
- **FastAPI API** and **Scheduler** run on the host communicating with the Docker daemon.

### Mode 2: Multi-VM Cluster Mode (Vagrant + Ansible)
Deploys 1 Controller VM (`192.168.56.10`) and 3 Worker VMs (`192.168.56.11-13`):
```bash
vagrant up
cd ansible
ansible-playbook -i inventory.ini setup.yml
```

---

## 🛡️ Resilience & Auto-Healing

The scheduler includes continuous health monitoring:
- **Worker Heartbeats**: Workers missing heartbeats (> 30s) are marked `OFFLINE`.
- **Container Failure Detection**: If a container crashes or is manually killed (`docker kill`), the scheduler automatically reschedules the allocation onto an available healthy worker, recreates the container, and updates Traefik routing.

---

## 🔒 DevSecOps Pipeline
GitHub Actions CI (`.github/workflows/ci.yml`) features:
- **SAST**: Ruff linting & code formatting checks.
- **Dependency Audit**: Pip-audit scanning Python dependencies for known CVEs.
- **Secret Scanning**: Gitleaks detecting credentials before commits.
- **Container Security**: Trivy scanning images for security vulnerabilities.
