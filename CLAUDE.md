# Homeserver — project rules

Ansible stack that renders one Docker Compose file for the Beelink homeserver. The
`add-service` skill in `.claude/skills/` covers adding a container. Global preferences
in `~/.claude/AGENTS.md` apply.

## Documentation contract

The docs are part of the change, not a follow-up. Before every commit, re-read the
sections below that the change touches and update them **in the same commit**:

| Change | Update |
|---|---|
| Service added / removed / renamed, image or port changed | `README.md` service tables; homepage tile in `roles/containers/templates/services.yaml.j2`; the matching box in `docs/architecture.drawio` |
| Network membership, published ports, firewall, tunnel or Access scope | `README.md` → Networking; `docs/architecture.drawio` (networks, entry paths, legend) |
| Volume added to Zerobyte, backup or storage layout | `README.md` → Backups / Storage; `docs/architecture.drawio` storage boxes |
| Rendering pipeline (`setup.yml`, `compose.yml.j2`, `run.yml`) or a repo convention | `README.md` → Infrastructure / Deployment; `.claude/skills/add-service/SKILL.md` |

`scripts/check_docs.py` enforces the mechanical part (every compose service and network
is mentioned in the README or the diagram) and runs in CI; run it locally before
committing. The judgment part — does the prose still describe what the code does — is
on whoever commits.

## Verification before claiming done

`yamllint . && ansible-lint && ansible-playbook --syntax-check site.yml && python3 scripts/check_docs.py`,
then `ansible-playbook site.yml -t containers --check --diff` against the server.
