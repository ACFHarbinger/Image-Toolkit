import jpype
import atexit
import getpass
try:
    import app.src.utils.definitions as udef
except:
    import src.utils.definitions as udef

from jpype.types import JArray, JChar


class JavaVaultManager:
    """
    A Python wrapper to manage the SecureJsonVault by calling
    the compiled Java code via Jpype.

    This class is best used as a context manager:
    with JavaVaultManager("path/to/my.jar") as manager:
        manager.load_keystore(...)
        manager.get_secret_key(...)
    """
    def __init__(self, bc_provider_path: str = None):
        """
        Initializes the wrapper and starts the JVM.

        :param jar_path: Path to your compiled 'cryptography-1.0.0-SNAPSHOT.jar'.
        :param bc_provider_path: (Optional) Path to the Bouncy Castle JAR 
                                 if it's not included in an uber-jar.
        """
        if not jpype.isJVMStarted():
            classpath = [udef.JAR_FILE]
            if bc_provider_path:
                # Add Bouncy Castle JARs if they are separate
                classpath.append(f"{bc_provider_path}/*") 
                
            print(f"Starting JVM with classpath: {classpath}")
            jpype.startJVM(classpath=classpath)
            # Ensure JVM shuts down when Python exits
            atexit.register(self.shutdown)
        
        # Import the Java classes from your package
        try:
            KeyStoreManagerClass = jpype.JClass("com.personal.image_toolkit.KeyStoreManager")
            self.SecureJsonVault = jpype.JClass("com.personal.image_toolkit.SecureJsonVault")
            
            # 💡 FIX 1: Create an instance of the KeyStoreManager class
            self.keystore_manager = KeyStoreManagerClass()
            
        except jpype.JException as e:
            print("\n--- ERROR ---")
            print(f"Could not find Java class: {e}")
            print("Did you build the 'uber-jar' with dependencies?")
            print("Please see the 'maven-shade-plugin' example.")
            print("-------------\n")
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
        Calls KeyStoreManager.loadKeyStore()
        """
        try:
            print(f"Loading keystore: {keystore_path}")
            # 💡 FIX 2: Call the method on the instance, not the class
            self.keystore = self.keystore_manager.loadKeyStore(
                keystore_path,
                self._to_char_array(keystore_pass)
            )
            print("Keystore loaded successfully.")
        except Exception as e:
            print(f"Java Error loading keystore: {e}")
            raise

    def get_secret_key(self, key_alias: str, key_pass: str):
        """
        Retrieves the AES SecretKey from the loaded KeyStore.
        Calls KeyStoreManager.getSecretKey()
        """
        if self.keystore is None:
            raise ValueError("Keystore is not loaded. Call load_keystore() first.")
        
        try:
            print(f"Retrieving secret key for alias: {key_alias}")
            # 💡 FIX 3: Call the method on the instance, not the class
            self.secret_key = self.keystore_manager.getSecretKey(
                self.keystore,
                key_alias,
                self._to_char_array(key_pass)
            )
            if self.secret_key is None:
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
        Calls SecureJsonVault.saveData()
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
        Calls SecureJsonVault.loadData()
        
        :return: The decrypted JSON as a Python string.
        """
        if self.vault is None:
            raise ValueError("Vault is not initialized. Call init_vault() first.")
            
        try:
            print("Loading data from vault...")
            # loadData() returns a Java String, which Jpype
            # automatically converts to a Python string.
            decrypted_data = self.vault.loadData()
            print("Data loaded and decrypted successfully.")
            return str(decrypted_data)
        except Exception as e:
            print(f"Java Error loading data: {e}")
            print("This may be due to a wrong key or file tampering.")
            raise

    def shutdown(self):
        """Shuts down the JVM if it's running."""
        if jpype.isJVMStarted():
            print("Shutting down JVM...")
            jpype.shutdownJVM()
            print("JVM shut down.")

    def __enter__(self):
        """Allows use as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Shuts down the JVM when exiting the 'with' block."""
        self.shutdown()
        return False


def run_vault_operations():
    try:
        # Get passwords securely from user
        keystore_pass = getpass.getpass(f"Enter password for keystore '{udef.KEYSTORE_FILE}': ")
        key_entry_pass = getpass.getpass(f"Enter password for key alias '{udef.KEY_ALIAS}': ")

        # Use the context manager to handle JVM start/stop
        with JavaVaultManager(udef.JAR_FILE) as manager:
            
            # 1. Load the .p12 keystore
            manager.load_keystore(udef.KEYSTORE_FILE, keystore_pass)
            
            # 2. Get the specific AES key
            manager.get_secret_key(udef.KEY_ALIAS, key_entry_pass)
            
            # 3. Initialize the vault with that key
            manager.init_vault(udef.VAULT_FILE)

            # 4. Save data to the vault
            json_to_save = '{"api_key": "abc-123", "secret_message": "This was encrypted by Java!"}'
            print(f"\nSaving data to vault: {json_to_save}")
            manager.save_data(json_to_save)

            # 5. Load data back from the vault
            print("\nLoading data from vault...")
            loaded_data = manager.load_data()
            print(f"Success! Decrypted data: {loaded_data}")
            
            assert json_to_save == loaded_data
            print("\nVerification successful: Data matches.")

    except Exception as e:
        print(f"\n--- PYTHON ERROR ---")
        print(f"An operation failed: {e}")
        print("Please check your JAR path, file paths, and passwords.")
