# Ephemeral Machines Platform

Platform for deploying and managing **ephemeral machines** (Docker containers) using Docker, Vagrant, and Ansible — in the spirit of an automated "hacker lab".

## Architecture

- **REST API** (FastAPI) — user entry points
- **Scheduler** — daemon that allocates/releases resources
- **Worker Agent** — executes containers on each worker
- **PostgreSQL** — database
- **Traefik** — dynamic reverse proxy (HTTPS)
- **CLI** `labctl` — command-line user interface

## Prerequisites

| Tool | Minimum Version | Installation |
|---|---|---|
| Python | 3.11+ | https://python.org |
| Docker Desktop | 4.x | https://docker.com/products/docker-desktop |
| Vagrant | 2.4+ | https://vagrantup.com |
| VirtualBox | 7.x | https://virtualbox.org (for Vagrant) |
| Git | 2.40+ | https://git-scm.com |

> **Note**: Ansible is automatically installed within the Python `.venv`, no need to install it globally.

## Installation

### Step 1 — Clone the project

```bash
git clone <repo-url>
cd plateforme-machines-ephemeres
```

### Step 2 — Install system tools
Windows (PowerShell as Administrator):
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```
Linux / macOS:
```bash
chmod +x install.sh
./install.sh
```

### Step 3 — Project setup

Windows:
```powershell
.\setup.ps1
```
Linux / macOS:
```bash
chmod +x setup.sh
./setup.sh
```

### Step 4 — Run services
Terminal 1 — API:
```powershell
cd api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```
Terminal 2 — Scheduler:
```powershell
cd scheduler
.\.venv\Scripts\Activate.ps1
python -m app.main
```

### Step 5 — Test
Swagger API: http://localhost:8000/docs

Traefik Dashboard: http://localhost:8080

Reserved Lab: https://lab-1.lab.local

## Security & Best Practices

The platform integrates several robust security mechanisms:

1. **Input Validation**: Use of Pydantic to strictly validate all payloads (types, email formats, CPU/RAM limits, reservation durations).
2. **Authentication**: JWT (JSON Web Token) authentication with expiration and secure password hashing via **Bcrypt** (`passlib`).
3. **Authorization (RBAC & Ownership)**: Role-based access control (`admin` vs `user`) for sensitive actions (machine management, worker statuses) and strict verification of resource ownership (users can only access their own reservations).
4. **Endpoint Protection**:
   - Configured **CORS** middleware.
   - Strict HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`).
5. **Proper Error Handling**: Centralized exceptions (`AppError`), graceful database integrity error handling (`IntegrityError`), and structured JSON responses without technical stack trace leaks.

### Container Security

To guarantee isolation and integrity of ephemeral environments executed on workers, containers follow these best practices:
- **Minimal Image**: Use of lean or optimized base images combined with systematic package cache cleanup (`apt-get clean && rm -rf /var/lib/apt/lists/*`) to reduce the attack surface.
- **Non-Root User**: Running containers with restricted privileges (non-root user or dedicated `nobody` account) when administrative privileges are not required by the lab.
- **CPU/RAM Limitation**: Strict and dynamic resource allocation to each container according to reservation parameters (`mem_limit` and `nano_cpus` via the Docker API), preventing saturation or Denial of Service (DoS) attacks.
- **Network Isolation**: Attaching all ephemeral containers to the isolated `lab-net` Docker bridge network. No raw ports are exposed directly on the host; all incoming traffic is filtered, compartmentalized, and routed by the Traefik reverse proxy via TLS.
- **No Secrets in Image**: Absolute absence of secrets, private keys, passwords, or hardcoded tokens in Dockerfiles or images. Sensitive configurations are injected dynamically at runtime (via `.env` environment variables or secure volumes).

### Secret Management

