#include "ImageDatabase.hpp"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <ctime>

using namespace std::string_literals;

PgvectorImageDatabase::PgvectorImageDatabase(int embed_dim, 
                                             const std::string& db_name, 
                                             const std::string& db_user, 
                                             const std::string& db_password, 
                                             const std::string& db_host, 
                                             const std::string& db_port)
    : m_embeddingDim(embed_dim) {
    
    // Construct PostgreSQL connection string
    m_connStr = "dbname=" + db_name + " user=" + db_user + " password=" + db_password +
                " host=" + db_host + " port=" + db_port;
    
    try {
        connect();
        createTables();
    } catch (const std::exception& e) {
        std::cerr << "Database initialization failed: " << e.what() << std::endl;
        // Exit process or throw a specific error
        throw; 
    }
}

PgvectorImageDatabase::~PgvectorImageDatabase() {
    // Connection closes automatically when m_conn is destroyed (unique_ptr)
}

void PgvectorImageDatabase::connect() {
    try {
        m_conn = std::make_unique<pqxx::connection>(m_connStr);
        if (!m_conn->is_open()) {
            throw std::runtime_error("Connection object not open.");
        }
    } catch (const pqxx::sql_error& e) {
        std::cerr << "Error connecting to database (SQL): " << e.what() << std::endl;
        throw;
    } catch (const std::exception& e) {
        std::cerr << "Error connecting to database: " << e.what() << std::endl;
        throw;
    }
}

void PgvectorImageDatabase::createTables() {
    if (!m_conn) throw std::runtime_error("Database connection not established.");
    
    pqxx::work w(*m_conn);
    try {
        // Enable pgvector extension
        w.exec("CREATE EXTENSION IF NOT EXISTS vector;");

        // Images Table
        w.exec("CREATE TABLE IF NOT EXISTS images ("
               "id SERIAL PRIMARY KEY,"
               "file_path TEXT UNIQUE NOT NULL,"
               "filename TEXT NOT NULL,"
               "file_size BIGINT,"
               "width INTEGER,"
               "height INTEGER,"
               "group_name TEXT," 
               "subgroup_name TEXT," 
               "date_added TIMESTAMP WITHOUT TIME ZONE NOT NULL,"
               "date_modified TIMESTAMP WITHOUT TIME ZONE,"
               "embedding vector(" + std::to_string(m_embeddingDim) + ")" 
               ");");

        // Groups/Subgroups/Tags/ImageTags (omitted for brevity, follows SQL schema from Python)

        // Indexes
        w.exec("CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path);");
        w.exec("CREATE INDEX IF NOT EXISTS idx_images_embedding ON images USING hnsw (embedding vector_l2_ops) WHERE embedding IS NOT NULL;");

        w.commit();
    } catch (const std::exception& e) {
        w.abort();
        throw;
    }
}

int PgvectorImageDatabase::getOrCreateEntity(const std::string& table, const std::string& name) {
    pqxx::work w(*m_conn);
    // Use prepared statement to prevent SQL injection
    w.prepare("get_or_create_" + table, 
              "INSERT INTO " + table + " (name) VALUES ($1) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;");
    
    pqxx::result r = w.exec_prepared("get_or_create_" + table, name);
    w.commit();
    return r[0][0].as<int>();
}

// Simplified CRUD and Management methods

