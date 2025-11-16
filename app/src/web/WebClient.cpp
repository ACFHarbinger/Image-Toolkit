#include "WebClient.h"
#include "../core/FileSystemUtil.h" // Assuming this exists from previous step
#include <iostream>
#include <fstream>
#include <curl/curl.h>
#include <gumbo.h>

namespace fs = std::filesystem;

// A simple URI parser struct
struct Uri {
    std::string protocol, host, port, path, query;
};

// Basic URI parser to help with resolving relative URLs
Uri parseUri(const std::string& url) {
    Uri uri;
    auto protocolEnd = url.find("://");
    if (protocolEnd != std::string::npos) {
        uri.protocol = url.substr(0, protocolEnd);
        std::string rest = url.substr(protocolEnd + 3);
        auto hostEnd = rest.find('/');
        if (hostEnd == std::string::npos) {
            hostEnd = rest.find('?');
        }
        
        std::string hostPort = (hostEnd == std::string::npos) ? rest : rest.substr(0, hostEnd);
        if (hostEnd != std::string::npos) {
            rest = rest.substr(hostEnd);
        } else {
            rest = "";
        }

        auto portStart = hostPort.find(':');
        if (portStart != std::string::npos) {
            uri.host = hostPort.substr(0, portStart);
            uri.port = hostPort.substr(portStart + 1);
        } else {
            uri.host = hostPort;
        }

        auto queryStart = rest.find('?');
        if (queryStart != std::string::npos) {
            uri.path = rest.substr(0, queryStart);
            uri.query = rest.substr(queryStart + 1);
        } else {
            uri.path = rest;
        }
    }
    return uri;
}

// --- WebClient Implementation ---

WebClient::WebClient(const std::filesystem::path& downloadDir)
    : m_downloadDir(downloadDir), m_statusCallback(nullptr), m_imageSavedCallback(nullptr) {
    curl_global_init(CURL_GLOBAL_ALL);
    m_curlHandle = curl_easy_init();
    if (!m_curlHandle) {
        throw std::runtime_error("Failed to initialize libcurl");
    }
    FileSystemUtil::createDirectory(m_downloadDir);
}

WebClient::~WebClient() {
    if (m_curlHandle) {
        curl_easy_cleanup(static_cast<CURL*>(m_curlHandle));
    }
    curl_global_cleanup();
}

void WebClient::setStatusCallback(StatusCallback callback) {
    m_statusCallback = callback;
}

void WebClient::setImageSavedCallback(ImageSavedCallback callback) {
    m_imageSavedCallback = callback;
}

// libcurl callback to write data to a std::string
size_t WebClient::writeCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    static_cast<std::string*>(userp)->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

// libcurl callback to write data to a FILE*
size_t WebClient::writeFileCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    return fwrite(contents, size, nmemb, static_cast<FILE*>(userp));
}

bool WebClient::httpGet(const std::string& url, std::string& output) {
    CURL* curl = static_cast<CURL*>(m_curlHandle);
    if (!curl) return false;

    output.clear();
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &output);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L); // Follow redirects
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");

    CURLcode res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
        return false;
    }
    return true;
}