The platform enforces a rigorous secret management and protection policy:
- **Environment Variables**: All sensitive settings (`DATABASE_URL`, `JWT_SECRET`, database passwords) are injected exclusively via environment variables read by Pydantic (`BaseSettings`).
- **`.env` Excluded from Git**: The `.env` file and all local configuration files containing secrets are strictly excluded from version control via `.gitignore`. Only the `.env.example` template without real values is versioned.
- **CI/CD Secrets**: Continuous integration and deployment pipelines (GitHub Actions / GitLab CI) securely store and inject production secrets (via encrypted repository *Secrets*), without ever exposing them in build logs.
- **Ansible Vault**: Confidential variables and SSH/deployment access keys used during Ansible provisioning are encrypted via **Ansible Vault** (`ansible-vault encrypt`), ensuring no plaintext passwords transit in playbooks.
- **Secret Rotation**: A regular rotation procedure is in place to periodically renew secret keys (`JWT_SECRET`, DB secrets) without major service disruption to platform services.

### Dependency Security

Software supply chain security is ensured through rigorous dependency management:
- **Dependency Scanning**: Use of automated audit tools (`pip-audit` or `safety` for Python packages, and Trivy / Dependabot for Docker images) integrated into development workflows.
- **Vulnerability Identification**: Continuous analysis of CVEs (Common Vulnerabilities and Exposures) across all `requirements.txt` files (`api`, `scheduler`, root) and container images.
- **Package Updates**: Technology watch and periodic dependency updates to benefit from security patches and stable versions.
- **Blocking Critical Vulnerabilities**: Automatic CI/CD pipeline failure upon detection of a critical or high severity vulnerability (high CVSS), preventing any merge or deployment of vulnerable code.

### Docker Image Scanning

Deployed container security is reinforced by a systematic image scanning policy:
- **Image Scanning**: Use of cutting-edge container scanning tools (such as **Trivy** or Docker Scan) to inspect all layers of built images (e.g., `trivy image lab-kali:latest`).
- **CVE Detection**: Automated identification of all known vulnerabilities (CVEs) present in system packages (`apt`, `apk`, `apk-tools`) and embedded application libraries.
- **Security Thresholds**: Configuration of strict acceptance thresholds in the CI/CD pipeline (e.g., build failure upon presence of vulnerabilities classified as `CRITICAL` or `HIGH`).
- **Vulnerability Remediation**: Immediate application of security patches (base image updates, rebuild with updated packages, or Dockerfile fixes) prior to production release.

### Secret Detection

To prevent accidental leakage of sensitive information in source code, the platform implements strict secret detection controls:
- **Git Scanning**: Use of repository history analysis tools (such as **Gitleaks** or **TruffleHog**) to scan all commits and detect past or current leaks.
- **Credential Detection**: Automated identification of plaintext passwords, database connection strings, and administrative credentials.
- **Token Detection**: Search for API keys, static JWT authentication tokens, OAuth secrets, and SSH private keys (`.key`).
- **Blocking Secrets in Repository**: Integration of *pre-commit* hooks (via Gitleaks) that instantly block any local commit containing secrets before it can be pushed to the remote repository.

### Integration Tests

The platform features a complete integration test suite validating component interoperability:
- **API + PostgreSQL**: Persistence layer validation via SQLAlchemy and Alembic, ensuring compliance of schemas, relationships, and transactions (integration tests in `api/tests/test_integration.py`).
- **API + Docker**: Validation of interactions between the API (via `ContainerManager`) and the Docker daemon (`/var/run/docker.sock`) for container creation and management.
- **Scheduler + Workers**: Tests of the scheduler daemon and synchronization of cores, RAM, and heartbeats with worker agents on the cluster.
- **Reservation + Docker**: End-to-end validation of the ephemeral lab lifecycle (`test_traefik_proxy.py` script), including container provisioning, Traefik dynamic routing (HTTPS), and automatic post-deletion purging.

### Resilience Tests

