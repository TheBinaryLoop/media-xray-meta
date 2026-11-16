#!/usr/bin/env bash
# Whole soundtrack of each file as 16 kHz mono Opus. The file is read through pv at a fixed byte rate so
# the NAS link keeps headroom for streams; ffmpeg runs at the lowest CPU priority.
# Usage: fullaudio.sh PV plan.tsv outdir   (plan: key, path, map)
set -u
pv=$1 plan=$2 out=$3
mkdir -p "$out"
while IFS=$'\t' read -r key path map; do
  [ -s "$out/$key.opus" ] && continue
  "$pv" -q -L 12m "$path" | nice -n 19 ffmpeg -nostdin -hide_banner -loglevel error -threads 1 \
    -i pipe:0 -map "$map" -vn -ac 1 -ar 16000 -c:a libopus -b:a 32k -f ogg "$out/$key.opus.part" \
    && mv "$out/$key.opus.part" "$out/$key.opus" || echo "FAILED $key" >&2
done < "$plan"
