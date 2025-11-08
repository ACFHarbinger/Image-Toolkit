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
    using a Service Account.
    """
    
    def __init__(
        self,
        service_account_file: str,
        local_source_path: str,
        drive_destination_folder_name: str,
        dry_run: bool = False,
        logger: Callable[[str], None] = print,  # Default to print if no logger provided
        user_email_to_share_with: Optional[str] = None
    ):
        """
        Initializes the sync manager with configuration parameters.
        
        :param service_account_file: Path to the Google Service Account JSON key file.
        :param local_source_path: Local folder path to synchronize.
        :param drive_destination_folder_name: Destination folder path inside Google Drive (e.g., "Backups/Current").
        :param dry_run: If True, simulate actions without modifying Drive.
        :param logger: Function used for logging output (defaults to built-in print).
        :param user_email_to_share_with: Optional email address to grant Editor access to the destination folder.
        """
        self.key_file = service_account_file
        self.local_path = local_source_path
        self.remote_path = drive_destination_folder_name
        self.dry_run = dry_run
        self.logger = logger
        self.share_email = user_email_to_share_with
        self.drive_service: Optional[Any] = None
        self.dest_folder_id: Optional[str] = None
        # Flag controlled by the worker thread's stop method
        self._is_running = True 
        
    def check_stop(self):
        """Checks the running flag and raises an exception if the stop signal was received."""
        if not self._is_running:
            raise InterruptedError("Synchronization manually interrupted.")

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
        Finds the ID of the destination folder by traversing the path, 
        creating subfolders if they don't exist, and stores the ID in self.dest_folder_id.
        """
        self.check_stop()
        
        # Maps local relative paths (including the filename or folder name) to their remote ID
        self.remote_path_to_id: Dict[str, str] = {}
        
        path_components = [p for p in self.remote_path.split('/') if p]
        current_parent_id = 'root'
        current_remote_path = ''
        
        self.logger(f"🔍 Locating/Creating destination path: /{self.remote_path}")

        if not self.drive_service:
             self.logger("Error: Drive service not initialized.")
             return None

        for folder_name in path_components:
            self.check_stop()
            
            # Construct the relative path for the map
            if current_remote_path:
                current_remote_path = f"{current_remote_path}/{folder_name}"
            else:
                current_remote_path = folder_name
                
            # Query for the folder using the current parent ID
            query = (
                f"name='{folder_name}' and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"'{current_parent_id}' in parents and "
                f"trashed=false"
            )
            try:
                # FIX: Simplified query structure to avoid 403 supportsAllDrives conflict on personal drives
                response = self.drive_service.files().list(
                    q=query, 
                    spaces='drive', 
                    fields='files(id, name)'
                ).execute()
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
                        current_parent_id = f"DRY_RUN_ID_{folder_name}"
                    else:
                        folder = self.drive_service.files().create(
                            body=file_metadata, 
                            fields='id'
                        ).execute()
                        current_parent_id = folder.get('id')
                        self.logger(f"   Created folder: {folder_name} (ID: {current_parent_id})")
                        
                # Store path mapping
                self.remote_path_to_id[current_remote_path] = current_parent_id
                        
            except HttpError as e:
                self.logger(f"❌ Error locating/creating folder '{folder_name}': {e}")
                return None
            except Exception as e:
                 self.logger(f"❌ Unexpected error in folder creation for '{folder_name}': {e}")
                 return None

        self.logger(f"✅ Destination Folder ID: {current_parent_id}")
        self.dest_folder_id = current_parent_id
        
        # Log URL only after loop completes and ID is confirmed
        if current_parent_id and not self.dry_run and not current_parent_id.startswith("DRY_RUN_ID"):
            drive_url = f"https://drive.google.com/drive/folders/{current_parent_id}"
            self.logger(f"🔗 Destination Folder URL: {drive_url}")
        
        # FIX: Guarantee the final ID is returned successfully
        return current_parent_id
            
    def _share_folder_with_user(self, file_id: str, user_email: str):
        """Shares a file/folder with a specific user email as an Editor."""
        self.check_stop()
        if not self.drive_service:
            self.logger("Error: Drive service not initialized for sharing.")
            return

        self.logger(f"🔒 Attempting to share folder with user: {user_email}")
        
        # Check if permission already exists (simplified check)
        try:
            permissions = self.drive_service.permissions().list(
                fileId=file_id,
                fields='permissions(id, emailAddress, role)',
                supportsAllDrives=True
            ).execute()
            
            for p in permissions.get('permissions', []):
                if p.get('emailAddress') == user_email and p.get('role') in ['writer', 'owner']:
                    self.logger("   Access already granted (Editor/Owner role). Skipping share.")
                    return True 

        except HttpError as e:
            self.logger(f"⚠️ Warning: Could not check existing permissions. Attempting to grant access: {e}")
            
        new_permission = {
            'type': 'user',
            'role': 'writer',  # 'writer' role corresponds to Editor permission level
            'emailAddress': user_email
        }

        if self.dry_run:
            self.logger(f"   [DRY RUN] Would have shared folder ID {file_id} with {user_email} as Editor.")
            return True

        try:
            self.drive_service.permissions().create(
                fileId=file_id,
                body=new_permission,
                sendNotificationEmail=False,
                supportsAllDrives=True
            ).execute()
            self.logger(f"✅ Shared folder ID {file_id} with {user_email} as Editor.")
            return True
        except HttpError as e:
            self.logger(f"❌ Error sharing folder with {user_email}. Access likely denied or already set: {e}")
            return False
        except Exception as e:
            self.logger(f"❌ Unexpected error during sharing: {e}")
            return False
            
    def _get_local_files_map(self) -> Dict[str, Dict[str, Any]]:
        """Creates a map of relative_path -> (absolute_path, timestamp) for all local files/folders."""
        local_items: Dict[str, Dict[str, Any]] = {}
        base_path = os.path.normpath(self.local_path)
        base_len = len(base_path) + len(os.sep) 

        for root, dirs, files in os.walk(base_path):
            self.check_stop()

            for d in dirs:
                abs_path = os.path.join(root, d)
                rel_path = abs_path[base_len:].replace(os.sep, '/')
                local_items[rel_path] = {'path': abs_path, 'mtime': int(os.path.getmtime(abs_path)), 'is_folder': True}

            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = abs_path[base_len:].replace(os.sep, '/')
                local_items[rel_path] = {'path': abs_path, 'mtime': int(os.path.getmtime(abs_path)), 'is_folder': False}
                
        return local_items

    def _get_remote_files_map(self) -> Dict[str, Dict[str, Any]]:
        """Creates a map of relative_path -> (file_id, timestamp, is_folder) for remote items."""
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        remote_items: Dict[str, Dict[str, Any]] = {}
        id_to_rel_path: Dict[str, str] = {self.dest_folder_id: ''}
        
        # Query items within the destination folder or shared with me
        query = f"'{self.dest_folder_id}' in parents and trashed=false"
        
        items: List[Any] = []
        page_token = None
        while True:
            self.check_stop()
            try:
                response = self.drive_service.files().list(
                    q=query, 
                    spaces='drive', 
                    fields='nextPageToken, files(id, name, modifiedTime, mimeType, parents)',
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    pageToken=page_token
                ).execute()
            except HttpError as e:
                self.logger(f"❌ Error listing remote files: {e}")
                raise RuntimeError(SYNC_ERROR)
                
            items.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
                
        # Build path map from the retrieved files
        for item in items:
            self.check_stop()
            # This logic assumes a file/folder has exactly one parent (the destination folder)
            if item.get('parents'):
                parent_id = item['parents'][0]
                if parent_id in id_to_rel_path:
                    parent_path = id_to_rel_path[parent_id]
                    current_rel_path = os.path.join(parent_path, item['name']).replace(os.sep, '/')
                    id_to_rel_path[item['id']] = current_rel_path

        # Populate remote items map
        for item in items:
            self.check_stop()
            item_id = item['id']
            if item_id in id_to_rel_path and item_id != self.dest_folder_id:
                modified_time_iso = item.get('modifiedTime')
                timestamp = 0
                try:
                    dt_object = datetime.strptime(modified_time_iso, "%Y-%m-%dT%H:%M:%S.%fZ")
                    timestamp = int(dt_object.timestamp())
                except (ValueError, TypeError):
                    pass 
                
                remote_items[id_to_rel_path[item_id]] = {
                    'id': item_id, 
                    'mtime': timestamp, 
                    'is_folder': item['mimeType'] == 'application/vnd.google-apps.folder'
                }
                
        # Debugging: Log items found in remote
        self.logger(f"\n--- Current Remote Files in Destination Folder ---")
        if not remote_items:
            self.logger("   (Folder is empty)")
        else:
            # Log only file paths, not IDs
            for path in sorted(remote_items.keys()):
                item = remote_items[path]
                item_type = "[Folder]" if item['is_folder'] else "[File]"
                self.logger(f"   {item_type} {path} (Modified: {datetime.fromtimestamp(item['mtime']).strftime('%Y-%m-%d %H:%M:%S')})")
        self.logger("--------------------------------------------------")

        return remote_items

    def _create_remote_folder(self, rel_path: str):
        """Creates a remote folder given its relative path, returning its ID."""
        self.check_stop()
        parent_rel_path = os.path.dirname(rel_path).replace(os.sep, '/')
        parent_id = self.remote_path_to_id.get(parent_rel_path) or self.dest_folder_id
        folder_name = os.path.basename(rel_path)
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        
        if self.dry_run:
            new_id = f"DRY_RUN_ID_{folder_name}"
            self.logger(f"   [DRY RUN] Creating remote folder: {rel_path}")
            self.remote_path_to_id[rel_path] = new_id
            return new_id

        try:
            folder = self.drive_service.files().create(
                body=file_metadata, 
                fields='id',
                supportsAllDrives=True
            ).execute()
            new_id = folder.get('id')
            self.logger(f"   Created remote folder: {rel_path} (ID: {new_id})")
            self.remote_path_to_id[rel_path] = new_id
            return new_id
        except HttpError as e:
            self.logger(f"❌ Error creating folder '{rel_path}': {e}")
            raise RuntimeError(SYNC_ERROR)


    def _upload_file(self, local_file_path: str, file_name: str, remote_file_id: Optional[str], rel_path: str):
        """Uploads or updates a file."""
        self.check_stop()
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        parent_rel_path = os.path.dirname(rel_path).replace(os.sep, '/')
        parent_id = self.remote_path_to_id.get(parent_rel_path) or self.dest_folder_id

        file_metadata = {'name': file_name}
        
        local_mtime = os.path.getmtime(local_file_path)
        dt_object = datetime.fromtimestamp(local_mtime)
        file_metadata['modifiedTime'] = dt_object.isoformat("T") + "Z"

        media = MediaFileUpload(local_file_path, resumable=True)

        if self.dry_run:
            action = "UPDATE" if remote_file_id else "UPLOAD"
            self.logger(f"   [DRY RUN] {action}: {rel_path}")
            return True

        try:
            if remote_file_id:
                self.drive_service.files().update(
                    fileId=remote_file_id, 
                    body=file_metadata,
                    media_body=media,
                    addParents=parent_id, 
                    supportsAllDrives=True
                ).execute()
            else:
                file_metadata['parents'] = [parent_id]
                self.drive_service.files().create(
                    body=file_metadata, 
                    media_body=media, 
                    fields='id, parents', 
                    supportsAllDrives=True,
                ).execute()
            return True
        except HttpError as e:
            self.logger(f"❌ Error during file operation for '{rel_path}': {e}")
            return False

    def _delete_file(self, file_id: str, remote_name: str):
        """Deletes a file or folder on Google Drive."""
        self.check_stop()
        if not self.drive_service:
            raise RuntimeError("Drive service not initialized.")

        self.logger(f"   DELETING: {remote_name}")
        
        if self.dry_run:
            self.logger(f"   [DRY RUN] Would have deleted file/folder: {remote_name}")
            return True
        
        try:
            self.drive_service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
            return True
        except HttpError as e:
            self.logger(f"❌ Error deleting '{remote_name}': {e}")
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
            # 1. Prerequisite Checks
            self.check_stop()
            
            local_path_exists = os.path.exists(self.local_path)
            local_path_is_dir = os.path.isdir(self.local_path)
            
            if not os.path.exists(self.key_file):
                return (False, f"Service Account key file '{self.key_file}' not found.")

            # 2. Initialize Drive Service and Find Destination Folder
            self._get_drive_service()
            dest_folder_id = self._find_or_create_destination_folder()
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")
            
            if dest_folder_id is None and not self.dry_run:
                self.logger("❌ Failed to secure destination folder ID.")
                return (False, "Failed to secure destination folder ID.")
            
            # 2a. Share the destination folder if email provided
            if self.share_email and dest_folder_id and not dest_folder_id.startswith("DRY_RUN_ID"):
                self._share_folder_with_user(dest_folder_id, self.share_email)
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")

            if not local_path_exists or not local_path_is_dir:
                if self.share_email:
                    return (True, "Share Action Completed. Local sync skipped due to invalid source path.")
                else:
                    return (False, f"Local source path '{self.local_path}' does not exist or is not a directory.")

            # 3. Get file maps
            self.logger("📋 Comparing local and remote files recursively...")
            local_items = self._get_local_files_map()
            remote_items = self._get_remote_files_map()
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")

            self.logger("\n--- Sync Operation Analysis & Execution ---")
            
            items_to_sync = 0
            items_to_delete = 0
            remaining_remote = remote_items.copy()

            # A. Determine items to upload/update/create folder
            for rel_path, local_data in local_items.items():
                self.check_stop()
                local_mtime = local_data['mtime']
                
                if local_data['is_folder']:
                    if rel_path not in remaining_remote:
                        self.check_stop()
                        self._create_remote_folder(rel_path)
                    else:
                        remaining_remote.pop(rel_path)
                    continue

                # --- Handle Files (Upload/Update) ---
                remote_data = remaining_remote.get(rel_path)
                
                if remote_data:
                    remote_mtime = remote_data['mtime']
                    remote_id = remote_data['id']
                    
                    if local_mtime > remote_mtime + 1:
                        self.logger(f"   UPDATING: {rel_path} (Local newer)")
                        self._upload_file(local_data['path'], os.path.basename(rel_path), remote_id, rel_path)
                        items_to_sync += 1
                    
                    remaining_remote.pop(rel_path) 
                else:
                    self.logger(f"   UPLOADING: {rel_path} (New item)")
                    self._upload_file(local_data['path'], os.path.basename(rel_path), None, rel_path)
                    items_to_sync += 1

            # B. Determine items to delete
            for remote_name in sorted(remaining_remote.keys(), key=lambda x: x.count('/'), reverse=True):
                self.check_stop()
                remote_data = remaining_remote[remote_name]
                self._delete_file(remote_data['id'], remote_name)
                items_to_delete += 1

            total_actions = items_to_sync + items_to_delete
            
            self.logger("\n--- Sync Execution Summary ---")
            
            if total_actions == 0:
                self.logger("✅ Sync successful! No changes required.")
                final_message = "No changes needed."
            else:
                self.logger(f"✅ Sync successful! Total actions: {total_actions} (Upload/Update: {items_to_sync}, Delete: {items_to_delete})")
                status_word = "Simulated" if self.dry_run else "Completed"
                final_message = f"{status_word} with {total_actions} actions."
            
            return (True, final_message)

        except InterruptedError:
            return (False, "Synchronization manually cancelled.")
        except RuntimeError as e:
            return (False, f"Sync failed: {e}")
        except HttpError as e:
            self.logger(f"❌ Google API Error during sync: {e}")
            return (False, f"Sync failed due to API error: {e}")
        except Exception as e:
            self.logger(f"❌ An unexpected error occurred: {e}")
            return (False, f"Sync failed due to unexpected error: {e}")

    def check_stop_status(self, dest_folder_id: Optional[str]) -> bool:
        """Helper to centralize the check_stop call and logging."""
        try:
            self.check_stop()
            return True
        except InterruptedError:
            return False
