#include "BaseTestFixture.h"

// Create a test suite fixture
class FileSystemTest : public BaseTestFixture {};

TEST_F(FileSystemTest, PathContainsTrue) {
    ASSERT_TRUE(FileSystemEntries::pathContains(tempDir, subdirPath));
    ASSERT_TRUE(FileSystemEntries::pathContains(tempDir, fileC_txt));
}

TEST_F(FileSystemTest, PathContainsEqual) {
    ASSERT_TRUE(FileSystemEntries::pathContains(tempDir, tempDir));
}

TEST_F(FileSystemTest, PathContainsFalse) {
    // Create a path outside the temp directory
    fs::path otherDir = fs::temp_directory_path() / "OtherDir_XXXXXX";
    fs::create_directory(otherDir);
    ASSERT_FALSE(FileSystemEntries::pathContains(tempDir, otherDir));
    fs::remove(otherDir);
}

TEST_F(FileSystemTest, GetFilesByExtensionNoRecursive) {
    auto files = FileSystemEntries::getFilesByExtension(tempDir, "txt", false);
    ASSERT_EQ(files.size(), 1);
    ASSERT_EQ(files[0].filename().string(), "file_a.txt");
}

TEST_F(FileSystemTest, GetFilesByExtensionRecursive) {
    auto files = FileSystemEntries::getFilesByExtension(tempDir, ".txt", true);
    ASSERT_EQ(files.size(), 2);
    // Convert to set for easy comparison, as order is not guaranteed
    std::set<std::string> filenames;
    for(const auto& f : files) {
        filenames.insert(f.filename().string());
    }
    ASSERT_TRUE(filenames.count("file_a.txt"));
    ASSERT_TRUE(filenames.count("file_c.txt"));
}

TEST_F(FileSystemTest, DeleteFilesByExtensions) {
    int deletedCount = FileSystemEntries::deleteFilesByExtensions(tempDir, {"txt", ".log"});
    ASSERT_EQ(deletedCount, 3);
    
    // Check that they are gone
    ASSERT_FALSE(fs::exists(fileA_txt));
    ASSERT_FALSE(fs::exists(fileB_log));
    ASSERT_FALSE(fs::exists(fileC_txt));
    
    // Check that others remain
    ASSERT_TRUE(fs::exists(imgRed_png));
}

TEST_F(FileSystemTest, DeletePathFile) {
    ASSERT_TRUE(fs::exists(imgRed_png));
    bool result = FileSystemEntries::deletePath(imgRed_png);
    ASSERT_TRUE(result);
    ASSERT_FALSE(fs::exists(imgRed_png));
}

TEST_F(FileSystemTest, DeletePathDirectory) {
    ASSERT_TRUE(fs::exists(subdirPath));
    bool result = FileSystemEntries::deletePath(subdirPath);
    ASSERT_TRUE(result);
    ASSERT_FALSE(fs::exists(subdirPath));
    ASSERT_FALSE(fs::exists(fileC_txt)); // Check recursive delete
}

TEST_F(FileSystemTest, DeletePathNonExistent) {
    bool result = FileSystemEntries::deletePath("/this/path/never/existed");
    ASSERT_FALSE(result);
}