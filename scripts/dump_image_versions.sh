#!/usr/bin/env bash
# Dump every running container's image, version label, and immutable repo digest to a
# text file. Use this to capture what's actually running before pinning images in the
# ansible task files (the digest is what you pin to for reproducible deploys).
#
# Usage:
#   ./dump_image_versions.sh                 # writes image-versions-<date>.txt
#   ./dump_image_versions.sh /tmp/pins.txt   # writes to a given path
set -euo pipefail

out="${1:-image-versions-$(date +%F).txt}"

{
  printf '%-24s\t%-50s\t%-22s\t%s\n' "CONTAINER" "IMAGE" "VERSION_LABEL" "REPO_DIGEST"
  docker ps --format '{{.Names}}\t{{.Image}}' | sort | while IFS=$'\t' read -r name image; do
    digest=$(docker inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}-{{end}}' "$name" 2>/dev/null || echo '-')
    version=$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$name" 2>/dev/null || true)
    [ -z "${version:-}" ] && version='-'
    printf '%-24s\t%-50s\t%-22s\t%s\n' "$name" "$image" "$version" "$digest"
  done
} | tee "$out"

echo "Wrote $out"
