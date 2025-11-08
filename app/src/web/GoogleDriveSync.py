import os
import sys

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import DefaultCredentialsError
from typing import Callable, Dict, Any, Optional

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

# IMPORTANT: Path to your Google Service Account JSON key file.
# This Service Account must have access to the Google Drive folder.
SERVICE_ACCOUNT_FILE = 'service_account_key.json'

# Define the scopes (read/write access to all Google Drive files)
SCOPES = ['https://www.googleapis.com/auth/drive']

# Local folder path you want to synchronize (e.g., a folder on your server)
LOCAL_SOURCE_PATH = "/path/to/local/source/folder" 

# Destination folder *name* inside your Google Drive. 
# This folder will be created if it does not exist.
DRIVE_DESTINATION_FOLDER_NAME = "Scheduled_Backups/Current_Month"

# Optional: If you want to perform a dry run (show actions without executing them)
DRY_RUN = False 

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/drive']
SYNC_ERROR = "SyncFailed"

# ==============================================================================
# 2. HELPER FUNCTIONS: DRIVE & AUTH
# ==============================================================================

def get_drive_service(key_file: str, logger: Callable[[str], None]):
    """Authenticates using the Service Account key and returns a Google Drive service object."""
    logger("🔑 Authenticating with Google Drive...")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            key_file, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        logger("✅ Authentication successful.")
        return service
    except DefaultCredentialsError as e:
        logger(f"❌ Authentication Error: The service account key file may be missing or invalid: {e}")
        raise RuntimeError(SYNC_ERROR)
    except Exception as e:
        logger(f"❌ An unexpected authentication error occurred: {e}")
        raise RuntimeError(SYNC_ERROR)

def find_or_create_destination_folder(service: Any, folder_path_str: str, dry_run: bool, logger: Callable[[str], None]):
    """
    Finds the ID of the destination folder by traversing the path, creating subfolders if they don't exist.
    """
    path_components = [p for p in folder_path_str.split('/') if p]
    current_parent_id = 'root'
    logger(f"🔍 Locating/Creating destination path: /{folder_path_str}")

    for folder_name in path_components:
        query = (
            f"name='{folder_name}' and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"'{current_parent_id}' in parents and "
            f"trashed=false"
        )
        try:
            response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = response.get('files', [])

            if files:
                current_parent_id = files[0]['id']
            else:
                logger(f"   Creating folder: {folder_name}")
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent_id]
                }
                if dry_run:
                    logger(f"   [DRY RUN] Would have created folder '{folder_name}'")
                    # In dry run, we cannot assume the ID, so we stop traversal.
                    return None 
                
                folder = service.files().create(body=file_metadata, fields='id').execute()
                current_parent_id = folder.get('id')
                logger(f"   Created folder: {folder_name} (ID: {current_parent_id})")
        except HttpError as e:
            logger(f"❌ Error locating/creating folder '{folder_name}': {e}")
            return None
        except Exception as e:
             logger(f"❌ Unexpected error in folder creation for '{folder_name}': {e}")
             return None

    logger(f"✅ Destination Folder ID: {current_parent_id}")
    return current_parent_id

def get_local_files_map(local_path: str, logger: Callable[[str], None]) -> Dict[str, Dict[str, Any]]:
    """Creates a map of filename -> (absolute_path, timestamp) for local files in the root."""
    local_files: Dict[str, Dict[str, Any]] = {}
    for root, _, files in os.walk(local_path):
        # Only process files directly at the root of the source path for the simplified sync
        if root != local_path:
            continue
            
        for file in files:
            absolute_path = os.path.join(root, file)
            timestamp = int(os.path.getmtime(absolute_path))
            local_files[file] = {'path': absolute_path, 'mtime': timestamp}
    return local_files

