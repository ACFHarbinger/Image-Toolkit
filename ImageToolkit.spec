# -- mode: python ; coding: utf-8 --

# To build: pyinstaller ImageToolkit.spec [--clean]

import PySide6
import os

pyside_path = os.path.dirname(PySide6.__file__)

# pathex=['.'] means it looks in the current directory (where ImageToolkit.spec is)

pathex=['/backend', '/gui']

a = Analysis(
    ['__main__.py'],  # Your main entry point file
    pathex=['/backend', '/gui'],

    binaries=[],
    datas=[],

    # Add hidden imports for modules that PyInstaller might miss, especially
    # components of your project structure (like the modules in your 'src' folder)
    hiddenimports=[
        # Core modules PyInstaller often needs for PySide6/subprocess interactions
        'PySide6.QtSvg',
        'PySide6.QtXml',

        # Add your own module imports explicitly if they are not in __main__.py:
        # e.g., 'src.gui.tabs.wallpaper_tab',
        # e.g., 'src.gui.tabs.search_tab',
        # If your modules are correctly packaged and imported in __main__.py,
        # PyInstaller usually finds them. If the build fails later, add them here.
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=None,
    key=None,
    collect_all=[],
    collect_submodules=[],
    collect_data=[(pyside_path, 'PySide6')], # Include PySide6 data globally
    collect_entrypoints=[],
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_clean_pkgname=[],
    icon='assets/images/image_toolkit_icon.ico'
)


a.datas += Tree(os.path.join(pyside_path, 'Qt', 'plugins', 'platforms'), prefix='PySide6/Qt/plugins/platforms')


pyz = PYZ(a.pure, a.zipped_data,
    cipher=None
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ImageToolkitApp', # Name of the executable file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Use 'False' for a GUI application (no command line window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/images/image_toolkit_icon.ico'
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ImageToolkit' # Name of the final folder/bundle
)