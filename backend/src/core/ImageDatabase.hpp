#pragma once

#include <string>
#include <vector>
#include <map>
#include <optional>
#include <pqxx/pqxx>

class PgvectorImageDatabase {
public:
    PgvectorImageDatabase(int embed_dim, 
                          const std::string& db_name, 
                          const std::string& db_user, 
                          const std::string& db_password, 
                          const std::string& db_host, 
                          const std::string& db_port);

    ~PgvectorImageDatabase();
    
    // Schema & Connection
    void connect();
    void createTables();
    void resetDatabase();
    
    // CRUD Operations
    int addImage(const std::string& file_path, 
                 const std::optional<std::vector<float>>& embedding,
                 const std::optional<std::string>& group_name,
                 const std::optional<std::string>& subgroup_name, 
                 const std::optional<std::vector<std::string>>& tags,
                 const std::optional<int>& width,
                 const std::optional<int>& height);
                 
    std::map<std::string, std::string> getImageByPath(const std::string& file_path);
    std::vector<std::map<std::string, std::string>> searchImages(/* ... arguments ... */);
    
    // Metadata Management
    void addGroup(const std::string& name);
    void addSubgroup(const std::string& name, const std::string& group_name);
    void addTag(const std::string& name, const std::optional<std::string>& type);
    
    // Renaming/Deletion/Listing methods...
    // (Declarations for rename_group, delete_tag, get_all_tags_with_types, etc.)
    void renameGroup(const std::string& old_name, const std::string& new_name);
    void deleteTag(const std::string& name);
    std::vector<std::map<std::string, std::string>> getAllTagsWithTypes();
    
private:
    std::unique_ptr<pqxx::connection> m_conn;
    int m_embeddingDim;
    std::string m_connStr;

    int getOrCreateEntity(const std::string& table, const std::string& name);
    int getOrCreateTag(const std::string& name);
};