bool WebClient::downloadImage(const std::string& url, const std::filesystem::path& savePath) {
    CURL* curl = static_cast<CURL*>(m_curlHandle);
    if (!curl) return false;

    FILE* fp = fopen(savePath.string().c_str(), "wb");
    if (!fp) {
        std::cerr << "Failed to open file for writing: " << savePath.string() << std::endl;
        return false;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeFileCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");

    CURLcode res = curl_easy_perform(curl);
    fclose(fp); // Always close the file handle

    if (res != CURLE_OK) {
        std::cerr << "curl_easy_perform() for image download failed: " << curl_easy_strerror(res) << std::endl;
        fs::remove(savePath); // Delete partial file on error
        return false;
    }
    return true;
}

std::string WebClient::resolveUrl(const std::string& baseUrl, const std::string& relativeUrl) {
    if (relativeUrl.rfind("http://", 0) == 0 || relativeUrl.rfind("https://", 0) == 0) {
        return relativeUrl; // Already absolute
    }

    Uri base = parseUri(baseUrl);
    std::string baseAddress = base.protocol + "://" + base.host;
    if (!base.port.empty()) {
        baseAddress += ":" + base.port;
    }

    if (relativeUrl.rfind("//", 0) == 0) {
        return base.protocol + ":" + relativeUrl; // Protocol-relative
    }

    if (relativeUrl.rfind("/", 0) == 0) {
        return baseAddress + relativeUrl; // Root-relative
    }

    // Path-relative
    std::string path = base.path;
    auto lastSlash = path.rfind('/');
    if (lastSlash != std::string::npos) {
        path = path.substr(0, lastSlash + 1);
    } else {
        path = "/";
    }
    return baseAddress + path + relativeUrl;
}

void WebClient::searchForImgTags(GumboNode* node, std::set<std::string>& foundUrls) {
    if (node->type != GUMBO_NODE_ELEMENT) {
        return;
    }

    if (node->v.element.tag == GUMBO_TAG_IMG) {
        GumboAttribute* src = gumbo_get_attribute(&node->v.element.attributes, "src");
        if (src && src->value) {
            std::string srcUrl = src->value;
            if (srcUrl.rfind("data:", 0) != 0) { // Skip inline data URIs
                foundUrls.insert(srcUrl);
            }
        }
    }

    GumboVector* children = &node->v.element.children;
    for (unsigned int i = 0; i < children->length; ++i) {
        searchForImgTags(static_cast<GumboNode*>(children->data[i]), foundUrls);
    }
}

void WebClient::findImageUrls(const std::string& htmlContent, const std::string& baseUrl, std::set<std::string>& foundUrls) {
    GumboOutput* output = gumbo_parse(htmlContent.c_str());
    if (!output) return;

    std::set<std::string> relativeUrls;
    searchForImgTags(output->root, relativeUrls);
    gumbo_destroy_output(&kGumboDefaultOptions, output);

    // Resolve all found URLs
    for (const auto& relUrl : relativeUrls) {
        foundUrls.insert(resolveUrl(baseUrl, relUrl));
    }
}

std::filesystem::path WebClient::getUniqueFilename(const std::filesystem::path& filepath) {
    if (!fs::exists(filepath)) {
        return filepath;
    }

    fs::path base = filepath.parent_path() / filepath.stem();
    std::string ext = filepath.extension().string();
    int counter = 1;
    fs::path newPath = base;
    newPath += " (" + std::to_string(counter) + ")" + ext;

    while (fs::exists(newPath)) {
        counter++;
        newPath = base;
        newPath += " (" + std::to_string(counter) + ")" + ext;
    }
    return newPath;
}

int WebClient::runCrawl(const std::string& targetUrl,
                        const std::string& replaceStr,
                        const std::vector<std::string>& replacements,
                        int skipFirst,
                        int skipLast) {
    
    std::vector<std::string> urlsToScrape;
    urlsToScrape.push_back(targetUrl);

    if (!replaceStr.empty() && !replacements.empty()) {
        for (const auto& rep : replacements) {
            std::string newUrl = targetUrl;
            size_t pos = newUrl.find(replaceStr);
            if (pos != std::string::npos) {
                newUrl.replace(pos, replaceStr.length(), rep);
            }
            urlsToScrape.push_back(newUrl);
        }
    }

    int totalPages = urlsToScrape.size();
    int totalDownloaded = 0;

    for (int i = 0; i < totalPages; ++i) {
        const std::string& url = urlsToScrape[i];
        if (m_statusCallback) m_statusCallback("Loading page " + std::to_string(i + 1) + "/" + std::to_string(totalPages) + ": " + url);

        std::string htmlContent;
        if (!httpGet(url, htmlContent)) {
            if (m_statusCallback) m_statusCallback("Failed to load page: " + url);
            continue;
        }

        if (m_statusCallback) m_statusCallback("Scanning for images...");
        std::set<std::string> imageUrls;
        findImageUrls(htmlContent, url, imageUrls);

        if (imageUrls.empty()) {
            if (m_statusCallback) m_statusCallback("No images found on page " + std::to_string(i + 1));
            continue;
        }
        
        // Convert set to vector to apply skipping
        std::vector<std::string> images(imageUrls.begin(), imageUrls.end());
        
        int totalFound = images.size();
        int skipTotal = skipFirst + skipLast;
        if (skipTotal >= totalFound) {
             if (m_statusCallback) m_statusCallback("Not enough images to skip on page " + std::to_string(i + 1));
             continue;
        }

        int endIdx = totalFound - skipLast;
        int startIdx = skipFirst;
        int totalToDownload = endIdx - startIdx;
        
        if (m_statusCallback) m_statusCallback("Downloading " + std::to_string(totalToDownload) + " unique images from page " + std::to_string(i + 1) + "...");

        for (int j = startIdx; j < endIdx; ++j) {
            const std::string& imgUrl = images[j];
            if (m_statusCallback) m_statusCallback("Page " + std::to_string(i + 1) + "/" + std::to_string(totalPages) + ": Downloading image " + std::to_string(j - startIdx + 1) + "/" + std::to_string(totalToDownload) + "...");

            // Get filename from URL
            Uri imgUri = parseUri(imgUrl);
            std::string filename = std::filesystem::path(imgUri.path).filename().string();
            if (filename.empty() || filename.find('.') == std::string::npos) {
                filename = "image_" + std::to_string(std::hash<std::string>{}(imgUrl)) + ".jpg";
            }
            
            fs::path savePath = getUniqueFilename(m_downloadDir / filename);
            
            if (downloadImage(imgUrl, savePath)) {
                totalDownloaded++;
                if (m_imageSavedCallback) m_imageSavedCallback(savePath.string());
            }
        }
    }

    if (m_statusCallback) m_statusCallback("Crawl complete. Downloaded " + std::to_string(totalDownloaded) + " total images.");
    return totalDownloaded;
}