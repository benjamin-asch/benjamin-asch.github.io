#!/usr/bin/env sh

shopt -s nocaseglob nullglob
for f in *.heic; do
    heif-convert "$f" "${f%.*}.jpg" && rm -- "$f"
done
shopt -u nocaseglob nullglob
