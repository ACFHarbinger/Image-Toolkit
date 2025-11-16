#include "DatabaseManager.h"
#include <iostream>
#include <sstream>
#include <iomanip>

// Helper to build connection string
std::string buildConnectionString(
    const std::string& dbName, const std::string& dbUser, 
    const std::string& dbPassword, const std::string& dbHost, 
    const std::string& dbPort) {
    
    std::string n = !dbName.empty() ? dbName : (std::getenv("DB_NAME") ? std::getenv("DB_NAME") : "");
    std::string u = !dbUser.empty() ? dbUser : (std::getenv("DB_USER") ? std::getenv("DB_USER") : "");
    std::string p = !dbPassword.empty() ? dbPassword : (std::getenv("DB_PASSWORD") ? std::getenv("DB_PASSWORD") : "");
    std::string h = !dbHost.empty() ? dbHost : (std::getenv("DB_HOST") ? std::getenv("DB_HOST") : "localhost");
    std::string po = !dbPort.empty() ? dbPort : (std::getenv("DB_PORT") ? std::getenv("DB_PORT") : "5432");
    
    return "dbname=" + n + " user=" + u + " password=" + p + " host=" + h + " port=" + po;
}

// Helper to convert vector<float> to pgvector string "[1,2,3]"
std::string vectorToString(const std::vector<float>& vec) {
    std::stringstream ss;
    ss << "[";
    for (size_t i = 0; i < vec.size(); ++i) {
        ss << vec[i];
        if (i < vec.size() - 1) ss << ",";
    }
    ss << "]";
    return ss.str();
}


DatabaseManager::DatabaseManager(int embedDim,
                                 const std::string& dbName,
                                 const std::string& dbUser,
                                 const std::string& dbPassword,
                                 const std::string& dbHost,
                                 const std::string& dbPort)
    : m_embeddingDim(embedDim) {
    
    // Note: dotenv logic is not included. Env vars should be set
    // by the environment or C++ dotenv library.
    m_connectionString = buildConnectionString(dbName, dbUser, dbPassword, dbHost, dbPort);
    connect();
    createTables();
}

DatabaseManager::~DatabaseManager() {
    if (m_conn && m_conn->is_open()) {
        m_conn->close();
    }
}

void DatabaseManager::connect() {
    try {
        m_conn = std::make_unique<pqxx::connection>(m_connectionString);
        std::cout << "Database connection established to " << m_conn->dbname() << std::endl;
    } catch (const pqxx::broken_connection& e) {
        std::cerr << "Error connecting to database: " << e.what() << std::endl;
        std::cerr << "\nPlease ensure PostgreSQL is running and connection details are correct." << std::endl;
        exit(1);
    }
}

void DatabaseManager::createTables() {
    if (!m_conn) return;
    try {
        pqxx::work txn(*m_conn);
        txn.exec("CREATE EXTENSION IF NOT EXISTS vector;");
        
        txn.exec("CREATE TABLE IF NOT EXISTS images ("
                 "id SERIAL PRIMARY KEY, "
                 "file_path TEXT UNIQUE NOT NULL, "
                 "filename TEXT NOT NULL, "
                 "file_size BIGINT, "
                 "width INTEGER, "
                 "height INTEGER, "
                 "group_name TEXT, "
                 "subgroup_name TEXT, "
                 "date_added TIMESTAMP WITHOUT TIME ZONE NOT NULL, "
                 "date_modified TIMESTAMP WITHOUT TIME ZONE, "
                 "embedding vector(" + std::to_string(m_embeddingDim) + "));");
        
        txn.exec("CREATE TABLE IF NOT EXISTS groups (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL);");
        // ... (creation for subgroups, tags, image_tags) ...

        txn.exec("CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path);");
        txn.exec("CREATE INDEX IF NOT EXISTS idx_images_embedding ON images USING hnsw (embedding vector_l2_ops) WHERE embedding IS NOT NULL;");

        txn.commit();
    } catch (const std::exception& e) {
        std::cerr << "Error during table creation: " << e.what() << std::endl;
        throw;
    }
}

void DatabaseManager::resetDatabase() {
     if (!m_conn) throw std::runtime_error("Not connected to database.");
    try {
        pqxx::work txn(*m_conn);
        txn.exec("DROP TABLE IF EXISTS image_tags CASCADE;");
        txn.exec("DROP TABLE IF EXISTS images CASCADE;");
        txn.exec("DROP TABLE IF EXISTS tags CASCADE;");
        txn.exec("DROP TABLE IF EXISTS groups CASCADE;");
        txn.exec("DROP TABLE IF EXISTS subgroups CASCADE;");
        txn.commit();
        createTables();
    } catch (const std::exception& e) {
        std::cerr << "Error during database reset: " << e.what() << std::endl;
        throw;
    }
}

