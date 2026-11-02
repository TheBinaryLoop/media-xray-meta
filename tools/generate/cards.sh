#!/usr/bin/env bash
# Per-frame YAVG and YHIGH (90th percentile luma) at 5 fps, lowest CPU and IO priority.
# Usage: cards.sh plan.tsv outdir   (plan: key, path, start, duration)
set -u
plan=$1 out=$2
mkdir -p "$out"
while IFS=$'\t' read -r key path start dur; do
  [ -s "$out/$key.cards" ] && continue
  nice -n 19 ionice -c3 ffmpeg -nostdin -hide_banner -loglevel error -threads 1 -skip_loop_filter all -skip_frame noref \
    -ss "$start" -t "$dur" -i "$path" -map 0:v:0 \
    -vf "fps=5,scale=480:-2,signalstats,metadata=print:file=$out/$key.cards.tmp" \
    -f null - && mv "$out/$key.cards.tmp" "$out/$key.cards" || echo "FAILED $key" >&2
done < "$plan"