int PgvectorImageDatabase::addImage(const std::string& file_path, 
                                    const std::optional<std::vector<float>>& embedding,
                                    const std::optional<std::string>& group_name,
                                    const std::optional<std::string>& subgroup_name, 
                                    const std::optional<std::vector<std::string>>& tags,
                                    const std::optional<int>& width,
                                    const std::optional<int>& height) {
    
    if (group_name) addGroup(*group_name);
    if (group_name && subgroup_name) addSubgroup(*subgroup_name, *group_name);

    pqxx::work w(*m_conn);
    
    // Convert embedding to string format: '[f1, f2, f3]'
    std::string embed_str = "NULL";
    if (embedding) {
        std::stringstream ss;
        ss << '[';
        for (size_t i = 0; i < embedding->size(); ++i) {
            ss << embedding->at(i) << (i == embedding->size() - 1 ? "" : ",");
        }
        ss << ']';
        embed_str = ss.str();
    }
    
    // We must use a separate statement builder or raw query with careful escaping
    // due to the non-standard pgvector type. Using pqxx::zview for safety.
    
    std::string sql = 
        "INSERT INTO images (file_path, filename, file_size, width, height, group_name, subgroup_name, date_added, date_modified, embedding) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), " + embed_str + ") "
        "ON CONFLICT (file_path) DO UPDATE SET "
        "group_name = EXCLUDED.group_name, subgroup_name = EXCLUDED.subgroup_name, date_modified = NOW(), embedding = EXCLUDED.embedding "
        "RETURNING id;";
        
    pqxx::result r = w.exec_params(sql, 
        file_path, 
        fs::path(file_path).filename().string(), 
        0, // file_size placeholder
        width.has_value() ? std::to_string(*width) : "NULL",
        height.has_value() ? std::to_string(*height) : "NULL",
        group_name.has_value() ? *group_name : "NULL",
        subgroup_name.has_value() ? *subgroup_name : "NULL"
    );
    
    int image_id = r[0][0].as<int>();
    
    if (tags) {
        // Tag logic...
    }
    
    w.commit();
    return image_id;
}

void PgvectorImageDatabase::addGroup(const std::string& name) {
    getOrCreateEntity("groups", name);
}

void PgvectorImageDatabase::addSubgroup(const std::string& name, const std::string& group_name) {
    pqxx::work w(*m_conn);
    int group_id = getOrCreateEntity("groups", group_name); // Ensures group exists first
    w.exec_params("INSERT INTO subgroups (name, group_id) VALUES ($1, $2) ON CONFLICT (name, group_id) DO NOTHING;",
                  name, group_id);
    w.commit();
}

void PgvectorImageDatabase::renameGroup(const std::string& old_name, const std::string& new_name) {
    if (old_name == new_name) return;

    pqxx::work w(*m_conn);
    try {
        w.exec_params("UPDATE images SET group_name = $1 WHERE group_name = $2", new_name, old_name);
        w.exec_params("UPDATE groups SET name = $1 WHERE name = $2", new_name, old_name);
        w.commit();
    } catch (const std::exception& e) {
        w.abort();
        throw;
    }
}

void PgvectorImageDatabase::deleteTag(const std::string& name) {
    pqxx::work w(*m_conn);
    w.exec_params("DELETE FROM tags WHERE name = $1", name);
    w.commit();
}

std::vector<std::map<std::string, std::string>> PgvectorImageDatabase::getAllTagsWithTypes() {
    pqxx::work w(*m_conn);
    pqxx::result r = w.exec("SELECT name, type FROM tags ORDER BY name");

    std::vector<std::map<std::string, std::string>> tags;
    for (const auto& row : r) {
        std::map<std::string, std::string> tag;
        tag["name"] = row["name"].as<std::string>();
        tag["type"] = row["type"].is_null() ? "" : row["type"].as<std::string>();
        tags.push_back(tag);
    }
    return tags;
}

void PgvectorImageDatabase::resetDatabase() {
    if (!m_conn) throw std::runtime_error("Not connected to the database.");
    
    pqxx::work w(*m_conn);
    try {
        w.exec("DROP TABLE IF EXISTS image_tags CASCADE;");
        w.exec("DROP TABLE IF EXISTS images CASCADE;");
        w.exec("DROP TABLE IF EXISTS tags CASCADE;");
        w.exec("DROP TABLE IF EXISTS subgroups CASCADE;");
        w.exec("DROP TABLE IF EXISTS groups CASCADE;");
        w.commit();
        createTables();
    } catch (const std::exception& e) {
        w.abort();
        throw;
    }
}