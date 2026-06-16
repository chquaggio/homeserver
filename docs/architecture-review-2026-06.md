# Homeserver architecture review — action items (2026-06-16)

Handoff notes from a mymcp working session. These are **homeserver-repo concerns** raised while
designing the MCP server; capture them here for a future chat in this repo. Ordered by
consequence.

---

## Applied 2026-06-16 (working session)

Worked through this doc in-repo. Two **previously unknown gaps** were found and fixed, plus
items #2, #5 partially done. Runtime/dashboard steps remain (see boxes below).

**Bugs found that this doc didn't list:**
- **Immich was entirely absent from Zerobyte** — neither the photo DB nor the library was backed
  up, and Zerobyte has no `/mnt/das` mount so it *couldn't* reach the library. Photo metadata
  (faces/albums) now dumped + backed up; photo *files* deferred (GCloud retained for now).
- **Shared-Postgres backup path typo** — Zerobyte mounted `./postgres-data` (hyphen) but the DB
  writes to `./postgres_data` (underscore), so the shared DB was never captured. Replaced with a
  logical-dump mount (see #2).

**Changes made:**
- `db.yml` / `immich.yml`: added `postgres-backup-local` dump sidecars (#2).
- `zerobyte.yml`: back up dump dirs instead of live data dir; added missing app data
  (audiobookshelf, homepage, wishlist).
- `watchtower.yml` (new, wired into `main.yml`): Watchtower in notify-only mode → Telegram (#5).

Deploy with: `ansible-playbook -t containers site.yml`

---

## 1. Backups & disaster recovery — HIGHEST PRIORITY

**Current state:** Zerobyte backs up all Docker volumes to AWS S3. **No restore has ever been
tested.** No local/offline second copy. Google Cloud currently holds a second copy of photos, but
the user plans to delete it.

**Risks:**
- The 12TB DAS is a **single USB-attached ext4 disk, no RAID** — one disk failure = total loss of
  whatever isn't backed up elsewhere.
- An untested backup is a hope, not a backup. Restore can fail on encryption keys, S3
  permissions, volume layout, or DB consistency — and you find out at the worst time.

**Actions:**
- [ ] **Do a real restore drill BEFORE deleting the Google Cloud photo copy.** Restore Immich
      (DB + library) into a scratch location and confirm photos + faces/albums come back. Removing
      the GCloud copy first leaves the only second copy as an unverified S3 backup.
- [ ] Document the restore procedure (keys, bucket, order of operations) so it's repeatable.
- [~] Confirm Zerobyte captures the *right* volumes (Immich, Trilium, Actual, Postgres, Vikunja,
      app data) and that its own config/keys are themselves recoverable. → DB dumps + missing app
      data (audiobookshelf, homepage, wishlist) now added; the **Immich photo library
      (`/mnt/das/immich`) is still NOT in S3** (deferred — GCloud is the photo copy for now).
      Still TODO: verify Zerobyte's own config/keys are recoverable.

## 2. Database backups (free fix, no new cost)

**Current state:** Neither the shared Postgres 17 nor Immich's Postgres is dumped. They're only
caught by Zerobyte's **file-level volume** backup, which is **unsafe for a running database**
(can capture a torn/inconsistent state that won't restore cleanly).

**Action (no extra spend — reuses the existing S3 backup):**
- [x] Add a scheduled `pg_dump`/`pg_dumpall` (cron or a tiny sidecar) that writes dumps into a
      path **already inside a Zerobyte-backed volume**. → `db-backup` + `immich-db-backup`
      sidecars (`prodrigestivill/postgres-backup-local`) dump daily into `./db-backups` and
      `./immich/db-backups`, both now backed up by Zerobyte. Retention 14d/8w/12m.
- [x] For Immich specifically: the DB image is pinned to a `vectorchord`/`pgvecto.rs` build —
      record the exact image tag. → Recorded in `immich.yml`:
      `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0` (restore must match).

## 3. Public exposure audit (Cloudflare tunnel)

**Publicly exposed today:** jellyfin, homepage, actual, trilium, openwebui, seerr, mealie,
audiobookshelf, wishlist.
- Behind **Cloudflare Access (email-restricted):** actual, homepage.
- **Relying only on native app auth:** jellyfin, trilium, openwebui, seerr, mealie,
  audiobookshelf, wishlist.

**Notes / actions:**
- [ ] Highest-value to put behind Cloudflare Access next: **trilium** (its ETAPI token is full
      read/write to all notes) and **openwebui** (admin can register tools / run MCP and it bridges
      to the LLM). **wishlist** is a custom app and the least battle-tested.
- [ ] **mymcp must NOT be exposed via the tunnel** (decided in the MCP work — it's local/Tailscale
      only). Verify it has no tunnel ingress.

## 4. Pi-hole removal (leaning yes)

Only ~2% of queries are blocked, and DNS is already served via Tailscale + Cloudflare.
- [ ] Before removing: confirm nothing depends on Pi-hole for **local name resolution** (the
      `.fantaquoggio.bid` / internal hostnames). Make sure Tailscale MagicDNS / Cloudflare cover
      those names.
- [ ] Removing it also eliminates a single-point-of-failure (Pi-hole serving LAN DNS from a
      container on the same host it depends on).

## 5. Image pinning + controlled updates

Most services float on `:latest` (`lscr.io/*:latest`, jellyfin, immich `:release`, etc.) →
non-reproducible deploys, surprise breakages, no clean rollback.
- [x] Controlled update flow → **Watchtower in notify-only mode** added (`watchtower.yml`):
      checks daily at 06:00, sends a Telegram report, never pulls/restarts
      (`WATCHTOWER_MONITOR_ONLY=true`).
- [ ] Pin images to specific tags/digests. Deferred to incremental work — capture current
      running digests from the host first:
      `docker inspect --format '{{.Config.Image}} -> {{index .RepoDigests 0}}' $(docker ps -q)`
      then pin each `image:` to the digest. New services (watchtower, both backup sidecars) are
      already pinned to fixed tags.

## 6. Alerting gaps (DAS is the blind spot)

Beszel already sends Telegram alerts on high temperature. Per beszel.dev, Beszel natively
supports **S.M.A.R.T. drive-failure**, **disk usage**, **CPU/memory/temp/load**, **network**, and
**container status** alerts (25+ notification channels incl. Telegram). The agent is already wired
for SMART (`SYS_RAWIO` + `{{ das_device }}` passthrough) and container monitoring (docker.sock) —
**so this is dashboard config, no repo change.** Set up in the Beszel UI per system:
- [ ] **Disk** alert on the `das-01` filesystem → threshold ~85% (covers disk-full on `/mnt/das`).
- [ ] **S.M.A.R.T.** alert enabled for the DAS drive (drive-failure notification).
- [ ] **Container status** / system-down alert (catches container-down + agent offline).
- [ ] Backup job success/failure: Beszel doesn't watch Zerobyte directly. Options: a Beszel
      disk/process check on the dump dirs, Zerobyte's own notifications, or a tiny healthcheck on
      the `postgres-backup-local` sidecars (they expose a healthcheck port).

---

## Things that are already fine

- **Secrets:** managed with `ansible-vault` (`.vault_pass` present). New mymcp secrets (LLM
  endpoint, per-service tokens) should live in the vault and be injected as env into the container.
- **LLM offload:** inference runs on a separate box (`bestione:8000`), keeping it off the server.
- **Remote access:** Tailscale + Cloudflare tunnel (with Access on the sensitive apps).

## Cross-repo note (mymcp)

mymcp is becoming a privileged automation hub with credentials to many services and **no
read-only tokens available**. Mitigation decided on the MCP side: **mutating tools require an
explicit confirm flag** (default to dry-run / no-op). If any service later supports scoped/
read-only API tokens (e.g. a read-only Jellyfin key), prefer issuing those to mymcp.
