#ifndef WEB_CLIENT_H
#define WEB_CLIENT_H

#include <string>
#include <vector>
#include <set>
#include <filesystem>
#include <functional>
#include <gumbo.h>

/**
 * @brief Replaces the Python WebCrawler, ImageCrawler, and WebFileLoader.
 *
 * This class uses libcurl for HTTP requests and Gumbo-parser for HTML parsing
 * to find and download images from web pages.
 */
class WebClient {
public:
    /**
     * @brief Callback function for status updates.
     * (std::string message)
     */
    using StatusCallback = std::function<void(const std::string&)>;

    /**
     * @brief Callback function for when an image is saved.
     * (std::string saved_file_path)
     */
    using ImageSavedCallback = std::function<void(const std::string&)>;

    WebClient(const std::filesystem::path& downloadDir);
    ~WebClient();

    /**
     * @brief Sets the callback for status updates.
     */
    void setStatusCallback(StatusCallback callback);

    /**
     * @brief Sets the callback for saved images.
     */
    void setImageSavedCallback(ImageSavedCallback callback);

    /**
     * @brief Runs the full image crawl logic.
     *
     * @param targetUrl The base URL to scrape.
     * @param replaceStr A substring in the URL to replace (e.g., "PAGE_NUM").
     * @param replacements A list of strings to replace 'replaceStr' with.
     * @param skipFirst Number of images to skip from the start.
     * @param skipLast Number of images to skip from the end.
     * @return Total number of images successfully downloaded.
     */
    int runCrawl(const std::string& targetUrl,
                 const std::string& replaceStr,
                 const std::vector<std::string>& replacements,
                 int skipFirst,
                 int skipLast);

    /**
     * @brief Downloads the content of a single URL.
     * @param url The URL to fetch.
     * @param output The string to store the fetched content.
     * @return true on success, false on failure.
     */
    bool httpGet(const std::string& url, std::string& output);

    /**
     * @brief Downloads an image file from a URL.
     * @param url The URL of the image.
     * @param savePath The local path to save the image.
     * @return true on success, false on failure.
     */
    bool downloadImage(const std::string& url, const std::filesystem::path& savePath);

private:
    /**
     * @brief Parses HTML and finds all image source URLs.
     * @param htmlContent The HTML to parse.
     * @param baseUrl The page's base URL (for resolving relative links).
     * @param foundUrls A set to store the absolute image URLs.
     */
    void findImageUrls(const std::string& htmlContent, const std::string& baseUrl, std::set<std::string>& foundUrls);

    /**
     * @brief Recursive helper for Gumbo to find <img> tags.
     */
    void searchForImgTags(GumboNode* node, std::set<std::string>& foundUrls);

    /**
     * @brief Resolves a relative URL against a base URL.
     */
    std::string resolveUrl(const std::string& baseUrl, const std::string& relativeUrl);
    
    /**
     * @brief Finds a unique filename to avoid overwrites.
     */
    std::filesystem::path getUniqueFilename(const std::filesystem::path& filepath);

    void* m_curlHandle; // void* to avoid including curl.h in header
    std::filesystem::path m_downloadDir;
    StatusCallback m_statusCallback;
    ImageSavedCallback m_imageSavedCallback;

    // libcurl write callback (static)
    static size_t writeCallback(void* contents, size_t size, size_t nmemb, void* userp);
    // libcurl file write callback (static)
    static size_t writeFileCallback(void* contents, size_t size, size_t nmemb, void* userp);
};

#endif // WEB_CLIENT_H