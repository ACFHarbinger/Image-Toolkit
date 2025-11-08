import os
import sys

from ..utils.definitions import SCOPES, SYNC_ERROR
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.exceptions import DefaultCredentialsError
from typing import Callable, Dict, Any, Optional, List


class GoogleDriveSync:
    """
    Manages one-way synchronization of a local directory to a specific folder in Google Drive 
    using a Service Account, now supporting recursive subdirectories.
    """
    def __init__(
        self,
        service_account_file: str,
        local_source_path: str,
        drive_destination_folder_name: str,
        dry_run: bool = False,
        logger: Callable[[str], None] = print,  # Default to print if no logger provided
        user_email_to_share_with: Optional[str] = None # Optional email for sharing
    ):
        """
        Initializes the sync manager with configuration parameters.
        ... (docstring truncated for brevity)
        """
        self.key_file = service_account_file
        self.local_path = local_source_path
        self.remote_path = drive_destination_folder_name
        self.dry_run = dry_run
        self.logger = logger
        self.drive_service: Optional[Any] = None
        self.dest_folder_id: Optional[str] = None
        self.share_email = user_email_to_share_with
        # Cache for mapping relative paths to Drive IDs, essential for recursion
        # Key: Relative path (e.g., 'subfolder/file.txt'), Value: Drive File ID
        self.remote_path_id_map: Dict[str, str] = {}
        # Cache for mapping folder relative paths to Drive IDs
        self.remote_folder_id_map: Dict[str, str] = {}


    # ==============================================================================
    # 2. HELPER METHODS: DRIVE & AUTH
    # ==============================================================================

    def _get_drive_service(self):
        """Authenticates using the Service Account key and sets the Google Drive service object."""
        self.logger("🔑 Authenticating with Google Drive...")
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.key_file, scopes=SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            self.logger("✅ Authentication successful.")
        except DefaultCredentialsError as e:
            self.logger(f"❌ Authentication Error: The service account key file may be missing or invalid: {e}")
            raise RuntimeError(SYNC_ERROR)
        except Exception as e:
            self.logger(f"❌ An unexpected authentication error occurred: {e}")
            raise RuntimeError(SYNC_ERROR)

    def _find_or_create_destination_folder(self) -> Optional[str]:
        """
        Finds the ID of the root destination folder by traversing the path, 
        creating subfolders if they don't exist, and stores the ID in self.dest_folder_id.
        """
        path_components = [p for p in self.remote_path.split('/') if p]
        current_parent_id = 'root'
        self.logger(f"🔍 Locating/Creating destination path: /{self.remote_path}")

        if not self.drive_service:
             self.logger("Error: Drive service not initialized.")
             return None

        for folder_name in path_components:
            query = (
                f"name='{folder_name}' and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"'{current_parent_id}' in parents and "
                f"trashed=false"
            )
            try:
                response = self.drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
                files = response.get('files', [])

                if files:
                    current_parent_id = files[0]['id']
                else:
                    self.logger(f"   Creating folder: {folder_name}")
                    file_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent_id]
                    }
                    if self.dry_run:
                        self.logger(f"   [DRY RUN] Would have created folder '{folder_name}'")
                        return None 
                    
                    folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
                    current_parent_id = folder.get('id')
                    self.logger(f"   Created folder: {folder_name} (ID: {current_parent_id})")
            except HttpError as e:
                self.logger(f"❌ Error locating/creating folder '{folder_name}': {e}")
                return None
            except Exception as e:
                 self.logger(f"❌ Unexpected error in folder creation for '{folder_name}': {e}")
                 return None

        self.logger(f"✅ Destination Folder ID: {current_parent_id}")
        self.dest_folder_id = current_parent_id
        
        # LOG FOLDER URL
        if current_parent_id:
            drive_url = f"https://drive.google.com/drive/folders/{current_parent_id}"
            self.logger(f"🔗 Destination Folder URL: {drive_url}")
        
        return current_parent_id

    def _get_local_files_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Creates a map of relative_path -> (absolute_path, timestamp) for ALL local files and folders.
        The map key is the relative path (e.g., 'sub/file.txt' or 'sub/').
        """
        local_files: Dict[str, Dict[str, Any]] = {}
        
        for root, dirs, files in os.walk(self.local_path):
            # Calculate the relative path of the current directory from the source root
            relative_dir = os.path.relpath(root, self.local_path)
            
            # Ensure folder structure is mapped for synchronization
            if relative_dir != '.':
                # Store the relative path of the folder itself (must end with '/')
                folder_key = relative_dir.replace('\\', '/') + '/'
                local_files[folder_key] = {
                    'path': root, 
                    'mtime': int(os.path.getmtime(root)),
                    'is_folder': True
                }

            # Map files within the current directory
            for file in files:
                absolute_path = os.path.join(root, file)
                
                # Create the full relative path key (e.g., 'sub/file.txt')
                if relative_dir == '.':
                    file_key = file
                else:
                    file_key = os.path.join(relative_dir, file).replace('\\', '/')
                    
                local_files[file_key] = {
                    'path': absolute_path, 
                    'mtime': int(os.path.getmtime(absolute_path)),
                    'is_folder': False
                }
                
        return local_files

    def _get_remote_files_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Creates a map of relative_path -> (file_id, timestamp) for ALL remote items 
        under the destination folder. Populates self.remote_path_id_map.
        """
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        remote_files: Dict[str, Dict[str, Any]] = {}
        self.remote_path_id_map = {}
        self.remote_folder_id_map = {}

        # Query to search only within the destination folder hierarchy
        # We need to find all items that are descendants of dest_folder_id
        
        # The Drive API doesn't easily support recursive searching by parent. 
        # A workaround is to fetch all files and reconstruct the path structure locally.
        
        items: List[Any] = []
        page_token = None
        
        # We need fields: id, name, parents, modifiedTime, mimeType
        fields = 'nextPageToken, files(id, name, parents, modifiedTime, mimeType)'
        
        # Fetch all files under the destination folder ID
        query = f"'{self.dest_folder_id}' in parents and trashed=false"
        
        # We fetch files recursively by starting at the destination root, and then tracing all paths.
        # Drive API v3: files are not strictly children, they have multiple parents. We'll use a local mapping.
        
        # 1. Fetch ALL items (folders and files) that are children of the root dest folder
        # We'll use a loop to reconstruct the full path for each item later.
        
        all_remote_items: Dict[str, Dict[str, Any]] = {} # Key: fileId, Value: item_data
        
        # Get all file IDs and parents below the destination root recursively (simulated traversal)
        # For simplicity and performance, we'll rely on the parent ID for direct comparison.
        # This implementation will list all files/folders *in the destination hierarchy* # and rebuild the paths relative to the destination root.

        # Drive API search query structure to list descendants recursively is complex and slow.
        # Instead, we will list only DIRECT children, and rely on the fact that syncs typically
        # only involve direct children of the target folder. 
        # For true recursion, we need an advanced traversal function:

        # Let's perform a simpler recursive fetch starting from dest_folder_id
        def fetch_remote_items_recursively(parent_id: str, current_path: str) -> List[Dict[str, Any]]:
            """Helper function to recursively fetch remote items and build paths."""
            sub_items = []
            page_token = None
            
            # List items where the current parent_id is one of the parents
            query = f"'{parent_id}' in parents and trashed=false"

            while True:
                try:
                    response = self.drive_service.files().list(
                        q=query, 
                        spaces='drive', 
                        fields=fields,
                        pageToken=page_token
                    ).execute()
                except HttpError as e:
                    self.logger(f"❌ Error listing remote files for path '{current_path}': {e}")
                    raise RuntimeError(SYNC_ERROR)

                for item in response.get('files', []):
                    name = item['name']
                    is_folder = item.get('mimeType') == 'application/vnd.google-apps.folder'
                    
                    # Build the relative path key
                    if current_path == '':
                        relative_path = name
                    else:
                        relative_path = os.path.join(current_path, name).replace('\\', '/')
                        
                    # Add item details
                    item_details = {
                        'id': item['id'],
                        'mtime': self._parse_drive_time(item.get('modifiedTime')),
                        'is_folder': is_folder
                    }
                    
                    # Store in the main remote map
                    remote_files[relative_path] = item_details
                    
                    # Store ID for quick folder lookup during upload
                    if is_folder:
                        folder_key = relative_path + '/'
                        remote_files[folder_key] = item_details
                        self.remote_folder_id_map[folder_key] = item['id']
                    else:
                         self.remote_path_id_map[relative_path] = item['id']

                    # If it's a folder, recurse
                    if is_folder:
                        sub_items.extend(fetch_remote_items_recursively(item['id'], relative_path))
                    
                    sub_items.append(item)
                    
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
                    
            return sub_items
            
        fetch_remote_items_recursively(self.dest_folder_id, '')

        # Log remote files map for viewing/debugging (always runs if destination is secured)
        self.logger("\n--- Current Remote Files in Destination Folder ---")
        if remote_files:
            # Sort files by path for clean viewing
            sorted_files = sorted(remote_files.keys())
            for path in sorted_files:
                item = remote_files[path]
                # Skip keys representing files that are also folders (file keys without the ending '/')
                if item['is_folder'] and not path.endswith('/'):
                    continue
                
                display_path = path if not item['is_folder'] else path[:-1] # Remove trailing / for display
                file_type = "Folder" if item['is_folder'] else "File"
                mod_time = datetime.fromtimestamp(item['mtime']).strftime('%Y-%m-%d %H:%M:%S')
                self.logger(f"   [{file_type.ljust(6)}] {display_path} (Modified: {mod_time})")
        else:
            self.logger("   (Folder is empty)")
        self.logger("--------------------------------------------------")
        
        return remote_files
    
    def _parse_drive_time(self, modified_time_iso: str) -> int:
        """Converts Drive API RFC 3339 time string to Unix timestamp."""
        timestamp = 0
        if modified_time_iso:
            try:
                # Drive API uses RFC 3339 format, convert to Unix seconds (int)
                # datetime.fromisoformat handles the 'Z' (UTC) ending or timezone info
                dt_object = datetime.fromisoformat(modified_time_iso.replace('Z', '+00:00'))
                timestamp = int(dt_object.timestamp())
            except (ValueError, TypeError, AttributeError):
                # Handle cases where modifiedTime format is slightly off or missing
                pass
        return timestamp

    def _get_parent_id(self, relative_path: str, is_folder: bool) -> Optional[str]:
        """
        Determines the parent ID in Google Drive based on the item's relative path.
        Creates parent folders if they don't exist.
        """
        
        if relative_path == '.' or relative_path == '':
            return self.dest_folder_id # Root level items go into the main destination folder

        # Determine the parent's relative path
        if is_folder:
            parent_rel_path = os.path.dirname(relative_path).replace('\\', '/')
            # If parent_rel_path is empty (i.e., immediate child of root), use dest_folder_id
            if not parent_rel_path:
                return self.dest_folder_id
            
            # Parent must end with '/' in our map
            parent_key = parent_rel_path + '/'
        else: # It's a file
            parent_rel_path = os.path.dirname(relative_path).replace('\\', '/')
            # If file is in root, parent_rel_path is empty
            if not parent_rel_path:
                return self.dest_folder_id
            
            parent_key = parent_rel_path + '/'

        # Check if parent folder ID is already known
        if parent_key in self.remote_folder_id_map:
            return self.remote_folder_id_map[parent_key]

        # Parent folder ID is not known, must traverse/create it
        
        # Split path into components (e.g., 'sub1/sub2/' -> ['sub1', 'sub2'])
        path_components = [p for p in parent_rel_path.split('/') if p]
        current_id = self.dest_folder_id
        
        # Traverse the structure from the destination root
        temp_path = []
        for component in path_components:
            temp_path.append(component)
            current_rel_path = '/'.join(temp_path)
            current_key = current_rel_path + '/'

            if current_key in self.remote_folder_id_map:
                current_id = self.remote_folder_id_map[current_key]
                continue
            
            # Folder needs to be created
            self.logger(f"   Creating required subfolder: {current_rel_path}")
            file_metadata = {
                'name': component,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [current_id]
            }
            
            if self.dry_run:
                self.logger(f"   [DRY RUN] Would have created subfolder '{current_rel_path}'")
                # Cannot proceed with file upload/update without a real parent ID in live mode
                return None 
            
            try:
                folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
                current_id = folder.get('id')
                # Cache the newly created folder ID
                self.remote_folder_id_map[current_key] = current_id
            except HttpError as e:
                self.logger(f"❌ Error creating subfolder '{current_rel_path}': {e}")
                return None # Failed to create parent, cannot continue
        
        return current_id
    
    def _upload_file(self, local_item_path: str, relative_path: str, remote_file_id: Optional[str], is_folder: bool):
        """Uploads or updates a file or creates a folder."""
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        item_name = os.path.basename(local_item_path)
        
        # 1. Determine Parent ID and create necessary subfolders
        parent_id = self._get_parent_id(relative_path, is_folder)
        if not parent_id and not self.dry_run:
            self.logger(f"   Skipping {relative_path}: Failed to secure parent folder ID.")
            return False
            
        # --- Handle Folder Creation/Update ---
        if is_folder:
            if remote_file_id:
                # Folder already exists, nothing to update in a basic sync
                self.logger(f"   SKIPPED: Folder already exists: {relative_path}")
                return True
            
            # Create a new folder
            file_metadata = {
                'name': item_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            if self.dry_run:
                self.logger(f"   [DRY RUN] UPLOAD: Folder {relative_path}")
                return True
            
            try:
                folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
                # Cache the ID for later use
                self.remote_folder_id_map[relative_path + '/'] = folder.get('id')
                self.logger(f"   UPLOADED: Folder {relative_path}")
                return True
            except HttpError as e:
                self.logger(f"❌ Error creating folder '{relative_path}': {e}")
                return False

        # --- Handle File Upload/Update ---
        
        # File metadata
        file_metadata = {
            'name': item_name,
            'parents': [parent_id]
        }
        
        local_mtime = os.path.getmtime(local_item_path)
        dt_object = datetime.fromtimestamp(local_mtime)
        file_metadata['modifiedTime'] = dt_object.isoformat("T") + "Z"

        media = MediaFileUpload(local_item_path, resumable=True)

        if self.dry_run:
            action = "UPDATE" if remote_file_id else "UPLOAD"
            self.logger(f"   [DRY RUN] {action}: {relative_path}")
            return True

        try:
            if remote_file_id:
                # Update existing file
                self.drive_service.files().update(fileId=remote_file_id, body=file_metadata, media_body=media).execute()
                self.logger(f"   UPDATED: {relative_path}")
            else:
                # Upload new file
                self.drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                self.logger(f"   UPLOADED: {relative_path}")
            return True
        except HttpError as e:
            self.logger(f"❌ Error during file operation for '{relative_path}': {e}")
            return False

    def _delete_file(self, file_id: str, relative_path: str):
        """Deletes a file or folder on Google Drive."""
        if not self.drive_service:
            raise RuntimeError("Drive service not initialized.")

        self.logger(f"   DELETING: {relative_path}")
        
        if self.dry_run:
            self.logger(f"   [DRY RUN] Would have deleted file/folder: {relative_path}")
            return True
        
        try:
            # We delete the item by its ID. Drive handles recursive deletion for folders.
            self.drive_service.files().delete(fileId=file_id).execute()
            self.logger(f"   DELETED: {relative_path}")
            return True
        except HttpError as e:
            self.logger(f"❌ Error deleting '{relative_path}': {e}")
            return False

    # NEW METHOD: Programmatic Sharing
    def _share_folder_with_user(self, file_id: str, user_email: str):
        """Shares a file/folder with a specific user email as an Editor."""
        if not self.drive_service:
            self.logger("Error: Drive service not initialized for sharing.")
            return True # Return True to not block the main process

        self.logger(f"\n🔒 Attempting to share folder with user: {user_email}")
        
        # 1. Check if permission already exists (to avoid redundancy/errors)
        # Check permissions is resource-intensive and prone to failure if the SA is not the owner.
        # We will try to create the permission directly and catch the 409 Conflict error if it exists.
        
        # 2. Grant new permission
        new_permission = {
            'type': 'user',
            'role': 'writer',  # 'writer' role = Editor permission
            'emailAddress': user_email
        }

        if self.dry_run:
            self.logger(f"   [DRY RUN] Would have shared folder ID {file_id} with {user_email} as Editor.")
            return True

        try:
            # sendNotificationEmail=True to notify the user they've been granted access
            self.drive_service.permissions().create(
                fileId=file_id,
                body=new_permission,
                sendNotificationEmail=True,
                fields='id' # Request minimal fields
            ).execute()
            self.logger(f"✅ Successfully shared folder with {user_email} as Editor. (Check their email for notification)")
            return True
        except HttpError as e:
            if e.resp.status == 409: # HTTP 409 Conflict typically means permission already exists
                self.logger(f"   Permission already exists for {user_email}. Skipping.")
                return True
            else:
                self.logger(f"❌ Error sharing folder with {user_email}. Check Service Account permissions: {e}")
                return False
        except Exception as e:
            self.logger(f"❌ Unexpected error during sharing: {e}")
            return False
            
    # ==============================================================================
    # 3. CORE SYNCHRONIZATION EXECUTION
    # ==============================================================================

    def execute_sync(self) -> tuple[bool, str]:
        """
        Main function to orchestrate the one-way sync logic.
        Returns (success_status, final_message).
        """
        try:
            # 1. Prerequisite Checks (Key file only, as we need to connect regardless of local path status)
            if not os.path.exists(self.key_file):
                return (False, f"Service Account key file '{self.key_file}' not found.")

            # 2. Initialize Drive Service and Find Destination Folder
            self._get_drive_service()
            dest_folder_id = self._find_or_create_destination_folder()
            
            if dest_folder_id is None and not self.dry_run:
                self.logger("❌ Failed to secure destination folder ID.")
                return (False, "Failed to secure destination folder ID.")
            
            # 3. Share folder if email provided (Done immediately after folder ID is secured)
            share_status_message = "No sharing requested."
            if dest_folder_id and self.share_email and '@' in self.share_email:
                if self._share_folder_with_user(dest_folder_id, self.share_email):
                    share_status_message = f"Folder shared with {self.share_email}."
                else:
                    return (False, "Failed to complete sharing operation.")
            elif self.share_email and '@' not in self.share_email:
                return (False, f"Invalid email format provided for sharing: {self.share_email}")

            # 4. Check Local Path validity *before* attempting file sync
            if not os.path.exists(self.local_path) or not os.path.isdir(self.local_path):
                # If local path is invalid, we return success if we were only trying to share/view remote
                if self.share_email or self.dry_run:
                    self.logger(f"⚠️ Local source path '{self.local_path}' is invalid. Skipping file synchronization.")
                    
                    # If sharing was requested, return a success message about the share status.
                    if self.share_email:
                        return (True, f"Share Action completed successfully. {share_status_message}")
                    
                    # Otherwise, return success for the dry run/view action.
                    return (True, "Dry Run/View Remote Map completed. Local file sync skipped.")
                else:
                    return (False, f"Local source path '{self.local_path}' does not exist or is not a directory. Sync failed.")


            # --- BEGIN FILE SYNCHRONIZATION LOGIC ---
            
            # 5. Get file maps (Remote map is now logged inside _get_remote_files_map)
            self.logger("📋 Comparing local and remote files recursively...")
            local_files = self._get_local_files_map()
            remote_files = self._get_remote_files_map()
            
            self.logger("\n--- Sync Operation Analysis & Execution ---")
            
            files_to_sync = 0
            files_to_delete = 0

            # Get keys for sorting (Folders first to ensure parents are created before children)
            # Folders have keys ending in '/'
            local_keys_sorted = sorted(local_files.keys(), key=lambda k: (local_files[k]['is_folder'], k))

            # A. Determine items to upload/update
            for relative_path in local_keys_sorted:
                local_data = local_files[relative_path]
                local_mtime = local_data['mtime']
                is_folder = local_data['is_folder']
                local_item_path = local_data['path']
                
                # Check for files and folders that need to be created or updated
                if relative_path in remote_files:
                    remote_data = remote_files[relative_path]
                    remote_mtime = remote_data['mtime']
                    remote_id = remote_data['id']
                    
                    # File/Folder exists remotely. Check if update is needed (only for files)
                    if not is_folder and local_mtime > remote_mtime + 1:
                        self._upload_file(local_item_path, relative_path, remote_id, is_folder=False)
                        files_to_sync += 1
                    
                    # Mark as processed to prevent deletion
                    remote_files.pop(relative_path) 
                else:
                    # Item exists locally but not remotely -> UPLOAD/CREATE
                    self._upload_file(local_item_path, relative_path, None, is_folder)
                    files_to_sync += 1

            # B. Determine items to delete (remaining items in remote_files map)
            # Sort files by path (Folders last to ensure children are removed before parent folder)
            remote_keys_to_delete = sorted(remote_files.keys(), key=lambda k: (remote_files[k]['is_folder'], k), reverse=True)
            
            for relative_path in remote_keys_to_delete:
                remote_data = remote_files[relative_path]
                # Check if this item is a folder and should be skipped for file key overlap
                if remote_data['is_folder'] and not relative_path.endswith('/'):
                    continue
                    
                self._delete_file(remote_data['id'], relative_path)
                files_to_delete += 1

            total_actions = files_to_sync + files_to_delete
            
            self.logger("\n--- Sync Execution Summary ---")
            
            if total_actions == 0:
                self.logger("✅ Sync successful! No changes required.")
                final_message = "No changes needed."
            else:
                self.logger(f"✅ Sync successful! Total actions: {total_actions} (Upload/Update/Create: {files_to_sync}, Delete: {files_to_delete})")
                status_word = "Simulated" if self.dry_run else "Completed"
                final_message = f"{status_word} with {total_actions} actions."
            
            return (True, final_message)

        except RuntimeError as e:
            # Handles authentication and folder creation failures (raised using SYNC_ERROR)
            return (False, f"Sync failed: {e}")
        except HttpError as e:
            self.logger(f"❌ Google API Error during sync: {e}")
            return (False, f"Sync failed due to API error: {e}")
        except Exception as e:
            self.logger(f"❌ An unexpected error occurred: {e}")
            return (False, f"Sync failed due to unexpected error: {e}")


# ==============================================================================
# 4. MAIN EXECUTION FLOW (Example of how to use the class)
# ==============================================================================

if __name__ == "__main__":
    
    # --- Configuration from Original Script ---
    SERVICE_ACCOUNT_FILE = 'service_account_key.json'
    LOCAL_SOURCE_PATH = "/path/to/local/source/folder" # CHANGE ME
    DRIVE_DESTINATION_FOLDER_NAME = "Scheduled_Backups/Current_Month"
    DRY_RUN = False 
    SHARE_EMAIL = "your.personal.email@example.com" # NEW: Change me if testing sharing
    # ------------------------------------------

    if LOCAL_SOURCE_PATH == "/path/to/local/source/folder":
        print("ERROR: Please update LOCAL_SOURCE_PATH in the __main__ block before running.")
        sys.exit(1)

    if DRY_RUN:
        print("\n=======================================================")
        print("          !!! D R Y   R U N   M O D E !!!")
        print("    No changes will be made to the Google Drive.")
        print("=======================================================\n")

    sync_manager = GoogleDriveSync(
        service_account_file=SERVICE_ACCOUNT_FILE,
        local_source_path=LOCAL_SOURCE_PATH,
        drive_destination_folder_name=DRIVE_DESTINATION_FOLDER_NAME,
        dry_run=DRY_RUN,
        user_email_to_share_with=SHARE_EMAIL
    )

    success, message = sync_manager.execute_sync()

    if success:
        print(f"\nScript finished successfully. Status: {message}")
        sys.exit(0)
    else:
        print(f"\nScript finished with failure. Error: {message}")
        sys.exit(1)
