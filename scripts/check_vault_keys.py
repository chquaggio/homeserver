#!/usr/bin/env python3
"""Compare the vault keys that group_vars references with the keys in vault.yml.

A referenced key that the vault lacks fails the check; a vault key that nothing
references is listed, since it may be kept on purpose (a rollback, for instance).
Needs .vault_pass, so it runs on the control machine and not in CI.
"""
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
VAULT = ROOT / "group_vars/all/vault.yml"

plaintext = subprocess.run(
    ["ansible-vault", "view", str(VAULT)], cwd=ROOT, check=True, capture_output=True, text=True
).stdout
in_vault = set(yaml.safe_load(plaintext))

# Vault keys are uppercase and only group_vars reads them; roles use the lowercase aliases.
referenced = set()
for path in (ROOT / "group_vars").rglob("*.yml"):
    if path != VAULT:
        referenced |= set(re.findall(r"\{\{\s*([A-Z][A-Z0-9_]+)\b", path.read_text()))

unused = sorted(in_vault - referenced)
if unused:
    print("In the vault, referenced nowhere:\n" + "\n".join(f"  - {k}" for k in unused))
missing = sorted(referenced - in_vault)
if missing:
    print("Referenced, missing from the vault:\n" + "\n".join(f"  - {k}" for k in missing))
    sys.exit(1)
print("vault keys OK")
