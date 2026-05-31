import base64
import logging
import os
import sys

from omegaconf import DictConfig
from typing import Optional

from safetensors import safe_open
from safetensors.torch import save_file

logger = logging.getLogger(__name__)


def embed_preview_image(
    model_path: str, image_path: str, output_path: Optional[str] = None
) -> bool:
    """
    Embeds an image as a base64 string into the metadata of an existing .safetensors model file.

    Args:
        model_path (str): Path to the existing .safetensors model file.
        image_path (str): Path to the image file to embed (e.g., .png, .jpg).
        output_path (Optional[str]): Path to save the updated model. If None, overwrites the original model_path.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    if output_path is None:
        output_path = model_path

    try:
        # 1. Read, resize and encode the image
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        from PIL import Image
        import io

        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g. RGBA -> RGB for JPEG compatibility)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize to max 512px while maintaining aspect ratio
            img.thumbnail((512, 512))

            # Save to buffer
            buf = io.BytesIO()
            # Use JPEG for smaller size, or original format if preferred
            img.save(buf, format="JPEG", quality=85)
            image_data = buf.getvalue()

        base64_encoded = base64.b64encode(image_data).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{base64_encoded}"

        # 2. Read existing weights and metadata from the .safetensors file
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        tensors = {}
        metadata = {}

        # Open the safetensors file using PyTorch framework
        with safe_open(model_path, framework="pt", device="cpu") as f:
            # Safely extract existing metadata
            existing_metadata = f.metadata()
            if existing_metadata:
                metadata.update(existing_metadata)

            # Extract all tensors
            for key in f.keys():
                tensors[key] = f.get_tensor(key)

        # 3. Add the base64 image string to the metadata
        # Setting both common keys to ensure compatibility with various UIs (like ComfyUI)
        metadata["preview"] = data_uri
        metadata["modelspec.thumbnail"] = data_uri

        # 4. Save the updated weights and metadata
        # Use a temporary file for safety during the overwrite process
        temp_output = output_path + ".tmp"

        save_file(tensors, temp_output, metadata=metadata)

        # Atomically replace the target file
        os.replace(temp_output, output_path)

        logger.info(
            f"Successfully embedded preview image from '{image_path}' into '{output_path}'."
        )
        return True

    except FileNotFoundError as e:
        logger.error(f"File Error: {e}")
        return False
    except Exception as e:
        logger.exception(f"An error occurred while embedding the preview image: {e}")
        # Clean up the temporary file if an error occurs during saving
        if "temp_output" in locals() and os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
        return False


def main(cfg: DictConfig) -> None:
    # Use embed_metadata override from config
    metadata_cfg = cfg.get("data", {}).get("embed_metadata", {})
    model_path = metadata_cfg.get("model_path")
    image_path = metadata_cfg.get("image_path")
    output_path = metadata_cfg.get("output_path", None)

    if not model_path or not image_path:
        logger.error(
            "Missing model_path or image_path. Please provide data.embed_metadata.model_path and data.embed_metadata.image_path"
        )
        sys.exit(1)

    success = embed_preview_image(model_path, image_path, output_path)
    if not success:
        sys.exit(1)
