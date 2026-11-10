# scripts/

These are helpers that live outside the Ansible playbook. Most of them bootstrap a machine or run once, and anything that has to be reproducible across reboots belongs in an Ansible role instead.

| Script | Purpose | Ansible-managed equivalent? |
|---|---|---|
| `install_docker.sh` | Installs Docker once on a fresh host, following the curl-based procedure of the official Docker docs. | **Yes**: `roles/docker/` does the same idempotently and is the preferred path, while the script stays available for emergency manual installs. |
| `install_cuda.sh` | Installs the CUDA 13.0 toolkit on WSL Ubuntu, and is used only on the workstation. | No, because it is specific to the workstation. |
| `install_cuda_129.sh` | Does the same as `install_cuda.sh` with CUDA pinned to 12.9. | No, because it is specific to the workstation. |
| `upgrade_nvim.sh` | Downloads the latest Neovim release tarball into `/opt/nvim`, which is faster than waiting for the role to run. | **Partially**: `roles/system/tasks/neovim.yml` handles installs, and the script is a quick manual upgrade path. |
| `check_docs.py` | Fails if a compose service or network is missing from `README.md` and `docs/architecture.drawio`. CI runs it, and CLAUDE.md asks for it before every commit. | Not applicable. |
| `add_transactions.py` | Imports a semicolon-delimited CSV from an Italian bank into the Actual Budget server, and is run on demand. | No, because it is a runtime tool that changes no server configuration. |
| `check_vault_keys.py` | Fails if `group_vars` references a vault key that `vault.yml` lacks, and lists the vault keys that nothing references. It decrypts the vault, so it runs on the control machine and not in CI. | Not applicable. |
