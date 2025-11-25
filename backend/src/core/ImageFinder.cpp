#include "ImageFinder.hpp"
#include "FileSystemTool.hpp"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <openssl/sha.h>
#include <filesystem>
#include <iostream>

namespace fs = std::filesystem;

// ================= DuplicateFinder =================

std::optional<std::string> DuplicateFinder::getFileHash(const std::string& filepath, 
                                                        const std::string& algorithm, 
                                                        size_t chunk_size) {
    std::ifstream file(filepath, std::ios::binary);
    if (!file) return std::nullopt;

    if (algorithm == "sha256") {
        SHA256_CTX sha256;
        SHA256_Init(&sha256);
        std::vector<char> buffer(chunk_size);
        while (file.read(buffer.data(), chunk_size)) {
            SHA256_Update(&sha256, buffer.data(), chunk_size);
        }
        SHA256_Update(&sha256, buffer.data(), file.gcount());
        
        unsigned char hash[SHA256_DIGEST_LENGTH];
        SHA256_Final(hash, &sha256);
        
        std::stringstream ss;
        for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
            ss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
        }
        return ss.str();
    }
    return std::nullopt;
}

std::map<std::string, std::vector<std::string>> DuplicateFinder::findDuplicateImages(
    const std::string& directory, 
    const std::vector<std::string>& extensions, 
    bool recursive) 
{
    std::string dir_abs = FSETool::toAbsolutePath(directory);
    
    // Default extensions
    std::vector<std::string> exts = extensions;
    if (exts.empty()) exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"};
    // Normalize to lower case with dot
    for(auto& e : exts) {
        if(e[0] != '.') e = "." + e;
        std::transform(e.begin(), e.end(), e.begin(), ::tolower);
    }

    // 1. Group by Size
    std::map<uintmax_t, std::vector<std::string>> size_groups;
    
    auto processEntry = [&](const fs::directory_entry& entry) {
        if (entry.is_regular_file()) {
            std::string ext = entry.path().extension().string();
            std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
            
            bool match = false;
            for(const auto& e : exts) if (e == ext) match = true;
            
            if (match) {
                try {
                    size_groups[entry.file_size()].push_back(entry.path().string());
                } catch(...) {}
            }
        }
    };

    if (recursive) {
        for (const auto& entry : fs::recursive_directory_iterator(dir_abs)) processEntry(entry);
    } else {
        for (const auto& entry : fs::directory_iterator(dir_abs)) processEntry(entry);
    }

    // 2. Group by Hash (only for size collisions)
    std::map<std::string, std::vector<std::string>> duplicates;
    
    for (const auto& [size, paths] : size_groups) {
        if (paths.size() < 2) continue;

        std::map<std::string, std::vector<std::string>> hash_groups;
        for (const auto& p : paths) {
            auto h = getFileHash(p);
            if (h) hash_groups[*h].push_back(p);
        }

        for (const auto& [hash, p_list] : hash_groups) {
            if (p_list.size() > 1) {
                duplicates[hash] = p_list;
            }
        }
    }
    return duplicates;
}


// ================= SimilarityFinder =================

std::vector<std::string> SimilarityFinder::getImagesList(const std::string& directory, 
                                                         const std::vector<std::string>& extensions, 
                                                         bool recursive) {
    // Reuse logic inside findDuplicateImages but strictly listing
    std::vector<std::string> images;
    std::string dir_abs = FSETool::toAbsolutePath(directory);
    std::vector<std::string> exts = extensions;
    if (exts.empty()) exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"};
    for(auto& e : exts) { if(e[0] != '.') e = "." + e; std::transform(e.begin(), e.end(), e.begin(), ::tolower); }

    auto check = [&](const fs::path& p) {
        std::string ext = p.extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        for(const auto& e : exts) if(e == ext) return true;
        return false;
    };

    if (recursive) {
        for (const auto& entry : fs::recursive_directory_iterator(dir_abs)) 
            if (entry.is_regular_file() && check(entry.path())) images.push_back(entry.path().string());
    } else {
        for (const auto& entry : fs::directory_iterator(dir_abs))
             if (entry.is_regular_file() && check(entry.path())) images.push_back(entry.path().string());
    }
    return images;
}

// --- pHash Helpers ---
uint64_t SimilarityFinder::computeAverageHash(const cv::Mat& img) {
    if (img.empty()) return 0;
    cv::Mat resized;
    // 1. Resize to 8x8, 2. Convert to Gray
    cv::resize(img, resized, cv::Size(8, 8), 0, 0, cv::INTER_AREA);
    if (resized.channels() > 1) cv::cvtColor(resized, resized, cv::COLOR_BGR2GRAY);
    
    // 3. Compute Mean
    double mean = cv::mean(resized)[0];
    
    // 4. Compute Bits
    uint64_t hash = 0;
    for (int i = 0; i < resized.rows; ++i) {
        for (int j = 0; j < resized.cols; ++j) {
            if (resized.at<uint8_t>(i, j) > mean) {
                hash |= (1ULL << (i * 8 + j));
            }
        }
    }
    return hash;
}

