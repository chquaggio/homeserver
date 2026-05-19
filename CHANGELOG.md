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
