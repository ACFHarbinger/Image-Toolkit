import sys
from pathlib import Path

# Project Root
if getattr(sys, "frozen", False):
    ROOT_DIR = (
        Path(sys._MEIPASS)
        if hasattr(sys, "_MEIPASS")
        else Path(sys.executable).resolve().parent
    )
else:
    ROOT_DIR = Path(__file__).resolve().parents[3]

# System Dirs
IMAGE_TOOLKIT_DIR = Path.home() / ".image-toolkit"
THUMBNAIL_CACHE_DIR = IMAGE_TOOLKIT_DIR / "thumbnail-cache"
# Previously redeclared identically as _DEFAULT_INDEX_DIR in both
# core/cbir_search.py (reader) and models/tuning/cbir_index_builder.py (writer).
CBIR_INDEX_DIR = IMAGE_TOOLKIT_DIR / "cbir_index"

# Base Dirs
BACKEND_DIR = ROOT_DIR / "backend"
ASSETS_DIR = ROOT_DIR / "assets"
SECRETS_DIR = ASSETS_DIR / "secrets"
LOCAL_SECRETS_DIR = IMAGE_TOOLKIT_DIR / "secrets"
IMAGES_DIR = ASSETS_DIR / "images"
API_DIR = ASSETS_DIR / "api"
CONFIGS_DIR = ROOT_DIR / "configs"

# Files
_crypto_lib_name = "libitk_crypto.dll" if sys.platform == "win32" else "libitk_crypto.so"


def _git_common_checkout_root(root: Path) -> Path | None:
    """If ``root`` is a linked git worktree, return the main checkout.

    Isolated D12 worktrees do not copy ``just build-base`` artifacts
    (``libitk_crypto.so`` lives next to the compiled ``base`` extension in
    the primary clone). The worktree's ``.git`` file points at
    ``<main>/.git/worktrees/<name>``.
    """
    git = root / ".git"
    if not git.is_file():
        return None
    try:
        text = git.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if not line.startswith("gitdir:"):
            continue
        gitdir = Path(line.split(":", 1)[1].strip())
        if gitdir.parent.name == "worktrees":
            return gitdir.parent.parent.parent
    return None


def resolve_crypto_lib_file() -> str:
    """Locate ``libitk_crypto.so``, built as part of ``just build-base``.

    Crypto is not a separate module: ``base/CMakeLists.txt`` compiles
    ``base/src/secret/itk_crypto.c`` into this shared library. Search the
    source tree, a linked main checkout (git worktrees), ``sys.path``, and
    the frozen-bundle directory. Prefer the project-root install over
    ``build/crypto/`` so a stale cmake output cannot shadow it.
    """
    roots: list[Path] = [ROOT_DIR]
    main_checkout = _git_common_checkout_root(ROOT_DIR)
    if main_checkout is not None:
        roots.append(main_checkout)
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    for entry in sys.path:
        if entry:
            roots.append(Path(entry))

    seen: set[str] = set()
    fallback = str(ROOT_DIR / "build" / "crypto" / _crypto_lib_name)
    for root in roots:
        for candidate in (
            root / _crypto_lib_name,
            root / "build" / "crypto" / _crypto_lib_name,
        ):
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file():
                return key
    return fallback


# Resolved at import for callers that still read the constant; vault_manager
# re-resolves at load so a worktree launched with PYTHONPATH still finds the
# library built in the main checkout.
CRYPTO_LIB_FILE = resolve_crypto_lib_file()

ICON_FILE = str(IMAGES_DIR / "image_toolkit_icon.png")
DAEMON_CONFIG_PATH = IMAGE_TOOLKIT_DIR / ".slideshow_config.json"
MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH = IMAGE_TOOLKIT_DIR / ".monitor_slideshow_daemon.json"

# API / Auth Files
GOOGLE_API_FILE = str(API_DIR / "google_api_key.json")
SERVICE_ACCOUNT_FILE = str(API_DIR / "image_toolkit_service.json")
CLIENT_SECRETS_FILE = str(API_DIR / "client_secret.json")
TOKEN_FILE = str(API_DIR / "token.json")

# Secrets Files (Templates/Defaults)
BASE_KEYSTORE_FILE = str(SECRETS_DIR / "my_keystore.p12")
BASE_VAULT_FILE = str(SECRETS_DIR / "my_secure_data.vault")
BASE_PEPPER_FILE = str(SECRETS_DIR / "pepper.txt")

# Other
LOCAL_SOURCE_PATH = str(Path.home() / "Downloads" / "Data")
