#!/usr/bin/env bash
# Contact sheet of frames: sheet.sh FILE START SECONDS FPS COLS ROWS OUT
set -eu
f=$1 start=$2 dur=$3 fps=$4 cols=$5 rows=$6 out=$7
filter="fps=${fps},scale=320:-1,drawtext=text='%{pts\:hms\:${start}}':x=5:y=5:fontsize=20:fontcolor=yellow:box=1:boxcolor=black,tile=${cols}x${rows}"
nice -n 19 ionice -c3 ffmpeg -nostdin -loglevel error -threads 1 -ss "$start" -t "$dur" -i "$f" -vf "$filter" -frames:v 1 -y "$out"
