#include "FileSystemTool.hpp"
#include <iostream>
#include <algorithm>

// === FSETool Implementation ===

bool FSETool::pathContains(const std::string& parent_path, const std::string& child_path) {
    try {
        fs::path parent = fs::absolute(parent_path);
        fs::path child = fs::absolute(child_path);
        
        // Check if child starts with parent path
        // std::filesystem doesn't have a direct "is_subpath" method, so we use string logic 
        // or mismatch.
        auto [it_p, it_c] = std::mismatch(parent.begin(), parent.end(), child.begin());
        return it_p == parent.end();
    } catch (...) {
        return false;
    }
}

bool FSETool::createDirectoryForFile(const std::string& filepath) {
    fs::path p(filepath);
    if (p.has_parent_path()) {
        return createDirectory(p.parent_path().string());
    }
    return false;
}

bool FSETool::createDirectory(const std::string& dirpath) {
    try {
        if (fs::exists(dirpath)) return true;
        fs::create_directories(dirpath);
        std::cout << "Created directory: '" << dirpath << "'." << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "ERROR: could not create directory '" << dirpath << "': " << e.what() << std::endl;
        return false;
    }
}

std::string FSETool::toAbsolutePath(const std::string& path) {
    try {
        return fs::absolute(path).string();
    } catch (...) {
        return path;
    }
}

std::vector<std::string> FSETool::getFilesByExtension(const std::string& directory, 
                                                      std::string extension, 
                                                      bool recursive) {
    std::vector<std::string> files;
    std::string dir_abs = toAbsolutePath(directory);
    
    // Normalize extension to have dot
    if (!extension.empty() && extension[0] != '.') extension = "." + extension;

    try {
        if (recursive) {
            for (const auto& entry : fs::recursive_directory_iterator(dir_abs)) {
                if (entry.is_regular_file() && entry.path().extension() == extension) {
                    files.push_back(entry.path().string());
                }
            }
        } else {
            for (const auto& entry : fs::directory_iterator(dir_abs)) {
                if (entry.is_regular_file() && entry.path().extension() == extension) {
                    files.push_back(entry.path().string());
                }
            }
        }
    } catch (...) {}
    return files;
}

// === FileDeleter Implementation ===

bool FileDeleter::deletePath(const std::string& path_to_delete) {
    std::string abs_path = FSETool::toAbsolutePath(path_to_delete);
    if (!fs::exists(abs_path)) return false;

    try {
        return fs::remove_all(abs_path) > 0;
    } catch (const std::exception& e) {
        std::cerr << "Delete Error: " << e.what() << std::endl;
        return false;
    }
}

int FileDeleter::deleteFilesByExtensions(const std::string& directory, 
                                         const std::vector<std::string>& extensions) {
    std::string dir_abs = FSETool::toAbsolutePath(directory);
    int deleted = 0;
    
    // Create a set of extensions for O(1) lookup, ensure they start with dot
    std::vector<std::string> norm_exts;
    for (auto ext : extensions) {
        norm_exts.push_back(ext[0] == '.' ? ext : "." + ext);
    }

    try {
        for (const auto& entry : fs::recursive_directory_iterator(dir_abs)) {
            if (entry.is_regular_file()) {
                std::string file_ext = entry.path().extension().string();
                // Match extension
                bool match = false;
                for (const auto& ext : norm_exts) {
                    if (file_ext == ext) { match = true; break; }
                }

                if (match) {
                    try {
                        fs::remove(entry.path());
                        deleted++;
                    } catch (...) {}
                }
            }
        }
    } catch (...) {}
    return deleted;
}