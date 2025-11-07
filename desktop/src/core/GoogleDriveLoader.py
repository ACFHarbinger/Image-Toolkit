import os
import sys
import time
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import DefaultCredentialsError

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

# ==============================================================================
# 2. HELPER FUNCTIONS: DRIVE & AUTH
# ==============================================================================

def get_drive_service(key_file):
    """Authenticates using the Service Account key and returns a Google Drive service object."""
    print("🔑 Authenticating with Google Drive...")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            key_file, scopes=SCOPES
        )
        # Build the Drive service v3
        service = build('drive', 'v3', credentials=credentials)
        print("✅ Authentication successful.")
        return service
    except DefaultCredentialsError as e:
        print(f"❌ Authentication Error: The service account key file may be missing or invalid.")
        print(f"   Expected file: {key_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected authentication error occurred: {e}")
        sys.exit(1)

def find_or_create_destination_folder(service, folder_path_str):
    """
    Finds the ID of the destination folder by traversing the path, creating subfolders if they don't exist.
    """
    path_components = [p for p in folder_path_str.split('/') if p]
    current_parent_id = 'root' # Start search from the root of the drive

    print(f"🔍 Locating/Creating destination path: /{folder_path_str}")

    for folder_name in path_components:
        # 1. Search for the folder in the current parent
        query = (
            f"name='{folder_name}' and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"'{current_parent_id}' in parents and "
            f"trashed=false"
        )
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])

        if files:
            # Folder found
            current_parent_id = files[0]['id']
            # print(f"   Found folder: {folder_name} (ID: {current_parent_id})")
        else:
            # Folder not found, create it
            print(f"   Creating folder: {folder_name}")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [current_parent_id]
            }
            if DRY_RUN:
                print(f"   [DRY RUN] Would have created folder '{folder_name}'")
                return None # Cannot continue in dry run if path does not exist
            
            try:
                folder = service.files().create(body=file_metadata, fields='id').execute()
                current_parent_id = folder.get('id')
                print(f"   Created folder: {folder_name} (ID: {current_parent_id})")
            except HttpError as e:
                print(f"❌ Error creating folder '{folder_name}': {e}")
                return None

    print(f"✅ Destination Folder ID: {current_parent_id}")
    return current_parent_id

# ==============================================================================
# 3. CORE SYNCHRONIZATION LOGIC
# ==============================================================================

def get_local_files_map(local_path):
    """Creates a map of relative_path -> (absolute_path, timestamp) for local files."""
    local_files = {}
    for root, _, files in os.walk(local_path):
        for file in files:
            absolute_path = os.path.join(root, file)
            relative_path = os.path.relpath(absolute_path, local_path)
            # Use mtime (modification time) for comparison, converted to seconds (int)
            timestamp = int(os.path.getmtime(absolute_path))
            local_files[relative_path] = {'path': absolute_path, 'mtime': timestamp}
    return local_files

def get_remote_files_map(service, folder_id):
    """
    Creates a map of relative_path -> (file_id, timestamp) for remote files.
    Note: Drive API timestamps are in milliseconds/RFC 3339 format, we convert to seconds (int).
    """
    remote_files = {}
    
    # We use a recursive query to get all files under the folder_id
    query = (
        f"'{folder_id}' in parents and "
        f"trashed=false"
    )
    
    # Fields: name, id, parents (to rebuild path), modifiedTime
    # We need to list files recursively, which Drive API doesn't do easily.
    # The simplest sync approach is to list files only in the root of the destination 
    # and rely on the local os.walk for directory structure (recreating folders as needed)
    
    # Simplified query: list files *directly* under the destination folder
    query = (
        f"'{folder_id}' in parents and "
        f"trashed=false"
    )
    
    items = []
    page_token = None
    while True:
        response = service.files().list(
            q=query, 
            spaces='drive', 
            fields='nextPageToken, files(id, name, modifiedTime, mimeType)',
            pageToken=page_token
        ).execute()
        
        items.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
            
    # Map files and folders at the root of the destination
    for item in items:
        # Convert Drive's RFC 3339 timestamp to Unix seconds
        # Example: '2023-11-06T19:30:00.000Z'
        modified_time_iso = item.get('modifiedTime')
        
        # Parse the ISO format string and get the timestamp in seconds
        try:
            dt_object = datetime.strptime(modified_time_iso, "%Y-%m-%dT%H:%M:%S.%fZ")
            timestamp = int(dt_object.timestamp())
        except:
            timestamp = 0 # Fallback if parsing fails
            
        # The key is the file/folder name at the destination root
        remote_files[item['name']] = {
            'id': item['id'], 
            'mtime': timestamp, 
            'is_folder': item['mimeType'] == 'application/vnd.google-apps.folder'
        }
        
    return remote_files

