"""`model` command group: ad-hoc single-image generation via SD3."""

from __future__ import annotations

import sys

from backend.src.models.wrappers.sd3_wrapper import SD3Wrapper


def dispatch_model(args: dict) -> None:
    command = args.get("model_command")
    if command == "generate":
        prompt = args.get("prompt", "")
        output = args.get("output", "output.png")
        model_name = args.get("model", "stable-diffusion")
        try:
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