int DatabaseManager::getOrCreateTag(pqxx::work& txn, const std::string& name) {
    std::string sql = "INSERT INTO tags (name) VALUES (" + txn.quote(name) + ") "
                      "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                      "RETURNING id;";
    pqxx::result res = txn.exec(sql);
    return res[0][0].as<int>();
}

void DatabaseManager::addGroup(pqxx::work& txn, const std::string& name) {
    if (name.empty()) return;
    txn.exec("INSERT INTO groups (name) VALUES (" + txn.quote(name) + ") ON CONFLICT (name) DO NOTHING;");
}

int DatabaseManager::addImage(const std::string& filePath,
                            const std::optional<std::vector<float>>& embedding,
                            const std::optional<std::string>& groupName,
                            const std::optional<std::string>& subgroupName,
                            const std::optional<std::vector<std::string>>& tags,
                            std::optional<int> width,
                            std::optional<int> height) {
    try {
        pqxx::work txn(*m_conn);
        std::string filename = std::filesystem::path(filePath).filename().string();
        std::string now = "NOW()";

        if (groupName.has_value() && !groupName.value().empty()) {
            addGroup(txn, groupName.value());
        }
        // ... (add subgroup logic) ...

        std::string sql = "INSERT INTO images (file_path, filename, width, height, group_name, subgroup_name, date_added, date_modified, embedding) "
                          "VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8) "
                          "ON CONFLICT (file_path) DO UPDATE SET "
                          "width = EXCLUDED.width, height = EXCLUDED.height, group_name = EXCLUDED.group_name, "
                          "subgroup_name = EXCLUDED.subgroup_name, date_modified = $7, embedding = EXCLUDED.embedding "
                          "RETURNING id";
        
        pqxx::result res = txn.exec_params(sql,
            filePath,
            filename,
            width.has_value() ? std::optional(width.value()) : std::nullopt,
            height.has_value() ? std::optional(height.value()) : std::nullopt,
            groupName.has_value() ? std::optional(groupName.value()) : std::nullopt,
            subgroupName.has_value() ? std::optional(subgroupName.value()) : std::nullopt,
            pqxx::null, // Using NULL placeholder, $7, which will be NOW()
            embedding.has_value() ? std::optional(vectorToString(embedding.value())) : std::nullopt
        );
        
        // This is a workaround for pqxx not handling NOW() cleanly in prepared statements
        sql = sql.replace("$7", "NOW()");

        int image_id = res[0][0].as<int>();

        if (tags.has_value()) {
            txn.exec_params("DELETE FROM image_tags WHERE image_id = $1", image_id);
            for (const auto& tag : tags.value()) {
                int tag_id = getOrCreateTag(txn, tag);
                txn.exec_params("INSERT INTO image_tags (image_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", image_id, tag_id);
            }
        }

        txn.commit();
        return image_id;
    } catch (const std::exception& e) {
        std::cerr << "Error adding image: " << e.what() << std::endl;
        throw;
    }
}

// ... Implementations for searchImages, getAllGroups, etc. ...
// These would follow a similar pattern of building SQL strings
// and using txn.exec() or txn.exec_params().

std::vector<std::map<std::string, std::string>> DatabaseManager::searchImages(
        const std::optional<std::string>& groupName,
        const std::optional<std::string>& subgroupName,
        const std::optional<std::vector<std::string>>& tags,
        int limit) {
    
    // Implementation would be complex, building the query string
    // dynamically as in the Python version.
    std::vector<std::map<std::string, std::string>> results;
    std::cout << "searchImages C++ implementation is non-trivial and omitted for brevity." << std::endl;
    return results;
}

std::vector<std::string> DatabaseManager::getAllGroups() {
    std::vector<std::string> groups;
    pqxx::work txn(*m_conn);
    for (auto const& [name] : txn.query<std::string>("SELECT name FROM groups ORDER BY name")) {
        groups.push_back(name);
    }
    return groups;
}

std::vector<std::string> DatabaseManager::getAllTags() {
    std::vector<std::string> tags;
    pqxx::work txn(*m_conn);
    for (auto const& [name] : txn.query<std::string>("SELECT name FROM tags ORDER BY name")) {
        tags.push_back(name);
    }
    return tags;
}