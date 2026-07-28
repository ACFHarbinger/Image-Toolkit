"""Top-level CLI command router and command-group implementations.

`main.py` parses argv into `(command, opts)` via
:mod:`backend.src.utils.io.arg_parser` and hands both to
:func:`dispatch_command`, which routes to one of the `dispatch_*` functions
below — one per command group (`core`, `web`, `database`, `model`, `stitch`,
`update-settings`). Kept in a single module rather than one file per group:
each group's own logic is small (dozens of lines), and main.py only ever
needs `dispatch_command` from here regardless of how many groups exist.
"""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import json
import os
import re
import sys

import yaml
from PySide6.QtCore import QSettings

import backend.src.constants as udef
from backend.src.constants import BACKEND_DIR
from backend.src.core.image_converter import ImageFormatConverter
from backend.src.core.image_merger import ImageMerger
from backend.src.core.vault_manager import VaultManager
from backend.src.utils.display.slideshow_daemon import run as launch_slideshow
from backend.src.web.crawlers.image_crawler import ImageCrawler

# ─────────────────────────── core: convert / merge / stitch ───────────────


def dispatch_core(args: dict) -> None:
    command = args.get("core_command")
    if command == "convert":
        inputs = args.get("input")
        output = args.get("output")
        fmt = args.get("format")
        recursive = args.get("recursive", False)

        # Determine if single or batch
        if len(inputs) == 1 and os.path.isfile(inputs[0]):
            success = ImageFormatConverter.convert_single_image(
                image_path=inputs[0],
                output_name=output,
                format=fmt,
            )
            print(
                f"Conversion {'successful' if success else 'failed'}", file=sys.stderr
            )
        else:
            # Batch conversion — multiple inputs or a directory
            for input_path in inputs:
                if os.path.isdir(input_path):
                    ImageFormatConverter.convert_batch(
                        input_dir=input_path,
                        inputs_formats=[
                            "webp",
                            "png",
                            "jpg",
                            "jpeg",
                            "bmp",
                            "gif",
                            "tiff",
                            "avif",
                        ],
                        output_dir=output,
                        output_format=fmt,
                        recursive=recursive,
                    )
                elif os.path.isfile(input_path):
                    success = ImageFormatConverter.convert_single_image(
                        image_path=input_path,
                        output_name=output,
                        format=fmt,
                    )
    elif command == "stitch":
        # Load defaults from Hydra config if available
        config_path = os.path.join(BACKEND_DIR, "config", "core", "stitch.yaml")
        defaults = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                defaults = yaml.safe_load(os.path.expandvars(f.read())) or {}

        inputs = args.get("input") or [defaults.get("input_dir")]
        output = args.get("output") or defaults.get(
            "output_path", "/tmp/stitched_panorama.png"
        )

        # Filter out None if both CLI and config are empty
        inputs = [i for i in inputs if i]
        if not inputs:
            print(
                "❌ Error: No input directory specified in CLI or stitch.yaml",
                file=sys.stderr,
            )
            return
        image_paths = []
        for inp in inputs:
            if os.path.isdir(inp):
                # Get images from dir, excluding the output file if it's in the same dir
                images = [
                    os.path.join(inp, f)
                    for f in os.listdir(inp)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                    and os.path.realpath(os.path.join(inp, f))
                    != os.path.realpath(output)
                ]
                image_paths.extend(sorted(images))
            elif os.path.isfile(inp):
                image_paths.append(inp)

        if len(image_paths) < 2:
            print("❌ Error: Need at least 2 images for stitching.", file=sys.stderr)
            return

        print(f"🚀 Starting Perfect Stitch on {len(image_paths)} frames...")
        merger = ImageMerger()
        try:
            # Use default settings from stitch.yaml via Hydra or explicit params
            # For now we use the merger's default which delegates to the pipeline
            merger.perfect_stitch(image_paths, output)
            print(f"✅ Panorama saved to: {output}")
        except Exception as e:
            print(f"❌ Stitching failed: {e}", file=sys.stderr)
    elif command == "merge":
        # Placeholder for other merge modes
        print("Merge command not yet fully connected to CLI", file=sys.stderr)


