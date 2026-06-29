@echo off
setlocal enabledelayedexpansion

:: Set manager to 'uv' if no argument is provided, otherwise use the argument
set MANAGER=%1
if "%MANAGER%"=="" set MANAGER=uv

echo Using manager: %MANAGER%

:: Check manager type and execute appropriate commands
if "%MANAGER%"=="uv" (
    :: Check if uv is installed
    uv --version >nul 2>&1
    if !errorlevel! == 1 (
        echo Warning: uv is not installed or not in PATH
        echo Installing uv...
        
        :: Install uv using the official installer
        powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        
        :: Source the profile to make uv available in current session
        if exist "%USERPROFILE%\.cargo\env.bat" call "%USERPROFILE%\.cargo\env.bat"
    )
    
    :: Initialize project with Python 3.11
    uv init --python 3.11

    :: Create and activate virtual environment
    uv venv env\img_db
    call env\img_db\Scripts\activate.bat

    :: Install requirements
    uv pip install -r env\requirements.txt
) else if "%MANAGER%"=="conda" (
    :: Check if conda is installed
    conda --version >nul 2>&1
    if !errorlevel! == 1 (
        echo Warning: conda is not installed or not in PATH
        echo Installing conda...
        
        :: Download conda installer
        echo Downloading Anaconda installer...
        powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Windows-x86_64.exe' -OutFile 'Anaconda3-installer.exe'"
        
        :: Install conda silently
        if exist Anaconda3-installer.exe (
            echo Installing Anaconda (this may take a few minutes)...
            Anaconda3-installer.exe /S /D=%USERPROFILE%\Anaconda3
        ) else (
            echo Error: Failed to download Anaconda installer
            exit /b 1
        )


        :: Add conda to PATH for current session
        if exist "%USERPROFILE%\Anaconda3" (
            set "PATH=%USERPROFILE%\Anaconda3;%USERPROFILE%\Anaconda3\Scripts;%USERPROFILE%\Anaconda3\Library\bin;%PATH%"
        
            :: Initialize conda
            echo Initializing conda...
            call conda init cmd.exe
        ) else (
            echo Error: Anaconda installation failed
            exit /b 1
        )
        
        :: Clean up installer
        if exist Anaconda3-installer.exe del Anaconda3-installer.exe
    )
    
    :: Create conda environment with dependencies
    if exist "env\environment.yml" (
        conda env create --file env\environment.yml -y
    ) else (
        conda create --name wsr python=3.11 -y
    )

    :: Activate conda environment
    call conda activate img_db
) else if "%MANAGER%"=="venv" (
    :: Check if Python is installed
    python --version >nul 2>&1
    if errorlevel == 1 (
        echo Error: Python is not installed or not in PATH
        exit /b 1
    )
    
    :: Create and activate virtual environment
    python -m venv env\.img_db
    call env\.img_db\Scripts\activate.bat

    :: Install requirements
    pip install -r env\requirements.txt
) else (
    echo Error: unknown manager selected.
    exit /b 1
)

echo Setup completed successfully with %MANAGER%
endlocal