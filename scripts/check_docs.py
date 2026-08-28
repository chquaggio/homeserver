#!/usr/bin/env python3
"""Fail if a compose service or network is not mentioned in README.md or the diagram.

Catches the shallow drift (a service added or renamed without touching the docs);
CLAUDE.md's documentation contract covers the rest.
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = ROOT / "roles/containers/tasks"
DOCS = (ROOT / "README.md").read_text().lower() + (ROOT / "docs/architecture.drawio").read_text().lower()


def imported_task_files():
    for line in (TASKS / "main.yml").read_text().splitlines():
        m = re.match(r"^- import_tasks: (\S+\.yml)$", line)
        if m and m.group(1) not in ("setup.yml", "run.yml", "ghcr_login.yml"):
            yield TASKS / m.group(1)


def service_names():
    for path in imported_task_files():
        for task in yaml.safe_load(path.read_text()) or []:
            facts = task.get("set_fact") or task.get("ansible.builtin.set_fact") or {}
            for key, value in facts.items():
                if key.endswith("_service") and isinstance(value, dict):
                    yield value["name"], path.name


def network_names():
    text = (ROOT / "roles/containers/templates/compose.yml.j2").read_text()
    networks = text.split("\nnetworks:\n", 1)[1]
    return re.findall(r"^  ([a-z0-9-]+):", networks, re.M)


missing = [f"service {n} ({src})" for n, src in service_names() if n.lower() not in DOCS]
missing += [f"network {n}" for n in network_names() if n.lower() not in DOCS]
if missing:
    print("Not mentioned in README.md or docs/architecture.drawio:")
    print("\n".join(f"  - {m}" for m in missing))
    sys.exit(1)
print("docs check OK")
