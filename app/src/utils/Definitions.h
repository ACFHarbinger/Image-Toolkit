#ifndef DEFINITIONS_H
#define DEFINITIONS_H

#include <string>
#include <vector>
#include <filesystem>

namespace Definitions {

// --- File System Paths ---
// NOTE: These paths are defined relative to an assumed runtime directory 
// or will be dynamically resolved by FileSystemUtil/Configuration Manager.
// We use raw strings where necessary for path separators.

// Base Directories (relative paths are placeholders)
const std::string CRYPTO_DIR = "assets/cryptography";
const std::string IMAGES_DIR = "assets/images";
const std::string API_DIR = "assets/api";
const std::string LOCAL_SOURCE_PATH = "data";
const std::string DRIVE_DESTINATION_FOLDER_NAME = "data";

// Specific Files
const std::string JAR_FILE = "cryptography/target/cryptography-1.0.0-SNAPSHOT-uber.jar";
const std::string KEYSTORE_FILE = CRYPTO_DIR + "/my_java_keystore.p12";
const std::string VAULT_FILE = CRYPTO_DIR + "/my_secure_data.vault";
const std::string PEPPER_FILE = CRYPTO_DIR + "/pepper.txt";
const std::string KEY_ALIAS = "my-aes-key";
const std::string ICON_FILE = IMAGES_DIR + "/image_toolkit_icon.png";
const std::string SERVICE_ACCOUNT_FILE = API_DIR + "/image_toolkit_service.json";
const std::string CLIENT_SECRETS_FILE = API_DIR + "/client_secret.json";
const std::string TOKEN_FILE = API_DIR + "/token.json";


// --- Settings ---

// Image manipulation
const std::vector<std::string> SUPPORTED_IMG_FORMATS = {
    "webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"
};

// Web Crawler
const std::vector<std::string> WC_BROWSERS = {
    "brave", "firefox", "chrome", "edge", "safari"
};

const int CRAWLER_TIME_OPEN = 120;
const int CRAWLER_SETUP_WAIT_TIME = 15;

// GUI settings
const double CTRL_C_TIMEOUT = 2.0;
const std::vector<std::string> APP_STYLES = {
    "fusion", "windows", "windowsxp", "macintosh"
};

// Database
const std::vector<std::string> START_TAGS = {
    "landscape", "night", "day", "indoor", "outdoor",
    "solo", "multiple", "fanart", "official", "cosplay",
    "portrait", "full_body", "action", "close_up", "nsfw",
    "color", "monochrome", "sketch", "digital", "traditional"
};

// Google Drive
const std::vector<std::string> SCOPES = {
    "https://www.googleapis.com/auth/drive"
};
const std::string SYNC_ERROR = "SyncFailed";

} // namespace Definitions

#endif // DEFINITIONS_H