# ─────────────────────────────────── web: crawl ────────────────────────────


def dispatch_web(args: dict) -> None:
    command = args.get("web_command")
    if command == "crawl":
        try:
            config = {
                "url": args.get("query"),
                "download_dir": args.get("output"),
                "limit": args.get("limit"),
                "type": "general",
                "headless": True,
                "browser": "chrome",
            }

            crawler = ImageCrawler(config)

            # Connect signals to print to terminal for CLI usage
            crawler.on_status.connect(lambda msg: print(f"[*] {msg}"))
            crawler.on_finished.connect(lambda msg: print(f"[+] {msg}"))

            print(f"🚀 Starting web crawler for: {config['url']}")
            crawler.run()
        except ImportError as e:
            print(f"❌ Error: Required modules not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Web crawler failed: {e}", file=sys.stderr)
    else:
        print(f"Web command '{command}' not yet connected to CLI", file=sys.stderr)


# ───────────────────────────────── database: search ────────────────────────
# DB.6 — the library moved from a standalone Postgres database to a
# session-keyed unified store, so this CLI command can only run against an
# already-open session (e.g. invoked from within the running app post
# vault-unlock).


def dispatch_database(args: dict) -> None:
    command = args.get("db_command")
    if command == "search":
        query = args.get("query", "")
        limit = args.get("limit", 50)
        try:
            from backend.src.database.unified import session
            from backend.src.database.unified.facade import UnifiedImageDatabase

            db = UnifiedImageDatabase(session.get_session())
            results = db.search_images(filename_pattern=query, limit=limit)
            if not results:
                print("No results found.")
                return
            for img in results:
                print(
                    f"{img.get('id', '?'):>6} | {img.get('filename', '')} | "
                    f"{img.get('group_name', '')} / {img.get('subgroup_name', '')} | "
                    f"tags: {', '.join(img.get('tags', []))}"
                )
        except ImportError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Database search failed: {e}", file=sys.stderr)
    else:
        print(f"Database command '{command}' is not recognised.", file=sys.stderr)
        print("Available commands: search", file=sys.stderr)


# ───────────────────────────── model: ad-hoc SD3 generation ────────────────


def dispatch_model(args: dict) -> None:
    command = args.get("model_command")
    if command == "generate":
        prompt = args.get("prompt", "")
        output = args.get("output", "output.png")
        model_name = args.get("model", "stable-diffusion")
        try:
            from backend.src.models.wrappers.sd3_wrapper import SD3Wrapper

            print(f"🚀 Generating image with {model_name}: {prompt!r}")
            wrapper = SD3Wrapper()
            wrapper.generate_image(
                prompt=prompt, model_path=model_name, output_path=output
            )
            print(f"✅ Image saved to: {output}")
        except ImportError as e:
            print(f"❌ Error: Required modules not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Generation failed: {e}", file=sys.stderr)
    else:
        print(f"Model command '{command}' is not recognised.", file=sys.stderr)
        print("Available commands: generate", file=sys.stderr)


# ───────────── stitch: top-level `stitch` command (single or --batch-dir) ──
# Distinct from the `core stitch` subcommand above, which goes through
# ImageMerger instead of AnimeStitchPipeline.

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _collect_image_paths(directory: str) -> list:
    """Return sorted image paths from a directory (non-recursive)."""
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in _IMG_EXTS
    )


def _run_single_stitch(image_paths: list, output: str, renderer: str) -> bool:
    """Run AnimeStitchPipeline on image_paths; return True on success."""
    from backend.src.animation import AnimeStitchPipeline

    pipeline = AnimeStitchPipeline(renderer=renderer)
    try:
        pipeline.run(image_paths=image_paths, output_path=output)
        return True
    except Exception as exc:
        print(f"  ❌ Stitching failed: {exc}", file=sys.stderr)
        return False


