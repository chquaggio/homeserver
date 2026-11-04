<div align="center">

# 🏠 HomeServer

## Ansible-powered Docker Compose Infrastructure

[![Ansible](https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white)](https://www.ansible.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tailscale](https://img.shields.io/badge/Tailscale-1C1C1C?style=for-the-badge&logo=tailscale&logoColor=white)](https://tailscale.com/)

*Ansible renders and deploys the Docker Compose stack of one home server*

</div>

---

## 📖 Overview

This repository holds the Ansible playbooks and roles that provision a personal home server and deploy its services. Every service runs as a
Docker container, and all of them are defined in a single Docker Compose file that Ansible generates from one task file per service.

The server hosts a media stack built around Jellyfin and the *arr applications, together with personal apps for finance, notes, recipes and
photos. It is reached over Tailscale, while a few apps are published on the internet through an outbound Cloudflare tunnel.

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎬 Media Hub

Sonarr, Radarr and Prowlarr find releases, qBittorrent and VibraVid download them, Bazarr adds subtitles and Jellyfin serves the result. Torrent
traffic leaves through a Proton VPN tunnel.

### 🤖 Local LLM

Spesatracker parses grocery receipts with an LLM that runs on the home PC, so receipt data does not leave the house.

### 🔒 Secure Access

Remote access goes through Tailscale, and Vaultwarden stores passwords and secrets.

</td>
<td width="50%">

### 📊 Self-Hosted Apps

Actual Budget, Trilium, Mealie and Immich cover finance, notes, recipes and photos.

### 🐳 Infrastructure as Code

One Ansible run renders the Compose file and recreates only the containers whose definition changed.

### 💾 Backups

Sidecars dump every Postgres database daily, and Zerobyte ships the config volumes and the dumps to S3 with restic.

</td>
</tr>
</table>

## 🖥️ Host

The server is a Beelink mini PC with 4 cores and 15 GB of RAM running Ubuntu, and its Intel GPU handles Jellyfin's hardware transcoding through Quick Sync. Media and photos live on a TerraMaster D4-320 enclosure attached over USB, described under [Storage](#storage).

`site.yml` configures the host with three roles before it deploys the containers:

- `common` installs the base packages, Node, Homebrew and the dotfiles from `chquaggio/dotfiles`, and hardens the network with UFW and an sshd configuration that refuses root logins. `ansible-playbook site.yml -t firewall` runs the firewall part alone.
- `docker` installs Docker Engine and the Compose plugin from Docker's apt repository and adds the user to the `docker` group.
- `system` mounts the DAS through fstab, failing the run if `/mnt/das` is not a mountpoint afterwards, and installs Neovim.

Some of the setup lives outside this repository, so a rebuild of the server needs the following steps by hand:

- Tailscale is installed and logged in manually.
- The routes of the Cloudflare tunnel and their Access policies are configured in the Cloudflare dashboard, because `cloudflared` runs with a token.
- The Zerobyte backup plan is configured in the Zerobyte UI.
- The Proton VPN subscription and its WireGuard key belong to the Proton account, and the key reaches the server through the vault.
- Secrets live in `group_vars/all/vault.yml`, encrypted with Ansible Vault, and the password file `.vault_pass` stays on the machine that runs Ansible.

## 🏗️ Architecture

### System Overview

The editable diagram is [`docs/architecture.drawio`](docs/architecture.drawio), which opens in [app.diagrams.net](https://app.diagrams.net) or
in the VS Code Draw.io extension. It draws the trust boundaries, that is the paths through the Cloudflare tunnel and through the LAN or the
tailnet, the `qnet` and `docker-api` networks, the Proton VPN path that only qBittorrent uses, and the containers that hold the Docker socket.

```text
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

- **Tailscale**: the server belongs to a private Tailscale tailnet, through which every remote device reaches it, and MagicDNS resolves its name
  `quoggioserver`.
- **Cloudflare tunnel**: `cloudflared` keeps an outbound connection to Cloudflare and publishes a few apps on `*.fantaquoggio.bid`, so the
  router opens no inbound port for them. Some of these hostnames sit behind Cloudflare Access with an email one-time code, while the others
  rely on the app's own login. The list of published apps and the policy of each one are kept in `docs/private/exposure.md`, which git
  ignores because the repository is public.
- **VPN egress (qBittorrent only)**: qBittorrent runs inside the network namespace of `gluetun`, which keeps a WireGuard tunnel to Proton VPN
  open, so torrent traffic can leave only through the tunnel and stops when the tunnel drops. Proton forwards one peer port into the tunnel,
  which is why the home router has no forwarding rule for qBittorrent. Every other container, `cloudflared` and Tailscale included, keeps using
  the home connection. Setup, verification and troubleshooting are in [`docs/vpn.md`](docs/vpn.md).
- **Firewall**: UFW lets only the tailnet and the LAN reach host services. Docker inserts its own iptables rules ahead of UFW, so published
  container ports bypass it, and a service that must stay internal therefore declares no `ports:` at all.
- **Docker networks**: apps talk to each other on the shared `qnet`. Databases and caches sit only on per-stack networks marked
  `internal: true`, so that an app reaches the database it owns and nothing else. These networks are `db-shared` (the shared Postgres and its
  dump sidecar, joined by Spesatracker), `immich`, `karutuogg` and `fantaquoggio`. The shared Postgres has no published port, and it is queried
  with `docker exec postgres psql …`.
- **Tailnet-only ports**: `fantaquoggio-postgres` also sits on `qnet` and publishes `5432` bound to the Tailscale address (`tailscale_ip`),
  because the valuation model runs on Christian's machine and reads the database directly. Binding a `ports:` line to `{{ tailscale_ip }}` is
  the pattern for anything that the tailnet must reach while the LAN and the internet must not, and the Airflow UI follows it as well.
- **Docker socket**: the internal `docker-api` network carries only the Docker socket proxy and the containers that read from it. Beszel-agent
  keeps the raw socket, because it runs on the host network to collect accurate metrics.
- **Cross-machine calls**: Spesatracker calls the self-hosted LLM API that runs on the home PC (`bestione:8000`).

### Storage

- **TerraMaster D4-320 DAS**: a USB enclosure exposes a 12TB ext4 disk (label `das-01`), which fstab mounts at `/mnt/das`.
- **Media path**: the `media_dir` Ansible variable (default `/mnt/das`) is the root that every media service bind-mounts from, which includes
  Jellyfin, the *arr stack, qBittorrent, VibraVid and Calibre-Web.
- **Health monitoring**: Beszel-agent receives the DAS block device to read S.M.A.R.T. data, and mounts `/mnt/das` read-only at
  `/extra-filesystems/das-01` to report capacity.

#### Ebooks

Calibre-Web Automated (CWA) owns two DAS directories, both of which its Ansible task creates:

- `calibre-library/` holds the Calibre library, including `metadata.db`, and CWA restructures everything it imports into its own author and
  title layout.
- `cwa-book-ingest/` is the drop zone. **CWA deletes files from it after importing them**, so it must never point at `books/` or at any other
  library directory.

CWA does not touch the older `books/` and `pdfs/` directories. An ebook copied into `cwa-book-ingest/` appears in the library within a minute.

### Infrastructure

Ansible builds the stack in five steps:

1. Each service is an Ansible task that sets a `*_service` fact, which holds a plain Compose service definition plus a `name` key.
2. Ansible collects every `*_service` fact into a `services` list.
3. It creates every bind-mount host directory that the services declare, because Docker would otherwise create them owned by root.
4. It renders `compose.yml` by dumping each service dict as YAML, so any Compose key works and no allowlist applies.
5. It runs `docker compose up` through `community.docker.docker_compose_v2`, which recreates only the containers whose definition changed and
   removes the containers that are no longer defined.

---

## 📦 Services

Each service is defined in `roles/containers/tasks/<service>.yml`. Where the host port differs from the container port, the table shows both as
`host→container`.

<details>
<summary><b>🏠 Dashboard</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Homepage** | `:3000` | Dashboard with a tile for every service |

</details>

<details open>
<summary><b>🎬 Media</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Jellyfin** | `:8096` | Media server for movies and TV shows |
| **Seerr** | `:5055` | Media request management. The container runs the Seerr image, while its task file keeps the earlier name `jellyseerr.yml` |
| **Sonarr** | `:8989` | TV show automation |
| **Radarr** | `:7878` | Movie automation |
| **Prowlarr** | `:9696` | Indexer management for the *arr stack |
| **Bazarr** | `:6767` | Subtitle management |
| **qBittorrent** | `:8585` (published by gluetun) | Torrent client. It shares gluetun's network, so its only route to the internet is the Proton VPN tunnel, and other containers reach it as `qbittorrent:8585` through gluetun's alias on `qnet`. Its peer port is the one Proton forwards, and no peer port is published on the host |
| **FlareSolverr** | `:8191` | Proxy that solves Cloudflare challenges for Prowlarr |
| **VibraVid** | `:8001→8000` | Streaming-site downloader that Sonarr and Radarr poll as a download client |
| **Calibre-Web Automated** | `:8083` | Ebook library and OPDS feed for KOReader, reachable from the LAN and the tailnet only |
| **Immich** | `:2283` | Photo and video library, run as `immich-server` with `immich-machine-learning` for face recognition and smart search |

</details>

<details open>
<summary><b>🤖 AI & Productivity</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **MyMCP** | `:7000` | Personal MCP (Model Context Protocol) server |
| **Trilium** | `:5050→8080` | Notes and knowledge management |

</details>

<details open>
<summary><b>🏡 Personal Applications</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Actual Budget** | `:5006` | Personal finance management |
| **Mealie** | `:9925→9000` | Recipe management |
| **Spesatracker** | `:8400` | Grocery receipt and expense tracker, which parses receipts with the LLM on bestione |
| **Karutuogg** | `:8410→8000` | Discord card-game bot with a companion web app, split into `karutuogg-web` and `karutuogg-bot` with its own Postgres |
| **FantaQuoggio** | none (tunnel only) | Fantacalcio auction copilot and lineup advisor. API and SPA ship in one image (`fantaquoggio`), which is reachable only through the tunnel at `app.fantaquoggio.bid`. Its Airflow 3 pipeline runs as `fantaquoggio-airflow-apiserver` (UI on `:8420→8080`, bound to the Tailscale address), `fantaquoggio-airflow-scheduler` and `fantaquoggio-airflow-dag-processor`. Two one-shot containers run before them: `fantaquoggio-db-init` (app image) creates the databases and roles and runs the app migrations, after which `fantaquoggio-airflow-init` (Airflow image) migrates the Airflow metadata. Both images are pinned to `fantaquoggio_version`, so a deploy is a bump of that variable. Provider files (the SofaSport response cache and the fantacalcio.it xlsx) live in `fantaquoggio/data/raw/<provider>/` and the trained model artifacts in `fantaquoggio/data/models/mister/`, and neither directory is in the backup set |

**Actualtap** (`:8000`) and **Docling** (`:5001`) are disabled in `main.yml`.

</details>

<details>
<summary><b>🔒 Infrastructure & Security</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **cloudflared** | none | Outbound Cloudflare tunnel that publishes selected apps on `*.fantaquoggio.bid` |
| **gluetun** | `:8585` (qBittorrent WebUI) | WireGuard tunnel to Proton VPN for qBittorrent, with a kill switch and automatic port forwarding, described in [`docs/vpn.md`](docs/vpn.md) |
| **Vaultwarden** | `:8222→80` | Password and secret store compatible with Bitwarden. It is published through the Cloudflare tunnel, which terminates HTTPS, because the web vault needs a secure context and does not work on the plain `:8222` URL. Registration is closed, and new accounts are invited from `/admin` |
| **vaultwarden-backup** | none | Nightly `sqlite3 .backup` snapshot of the vault into `vaultwarden/backups`, kept for 14 days |

</details>

<details>
<summary><b>🧰 Ops / Utilities</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **WUD** | `:3004→3000` | What's Up Docker, an image-update dashboard that only notifies through Telegram |
| **Beszel** | `:8090` | Server and container monitoring hub |
| **beszel-agent** | none (host network) | Collects host, container and S.M.A.R.T. metrics for Beszel. It runs on the host network and mounts the Docker socket directly |
| **socket-proxy** | none | Read-only Docker API gateway for Homepage and WUD, on the internal `docker-api` network |
| **Zerobyte** | `:4096` | Backup management |
| **GHCR login** | none | Helper that authenticates image pulls from GitHub Container Registry |

</details>

---

## 🗄️ Data layer

Databases and caches run as containers like every other service. Smaller apps share the general Postgres, while the larger ones run their own
instance.

### PostgreSQL

| Instance | Image | Used by |
|----------|-------|---------|
| **postgres** (no published port) | `postgres:17` | Spesatracker |
| **immich-postgres** | `immich-app/postgres` (vectorchord) | Immich |
| **karutuogg-postgres** | `postgres:17` | Karutuogg |
| **fantaquoggio-postgres** (`:5432`, Tailscale address only) | `postgres:17` | FantaQuoggio, with the app database `fantaquoggio` and the Airflow metadata database `airflow`, each written by its own role |

### Redis / Valkey

| Instance | Image | Used by |
|----------|-------|---------|
| **immich-redis** | `valkey/valkey` | Immich |

### Backups

Each Postgres instance has a `*-db-backup` sidecar (`prodrigestivill/postgres-backup-local`) that writes daily dumps. **db-backup** covers
postgres, **immich-db-backup** covers immich-postgres and **karutuogg-db-backup** covers karutuogg-postgres. **fantaquoggio-db-backup** dumps
both FantaQuoggio databases but leaves out the dbt schemas `staging`, `intermediate` and `marts`, since a `dbt_build` recreates them.

Vaultwarden keeps its vault in SQLite, and a file copy of a live SQLite database can capture a half-written state. **vaultwarden-backup**
therefore writes `sqlite3 .backup` snapshots into `vaultwarden/backups`, together with attachments, sends, `config.json` and the RSA keys.

**Zerobyte** mounts every service's config or data directory and the dump directories under `/containers/…`, and ships them with restic to S3. A
volume added in `zerobyte.yml` only becomes visible to Zerobyte, because the backup plan itself is configured in the Zerobyte UI. Photos
(`/mnt/das/immich`) and media stay out of the backup because of their size, although the DAS is a single disk without redundancy and a disk
failure would lose them.

---

## 🚀 Deployment

A deployment goes through three stages:

```text
1️⃣ Service Definition
   ↓ Each service defined in roles/containers/tasks/<service>.yml
   
2️⃣ Template Rendering  
   ↓ setup.yml creates bind-mount directories and dumps the services into compose.yml
   
3️⃣ Deployment
   ↓ docker compose up -d recreates only what changed and removes orphans
```

### Key Files

- `roles/containers/templates/compose.yml.j2`: the Docker Compose template, which dumps each service dict as it is.
- `roles/containers/tasks/setup.yml`: collects all services, creates the bind-mount directories and renders the Compose file.
- `roles/containers/tasks/run.yml`: deploys the stack.
- `roles/containers/tasks/<service>.yml`: one service definition each.

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

Each service takes its configuration from the environment variables and volume mounts in its Ansible task.

### Default Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Timezone** | `Europe/Rome` | Used by most services |
| **User/Group** | `PUID=1000`, `PGID=1000` | User and group the services run as |
| **Media Storage** | `/mnt/das/` | Shared media directory on the TerraMaster D4-320 DAS (`media_dir` variable) |
| **Service Data** | `./service-name/` | Per-service data directories |
| **LLM API** | `http://bestione:8000/v1` | OpenAI-compatible endpoint used by Spesatracker |
