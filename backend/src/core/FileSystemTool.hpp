#pragma once

#include <string>
#include <vector>
#include <filesystem>
#include <optional>

namespace fs = std::filesystem;

class FSETool {
public:
    // Utility Methods
    static bool pathContains(const std::string& parent_path, const std::string& child_path);
    
    // Directory Creation (Replaces the decorator logic)
    static bool createDirectoryForFile(const std::string& filepath);
    static bool createDirectory(const std::string& dirpath);

    // Path Normalization (Replaces ensure_absolute_paths decorator)
    static std::string toAbsolutePath(const std::string& path);

    // File Searching
    static std::vector<std::string> getFilesByExtension(const std::string& directory, 
                                                        std::string extension, 
                                                        bool recursive = false);
};

class FileDeleter {
public:
    static bool deletePath(const std::string& path_to_delete);
    static int deleteFilesByExtensions(const std::string& directory, 
                                       const std::vector<std::string>& extensions);
};