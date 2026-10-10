# Ephemeral Machines Platform (Lab Hacker)

Platform for provisioning, configuring, and managing ephemeral machines as Docker containers using FastAPI, PostgreSQL, Traefik, Vagrant, and Ansible.

## Architecture Overview

The system consists of the following components:

- REST API (FastAPI): Handles user authentication, machine templates, reservations, and worker registry.
- Scheduler: Background daemon that monitors pending reservations, enforces resource constraints, provisions containers, tracks expiration, and auto-heals failed workloads.
- Worker Agent: Service running on each worker node reporting hardware capacity and handling container lifecycle requests.
- Traefik Reverse Proxy: Dynamic reverse proxy providing automated HTTPS routing and domain resolution per container.
- PostgreSQL: Relational database storing users, workers, machine templates, reservations, and event logs.
- Dedicated CLI (labctl): Command-line tool for users to manage sessions, reserve machines, and access containers.

## How Users Interact With The Platform

Users interact with the platform on two distinct levels:

1. Platform Control Level (Cluster and Resource Management):
   Users use the CLI (`labctl`) or REST API to browse templates, request ephemeral machines, inspect remaining time, and release allocations. The scheduler assigns requests to available workers.

2. Container Execution Level (Direct In-Container Access):
   Users do not just control workers; they execute commands and run software directly inside their ephemeral containers:
   - Interactive Shell: Run `python cli/labctl.py exec <id>` to drop directly into a shell inside the container.
   - SSH Access: For Linux/Kali containers with SSH enabled, connect via `python cli/labctl.py ssh <id>` or `ssh root@lab-<id>.lab.local -p 22` (default password: `kali`).
   - Web Access: Access web services through Traefik HTTPS at `https://lab-<id>.lab.local`.

## Prerequisites

- Operating System: Windows, Linux, or macOS
- Python: Version 3.11 or higher
- Docker and Docker Compose
- VirtualBox and Vagrant (optional, required only for multi-VM cluster mode)
- Git

## Getting Started

### Option A: Local Standalone Mode (Fastest)

This mode runs PostgreSQL and Traefik in Docker, while the API and Scheduler run on the host.

1. Start database and reverse proxy:
```bash
docker compose up -d
```

2. Initialize database schema and default seed data:
```bash
cd api
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python seed.py
cd ..
```

3. Configure local DNS resolution (one-time setup):
- Windows (Run PowerShell as Administrator):
```powershell
.\scripts\update-hosts.ps1
```
- Linux / macOS:
```bash
sudo ./scripts/update-hosts.sh
```

4. Start REST API (Terminal 1):
```bash
cd api
# Activate venv
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Start Scheduler (Terminal 2):
```bash
cd scheduler
python -m venv .venv
# Activate venv
pip install -r requirements.txt
python -m app.main
```

### Option B: Multi-VM Cluster Mode (Vagrant and Ansible)

This mode deploys 1 Controller VM (`192.168.56.10`) and 3 Worker VMs (`192.168.56.11-13`).

1. Boot all virtual machines:
```bash
vagrant up
```

2. Deploy complete infrastructure with Ansible:
```bash
cd ansible
ansible-playbook -i inventory.ini setup.yml
```

The Ansible playbook performs the following tasks:
- Installs Docker CE and Compose plugin on all cluster nodes.
- Synchronizes project sources from host to the controller.
- Sets up environment files and SSL certificates.
- Runs PostgreSQL and Traefik via Docker Compose.
- Executes Alembic migrations and database seeding.
- Deploys and enables `lab-api.service` and `lab-scheduler.service` on the controller.
- Deploys and enables `worker-agent.service` on each worker node.

## CLI Usage Guide (labctl)

The CLI tool is located at `cli/labctl.py`.

### 1. User Authentication
```bash
# Login (seeded accounts: user@lab.local / user12345 or admin@lab.local / admin12345)
python cli/labctl.py login user@lab.local user12345

# Logout
python cli/labctl.py logout
```

### 2. View Machine Catalog
```bash
python cli/labctl.py machines
```

### 3. Create a Machine Template
```bash
python cli/labctl.py create-machine --name debian-tools --image debian:12 --cpu 1 --ram 512 --port 80
```

### 4. Reserve an Ephemeral Machine
```bash
# Reserve by machine name
python cli/labctl.py reserve --machine kali --cpu 1 --ram 512 --duration 30

# Reserve by image name
python cli/labctl.py reserve --image nginxdemos/hello --duration 15

# Reserve by template ID
python cli/labctl.py reserve --machine-id 1 --cpu 1 --ram 512 --duration 60
```

### 5. List and Inspect Reservations
```bash
# List all personal reservations with remaining time
python cli/labctl.py list

# View detailed status and access information
python cli/labctl.py status 1
```

### 6. Connect and Command Inside Containers
```bash
# Connect via Traefik reverse proxy (checks HTTPS connectivity and prints access details)
python cli/labctl.py connect 1 --wait

# Open container in default web browser
python cli/labctl.py connect 1 --browser

# Execute commands directly inside the container (interactive shell)
python cli/labctl.py exec 1 /bin/bash
python cli/labctl.py exec 1 uname -a

# Connect directly via SSH (for Kali or Linux containers)
python cli/labctl.py ssh 1
# Manual SSH alternative:
ssh root@lab-1.lab.local -p 22
```

### 7. Lifecycle Controls and Release
```bash
# Stop active reservation
python cli/labctl.py stop 1

# Start stopped reservation
python cli/labctl.py start 1

# Delete and release resources immediately
python cli/labctl.py delete 1
```

## Resilience and Auto-Healing

The scheduler includes continuous health monitoring and self-healing:

- Worker Offline Detection: Workers that miss heartbeats for more than 30 seconds are automatically marked `OFFLINE`.
- Container Crash Detection: If an ephemeral container is killed or crashes (`docker kill`), the scheduler detects the failure within seconds.
- Auto-Repair: The scheduler reschedules the impacted reservation onto an available healthy worker, recreates the container, re-applies Traefik reverse proxy labels, and updates the database records.

To test auto-repair live:
1. Reserve a machine: `python cli/labctl.py reserve --machine kali`.
2. Wait until status is `RUNNING` via `python cli/labctl.py list`.
3. Kill the container manually: `docker kill lab-reservation-1`.
4. Observe the scheduler logs: it detects the crash and automatically recovers the container.

## Web Interfaces and Dashboards

- Interactive REST API Documentation: http://localhost:8000/docs
- Traefik Routing Dashboard: http://localhost:8080/dashboard/
- Ephemeral Lab Instance: https://lab-<id>.lab.local

## Running Automated Tests

Run the full pytest suite (Unit, API, Scheduler, CLI, and Worker Agent):
```bash
.\api\.venv\Scripts\python.exe -m pytest api/tests/ scheduler/tests/ cli/tests/ worker_agent/test_agent_endpoints.py
```

Run the complete evaluation suite verifying all project criteria:
```bash
.\api\.venv\Scripts\python.exe test_all_criteria.py
```

## DevSecOps Pipeline

The repository includes a GitHub Actions pipeline (`.github/workflows/ci.yml`) covering:
- Static Code Analysis (SAST): Ruff linting.
- Dependency Security: Pip-audit checking Python packages for CVEs.
- Secret Detection: Gitleaks scanning commits for leaked credentials.
- Multi-component Integration Tests: Automated test execution against a test database.
- Container Image Scan: Trivy scanning Docker images for high and critical CVEs.
- Container Registry Publish: Automated build and push to GitHub Container Registry (GHCR).
