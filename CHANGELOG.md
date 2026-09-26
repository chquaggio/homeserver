## [2026-09-26 10:51] Push Summary

### Conversation Context
This push carries three commits that never had an entry. The first replaces Infisical with Vaultwarden; it was deployed on 2026-09-04 and committed later on `main`. The second adds FantaQuoggio's deployment on the `fantaquoggio` branch; it was written on 2026-09-14, before the application's own stack existed. The last two bring that branch in line with the stack FantaQuoggio's work item 7 built and ran locally, for the first deploy (FantaQuoggio work item 8).

A survey of the branch against the local `compose.yml` found several mismatches:
- the migration command and the bootstrap DSN did not work with the released image;
- the transfer windows were in a format the app rejects;
- five settings were never rendered;
- the Airflow UI password file was mounted read-only, which SimpleAuthManager cannot open for appending;
- the three Airflow services had no healthchecks;
- the metadata migration ran inside the scheduler, so the api-server and dag-processor could start against an unmigrated schema.

The migration now has its own one-shot, as in Airflow's official compose, which makes eight containers. The UI password is written at the api-server's start. Every non-secret tunable lives in `services.yml`. The dag-processor gets 768m after a 459 MiB local peak against 512m.

A fresh-context review then showed that DAGs unpaused at creation would run their latest tick at once, against an empty warehouse. The stack therefore starts paused, and the first deploy unpauses the DAGs in order after the backfill and the first model training. FantaQuoggio is pinned to the `v0.5.0` images.

### Commits
1. `feat(containers): replace Infisical with Vaultwarden`
   - `roles/containers/tasks/vaultwarden.yml`: added; `infisical.yml`: removed
   - `roles/containers/tasks/{db,main,zerobyte}.yml`, `templates/compose.yml.j2`, `services.yaml.j2`, `vibravid_config.json.j2`, `group_vars/all/services.yml`: the swap
   - `README.md`, `docs/architecture.drawio`: the service tables and diagram
2. `feat(containers): add FantaQuoggio app and its Airflow pipeline`
   - `roles/containers/tasks/fantaquoggio.yml`: Postgres, db-backup, db-init, the app, the three Airflow services
   - `group_vars/all/{services,infrastructure}.yml`, `templates/compose.yml.j2`, `services.yaml.j2`, `tasks/{main,zerobyte}.yml`: variables, network, tiles, backups
   - `README.md`, `docs/architecture.drawio`: the stack documented
3. `fix(containers): align FantaQuoggio with the stack as built`
   - `roles/containers/tasks/fantaquoggio.yml`: db-init command and DSN, the `fantaquoggio-airflow-init` one-shot and dependencies, healthchecks, the api-server's start command, 768m dag-processor, DAGs paused at creation, the rendered settings, `data/models/mister`
   - `group_vars/all/services.yml`: transfer windows as a list, Season ids, the request budget
   - `roles/containers/templates/fantaquoggio-airflow-passwords.json.j2`: removed
   - `README.md`, `docs/architecture.drawio`: the second one-shot, the model artifacts
4. `feat(containers): deploy FantaQuoggio v0.5.0`
   - `group_vars/all/services.yml`: `fantaquoggio_version` 0.5.0

---

## [2026-08-28 12:22] Push Summary

### Conversation Context
The starting point was a full review of the homeserver configuration from the security,
scalability, readability and maintainability angles, verified against the live server
rather than the repo alone. The review found that the public GitHub repo carried plaintext
credentials (wishlist, vikunja), that Homepage — reachable from the LAN without any auth and
from the internet behind Cloudflare Access — held the raw Docker socket and therefore root
on the host, that every published port bypasses UFW, and that the compose template was an
allowlist silently dropping `network_mode`, `user` and `healthcheck` (beszel-agent and
Postgres were not configured the way their task files claimed; trilium's `ro1` typo made a
mount read-write). pihole and audiobookshelf were still running as orphans despite being
disabled, `tailscale.yml` was not a valid playbook, and every deploy force-recreated all 36
containers.

