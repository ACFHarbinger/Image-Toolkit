#include "FileSystemEntries.h"
#include <iostream>

namespace ImageToolkit
{
    // --- Utility Method Implementations ---

    void FileSystemEntries::ensureDirectoryExists(const fs::path& filePath)
    {
        fs::path directory = filePath.parent_path();
        if (!directory.empty() && !fs::exists(directory))
        {
            try
            {
                fs::create_directories(directory);
                std::cout << "Created directory: '" << directory.string() << "'." << std::endl;
            }
            catch (const std::exception& e)
            {
                throw ImageToolException("Could not create directory: " + directory.string() + ". Reason: " + e.what());
            }
        }
    }

    fs::path FileSystemEntries::makeAbsolute(const fs::path& path)
    {
        return fs::absolute(path);
    }

    // --- Core Method Implementations ---

    bool FileSystemEntries::pathContains(const fs::path& parentPath, const fs::path& childPath)
    {
        try
        {
            fs::path parent = fs::canonical(parentPath);
            fs::path child = fs::canonical(childPath);

            // Iterate up from the child to see if we find the parent
            auto it = child.parent_path();
            while (!it.empty() && it != it.root_path()) {
                if (it == parent) {
                    return true;
                }
                it = it.parent_path();
            }
            // Check the root case
            return it == parent;
        }
        catch (const fs::filesystem_error&)
        {
            return false;
        }
    }

    int FileSystemEntries::deleteFilesByExtensions(fs::path directory, const std::vector<std::string>& extensions)
    {
        directory = makeAbsolute(directory);
        int deletedCount = 0;

        for (const auto& ext : extensions)
        {
            std::string targetExt = ext.find('.') == 0 ? ext : "." + ext;
            targetExt = to_lower(targetExt);

            // Use recursive_directory_iterator to match rglob
            for (const auto& entry : fs::recursive_directory_iterator(directory))
            {
                // FIX 1: Use fs::is_regular_file(entry) instead of entry.is_file()
                if (fs::is_regular_file(entry) && to_lower(entry.path().extension().string()) == targetExt)
                {
                    try
                    {
                        fs::remove(entry.path());
                        std::cout << "Deleted: " << entry.path().string() << std::endl;
                        deletedCount++;
                    }
                    catch (const std::exception& e)
                    {
                        std::cerr << "ERROR: Could not delete file " << entry.path().string() << ". Reason: " << e.what() << std::endl;
                    }
                }
            }
        }
        std::cout << "Deleted " << deletedCount << " files recursively." << std::endl;
        return deletedCount;
    }

    bool FileSystemEntries::deletePath(fs::path pathToDelete)
    {
        pathToDelete = makeAbsolute(pathToDelete);

        if (!fs::exists(pathToDelete))
        {
            std::cerr << "WARNING: specified path does not exist - did not delete '" << pathToDelete.string() << "'." << std::endl;
            return false;
        }

        try
        {
            if (fs::is_directory(pathToDelete))
            {
                fs::remove_all(pathToDelete); // Replaces shutil.rmtree
                std::cout << "Deleted directory: '" << pathToDelete.string() << "'." << std::endl;
            }
            else if (fs::is_regular_file(pathToDelete)) // Use fs::is_regular_file for consistency
            {
                fs::remove(pathToDelete); // Replaces os.remove
                std::cout << "Deleted file: '" << pathToDelete.string() << "'." << std::endl;
            }
            return true;
        }
        catch (const std::exception& e)
        {
            // FIX 2: Use << to stream C-style strings, not +
            std::cerr << "ERROR: Could not delete " << pathToDelete.string() << ". Reason: " << e.what() << std::endl;
            return false;
        }
    }

    std::vector<fs::path> FileSystemEntries::getFilesByExtension(fs::path directory, std::string extension, bool recursive)
    {
        directory = makeAbsolute(directory);
        std::vector<fs::path> files;

        // FIX 3: Use C++17-compatible check (std::string::starts_with is C++20)
        if (extension.empty() || extension[0] != '.') {
            extension = "." + extension;
        }
        extension = to_lower(extension);

        auto add_file_if_match = [&](const fs::directory_entry& entry) {
            // Use fs::is_regular_file for consistency
            if (fs::is_regular_file(entry) && to_lower(entry.path().extension().string()) == extension) {
                // Return resolved/absolute paths
                files.push_back(fs::absolute(entry.path()));
            }
        };

        try
        {
            if (recursive) {
                for (const auto& entry : fs::recursive_directory_iterator(directory)) {
                    add_file_if_match(entry);
                }
            } else {
                for (const auto& entry : fs::directory_iterator(directory)) {
                    add_file_if_match(entry);
                }
            }
        }
        catch(const std::exception& e)
        {
            std::cerr << "Error scanning directory " << directory.string() << ": " << e.what() << std::endl;
        }
        return files;
    }

} // namespace ImageToolkit