int SimilarityFinder::hammingDistance(uint64_t h1, uint64_t h2) {
    uint64_t x = h1 ^ h2;
    // Count set bits (Kernighan's or built-in)
    int dist = 0;
    while(x) {
        dist++;
        x &= x - 1;
    }
    return dist;
}

std::map<std::string, std::vector<std::string>> SimilarityFinder::findSimilarPHash(
    const std::string& directory, 
    const std::vector<std::string>& extensions, 
    int threshold) 
{
    auto images = getImagesList(directory, extensions);
    std::vector<std::pair<std::string, uint64_t>> hashes;

    // 1. Calc Hashes
    for (const auto& path : images) {
        cv::Mat img = cv::imread(path);
        if (!img.empty()) {
            hashes.push_back({path, computeAverageHash(img)});
        }
    }

    // 2. Group O(N*M)
    std::map<std::string, std::vector<std::string>> results;
    std::vector<bool> visited(hashes.size(), false);
    int group_id = 0;

    for (size_t i = 0; i < hashes.size(); ++i) {
        if (visited[i]) continue;
        
        std::vector<std::string> group;
        group.push_back(hashes[i].first);
        visited[i] = true;

        for (size_t j = i + 1; j < hashes.size(); ++j) {
            if (visited[j]) continue;
            if (hammingDistance(hashes[i].second, hashes[j].second) <= threshold) {
                group.push_back(hashes[j].first);
                visited[j] = true;
            }
        }

        if (group.size() > 1) {
            results["group_" + std::to_string(group_id++)] = group;
        }
    }
    return results;
}

// --- SSIM Helpers ---
double SimilarityFinder::computeSSIM(const cv::Mat& i1, const cv::Mat& i2) {
    const double C1 = 6.5025, C2 = 58.5225;
    
    cv::Mat I1, I2;
    i1.convertTo(I1, CV_32F);
    i2.convertTo(I2, CV_32F);

    cv::Mat I1_2   = I1.mul(I1);
    cv::Mat I2_2   = I2.mul(I2);
    cv::Mat I1_I2  = I1.mul(I2);

    cv::Mat mu1, mu2;
    cv::GaussianBlur(I1, mu1, cv::Size(11, 11), 1.5);
    cv::GaussianBlur(I2, mu2, cv::Size(11, 11), 1.5);

    cv::Mat mu1_2   = mu1.mul(mu1);
    cv::Mat mu2_2   = mu2.mul(mu2);
    cv::Mat mu1_mu2 = mu1.mul(mu2);

    cv::Mat sigma1_2, sigma2_2, sigma12;
    cv::GaussianBlur(I1_2, sigma1_2, cv::Size(11, 11), 1.5);
    sigma1_2 -= mu1_2;

    cv::GaussianBlur(I2_2, sigma2_2, cv::Size(11, 11), 1.5);
    sigma2_2 -= mu2_2;

    cv::GaussianBlur(I1_I2, sigma12, cv::Size(11, 11), 1.5);
    sigma12 -= mu1_mu2;

    cv::Mat t1, t2, t3;
    t1 = 2 * mu1_mu2 + C1;
    t2 = 2 * sigma12 + C2;
    t3 = t1.mul(t2);

    t1 = mu1_2 + mu2_2 + C1;
    t2 = sigma1_2 + sigma2_2 + C2;
    t1 = t1.mul(t2);

    cv::Mat ssim_map;
    cv::divide(t3, t1, ssim_map);
    cv::Scalar mssim = cv::mean(ssim_map);
    return mssim[0];
}

std::map<std::string, std::vector<std::string>> SimilarityFinder::findSimilarSSIM(
    const std::string& directory, 
    const std::vector<std::string>& extensions, 
    double threshold) 
{
    auto images = getImagesList(directory, extensions);
    std::vector<std::pair<std::string, cv::Mat>> cache;
    cv::Size process_size(256, 256);

    for (const auto& path : images) {
        cv::Mat img = cv::imread(path, cv::IMREAD_GRAYSCALE);
        if (!img.empty()) {
            cv::resize(img, img, process_size, 0, 0, cv::INTER_LANCZOS4);
            cache.push_back({path, img});
        }
    }

    std::map<std::string, std::vector<std::string>> results;
    std::vector<bool> visited(cache.size(), false);
    int gid = 0;

    for (size_t i = 0; i < cache.size(); ++i) {
        if (visited[i]) continue;
        std::vector<std::string> group;
        group.push_back(cache[i].first);
        visited[i] = true;

        for (size_t j = i + 1; j < cache.size(); ++j) {
            if (visited[j]) continue;
            double score = computeSSIM(cache[i].second, cache[j].second);
            if (score > threshold) {
                group.push_back(cache[j].first);
                visited[j] = true;
            }
        }

        if (group.size() > 1) {
            results["ssim_group_" + std::to_string(gid++)] = group;
        }
    }
    return results;
}