Decisions: unused services were removed rather than secured (wishlist, vikunja, and the
already-disabled pihole/audiobookshelf). The template now dumps each `*_service` dict as
YAML so any Compose key works, and `setup.yml` derives bind-mount directories from the
volumes instead of a copy-pasted task per service; `run.yml` uses `docker_compose_v2` with
`remove_orphans` and without `--force-recreate`. For the socket, a read-only
`docker-socket-proxy` on an internal network was chosen over removing Homepage's docker
integration: it blocks the root-takeover path while keeping the status dots, with the known
limitation that container `inspect` still exposes env vars. Databases and caches moved to
per-stack `internal: true` networks so an app can reach only the database it owns; this
forced the shared Postgres to drop its published port. Cloudflare Access stays the perimeter
(it covers homepage and actual only; Jellyfin must stay Access-free for the TVs) — a
self-hosted IdP was assessed and rejected as heavier and inside the perimeter. UFW rules are
now edited in place instead of reset on every run, the world-open 22/53 rules are gone
(Tailscale SSH and the LAN/tailnet allow rules cover every legitimate path), and root SSH
login is disabled; these tasks got a `firewall` tag so they run without the rest of `common`
(apt upgrade + reboot). VibraVid was pinned to v1.4.0 with resource limits, Immich ML got
limits too, and Zerobyte gained the spesatracker and vibravid volumes that were persisted but
never backed up. Finally the README was rewritten, a draw.io architecture diagram added, and
a documentation contract (`CLAUDE.md` + `scripts/check_docs.py` in CI) requires docs to
change in the same commit as the code they describe.

### Commits
1. `chore(containers): drop wishlist, pihole, audiobookshelf, vikunja and the tailscale playbook`
   - `roles/containers/tasks/{wishlist,pihole,audiobookshelf,vikunja}.yml`, `tailscale.yml`: removed
   - `roles/containers/tasks/main.yml`: imports removed
   - `group_vars/all/services.yml`: dropped `oai_key`, `pihole_password`, `audiobookshelf_key`, stale karuta comments
   - `roles/containers/templates/services.yaml.j2`: tiles removed, Mealie hostname typo fixed
   - `roles/containers/tasks/zerobyte.yml`: removed mounts of deleted services
   - `.ansible-lint`: no longer excludes `tailscale.yml`
2. `refactor(containers): derive bind-mount dirs from volumes and deploy with docker_compose_v2`
   - `roles/containers/tasks/setup.yml`: collects `./` and `media_dir` host paths from every service's volumes and creates the missing ones (`install -d`, owner `username`); NPM leftovers removed
   - `roles/containers/tasks/run.yml`: `community.docker.docker_compose_v2`, `pull: always`, `remove_orphans`, optional `compose_services`
   - `requirements.yml`: `community.docker >= 5.0.0`
   - `roles/containers/tasks/ghcr_login.yml`: always-true `when` removed
   - 10 service task files: "Setup directories" tasks removed; `actualtap.yml` config dir path fixed
3. `fix(containers): render every compose key; repair beszel-agent and trilium mounts`
   - `roles/containers/templates/compose.yml.j2`: dumps each service dict with `to_nice_yaml`
   - `roles/containers/tasks/beszel.yml`: agent on host network for real (`networks` removed, `HUB_URL=http://localhost:8090`)
   - `roles/containers/tasks/trilium.yml`: `ro1` → `ro`
