## [2026-06-16 22:40] Push Summary

### Conversation Context
The user asked to review and apply the handoff doc in `docs/` (`architecture-review-2026-06.md`) — a prioritized list of homeserver concerns raised during a separate mymcp session — and to surface any additional findings. Investigating the repo against the doc turned up two gaps the doc itself didn't list: Immich was entirely absent from Zerobyte's backup set (neither its Postgres nor the photo library was captured, and Zerobyte has no `/mnt/das` mount so it couldn't reach the library at all), and the shared-Postgres backup used a mismatched path (`./postgres-data` hyphen vs the real `./postgres_data` underscore), meaning the shared DB was never backed up. After clarifying scope with the user, we applied backups (#1/#2), image-update visibility (#5), and documented alerting (#6). Key decisions: the user confirmed the Google Cloud photo copy still exists, so a restore drill remains safe to do before deleting it; photo *files* are deliberately left out of S3 for now (DB dumps only — GCloud stays the photo copy) to avoid a large/expensive upload; image pinning is deferred to incremental work with Watchtower in notify-only mode chosen over Renovate (the user accepted that Watchtower reports only image digests, not release notes); and #6 alerting needs no repo change since Beszel already supports SMART/disk/container alerts and the agent is wired for them — only dashboard rules remain. DB backups were implemented as `prodrigestivill/postgres-backup-local` sidecars (majors pinned 17/14 to match each server) writing daily dumps into Zerobyte-backed directories, with the exact Immich vectorchord Postgres tag recorded in-comment for restore compatibility. A follow-up question led to confirming (via Watchtower docs) that its notifications contain no changelogs, and to adding `scripts/dump_image_versions.sh` to capture running image digests on the host ahead of pinning.

### Changes
- `roles/containers/tasks/db.yml`: Added `db-backup` sidecar (`postgres-backup-local:17`) producing daily logical dumps of the shared Postgres into `./db-backups`, plus its backup directory.
- `roles/containers/tasks/immich.yml`: Added `immich-db-backup` sidecar (`postgres-backup-local:14`) dumping the Immich Postgres into `./immich/db-backups`; recorded the exact vectorchord image tag for restore compatibility.
- `roles/containers/tasks/zerobyte.yml`: Replaced the broken `./postgres-data` mount with the two dump directories; added previously-uncaptured app data (audiobookshelf, homepage, wishlist).
- `roles/containers/tasks/watchtower.yml`: New Watchtower service in notify-only mode (`WATCHTOWER_MONITOR_ONLY`), daily check reporting to Telegram via existing vault credentials.
- `roles/containers/tasks/main.yml`: Wired `watchtower.yml` into the import list.
- `scripts/dump_image_versions.sh`: New helper dumping running containers' image, version label, and repo digest to a text file for incremental image pinning.
- `scripts/README.md`: Documented the new script.
- `docs/architecture-review-2026-06.md`: Added an "Applied 2026-06-16" section, ticked completed action items, and annotated the remaining runtime/dashboard steps.

---

## [2026-06-04 19:08] Push Summary

### Conversation Context
The user invoked the `/add-service` skill to add Immich (self-hosted photo/video management) to the homeserver stack, asking that the current documentation be researched online rather than recalled. The official docker-compose.yml for the latest release (v2.7.5) was fetched from the Immich GitHub releases page, which revealed that Immich is a four-container deployment: the server, an optional machine-learning sidecar, a Redis-compatible cache (valkey), and — crucially — a *custom* Postgres image (`ghcr.io/immich-app/postgres:14-vectorchord`) that bundles the vectorchord extension, meaning the stack's existing shared `postgres:17` from `db.yml` cannot be reused and Immich gets a dedicated database container. The user chose to store the photo library on the DAS (`{{ media_dir }}/immich`, consistent with the Jellyfin media layout) while keeping postgres data and the ML model cache on local disk, to include the ML container in CPU mode (face recognition + smart search, no hardware acceleration), to vault the DB password, and to add a homepage tile under the Media group. Two template gaps surfaced along the way: `compose.yml.j2` did not support `shm_size` (Immich's postgres wants 128mb vs Docker's 64MB default), so support was added; and named volumes aren't supported, so the ML model cache uses a bind mount instead. The homepage widget block is committed commented-out with the Jinja reference escaped (`{{ '{{ immich_key }}' }}`) because even YAML comments get templated and `immich_key` doesn't exist until the user generates an API key after first login — uncommenting requires both vaulting `IMMICH_KEY` and un-escaping the reference. No icon file was needed: homepage resolves `immich.png` from the dashboard-icons CDN like every other tile in this repo. The vault secret was added non-interactively (generated 32-char alphanumeric password, per Immich's character restriction) via a scripted `EDITOR` with `ansible-vault edit`, and the stack was deployed with `ansible-playbook -t containers site.yml`. A known pre-existing gap was noted but not fixed: `compose.yml.j2` silently drops `healthcheck` keys (affects `db.yml` too).

