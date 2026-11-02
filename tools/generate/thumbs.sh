#!/usr/bin/env bash
# Every frame of a window as a 32x18 grayscale thumbnail (raw bytes), at the lowest CPU and IO priority.
# Usage: thumbs.sh plan.tsv outdir   (plan: key, path, start, duration)
set -u
plan=$1 out=$2
mkdir -p "$out"
while IFS=$'\t' read -r key path start dur; do
  [ -s "$out/$key.gray" ] && continue
  nice -n 19 ionice -c3 ffmpeg -nostdin -hide_banner -loglevel error -threads 1 -skip_loop_filter all \
    -ss "$start" -t "$dur" -i "$path" -map 0:v:0 -vf "scale=32:18:flags=area,format=gray" -f rawvideo "$out/$key.gray.tmp" \
    && mv "$out/$key.gray.tmp" "$out/$key.gray" || echo "FAILED $key" >&2
done < "$plan"
