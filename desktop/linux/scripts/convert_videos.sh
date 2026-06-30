#!/bin/bash

# --- Function to check if FFmpeg is installed ---
check_ffmpeg() {
    if ! command -v ffmpeg &> /dev/null
    then
        echo "🚨 ERROR: FFmpeg is not found."
        echo "Please ensure FFmpeg is installed and accessible in your system's PATH."
        exit 1
    fi
}

# --- Function to display usage information ---
usage() {
    echo "Usage: $0 [DIRECTORY_PATH]"
    echo "Converts all .mkv files in the specified directory to .mp4 format."
    echo "If no path is provided, it processes the current directory."
}

# --- Main conversion function ---
convert_file() {
    # 1. Capture the input argument safely
    INPUT_PATH="$1"  # Renaming to INPUT_PATH makes variable usage cleaner
    
    # 2. Use dirname and basename to safely construct paths
    DIR_NAME=$(dirname -- "$INPUT_PATH")
    FILENAME=$(basename -- "$INPUT_PATH")
    FILENAME_NO_EXT="${FILENAME%.*}"
    
    # 3. Create the output filename in the same directory
    OUTPUT_PATH="${DIR_NAME}/${FILENAME_NO_EXT}.mp4"

    echo ""
    echo "🎬 Processing: $FILENAME"
    echo "   Output: $(basename -- "$OUTPUT_PATH")"

    # Execute FFmpeg command
    ffmpeg -i "$INPUT_PATH" \
           -c copy \
           -movflags +faststart \
           -y \
           "$OUTPUT_PATH"

    if [ $? -eq 0 ]; then
        echo "✅ Success: $FILENAME converted to MP4."
    else
        echo "❌ FAILED: $FILENAME conversion failed. Check the FFmpeg output for details."
        echo "   (This often means the codecs are incompatible and a re-encode is needed.)"
    fi
}

# --- Script Execution Start ---

# Check for required tool
check_ffmpeg

# Determine the directory to process
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    usage
    exit 0
elif [ -z "$1" ]; then
    # Use current directory if no argument is given
    DIR_PATH="."
    echo "Starting conversion in the current directory: $DIR_PATH"
elif [ -d "$1" ]; then
    # Use the directory passed as argument
    DIR_PATH="$1"
    echo "Starting conversion in directory: $DIR_PATH"
else
    echo "Error: Directory '$1' not found or is not a valid directory."
    usage
    exit 1
fi

# Find all .mkv files and loop through them
for FILE_PATH in "$DIR_PATH"/*.mkv; do
    # Check if the file actually exists (handles the case where no *.mkv files are found)
    if [ -f "$FILE_PATH" ]; then
        convert_file "$FILE_PATH"
    else
        # This branch runs if the glob expands to literal "$DIR_PATH/*.mkv" because no files were found.
        # It ensures we don't print "Found files to convert." if nothing is there.
        if [ "$FILE_PATH" == "$DIR_PATH/*.mkv" ]; then
            echo "No .mkv files found in: $DIR_PATH"
        fi
        exit 0
    fi
done

echo ""
echo "--- Conversion Complete ---"