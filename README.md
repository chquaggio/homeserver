# HomeServer

This repository holds the Ansible playbook that provisions one home server and deploys the services that run on it. Every service is a Docker container, and Ansible generates a single Docker Compose file for all of them from one task file per service.

The server hosts a media stack built around Jellyfin and the *arr applications, together with personal apps for finance, notes, recipes, photos and passwords. Devices reach it over Tailscale or the home LAN, while a few apps are published on the internet through an outbound Cloudflare tunnel, so that the router forwards no port.

The repository exists so that the state of the server can be read from files and reproduced with one command. A service is added, changed or removed by editing its task file and running the playbook, which recreates only the containers whose definition changed.

## Usage

The playbook runs from a control machine that reaches the server over SSH as `quoggioserver`. It needs the collections listed in `requirements.yml`, the encrypted secrets in `group_vars/all/vault.yml` and the vault password in `.vault_pass`. Git ignores both files because the repository is public, which means that they exist only on the control machine and have to be copied to any new one by hand.

```bash
ansible-galaxy collection install -r requirements.yml

# Configure the host and deploy every container
ansible-playbook site.yml

# Deploy the containers only
ansible-playbook site.yml --tags containers

# Deploy some services, given as comma-separated Compose service names
ansible-playbook site.yml --tags containers -e compose_services=vibravid,sonarr

# Show the compose.yml diff and the containers that a run would recreate
ansible-playbook site.yml --tags containers --check --diff

# Apply the firewall rules only
ansible-playbook site.yml --tags firewall

# Upgrade the apt packages, and reboot the server if the upgrade requires it
ansible-playbook upgrade.yml
```

`site.yml` installs missing packages without upgrading the installed ones, so that a deploy does not restart the server. Upgrades and the reboot that a new kernel requires are confined to `upgrade.yml`, which is run on purpose.

Before a commit, the following checks have to pass, and CI runs the same linters on every push to `main`.

```bash
yamllint . && ansible-lint && ansible-playbook --syntax-check site.yml upgrade.yml && python3 scripts/check_docs.py && python3 scripts/check_vault_keys.py
```

`scripts/check_docs.py` fails when a Compose service or network is mentioned neither in this README nor in the diagram, which keeps the tables below aligned with the task files. `scripts/check_vault_keys.py` fails when `group_vars` references a key that the vault lacks, and since it decrypts the vault it runs on the control machine only.

## Host

The server is a Beelink mini PC with 4 cores and 15 GB of RAM that runs Ubuntu 24.04, and its Intel GPU handles Jellyfin's hardware transcoding through Quick Sync. Containers keep their configuration on the internal disk under `/opt/docker/compose`, whereas media and photos live on an external enclosure described under [Storage](#storage).

`site.yml` applies four roles in order.