def upload_file(service, local_file_path, file_name, folder_id, remote_file_id=None):
    """Uploads a file, or updates an existing one if remote_file_id is provided."""
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    
    # Set the local modification time on the remote file (critical for sync logic)
    # Drive API needs modifiedTime in RFC 3339 format (YYYY-MM-DDTHH:mm:ss.sssZ)
    local_mtime = os.path.getmtime(local_file_path)
    dt_object = datetime.fromtimestamp(local_mtime)
    file_metadata['modifiedTime'] = dt_object.isoformat("T") + "Z"

    media = MediaFileUpload(local_file_path, resumable=True)

    if DRY_RUN:
        action = "UPDATE" if remote_file_id else "UPLOAD"
        print(f"   [DRY RUN] {action}: {file_name}")
        return True

    try:
        if remote_file_id:
            # Update existing file
            service.files().update(fileId=remote_file_id, body=file_metadata, media_body=media).execute()
        else:
            # Upload new file
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except HttpError as e:
        print(f"❌ Error during file operation for '{file_name}': {e}")
        return False

def delete_file(service, file_id, file_name):
    """Deletes a file or folder on Google Drive."""
    print(f"   DELETING: {file_name}")
    
    if DRY_RUN:
        print(f"   [DRY RUN] Would have deleted file/folder: {file_name}")
        return True
    
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except HttpError as e:
        print(f"❌ Error deleting '{file_name}': {e}")
        return False

def execute_sync(service, local_path, remote_folder_id):
    """
    Performs one-way synchronization (remote mirrors local).
    Note: This implementation is non-recursive, only syncs files at the top level
    of the LOCAL_SOURCE_PATH to the DRIVE_DESTINATION_FOLDER_NAME.
    For full recursion, the logic would need to be much more complex, tracking folder IDs.
    """
    
    local_files = get_local_files_map(local_path)
    remote_files = get_remote_files_map(service, remote_folder_id)
    
    print("\n--- Sync Operation Analysis ---")
    
    # 1. Determine files to upload/update
    files_to_sync = 0
    
    # We only care about files at the root of the local source for this simplified sync
    # For full recursion, we would process the entire local_files map
    
    for relative_path, local_data in local_files.items():
        # Only process files at the top level of the sync for this simplified logic
        if os.path.dirname(relative_path) != "":
            continue 
            
        local_name = os.path.basename(local_data['path'])
        local_mtime = local_data['mtime']
        
        if local_name in remote_files:
            remote_data = remote_files[local_name]
            remote_mtime = remote_data['mtime']
            remote_id = remote_data['id']
            
            # Check if local file is newer than remote file (or equal, which we ignore)
            # Add a 1-second buffer due to filesystem/API timestamp inconsistencies
            if local_mtime > remote_mtime + 1:
                print(f"   UPDATING: {local_name} (Local newer: {local_mtime} > {remote_mtime})")
                upload_file(service, local_data['path'], local_name, remote_folder_id, remote_id)
                files_to_sync += 1
            else:
                # print(f"   SKIPPING: {local_name} (Remote up-to-date)")
                pass
        else:
            # File exists locally but not remotely -> UPLOAD
            print(f"   UPLOADING: {local_name} (New file)")
            upload_file(service, local_data['path'], local_name, remote_folder_id)
            files_to_sync += 1

    # 2. Determine files to delete (only files/folders directly in the destination)
    files_to_delete = 0
    local_root_names = {os.path.basename(f) for f in os.listdir(local_path)}
    
    for remote_name, remote_data in remote_files.items():
        if remote_name not in local_root_names:
            # File exists remotely but not locally -> DELETE (rclone sync behavior)
            print(f"   DELETING: {remote_name} (Not found locally)")
            delete_file(service, remote_data['id'], remote_name)
            files_to_delete += 1
    
    total_actions = files_to_sync + files_to_delete
    print("\n--- Rclone Execution Summary ---")
    
    if total_actions == 0:
        print("No changes required. Source and Destination are synchronized.")
    else:
        print(f"Total actions performed: {total_actions} (Upload/Update: {files_to_sync}, Delete: {files_to_delete})")
        
    return total_actions > 0

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