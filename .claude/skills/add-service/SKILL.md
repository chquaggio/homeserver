---
name: add-service
description: Use when adding a new Docker service to this homeserver ansible stack — creating a new roles/containers/tasks/<name>.yml, wiring it into main.yml, and optionally adding a homepage tile or vault secret. Triggered by "add a service", "add a container", "add <something> to homeserver", "scaffold a new service".
---

# Add a service to the ansible stack

Walks through creating a new containerized service in this repo end-to-end: task file, import wiring, optional homepage tile, optional vault secret. The DRY refactor in `setup.yml` means **no manual edit to setup.yml is needed** — services are auto-discovered via `query('varnames', '_service$')`.

## When to use

- User asks to add a new container, service, or tile
- User asks to "scaffold" a new ansible service
- User describes a docker image they want to run on the homeserver

## When NOT to use

- Modifying an *existing* service (just edit its task file directly)
- One-off `docker run` test (not infrastructure)
- Service that isn't containerized

## Workflow

Follow these steps in order. Use `AskUserQuestion` for each user prompt — never make assumptions about the service shape.

### Step 1 — Gather core service details

Ask the user (one `AskUserQuestion` call, multiple questions):

- **Service name** (lowercase, single word — used as filename, container name, network alias)
- **Docker image** (e.g. `lscr.io/linuxserver/foo:latest`, `ghcr.io/owner/repo:tag`)
- **Primary port mapping** (e.g. `8080:8080` — or `none` if internal-only)
- **Uses media storage?** (yes/no — determines whether to bind `{{ media_dir }}`)
- **Uses linuxserver.io image conventions?** (yes/no — determines PUID/PGID/TZ env vars)

### Step 2 — Look at a similar existing service

Read 1-2 existing task files that match the new service's shape:
- linuxserver-style → `roles/containers/tasks/sonarr.yml`, `radarr.yml`
- ghcr image with secrets → `roles/containers/tasks/wishlist.yml`, `trilium.yml`
- Simple stateful app → `roles/containers/tasks/mealie.yml`, `actual.yml`
- Network device passthrough → `roles/containers/tasks/beszel.yml`, `pihole.yml`

Use whichever is closest as the template — don't reinvent the volume/env pattern.

### Step 3 — Generate the task file

Create `roles/containers/tasks/<name>.yml`. Standard skeleton:

```yaml
---
- name: Configure <Name> service
  set_fact:
    <name>_service:
      name: <name>
      image: <image>
      container_name: <name>
      ports:
        - "<host>:<container>"
      volumes:
        - ./<name>/config:/config
        # add {{ media_dir }}/... bindings only if needed
      environment:
        - "PUID={{ puid }}"      # only if linuxserver
        - "PGID={{ pgid }}"      # only if linuxserver
        - "TZ={{ tz }}"
      networks:
        - qnet
      restart: unless-stopped

- name: Setup <Name> directories
  ansible.builtin.file:
    path: "{{ docker_compose_dir }}/<name>/{{ item }}"
    owner: "{{ username }}"
    group: "{{ username }}"
    state: directory
  loop:
    - "config"
```

**Rules:**
- Always set `name`, `container_name`, `image` at the top
- Use `{{ media_dir }}/<subdir>` for media bindings (never hardcode `/media` or `/mnt/das`)
- Use `{{ tz }}`, `{{ puid }}`, `{{ pgid }}` for those env vars — never hardcode
- Always `networks: [qnet]` and `restart: unless-stopped`
- The fact name MUST end in `_service` (e.g. `foo_service`) — `setup.yml` auto-discovers via `query('varnames', '_service$')`. If you skip this convention, the service won't appear in the rendered compose.
- For directory-creation tasks, loop over the subdirs the container expects (`config`, `cache`, `data`, etc.)

### Step 4 — Wire into main.yml

Edit `roles/containers/tasks/main.yml` and add the import in alphabetical order with the others:

```yaml
- import_tasks: <name>.yml
```

**Do NOT** touch `setup.yml` — it auto-discovers.

### Step 5 — Vault secret (if applicable)

Ask: "Does this service need a secret (API key, password, token)?"

If yes:
1. Edit the vault: `ansible-vault edit group_vars/all/vault.yml`
   - Add `<NAME>_KEY: "..."` (or similar) in ALL_CAPS
2. Add reference in `group_vars/all/services.yml`:
   ```yaml
   <name>_key: "{{ <NAME>_KEY }}"
   ```
3. Reference in the task file as `{{ <name>_key }}` (quote env vars: `- "API_KEY={{ <name>_key }}"`)

Do NOT touch `vault.yml` content via the regular Edit tool — it's encrypted. Use `ansible-vault edit` and have the user do it interactively if needed.

### Step 6 — Homepage tile (if applicable)

Ask: "Does this service have a UI worth surfacing on the homepage dashboard?"

If yes, ask which group:
- **Utilities** (line 2) — generic tools, dashboards
- **Arr** (line 150) — *arr stack, downloaders
- **Media** (line 218) — media playback/management
- **AI** (line 251) — LLM-related tools

Append a tile to `roles/containers/templates/services.yaml.j2` under the chosen group:

```yaml
    - <Name>:
        icon: <name>.png
        href: http://quoggioserver:<port>
        description: <short description>
        server: server-docker
        container: <name>
        statusStyle: "dot"
        showStats: true
        # widget block only if a homepage widget exists for this service
        # widget:
        #   type: <type>
        #   url: http://<name>:<internal-port>
        #   key: "{{ <name>_key }}"
```

The user is responsible for adding the `<name>.png` icon to `roles/containers/files/homepage_config/` — mention this.

### Step 7 — Verify

Run:

```bash
ansible-playbook --syntax-check site.yml
```

If it passes, you're done. Output to the user:

- Files created / modified (list with paths)
- Whether vault edit is needed (and the command)
- Whether icon needs to be added (and the path)
- Next command to run: `ansible-playbook -t containers site.yml`

## Common mistakes

| Mistake | Fix |
|---|---|
| Forgot the `_service` suffix on the fact name | Rename to `<name>_service` — setup.yml won't pick it up otherwise |
| Hardcoded `/media`, `/mnt/das`, `1000`, `Europe/Rome` | Use `{{ media_dir }}`, `{{ puid }}`, `{{ pgid }}`, `{{ tz }}` |
| Edited `setup.yml` | Revert. Auto-discovery handles it. |
| Edited vault.yml with Edit tool | It's encrypted — use `ansible-vault edit` instead |
| Skipped quoting env vars with jinja (e.g. `- PUID={{ puid }}`) | Yamllint flags unquoted templates; wrap as `- "PUID={{ puid }}"` |
| Missing `restart: unless-stopped` or `networks: [qnet]` | Standard for every service — add them |

## Quick reference: per-file checklist

- [ ] `roles/containers/tasks/<name>.yml` — created
- [ ] `roles/containers/tasks/main.yml` — `import_tasks: <name>.yml` added
- [ ] `group_vars/all/vault.yml` — secret added (if applicable)
- [ ] `group_vars/all/services.yml` — secret ref added (if applicable)
- [ ] `roles/containers/templates/services.yaml.j2` — homepage tile (if applicable)
- [ ] `roles/containers/files/homepage_config/<name>.png` — icon (user adds manually)
- [ ] `ansible-playbook --syntax-check site.yml` passes
