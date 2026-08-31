# -- mode: python ; coding: utf-8 --
# PyInstaller build specification for Image-Toolkit desktop application.
# To build: pyinstaller --clean ImageToolkit.spec

import glob
import os
import sys

# PyInstaller injects SPECPATH, Analysis, PYZ, EXE, COLLECT at runtime
spec_root = globals().get("SPECPATH", os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.abspath(spec_root)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Submodule paths
asp_backend_path = os.path.join(ROOT_DIR, 'submodules', 'ASP', 'backend', 'src')
asp_gui_path = os.path.join(ROOT_DIR, 'submodules', 'ASP', 'gui', 'src')
csg_logic_path = os.path.join(ROOT_DIR, 'submodules', 'CSG', 'logic', 'src')
csg_gui_path = os.path.join(ROOT_DIR, 'submodules', 'CSG', 'gui', 'src')
hie_middleware_path = os.path.join(ROOT_DIR, 'submodules', 'HIE', 'middleware', 'src')
hie_gui_path = os.path.join(ROOT_DIR, 'submodules', 'HIE', 'gui', 'src')

pathex = [
    ROOT_DIR,
    os.path.join(ROOT_DIR, 'backend'),
    os.path.join(ROOT_DIR, 'gui'),
    os.path.join(ROOT_DIR, 'git'),
    asp_backend_path,
    asp_gui_path,
    csg_logic_path,
    csg_gui_path,
    hie_middleware_path,
    hie_gui_path,
]

# Helper to enumerate all Python module names under a directory
def find_python_modules(base_dir, prefix=''):
    modules = []
    if not os.path.isdir(base_dir):
        return modules
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.py') and not f.startswith('.'):
                rel = os.path.relpath(os.path.join(root, f), base_dir)
                mod = rel.replace('/', '.').replace('\\', '.')
                if mod.endswith('.__init__.py'):
                    mod = mod[:-12]
                elif mod.endswith('.py'):
                    mod = mod[:-3]
                if mod:
                    modules.append(prefix + mod if prefix else mod)
    return modules

# Enumerate modules
hidden_modules = set()
hidden_modules.update(find_python_modules(os.path.join(ROOT_DIR, 'backend', 'src'), 'backend.src.'))
hidden_modules.update(find_python_modules(os.path.join(ROOT_DIR, 'backend', 'controllers'), 'backend.controllers.'))
hidden_modules.update(find_python_modules(os.path.join(ROOT_DIR, 'gui', 'src'), 'gui.src.'))
hidden_modules.update(find_python_modules(os.path.join(ROOT_DIR, 'git', 'scripts'), 'git.scripts.'))
hidden_modules.update(find_python_modules(asp_backend_path, 'asp_backend.'))
hidden_modules.update(find_python_modules(asp_gui_path, 'asp_gui.'))
hidden_modules.update(find_python_modules(csg_gui_path, 'csg_gui.'))

# Standard and third-party hidden imports
third_party_hidden = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtXml',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPrintSupport',
    'sqlcipher3',
    'pysqlcipher3',
    'sqlite3',
    'psycopg2',
    'psycopg',
    'PIL',
    'PIL.Image',
    'PIL.PngImagePlugin',
    'PIL.JpegImagePlugin',
    'cv2',
    'numpy',
    'scipy',
    'yaml',
    'json',
    'requests',
    'urllib3',
    'backend.src._version',
]
hidden_modules.update(third_party_hidden)

# Datas to bundle
datas = [
    (os.path.join(ROOT_DIR, 'assets'), 'assets'),
    (os.path.join(ROOT_DIR, 'configs'), 'configs'),
]

# Database schemas if not covered by package
schema_path = os.path.join(ROOT_DIR, 'backend', 'src', 'database', 'unified')
if os.path.isdir(schema_path):
    datas.append((schema_path, os.path.join('backend', 'src', 'database', 'unified')))

# Submodules tree if present
submodules_dir = os.path.join(ROOT_DIR, 'submodules')
if os.path.isdir(submodules_dir):
    datas.append((submodules_dir, 'submodules'))

# Binaries: native crypto library and C++ base extension
binaries = []
crypto_lib_so = os.path.join(ROOT_DIR, 'build', 'crypto', 'libitk_crypto.so')
crypto_lib_dll = os.path.join(ROOT_DIR, 'build', 'crypto', 'libitk_crypto.dll')
if os.path.exists(crypto_lib_so):
    binaries.append((crypto_lib_so, 'build/crypto'))
    binaries.append((crypto_lib_so, '.'))
if os.path.exists(crypto_lib_dll):
    binaries.append((crypto_lib_dll, 'build/crypto'))
    binaries.append((crypto_lib_dll, '.'))

for base_lib in (
    glob.glob(os.path.join(ROOT_DIR, 'base*.so'))
    + glob.glob(os.path.join(ROOT_DIR, 'base*.pyd'))
    + glob.glob(os.path.join(ROOT_DIR, 'build', 'base', 'base*.so'))
    + glob.glob(os.path.join(ROOT_DIR, 'build', 'base', 'base*.pyd'))
):
    binaries.append((base_lib, '.'))

# Select application icon based on platform
icon_ico = os.path.join(ROOT_DIR, 'assets', 'images', 'image_toolkit_icon.ico')
icon_png = os.path.join(ROOT_DIR, 'assets', 'images', 'image_toolkit_icon.png')
app_icon = icon_ico if os.path.exists(icon_ico) and sys.platform == 'win32' else icon_png

a = Analysis(
    ['gui/__main__.py'],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(list(hidden_modules)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib.tests', 'pytest'],
    noarchive=False,
    optimize=0,
    cipher=None,
    key=None,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ImageToolkitApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon if os.path.exists(app_icon) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ImageToolkit',
)