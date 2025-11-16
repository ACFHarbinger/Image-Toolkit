#include "VaultManager.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include "FileSystemUtil.h"

// --- JNI Helper Macros ---
#define FIND_CLASS(env, name) \
    env->FindClass(name); \
    checkJNIException("FindClass " #name); \
    if (!cls) return false;

#define GET_METHOD_ID(env, var, cls, name, sig) \
    var = env->GetMethodID(cls, name, sig); \
    checkJNIException("GetMethodID " #name); \
    if (!var) return false;

#define GET_STATIC_METHOD_ID(env, var, cls, name, sig) \
    var = env->GetStaticMethodID(cls, name, sig); \
    checkJNIException("GetStaticMethodID " #name); \
    if (!var) return false;


VaultManager::VaultManager(const std::string& jarPath, const std::string& pepperPath) {
    m_pepper = loadOrGeneratePepper(pepperPath);

    // 1. Initialize JVM
    JavaVMInitArgs vm_args;
    JavaVMOption options[1];
    std::string classpath = "-Djava.class.path=" + jarPath;
    options[0].optionString = (char*)classpath.c_str();
    
    vm_args.version = JNI_VERSION_1_8;
    vm_args.nOptions = 1;
    vm_args.options = options;
    vm_args.ignoreUnrecognized = JNI_FALSE;

    int res = JNI_CreateJavaVM(&m_jvm, (void**)&m_env, &vm_args);
    if (res != JNI_OK) {
        throw std::runtime_error("Failed to create Java VM");
    }

    // 2. Find Classes
    m_keyStoreManagerClass = (jclass)m_env->NewGlobalRef(m_env->FindClass("com/personal/image_toolkit/KeyStoreManager"));
    m_secureJsonVaultClass = (jclass)m_env->NewGlobalRef(m_env->FindClass("com/personal/image_toolkit/SecureJsonVault"));
    
    if (!m_keyStoreManagerClass || !m_secureJsonVaultClass) {
        throw std::runtime_error("Failed to find Java classes.");
    }
    
    // 3. Create KeyStoreManager instance
    jmethodID ksmCtor = m_env->GetMethodID(m_keyStoreManagerClass, "<init>", "()V");
    jobject localKsmObj = m_env->NewObject(m_keyStoreManagerClass, ksmCtor);
    m_keyStoreManagerObj = m_env->NewGlobalRef(localKsmObj);
    m_env->DeleteLocalRef(localKsmObj);

    std::cout << "VaultManager initialized, JVM started." << std::endl;
}

VaultManager::~VaultManager() {
    // Release JNI global references
    if (m_env) {
        if (m_vaultObj) m_env->DeleteGlobalRef(m_vaultObj);
        if (m_secretKeyObj) m_env->DeleteGlobalRef(m_secretKeyObj);
        if (m_keystoreObj) m_env->DeleteGlobalRef(m_keystoreObj);
        if (m_keyStoreManagerObj) m_env->DeleteGlobalRef(m_keyStoreManagerObj);
        if (m_secureJsonVaultClass) m_env->DeleteGlobalRef(m_secureJsonVaultClass);
        if (m_keyStoreManagerClass) m_env->DeleteGlobalRef(m_keyStoreManagerClass);
    }
    if (m_jvm) {
        m_jvm->DestroyJavaVM();
        std::cout << "JVM shut down." << std::endl;
    }
}

// --- Public Methods ---

bool VaultManager::loadKeystore(const std::string& keystorePath, const std::string& keystorePass) {
    jmethodID loadMethod = m_env->GetMethodID(m_keyStoreManagerClass, "loadKeyStore", "(Ljava/lang/String;[C)Ljava/security/KeyStore;");
    if (!loadMethod) return false;

    jstring jPath = stringToJString(keystorePath);
    jcharArray jPass = stringToJCharArray(keystorePass);
    
    jobject localKeystore = m_env->CallObjectMethod(m_keyStoreManagerObj, loadMethod, jPath, jPass);
    checkJNIException("loadKeyStore");
    
    m_env->DeleteLocalRef(jPath);
    m_env->DeleteLocalRef(jPass);

    if (localKeystore) {
        m_keystoreObj = m_env->NewGlobalRef(localKeystore);
        m_env->DeleteLocalRef(localKeystore);
        std::cout << "Keystore loaded successfully." << std::endl;
        return true;
    }
    return false;
}

bool VaultManager::containsAlias(const std::string& keyAlias) {
    if (!m_keystoreObj) return false;
    
    jclass keystoreClass = m_env->GetObjectClass(m_keystoreObj);
    jmethodID containsMethod = m_env->GetMethodID(keystoreClass, "containsAlias", "(Ljava/lang/String;)Z");
    if (!containsMethod) return false;

    jstring jAlias = stringToJString(keyAlias);
    jboolean result = m_env->CallBooleanMethod(m_keystoreObj, containsMethod, jAlias);
    m_env->DeleteLocalRef(jAlias);
    
    return (bool)result;
}

bool VaultManager::createKeyIfMissing(const std::string& keyAlias, const std::string& keystorePath, const std::string& keystorePass) {
    if (containsAlias(keyAlias)) {
        std::cout << "Key entry '" << keyAlias << "' already exists. Skipping creation." << std::endl;
        return true;
    }
    
    std::cout << "Key entry '" << keyAlias << "' not found. Generating..." << std::endl;

    jmethodID storeMethod = m_env->GetMethodID(m_keyStoreManagerClass, "storeSecretKey", "(Ljava/security/KeyStore;Ljava/lang/String;[C)V");
    jmethodID saveMethod = m_env->GetMethodID(m_keyStoreManagerClass, "saveKeyStore", "(Ljava/security/KeyStore;Ljava/lang/String;[C)V");
    if (!storeMethod || !saveMethod) return false;
    
    jstring jAlias = stringToJString(keyAlias);
    jstring jPath = stringToJString(keystorePath);
    jcharArray jPass = stringToJCharArray(keystorePass);

    m_env->CallVoidMethod(m_keyStoreManagerObj, storeMethod, m_keystoreObj, jAlias, jPass);
    checkJNIException("storeSecretKey");
    
    m_env->CallVoidMethod(m_keyStoreManagerObj, saveMethod, m_keystoreObj, jPath, jPass);
    checkJNIException("saveKeyStore");
    
    m_env->DeleteLocalRef(jAlias);
    m_env->DeleteLocalRef(jPath);
    m_env->DeleteLocalRef(jPass);
    
    std::cout << "Secret key created and KeyStore saved." << std::endl;
    return true;
}

bool VaultManager::getSecretKey(const std::string& keyAlias, const std::string& keyPass) {
    jmethodID getMethod = m_env->GetMethodID(m_keyStoreManagerClass, "getSecretKey", "(Ljava/security/KeyStore;Ljava/lang/String;[C)Ljavax/crypto/SecretKey;");
    if (!getMethod) return false;

    jstring jAlias = stringToJString(keyAlias);
    jcharArray jPass = stringToJCharArray(keyPass);
    
    jobject localKey = m_env->CallObjectMethod(m_keyStoreManagerObj, getMethod, m_keystoreObj, jAlias, jPass);
    checkJNIException("getSecretKey");

    m_env->DeleteLocalRef(jAlias);
    m_env->DeleteLocalRef(jPass);

    if (localKey) {
        m_secretKeyObj = m_env->NewGlobalRef(localKey);
        m_env->DeleteLocalRef(localKey);
        std::cout << "SecretKey retrieved." << std::endl;
        return true;
    }
    return false;
}

bool VaultManager::initVault(const std::string& vaultFilePath) {
    if (!m_secretKeyObj) return false;

    jmethodID vaultCtor = m_env->GetMethodID(m_secureJsonVaultClass, "<init>", "(Ljavax/crypto/SecretKey;Ljava/lang/String;)V");
    if (!vaultCtor) return false;
    
    jstring jPath = stringToJString(vaultFilePath);
    jobject localVault = m_env->NewObject(m_secureJsonVaultClass, vaultCtor, m_secretKeyObj, jPath);
    checkJNIException("initVault");
    m_env->DeleteLocalRef(jPath);
    
    if (localVault) {
        m_vaultObj = m_env->NewGlobalRef(localVault);
        m_env->DeleteLocalRef(localVault);
        std::cout << "Vault initialized." << std::endl;
        return true;
    }
    return false;
}

bool VaultManager::saveData(const std::string& jsonString) {
    if (!m_vaultObj) return false;
    
    jmethodID saveMethod = m_env->GetMethodID(m_secureJsonVaultClass, "saveData", "(Ljava/lang/String;)V");
    if (!saveMethod) return false;
    
    jstring jJson = stringToJString(jsonString);
    m_env->CallVoidMethod(m_vaultObj, saveMethod, jJson);
    checkJNIException("saveData");
    m_env->DeleteLocalRef(jJson);
    
    std::cout << "Data saved successfully." << std::endl;
    return true;
}

std::string VaultManager::loadData() {
    if (!m_vaultObj) return "{}";
    
    jmethodID loadMethod = m_env->GetMethodID(m_secureJsonVaultClass, "loadData", "()Ljava/lang/String;");
    if (!loadMethod) return "{}";

    jstring jData = (jstring)m_env->CallObjectMethod(m_vaultObj, loadMethod);
    
    // Check for Java exceptions (e.g., file not found)
    if (m_env->ExceptionCheck()) {
        jthrowable exc = m_env->ExceptionOccurred();
        m_env->ExceptionClear();
        // m_env->CallVoidMethod(exc, m_env->GetMethodID(m_env->GetObjectClass(exc), "printStackTrace", "()V"));
        std::cerr << "Java exception in loadData. Returning empty JSON." << std::endl;
        return "{}";
    }

    if (jData) {
        std::string sData = jstringToString(jData);
        m_env->DeleteLocalRef(jData);
        std::cout << "Data loaded and decrypted." << std::endl;
        return sData;
    }
    
    return "{}";
}

bool VaultManager::saveAccountCredentials(const std::string& accountName, const std::string& rawPassword) {
    std::string salt = generateSalt();
    std::string hash = hashPassword(rawPassword, salt);
    
    // Using a basic JSON library or manual string building.
    // For real C++, use nlohmann/json or similar.
    std::string json = "{\"account_name\":\"" + accountName + "\", "
                       "\"hashed_password\":\"" + hash + "\", "
                       "\"salt\":\"" + salt + "\"}";
                       
    return saveData(json);
}

std::map<std::string, std::string> VaultManager::loadAccountCredentials() {
    std::string json = loadData();
    std::map<std::string, std::string> creds;
    
    // Rudimentary JSON parsing. Use a library in production.
    try {
        size_t namePos = json.find("\"account_name\":\"") + 16;
        size_t nameEnd = json.find("\"", namePos);
        creds["account_name"] = json.substr(namePos, nameEnd - namePos);

        size_t hashPos = json.find("\"hashed_password\":\"") + 19;
        size_t hashEnd = json.find("\"", hashPos);
        creds["hashed_password"] = json.substr(hashPos, hashEnd - hashPos);

        size_t saltPos = json.find("\"salt\":\"") + 8;
        size_t saltEnd = json.find("\"", saltPos);
        creds["salt"] = json.substr(saltPos, saltEnd - saltPos);
    } catch (...) {
        std::cerr << "Failed to parse credentials JSON." << std::endl;
    }
    return creds;
}

// --- Private & Helper Methods ---

std::string VaultManager::loadOrGeneratePepper(const std::string& pepperPath) {
    FileSystemUtil::createDirectory(pepperPath, true);
    
    std::ifstream ifs(pepperPath);
    if (ifs.is_open()) {
        std::string pepper;
        std::getline(ifs, pepper);
        if (!pepper.empty()) {
            std::cout << "Loading existing pepper." << std::endl;
            return pepper;
        }
    }

    std::cout << "Generating new pepper." << std::endl;
    unsigned char buffer[32];
    if (RAND_bytes(buffer, sizeof(buffer)) != 1) {
        throw std::runtime_error("Failed to generate random bytes for pepper.");
    }

    std::stringstream ss;
    for (int i = 0; i < sizeof(buffer); ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)buffer[i];
    }
    std::string pepper = ss.str();
    
    std::ofstream ofs(pepperPath);
    ofs << pepper;
    
    // std::filesystem::permissions(pepperPath, fs::perms::owner_read);
    
    return pepper;
}

std::string VaultManager::hashPassword(const std::string& rawPassword, const std::string& salt) {
    std::string combined = rawPassword + salt + m_pepper;
    unsigned char hash[SHA256_DIGEST_LENGTH];
    
    SHA256_CTX sha256;
    SHA256_Init(&sha256);
    SHA256_Update(&sha256, combined.c_str(), combined.length());
    SHA256_Final(hash, &sha256);
    
    std::stringstream ss;
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
    }
    return ss.str();
}

std::string VaultManager::generateSalt() {
    unsigned char buffer[16];
    if (RAND_bytes(buffer, sizeof(buffer)) != 1) {
        throw std::runtime_error("Failed to generate random bytes for salt.");
    }
    std::stringstream ss;
    for (int i = 0; i < sizeof(buffer); ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << (int)buffer[i];
    }
    return ss.str();
}

jstring VaultManager::stringToJString(const std::string& str) {
    return m_env->NewStringUTF(str.c_str());
}

std::string VaultManager::jstringToString(jstring jstr) {
    if (!jstr) return "";
    const char* chars = m_env->GetStringUTFChars(jstr, nullptr);
    std::string str = chars;
    m_env->ReleaseStringUTFChars(jstr, chars);
    return str;
}

jcharArray VaultManager::stringToJCharArray(const std::string& str) {
    jcharArray jca = m_env->NewCharArray(str.length());
    std::vector<jchar> chars;
    for (char c : str) {
        chars.push_back((jchar)c);
    }
    m_env->SetCharArrayRegion(jca, 0, str.length(), chars.data());
    return jca;
}

void VaultManager::checkJNIException(const std::string& context) {
    if (m_env->ExceptionCheck()) {
        std::cerr << "JNI EXCEPTION during: " << context << std::endl;
        m_env->ExceptionDescribe();
        m_env->ExceptionClear();
        throw std::runtime_error("JNI Exception occurred.");
    }
}