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

The home server runs a comprehensive media management and personal productivity stack, with all services containerized and orchestrated through Docker Compose. The server integrates with Tailscale for secure networking and uses Pi-hole for DNS management and local service resolution.

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎬 Media Hub
Complete *arr stack with Jellyfin, automated downloads, and subtitle management

### 🤖 AI-Powered
OpenWebUI and Mealie integrated with self-hosted LLM API

### 🔒 Secure Access
Tailscale VPN for encrypted remote access

</td>
<td width="50%">

### 📊 Self-Hosted Apps
Finance tracking, task management, notes, and recipes

### 🐳 Infrastructure as Code
Fully automated deployment with Ansible + Docker Compose

### 🌐 Smart DNS
Pi-hole for ad-blocking and local service resolution

</td>
</tr>
</table>

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         🌐 Tailscale Network                        │
│                                                                      │
│  ┌─────────────────┐               ┌──────────────────────────────┐  │
│  │   Home PC       │               │      Home Server             │  │
│  │  (bestione)     │◄────────────► │   (quoggioserver)            │  │
│  │  LLM API :8000  │   Secure      │                              │  │
│  └─────────────────┘   Network     │  ┌────────────────────────┐  │  │
│                                    │  │   Pi-hole DNS :53      │  │  │
│                                    │  │   Web UI :8053         │  │  │
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

- **Tailscale**: The server is part of a private Tailscale tailnet for secure remote access
- **Pi-hole**: Acts as the primary DNS server and provides local hostname resolution (replacing MagicDNS)
- **Docker Network**: All containers communicate through a shared `qnet`
- **Cross-machine Communication**: OpenWebUI can communicate with a self-hosted LLM API running on my home PC (`bestione:8000`)

### Storage

- **TerraMaster D4-320 DAS**: USB-attached enclosure exposing a 12TB ext4 disk (label `das-01`) mounted at `/mnt/das` via fstab
- **Media path**: Centralized under the `media_dir` ansible variable (default `/mnt/das`); all media services (Jellyfin, *arr stack, qBittorrent, Audiobookshelf) bind-mount from here
- **Health monitoring**: Beszel-agent passes the DAS block device through for S.M.A.R.T. and mounts `/mnt/das` read-only at `/extra-filesystems/das-01` for capacity reporting

### Infrastructure

The setup uses Ansible to:

1. Define each service as an Ansible task that sets a `*_service` fact (image, ports, volumes, environment, networks)
2. Combine all service definitions into a unified `services` list
3. Render a Docker Compose file from the `compose.yml.j2` template
4. Deploy everything with `docker compose up`

---

## 📦 Services

<details>
<summary><b>🏠 Dashboard & Management</b></summary>

- **Homepage** (`:3000`) - Service dashboard and homepage

</details>

<details open>
<summary><b>🎬 Media Management Stack</b></summary>

| Service | Port | Description |
|---------|------|-------------|
| **Jellyfin** | `:8096` | Media server for movies and TV shows |
| **Jellyseerr** | `:5055` | Media request management |
| **Sonarr** | `:8989` | TV show management and automation |
| **Radarr** | `:7878` | Movie management and automation |
| **Prowlarr** | `:9696` | Indexer management for *arr stack |
| **Bazarr** | `:6767` | Subtitle management |
| **qBittorrent** | `:8585`, `:6881` | Torrent client |
| **Audiobookshelf** | `:13378→80` | Audiobook and podcast server |

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
| **Vikunja** | `:3456` | Task and project management |
| **Mealie** | `:9925→9000` | Recipe management with AI integration |

</details>

<details>
<summary><b>🔧 Infrastructure Services</b></summary>

- **Pi-hole** (`:53` DNS, `:8053` Web UI) - Network-wide ad blocking and DNS server
- **cloudflared** - DNS-over-HTTPS / Cloudflare tunnel helper

</details>

<details>
<summary><b>🧰 Ops / Utilities</b></summary>

- **GHCR login** - Auth helper for pulling images from GitHub Container Registry
- **WUD** (`:3004`) - What's Up Docker: image-update dashboard with per-image changelog links, notify-only via Telegram
- **Beszel** - Utility container (see `roles/containers/tasks/beszel.yml`)
- **Docling** - Utility container (see `roles/containers/tasks/docling.yml`)
- **Zerobyte** - Utility container (see `roles/containers/tasks/zerobyte.yml`)

</details>

---

## 🚀 Deployment

The deployment follows this workflow:

```
1️⃣ Service Definition
   ↓ Each service defined in roles/containers/tasks/<service>.yml
   
2️⃣ Template Rendering  
   ↓ compose.yml.j2 combines all services
   
3️⃣ Deployment
   ↓ docker compose up -d deploys the stack
```

### Key Files

- `roles/containers/templates/compose.yml.j2` - Docker Compose template
- `roles/containers/tasks/setup.yml` - Combines all services and renders compose file
- `roles/containers/tasks/run.yml` - Deploys the stack
- `roles/containers/tasks/<service>.yml` - Individual service definitions

### Running the Deployment

```bash
# Deploy the entire stack
ansible-playbook site.yml

# Or run specific roles
ansible-playbook site.yml --tags containers
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
