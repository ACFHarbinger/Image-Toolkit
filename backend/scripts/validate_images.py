import os
import sys
import struct
from PIL import Image

def validate_webp(path):
    """
    Performs deep binary validation of a WebP file.
    Checks RIFF headers, chunk sizes, and internal signatures.
    """
    issues = []
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return ["Truncated (less than 12 bytes)"]
            
            # RIFF check (52 49 46 46)
            if header[0:4] != b"RIFF":
                issues.append(f"Missing RIFF magic! Found: {header[0:4].hex()} ({header[0:4]})")
            
            # WEBP check
            if header[8:12] != b"WEBP":
                issues.append(f"Missing WEBP signature! Found: {header[8:12].hex()}")
                
            # RIFF size check (bytes 4-7, little endian)
            # This is the size of the rest of the file following this element.
            # Total file size should be riff_size + 8.
            riff_size = struct.unpack("<I", header[4:8])[0]
            expected_total_size = riff_size + 8
            actual_size = os.path.getsize(path)
            
            if actual_size > expected_total_size:
                # Read the rest of the data to check for concatenated chunks
                data = f.read()
                if b"RIFF" in data:
                    # This is the "Invalid Chunk header" 0x52494646 error candidate
                    issues.append("CRITICAL: Contains secondary RIFF signature (likely a concatenated image sequence)")
                else:
                    issues.append(f"WARNING: File trailing data exists. Expected {expected_total_size}, Actual {actual_size}")
            elif actual_size < expected_total_size:
                issues.append(f"ERROR: Truncated file. Expected {expected_total_size}, Actual {actual_size}")

        # Try decoding with PIL as a real-world test
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as e:
            issues.append(f"PIL verification failed: {e}")

    except Exception as e:
        issues.append(f"Access error: {e}")
        
    return issues

def main(target_dir):
    if not os.path.isdir(target_dir):
        print(f"❌ Error: {target_dir} is not a directory.")
        return

    print(f"🔍 Validating images in: {target_dir}")
    print("=" * 60)
    count = 0
    errors = 0
    
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
                path = os.path.join(root, file)
                count += 1
                
                # Only perform deep validation on WebP for now as it's the primary issue source
                if file.lower().endswith(".webp"):
                    issues = validate_webp(path)
                    if issues:
                        errors += 1
                        print(f"❌ {os.path.relpath(path, target_dir)}")
                        for issue in issues:
                            print(f"   - {issue}")
    
    print("-" * 60)
    print(f"✅ Summary: Scanned {count} images. Found {errors} files with issues.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_images.py <directory>")
    else:
        main(sys.argv[1])
