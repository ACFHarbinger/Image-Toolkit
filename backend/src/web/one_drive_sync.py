import os
import msal
import shutil
import requests

from typing import Callable, Dict, Any
from ..utils.definitions import GRAPH_API_ENDPOINT


class OneDriveSync:
    """
    Manages synchronization for OneDrive using MS Graph API and MSAL.
    """
    def __init__(
        self,
        local_source_path: str,
        drive_destination_folder_name: str,
        client_id: str = None,
        client_secret: str = None, # Not typically used for Public Client (Desktop App) flow
        dry_run: bool = False,
        logger: Callable[[str], None] = print,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download"
    ):
        self.local_path = local_source_path
        self.remote_path = drive_destination_folder_name.strip("/")
        self.client_id = client_id
        self.dry_run = dry_run
        self.logger = logger
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        self._is_running = True
        
        self.access_token = None
        self.headers = None
        self.remote_path_to_id = {} # Cache for folder IDs

    def check_stop(self):
        if not self._is_running:
            raise InterruptedError("Synchronization manually interrupted.")

    def _authenticate(self):
        """
        Authenticates using MSAL Device Code Flow (safest for desktop apps without needing a redirect URI).
        """
        if not self.client_id:
            raise ValueError("OneDrive Client ID is missing.")

        scopes = ["Files.ReadWrite.All", "User.Read"]
        app = msal.PublicClientApplication(self.client_id)

        self.logger("🔑 Authenticating with Microsoft Graph...")
        
        # 1. Try silent token acquisition (cached)
        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])

        # 2. If silent fails, use Device Code Flow
        if not result:
            self.logger("   Initiating Device Code Flow...")
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise ValueError("Failed to create device flow.")

            # Show code to user in logs (Ideally this would be a popup, but logs work for now)
            self.logger(f"\n⚠️  ACTION REQUIRED ⚠️")
            self.logger(f"   1. Open: {flow['verification_uri']}")
            self.logger(f"   2. Enter Code: {flow['user_code']}")
            self.logger(f"   Waiting for authentication...\n")

            result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self.access_token = result["access_token"]
            self.headers = {'Authorization': 'Bearer ' + self.access_token}
            self.logger("✅ Authentication successful.")
        else:
            error = result.get("error")
            desc = result.get("error_description")
            raise RuntimeError(f"Authentication failed: {error} - {desc}")

    def _get_local_files_map(self) -> Dict[str, Dict[str, Any]]:
        """Creates a map of relative_path -> metadata for local files."""
        local_items = {}
        base_len = len(self.local_path) + len(os.sep) 

        for root, dirs, files in os.walk(self.local_path):
            self.check_stop()
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = abs_path[base_len:].replace(os.sep, '/')
                local_items[rel_path] = {'path': abs_path, 'is_folder': False}
            for d in dirs:
                abs_path = os.path.join(root, d)
                rel_path = abs_path[base_len:].replace(os.sep, '/')
                local_items[rel_path] = {'path': abs_path, 'is_folder': True}
        return local_items

    def _get_remote_files_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Recursively lists files from OneDrive.
        Since Graph API doesn't have a simple "recursive list" for a specific folder path easily accessible,
        we traverse layer by layer.
        """
        self.logger(f"🔍 Scanning remote folder: {self.remote_path}")
        remote_items = {}
        
        # Resolve root folder ID
        root_id = self._resolve_path_to_id(self.remote_path)
        if not root_id:
            self.logger("   Remote folder does not exist yet.")
            return {}

        # Queue for traversal: (folder_id, relative_path_prefix)
        queue = [(root_id, "")]

        while queue:
            self.check_stop()
            current_id, current_rel = queue.pop(0)
            
            url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{current_id}/children"
            
            while url:
                self.check_stop()
                response = requests.get(url, headers=self.headers)
                if response.status_code != 200:
                    self.logger(f"❌ Error listing children for {current_rel}: {response.text}")
                    break
                
                data = response.json()
                items = data.get('value', [])
                
                for item in items:
                    name = item['name']
                    item_id = item['id']
                    is_folder = 'folder' in item
                    rel_path = os.path.join(current_rel, name).replace(os.sep, '/') if current_rel else name
                    
                    remote_items[rel_path] = {
                        'id': item_id,
                        'is_folder': is_folder
                    }
                    
                    if is_folder:
                        queue.append((item_id, rel_path))
                        # Cache ID for potential uploads later
                        full_path_key = f"{self.remote_path}/{rel_path}" if self.remote_path else rel_path
                        self.remote_path_to_id[full_path_key] = item_id

                url = data.get('@odata.nextLink') # Pagination

        return remote_items

    def _resolve_path_to_id(self, path: str):
        """Resolves a remote path to an Item ID."""
        if not path: return "root"
        
        # Check cache
        if path in self.remote_path_to_id:
            return self.remote_path_to_id[path]

        url = f"{GRAPH_API_ENDPOINT}/me/drive/root:/{path}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            item_id = response.json()['id']
            self.remote_path_to_id[path] = item_id
            return item_id
        return None

    def _upload_file(self, local_path: str, rel_path: str):
        self.check_stop()
        target_path = f"{self.remote_path}/{rel_path}" if self.remote_path else rel_path
        
        if self.dry_run:
            self.logger(f"   [DRY RUN] UPLOAD: {rel_path}")
            return True

        # Graph API Upload (PUT)
        # For larger files, an upload session is needed. This handles small files (<4MB).
        url = f"{GRAPH_API_ENDPOINT}/me/drive/root:/{target_path}:/content"
        
        try:
            with open(local_path, 'rb') as f:
                response = requests.put(url, headers=self.headers, data=f)
            
            if response.status_code in [200, 201]:
                return True
            self.logger(f"❌ Error uploading {rel_path}: {response.text}")
            return False
        except Exception as e:
            self.logger(f"❌ Upload exception {rel_path}: {e}")
            return False

    def _create_remote_folder(self, rel_path: str):
        self.check_stop()
        # Determine parent path and name
        parts = rel_path.split('/')
        folder_name = parts[-1]
        parent_rel = "/".join(parts[:-1])
        
        full_parent_path = f"{self.remote_path}/{parent_rel}" if parent_rel else self.remote_path
        if not full_parent_path: full_parent_path = "" # root

        if self.dry_run:
            self.logger(f"   [DRY RUN] CREATE FOLDER: {rel_path}")
            return True

        parent_id = self._resolve_path_to_id(full_parent_path)
        if not parent_id:
            # If parent doesn't exist, we need to create it recursively
            # For simplicity, we assume standard recursive creation order from main loop handles this,
            # or we fail if deep nesting creation order is wrong.
            # In the execute_sync loop, we iterate ensuring parents are processed first.
            self.logger(f"❌ Cannot create {rel_path}, parent not found.")
            return False

        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{parent_id}/children"
        body = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "replace"
        }
        response = requests.post(url, headers=self.headers, json=body)
        if response.status_code == 201:
            new_id = response.json()['id']
            full_path = f"{self.remote_path}/{rel_path}" if self.remote_path else rel_path
            self.remote_path_to_id[full_path] = new_id
            return True
        self.logger(f"❌ Error creating folder {rel_path}: {response.text}")
        return False

    def _download_file(self, item_id: str, local_dest: str):
        self.check_stop()
        if self.dry_run:
            self.logger(f"   [DRY RUN] DOWNLOAD: {item_id} -> {os.path.basename(local_dest)}")
            return True

        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}/content"
        
        try:
            response = requests.get(url, headers=self.headers, stream=True)
            if response.status_code == 200:
                with open(local_dest, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            self.logger(f"❌ Error downloading {item_id}: {response.text}")
            return False
        except Exception as e:
            self.logger(f"❌ Download exception: {e}")
            return False

    def _delete_local(self, local_path: str):
        self.check_stop()
        if not os.path.exists(local_path): return True
        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE LOCAL: {local_path}")
            return True
        try:
            if os.path.isdir(local_path): shutil.rmtree(local_path)
            else: os.remove(local_path)
            return True
        except Exception as e:
            self.logger(f"❌ Error deleting local {local_path}: {e}")
            return False

    def _delete_remote(self, item_id: str, rel_path: str):
        self.check_stop()
        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE REMOTE: {rel_path}")
            return True
        
        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}"
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 204:
            return True
        self.logger(f"❌ Error deleting remote {rel_path}: {response.text}")
        return False

    def execute_sync(self) -> tuple[bool, str]:
        try:
            self._authenticate()
            self.check_stop()

            if not os.path.exists(self.local_path):
                return (False, f"Local path '{self.local_path}' does not exist.")

            # 1. Scan
            self.logger("📋 Scanning local and remote files...")
            local_items = self._get_local_files_map()
            remote_items = self._get_remote_files_map()
            
            self.logger(f"   Found {len(local_items)} local items.")
            self.logger(f"   Found {len(remote_items)} remote items.")

            # 2. Sync
            items_uploaded = 0
            items_downloaded = 0
            items_deleted_local = 0
            items_deleted_remote = 0
            items_skipped = 0
            items_ignored = 0
            
            items_skipped_remote = remote_items.copy()

            # Process Local
            for rel_path, local_data in local_items.items():
                self.check_stop()
                
                if local_data['is_folder']:
                    if rel_path in items_skipped_remote:
                        items_skipped_remote.pop(rel_path)
                    else:
                        # Folder local only
                        if self.action_local == "upload":
                            if self._create_remote_folder(rel_path): items_uploaded += 1
                        elif self.action_local == "delete_local":
                            self.logger(f"   DELETING LOCAL FOLDER: {rel_path}")
                            if self._delete_local(local_data['path']): items_deleted_local += 1
                        elif self.action_local == "ignore_local":
                            items_ignored += 1
                    continue

                remote_data = items_skipped_remote.get(rel_path)
                if remote_data:
                    items_skipped += 1
                    items_skipped_remote.pop(rel_path)
                else:
                    # Local orphan
                    if self.action_local == "upload":
                        self.logger(f"   UPLOADING: {rel_path}")
                        if self._upload_file(local_data['path'], rel_path): items_uploaded += 1
                    elif self.action_local == "delete_local":
                        self.logger(f"   DELETING LOCAL: {rel_path}")
                        if self._delete_local(local_data['path']): items_deleted_local += 1
                    elif self.action_local == "ignore_local":
                        self.logger(f"   IGNORING LOCAL: {rel_path}")
                        items_ignored += 1

            # Process Remote
            for rel_path, remote_data in items_skipped_remote.items():
                self.check_stop()
                
                if remote_data['is_folder']:
                    if self.action_remote == "delete_remote":
                        self.logger(f"   DELETING REMOTE FOLDER: {rel_path}")
                        if self._delete_remote(remote_data['id'], rel_path): items_deleted_remote += 1
                    continue

                if self.action_remote == "download":
                    self.logger(f"   DOWNLOADING: {rel_path}")
                    local_dest = os.path.join(self.local_path, rel_path)
                    if self._download_file(remote_data['id'], local_dest): items_downloaded += 1
                elif self.action_remote == "delete_remote":
                    self.logger(f"   DELETING REMOTE: {rel_path}")
                    if self._delete_remote(remote_data['id'], rel_path): items_deleted_remote += 1
                elif self.action_remote == "ignore_remote":
                    self.logger(f"   IGNORING REMOTE: {rel_path}")
                    items_ignored += 1

            total = items_uploaded + items_downloaded + items_deleted_local + items_deleted_remote
            
            self.logger("\n--- Sync Execution Summary ---")
            if total == 0 and items_ignored == 0:
                msg = "No changes needed."
            else:
                prefix = "Simulated" if self.dry_run else "Completed"
                msg = f"{prefix} {total} actions. (Up: {items_uploaded}, Down: {items_downloaded}, Del-L: {items_deleted_local}, Del-R: {items_deleted_remote})"
            
            self.logger(f"✅ {msg}")
            return (True, msg)

        except Exception as e:
            self.logger(f"❌ Error: {e}")
            return (False, str(e))
