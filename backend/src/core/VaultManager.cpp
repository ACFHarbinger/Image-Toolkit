#include "VaultManager.hpp"
#include "FileSystemTool.hpp" // For directory creation
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <random>
#include <cstring>
#include <openssl/sha.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

// --- CONFIGURATION ---
// IMPORTANT: Update this path to where your compiled Kotlin JAR resides
const std::string JAR_PATH = "-Djava.class.path=cryptography-1.0.0-SNAPSHOT-uber.jar";
const std::string CRYPTO_DIR = "crypto_files";
const std::string PEPPER_FILE = CRYPTO_DIR + "/pepper.bin";
const std::string KEYSTORE_FILE = CRYPTO_DIR + "/key_store.vault";
const std::string VAULT_FILE = CRYPTO_DIR + "/secure_vault.dat";
const std::string KEY_ALIAS = "master_key";

// Static JVM members
JavaVM* VaultManager::jvm = nullptr;
JNIEnv* VaultManager::env = nullptr;

VaultManager::VaultManager() {
    m_pepper = loadOrGeneratePepper();
    initializeJVM();

    // 1. Initialize Classes and Objects
    if (!env) return;

    // Find Classes
    jclass clsKM = env->FindClass("com/personal/image_toolkit/KeyStoreManager");
    jclass clsKI = env->FindClass("com/personal/image_toolkit/KeyInitializer");
    jclass clsVault = env->FindClass("com/personal/image_toolkit/SecureJsonVault");

    if (!clsKM || !clsKI || !clsVault) {
        std::cerr << "Failed to find Kotlin classes. Check JAR path and classpath." << std::endl;
        checkJniException();
        return;
    }

    // Create Global References for Classes
    m_clsKeyStoreManager = (jclass)env->NewGlobalRef(clsKM);
    m_clsKeyInitializer = (jclass)env->NewGlobalRef(clsKI);
    m_clsSecureJsonVault = (jclass)env->NewGlobalRef(clsVault);

    // Instantiate KeyStoreManager
    jmethodID ctorKM = env->GetMethodID(m_clsKeyStoreManager, "<init>", "()V");
    jobject localKM = env->NewObject(m_clsKeyStoreManager, ctorKM);
    m_keystoreManagerObj = env->NewGlobalRef(localKM);

    // Instantiate KeyInitializer
    jmethodID ctorKI = env->GetMethodID(m_clsKeyInitializer, "<init>", "()V");
    jobject localKI = env->NewObject(m_clsKeyInitializer, ctorKI);
    m_keyInitializerObj = env->NewGlobalRef(localKI);
    
    checkJniException();
}

VaultManager::~VaultManager() {
    if (env) {
        if (m_keystoreManagerObj) env->DeleteGlobalRef(m_keystoreManagerObj);
        if (m_keyInitializerObj) env->DeleteGlobalRef(m_keyInitializerObj);
        if (m_vaultObj) env->DeleteGlobalRef(m_vaultObj);
        if (m_keystoreObj) env->DeleteGlobalRef(m_keystoreObj);
        if (m_secretKeyObj) env->DeleteGlobalRef(m_secretKeyObj);
        
        if (m_clsKeyStoreManager) env->DeleteGlobalRef(m_clsKeyStoreManager);
        if (m_clsKeyInitializer) env->DeleteGlobalRef(m_clsKeyInitializer);
        if (m_clsSecureJsonVault) env->DeleteGlobalRef(m_clsSecureJsonVault);
    }
}

void VaultManager::initializeJVM() {
    if (jvm != nullptr) {
        // Attach current thread if JVM exists
        jvm->AttachCurrentThread((void**)&env, nullptr);
        return;
    }

    JavaVMInitArgs vm_args;
    JavaVMOption options[1];
    
    // Set Classpath
    // In C++, we need to construct a char* for the option
    char* classpath_opt = new char[JAR_PATH.length() + 1];
    std::strcpy(classpath_opt, JAR_PATH.c_str());
    options[0].optionString = classpath_opt;

    vm_args.version = JNI_VERSION_1_8;
    vm_args.nOptions = 1;
    vm_args.options = options;
    vm_args.ignoreUnrecognized = JNI_FALSE;

    jint rc = JNI_CreateJavaVM(&jvm, (void**)&env, &vm_args);
    delete[] classpath_opt;

    if (rc != JNI_OK) {
        std::cerr << "Failed to create JVM: " << rc << std::endl;
        exit(1);
    }
}

void VaultManager::shutdownJVM() {
    if (jvm) {
        jvm->DestroyJavaVM();
        jvm = nullptr;
        env = nullptr;
    }
}

// --- Helpers ---

