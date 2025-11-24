import os
import io
import datetime
import shutil

from typing import Callable, Dict, Any, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from ..utils.definitions import SCOPES, SYNC_ERROR


class GoogleDriveSync:
    """
    Manages synchronization with configurable strategies for missing files.
    Supports both Service Account and Personal Account (OAuth) flows.
    """

    def __init__(
        self,
        local_source_path: str,
        drive_destination_folder_name: str,
        # Auth Data (Dictionaries, not paths)
        service_account_data: Optional[Dict[str, Any]] = None,
        client_secrets_data: Optional[Dict[str, Any]] = None,
        token_file: Optional[str] = None, # Path needed for persistence of OAuth tokens
        dry_run: bool = False,
        logger: Callable[[str], None] = print,
        user_email_to_share_with: Optional[str] = None,
        action_local_orphans: str = "upload", # "upload", "delete_local", or "ignore_local"
        action_remote_orphans: str = "download" # "download", "delete_remote", or "ignore_remote"
    ):
        """
        Initializes the sync manager with configuration parameters.
        """
        self.local_path = local_source_path
        self.remote_path = drive_destination_folder_name
        
        # Authentication Data
        self.sa_data = service_account_data
        self.cs_data = client_secrets_data
        self.token_file = token_file
        
        self.dry_run = dry_run
        self.logger = logger
        self.share_email = user_email_to_share_with
        
        # Sync Behavior
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        
        self.drive_service: Optional[Any] = None
        self.dest_folder_id: Optional[str] = None
        self._is_running = True 
        
    def check_stop(self):
        """Checks the running flag and raises an exception if the stop signal was received."""
        if not self._is_running:
            raise InterruptedError("Synchronization manually interrupted.")

    # ==============================================================================
    # 2. HELPER METHODS: DRIVE & AUTH
    # ==============================================================================

    def _get_drive_service(self):
        """
        Authenticates using either Service Account or Personal Account OAuth 2.0 flow.
        """
        if self.sa_data:
            self._auth_service_account()
        elif self.cs_data:
            self._auth_personal_account()
        else:
            self.logger("❌ Authentication Error: Missing both Service Account data and Client Secrets data.")
            raise RuntimeError(SYNC_ERROR)

    def _auth_service_account(self):
        """
        Authenticates using the Service Account flow with decrypted credentials.
        """
        self.logger("🔑 Authenticating with Google Drive (Service Account)...")
        try:
            # Check for required keys using literals directly
            if 'client_email' not in self.sa_data or 'private_key' not in self.sa_data:
                self.logger("❌ Authentication Error: Service account data is malformed.")
                raise RuntimeError(SYNC_ERROR)
            
            # Create credentials directly from the dictionary
            creds = service_account.Credentials.from_service_account_info(
                self.sa_data, scopes=SCOPES
            )
            
            self.drive_service = build('drive', 'v3', credentials=creds)
            self.logger("✅ Authentication successful.")

        except Exception as e:
            self.logger(f"❌ An unexpected authentication error occurred (Service Account): {e}")
            raise RuntimeError(SYNC_ERROR)

    def _auth_personal_account(self):
        """
        Authenticates using the Personal Account OAuth 2.0 flow with decrypted secrets.
        Uses InstalledAppFlow.from_client_config to avoid writing temp files.
        """
        self.logger("🔑 Authenticating with Google Drive (Personal Account)...")
        creds: Optional[Credentials] = None
        
        if not self.token_file:
            self.logger("❌ Authentication Error: Token file path is required for Personal Account.")
            raise RuntimeError(SYNC_ERROR)

        try:
            # 1. Try to load existing token
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            # 2. Refresh or Login if invalid
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.logger("   Refreshing expired token...")
                    creds.refresh(Request())
                else:
                    self.logger("   No valid token found. Starting OAuth flow...")
                    
                    # Validate client secrets data structure
                    if 'installed' not in self.cs_data and 'web' not in self.cs_data:
                        self.logger("❌ Authentication Error: Client secrets data invalid (missing 'installed' or 'web' key).")
                        raise RuntimeError(SYNC_ERROR)

                    # Initialize flow from dictionary
                    flow = InstalledAppFlow.from_client_config(
                        self.cs_data, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                self.logger(f"   Token saved to {self.token_file}")

            self.drive_service = build('drive', 'v3', credentials=creds)
            self.logger("✅ Authentication successful.")
        
        except Exception as e:
            self.logger(f"❌ An unexpected authentication error occurred: {e}")
            raise RuntimeError(SYNC_ERROR)

    def _find_or_create_destination_folder(self) -> Optional[str]:
        """
        Finds the ID of the destination folder by traversing the path, 
        creating subfolders if they don't exist.
        """
        self.check_stop()
        
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
            
            if current_remote_path:
                current_remote_path = f"{current_remote_path}/{folder_name}"
            else:
                current_remote_path = folder_name
                
            query = (
                f"name='{folder_name}' and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"'{current_parent_id}' in parents and "
                f"trashed=false"
            )
            try:
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
                        
                self.remote_path_to_id[current_remote_path] = current_parent_id
                        
            except HttpError as e:
                self.logger(f"❌ Error locating/creating folder '{folder_name}': {e}")
                return None
            except Exception as e:
                 self.logger(f"❌ Unexpected error in folder creation for '{folder_name}': {e}")
                 return None

        self.logger(f"✅ Destination Folder ID: {current_parent_id}")
        self.dest_folder_id = current_parent_id
        
        if current_parent_id and not self.dry_run and not current_parent_id.startswith("DRY_RUN_ID"):
            drive_url = f"https://drive.google.com/drive/folders/{current_parent_id}"
            self.logger(f"🔗 Destination Folder URL: {drive_url}")
        
        return current_parent_id
            
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
        """
        Creates a recursive map of relative_path -> (file_id, timestamp, is_folder) for remote items 
        by using a queue (BFS).
        """
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        remote_items: Dict[str, Dict[str, Any]] = {}
        
        # Queue: (folder_id, relative_path_string)
        folder_queue = [(self.dest_folder_id, '')]
        
        while folder_queue:
            self.check_stop()
            current_folder_id, current_rel_path = folder_queue.pop(0)
            
            # Query for immediate children of the current folder
            query = f"'{current_folder_id}' in parents and trashed=false"
            
            page_token = None
            while True:
                self.check_stop()
                try:
                    response = self.drive_service.files().list(
                        q=query, 
                        spaces='drive', 
                        fields='nextPageToken, files(id, name, modifiedTime, mimeType)',
                        pageToken=page_token
                    ).execute()
                except HttpError as e:
                    self.logger(f"❌ Error listing remote files: {e}")
                    raise RuntimeError(SYNC_ERROR)
                    
                items = response.get('files', [])
                
                for item in items:
                    item_name = item['name']
                    full_path = os.path.join(current_rel_path, item_name).replace(os.sep, '/')
                    item_id = item['id']

                    is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'

                    if is_folder:
                        folder_queue.append((item_id, full_path))
                        self.remote_path_to_id[full_path] = item_id 
                    
                    modified_time_iso = item.get('modifiedTime')
                    timestamp = 0
                    try:
                        if modified_time_iso and '.' in modified_time_iso:
                            dt_object = datetime.datetime.strptime(modified_time_iso, "%Y-%m-%dT%H:%M:%S.%fZ")
                        elif modified_time_iso:
                            dt_object = datetime.datetime.strptime(modified_time_iso, "%Y-%m-%dT%H:%M:%SZ")
                        timestamp = int(dt_object.timestamp())
                    except (ValueError, TypeError):
                        pass 
                    
                    remote_items[full_path] = {
                        'id': item_id, 
                        'mtime': timestamp, 
                        'is_folder': is_folder
                    }

                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
                
        self.logger(f"\n--- Current Remote Files in Destination Folder ---")
        if not remote_items:
            self.logger("   (Folder is empty)")
        else:
            for path in sorted(remote_items.keys()):
                item = remote_items[path]
                item_type = "[Folder]" if item['is_folder'] else "[File]"
                self.logger(f"   {item_type} {path} (Modified: {datetime.datetime.fromtimestamp(item['mtime']).strftime('%Y-%m-%d %H:%M:%S')})")
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
                fields='id'
            ).execute()
            new_id = folder.get('id')
            self.logger(f"   Created remote folder: {rel_path} (ID: {new_id})")
            self.remote_path_to_id[rel_path] = new_id
            return new_id
        except HttpError as e:
            self.logger(f"❌ Error creating folder '{rel_path}': {e}")
            raise RuntimeError(SYNC_ERROR)


    def _upload_file(self, local_file_path: str, file_name: str, remote_file_id: Optional[str], rel_path: str):
        """Uploads a new file (remote_file_id should be None in this sync mode)."""
        self.check_stop()
        if not self.drive_service or not self.dest_folder_id:
            raise RuntimeError("Drive service or destination ID not set.")

        parent_rel_path = os.path.dirname(rel_path).replace(os.sep, '/')
        parent_id = self.remote_path_to_id.get(parent_rel_path) or self.dest_folder_id

        file_metadata = {'name': file_name}
        
        # Set modified time based on local file for metadata consistency
        local_mtime = os.path.getmtime(local_file_path)
        dt_object = datetime.datetime.fromtimestamp(local_mtime)
        file_metadata['modifiedTime'] = dt_object.isoformat("T") + "Z"

        media = MediaFileUpload(local_file_path, resumable=True)

        if self.dry_run:
            self.logger(f"   [DRY RUN] UPLOAD: {rel_path}")
            return True

        try:
            file_metadata['parents'] = [parent_id]
            self.drive_service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id, parents'
            ).execute()
            return True
        except HttpError as e:
            self.logger(f"❌ Error during file upload for '{rel_path}': {e}")
            return False

    def _download_file(self, file_id: str, local_destination_path: str) -> bool:
        """Downloads a file's content and saves it to the local filesystem."""
        self.check_stop()
        if not self.drive_service:
            raise RuntimeError("Drive service not initialized.")

        local_dir = os.path.dirname(local_destination_path)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
            
        if self.dry_run:
            self.logger(f"   [DRY RUN] Download: {os.path.basename(local_destination_path)}")
            return True

        try:
            request = self.drive_service.files().get(fileId=file_id, alt='media')
            
            # Use io.FileIO to write the content directly to the file
            file_handle = io.FileIO(local_destination_path, 'wb')
            
            # Download the file content in chunks
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            file_handle.close()
            return True
            
        except HttpError as e:
            self.logger(f"❌ Error downloading file ID {file_id}: {e}")
            return False
        except Exception as e:
            self.logger(f"❌ Unexpected error during download: {e}")
            return False

    def _delete_local_content(self, path: str) -> bool:
        """Deletes a file or folder from the local filesystem."""
        self.check_stop()
        if not os.path.exists(path):
            return True
            
        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE LOCAL: {path}")
            return True
            
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True
        except Exception as e:
            self.logger(f"❌ Error deleting local path '{path}': {e}")
            return False

    def _delete_remote_content(self, file_id: str, rel_path: str) -> bool:
        """Deletes a file or folder from Google Drive."""
        self.check_stop()
        if not self.drive_service:
            raise RuntimeError("Drive service not initialized.")
            
        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE REMOTE: {rel_path} (ID: {file_id})")
            return True
            
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            return True
        except HttpError as e:
            self.logger(f"❌ Error deleting remote file ID {file_id}: {e}")
            return False

    # ==============================================================================
    # 3. CORE SYNCHRONIZATION EXECUTION
    # ==============================================================================

    def execute_sync(self) -> tuple[bool, str]:
        """
        Main function to orchestrate the synchronization logic based on selected actions.
        """
        try:
            self.check_stop()
            
            local_path_exists = os.path.exists(self.local_path)
            local_path_is_dir = os.path.isdir(self.local_path)
            
            self._get_drive_service()
            dest_folder_id = self._find_or_create_destination_folder()
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")
            
            if dest_folder_id is None and not self.dry_run:
                self.logger("❌ Failed to secure destination folder ID.")
                return (False, "Failed to secure destination folder ID.")
            
            # --- Share Logic (Only for Service Accounts) ---
            if self.share_email and dest_folder_id and not dest_folder_id.startswith("DRY_RUN_ID"):
                if self.sa_data:
                    self.logger(f"ℹ️  [Note] Sharing functionality with {self.share_email} is pending implementation.")
                else:
                    self.logger("Skipping Share Action: Sharing is only relevant for Service Account flow.")
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")

            if not local_path_exists or not local_path_is_dir:
                return (False, f"Local source path '{self.local_path}' does not exist or is not a directory.")

            self.logger("📋 Comparing local and remote files recursively...")
            local_items = self._get_local_files_map()
            remote_items = self._get_remote_files_map()
            
            if not self.check_stop_status(dest_folder_id): return (False, "Synchronization manually interrupted.")

            self.logger("\n--- Sync Operation Analysis and Execution ---")
            
            items_uploaded = 0
            items_downloaded = 0
            items_deleted_local = 0
            items_deleted_remote = 0
            items_skipped = 0
            items_ignored = 0
            
            # Tracker for remote items to know which have been processed/matched against local
            items_skipped_remote = remote_items.copy() 

            # 1. Process Local Items (Upload or Delete Local)
            for rel_path, local_data in local_items.items():
                self.check_stop()
                
                # --- FOLDERS ---
                if local_data['is_folder']:
                    if rel_path not in items_skipped_remote:
                        # Folder exists locally but not remotely
                        if self.action_local == "upload":
                            self.check_stop()
                            self._create_remote_folder(rel_path)
                        elif self.action_local == "delete_local":
                            self.logger(f"   DELETING LOCAL: {rel_path} (Recursive folder delete)")
                            if self._delete_local_content(local_data['path']):
                                items_deleted_local += 1
                        elif self.action_local == "ignore_local":
                            self.logger(f"   IGNORING LOCAL: {rel_path} (Action set to 'Do Nothing')")
                            items_ignored += 1
                    else:
                        # Folder exists in both
                        items_skipped_remote.pop(rel_path)
                    continue

                # --- FILES ---
                remote_data = items_skipped_remote.get(rel_path)
                
                if remote_data:
                    # File exists in both places. Match found.
                    self.logger(f"   SKIPPING: {rel_path} (File exists locally and remotely)")
                    items_skipped += 1
                    items_skipped_remote.pop(rel_path)
                else:
                    # File exists LOCALLY but not REMOTELY (Local Orphan)
                    if self.action_local == "upload":
                        self.logger(f"   UPLOADING: {rel_path}")
                        if self._upload_file(local_data['path'], os.path.basename(rel_path), None, rel_path):
                            items_uploaded += 1
                    elif self.action_local == "delete_local":
                        self.logger(f"   DELETING LOCAL: {rel_path} (Orphaned file)")
                        if self._delete_local_content(local_data['path']):
                            items_deleted_local += 1
                    elif self.action_local == "ignore_local":
                        self.logger(f"   IGNORING LOCAL: {rel_path} (Action set to 'Do Nothing')")
                        items_ignored += 1

            # 2. Process Remaining Remote Items (Download or Delete Remote)
            # Remaining items in items_skipped_remote exist *only* on the remote side.
            for rel_path, remote_data in items_skipped_remote.items():
                self.check_stop()
                
                # Remote Orphan
                if self.action_remote == "download":
                    if remote_data['is_folder']:
                        continue # Folders handled by file paths creation, or ignored
                    
                    self.logger(f"   DOWNLOADING: {rel_path}")
                    if self._download_file(remote_data['id'], os.path.join(self.local_path, rel_path)):
                        items_downloaded += 1
                        
                elif self.action_remote == "delete_remote":
                    self.logger(f"   DELETING REMOTE: {rel_path}")
                    if self._delete_remote_content(remote_data['id'], rel_path):
                        items_deleted_remote += 1
                
                elif self.action_remote == "ignore_remote":
                    self.logger(f"   IGNORING REMOTE: {rel_path} (Action set to 'Do Nothing')")
                    items_ignored += 1
                
            total_actions = items_uploaded + items_downloaded + items_deleted_local + items_deleted_remote
            
            self.logger("\n--- Sync Execution Summary ---")
            
            if total_actions == 0 and items_ignored == 0:
                self.logger(f"✅ Sync successful! No changes required. ({items_skipped} items matched)")
                final_message = "No changes needed."
            else:
                status_word = "Simulated" if self.dry_run else "Completed"
                self.logger(f"✅ Sync successful! Total actions: {total_actions}")
                self.logger(f"   Uploads: {items_uploaded}, Downloads: {items_downloaded}")
                self.logger(f"   Local Deletes: {items_deleted_local}, Remote Deletes: {items_deleted_remote}")
                self.logger(f"   Items Ignored: {items_ignored}, Items Skipped (Matched): {items_skipped}")
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