def dispatch_stitch(args: dict) -> None:  # noqa: C901
    batch_dir = (args.get("batch_dir") or "").strip()
    renderer = args.get("renderer") or "median"
    resume = bool(args.get("resume"))

    if batch_dir:
        # ── Batch mode ─────────────────────────────────────────────────────
        if not os.path.isdir(batch_dir):
            print(f"❌ --batch-dir '{batch_dir}' is not a directory.", file=sys.stderr)
            return

        suffix = (args.get("output_suffix") or "_stitched").strip()
        progress_path = os.path.join(batch_dir, ".stitch_progress.json")

        # Load progress state (Option E)
        progress: dict = {}
        if resume and os.path.isfile(progress_path):
            try:
                with open(progress_path) as f:
                    progress = json.load(f)
            except Exception:
                progress = {}

        subdirs = sorted(
            d.path
            for d in os.scandir(batch_dir)
            if d.is_dir() and not d.name.startswith(".")
        )
        if not subdirs:
            print(f"❌ No sub-directories found in '{batch_dir}'.", file=sys.stderr)
            return

        total = len(subdirs)
        done = skipped = failed = 0
        print(f"📂 Batch stitch: {total} sequence(s) in '{batch_dir}'")
        for i, seq_dir in enumerate(subdirs, 1):
            seq_name = os.path.basename(seq_dir)
            out_path = os.path.join(seq_dir, f"{seq_name}{suffix}.png")

            # Option C: resume — skip if output already exists
            if resume and (
                os.path.isfile(out_path) or progress.get(seq_name) == "done"
            ):
                print(f"  [{i}/{total}] ⏭  {seq_name}  (skipped — output exists)")
                skipped += 1
                continue

            image_paths = _collect_image_paths(seq_dir)
            if len(image_paths) < 2:
                print(
                    f"  [{i}/{total}] ⚠  {seq_name}  (skipped — fewer than 2 images)",
                    file=sys.stderr,
                )
                progress[seq_name] = "skipped"
                failed += 1
                continue

            print(
                f"  [{i}/{total}] 🚀 {seq_name}  ({len(image_paths)} frames) → {out_path}"
            )
            success = _run_single_stitch(image_paths, out_path, renderer)
            if success:
                print(f"  [{i}/{total}] ✅ {seq_name}")
                progress[seq_name] = "done"
                done += 1
            else:
                progress[seq_name] = "failed"
                failed += 1

            # Persist progress after each sequence (Option E)
            try:
                with open(progress_path, "w") as f:
                    json.dump(progress, f, indent=2)
            except Exception:
                pass

        print(f"\n📊 Batch complete: {done} done, {skipped} skipped, {failed} failed.")

    else:
        # ── Single-sequence mode ────────────────────────────────────────────
        inputs = args.get("input") or []
        output = (args.get("output") or "").strip() or "stitched_panorama.png"

        image_paths: list = []
        for inp in inputs:
            if os.path.isdir(inp):
                image_paths.extend(_collect_image_paths(inp))
            elif os.path.isfile(inp):
                image_paths.append(inp)

        if len(image_paths) < 2:
            print("❌ Need at least 2 images for stitching.", file=sys.stderr)
            return

        print(f"🚀 Stitching {len(image_paths)} frames → {output}")
        if _run_single_stitch(image_paths, output, renderer):
            print(f"✅ Panorama saved to: {output}")


# ────────────── update-settings: bulk vault/QSettings find-replace ─────────


