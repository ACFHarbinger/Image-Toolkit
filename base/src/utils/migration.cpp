// ---------------------------------------------------------------------------
// base/src/utils/migration.cpp — legacy JSON → SQLCipher migration
// Phase 10 of Rust→C++ migration.
// Requires HAVE_SQLCIPHER; uses the same DEK derivation as base::secret.
// ---------------------------------------------------------------------------
#include "utils/migration.hpp"

#include <pybind11/pybind11.h>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace py = pybind11;
namespace fs = std::filesystem;

#ifdef HAVE_SQLCIPHER
#  include <sqlcipher/sqlite3.h>
#  include <nlohmann/json.hpp>
   using json = nlohmann::json;
#endif

namespace base::utils {

// ---------------------------------------------------------------------------
// Helpers shared with base::secret
// ---------------------------------------------------------------------------

#ifdef HAVE_SQLCIPHER

// Open an encrypted SQLCipher database with the given key.
static sqlite3* open_encrypted_db(const std::string& path, const std::string& key) {
    sqlite3* db = nullptr;
    if (sqlite3_open(path.c_str(), &db) != SQLITE_OK) return nullptr;
    std::string pragma = "PRAGMA key = '" + key + "';";
    if (sqlite3_exec(db, pragma.c_str(), nullptr, nullptr, nullptr) != SQLITE_OK) {
        sqlite3_close(db);
        return nullptr;
    }
    return db;
}

static bool exec_sql(sqlite3* db, const std::string& sql) {
    char* err = nullptr;
    int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &err);
    if (err) sqlite3_free(err);
    return rc == SQLITE_OK;
}

// Migrate a JSON vault file at json_path into an encrypted SQLCipher database.
// JSON format assumed: { "entries": [ { "id": "...", "key": "...", "value": "..." }, ... ] }
static bool migrate_json_to_sqlcipher(
    const std::string& json_path,
    const std::string& db_path,
    const std::string& key)
{
    std::ifstream f(json_path);
    if (!f) return false;
    json data;
    try { f >> data; } catch (...) { return false; }

    sqlite3* db = open_encrypted_db(db_path, key);
    if (!db) return false;

    // Create table structure matching VaultDB schema
    static const char* DDL =
        "CREATE TABLE IF NOT EXISTS vault_entries ("
        "  id    TEXT PRIMARY KEY,"
        "  key   TEXT NOT NULL,"
        "  value BLOB NOT NULL"
        ");"
        "CREATE TABLE IF NOT EXISTS vault_meta ("
        "  k TEXT PRIMARY KEY,"
        "  v TEXT NOT NULL"
        ");";

    if (!exec_sql(db, DDL)) { sqlite3_close(db); return false; }
    if (!exec_sql(db, "BEGIN TRANSACTION;")) { sqlite3_close(db); return false; }

    bool ok = true;

    auto migrate_array = [&](const json& arr, const std::string& key_field,
                              const std::string& val_field) {
        if (!arr.is_array()) return;
        for (const auto& entry : arr) {
            std::string id  = entry.value("id", "");
            std::string k   = entry.value(key_field, "");
            std::string v   = entry.value(val_field, "");
            if (id.empty() || k.empty()) continue;

            sqlite3_stmt* stmt = nullptr;
            const char* sql =
                "INSERT OR REPLACE INTO vault_entries(id, key, value) VALUES(?,?,?);";
            if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
                ok = false; continue;
            }
            sqlite3_bind_text(stmt, 1, id.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, k.c_str(),  -1, SQLITE_TRANSIENT);
            sqlite3_bind_blob(stmt, 3, v.data(), static_cast<int>(v.size()), SQLITE_TRANSIENT);
            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }
    };

    if (data.contains("entries"))
        migrate_array(data["entries"], "key", "value");
    else if (data.is_array())
        migrate_array(data, "key", "value");
    else if (data.is_object()) {
        // Flat {key: value} map
        for (auto& [k, v] : data.items()) {
            std::string val = v.is_string() ? v.get<std::string>() : v.dump();
            std::string id  = k;
            sqlite3_stmt* stmt = nullptr;
            const char* sql =
                "INSERT OR REPLACE INTO vault_entries(id, key, value) VALUES(?,?,?);";
            if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) == SQLITE_OK) {
                sqlite3_bind_text(stmt, 1, id.c_str(),  -1, SQLITE_TRANSIENT);
                sqlite3_bind_text(stmt, 2, k.c_str(),   -1, SQLITE_TRANSIENT);
                sqlite3_bind_blob(stmt, 3, val.data(), static_cast<int>(val.size()), SQLITE_TRANSIENT);
                sqlite3_step(stmt);
                sqlite3_finalize(stmt);
            }
        }
    }

    // Record migration metadata
    std::string ts = std::to_string(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
    exec_sql(db, "INSERT OR REPLACE INTO vault_meta(k,v) VALUES('migrated_from','" +
                 json_path + "');");
    exec_sql(db, "INSERT OR REPLACE INTO vault_meta(k,v) VALUES('migrated_at','" +
                 ts + "');");

    ok = ok && exec_sql(db, "COMMIT;");
    sqlite3_close(db);
    return ok;
}

#endif // HAVE_SQLCIPHER

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

bool run_legacy_migration(
    const std::string& username,
    const std::string& password,
    const std::string& json_path,
    const std::string& db_path)
{
#ifdef HAVE_SQLCIPHER
    // Derive key same way as VaultDB: "<username>:<password>"
    std::string key = username + ":" + password;
    fs::create_directories(fs::path(db_path).parent_path());
    return migrate_json_to_sqlcipher(json_path, db_path, key);
#else
    (void)username; (void)password; (void)json_path; (void)db_path;
    throw std::runtime_error(
        "run_legacy_migration: SQLCipher support not compiled in. "
        "Rebuild with -DHAVE_SQLCIPHER=1.");
#endif
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_migration(py::module_& m) {
    m.def("run_legacy_migration",
        [](const std::string& username, const std::string& password,
           const std::string& json_path, const std::string& db_path) -> bool {
            py::gil_scoped_release rel;
            return base::utils::run_legacy_migration(username, password, json_path, db_path);
        },
        py::arg("username"), py::arg("password"),
        py::arg("json_path"), py::arg("db_path"),
        R"doc(
            Migrate a legacy JSON vault file to a SQLCipher-encrypted database.

            Parameters
            ----------
                username  : str   Username used to derive the encryption key.
                password  : str   Password used to derive the encryption key.
                json_path : str   Path to the source JSON vault file.
                db_path   : str   Path for the destination SQLCipher database.

            Returns
            -------
                bool   True on success.

            Raises
            ------
                RuntimeError   If SQLCipher support was not compiled in.
        )doc");
}

} // namespace base::utils
