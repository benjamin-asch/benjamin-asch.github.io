#!/bin/bash

# Dependency check
if ! command -v mogrify &> /dev/null; then
    echo "Error: ImageMagick (mogrify) is not installed. Install it with: sudo pacman -S imagemagick"
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "Error: FFmpeg is not installed. Install it with: sudo pacman -S ffmpeg"
    exit 1
fi

echo "Starting optimization..."

# 1. Optimize Images (JPG/JPEG)
# -auto-orient : Fixes rotation based on EXIF data (MUST come before -strip)
# -resize 1600x> : Resize to max width 1600px only if larger
# -quality 85 : moderate compression
# -strip : remove metadata (EXIF) to save space
# -interlace Plane : makes jpgs progressive
echo "Optimizing images..."
find . -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -exec mogrify -auto-orient -resize 1600x\> -quality 85 -strip -interlace Plane {} +

# 2. Optimize Videos (MP4)
echo "Optimizing videos..."
for video in *.mp4; do
    [ -f "$video" ] || continue
    
    echo "Processing $video..."
    # -movflags +faststart allows video to play before fully downloading
    ffmpeg -y -i "$video" -vcodec libx264 -crf 28 -preset fast -acodec aac -movflags +faststart "temp_$video" < /dev/null
    
    if [ $? -eq 0 ]; then
        mv "temp_$video" "$video"
    else
        echo "Failed to compress $video"
        rm "temp_$video"
    fi
done

echo "Done! All media optimized."
