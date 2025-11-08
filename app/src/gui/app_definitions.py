import os

from pathlib import Path


# --- GLOBAL CONFIGURATION (MOCK DATA for QLineEdit defaults) ---
SERVICE_ACCOUNT_FILE = os.path.join(Path.home(), "google_drive_key.json")
LOCAL_SOURCE_PATH = str(Path.home() / "Documents" / "sync_folder")
DRIVE_DESTINATION_FOLDER_NAME = "Automated_Backups/Monthly_Data"
DRY_RUN = True

# New image size limit
NEW_LIMIT_MB = 1024