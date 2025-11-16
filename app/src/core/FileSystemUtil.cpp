#include "FileSystemUtil.h"
#include <iostream>

namespace fs = std::filesystem;

bool FileSystemUtil::pathContains(const fs::path& parentPath, const fs::path& childPath) {
    try {
        fs::path parent = fs::canonical(parentPath);
        fs::path child = fs::canonical(childPath);

        while (child.has_parent_path()) {
            if (child == parent) {
                return true;
            }
            child = child.parent_path();
        }
        return child == parent;
    } catch (const fs::filesystem_error& e) {
        std::cerr << "pathContains error: " << e.what() << std::endl;
        return false;
    }
}

bool FileSystemUtil::createDirectory(const fs::path& path, bool isFilePath) {
    fs::path dirToCreate = isFilePath ? path.parent_path() : path;

    if (dirToCreate.empty() || fs::exists(dirToCreate)) {
        return true;
    }
    try {
        fs::create_directories(dirToCreate);
        std::cout << "Created directory: " << dirToCreate.string() << std::endl;
        return true;
    } catch (const fs::filesystem_error& e) {
        std::cerr << "ERROR: could not create directory '" << dirToCreate.string() << "': " << e.what() << std::endl;
        return false;
    }
}

fs::path FileSystemUtil::resolvePath(const fs::path& path) {
    try {
        if (fs::exists(path)) {
            return fs::canonical(path);
        }
        return fs::absolute(path);
    } catch (const fs::filesystem_error& e) {
        std::cerr << "resolvePath error: " << e.what() << std::endl;
        return fs::absolute(path);
    }
}

std::vector<std::string> FileSystemUtil::getFilesByExtension(const fs::path& directory, const std::string& extension, bool recursive) {
    std::vector<std::string> files;
    std::string ext = extension.find('.') == 0 ? extension : "." + extension;
    fs::path dir = resolvePath(directory);

    try {
        if (recursive) {
            for (const auto& entry : fs::recursive_directory_iterator(dir)) {
                if (entry.is_regular_file() && entry.path().extension() == ext) {
                    files.push_back(entry.path().string());
                }
            }
        } else {
            for (const auto& entry : fs::directory_iterator(dir)) {
                if (entry.is_regular_file() && entry.path().extension() == ext) {
                    files.push_back(entry.path().string());
                }
            }
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "getFilesByExtension error: " << e.what() << std::endl;
    }
    return files;
}

bool FileSystemUtil::deletePath(const fs::path& pathToDelete) {
    try {
        fs::path p = resolvePath(pathToDelete);
        if (!fs::exists(p)) {
            std::cout << "WARNING: path does not exist - did not delete '" << p.string() << "'." << std::endl;
            return false;
        }
        if (fs::is_directory(p)) {
            fs::remove_all(p);
            std::cout << "Deleted directory: '" << p.string() << "'." << std::endl;
        } else if (fs::is_regular_file(p)) {
            fs::remove(p);
            std::cout << "Deleted file: '" << p.string() << "'." << std::endl;
        }
        return true;
    } catch (const fs::filesystem_error& e) {
        std::cerr << "ERROR: Could not delete path " << pathToDelete.string() << ". Reason: " << e.what() << std::endl;
        return false;
    }
}

int FileSystemUtil::deleteFilesByExtensions(const fs::path& directory, const std::vector<std::string>& extensions) {
    fs::path dir = resolvePath(directory);
    int deletedCount = 0;

    std::vector<std::string> exts = extensions;
    for (auto& ext : exts) {
        if (ext.find('.') != 0) {
            ext = "." + ext;
        }
    }

    try {
        for (const auto& entry : fs::recursive_directory_iterator(dir)) {
            if (entry.is_regular_file()) {
                std::string fileExt = entry.path().extension().string();
                for (const auto& ext : exts) {
                    if (fileExt == ext) {
                        if (fs::remove(entry.path())) {
                            std::cout << "Deleted: " << entry.path().string() << std::endl;
                            deletedCount++;
                        }
                        break; // Move to the next file
                    }
                }
            }
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "deleteFilesByExtensions error: " << e.what() << std::endl;
    }
    
    std::cout << "Deleted " << deletedCount << " files recursively." << std::endl;
    return deletedCount;
}