4. `security: socket proxy, per-stack internal networks, firewall and sshd hardening`
   - `roles/containers/tasks/socket-proxy.yml`: `tecnativa/docker-socket-proxy:v0.5.0`, `CONTAINERS=1 IMAGES=1 POST=0`, on `docker-api`
   - `roles/containers/tasks/homepage.yml`, `wud.yml`, `files/homepage_config/docker.yaml`: socket mount removed, API via `socket-proxy:2375`
   - `roles/containers/templates/compose.yml.j2`: internal networks `docker-api`, `db-shared`, `infisical`, `immich`, `karutuogg`
   - `roles/containers/tasks/db.yml`, `templates/postgres-initdb.sh.j2`: no published port, healthcheck with `start_period`, initdb script creating extra databases from `shared_postgres_databases`, on `db-shared`
   - `roles/containers/tasks/infisical.yml`, `spesatracker.yml`: `depends_on` with `service_healthy`, joined `db-shared` (+ `infisical`); docker-exec DB provisioning removed
   - `roles/containers/tasks/immich.yml`, `karutuogg.yml`: databases/caches on their stack network only; Immich ML CPU/memory limits
   - `roles/containers/tasks/cloudflared.yml`: `TUNNEL_TOKEN` env instead of `--token`
   - `roles/containers/tasks/jellyfin.yml`: media mount read-only
   - `common/tasks/network.yml`, `common/handlers/main.yml`, `common/tasks/main.yml`: no `ufw reset`, world-open 22/53 rules deleted, `PermitRootLogin no` drop-in with restart handler, `firewall` tag
5. `feat(containers): pin vibravid v1.4.0, cap encode resources, back up spesatracker and vibravid`
   - `roles/containers/tasks/vibravid.yml`: `v1.4.0`, `deploy.resources.limits`, Movies/Shows mounts
   - `roles/containers/templates/vibravid_config.json.j2`: daily arr polling, no path mapping, trimmed provider fallback
   - `roles/containers/tasks/zerobyte.yml`: added `spesatracker/data`, `vibravid/conf`, `vibravid/data`
6. `docs: rewrite README, add draw.io architecture, documentation contract and check`
   - `README.md`: networking, storage, infrastructure, services, backups and deployment sections rewritten for the new pipeline and networks
   - `docs/architecture.drawio`: trust-boundary diagram (tunnel vs LAN/tailnet, networks, Docker socket paths)
   - `CLAUDE.md`: documentation contract and verification commands
   - `scripts/check_docs.py`, `scripts/README.md`, `.github/workflows/lint.yml`: mechanical docs check in CI
   - `.claude/skills/add-service/SKILL.md`: no directory tasks, networks rule, deploy commands

---

## [2026-08-25 00:29] Push Summary

