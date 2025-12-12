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
# -resize 1600x> : Resize to max width 1600px only if larger
# -quality 85 : moderate compression
# -strip : remove metadata (EXIF) to save space
# -interlace Plane : makes jpgs progressive (load blurry first, then sharp) which feels faster
echo "Optimizing images..."
find . -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -exec mogrify -resize 1600x\> -quality 85 -strip -interlace Plane {} +

# 2. Optimize Videos (MP4)
# We need a temp file because ffmpeg cannot edit in-place
echo "Optimizing videos..."
for video in *.mp4; do
    # Check if file exists to avoid error if no mp4s found
    [ -f "$video" ] || continue
    
    echo "Processing $video..."
    ffmpeg -y -i "$video" -vcodec libx264 -crf 28 -preset fast -acodec aac -movflags +faststart "temp_$video" < /dev/null
    
    # Check if compression succeeded before overwriting
    if [ $? -eq 0 ]; then
        mv "temp_$video" "$video"
    else
        echo "Failed to compress $video"
        rm "temp_$video"
    fi
done

echo "Done! All media optimized."
