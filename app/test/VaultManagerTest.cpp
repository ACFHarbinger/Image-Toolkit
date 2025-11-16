#include "gtest/gtest.h"
#include "VaultManager.h"
#include "FileSystemUtil.h"
#include <filesystem>

namespace fs = std::filesystem;

// --- IMPORTANT ---
// This test requires:
// 1. A valid JDK installed for JNI.
// 2. OpenSSL libs.
// 3. The path to the compiled `cryptography-1.0.0-SNAPSHOT-uber.jar` file.
//    We assume it's in a relative path.
const std::string JAR_PATH = "../cryptography/target/cryptography-1.0.0-SNAPSHOT-uber.jar";

class VaultManagerTest : public ::testing::Test {
protected:
    fs::path testDir;
    fs::path pepperPath;
    fs::path keystorePath;
    fs::path vaultPath;
    std::unique_ptr<VaultManager> vault;

    void SetUp() override {
        testDir = fs::temp_directory_path() / "img_toolkit_tests" / ::testing::UnitTest::GetInstance()->current_test_info()->name();
        fs::create_directories(testDir);
        
        pepperPath = testDir / "test_pepper.txt";
        keystorePath = testDir / "test_keystore.p12";
        vaultPath = testDir / "test_vault.dat";
        
        // Check if JAR exists before trying to run
        if (!fs::exists(JAR_PATH)) {
            vault.reset();
            return; // Skip tests if JAR is missing
        }

        try {
            vault = std::make_unique<VaultManager>(JAR_PATH, pepperPath.string());
        } catch (const std::exception& e) {
            std::cerr << "Failed to init VaultManager: " << e.what() << std::endl;
            vault.reset();
        }
    }

    void TearDown() override {
        vault.reset(); // Shuts down JVM
        fs::remove_all(testDir.parent_path());
    }
};

TEST_F(VaultManagerTest, InitAndCreateKey) {
    if (!vault) { GTEST_SKIP() << "Skipping test, JAR file not found at " << JAR_PATH; }

    ASSERT_TRUE(vault->loadKeystore(keystorePath.string(), "testpass"));
    ASSERT_FALSE(vault->containsAlias("test-key"));
    ASSERT_TRUE(vault->createKeyIfMissing("test-key", keystorePath.string(), "testpass"));
    ASSERT_TRUE(vault->containsAlias("test-key"));
}

TEST_F(VaultManagerTest, SaveAndLoadData) {
    if (!vault) { GTEST_SKIP() << "Skipping test, JAR file not found at " << JAR_PATH; }
    
    std::string keyAlias = "my-key";
    std::string pass = "password123";
    std::string testJson = "{\"hello\":\"world\", \"value\":123}";

    ASSERT_TRUE(vault->loadKeystore(keystorePath.string(), pass));
    ASSERT_TRUE(vault->createKeyIfMissing(keyAlias, keystorePath.string(), pass));
    ASSERT_TRUE(vault->getSecretKey(keyAlias, pass));
    ASSERT_TRUE(vault->initVault(vaultPath.string()));

    ASSERT_TRUE(vault->saveData(testJson));
    
    std::string loadedData = vault->loadData();
    ASSERT_EQ(loadedData, testJson);
}

TEST_F(VaultManagerTest, LoadEmptyVault) {
    if (!vault) { GTEST_SKIP() << "Skipping test, JAR file not found at " << JAR_PATH; }
    
    std::string keyAlias = "my-key";
    std::string pass = "password123";

    ASSERT_TRUE(vault->loadKeystore(keystorePath.string(), pass));
    ASSERT_TRUE(vault->createKeyIfMissing(keyAlias, keystorePath.string(), pass));
    ASSERT_TRUE(vault->getSecretKey(keyAlias, pass));
    ASSERT_TRUE(vault->initVault(vaultPath.string())); // Vault file doesn't exist yet

    std::string loadedData = vault->loadData();
    ASSERT_EQ(loadedData, "{}"); // Should return empty JSON
}

TEST_F(VaultManagerTest, SaveAndLoadCredentials) {
    if (!vault) { GTEST_SKIP() << "Skipping test, JAR file not found at " << JAR_PATH; }

    std::string keyAlias = "my-key";
    std::string pass = "password123";
    
    ASSERT_TRUE(vault->loadKeystore(keystorePath.string(), pass));
    ASSERT_TRUE(vault->createKeyIfMissing(keyAlias, keystorePath.string(), pass));
    ASSERT_TRUE(vault->getSecretKey(keyAlias, pass));
    ASSERT_TRUE(vault->initVault(vaultPath.string()));

    ASSERT_TRUE(vault->saveAccountCredentials("test_user", "test_pass_123"));
    
    auto creds = vault->loadAccountCredentials();
    
    ASSERT_EQ(creds["account_name"], "test_user");
    ASSERT_FALSE(creds["hashed_password"].empty());
    ASSERT_FALSE(creds["salt"].empty());
}