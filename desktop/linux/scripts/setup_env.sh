#!/bin/bash

# Set manager to 'uv' if no argument is provided, otherwise use the argument
MANAGER=${1:-uv}

echo "Using manager: $MANAGER"

# Check manager type and execute appropriate commands
if [ "$MANAGER" = "uv" ]; then
    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        echo "Warning: uv is not installed or not in PATH"
        echo "Installing uv..."

        # Install uv using the official installer
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Source the profile to make uv available in current session
        source "$HOME/.local/bin/env"
    fi

    # Initialize project with Python 3.11
    uv init --python 3.11

    # Create and activate virtual environment
    uv venv env/img_db
    source env/img_db/bin/activate

    # Install requirements
    uv pip install -r env/requirements.txt
elif [ "$MANAGER" = "conda" ]; then
    # Check if conda is installed
    if ! command -v conda &> /dev/null; then
        echo "Warning: conda is not installed or not in PATH"
        echo "Installing conda..."
        
        # Download conda installer
        echo "Downloading Anaconda installer..."
        curl -O https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Linux-x86_64.sh
        
        # Make installer executable
        chmod +x Anaconda3-2024.10-1-Linux-x86_64.sh
        
        # Install conda silently
        echo "Installing Anaconda (this may take a few minutes)..."
        bash Anaconda3-2024.10-1-Linux-x86_64.sh -b -p "$HOME/anaconda3"
        
        # Initialize conda for shell
        echo "Initializing conda..."
        "$HOME/anaconda3/bin/conda" init bash
        
        # Source conda to make it available in current session
        source "$HOME/anaconda3/etc/profile.d/conda.sh"

        # Clean up installer
        rm Anaconda3-2024.10-1-Linux-x86_64.sh
    fi

    # Create conda environment with dependencies
    conda env create --file env/environment.yml -y

    # Activate conda environment
    conda activate img_db
elif [ "$MANAGER" = "venv" ]; then
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is not installed or not in PATH"
        exit 1
    fi

    # Create and activate virtual environment
    python3 -m venv env/.img_db
    source env/.img_db/bin/activate

    # Install requirements
    pip install -r env/requirements.txt
else
    echo "Error: unknown manager selected."
    exit 1
fi

echo "Setup completed successfully with $MANAGER"