### Changes
- `roles/containers/tasks/immich.yml`: New. Four service facts — `immich-server` (port 2283, photos on `{{ media_dir }}/immich`, depends on redis+postgres), `immich-machine-learning` (CPU, bind-mounted model cache), `immich-redis` (valkey:9), `immich-postgres` (Immich's vectorchord image, dedicated DB, `shm_size: 128mb`) — plus directory setup for the upload and model-cache dirs.
- `roles/containers/tasks/main.yml`: Added `import_tasks: immich.yml` in alphabetical order.
- `group_vars/all/services.yml`: Added `immich_db_password` reference to the vaulted `IMMICH_DB_PASSWORD`.
- `roles/containers/templates/compose.yml.j2`: Added optional `shm_size` rendering for services that define it.
- `roles/containers/templates/services.yaml.j2`: Added Immich tile to the Media group; widget block commented out until an API key exists.
- `.gitignore`: Added `.claude/settings.local.json` (machine-local Claude Code permissions).
- `.claude/skills/add-service/SKILL.md`: New. Project skill documenting the end-to-end workflow for adding a containerized service to this ansible stack.

---

## [2026-05-19 16:27] Push Summary

### Conversation Context
After landing the DAS refactor, the user asked for a broader assessment of the repository and its structure. I produced a prioritized list of suggestions across security, structural, and hygiene categories; the user chose seven items to fix (TZ/PUID/PGID extraction, containers-role DRY, group_vars split, lint CI, host-key-checking, scripts README) plus the security item (beszel KEY/TOKEN leaking in plaintext), explicitly skipped the dead-code cleanup because the disabled services may be reactivated, and confirmed that the DAS should not be added to the inventory — it has no OS to connect to, so it is correctly modeled as block storage attached to `quoggioserver`. Two design choices needed clarification: for the containers-role DRY refactor we picked auto-discovery via `query('varnames', '_service$')` over per-file appending because it avoids touching every task file and lets disabled services automatically drop out of the rendered compose; for the `group_vars/all/` split we picked a three-way infrastructure / services / system layout over a binary infra/secrets split because it keeps host-level wiring separate from per-service refs and from user-environment knobs. For host key checking we replaced the blanket `False` with `StrictHostKeyChecking=accept-new` plus `ControlMaster=auto` — preserves trust-on-first-use convenience while restoring tamper detection after the initial connect, and adds connection reuse for speed. The user pre-created the `BA_KEY` and `BA_TOKEN` vault variables; the literal beszel hub token is now removed from source but remains in git history, so it must be rotated in the Beszel hub UI.

### Changes
- `group_vars/all/vars.yml`: Deleted. Contents redistributed across three new files.
- `group_vars/all/infrastructure.yml`: New file. Host/user identity, container runtime defaults (new `tz`, `puid`, `pgid`), docker layout, DAS storage vars, container registry and Cloudflare token.
- `group_vars/all/services.yml`: New file. All `*_key` / `*_password` / `*_token` / `*_user` service-level secret references, including new `ba_key` and `ba_token` for beszel-agent.
- `group_vars/all/system.yml`: New file. Shell, dotfiles repo, and extra packages list.
- `roles/containers/tasks/beszel.yml`: Replaced hardcoded `KEY=ssh-ed25519 ...` and `TOKEN=0d90d715-...` literals with `{{ ba_key }}` / `{{ ba_token }}`. **The old token value is in git history and must be rotated in Beszel hub.**
- `roles/containers/tasks/setup.yml`: Replaced manual 23-entry services list with `query('varnames', '_service$') | map('extract', vars) | list`. Adding a service now only requires creating a task file and importing it in `main.yml`.
- `roles/containers/tasks/{audiobookshelf,bazarr,mealie,openwebui,prowlarr,qbittorrent,radarr,sonarr,spesatracker,zerobyte}.yml`: `PUID=1000` / `PGID=1000` / `TZ=Europe/Rome` (and the inconsistent `TZ=Europe/Amsterdam` in audiobookshelf) replaced with `{{ puid }}` / `{{ pgid }}` / `{{ tz }}`.
- `ansible.cfg`: Removed `host_key_checking = False`. Added `[ssh_connection]` section with `StrictHostKeyChecking=accept-new` and `ControlMaster=auto` for trust-on-first-use plus SSH connection reuse.
- `.yamllint`: New file. Permissive yaml linting config (200-char line limit, document-start disabled, files-folder ignored).
- `.ansible-lint`: New file. Basic profile, excludes container files dir and scripts dir.
- `.github/workflows/lint.yml`: New file. CI workflow running `yamllint` and `ansible-lint` on push to main and on PRs.
- `scripts/README.md`: New file. One-row-per-script table documenting purpose and whether an ansible-managed equivalent exists.

---

## [2026-05-19 13:35] Push Summary

### Conversation Context
User bought a TerraMaster D4-320 DAS with a 12TB ext4 disk (label `das-01`, mounted at `/mnt/das`) and asked for a refactor of the ansible setup to reflect the new storage. Through clarifying questions we established that the DAS already contains the existing media library mirroring the current `/media/{Shows,Movies,downloads,books,pdfs}` layout, so this is a pointer change rather than a data migration. We chose to introduce a single `media_dir` variable (defaulting to `/mnt/das`) rather than hardcoding the new path or bind-mounting `/mnt/das` onto `/media` on the host — the variable approach keeps future moves to a one-line change and makes intent explicit. We also decided ansible should own the mount itself (fstab entry by `by-label` path, since USB enclosures get unstable `/dev/sdX` ordering) backed by an idempotent `mountpoint` assertion so containers never silently bind-mount into an empty directory. For Jellyfin specifically, both the host source and in-container target were aligned to `{{ media_dir }}` for consistency — user explicitly OK'd the manual library re-add in the Jellyfin UI in exchange for path symmetry. Beszel-agent was extended to pass the DAS block device through for S.M.A.R.T. and to mount the filesystem read-only at `/extra-filesystems/das-01` for capacity reporting. README was updated to add the DAS to the architecture diagram, a new Storage subsection, and the default-settings table.

### Changes
- `group_vars/all/vars.yml`: Added `media_dir`, `das_device` (by-label path), and `das_fstype` variables.
- `requirements.yml`: New file declaring the `ansible.posix` collection dependency (needed for the mount module).
- `roles/system/tasks/storage.yml`: New task file that creates the mountpoint, ensures fstab + active mount via `ansible.posix.mount`, and asserts the path is a real mountpoint before any container runs.
- `roles/system/tasks/main.yml`: Includes `storage.yml` ahead of `neovim.yml` so the DAS is mounted before the containers role runs.
- `roles/containers/tasks/jellyfin.yml`: Bind source and target both updated to `{{ media_dir }}` (requires re-adding library in Jellyfin UI).
- `roles/containers/tasks/sonarr.yml`: `/media/Shows` and `/media/downloads` host paths replaced with `{{ media_dir }}/...`; in-container `/tv`, `/downloads` unchanged.
- `roles/containers/tasks/radarr.yml`: Same treatment for `/media/Movies` and `/media/downloads`.
- `roles/containers/tasks/bazarr.yml`: Same treatment for `/media/Shows` and `/media/Movies`.
- `roles/containers/tasks/qbittorrent.yml`: `/media/downloads` host path now uses `{{ media_dir }}`.
- `roles/containers/tasks/audiobookshelf.yml`: `/media/books` and `/media/pdfs` host paths now use `{{ media_dir }}`.
- `roles/containers/tasks/beszel.yml`: Added DAS block device to beszel-agent `devices` for S.M.A.R.T., and replaced the commented `extra-filesystems` hint with an active read-only mount of `{{ media_dir }}` at `/extra-filesystems/das-01`.
- `README.md`: Added DAS box to the architecture ASCII diagram (with bind-mount arrow), added a new Storage subsection, and updated the Default Settings table to point to `/mnt/das/`.

---
