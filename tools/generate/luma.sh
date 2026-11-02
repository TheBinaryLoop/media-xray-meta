#!/usr/bin/env bash
# Per-frame luma statistics (5 fps) for windows of each file, at the lowest CPU and IO priority.
# Usage: luma.sh plan.tsv outdir   (plan: key, path, start, duration)
set -u
plan=$1 out=$2
mkdir -p "$out"
while IFS=$'\t' read -r key path start dur; do
  [ -s "$out/$key.luma" ] && continue
  nice -n 19 ionice -c3 ffmpeg -nostdin -hide_banner -loglevel error -threads 1 -skip_loop_filter all -skip_frame noref \
    -ss "$start" -t "$dur" -i "$path" -map 0:v:0 \
    -vf "fps=5,scale=480:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=$out/$key.luma.tmp" \
    -f null - && mv "$out/$key.luma.tmp" "$out/$key.luma" || echo "FAILED $key" >&2
done < "$plan"
