import jpype
import jpype.imports
from jpype.types import JArray, JChar

def main():
    try:
        # --- 1. Setup JVM ---
        # You MUST provide the paths to your JAR and its dependencies (Bouncy Castle)
        # Download the Bouncy Castle JARs from their website or your .m2 folder.
        # e.g., bcprov-jdk18on-1.78.jar
        
        # Get these paths right!
        PATH_TO_YOUR_JAR = 'cryptography/target/cryptography-1.0-SNAPSHOT.jar'
        PATH_TO_BC_PROV_JAR = '/path/to/your/bcprov-jdk18on-1.78.jar' 
        PATH_TO_BC_PKIX_JAR = '/path/to/your/bcpkix-jdk18on-1.78.jar'

        jpype.startJVM(
            classpath=[
                PATH_TO_YOUR_JAR, 
                PATH_TO_BC_PROV_JAR, 
                PATH_TO_BC_PKIX_JAR
            ]
        )
        
        # --- 2. Import your Java classes ---
        from com.personal.image_toolkit import KeyStoreManager, SecureJsonVault
        from java.security import KeyStore
        import javax.crypto.SecretKey

        # --- 3. Use the Java classes almost identically ---
        
        KEYSTORE_FILE = "my_java_keystore.p12"
        KEYSTORE_PASSWORD = "changeit"
        KEY_PASSWORD = "my_key_password"
        
        # Convert Python strings to Java char[]
        ks_pass_char = JArray(JChar)(KEYSTORE_PASSWORD)
        key_pass_char = JArray(JChar)(KEY_PASSWORD)

        # 1. Load keystore
        keyStore = KeyStoreManager.loadKeyStore(KEYSTORE_FILE, ks_pass_char)

        # 2. Store secret key
        secretKeyAlias = "my-secret-key-from-python"
        if not keyStore.containsAlias(secretKeyAlias):
            print("Storing new key...")
            KeyStoreManager.storeSecretKey(keyStore, secretKeyAlias, key_pass_char)
            KeyStoreManager.saveKeyStore(keyStore, KEYSTORE_FILE, ks_pass_char)

        # 3. Get secret key
        retrievedKey = KeyStoreManager.getSecretKey(keyStore, secretKeyAlias, key_pass_char)
        
        if not retrievedKey:
            raise Exception("Could not get key from keystore!")
            
        print("Successfully retrieved key from keystore via Jpype!")

        # 4. Use SecureJsonVault
        vaultFilePath = "user_data_from_python.vault"
        vault = SecureJsonVault(retrievedKey, vaultFilePath)
        
        sampleJson = '{"message": "Hello from Python calling Java!"}'
        vault.saveData(sampleJson)
        
        loadedJson = vault.loadData()
        print("\nSuccessfully decrypted data from vault:")
        print(loadedJson)
        
        assert sampleJson == loadedJson
        print("\nJpype end-to-end test successful!")

    except Exception as e:
        print("\nAn error occurred:")
        print(e)
    finally:
        if jpype.isJVMStarted():
            jpype.shutdownJVM()

if __name__ == "__main__":
    main()