def _recursive_replace(val, search: str, replace: str, use_regex: bool):
    """Apply search/replace to every string leaf in a str/dict/list value;
    return (new_val, replacement_count)."""
    local_count = 0
    if isinstance(val, str):
        if use_regex:
            try:
                new_val, count = re.subn(search, replace, val)
                return new_val, count
            except Exception:
                new_val = val.replace(search, replace)
                count = val.count(search)
                return new_val, count
        else:
            new_val = val.replace(search, replace)
            count = val.count(search)
            return new_val, count
    elif isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            new_v, count = _recursive_replace(v, search, replace, use_regex)
            new_dict[k] = new_v
            local_count += count
        return new_dict, local_count
    elif isinstance(val, list):
        new_list = []
        for item in val:
            new_item, count = _recursive_replace(item, search, replace, use_regex)
            new_list.append(new_item)
            local_count += count
        return new_list, local_count
    return val, 0


def dispatch_update_settings(args: dict) -> None:
    search = args.get("search")
    replace = args.get("replace")
    use_regex = args.get("regex", False)
    account = args.get("account", "a")
    password = args.get("password")

    if not search:
        print("❌ Error: --search pattern is required.", file=sys.stderr)
        return

    # Update cryptographic paths for the specified account
    udef.update_cryptographic_values(account)

    if not password:
        password = getpass.getpass(prompt=f"Enter Master Password for account '{account}': ")

    print(f"🔒 Initializing secure vault for account '{account}'...")
    try:
        vault_manager = VaultManager()
        vault_manager.load_keystore(udef.KEYSTORE_FILE, password)
        vault_manager.get_secret_key(udef.KEY_ALIAS, password)
        vault_manager.init_vault(udef.VAULT_FILE)
        stored_data = vault_manager.load_account_credentials()
    except Exception as e:
        print(f"❌ Failed to load secure vault: {e}", file=sys.stderr)
        return

    # Verify password hash
    stored_hash = stored_data.get("hashed_password")
    stored_salt = stored_data.get("salt")
    pepper = vault_manager.PEPPER
    password_combined = (password + stored_salt + pepper).encode("utf-8")
    verification_hash = hashlib.sha256(password_combined).hexdigest()
    if verification_hash != stored_hash:
        print("❌ Error: Invalid password.", file=sys.stderr)
        return

    print("✅ Vault unlocked successfully.")

    # 1. Update Vault
    updated_data, vault_count = _recursive_replace(stored_data, search, replace, use_regex)
    if vault_count > 0:
        try:
            vault_manager.save_data(json.dumps(updated_data))
            print(f"✅ Updated {vault_count} values/fields in the Secure Vault.")
        except Exception as e:
            print(f"❌ Failed to save updated vault data: {e}", file=sys.stderr)
            return
    else:
        print("ℹ️ No matching fields found in Secure Vault.")

    # 2. Update QSettings
    qsettings_count = 0
    try:
        qsettings = QSettings("ImageToolkit", "ImageToolkit")
        for key in qsettings.allKeys():
            val = qsettings.value(key)
            if isinstance(val, (str, list, dict)):
                new_val, count = _recursive_replace(val, search, replace, use_regex)
                if count > 0:
                    qsettings.setValue(key, new_val)
                    qsettings_count += count
        if qsettings_count > 0:
            print(f"✅ Updated {qsettings_count} values/fields in QSettings.")
        else:
            print("ℹ️ No matching fields found in QSettings.")
    except Exception as e:
        print(f"❌ Failed to update QSettings: {e}", file=sys.stderr)
        return

    with contextlib.suppress(Exception):
        vault_manager.shutdown()

    print("🎉 Settings bulk pattern update completed successfully!")


# ──────────────────────────────────── router ───────────────────────────────


def dispatch_command(command: str, args: dict) -> None:
    if command == "core":
        dispatch_core(args)
    elif command == "stitch":
        dispatch_stitch(args)
    elif command == "web":
        dispatch_web(args)
    elif command == "database":
        dispatch_database(args)
    elif command == "model":
        dispatch_model(args)
    elif command == "slideshow":
        launch_slideshow()
    elif command == "update-settings":
        dispatch_update_settings(args)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
