#!/bin/bash

IN_DIR="tmp"
IN_FILES=("nava-robin-4khd.com-002.png" "nava-robin-4khd.com-003.png")
IN_FORMATS=()
IN_PATHS=()
OUT_PATH="tmp/merged_image.png"
if [ ${#IN_FILES[@]} -eq 0 ]; then
    IN_PATHS+=("$IN_DIR")
else
    for filename in "${IN_FILES[@]}"; do
        IN_PATHS+=("${IN_DIR}/${filename}")
    done
fi

DIRECTION="horizontal"
GRID_SIZE=()
SPACING=0
if [ ${#GRID_SIZE[@]} -eq 0 ]; then
    python main.py merge --direction "$DIRECTION" --input_path "${IN_PATHS[@]}" \
    --output_path "$OUT_PATH" --input_formats "${IN_FORMATS[@]}" --spacing "$SPACING"
else
    python main.py merge --direction "$DIRECTION" --input_path "${IN_PATHS[@]}" \
    --output_path "$OUT_PATH" --input_formats "${IN_FORMATS[@]}" \
    --spacing "$SPACING" --grid_size "${GRID_SIZE[@]}"
fi