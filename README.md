<div align="center">

# 🏠 HomeServer

### Ansible-powered Docker Compose Infrastructure

[![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)](https://www.ansible.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tailscale](https://img.shields.io/badge/Tailscale-1C1C1C?style=for-the-badge&logo=tailscale&logoColor=white)](https://tailscale.com/)

*Automated deployment and management of a comprehensive home server stack*

</div>

---

## 📖 Overview

This repository contains Ansible playbooks and roles to provision and manage a personal home server. The entire setup runs as Docker containers via a single Docker Compose file generated from Ansible templates.

The home server runs a comprehensive media management and personal productivity stack, with all services containerized and orchestrated through Docker Compose. The server is reached over Tailscale; a handful of apps are published on the internet through an outbound Cloudflare tunnel.

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎬 Media Hub
Complete *arr stack with Jellyfin, automated downloads, and subtitle management

### 🤖 AI-Powered
OpenWebUI and Mealie integrated with self-hosted LLM API

### 🔒 Secure Access
Tailscale VPN for encrypted remote access, Vaultwarden as the password and secret store

</td>
<td width="50%">

### 📊 Self-Hosted Apps
Finance tracking, notes, recipes and photos

### 🐳 Infrastructure as Code
Fully automated deployment with Ansible + Docker Compose

### 💾 Backups
Daily Postgres dumps and Zerobyte (restic) shipping config volumes to S3

</td>
</tr>
</table>

## 🏗️ Architecture

### System Overview

Editable diagram: [`docs/architecture.drawio`](docs/architecture.drawio) (open with [app.diagrams.net](https://app.diagrams.net) or the VS Code Draw.io extension). It shows the trust boundaries: Cloudflare tunnel vs LAN/tailnet paths, the `qnet` and `docker-api` networks, and who holds the Docker socket.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         🌐 Tailscale Network                        │
│                                                                      │
│  ┌─────────────────┐               ┌──────────────────────────────┐  │
│  │   Home PC       │               │      Home Server             │  │
│  │  (bestione)     │◄────────────► │   (quoggioserver)            │  │
│  │  LLM API :8000  │   Secure      │                              │  │
│  └─────────────────┘   Network     │  ┌────────────────────────┐  │  │
│                                    │  │  cloudflared tunnel    │  │  │
│                                    │  │  (outbound only)       │  │  │
│                                    │  └────────────────────────┘  │  │
│                                    │                              │  │
│                                    │  ┌────────────────────────┐  │  │
│                                    │  │  Docker Compose Stack  │  │  │
│                                    │  │  (qnet network)        │  │  │
│                                    │  │                        │  │  │
│                                    │  │  📺 Media Services     │  │  │
│                                    │  │  🤖 AI & Productivity  │  │  │
│                                    │  │  🏡 Personal Apps      │  │  │
│                                    │  │  🔧 Infrastructure     │  │  │
│                                    │  └───────────┬────────────┘  │  │
│                                    │              │ bind mount    │  │
│                                    │  ┌───────────▼────────────┐  │  │
│                                    │  │  💾 /mnt/das (12TB)    │  │  │
│                                    │  │  TerraMaster D4-320    │  │  │
│                                    │  │  ext4, label das-01    │  │  │
│                                    │  └────────────────────────┘  │  │
│                                    └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Networking

- **Tailscale**: The server is part of a private Tailscale tailnet for secure remote access; MagicDNS resolves `quoggioserver`
- **Cloudflare tunnel**: `cloudflared` publishes selected apps on `*.fantaquoggio.bid` behind Cloudflare Access; no inbound port is opened
- **Firewall**: UFW allows only the tailnet and the LAN to reach host services. Published container ports bypass UFW (Docker manages its own iptables rules), so a service that must stay internal should not declare `ports:` at all
- **Docker Networks**: apps talk to each other on the shared `qnet`. Databases and caches live only on per-stack `internal: true` networks — `db-shared` (postgres + dump sidecar, joined by spesatracker), `immich`, `karutuogg`, `fantaquoggio` — so an app can reach the database it owns and nothing else; the shared Postgres has no published port (use `docker exec postgres psql …`). One exception: `fantaquoggio-postgres` also sits on `qnet` and publishes `5432` **bound to the Tailscale address** (`tailscale_ip`), because the valuation model runs on Christian's machine and reads it directly. Binding a `ports:` line to `{{ tailscale_ip }}` is the pattern for anything that must be reachable from the tailnet but not from the LAN or the internet; the Airflow UI uses it too. `docker-api` (internal) carries only the Docker socket proxy and its consumers; beszel-agent keeps the raw socket because it runs on the host network for accurate metrics
- **Cross-machine Communication**: OpenWebUI can communicate with a self-hosted LLM API running on my home PC (`bestione:8000`)

### Storage

- **TerraMaster D4-320 DAS**: USB-attached enclosure exposing a 12TB ext4 disk (label `das-01`) mounted at `/mnt/das` via fstab
- **Media path**: Centralized under the `media_dir` ansible variable (default `/mnt/das`); all media services (Jellyfin, *arr stack, qBittorrent, VibraVid, Calibre-Web) bind-mount from here
- **Health monitoring**: Beszel-agent passes the DAS block device through for S.M.A.R.T. and mounts `/mnt/das` read-only at `/extra-filesystems/das-01` for capacity reporting

#### Ebooks

Calibre-Web Automated owns two DAS directories, both created by its Ansible task:

- `calibre-library/` — the Calibre library, including `metadata.db`. CWA restructures everything it imports into its own author/title layout.
- `cwa-book-ingest/` — drop zone. **CWA deletes files from here after importing them**, so it must never be pointed at `books/` or any other library directory.

The pre-existing `books/` and `pdfs/` directories are not touched by CWA. To add an ebook, copy it into `cwa-book-ingest/` and CWA imports it within a minute.

### Infrastructure

The setup uses Ansible to:

1. Define each service as an Ansible task that sets a `*_service` fact — a plain Compose service definition plus a `name` key
2. Combine all `*_service` facts into a `services` list
3. Create every bind-mount host directory the services declare (Docker would otherwise create them root-owned)
4. Render `compose.yml` by dumping each service dict as YAML — any Compose key works, there is no allowlist
5. Run `docker compose up` through `community.docker.docker_compose_v2`: only containers whose definition changed are recreated, containers no longer defined are removed

---

## 📦 Services

Each service is defined in `roles/containers/tasks/<service>.yml`. Ports shown as `host→container` when they differ.

<details>
<summary><b>🏠 Dashboard</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Homepage** | `:3000` | Dashboard with tiles for every service |

</details>

<details open>
<summary><b>🎬 Media</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Jellyfin** | `:8096` | Media server for movies and TV shows |
| **Jellyseerr** | `:5055` | Media request management |
| **Sonarr** | `:8989` | TV show automation |
| **Radarr** | `:7878` | Movie automation |
| **Prowlarr** | `:9696` | Indexer management for the *arr stack |
| **Bazarr** | `:6767` | Subtitle management |
| **qBittorrent** | `:8585`, `:6881` | Torrent client |
| **FlareSolverr** | `:8191` | Cloudflare proxy for Prowlarr |
| **VibraVid** | `:8001→8000` | Streaming-site downloader, polled by Sonarr/Radarr as a download client |
| **Calibre-Web Automated** | `:8083` | Ebook library and OPDS feed for KOReader — LAN/Tailscale only, no public route |
| **Immich** | `:2283` | Photo and video library |

</details>

<details open>
<summary><b>🤖 AI & Productivity</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **OpenWebUI** | `:3333→8080` | Web interface for LLM interaction (connects to home PC LLM API) |
| **MyMCP** | `:7000` | Personal MCP (Model Context Protocol) server |
| **Trilium** | `:5050→8080` | Note-taking and knowledge management |

</details>

<details open>
<summary><b>🏡 Personal Applications</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Actual Budget** | `:5006` | Personal finance management |
| **Mealie** | `:9925→9000` | Recipe management with AI integration |
| **Spesatracker** | `:8400` | Grocery receipt and expense tracker |
| **Karutuogg** | `:8410→8000` | Discord card-game bot with companion web app (`karutuogg-web` + `karutuogg-bot`, own Postgres) |
| **FantaQuoggio** | — (tunnel only) | Fantacalcio auction copilot and lineup advisor: API + SPA in one image (`fantaquoggio`), reached only through the tunnel at `app.fantaquoggio.bid`. Its Airflow 3 pipeline runs as `fantaquoggio-airflow-apiserver` (UI `:8420→8080` on the Tailscale address only), `fantaquoggio-airflow-scheduler` and `fantaquoggio-airflow-dag-processor`; two one-shots run first: `fantaquoggio-db-init` (app image) creates databases and roles and runs the app migrations, then `fantaquoggio-airflow-init` (Airflow image) migrates the Airflow metadata before the three Airflow services start. Images are pinned to `fantaquoggio_version`; a deploy is a bump of that variable. Provider files (SofaSport response cache, fantacalcio.it xlsx) live in `fantaquoggio/data/raw/<provider>/` and the trained model artifacts in `fantaquoggio/data/models/mister/`, both outside the backup set |

Disabled in `main.yml`: **Actualtap** (`:8000`), **Docling** (`:5001`).

</details>

<details>
<summary><b>🔒 Infrastructure & Security</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **cloudflared** | — | Outbound Cloudflare tunnel publishing selected apps on `*.fantaquoggio.bid` |
| **Vaultwarden** | `:8222→80` | Password and secret store (Bitwarden-compatible). Reached over HTTPS at `quoggioserver.tailf385d.ts.net` via Tailscale Serve — the web vault needs a secure context and does not work on the plain `:8222` URL. Registration is closed; invite accounts from `/admin` |
| **vaultwarden-backup** | — | Nightly `sqlite3 .backup` snapshot of the vault into `vaultwarden/backups`, kept 14 days |

</details>

<details>
<summary><b>🧰 Ops / Utilities</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **WUD** | `:3004→3000` | What's Up Docker: image-update dashboard, notify-only via Telegram |
| **Beszel** | `:8090` | Server and container monitoring |
| **socket-proxy** | — | Read-only Docker API gateway for Homepage and WUD, on the internal `docker-api` network |
| **Zerobyte** | `:4096` | Backup management |
| **GHCR login** | — | Auth helper for pulling images from GitHub Container Registry |

</details>

---

## 🗄️ Data layer

Databases and caches are containers too. Some apps share the general Postgres; larger apps run their own.

### PostgreSQL

| Instance | Image | Used by |
|----------|-------|---------|
| **postgres** (`:5432`) | `postgres:17` | Spesatracker |
| **immich-postgres** | `immich-app/postgres` (vectorchord) | Immich |
| **karutuogg-postgres** | `postgres:17` | Karutuogg |
| **fantaquoggio-postgres** (`:5432`, Tailscale address only) | `postgres:17` | FantaQuoggio: app database `fantaquoggio` and Airflow metadata `airflow`, one role per writer |

### Redis / Valkey

| Instance | Image | Used by |
|----------|-------|---------|
| **immich-redis** | `valkey/valkey` | Immich |

### Backups

Each Postgres instance has a `*-db-backup` sidecar (`prodrigestivill/postgres-backup-local`) writing daily dumps: **db-backup** (postgres), **immich-db-backup** (immich-postgres), **karutuogg-db-backup** (karutuogg-postgres), **fantaquoggio-db-backup** (fantaquoggio-postgres, both databases).

Vaultwarden's SQLite vault gets the same treatment from **vaultwarden-backup**: a file copy of a live SQLite database can capture a torn state, so the sidecar writes `sqlite3 .backup` snapshots (plus attachments, sends, `config.json` and the RSA keys) into `vaultwarden/backups`.

**Zerobyte** mounts every service's config/data directory and the dump directories under `/containers/…` and ships them with restic to S3. Adding a volume in `zerobyte.yml` only makes it visible — the backup plan itself is configured in the Zerobyte UI. Photos (`/mnt/das/immich`) and media are deliberately excluded because of their size; the DAS is a single disk with no redundancy.

---

## 🚀 Deployment

The deployment follows this workflow:

```
1️⃣ Service Definition
   ↓ Each service defined in roles/containers/tasks/<service>.yml
   
2️⃣ Template Rendering  
   ↓ setup.yml creates bind-mount directories and dumps the services into compose.yml
   
3️⃣ Deployment
   ↓ docker compose up -d recreates only what changed and removes orphans
```

### Key Files

- `roles/containers/templates/compose.yml.j2` - Docker Compose template (dumps each service dict as-is)
- `roles/containers/tasks/setup.yml` - Combines all services, creates bind-mount directories, renders compose file
- `roles/containers/tasks/run.yml` - Deploys the stack
- `roles/containers/tasks/<service>.yml` - Individual service definitions

### Running the Deployment

```bash
# Deploy the entire stack
ansible-playbook site.yml

# Only the containers role
ansible-playbook site.yml --tags containers

# Only some services (comma-separated compose service names)
ansible-playbook site.yml --tags containers -e compose_services=vibravid,sonarr

# Preview: shows the compose.yml diff and which containers would be recreated
ansible-playbook site.yml --tags containers --check --diff
```

---

## ⚙️ Configuration

Services are configured through environment variables and volume mounts defined in their respective Ansible tasks.

### Default Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Timezone** | `Europe/Rome` | Used by most services |
| **User/Group** | `PUID=1000`, `PGID=1000` | Service execution context |
| **Media Storage** | `/mnt/das/` | Shared media directory on TerraMaster D4-320 DAS (`media_dir` var) |
| **Service Data** | `./service-name/` | Per-service data directories |
| **AI Integration** | `http://bestione:8000/v1` | LLM API endpoint for OpenWebUI and Mealie |
