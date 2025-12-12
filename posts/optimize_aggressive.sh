#!/bin/bash

# Dependency check
if ! command -v mogrify &> /dev/null; then
    echo "Error: ImageMagick (mogrify) is not installed."
    exit 1
fi

echo "Starting aggressive optimization..."

# Optimize Images (JPG/JPEG)
# -auto-orient : Rotates the image correctly BEFORE removing metadata.
# -resize 1200x> : Downscales to 1200px max width (good for blog posts).
# -quality 75 : Drops quality slightly to save significant space.
# -sampling-factor 4:2:0 : Compresses color information (saves ~15%).
# -strip : Removes Exif data/metadata to save space.
# -interlace Plane : Makes images load progressively (blurry to sharp).

echo "Optimizing images..."
find . -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -exec mogrify -auto-orient -resize 1200x\> -quality 75 -sampling-factor 4:2:0 -strip -interlace Plane {} +

echo "Done! Images are now oriented and aggressively compressed (approx 200-400kb)."
