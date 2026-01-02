import os
import sys
import sysconfig
import subprocess

from pathlib import Path


def main():
    """
    Wrapper for the Rust implementation of the slideshow daemon.
    """
    # Find project root
    current_file = Path(__file__).resolve()
    # backend/src/utils/slideshow_daemon.py -> backend/src/utils -> backend/src -> backend -> Image-Toolkit
    project_root = current_file.parent.parent.parent.parent
    
    # Path to the Rust binary
    # We check debug first, then release
    bin_name = "slideshow_daemon"
    debug_bin = project_root / "target" / "debug" / bin_name
    release_bin = project_root / "target" / "release" / bin_name
    
    if release_bin.exists():
        bin_path = release_bin
    elif debug_bin.exists():
        bin_path = debug_bin
    else:
        print(f"Error: Rust binary not found at {debug_bin} or {release_bin}.")
        print("Please build the Rust project first using 'cargo build --bin slideshow_daemon'.")
        sys.exit(1)

    # Set up environment (LD_LIBRARY_PATH for Python linking)
    env = os.environ.copy()
    lib_dir = sysconfig.get_config_var('LIBDIR')
    if lib_dir:
        current_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{lib_dir}:{current_ld}".strip(":")

    print(f"Launching Rust Slideshow Daemon: {bin_path}")
    
    try:
        # Run the binary, passing through any arguments
        subprocess.run([str(bin_path)] + sys.argv[1:], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Slideshow Daemon exited with error: {e}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nSlideshow Daemon stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
