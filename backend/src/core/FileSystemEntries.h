#pragma once
#include "Common.h"

namespace ImageToolkit
{
    /**
     * @brief A tool for managing file system entries, including path
     * resolution, directory creation, file searching, and deletion.
     * C++ equivalent of the Python FSETool class.
     */
    class FileSystemEntries
    {
    public:
        // --- Utility Methods (Decorator Replacements) ---

        /**
         * @brief Ensures the parent directory of a given file path exists.
         * @param filePath The full path to a file.
         */
        static void ensureDirectoryExists(const fs::path& filePath);

        /**
         * @brief Converts a relative path to an absolute path.
         * @param path The path to resolve.
         * @return The absolute path.
         */
        static fs::path makeAbsolute(const fs::path& path);

        // --- Core File System Methods ---

        /**
         * @brief Checks if parent_path contains child_path.
         */
        static bool pathContains(const fs::path& parentPath, const fs::path& childPath);

        /**
         * @brief Recursively delete files with extension(s) in a directory.
         */
        static int deleteFilesByExtensions(fs::path directory, const std::vector<std::string>& extensions);

        /**
         * @brief Deletes a file or directory recursively.
         */
        static bool deletePath(fs::path pathToDelete);

        /**
         * @brief Gets all files with a specific extension in a directory.
         */
        static std::vector<fs::path> getFilesByExtension(fs::path directory, std::string extension, bool recursive = false);
    };

} // namespace ImageToolkit