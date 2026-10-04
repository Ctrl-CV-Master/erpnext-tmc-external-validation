#!/usr/bin/env bash
# Sample total used RAM every 5s; final_metrics computes the peak.
OUT="${GITHUB_WORKSPACE:-$PWD}/smoke-out"
mkdir -p "$OUT"
: > "$OUT/peak_ram.log"
while true; do
  used=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print t-a}' /proc/meminfo)
  echo "$(date +%s) ${used}" >> "$OUT/peak_ram.log"
  sleep 5
done
