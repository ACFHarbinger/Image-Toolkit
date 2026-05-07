import os
import subprocess
import sys
from pathlib import Path


def start_daemon(debug: bool = False):
    """
    Launch the Rust slideshow daemon binary.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    
    # Priority: release, then debug
    candidates = [
        project_root / "target" / "release" / "slideshow_daemon",
        project_root / "target" / "debug" / "slideshow_daemon",
        project_root / "base" / "target" / "release" / "slideshow_daemon",
    ]
    
    bin_path = None
    for cand in candidates:
        if cand.exists():
            bin_path = cand
            break
            
    if not bin_path:
        print("ERROR: slideshow_daemon binary not found. Please run 'cargo build --release' in 'base/'")
        return

    env = os.environ.copy()
    # Add project root to library path for native extensions
    if "LD_LIBRARY_PATH" in env:
        env["LD_LIBRARY_PATH"] = f"{project_root}:{env['LD_LIBRARY_PATH']}"
    else:
        env["LD_LIBRARY_PATH"] = str(project_root)

    args = [str(bin_path)]
    if debug:
        args.append("--debug")

    try:
        # Launch as background process
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        print(f"Slideshow daemon started (debug={debug}).")
    except Exception as e:
        print(f"Failed to launch slideshow daemon: {e}")


if __name__ == "__main__":
    is_debug = "--debug" in sys.argv
    start_daemon(debug=is_debug)
