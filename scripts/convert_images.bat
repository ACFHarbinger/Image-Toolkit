@echo off
setlocal

set IN_PATH=
set OUT_FORMAT=png
set OUT_PATH=
rem For multiple formats, set them as space-separated values
set IN_FORMATS=jpg png

if defined OUT_PATH (
    python main.py convert --output_format "%OUT_FORMAT%" --input_path "%IN_PATH%" --output_path "%OUT_PATH%" --input_formats %IN_FORMATS%
) else (
    python main.py convert --output_format "%OUT_FORMAT%" --input_path "%IN_PATH%" --input_formats %IN_FORMATS%
)

endlocal