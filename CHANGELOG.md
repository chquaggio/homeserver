## [2026-07-13 09:58] Push Summary

### Conversation Context
mymcp v0.11.0 adds a Mealie service (four intent-level tools: find_recipe, meal_plan,
import_recipe, save_recipe), and its config requires MEALIE_URL and MEALIE_TOKEN at container
startup — without them the new image fails validation on boot. The vault's existing MEALIE_KEY
is the same valid API token the integration was live-verified with (confirmed against
/api/users/self), so it is reused via the existing `mealie_key` var rather than adding a new
vault entry. The URL points at the qnet container port (http://mealie:9000) — 9925 is only the
host mapping. Takes effect on the next deploy, which will also pull the :latest image containing
the Mealie tools.

### Changes
- `roles/containers/tasks/mymcp.yml`: Added `MEALIE_URL=http://mealie:9000` and `MEALIE_TOKEN={{ mealie_key }}` to the mymcp container environment.

---

## [2026-06-19 14:35] Push Summary

### Conversation Context
After enabling Diun repo-watch, the LinuxServer *arr images flooded notifications with non-release tags (`development-…-beta.9-ls771`, `version-<buildid>`, `1.5.7-development`). The user wanted notifications only for real version releases. Chose `excludeTags` over `includeTags`: a strict semver `includeTags` allowlist would also stop watching the moving tags still in use (`postgres:17`, `valkey:9`, `:latest`/`:release`/`:main`, including the user's own images), whereas `excludeTags` drops only the junk and keeps everything else (clean semver + moving tags) watched. The regex strips pre-releases (alpha/beta/rc/dev/nightly/snapshot), numeric build tags (`version-…`), and `-ls<build>` variants. Verified lint passes; takes effect on next deploy.

### Changes
- `roles/containers/tasks/diun.yml`: Added `DIUN_DEFAULTS_EXCLUDETAGS` regex to suppress pre-release / build-id / LinuxServer `-ls` tag noise from repo-watch.

---

## [2026-06-18 00:36] Push Summary

### Conversation Context
The user pinned ~20 service images from floating tags (`:latest`/`:release`/`:main`) to explicit versions (the #5 controlled-update work), now that Diun repo-watch surfaces newer versions. They also asked to remove `scripts/dump_image_versions.sh` because it didn't work, explicitly instructing not to attempt a fix — so it was deleted (and its row dropped from `scripts/README.md`) rather than repaired. Lint and syntax-check confirmed green before pushing.

### Changes
- `roles/containers/tasks/*.yml`: Pinned images to explicit versions (immich `v2.7.5`, mealie `v3.19.2`, openwebui `v0.9.6`, pihole `2026.06.0`, zerobyte `v0.39.0`, docling `v1.24.0`, the *arr/qbittorrent LinuxServer tags, jellyfin `10.11.11`, beszel `0.18.7`, cloudflared `2026.6.0`, actual `26.6.0`, audiobookshelf `2.35.1`, trilium `v0.103.0`, seerr `v3.3.0`, homepage `v1.13.2`).
- `scripts/dump_image_versions.sh`: Removed (didn't work; deleted per request, not fixed).
- `scripts/README.md`: Dropped the script's row.

---

## [2026-06-17 22:48] Push Summary

### Conversation Context
The user asked to enable Diun's repo-watch so pinned images would surface "a newer version exists" (digest-only watching on a fixed semver tag never changes). Enabled it globally but bounded to avoid the rate-limit/noise the Diun docs warn about: `DIUN_DEFAULTS_WATCHREPO=true`, `DIUN_DEFAULTS_MAXTAGS=10`, `DIUN_DEFAULTS_SORTTAGS=semver` (watch the 10 highest semver tags per repo; `FIRSTCHECKNOTIF=false` keeps initial discovery silent; `includeTags` regex noted as a further tightening). Also answered a version-lookup question: verified empirically that `ghcr.io/immich-app/immich-server:release` and `:v2.7.5` share the same digest, so the package tracks the GitHub release; and demonstrated that enumerating registry tags is unreliable (immich has 2000+ lexically-ordered tags dominated by per-commit sha tags).

### Changes
- `roles/containers/tasks/diun.yml`: Enabled bounded repo-watch (`WATCHREPO`, `MAXTAGS=10`, `SORTTAGS=semver`).

---

## [2026-06-17 22:41] Push Summary

### Conversation Context
After Diun went live, its logs showed `failed=3` every run: the private `ghcr.io/chquaggio/*` images (wishlist, spesatracker, mymcp) returned "unauthorized" because Diun had no GHCR credentials, so they were never checked for updates. (The single bazarr notification and otherwise-silent runs were confirmed correct: first sighting is a silent baseline via `DIUN_WATCH_FIRSTCHECKNOTIF=false`, and Diun notifies only on real digest changes — bazarr's `:latest` digest moved between runs.) Fix: add a `DIUN_REGOPTS` block pointing at `ghcr.io`, reusing the same `ghcr_username`/`ghcr_token` vault vars that `ghcr_login.yml` already uses. Also clarified that Diun watches each container's running tag by digest, so moving tags like `:latest`/`:release` already trigger update notifications without version pinning (pinned tags would need repo-watching to surface new versions). Both linters confirmed passing locally before push.

### Changes
- `roles/containers/tasks/diun.yml`: Added `DIUN_REGOPTS_0` (ghcr.io, selector image) with the GHCR vault credentials so Diun can check the private ghcr.io/chquaggio/* images.

---

## [2026-06-16 23:24] Push Summary

### Conversation Context
After the vault-password CI fix, ansible-lint advanced past the vault error and surfaced the next failure: `syntax-check[unknown-module]` (an unskippable rule) for `community.docker.docker_login` (`roles/containers/tasks/ghcr_login.yml`) and `docker_container` (`roles/docker/tasks/main.yml`). Both modules live only in the `community.docker` collection, which `requirements.yml` did not list — so CI, which installs collections solely from that file, lacked them. It had passed locally because `community.docker` is installed globally. Fix: add `community.docker` (`>=3.0.0`) to `requirements.yml`. Faithful local isolation was hampered by ansible-compat caching its own collection copy (moving the user-path collection aside didn't reproduce the failure), so verification was done at the exact step CI runs: `ansible-galaxy collection install -r requirements.yml` into an empty target installed `community.docker:5.2.1` containing `docker_login` and `docker_container` — the modules CI couldn't resolve.

### Changes
- `requirements.yml`: Added the `community.docker` collection (`>=3.0.0`) so CI installs the `docker_login`/`docker_container` modules the playbooks use.

---

## [2026-06-16 23:16] Push Summary

### Conversation Context
The previous push made `yamllint` and `ansible-lint` pass locally, but CI still failed: ansible-lint's internal `ansible-playbook --syntax-check` aborted with "vault password file not found". Root cause is an environment difference — `ansible.cfg` sets `vault_password_file = ./.vault_pass`, and both that file and the encrypted `group_vars/all/vault.yml` are gitignored, so CI has neither; ansible aborts at startup when the configured password file is absent. It passed locally only because both files exist on disk. Since there is no vaulted content to decrypt in CI, the fix is to give CI a throwaway `.vault_pass`. This was verified by faithfully simulating CI locally (temporarily moving both real files aside, with a guaranteed restore): the failure reproduced exactly (4 internal-errors), and a dummy `.vault_pass` made ansible-lint pass with 0 failures. The real vault files were confirmed intact afterward.

### Changes
- `.github/workflows/lint.yml`: Added a step to write a throwaway `.vault_pass` before the lint steps, so ansible-lint's syntax-check can run in CI (no vaulted files exist there to decrypt).

---

## [2026-06-16 23:12] Push Summary

### Conversation Context
Follow-up to the backups/update-notifier work. First, the user flagged that `containrrr/watchtower` is archived (read-only since 2025-12-17, last release Nov 2023); after confirming via project pages that Diun (`crazy-max/diun`) is actively maintained and purpose-built for notify-only, Watchtower was replaced with Diun (pinned to `4.33.0`, watching all containers via the Docker provider, notifying on Telegram). A maintenance note was also added so future image adoption checks upstream project status. Then the user asked to delete the architecture-review doc and to fix the CI `lint` job, which was failing on `yamllint .` — and explicitly to find a general solution verified locally rather than push-and-retry. `yamllint` was installed locally via pipx to reproduce CI exactly. The errors fell into three mechanical classes (trailing whitespace, blank lines at file start/end) plus a handful of real sequence-indentation inconsistencies (list items indented +4 from their key instead of the repo-standard +2). The mechanical classes were fixed repo-wide with a single normalization sweep (strip trailing whitespace; trim leading/trailing blank lines to a single terminal newline); the indentation cases (mealie, docling, openwebui ports; user.yml loop; brew.yml block) were fixed by hand. Investigating further revealed the same lint job's second step, `ansible-lint`, was also failing (~94 pre-existing violations unrelated to this work, e.g. var-naming/no-role-prefix on the `_service` facts that auto-discovery relies on). The user chose to relax the `.ansible-lint` config (consistent with prior linter relaxations) rather than undertake a large refactor: the noisy structural rules were added to `skip_list`, `tailscale.yml` was excluded (its external role isn't installed in the lint env), and the three trivial `yaml[comments]` issues in `pihole.yml` were fixed directly. Both `yamllint` and `ansible-lint` were confirmed to exit 0 locally before pushing.

### Changes
- `roles/containers/tasks/diun.yml`: New — Diun image-update notifier (notify-only, Telegram), pinned `crazymax/diun:4.33.0`, replacing the archived Watchtower.
- `roles/containers/tasks/watchtower.yml`: Removed (upstream archived).
- `roles/containers/tasks/main.yml`: Swapped the Watchtower import for Diun.
- `.ansible-lint`: Added pre-existing structural rules to `skip_list`; excluded `tailscale.yml`.
- `roles/containers/tasks/{mealie,docling,openwebui}.yml`, `common/tasks/{brew,user}.yml`: Fixed sequence indentation to the repo-standard +2.
- `roles/containers/tasks/pihole.yml`: Fixed comment spacing (`#-` → `# -`).
- Repo-wide: stripped trailing whitespace and trimmed leading/trailing blank lines across task files to satisfy yamllint.
- `docs/architecture-review-2026-06.md`: Removed at the user's request.

---

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
