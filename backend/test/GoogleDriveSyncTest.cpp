#include "gtest/gtest.h"
#include "../src/web/GoogleDriveSync.h"
#include "../src/core/FileSystemUtil.h"
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

class GoogleDriveSyncTest : public ::testing::Test {
protected:
    fs::path testDir;
    fs::path localDir;

    void SetUp() override {
        testDir = fs::temp_directory_path() / "img_toolkit_tests" / ::testing::UnitTest::GetInstance()->current_test_info()->name();
        localDir = testDir / "local_sync_folder";
        fs::create_directories(localDir);
    }

    void TearDown() override {
        fs::remove_all(testDir.parent_path());
    }
};

TEST_F(GoogleDriveSyncTest, ExecuteSync) {
    // --- THIS TEST IS INTENTIONALLY DISABLED ---
    //
    // Running this test requires a valid, hardcoded OAuth 2.0 Access Token
    // for a real Google Drive account. This is a security risk and
    // cannot be provided here.
    //
    // To run this manually:
    // 1. Go to Google's OAuth 2.0 Playground.
    // 2. Authorize the scope: 'https://www.googleapis.com/auth/drive'
    // 3. Exchange the authorization code for tokens.
    // 4. Copy the "access_token".
    // 5. Paste the token below.
    
    std::string OAUTH_TOKEN = "PASTE_YOUR_ACCESS_TOKEN_HERE";
    
    if (OAUTH_TOKEN == "PASTE_YOUR_ACCESS_TOKEN_HERE") {
        FAIL() << "Test skipped: Requires a valid OAuth 2.0 access token.";
    }

    // 1. Create a local file
    std::ofstream(localDir / "test_upload.txt") << "hello drive";
    
    // 2. Setup logger
    std::vector<std::string> logs;
    auto logger = [&logs](const std::string& msg) {
        logs.push_back(msg);
        std::cout << "[SyncLog] " << msg << std::endl;
    };

    // 3. Init and run sync
    GoogleDriveSync sync(OAUTH_TOKEN, localDir, "CPP_TEST_FOLDER", true, logger);
    auto result = sync.executeSync();

    // 4. Check results
    ASSERT_TRUE(result.first) << "Sync failed: " << result.second;
    
    bool found_upload_log = false;
    for (const auto& log : logs) {
        if (log.find("[DRY RUN] UPLOAD: test_upload.txt") != std::string::npos) {
            found_upload_log = true;
            break;
        }
    }
    ASSERT_TRUE(found_upload_log) << "Did not find expected [DRY RUN] log message.";
}