def get_remote_files_map(service: Any, folder_id: str, logger: Callable[[str], None]) -> Dict[str, Dict[str, Any]]:
    """Creates a map of filename -> (file_id, timestamp) for remote files directly under folder_id."""
    remote_files: Dict[str, Dict[str, Any]] = {}
    query = f"'{folder_id}' in parents and trashed=false"
    
    items: list[Any] = []
    page_token = None
    while True:
        try:
            response = service.files().list(
                q=query, 
                spaces='drive', 
                fields='nextPageToken, files(id, name, modifiedTime, mimeType)',
                pageToken=page_token
            ).execute()
        except HttpError as e:
            logger(f"❌ Error listing remote files: {e}")
            raise RuntimeError(SYNC_ERROR)
            
        items.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
            
    for item in items:
        modified_time_iso = item.get('modifiedTime')
        try:
            # Drive API uses RFC 3339 format, we convert to Unix seconds (int)
            dt_object = datetime.strptime(modified_time_iso, "%Y-%m-%dT%H:%M:%S.%fZ")
            timestamp = int(dt_object.timestamp())
        except:
            timestamp = 0
            
        remote_files[item['name']] = {
            'id': item['id'], 
            'mtime': timestamp, 
            'is_folder': item['mimeType'] == 'application/vnd.google-apps.folder'
        }
        
    return remote_files

def upload_file(service: Any, local_file_path: str, file_name: str, folder_id: str, remote_file_id: Optional[str], dry_run: bool, logger: Callable[[str], None]):
    """Uploads or updates a file."""
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    
    local_mtime = os.path.getmtime(local_file_path)
    dt_object = datetime.fromtimestamp(local_mtime)
    # Drive API needs modifiedTime in RFC 3339 format
    file_metadata['modifiedTime'] = dt_object.isoformat("T") + "Z"

    media = MediaFileUpload(local_file_path, resumable=True)

    if dry_run:
        action = "UPDATE" if remote_file_id else "UPLOAD"
        logger(f"   [DRY RUN] {action}: {file_name}")
        return True

    try:
        if remote_file_id:
            service.files().update(fileId=remote_file_id, body=file_metadata, media_body=media).execute()
        else:
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except HttpError as e:
        logger(f"❌ Error during file operation for '{file_name}': {e}")
        return False

def delete_file(service: Any, file_id: str, file_name: str, dry_run: bool, logger: Callable[[str], None]):
    """Deletes a file or folder on Google Drive."""
    logger(f"   DELETING: {file_name}")
    
    if dry_run:
        logger(f"   [DRY RUN] Would have deleted file/folder: {file_name}")
        return True
    
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as e:
        logger(f"❌ Error deleting '{file_name}': {e}")
        return False
        
# ==============================================================================
# 3. CORE SYNCHRONIZATION EXECUTION
# ==============================================================================

