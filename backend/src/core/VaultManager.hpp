#pragma once

#include <string>
#include <map>
#include <vector>
#include <jni.h>
#include <memory>

class VaultManager {
public:
    VaultManager();
    ~VaultManager();

    // KeyStore Management
    void loadKeystore(const std::string& keystore_path, const std::string& keystore_pass);
    bool containsAlias(const std::string& key_alias);
    void createKeyIfMissing(const std::string& key_alias, const std::string& keystore_path, const std::string& keystore_pass);
    void getSecretKey(const std::string& key_alias, const std::string& key_pass);
    
    // Vault Interaction
    void initVault(const std::string& vault_file_path);
    void saveData(const std::string& json_string);
    std::string loadData();
    
    // Account Credentials
    void saveAccountCredentials(const std::string& account_name, const std::string& raw_password);
    std::map<std::string, std::string> loadAccountCredentials();
    void updateAccountPassword(const std::string& account_name, const std::string& new_raw_pass);
    
    // Helpers
    static void shutdownJVM();

private:
    // JNI State
    static JavaVM* jvm;
    static JNIEnv* env;
    
    // Java Objects (Global Refs)
    jobject m_keystoreManagerObj = nullptr;
    jobject m_keyInitializerObj = nullptr;
    jobject m_vaultObj = nullptr;
    jobject m_keystoreObj = nullptr;    // java.security.KeyStore
    jobject m_secretKeyObj = nullptr;   // javax.crypto.SecretKey

    // Cached Classes
    jclass m_clsKeyStoreManager = nullptr;
    jclass m_clsKeyInitializer = nullptr;
    jclass m_clsSecureJsonVault = nullptr;

    // Internal Helpers
    void initializeJVM();
    jcharArray stringToCharArray(const std::string& str);
    std::string jstringToString(jstring jStr);
    void checkJniException();
    
    // Pepper Logic (Still handled in C++ side for file management)
    std::string m_pepper;
    std::string loadOrGeneratePepper();
    std::string hashPassword(const std::string& raw_pass, const std::string& salt);
};