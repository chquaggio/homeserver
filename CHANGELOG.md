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