| Role | What it configures |
|---|---|
| `common` | Base packages, Node, Homebrew and the dotfiles from `chquaggio/dotfiles`, whose restore script runs only when the clone brings in new commits, followed by the UFW rules and an sshd configuration that refuses root logins |
| `docker` | Docker Engine and the Compose plugin from Docker's apt repository, and the membership of the user in the `docker` group |
| `system` | The fstab entry that mounts the enclosure at `/mnt/das`, with a check that fails the run if the path is not a mountpoint afterwards, and Neovim |
| `containers` | The Compose file and the containers, as described under [How the stack is rendered](#how-the-stack-is-rendered) |

Part of the setup lives outside the repository, and a rebuild has to repeat it by hand, as listed under [Rebuilding the server](#rebuilding-the-server).

## Services

Each service is defined in `roles/containers/tasks/<service>.yml`. Where the host port differs from the container port, the tables show both as `host→container`. A published port answers on the LAN and on the tailnet, unless the table says that it is bound to the Tailscale address.

### Media

| Service | Port | Description |
|---|---|---|
| **Jellyfin** | `:8096` | Media server for movies and TV shows |
| **Seerr** | `:5055` | Media request management |
| **Sonarr** | `:8989` | TV show automation |
| **Radarr** | `:7878` | Movie automation |
| **Prowlarr** | `:9696` | Indexer management for Sonarr and Radarr |
| **Bazarr** | `:6767` | Subtitle management |
| **qBittorrent** | `:8585`, published by gluetun | Torrent client. It shares gluetun's network namespace, so that its only route to the internet is the Proton VPN tunnel, and other containers reach it as `qbittorrent:8585` through gluetun's alias on `qnet` |
| **gluetun** | `:8585` | WireGuard tunnel to Proton VPN for qBittorrent, with a kill switch and automatic port forwarding, described in [`docs/vpn.md`](docs/vpn.md) |
| **FlareSolverr** | `:8191` | Proxy that solves Cloudflare challenges for Prowlarr |
| **VibraVid** | `:8001→8000` | Streaming-site downloader that Sonarr and Radarr poll as a download client |
| **Calibre-Web Automated** | `:8083` | Ebook library and OPDS feed for KOReader |

### Personal apps

| Service | Port | Description |
|---|---|---|
| **Homepage** | `:3000` | Dashboard with a tile for every service |
| **Immich** | `:2283` | Photo and video library, which runs as `immich-server` with `immich-machine-learning` for face recognition and smart search |
| **Actual Budget** | `:5006` | Personal finance, in the container `actualbudget` |
| **Trilium** | `:5050→8080` | Notes |
| **Mealie** | `:9925→9000` | Recipes |
| **Vaultwarden** | `:8222→80` | Password store compatible with the Bitwarden clients. The web vault needs HTTPS, which the Cloudflare tunnel provides, so the plain `:8222` URL does not work in a browser. Registration is closed, and new accounts are invited from `/admin` |
| **Spesatracker** | `:8400` | Grocery receipt and expense tracker. It parses receipts with an LLM served by the home PC (`bestione:8000`), so that receipt data stays inside the house |
| **Karutuogg** | `:8410→8000` | Discord card-game bot with a companion web app, split into `karutuogg-web` and `karutuogg-bot` |
| **MyMCP** | `:7000` | Personal MCP (Model Context Protocol) server |
| **FantaQuoggio** | none | Fantacalcio auction copilot and lineup advisor, described under [FantaQuoggio](#fantaquoggio) |

### Infrastructure

| Service | Port | Description |
|---|---|---|
| **cloudflared** | none | Outbound Cloudflare tunnel that publishes selected apps on `*.fantaquoggio.bid` |
| **socket-proxy** | none | Read-only gateway to the Docker API for Homepage and WUD, on the internal `docker-api` network |
| **WUD** | `:3004→3000` | What's Up Docker, which watches the image tags and announces new versions on Telegram without updating anything |
| **Beszel** | `:8090` | Monitoring hub for the server and its containers |
| **beszel-agent** | none (host network) | Collector of host, container and S.M.A.R.T. metrics for Beszel. It runs on the host network and mounts the Docker socket directly, because metrics read through a proxy or a bridge network would be incomplete |
| **Zerobyte** | `:4096` | Scheduler and web UI for the restic backups to S3 |
| **vaultwarden-backup** | none | Nightly `sqlite3 .backup` snapshot of the vault |

Image pulls from the GitHub Container Registry are authenticated by `ghcr_login.yml`, which is a login task and defines no container.

### Databases

Databases and caches run as containers on networks that only their own app can reach. Small apps share the general Postgres, whereas the larger ones run their own instance, and every instance has a sidecar that dumps it once a day.

| Instance | Image | Used by | Dump sidecar |
|---|---|---|---|
| **postgres** | `postgres:17` | Spesatracker | **db-backup** |
| **immich-postgres** | `immich-app/postgres` (vectorchord) | Immich | **immich-db-backup** |
| **immich-redis** | `valkey/valkey` | Immich, as a cache | none |
| **karutuogg-postgres** | `postgres:17` | Karutuogg | **karutuogg-db-backup** |
| **fantaquoggio-postgres** | `postgres:17` | FantaQuoggio, with the app database `fantaquoggio` and the Airflow metadata database `airflow` | **fantaquoggio-db-backup** |

The shared Postgres publishes no port, so it is queried with `docker exec postgres psql …`. Only `fantaquoggio-postgres` publishes one, `5432` bound to the Tailscale address, because the valuation model runs on another machine of the tailnet and reads the database directly.

### FantaQuoggio

The API and the single-page app ship in one image, `fantaquoggio`, which publishes no port on the host and is reachable only through the tunnel at `app.fantaquoggio.bid`. Its Airflow 3 pipeline runs in three containers from a second image, namely `fantaquoggio-airflow-apiserver` (whose UI is on `:8420→8080`, bound to the Tailscale address), `fantaquoggio-airflow-scheduler` and `fantaquoggio-airflow-dag-processor`.

Two one-shot containers run before the others on every deploy. `fantaquoggio-db-init`, from the app image, creates the databases and the role and applies the app migrations, after which `fantaquoggio-airflow-init`, from the Airflow image, migrates the Airflow metadata. Both images are pinned to the variable `fantaquoggio_version` in `group_vars/all/services.yml`, so that a deploy consists of changing that variable and running the playbook.

The provider files, which are the SofaSport response cache and the fantacalcio.it spreadsheets, live in `fantaquoggio/data/raw/<provider>/`, and the trained model artifacts in `fantaquoggio/data/models/mister/`. Since both can be fetched or trained again, neither directory is backed up.

## Networking

The editable diagram is [`docs/architecture.drawio`](docs/architecture.drawio), which opens in [app.diagrams.net](https://app.diagrams.net) or in the Draw.io extension of VS Code. It draws the entry paths, the Docker networks, the VPN path that only qBittorrent uses and the containers that hold the Docker socket.

### Entry paths

The server belongs to a private Tailscale tailnet, in which MagicDNS resolves its name `quoggioserver`, and every remote device reaches it that way. UFW admits traffic to host services from the tailnet and from the LAN only. Docker, however, inserts its own iptables rules ahead of UFW, with the consequence that a published container port bypasses the firewall, and a service that must stay internal therefore declares no `ports:` at all. A port that the tailnet must reach while the LAN must not is bound to the Tailscale address through the variable `tailscale_ip`, as the FantaQuoggio database and the Airflow UI are.

`cloudflared` keeps an outbound connection to Cloudflare and publishes a few apps on `*.fantaquoggio.bid`. Some of those hostnames sit behind Cloudflare Access with an email one-time code, while the others rely on the login of the app. The routes and their policies are configured in the Cloudflare dashboard, and the list of published apps is kept in `docs/private/exposure.md`, which git ignores.

qBittorrent runs inside the network namespace of `gluetun`, which keeps a WireGuard tunnel to Proton VPN open, so that torrent traffic leaves through the tunnel and stops when the tunnel drops. Proton forwards one peer port into the tunnel, which is why the router has no forwarding rule for qBittorrent. Every other container keeps using the home connection, as `cloudflared` and Tailscale do. Setup, verification and troubleshooting are in [`docs/vpn.md`](docs/vpn.md).

### Docker networks

Apps talk to each other on the shared network `qnet`. Databases and caches join only a network marked `internal: true`, which has no route to the outside and admits no published port, so that an app reaches the database it owns and no other. An app container that needs both joins both networks.

| Network | Internal | Members |
|---|---|---|
| `qnet` | no | Every app container |
| `db-shared` | yes | `postgres`, `db-backup`, Spesatracker |
| `immich` | yes | `immich-postgres`, `immich-redis`, `immich-db-backup`, the two Immich app containers |
| `karutuogg` | yes | `karutuogg-postgres`, `karutuogg-db-backup`, the two Karutuogg app containers |
| `fantaquoggio` | yes | `fantaquoggio-postgres`, `fantaquoggio-db-backup`, the two one-shot containers, the app and the Airflow containers |
| `docker-api` | yes | `socket-proxy`, Homepage, WUD |

## Storage

A TerraMaster D4-320 enclosure, attached over USB, exposes one 12 TB ext4 disk labelled `das-01`, which fstab mounts at `/mnt/das`. The Ansible variable `media_dir` points to that path, and Jellyfin, the *arr applications, qBittorrent, VibraVid, Calibre-Web Automated and Immich bind-mount their data from it. The enclosure holds a single disk without redundancy, so a failure of that disk loses whatever is stored only there.

Beszel-agent receives the block device of the enclosure in order to read its S.M.A.R.T. data, and mounts `/mnt/das` read-only at `/extra-filesystems/das-01` in order to report its capacity.

Calibre-Web Automated owns two directories on the enclosure. `calibre-library/` holds the Calibre library with its `metadata.db`, and the app rearranges everything it imports into its own layout by author and title. `cwa-book-ingest/` is the drop zone, from which the app deletes each file after importing it, and for that reason the drop zone must not point at `books/` or at any other library directory. An ebook copied into the drop zone appears in the library within a minute.

## Backups

Backups happen in two stages, of which only the second leaves the server.

In the first stage, sidecar containers write consistent snapshots of the databases to the internal disk, because a file copy of a running database can capture a half-written state. Each Postgres sidecar (`prodrigestivill/postgres-backup-local`) runs `pg_dump` every night and keeps 14 daily, 8 weekly and 12 monthly dumps in a `db-backups` directory. The FantaQuoggio sidecar leaves out the dbt schemas `staging`, `intermediate` and `marts`, since a `dbt_build` recreates them. Vaultwarden stores its vault in SQLite, so **vaultwarden-backup** takes a `sqlite3 .backup` snapshot every night at 04:00 and keeps 14 of them in `vaultwarden/backups`, together with the attachments, the sends, `config.json` and the RSA keys.

In the second stage, Zerobyte copies directories to an S3 bucket with restic. `zerobyte.yml` mounts the candidate directories into the Zerobyte container under `/containers/…`, while the backup plan, which decides which of them are copied and when, is configured in the Zerobyte UI and is not part of this repository. Mounting a new directory therefore makes it selectable in the UI without adding it to the backup.

The plan runs every Sunday at 04:00 and keeps the last 3 snapshots. It covers the configuration directories of Actual Budget, Jellyfin, Seerr, Mealie, Trilium, Sonarr, Radarr, Prowlarr, Bazarr and qBittorrent, and it is limited to them so that the repository in the bucket stays within a few gigabytes.

| Data | Local snapshot | Copied to S3 |
|---|---|---|
| Configuration of the ten apps listed above | none | weekly |
| Postgres databases, Immich's included | daily dump | no |
| Vaultwarden vault | daily snapshot | no |
| Photos (`/mnt/das/immich`) and media | none | no |
| Configuration of the remaining apps | none | no |

The database dumps and the photos are left out of the plan to keep the bucket free of charge. As a consequence, the dumps protect against a damaged database or a mistaken deletion, but not against the loss of the internal disk, and the photos have no second copy.

### Restoring

A directory copied to S3 is restored from the Zerobyte UI, which lists the snapshots and writes the chosen one back to its original path. The container that owns the directory should be stopped during the restore and started again afterwards.

A Postgres dump is replayed into its instance with `psql`. The dumps are taken with `--clean --if-exists`, so they drop and recreate the objects they contain and can be replayed over an existing database. The command for the shared instance is the following, and the other instances differ in the container name, the user and the directory.

```bash
cd /opt/docker/compose
gunzip -c db-backups/last/<database>-latest.sql.gz | docker exec -i postgres psql -U <user> -d <database>
```

A Vaultwarden snapshot is a `tar.xz` archive of the data directory. To restore it, stop the `vaultwarden` container, extract the archive over `vaultwarden/data`, and start the container again.

### Rebuilding the server

A rebuild on a new machine repeats by hand the steps that the repository does not cover, in this order.

1. Install Ubuntu, create the user `quoghs` with the SSH key of the control machine, then install Tailscale and log in, so that the machine answers as `quoggioserver`.
2. Run `ansible-playbook site.yml` from a control machine that holds `vault.yml` and `.vault_pass`. The Proton VPN WireGuard key, the tunnel token of `cloudflared` and the other credentials reach the server through the vault.
3. Leave the Cloudflare dashboard as it is, because the tunnel routes and the Access policies are stored there and apply again as soon as `cloudflared` connects with the same token.
4. Open the Zerobyte UI, connect the existing S3 repository with its restic password, restore the directories and recreate the backup plan. The restic password is generated by Zerobyte on the old server, so a copy has to exist somewhere else before that server is lost.
5. Replay the database dumps and the Vaultwarden snapshot, if the internal disk of the old server can still be read.

## How the stack is rendered

The `containers` role builds the stack in five steps.

1. Each service task sets a fact whose name ends in `_service` and whose value is a plain Compose service definition with an additional `name` key.
2. `setup.yml` collects every fact with that suffix into one `services` list, so that a new task file needs no registration beyond its import in `main.yml`.
3. `setup.yml` creates every host directory that the services bind-mount, because Docker would otherwise create the missing ones as root and break the containers that run as an unprivileged user.
4. `compose.yml.j2` writes each service dictionary to `compose.yml` as YAML without filtering its keys, so that any key Compose accepts can be used in a task file. The networks are declared in the same template.
5. `run.yml` calls `docker compose up` through `community.docker.docker_compose_v2`, which pulls the images, recreates the containers whose definition changed and removes those that are no longer defined.

Shared values such as the timezone (`Europe/Rome`), the user and group that containers run as (`1000`), the Compose directory and `media_dir` are defined in `group_vars/all/infrastructure.yml`. `group_vars/all/services.yml` maps each service setting to the vault key that holds its secret. Task files and templates take the name of the server from `inventory_hostname` and the published domain from `public_domain`, so that each is written once. The vault also holds the Tailscale address and the LAN subnet, which are not secrets but stay out of a public repository.

The `add-service` skill in `.claude/skills/` walks through the addition of a service, and `CLAUDE.md` lists which parts of this README and of the diagram a change has to update.