def execute_sync(
    key_file: str, 
    local_path: str, 
    remote_path: str, 
    dry_run: bool, 
    logger: Callable[[str], None]
) -> tuple[bool, str]:
    """
    Main function to orchestrate the one-way sync logic.
    Returns (success_status, final_message).
    """
    try:
        # 1. Initialize Drive Service
        drive_service = get_drive_service(key_file, logger)

        # 2. Find Destination Folder
        dest_folder_id = find_or_create_destination_folder(drive_service, remote_path, dry_run, logger)
        
        if dest_folder_id is None and not dry_run:
            logger("❌ Failed to secure destination folder ID.")
            return (False, "Failed to secure destination folder ID.")
        
        if dest_folder_id is None and dry_run:
            logger("⚠️ Cannot proceed with file sync comparison in DRY RUN as destination folder was not secured.")
            return (True, "Dry Run incomplete: Destination path creation was simulated.")

        # 3. Get file maps
        logger("📋 Comparing local and remote files...")
        local_files = get_local_files_map(local_path, logger)
        remote_files = get_remote_files_map(drive_service, dest_folder_id, logger)
        
        logger("\n--- Sync Operation Analysis & Execution ---")
        
        files_to_sync = 0
        files_to_delete = 0

        # A. Determine files to upload/update
        for local_name, local_data in local_files.items():
            local_mtime = local_data['mtime']
            
            if local_name in remote_files:
                remote_data = remote_files[local_name]
                remote_mtime = remote_data['mtime']
                remote_id = remote_data['id']
                
                # Check if local file is newer than remote file (1-second buffer)
                if local_mtime > remote_mtime + 1:
                    logger(f"   UPDATING: {local_name} (Local newer)")
                    upload_file(drive_service, local_data['path'], local_name, dest_folder_id, remote_id, dry_run, logger)
                    files_to_sync += 1
                
                # Mark as processed to prevent deletion
                remote_files.pop(local_name) 
            else:
                # File exists locally but not remotely -> UPLOAD
                logger(f"   UPLOADING: {local_name} (New file)")
                upload_file(drive_service, local_data['path'], local_name, dest_folder_id, None, dry_run, logger)
                files_to_sync += 1

        # B. Determine files to delete (remaining files in remote_files map)
        for remote_name, remote_data in remote_files.items():
            # All remaining items in remote_files must be deleted to mirror local source.
            delete_file(drive_service, remote_data['id'], remote_name, dry_run, logger)
            files_to_delete += 1

        total_actions = files_to_sync + files_to_delete
        
        logger("\n--- Sync Execution Summary ---")
        
        if total_actions == 0:
            logger("✅ Sync successful! No changes required.")
            final_message = "No changes needed."
        else:
            logger(f"✅ Sync successful! Total actions: {total_actions} (Upload/Update: {files_to_sync}, Delete: {files_to_delete})")
            status_word = "Simulated" if dry_run else "Completed"
            final_message = f"{status_word} with {total_actions} actions."
        
        return (True, final_message)

    except RuntimeError as e:
        # Handles authentication and folder creation failures
        return (False, f"Sync failed: {e}")
    except HttpError as e:
        logger(f"❌ Google API Error during sync: {e}")
        return (False, f"Sync failed due to API error.")
    except Exception as e:
        logger(f"❌ An unexpected error occurred: {e}")
        return (False, f"Sync failed due to unexpected error.")

# ==============================================================================
# 4. MAIN EXECUTION FLOW
# ==============================================================================

if __name__ == "__main__":
    
    # 4.1. Prerequisite Checks
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"Error: Service Account key file '{SERVICE_ACCOUNT_FILE}' not found.")
        sys.exit(1)
        
    if not os.path.isdir(LOCAL_SOURCE_PATH):
         print(f"Error: Local source path '{LOCAL_SOURCE_PATH}' does not exist.")
         sys.exit(1)
         
    if DRY_RUN:
        print("\n=======================================================")
        print("          !!! D R Y   R U N   M O D E !!!")
        print("    No changes will be made to the Google Drive.")
        print("=======================================================\n")

    try:
        # 4.2. Initialize Drive Service
        drive_service = get_drive_service(SERVICE_ACCOUNT_FILE)

        # 4.3. Find Destination Folder
        dest_folder_id = find_or_create_destination_folder(drive_service, DRIVE_DESTINATION_FOLDER_NAME)
        
        if dest_folder_id is None and not DRY_RUN:
             print("❌ Failed to secure destination folder ID. Exiting.")
             sys.exit(1)
             
        # If running dry run and the path could not be secured, we allow it to continue to report the error
        if dest_folder_id is None and DRY_RUN:
            print("⚠️  Cannot proceed with file sync comparison in DRY RUN as destination folder was not secured.")
        
        # 4.4. Run the Synchronization
        if dest_folder_id is not None or DRY_RUN:
            changes_made = execute_sync(drive_service, LOCAL_SOURCE_PATH, dest_folder_id)
            
            # 4.5. Exit Code for Scheduling Environment
            if not changes_made and not DRY_RUN:
                print("\nScript finished successfully (No changes needed).")
                sys.exit(0)
            elif DRY_RUN:
                 print("\nScript finished successfully in DRY RUN mode.")
                 sys.exit(0)
            else:
                print("\nScript finished successfully (Changes were made).")
                sys.exit(0)
        else:
             print("\nScript failed because destination folder could not be found/created.")
             sys.exit(1)

    except HttpError as e:
        print(f"❌ Google Drive API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected script error occurred: {e}")
        sys.exit(1)