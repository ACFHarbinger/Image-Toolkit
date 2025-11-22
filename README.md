# Image-Toolkit
Image database and edit toolkit.

## Tech Stack
- [Python Programming Language](https://www.python.org/)
- [PySide Framework](https://doc.qt.io/qtforpython-6/gettingstarted.html#getting-started)
- [Kotlin Programming Language](https://kotlinlang.org/)
- [TypeScript Programming Language](https://www.typescriptlang.org/)
- [React Framework](https://react.dev/)

## Setup Dependencies
You need to have binuntils to install the app using pyinstaller:
```bash
sudo apt install binutils
```

You also need to install qdbus6 for setting wallpapers on KDE Plasma:
```bash
sudo apt install qdbus-qt6 qt6-base-dev-tools
```

You can choose to install the rest of this repository's dependencies using any of the following methods below.

### Setup Python Dependencies
#### UV
To use the [UV Python package and project manager](https://github.com/astral-sh/uv) to setup the virtual environment, you first need to create the environment using the specified Python version (you can skip the next 2 steps if you dont want to build the project from scract, as the pyproject.toml file is already commited to the repository)
```bash
uv init --python 3.11 --name image-toolkit
```

and then install the required dependencies.
```bash 
uv add -r env/requirements.txt
uv add --dev env/dev_requirements.txt
```

You can also just do:
```bash
uv sync [--no-dev]
```

Afterwards, you can initialize the virtual environment by running one of the following commands:
- On the Linux CLI: `source .venv/bin/activate`
- On the Windows CMD: `.venv\Scripts\activate.bat`
- On the Windows PS: `.venv\Scripts\Activate.ps1`

Also, if you want to deactivate and/or delete the created virtual environment you can execute the following command(s).
```bash
deactivate
rm -rf .venv
```

##### UV Installation
To install uv, you simply need to execute the command `curl -LsSf https://astral.sh/uv/install.sh | sh` on the terminal (or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` on the Windows PowerShell).


#### Anaconda Environment
To setup the environment for the project using the [Anaconda distribution](https://www.anaconda.com/), you just need to run the following commands in the main directory:
```bash
conda env create --file env/environment.yml -y --name img_db
conda activate img_db
```

To list the installed packages (and their respective versions), just run the following command after activating the Conda environment:
```bash
conda list
```

and if you want to deactivate and/or delete the previously created Conda environment:
```bash
conda deactivate
conda remove -n img_db --all -y
```

##### Conda Installation
If you need to install conda beforehand, you just need to run the following commands (while replacing the variables for the values you want to use, which determine your Anaconda version):
```bash
curl -O https://repo.anaconda.com/archive/Anaconda3-<year>.<month>-<version_id>-Linux-x86_64.sh
bash Anaconda3-<year>.<month>-<version_id>-Linux-x86_64.sh
```
For this project, we used Anaconda 3 with year=2024, month=10, version_id=1.

#### Virtual Environment
To setup the virtual environment for the project using the Pip package installer and Python's venv module:
```bash
python3 -m venv env/.img_db
source env/.img_db/bin/activate
pip install -r env/requirements.txt
```

After activating the virtual environment, you can list the installed packages in a similar manner to Conda by using Pip:
```bash
pip list
```

and if you want to deactivate and/or delete the created virtual environment:
```bash
deactivate
rm -rf env/.img_db
```

### Setup C++ Dependencies:
You need to run the following command:
```bash
sudo apt install libgtest-dev libopencv-de libxext-dev libxt-dev libxrender-dev libpqxx-dev libgumbo-dev nlohmann-json3-dev libcxxopts-dev
```

## Usage
Before you start the program, you must initialize the PostgreSQL Database by running one of the following commands:
- On the Linux CLI: `sudo systemctl start postgresql`
- On the Windows CMD: `net start postgresql-x64-18`
- On the macOS Terminal: `brew services start postgresql`

Afterwards, you can stop the Database by running one of the following commands:
- On the Linux CLI: `brew services stop postgresql`
- On the Windows CMD: `net stop postgresql-x64-18`
- On the macOS Terminal: `brew services stop postgresql`

You can download and install PostgreSQL [from this website](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).

After installing PostgreSQL, you can use the `psql -U postgres -d img_db` command to connect to the database (and `exit` to leave it).

Note: you also need to instal pgvector from the [official github](https://github.com/pgvector/pgvector) in order to access full database functionality.

### Convert Image Format
You can either convert a single image at a time, like so (taking into account that the output_path should be written without the file extension, which is given by the format)
```bash
python main.py convert --output_format png --input_path <path_to_img> --output_path <path_new_img>
```

or batch convert all images in a directory that match one (or more) image formats.
```bash
python main.py convert --output_format png --input_path <path_to_dir> --input_formats webp avif --output_path <path_new_dir>
```

Note: if no --output_path argument is given, the new image will have the same name (or the images will be generated in the same directory, in the case of batch conversion), just with a different file extension.

## Build
### Python
To build the desktop app part of the project, you just need to run the following command:
```bash
pyinstaller --clean app.spec
```

### Core and Web
To build the core and web parts of the project, you need to run the following commands:
```bash
mkdir build
cd build
cmake ..
cmake --build . --clean-first
make
```

## Testing
### Python
You can run a test suite for all python functionality by simply running the following command:
```bash
pytest 
```

### Java
To test the Java portion of the project, you just need to do `mvn test`