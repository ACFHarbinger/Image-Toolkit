#ifndef FILESYSTEM_UTIL_H
#define FILESYSTEM_UTIL_H

#include <string>
#include <vector>
#include <filesystem> // Requires C++17 or later

// Corresponds to FSETool and FileDeleter
class FileSystemUtil {
public:
    /**
     * @brief Checks if a parent path contains a child path.
     */
    static bool pathContains(const std::filesystem::path& parentPath, const std::filesystem::path& childPath);

    /**
     * @brief Creates a directory if it doesn't exist.
     * @param path The path to the directory.
     * @param isFilePath If true, treats 'path' as a file path and creates its parent directory.
     */
    static bool createDirectory(const std::filesystem::path& path, bool isFilePath = false);

    /**
     * @brief Resolves a path to its absolute, canonical form.
     */
    static std::filesystem::path resolvePath(const std::filesystem::path& path);

    /**
     * @brief Gets all files with a specific extension in a directory.
     * @param directory The directory to search.
     * @param extension The file extension (e.g., ".jpg" or "jpg").
     * @param recursive Whether to search subdirectories.
     * @return A vector of absolute file paths.
     */
    static std::vector<std::string> getFilesByExtension(const std::filesystem::path& directory, const std::string& extension, bool recursive = false);

    /**
     * @brief Deletes a file or a directory (recursively).
     * @param pathToDelete The path to delete.
     * @return true on success, false on failure.
     */
    static bool deletePath(const std::filesystem::path& pathToDelete);

    /**
     * @brief Recursively deletes files matching extensions in a directory.
     * @param directory The directory to search.
     * @param extensions A vector of extensions (e.g., {".jpg", ".png"}).
     * @return The number of files deleted.
     */
    static int deleteFilesByExtensions(const std::filesystem::path& directory, const std::vector<std::string>& extensions);
};

#endif // FILESYSTEM_UTIL_H