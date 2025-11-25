#pragma once

#include <string>
#include <vector>
#include <map>
#include <optional>
#include <opencv2/opencv.hpp>

class DuplicateFinder {
public:
    static std::optional<std::string> getFileHash(const std::string& filepath, 
                                                  const std::string& algorithm = "sha256", 
                                                  size_t chunk_size = 65536);

    // Returns map: Hash -> List of Filepaths
    static std::map<std::string, std::vector<std::string>> findDuplicateImages(
        const std::string& directory, 
        const std::vector<std::string>& extensions = {}, 
        bool recursive = true
    );
};

class SimilarityFinder {
public:
    static std::vector<std::string> getImagesList(const std::string& directory, 
                                                  const std::vector<std::string>& extensions = {}, 
                                                  bool recursive = true);

    // aHash (Average Hash) Similarity
    static std::map<std::string, std::vector<std::string>> findSimilarPHash(
        const std::string& directory, 
        const std::vector<std::string>& extensions = {}, 
        int threshold = 5
    );

    // SSIM (Structural Similarity Index)
    static std::map<std::string, std::vector<std::string>> findSimilarSSIM(
        const std::string& directory, 
        const std::vector<std::string>& extensions = {}, 
        double threshold = 0.90
    );

    // ORB Feature Matching
    static std::map<std::string, std::vector<std::string>> findSimilarORB(
        const std::string& directory, 
        const std::vector<std::string>& extensions = {}, 
        double match_threshold = 0.65
    );
    
    // SIFT Feature Matching
    static std::map<std::string, std::vector<std::string>> findSimilarSIFT(
        const std::string& directory, 
        const std::vector<std::string>& extensions = {}
    );

private:
    static uint64_t computeAverageHash(const cv::Mat& img);
    static int hammingDistance(uint64_t h1, uint64_t h2);
    static double computeSSIM(const cv::Mat& i1, const cv::Mat& i2);
};