### Conversation Context
VibraVid (AstraeLabs' successor to the StreamingCommunity downloader) joins the stack as a
download client for the arr services, deployed from `ghcr.io/astraelabs/vibravid:latest` on
host port 8001 since 8000 is taken. The arr integration is polling-only rather than
webhook-based, deliberately: polling is pure env/config on the VibraVid side and stays fully
ansible-managed, while webhooks would require hand-configured connections and shared secrets
inside the Sonarr/Radarr UIs for a marginal latency win at a 5-minute polling interval;
`webhook_priority` support means webhooks can be layered on later without a migration.
`config.json` is seeded from the tuned instance that was running bare on the server
(`~/StreamingCommunity/Conf/config.json` — x265 re-encode, ita/eng track selection, provider
fallback order) as an ansible-authoritative template, so GUI edits revert on deploy. Downloads
mount the shared `{{ media_dir }}/downloads` at `/app/Video` with an `ARR.path_mapping` entry
translating to the `/downloads` path Sonarr/Radarr already mount, instead of a dedicated
directory that each arr app would need added by hand. The existing FlareSolverr container is
reused; the bypasser and Telegram-bot sidecars, and the docker-socket mount for in-app updates
(WUD already tracks updates here), were considered and skipped. Two new vault secrets back the
deploy: `VIBRAVID_SECRET_KEY` (Django) and `TMDB_API_KEY`, which VibraVid accepts exclusively
via environment. `login.json` and `domains.json` stay unmanaged — the former may hold provider
credentials, the latter is refetched online by the app.

### Changes
- `roles/containers/tasks/vibravid.yml`: New service task — container definition, persistent conf/data/logs/binary dirs, and templated config deploy.
- `roles/containers/templates/vibravid_config.json.j2`: Config seeded from the server's tuned instance, with arr polling enabled against sonarr/radarr via vault keys, `/app/Video → /downloads` path mapping, and FlareSolverr pointed at the stack container.
- `roles/containers/tasks/main.yml`: Import `vibravid.yml`.
- `group_vars/all/services.yml`: Added `vibravid_secret_key` and `tmdb_key` vault references.
- `roles/containers/templates/services.yaml.j2`: VibraVid tile in the Arr group (built-in `mdi-movie-open` icon, no PNG needed); ride-along fix of the Calibre-Web tile icon filename.

---

## [2026-08-04 11:01] Push Summary

### Conversation Context
Spesatracker's receipt parsing gains an LLM path for expanding the abbreviated line-item names
supermarket receipts use, which the regex parser can only partially recover. It points at the
self-hosted vLLM endpoint already running on `bestione` (`qwen3.6-27b-batiai`) rather than a
hosted API, so no key is involved and the three values live in `group_vars/all/services.yml` as
plain config instead of the vault. The 300s timeout is deliberately generous: parsing happens at
import time as a batch step, not in a user-facing request. All three vars pass through
`| default('')`, so an unset or empty `LLM_BASE_URL` falls back to the regex parser — if
`bestione` is down or the vars are missing, imports degrade instead of failing.

### Changes
- `group_vars/all/services.yml`: Added `spesatracker_llm_base_url`, `spesatracker_llm_model`, and `spesatracker_llm_timeout`.
- `roles/containers/tasks/spesatracker.yml`: Passed `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_TIMEOUT` into the container, all defaulted so an empty base URL keeps the regex-only parser.

---

## [2026-08-04 11:00] Push Summary

### Conversation Context
The goal was reading ebooks on the Kobo through KOReader's OPDS client, which needs a
server-side library. Calibre-Web Automated was chosen over plain Calibre-Web because it ingests
and converts automatically instead of requiring the library to be curated by hand in desktop
Calibre. The binding constraint was keeping it clear of the existing Audiobookshelf data: CWA's
ingest folder is consume-and-move — it deletes source files once imported — so it gets a
dedicated `cwa-book-ingest/` drop zone plus its own `calibre-library/`, and must never be
pointed at `media_dir/books` (audiobooks) or `pdfs/`. Both directories live on the DAS so
imports are same-filesystem renames rather than cross-device copies, and both are created by the
Ansible task rather than by hand, because Docker would otherwise autocreate them root-owned and
break the container's PUID/PGID. `NETWORK_SHARE_MODE=false` because the DAS is local ext4 where
inotify works, so the polling fallback is unnecessary. No Cloudflare tunnel route was added
deliberately: the Kobo syncs at home, so LAN/Tailscale reach is enough and the library stays off
the public internet. Zerobyte backs up only the config directory — the library itself is bulk
data and `metadata.db` is a live SQLite file needing a consistent snapshot rather than a file
copy, which is left unsolved for now.

### Changes
- `roles/containers/tasks/calibre-web-automated.yml`: New service — CWA `v4.0.6` on `:8083`, config volume, DAS-backed `cwa-book-ingest`/`calibre-library` mounts, `NETWORK_SHARE_MODE=false`, wud release-link label; creates the config and DAS library directories with correct ownership.
- `roles/containers/tasks/main.yml`: Imported the new task file.
- `roles/containers/templates/services.yaml.j2`: Added the homepage tile (docker stats + dot status).
- `roles/containers/tasks/zerobyte.yml`: Mounted the CWA config directory into the backup container, with a note on why the library and live `metadata.db` are excluded.
- `README.md`: Documented the two DAS directories and the consume-and-move ingest behaviour, noted Audiobookshelf's `books/`/`pdfs/` are untouched, and added the service-table row.

---

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
