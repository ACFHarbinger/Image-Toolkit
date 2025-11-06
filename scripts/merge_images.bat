@echo off
setlocal enabledelayedexpansion

set IN_DIR=tmp
set IN_FILES=nava-robin-4khd.com-002.png nava-robin-4khd.com-003.png
set IN_FORMATS=
set OUT_PATH=tmp\merged_image.png
set DIRECTION=horizontal
set GRID_SIZE=
set SPACING=0

:: Build IN_PATHS array
set IN_PATHS=
if "!IN_FILES!"=="" (
    set IN_PATHS=!IN_DIR!
) else (
    for %%f in (!IN_FILES!) do (
        if "!IN_PATHS!"=="" (
            set IN_PATHS=!IN_DIR!\%%f
        ) else (
            set IN_PATHS=!IN_PATHS! !IN_DIR!\%%f
        )
    )
)

:: Execute Python command based on GRID_SIZE
if "!GRID_SIZE!"=="" (
    python main.py merge --direction "!DIRECTION!" --input_path "!IN_PATHS!" --output_path "!OUT_PATH!" --input_formats "!IN_FORMATS!" --spacing "!SPACING!"
) else (
    python main.py merge --direction "!DIRECTION!" --input_path "!IN_PATHS!" --output_path "!OUT_PATH!" --input_formats "!IN_FORMATS!" --spacing "!SPACING!" --grid_size "!GRID_SIZE!"
)

endlocal