#!/usr/bin/env bash
# GitHub runner disk cleanup for the ERPNext experiment.
# Removes large preinstalled dev environments the experiment does not need.
# Keeps: python3, node (recorded only), docker, git, curl, and Chromium system libs.
set -u
MODE="${1:-normal}"
OUT="${GITHUB_WORKSPACE:-$PWD}/smoke-out"
mkdir -p "$OUT"

echo "=== df -h before cleanup ==="
df -h /
df -k / | awk 'NR==2{print "disk_free_before_kb="$4}' >> "$OUT/manifest.env"

TARGETS=(
  "/usr/local/lib/android"
  "/usr/share/dotnet"
  "/opt/ghc"
  "/usr/local/.ghcup"
  "/opt/hostedtoolcache/CodeQL"
  "/usr/share/swift"
  "/usr/local/share/boost"
  "/usr/share/miniconda"
  "/opt/hostedtoolcache/go"
  "/opt/hostedtoolcache/PyPy"
  "/opt/hostedtoolcache/Julia"
  "/usr/share/apache-maven-3.9*"
  "/usr/share/gradle-*"
  "/usr/share/sbt"
  "/usr/share/kotlinc"
  "/usr/lib/jvm"
  "/opt/pipx"
  "/usr/share/mysql"
  "/var/lib/mysql"
)
if [ "$MODE" = "deep" ]; then
  # Storage-optimization retry: also drop preinstalled browsers/toolcaches we do not use.
  TARGETS+=(
    "/opt/microsoft/msedge"
    "/opt/hostedtoolcache/ruby"
    "/opt/hostedtoolcache/php"
    "/opt/hostedtoolcache/node"
    "/usr/local/lib/node_modules"
    "/usr/lib/firefox"
    "/usr/share/mozilla"
  )
fi

for pat in "${TARGETS[@]}"; do
  for p in $pat; do
    if [ -e "$p" ]; then
      du -sh "$p" 2>/dev/null | awk -v p="$p" '{printf "removing %-45s %s\n", p, $1}'
      sudo rm -rf -- "$p"
    fi
  done
done

sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*
docker image prune -af >/dev/null 2>&1 || true
docker builder prune -af >/dev/null 2>&1 || true
sudo journalctl --vacuum-size=50M >/dev/null 2>&1 || true

echo "=== df -h after cleanup ==="
df -h /
df -k / | awk 'NR==2{print "disk_free_after_kb="$4}' >> "$OUT/manifest.env"
