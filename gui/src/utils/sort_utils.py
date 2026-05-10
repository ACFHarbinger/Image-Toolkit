import re

def natural_sort_key(s: str):
    """
    Generate a key for natural sorting (e.g., 'file2' before 'file10').
    Case-insensitive.
    """
    if s is None:
        return []
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]