jcharArray VaultManager::stringToCharArray(const std::string& str) {
    // Determine length (UTF-16 chars)
    // Simple ASCII conversion for passwords/paths
    jcharArray charArr = env->NewCharArray(str.length());
    std::vector<jchar> buffer(str.length());
    for(size_t i=0; i<str.length(); ++i) buffer[i] = (jchar)str[i];
    
    env->SetCharArrayRegion(charArr, 0, str.length(), buffer.data());
    return charArr;
}

std::string VaultManager::jstringToString(jstring jStr) {
    if (!jStr) return "";
    const char* chars = env->GetStringUTFChars(jStr, nullptr);
    std::string ret(chars);
    env->ReleaseStringUTFChars(jStr, chars);
    return ret;
}

void VaultManager::checkJniException() {
    if (env->ExceptionCheck()) {
        env->ExceptionDescribe(); // Prints to stderr
        env->ExceptionClear();
        throw std::runtime_error("Java Exception Occurred");
    }
}

// --- Business Logic Wrappers ---

void VaultManager::loadKeystore(const std::string& keystore_path, const std::string& keystore_pass) {
    jmethodID mid = env->GetMethodID(m_clsKeyStoreManager, "loadKeyStore", "(Ljava/lang/String;[C)Ljava/security/KeyStore;");
    if (!mid) return;

    jstring jPath = env->NewStringUTF(keystore_path.c_str());
    jcharArray jPass = stringToCharArray(keystore_pass);

    jobject localKS = env->CallObjectMethod(m_keystoreManagerObj, mid, jPath, jPass);
    checkJniException();

    if (m_keystoreObj) env->DeleteGlobalRef(m_keystoreObj);
    m_keystoreObj = env->NewGlobalRef(localKS);
    
    std::cout << "Keystore loaded successfully via JNI." << std::endl;
}

bool VaultManager::containsAlias(const std::string& key_alias) {
    if (!m_keystoreObj) throw std::runtime_error("Keystore not loaded");

    // We can call KeyStore.containsAlias directly or use KeyStoreManager wrapper if it exposes it
    // Assuming wrapper relies on underlying KeyStore object, let's call KeyStore method directly for simplicity
    jclass clsKS = env->GetObjectClass(m_keystoreObj);
    jmethodID mid = env->GetMethodID(clsKS, "containsAlias", "(Ljava/lang/String;)Z");
    
    jstring jAlias = env->NewStringUTF(key_alias.c_str());
    jboolean result = env->CallBooleanMethod(m_keystoreObj, mid, jAlias);
    checkJniException();
    
    return (bool)result;
}

void VaultManager::createKeyIfMissing(const std::string& key_alias, const std::string& keystore_path, const std::string& keystore_pass) {
    jmethodID mid = env->GetMethodID(m_clsKeyInitializer, "initializeKeystore", "(Ljava/lang/String;Ljava/lang/String;[C[C)V");
    if (!mid) return;

    jstring jPath = env->NewStringUTF(keystore_path.c_str());
    jstring jAlias = env->NewStringUTF(key_alias.c_str());
    jcharArray jPass = stringToCharArray(keystore_pass);

    env->CallVoidMethod(m_keyInitializerObj, mid, jPath, jAlias, jPass, jPass);
    checkJniException();

    // Reload logic
    loadKeystore(keystore_path, keystore_pass);
}

void VaultManager::getSecretKey(const std::string& key_alias, const std::string& key_pass) {
    if (!m_keystoreObj) throw std::runtime_error("Keystore not loaded");

    jmethodID mid = env->GetMethodID(m_clsKeyStoreManager, "getSecretKey", "(Ljava/security/KeyStore;Ljava/lang/String;[C)Ljavax/crypto/SecretKey;");
    
    jstring jAlias = env->NewStringUTF(key_alias.c_str());
    jcharArray jPass = stringToCharArray(key_pass);

    jobject localKey = env->CallObjectMethod(m_keystoreManagerObj, mid, m_keystoreObj, jAlias, jPass);
    checkJniException();

    if (m_secretKeyObj) env->DeleteGlobalRef(m_secretKeyObj);
    m_secretKeyObj = env->NewGlobalRef(localKey);
    
    std::cout << "SecretKey retrieved via JNI." << std::endl;
}

void VaultManager::initVault(const std::string& vault_file_path) {
    if (!m_secretKeyObj) throw std::runtime_error("SecretKey not loaded");

    jmethodID ctor = env->GetMethodID(m_clsSecureJsonVault, "<init>", "(Ljavax/crypto/SecretKey;Ljava/lang/String;)V");
    jstring jPath = env->NewStringUTF(vault_file_path.c_str());

    jobject localVault = env->NewObject(m_clsSecureJsonVault, ctor, m_secretKeyObj, jPath);
    checkJniException();

    if (m_vaultObj) env->DeleteGlobalRef(m_vaultObj);
    m_vaultObj = env->NewGlobalRef(localVault);
    
    std::cout << "SecureJsonVault initialized via JNI." << std::endl;
}

