#include "gtest/gtest.h"
#include "FileSystemUtil.h"
#include <fstream>
#include <filesystem>

namespace fs = std::filesystem;

class FileSystemTest : public ::testing::Test {
protected:
    fs::path testDir;

    void SetUp() override {
        // Create a unique temporary directory for each test
        testDir = fs::temp_directory_path() / "img_toolkit_tests" / ::testing::UnitTest::GetInstance()->current_test_info()->name();
        fs::create_directories(testDir);
    }

    void TearDown() override {
        // Clean up the temporary directory
        fs::remove_all(testDir.parent_path());
    }

    void createFile(const fs::path& path) {
        std::ofstream f(path);
        f << "test data";
        f.close();
    }
};

TEST_F(FileSystemTest, CreateDirectory) {
    fs::path newDir = testDir / "new_subdir";
    ASSERT_FALSE(fs::exists(newDir));
    ASSERT_TRUE(FileSystemUtil::createDirectory(newDir));
    ASSERT_TRUE(fs::exists(newDir));
}

TEST_F(FileSystemTest, CreateDirectoryForFile) {
    fs::path newFile = testDir / "another_dir" / "file.txt";
    ASSERT_FALSE(fs::exists(newFile.parent_path()));
    ASSERT_TRUE(FileSystemUtil::createDirectory(newFile, true));
    ASSERT_TRUE(fs::exists(newFile.parent_path()));
}

TEST_F(FileSystemTest, PathContains) {
    fs::path childFile = testDir / "child.txt";
    createFile(childFile);
    ASSERT_TRUE(FileSystemUtil::pathContains(testDir, childFile));
    ASSERT_FALSE(FileSystemUtil::pathContains(childFile, testDir));
}

TEST_F(FileSystemTest, GetFilesByExtension) {
    createFile(testDir / "a.txt");
    createFile(testDir / "b.log");
    createFile(testDir / "c.txt");
    
    auto files = FileSystemUtil::getFilesByExtension(testDir, ".txt", false);
    ASSERT_EQ(files.size(), 2);

    files = FileSystemUtil::getFilesByExtension(testDir, "log", false); // Test without dot
    ASSERT_EQ(files.size(), 1);
}

TEST_F(FileSystemTest, GetFilesByExtensionRecursive) {
    fs::create_directory(testDir / "sub");
    createFile(testDir / "a.txt");
    createFile(testDir / "sub" / "b.txt");

    auto files_non_rec = FileSystemUtil::getFilesByExtension(testDir, ".txt", false);
    ASSERT_EQ(files_non_rec.size(), 1);

    auto files_rec = FileSystemUtil::getFilesByExtension(testDir, ".txt", true);
    ASSERT_EQ(files_rec.size(), 2);
}

TEST_F(FileSystemTest, DeletePath) {
    fs::path file = testDir / "file_to_delete.txt";
    fs::path dir = testDir / "dir_to_delete";
    createFile(file);
    fs::create_directory(dir);

    ASSERT_TRUE(fs::exists(file));
    ASSERT_TRUE(fs::exists(dir));

    ASSERT_TRUE(FileSystemUtil::deletePath(file));
    ASSERT_TRUE(FileSystemUtil::deletePath(dir));

    ASSERT_FALSE(fs::exists(file));
    ASSERT_FALSE(fs::exists(dir));
}

TEST_F(FileSystemTest, DeleteFilesByExtensions) {
    fs::create_directory(testDir / "sub");
    createFile(testDir / "a.txt");
    createFile(testDir / "b.log");
    createFile(testDir / "sub" / "c.txt");

    int deleted = FileSystemUtil::deleteFilesByExtensions(testDir, {".txt"});
    ASSERT_EQ(deleted, 2);
    ASSERT_FALSE(fs::exists(testDir / "a.txt"));
    ASSERT_FALSE(fs::exists(testDir / "sub" / "c.txt"));
    ASSERT_TRUE(fs::exists(testDir / "b.log")); // Should still exist
}