#!/usr/bin/env bash
# One frame per second of a file as 960-px JPEGs (decoded on the GPU), as a tar on stdout.
# Waits while Jellyfin is transcoding a stream for a viewer, so playback always has the GPU first.
set -eu
while pgrep -u jellyfin -a ffmpeg | grep -q -E -- '-f hls|/transcodes/'; do sleep 30; done
d=$(mktemp -d)
nice -n 19 ionice -c3 ffmpeg -nostdin -hide_banner -loglevel error -init_hw_device vaapi=va:/dev/dri/renderD128 \
  -hwaccel vaapi -hwaccel_output_format vaapi -i "$1" -map 0:v:0 \
  -vf "fps=1,scale_vaapi=w=960:h=-2,hwdownload,format=nv12" -q:v 4 "$d/%05d.jpg"
tar cf - -C "$d" .
rm -rf "$d"