std::map<std::string, std::vector<std::string>> SimilarityFinder::findSimilarORB(
    const std::string& directory, 
    const std::vector<std::string>& extensions, 
    double match_threshold) 
{
    auto images = getImagesList(directory, extensions);
    auto orb = cv::ORB::create(500);
    std::vector<std::pair<std::string, cv::Mat>> descriptors;

    for (const auto& path : images) {
        cv::Mat img = cv::imread(path, cv::IMREAD_GRAYSCALE);
        if (img.empty()) continue;
        
        std::vector<cv::KeyPoint> kp;
        cv::Mat des;
        orb->detectAndCompute(img, cv::noArray(), kp, des);
        
        if (!des.empty() && des.rows > 10) {
            descriptors.push_back({path, des});
        }
    }

    std::map<std::string, std::vector<std::string>> results;
    std::vector<bool> visited(descriptors.size(), false);
    cv::BFMatcher matcher(cv::NORM_HAMMING, false); // CrossCheck false for KNN
    int gid = 0;

    for (size_t i = 0; i < descriptors.size(); ++i) {
        if (visited[i]) continue;
        std::vector<std::string> group = {descriptors[i].first};
        visited[i] = true;

        for (size_t j = i + 1; j < descriptors.size(); ++j) {
            if (visited[j]) continue;
            
            std::vector<std::vector<cv::DMatch>> knn_matches;
            matcher.knnMatch(descriptors[i].second, descriptors[j].second, knn_matches, 2);

            std::vector<cv::DMatch> good_matches;
            for (const auto& m : knn_matches) {
                if (m.size() < 2) continue;
                if (m[0].distance < 0.75 * m[1].distance) {
                    good_matches.push_back(m[0]);
                }
            }

            double similarity = (double)good_matches.size() / descriptors[i].second.rows;
            // Lower threshold for ORB (python was 0.20)
            if (similarity > 0.20 && good_matches.size() > 10) {
                group.push_back(descriptors[j].first);
                visited[j] = true;
            }
        }
        if (group.size() > 1) results["orb_group_" + std::to_string(gid++)] = group;
    }
    return results;
}

std::map<std::string, std::vector<std::string>> SimilarityFinder::findSimilarSIFT(
    const std::string& directory, 
    const std::vector<std::string>& extensions) 
{
    auto images = getImagesList(directory, extensions);
    auto sift = cv::SIFT::create(1000);
    std::vector<std::pair<std::string, cv::Mat>> descriptors;

    for (const auto& path : images) {
        cv::Mat img = cv::imread(path, cv::IMREAD_GRAYSCALE);
        if (img.empty()) continue;
        std::vector<cv::KeyPoint> kp;
        cv::Mat des;
        sift->detectAndCompute(img, cv::noArray(), kp, des);
        if (!des.empty() && des.rows > 10) descriptors.push_back({path, des});
    }

    std::map<std::string, std::vector<std::string>> results;
    std::vector<bool> visited(descriptors.size(), false);
    cv::BFMatcher matcher(cv::NORM_L2, false);
    int gid = 0;

    for (size_t i = 0; i < descriptors.size(); ++i) {
        if (visited[i]) continue;
        std::vector<std::string> group = {descriptors[i].first};
        visited[i] = true;

        for (size_t j = i + 1; j < descriptors.size(); ++j) {
            if (visited[j]) continue;
            std::vector<std::vector<cv::DMatch>> knn_matches;
            matcher.knnMatch(descriptors[i].second, descriptors[j].second, knn_matches, 2);

            std::vector<cv::DMatch> good_matches;
            for (const auto& m : knn_matches) {
                if (m.size() < 2) continue;
                if (m[0].distance < 0.75 * m[1].distance) {
                    good_matches.push_back(m[0]);
                }
            }

            double similarity = (double)good_matches.size() / descriptors[i].second.rows;
            if (similarity > 0.20) {
                group.push_back(descriptors[j].first);
                visited[j] = true;
            }
        }
        if (group.size() > 1) results["sift_group_" + std::to_string(gid++)] = group;
    }
    return results;
}