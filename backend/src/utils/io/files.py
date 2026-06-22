import os
import zipfile

def zip_directory(input_dir: str, output_zip: str) -> None:
    """Create a zip archive of a directory."""
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(input_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, input_dir)
                zipf.write(file_path, arcname)
    print(f"Directory '{input_dir}' zipped to '{output_zip}'")

def extract_zip(input_zip: str, output_dir: str) -> None:
    """Extracts a zip archive to a directory."""
    with zipfile.ZipFile(input_zip, "r") as zipf:
        zipf.extractall(output_dir)
    print(f"Zip archive '{input_zip}' was extracted to directory '{output_dir}'")
