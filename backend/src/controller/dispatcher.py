import logging
import subprocess
import sys

import hydra
from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger(__name__)

@hydra.main(config_path="../../config", config_name="base", version_base="1.3")
def main(cfg: DictConfig) -> None:
    command = cfg.get("command", "train")

    if command == "train":
        from backend.src.pipeline.anime_training_pipeline import main as train_main
        train_main(cfg)

    elif command == "embed_metadata":
        from backend.src.utils.safetensors_metadata import main as embed_main
        embed_main(cfg)

    elif command == "comfyui":
        logger.info("Starting ComfyUI headlessly...")
        try:
            # sys.executable is the python from .venv
            subprocess.run([sys.executable, "ComfyUI/main.py"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"ComfyUI failed to run or exited with error: {e}")
            sys.exit(e.returncode)
        except FileNotFoundError:
            logger.error("Could not find ComfyUI/main.py. Make sure ComfyUI is installed in the repository root.")
            sys.exit(1)

    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
