#ifndef VAULT_MANAGER_H
#define VAULT_MANAGER_H

#include <string>
#include <vector>
#include <map>
#include <jni.h> // Requires JNI headers (from JDK)
#include <openssl/sha.h> // Requires OpenSSL dependency
#include <openssl/rand.h>

// Corresponds to JavaVaultManager
class VaultManager {
public:
    VaultManager(const std::string& jarPath, const std::string& pepperPath);
    ~VaultManager();

    /**
     * @brief Loads the Java KeyStore.
     */
    bool loadKeystore(const std::string& keystorePath, const std::string& keystorePass);

    /**
     * @brief Checks if a key alias exists.
     */
    bool containsAlias(const std::string& keyAlias);

    /**
     * @brief Creates a new key if it's missing.
     */
    bool createKeyIfMissing(const std::string& keyAlias, const std::string& keystorePath, const std::string& keystorePass);

    /**
     * @brief Retrieves the SecretKey object from the keystore.
     */
    bool getSecretKey(const std::string& keyAlias, const std::string& keyPass);

    /**
     * @brief Initializes the SecureJsonVault Java object.
     */
    bool initVault(const std::string& vaultFilePath);

    /**
     * @brief Saves an encrypted JSON string.
     */
    bool saveData(const std::string& jsonString);

    /**
     * @brief Loads and decrypts the JSON string.
     */
    std::string loadData();

    /**
     * @brief Saves hashed account credentials.
     */
    bool saveAccountCredentials(const std::string& accountName, const std::string& rawPassword);

    /**
     * @brief Loads hashed account credentials.
     */
    std::map<std::string, std::string> loadAccountCredentials();


private:
    std::string loadOrGeneratePepper(const std::string& pepperPath);
    std::string hashPassword(const std::string& rawPassword, const std::string& salt);
    std::string generateSalt();
    
    // --- JNI Helper Methods ---
    jstring stringToJString(const std::string& str);
    std::string jstringToString(jstring jstr);
    jcharArray stringToJCharArray(const std::string& str);
    void checkJNIException(const std::string& context);

    // --- JNI State ---
    JavaVM* m_jvm = nullptr;
    JNIEnv* m_env = nullptr;
    
    jclass m_keyStoreManagerClass = nullptr;
    jclass m_secureJsonVaultClass = nullptr;
    
    jobject m_keyStoreManagerObj = nullptr;
    jobject m_keystoreObj = nullptr;
    jobject m_secretKeyObj = nullptr;
    jobject m_vaultObj = nullptr;
    
    // --- Crypto State ---
    std::string m_pepper;
};

#endif // VAULT_MANAGER_H