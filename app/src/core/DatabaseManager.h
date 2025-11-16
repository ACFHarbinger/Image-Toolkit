#ifndef DATABASE_MANAGER_H
#define DATABASE_MANAGER_H

#include <string>
#include <vector>
#include <map>
#include <optional>
#include <pqxx/pqxx> // Requires libpqxx dependency

// Corresponds to PgvectorImageDatabase
class DatabaseManager {
public:
    DatabaseManager(int embedDim = 128,
                    const std::string& dbName = "",
                    const std::string& dbUser = "",
                    const std::string& dbPassword = "",
                    const std::string& dbHost = "",
                    const std::string& dbPort = "");
    ~DatabaseManager();

    void resetDatabase();
    
    // ... Other methods from PgvectorImageDatabase ...
    // For brevity, only a few key methods are fully translated.
    // The pattern would be the same for all.

    /**
     * @brief Adds an image and its vector embedding to the database.
     */
    int addImage(const std::string& filePath,
                 const std::optional<std::vector<float>>& embedding,
                 const std::optional<std::string>& groupName,
                 const std::optional<std::string>& subgroupName,
                 const std::optional<std::vector<std::string>>& tags,
                 std::optional<int> width,
                 std::optional<int> height);

    /**
     * @brief Searches for images based on various criteria.
     */
    std::vector<std::map<std::string, std::string>> searchImages(
        const std::optional<std::string>& groupName,
        const std::optional<std::string>& subgroupName,
        const std::optional<std::vector<std::string>>& tags,
        int limit = 10);

    std::vector<std::string> getAllGroups();
    std::vector<std::string> getAllTags();

private:
    void connect();
    void createTables();
    int getOrCreateTag(pqxx::work& txn, const std::string& name);
    void addGroup(pqxx::work& txn, const std::string& name);

    std::unique_ptr<pqxx::connection> m_conn;
    std::string m_connectionString;
    int m_embeddingDim;
};

#endif // DATABASE_MANAGER_H