# scripts/

Ad-hoc helpers that live outside the ansible playbook. Most are bootstrap or one-off tools; ansible should be preferred for anything that needs to be reproducible across reboots.

| Script | Purpose | Ansible-managed equivalent? |
|---|---|---|
| `install_docker.sh` | One-shot Docker install on a fresh host (curl-based, matches the official Docker docs). | **Yes** — `roles/docker/` does this idempotently. Prefer the role. Keep this script around for emergency manual installs. |
| `install_cuda.sh` | Installs CUDA 13.0 toolkit on WSL Ubuntu. Used on the workstation, not the home server. | No — workstation-specific. |
| `install_cuda_129.sh` | Same as above but pinned to CUDA 12.9. | No — workstation-specific. |
| `upgrade_nvim.sh` | Pulls the latest Neovim release tarball into `/opt/nvim`. Useful when you don't want to wait for the role to run. | **Partially** — `roles/system/tasks/neovim.yml` handles installs; this script is a fast manual upgrade path. |
| `add_transactions.py` | Imports an Italian-bank CSV (semicolon-delimited) into the Actual Budget server. Standalone utility, run on demand. | No — runtime tool, not infrastructure. |