To guarantee high availability and robustness of the platform against incidents, several resilience scenarios are tested and handled:
- **Worker DOWN**: Automatic detection of unreachable workers (heartbeat interruption beyond tolerance threshold) and immediate status transition to `OFFLINE` to prevent new assignments.
- **Container DOWN**: Handling of accidental stops, container crashes, or creation failures, with event logging (`ReservationEvent`) and transition to `FAILED` status or recovery.
- **Recovery**: Automated incident recovery by the Scheduler (cleanup of orphaned resources, release of allocated CPU/RAM quotas on workers, and expiration of expired or timed-out reservations).
- **Re-scheduling**: Dynamic reallocation of queues (`PENDING`) and switching labs to a healthy and available worker when the infrastructure undergoes a disturbance or node failover.

### Build Stage (CI/CD Pipeline)

The CI/CD build stage executes the following steps in an isolated and reproducible manner:
- **Install Dependencies**: Download and clean installation of Python packages required for the API and Scheduler from locked `requirements.txt` files.
- **Build Application**: Syntactic validation, structural tests, and preparation of FastAPI application modules and synchronization daemons.
- **Build Docker Image**: Assembly of container images (e.g., `infra/dockerfiles/lab-kali/Dockerfile`) via Docker Buildx applying minimization rules and absence of secrets.

### Test Stage (CI/CD Pipeline)

The CI/CD test stage automatically validates non-regression and code correctness prior to any deployment:
- **Unit Tests**: Unit validation of security functions, password hashing (Bcrypt), creation/decoding of JWT tokens, and business logic.
- **API Tests**: Exhaustive validation of all REST endpoints (`/health`, `/users`, `/users/login`, `/machines`, `/workers`, `/reservations`) via the FastAPI test client.
- **Integration Tests**: Execution of the integration suite (`api/tests/test_integration.py`) connected to an ephemeral PostgreSQL service to validate transactions and persistence.

### Security Stage (CI/CD Pipeline)

The security stage automates vulnerability and integrity checks on each build:
- **SAST (Static Application Security Testing)**: Static source code analysis (via Ruff) to detect code flaws, syntax errors, and poor development practices.
- **Dependency Scan**: Automated audit of Python dependencies (via `pip-audit`) to identify known CVEs in third-party libraries.
- **Secret Scan**: Analysis of the repository and commits (via Gitleaks) to detect and block any accidental leakage of passwords, tokens, or private keys.
- **Container Scan**: In-depth analysis of built Docker images (via Trivy) with automatic pipeline failure upon detection of critical vulnerabilities (`CRITICAL` or `HIGH`).

### Registry Stage (CI/CD Pipeline)

The registry stage manages secure publication of validated container images:
- **Tag Image**: Application of multiple tags (e.g., `latest` and unique commit identifier `git sha`) on the Kali Linux image.
- **Publish Image**: Authenticated connection to the remote container registry (GitHub Container Registry - GHCR) and push of images validated by tests and security audits.
- **Manage Versions**: Rigorous version tracking and build traceability ensuring no unaudited image is referenced in production.

### Verification Stage (CI/CD Pipeline)

The post-deployment verification stage validates infrastructure health in production:
- **Healthcheck**: Querying the `/health` endpoint to verify API status and PostgreSQL availability.
- **API Verification**: Testing main routes and authentication.
- **Docker Verification**: Checking daemon status and active containers on worker clusters.
- **Traefik Verification**: Testing router resolution, TLS certificates, and HTTPS dynamic routing.
- **Deployment Validation**: Global validation of the smoke test report confirming continuous deployment success.

## Useful Commands

```bash
# Start infrastructure
docker compose up -d

# Stop infrastructure
docker compose down

# View logs
docker compose logs -f traefik
docker compose logs -f postgres

# Run comprehensive test suite (Unit, API, Integration, Security, Resilience)
.\api\.venv\Scripts\python.exe test_all_criteria.py

# Reset DB (⚠️ deletes everything)
docker compose down -v
docker compose up -d
cd api && alembic upgrade head && python seed.py
```
