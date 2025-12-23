# HomeServer (Ansible)

This repository contains Ansible playbooks and roles used to provision and operate my personal home server. Most applications run as Docker containers via a single Docker Compose file rendered from Ansible.

The core idea is:

- each container/service is defined as an Ansible task that sets a `*_service` fact (image, ports, volumes, env, networks)
- all services are combined into a `services` list
- `roles/containers/templates/compose.yml.j2` iterates that list to render `compose.yml`
- Ansible then runs `docker compose up`

## Architecture overview

### Networking model

- The homeserver is part of a **Tailscale tailnet**.
- **Pi-hole** is used as the **DNS server** for the network (effectively acting like “MagicDNS” for my internal naming).
- My home PC is on the same tailnet; **OpenWebUI** can call an LLM API hosted on the home PC (`http://bestione:8000/v1`), so the two machines must be able to reach each other over Tailscale.
- Containers are attached to a shared Docker network: `proxy-network`.
- Some services are exposed directly via host ports.
- There is also an **Nginx Proxy Manager** container present in the compose template; I *may not be using it anymore* (Pi-hole is the important piece for DNS and name-based access).

### High-level schema

```mermaid
flowchart LR
  subgraph Tailnet[Tailscale Tailnet]
    PC[Home PC\n(bestione)\nLLM API :8000]
    HS[Homeserver\nDocker host]
  end

  Client[Client devices\n(laptop/phone/desktop)] -->|Tailscale| Tailnet

  HS -->|DNS queries| PH[Pi-hole\nDNS + local records]
  PH -->|resolves service names| HS

  subgraph HS_DOCKER[Homeserver: Docker Compose]
    NET[Docker network: proxy-network]
    HP[homepage :3000]
    OW[openwebui :3333->8080]
    JF[jellyfin :8096]
    JS[jellyseerr :5055]
    SR[sonarr :8989]
    RR[radarr :7878]
    PR[prowlarr :9696]
    BZ[bazarr :6767]
    QB[qbittorrent :8585 + 6881]
    AB[audiobookshelf :13378->80]
    AC[actualbudget :5006]
    TR[trilium :5050->8080]
    VK[vikunja :3456]
    ML[mealie :9925->9000]
    MCP[mymcp :7000]
    NPM[nginx-proxy-manager :80/:443/:81]
  end

  NET --- HP & OW & JF & JS & SR & RR & PR & BZ & QB & AB & AC & TR & VK & ML & MCP & NPM

  OW -->|HTTP over Tailscale| PC
