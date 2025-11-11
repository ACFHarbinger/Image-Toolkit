import jpype
import time
import json # Added for JSON serialization/deserialization
import hashlib # Added for secure hashing
import os # Added for secure salt and pepper generation

try:
    import app.src.utils.definitions as udef
except:
    import src.utils.definitions as udef

from jpype.types import JArray, JChar


class JavaVaultManager:
    """
    A Python wrapper to manage the SecureJsonVault by calling
    the compiled Java code via Jpype.
    """
    @staticmethod
    def _load_or_generate_pepper():
        """
        Checks for the pepper file. If it doesn't exist, it generates a new 
        secure pepper and saves it.
        """
        # Ensure the directory for crypto files exists
        os.makedirs(udef.CRYPTO_DIR, exist_ok=True)
        
        if os.path.exists(udef.PEPPER_FILE):
            print(f"Loading existing pepper from: {udef.PEPPER_FILE}")
            with open(udef.PEPPER_FILE, 'r') as f:
                pepper = f.read().strip()
                if not pepper:
                    raise ValueError(f"Pepper file is empty: {udef.PEPPER_FILE}. Delete it to regenerate.")
                return pepper
        else:
            print(f"Pepper file not found. Generating new pepper at: {udef.PEPPER_FILE}")
            # Generate a strong, random pepper (32 bytes = 64 hex characters)
            pepper = os.urandom(32).hex()
            
            # Save the new pepper to the file
            with open(udef.PEPPER_FILE, 'w') as f:
                f.write(pepper)
            
            # Set restrictive permissions (read-only for owner, if supported)
            try:
                os.chmod(udef.PEPPER_FILE, 0o400)
            except OSError:
                # Handle systems that don't support chmod (like some Windows systems)
                print("Warning: Could not set restrictive file permissions on pepper file.")

            return pepper

    def __init__(self, bc_provider_path: str = None):
        """
        Initializes the wrapper, starts the JVM, and loads the pepper.
        """
        # --- Load or generate the secret pepper first ---
        self.PEPPER = self._load_or_generate_pepper()

        if not jpype.isJVMStarted():
            classpath = [udef.JAR_FILE]
            if bc_provider_path:
                classpath.append(f"{bc_provider_path}/*") 
                
            print(f"Starting JVM with classpath: {classpath}")
            jpype.startJVM(classpath=classpath)        
        try:
            KeyStoreManagerClass = jpype.JClass("com.personal.image_toolkit.KeyStoreManager")
            self.SecureJsonVault = jpype.JClass("com.personal.image_toolkit.SecureJsonVault")
            
            self.keystore_manager = KeyStoreManagerClass()
            
        except jpype.JException as e:
            print("\n--- ERROR ---")
            print(f"Could not find Java class: {e}")
            raise
            
        self.JString = jpype.JClass("java.lang.String")

        self.keystore = None
        self.secret_key = None
        self.vault = None

    def _to_char_array(self, py_string: str) -> 'JArray[JChar]':
        """Helper to convert a Python string to a Java char[]."""
        return self.JString(py_string).toCharArray()

    def load_keystore(self, keystore_path: str, keystore_pass: str):
        """
        Loads the Java KeyStore from a file.
        """
        try:
            print(f"Loading keystore: {keystore_path}")
            self.keystore = self.keystore_manager.loadKeyStore(
                keystore_path,
                self._to_char_array(keystore_pass)
            )
            print("Keystore loaded successfully.")
        except Exception as e:
            print(f"Java Error loading keystore: {e}")
            raise

    def contains_alias(self, key_alias: str) -> bool:
        """
        Checks if the loaded KeyStore contains an entry for the given alias.
        """
        if self.keystore is None:
            raise ValueError("Keystore is not loaded. Call load_keystore() first.")
        
        try:
            return self.keystore.containsAlias(key_alias)
        except Exception as e:
            print(f"Java Error checking alias: {e}")
            raise

    def create_key_if_missing(self, key_alias: str, keystore_path: str, keystore_pass: str):
        """
        Checks if the secret key exists in the loaded KeyStore. If not,
        it generates a new key, stores it, and saves the KeyStore file.
        """
        if self.keystore is None:
            raise ValueError("Keystore is not loaded. Call load_keystore() first.")
            
        if not self.contains_alias(key_alias):
            print(f"Key entry '{key_alias}' not found. Generating and storing new key...")
            
            # 1. Store the new key entry in the loaded keystore object (in memory)
            self.keystore_manager.storeSecretKey(
                self.keystore,
                key_alias,
                self._to_char_array(keystore_pass)
            )
            
            # 2. Save the keystore to disk to persist the new key
            self.keystore_manager.saveKeyStore(
                self.keystore,
                keystore_path,
                self._to_char_array(keystore_pass)
            )
            print(f"Secret key created and KeyStore saved to {keystore_path}.")
        else:
            print(f"Key entry '{key_alias}' already exists. Skipping creation.")

    def get_secret_key(self, key_alias: str, key_pass: str):
        """
        Retrieves the AES SecretKey from the loaded KeyStore.
        """
        if self.keystore is None:
            raise ValueError("Keystore is not loaded. Call load_keystore() first.")
        
        try:
            print(f"Retrieving secret key for alias: {key_alias}")
            self.secret_key = self.keystore_manager.getSecretKey(
                self.keystore,
                key_alias,
                self._to_char_array(key_pass)
            )
            if self.secret_key is None:
                # This should only happen if the key type is wrong or password is bad
                raise ValueError(f"No secret key found for alias '{key_alias}' or wrong password.")
            print("SecretKey retrieved.")
        except Exception as e:
            print(f"Java Error getting secret key: {e}")
            raise

    def init_vault(self, vault_file_path: str):
        """
        Initializes the SecureJsonVault with the retrieved SecretKey.
        """
        if self.secret_key is None:
            raise ValueError("Secret key is not loaded. Call get_secret_key() first.")
        
        print(f"Initializing secure vault at: {vault_file_path}")
        self.vault = self.SecureJsonVault(self.secret_key, vault_file_path)
        print("Vault initialized.")

    def save_data(self, json_string: str):
        """
        Saves a JSON string to the encrypted vault.
        """
        if self.vault is None:
            raise ValueError("Vault is not initialized. Call init_vault() first.")
        
        try:
            self.vault.saveData(json_string)
            print("Data saved successfully.")
        except Exception as e:
            print(f"Java Error saving data: {e}")
            raise

    def load_data(self) -> str:
        """
        Loads and decrypts the JSON string from the vault.
        """
        if self.vault is None:
            raise ValueError("Vault is not initialized. Call init_vault() first.")
            
        try:
            print("Loading data from vault...")
            decrypted_data = self.vault.loadData()
            print("Data loaded and decrypted successfully.")
            return str(decrypted_data)
        except Exception as e:
            # Handle empty vault file as an empty JSON object string
            if "file not found or empty" in str(e).lower():
                 print("Vault file is empty or not found. Returning empty JSON object.")
                 return "{}"
                 
            print(f"Java Error loading data: {e}")
            print("This may be due to a wrong key or file tampering.")
            raise
    
    def update_account_password(self, account_name: str, new_raw_pass: str):
        """
        Updates the master password by replacing the keystore and re-encrypting 
        the vault data with a new key derived from the new password.
        
        This method is non-destructive (preserves data).
        """
        print("Starting master password update process (data preserving)...")
        
        # 1. Retrieve ALL data from the currently open vault (encrypted with OLD key)
        try:
            # This loads everything, including the account hash/salt
            old_vault_content_json = self.load_data()
            old_vault_content = json.loads(old_vault_content_json)
        except Exception as e:
            raise RuntimeError(f"Failed to load data from old vault before reset: {e}")

        # 2. Shutdown JVM to release file locks before deleting files
        self.shutdown() 
        time.sleep(0.1) # Small pause to ensure file system release

        # 3. Delete Old Keystore and Vault
        if os.path.exists(udef.KEYSTORE_FILE):
            os.remove(udef.KEYSTORE_FILE)
            print(f"Deleted old KeyStore: {udef.KEYSTORE_FILE}")
        
        if os.path.exists(udef.VAULT_FILE):
            os.remove(udef.VAULT_FILE)
            print(f"Deleted old Vault file: {udef.VAULT_FILE}")
            
        # 4. Restart JVM and Establish New Cryptographic Chain
        self.__init__() # Re-initialize the manager (starts JVM, loads pepper, etc.)
        
        # 5. Create new KeyStore/Key Entry/Vault with the NEW password
        self.load_keystore(udef.KEYSTORE_FILE, new_raw_pass)
        self.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, new_raw_pass)
        self.get_secret_key(udef.KEY_ALIAS, new_raw_pass)
        self.init_vault(udef.VAULT_FILE)

        # 6. Re-hash and update the account credentials (hash/salt) within the data
        new_salt = os.urandom(16).hex()
        password_combined = (new_raw_pass + new_salt + self.PEPPER).encode('utf-8')
        new_hashed_password = hashlib.sha256(password_combined).hexdigest()

        old_vault_content.update({
            "account_name": account_name,
            "hashed_password": new_hashed_password,
            "salt": new_salt
        })

        # 7. Encrypt and save the updated data (with new hash/salt) to the new vault
        new_json_string = json.dumps(old_vault_content)
        self.save_data(new_json_string) 
        
        print("Master password update complete. Data preserved and re-encrypted.")

    def shutdown(self):
        """Shuts down the JVM if it's running."""
        if jpype.isJVMStarted():
            print("Shutting down JVM...")
            jpype.shutdownJVM()
            print("JVM shut down.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
        
    def save_account_credentials(self, account_name: str, raw_password: str):
        """
        Hashes and salts the raw password with the loaded pepper, then saves the 
        account name, resulting hash, and salt to the encrypted vault.
        """
        # 1. Generate a secure, unique salt (16 bytes)
        salt = os.urandom(16).hex()
        
        # 2. Combine all security components for hashing
        password_combined = (raw_password + salt + self.PEPPER).encode('utf-8')
        
        # 3. Hash the combined string (SHA-256 is used for simplicity)
        hashed_password = hashlib.sha256(password_combined).hexdigest()

        data_to_save = {
            "account_name": account_name,
            "hashed_password": hashed_password,
            "salt": salt
        }
        
        json_string = json.dumps(data_to_save)
        
        print(f"Saving credentials for account: {account_name}")
        self.save_data(json_string) # Uses the existing saveData() method

    def load_account_credentials(self) -> dict:
        """
        Loads, decrypts, and parses the account name, hashed password, and salt
        from the vault.
        
        :return: A dictionary containing the loaded credentials.
        """
        decrypted_json_string = self.load_data() # Uses the existing loadData() method
        
        try:
            loaded_data = json.loads(decrypted_json_string)
            
            # Ensure the required keys are present
            required_keys = ["account_name", "hashed_password", "salt"]
            if not all(key in loaded_data for key in required_keys):
                 raise KeyError(f"Decrypted JSON is missing one of the required keys: {required_keys}")
                 
            return loaded_data
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing loaded data: {e}")
            raise ValueError("The vault file contains invalid or corrupted JSON data.")