void VaultManager::saveData(const std::string& json_string) {
    if (!m_vaultObj) throw std::runtime_error("Vault not initialized");

    jmethodID mid = env->GetMethodID(m_clsSecureJsonVault, "saveData", "(Ljava/lang/String;)V");
    jstring jData = env->NewStringUTF(json_string.c_str());

    env->CallVoidMethod(m_vaultObj, mid, jData);
    checkJniException();
}

std::string VaultManager::loadData() {
    if (!m_vaultObj) throw std::runtime_error("Vault not initialized");

    jmethodID mid = env->GetMethodID(m_clsSecureJsonVault, "loadData", "()Ljava/lang/String;");
    jstring jResult = (jstring)env->CallObjectMethod(m_vaultObj, mid);
    
    // Check if exception occurred (e.g., file not found)
    if (env->ExceptionCheck()) {
        env->ExceptionClear(); 
        return "{}"; // Default to empty json
    }

    return jstringToString(jResult);
}

// --- C++ Side Logic (Pepper, Hashing, JSON) ---
// Note: This remains largely pure C++ because it interacts with Python-style logic 
// not the Kotlin vault itself, except for the saveData call.

std::string VaultManager::loadOrGeneratePepper() {
    FSETool::createDirectory(CRYPTO_DIR);
    std::ifstream file(PEPPER_FILE);
    if (file.is_open()) {
        std::string pepper;
        std::getline(file, pepper);
        return pepper;
    } else {
        std::random_device rd;
        std::vector<unsigned char> random_bytes(32);
        for(unsigned char& b : random_bytes) b = static_cast<unsigned char>(rd());
        std::stringstream ss;
        for(unsigned char b : random_bytes) ss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
        std::string pepper = ss.str();
        std::ofstream outfile(PEPPER_FILE);
        outfile << pepper;
        return pepper;
    }
}

std::string VaultManager::hashPassword(const std::string& raw_pass, const std::string& salt) {
    std::string combined = raw_pass + salt + m_pepper;
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256_CTX sha256;
    SHA256_Init(&sha256);
    SHA256_Update(&sha256, combined.c_str(), combined.length());
    SHA256_Final(hash, &sha256);
    std::stringstream ss;
    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) ss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
    return ss.str();
}

void VaultManager::saveAccountCredentials(const std::string& account_name, const std::string& raw_password) {
    std::random_device rd;
    std::vector<unsigned char> random_bytes(16);
    for(unsigned char& b : random_bytes) b = static_cast<unsigned char>(rd());
    std::stringstream salt_ss;
    for(unsigned char b : random_bytes) salt_ss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
    std::string salt = salt_ss.str();

    std::string hashed_password = hashPassword(raw_password, salt);

    json data;
    data["account_name"] = account_name;
    data["hashed_password"] = hashed_password;
    data["salt"] = salt;

    saveData(data.dump());
}

std::map<std::string, std::string> VaultManager::loadAccountCredentials() {
    std::string json_str = loadData();
    if (json_str == "{}" || json_str.empty()) return {};
    
    try {
        json j = json::parse(json_str);
        std::map<std::string, std::string> res;
        res["account_name"] = j["account_name"];
        res["hashed_password"] = j["hashed_password"];
        res["salt"] = j["salt"];
        return res;
    } catch (...) {
        return {};
    }
}

void VaultManager::updateAccountPassword(const std::string& account_name, const std::string& new_raw_pass) {
    // 1. Load Data
    std::string old_json = loadData();
    json j_old = json::parse(old_json);

    // 2. Clear References (Important so file locks are released by JVM GC)
    env->DeleteGlobalRef(m_vaultObj); m_vaultObj = nullptr;
    env->DeleteGlobalRef(m_keystoreObj); m_keystoreObj = nullptr;
    env->DeleteGlobalRef(m_secretKeyObj); m_secretKeyObj = nullptr;
    
    // Force GC? (Optional, JNI doesn't guarantee immediate GC)
    
    // 3. Delete Files
    FileDeleter::deletePath(KEYSTORE_FILE);
    FileDeleter::deletePath(VAULT_FILE);

    // 4. Create New
    createKeyIfMissing(KEY_ALIAS, KEYSTORE_FILE, new_raw_pass);
    getSecretKey(KEY_ALIAS, new_raw_pass);
    initVault(VAULT_FILE);

    // 5. Update Data
    std::random_device rd;
    std::vector<unsigned char> random_bytes(16);
    for(unsigned char& b : random_bytes) b = static_cast<unsigned char>(rd());
    std::stringstream new_salt_ss;
    for(unsigned char b : random_bytes) new_salt_ss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
    std::string new_salt = new_salt_ss.str();

    j_old["hashed_password"] = hashPassword(new_raw_pass, new_salt);
    j_old["salt"] = new_salt;

    saveData(j_old.dump());
}