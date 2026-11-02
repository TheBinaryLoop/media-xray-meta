#!/usr/bin/env bash
# Cut mono 11025 Hz FLAC windows from the English audio track, at the lowest CPU and IO priority.
# Usage: cut.sh plan.tsv outdir
set -u
plan=$1 out=$2
mkdir -p "$out"
while IFS=$'\t' read -r key path start dur; do
  [ -s "$out/$key.flac" ] && continue
  nice -n 19 ionice -c3 ffmpeg -nostdin -hide_banner -loglevel error -threads 1 \
    -ss "$start" -t "$dur" -i "$path" -map 0:a:0 -ac 1 -ar 11025 -c:a flac "$out/$key.flac.tmp.flac" \
    && mv "$out/$key.flac.tmp.flac" "$out/$key.flac" || echo "FAILED $key" >&2
done < "$plan"
