#!/bin/bash

IN_PATH=""
OUT_FORMAT="png"
OUT_PATH=""
IN_FORMATS=()
if [ -n "$OUT_PATH" ]; then
    python main.py convert --output_format "$OUT_FORMAT" --input_path "$IN_PATH" \
    --output_path "$OUT_PATH" --input_formats "${IN_FORMATS[@]}"
else
    python main.py convert --output_format "$OUT_FORMAT" --input_path "$IN_PATH" \
    --input_formats "${IN_FORMATS[@]}"
fi