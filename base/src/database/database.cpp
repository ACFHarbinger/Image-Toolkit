// ---------------------------------------------------------------------------
// base/src/database/database.cpp
//
// Unified Library Database engine (Phase DB, DB.2).
//
// A session-keyed SQLCipher connection: the Argon2id KDF runs exactly once,
// in the constructor, and the keyed sqlite3* handle lives for the object's
// lifetime. Generic parameterized SQL primitives (query/execute/executemany
// + transactions) back the Python DAL in backend/src/database/unified/;
// embeddings storage and brute-force cosine knn back DB.7 (HNSW later).
//
// Deliberately separate from base.secret (Vault-only, untouchable).
// See moon/roadmaps/unified_database.md §DB.2.
// ---------------------------------------------------------------------------

#include "database/database.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

// ===========================================================================
// FULL IMPLEMENTATION (SQLCipher + libsodium present)
// ===========================================================================

#ifdef HAVE_SQLCIPHER

#include <sqlite3.h>
extern "C" {
    int sqlite3_key(sqlite3 *db, const void *pKey, int nKey);
}
#include <sodium.h>
#include <argon2.h>

#include <algorithm>
#include <cmath>
#include <filesystem>

namespace fs = std::filesystem;

namespace base::database {

namespace {

constexpr int KEY_BYTES = 32;   // AES-256
constexpr int OPSLIMIT  = 2;    // crypto_pwhash_OPSLIMIT_INTERACTIVE
constexpr int MEM_KB    = 19456; // 19 MB — matches base.secret's parameters
                                 // (same password+salt must derive the same key)

// Derive a 32-byte key from password + salt. Identical construction to
// base.secret::derive_key so existing credentials work unchanged: the salt
// string is SHA-256'd to exactly 32 bytes, then Argon2id produces the DEK.
std::vector<uint8_t> derive_key(const std::string& password,
                                const std::string& salt_str) {
    std::vector<uint8_t> key(KEY_BYTES, 0);
    std::vector<uint8_t> salt(32, 0);
    crypto_hash_sha256(salt.data(),
                       reinterpret_cast<const unsigned char*>(salt_str.c_str()),
                       salt_str.size());
    int rc = argon2id_hash_raw(OPSLIMIT, MEM_KB, 1,
                               password.c_str(), password.size(),
                               salt.data(), salt.size(),
                               key.data(), key.size());
    if (rc != ARGON2_OK)
        throw std::runtime_error("base.database: Argon2id key derivation failed");
    return key;
}

// Bind one Python value to a prepared statement (1-based index).
void bind_value(sqlite3_stmt* stmt, int idx, const py::handle& value) {
    if (value.is_none()) {
        sqlite3_bind_null(stmt, idx);
    } else if (py::isinstance<py::bool_>(value)) {
        sqlite3_bind_int(stmt, idx, value.cast<bool>() ? 1 : 0);
    } else if (py::isinstance<py::int_>(value)) {
        sqlite3_bind_int64(stmt, idx, value.cast<sqlite3_int64>());
    } else if (py::isinstance<py::float_>(value)) {
        sqlite3_bind_double(stmt, idx, value.cast<double>());
    } else if (py::isinstance<py::str>(value)) {
        auto s = value.cast<std::string>();
        sqlite3_bind_text(stmt, idx, s.c_str(),
                          static_cast<int>(s.size()), SQLITE_TRANSIENT);
    } else if (py::isinstance<py::bytes>(value) ||
               py::isinstance<py::bytearray>(value)) {
        py::buffer_info info = py::buffer(value.cast<py::buffer>()).request();
        sqlite3_bind_blob(stmt, idx, info.ptr,
                          static_cast<int>(info.size), SQLITE_TRANSIENT);
    } else {
        throw py::type_error(
            "base.database: unsupported parameter type at index " +
            std::to_string(idx) + " (use None/bool/int/float/str/bytes)");
    }
}

// Convert the current row of a stepped statement to a Python tuple.
py::tuple row_to_tuple(sqlite3_stmt* stmt) {
    int n = sqlite3_column_count(stmt);
    py::tuple row(n);
    for (int i = 0; i < n; ++i) {
        switch (sqlite3_column_type(stmt, i)) {
            case SQLITE_NULL:
                row[i] = py::none();
                break;
            case SQLITE_INTEGER:
                row[i] = py::int_(static_cast<long long>(
                    sqlite3_column_int64(stmt, i)));
                break;
            case SQLITE_FLOAT:
                row[i] = py::float_(sqlite3_column_double(stmt, i));
                break;
            case SQLITE_BLOB: {
                const void* blob = sqlite3_column_blob(stmt, i);
                int size = sqlite3_column_bytes(stmt, i);
                row[i] = py::bytes(static_cast<const char*>(blob), size);
                break;
            }
            case SQLITE_TEXT:
            default: {
                const unsigned char* text = sqlite3_column_text(stmt, i);
                int size = sqlite3_column_bytes(stmt, i);
                row[i] = py::str(reinterpret_cast<const char*>(text), size);
                break;
            }
        }
    }
    return row;
}

// RAII prepared statement.
struct Stmt {
    sqlite3_stmt* stmt{nullptr};
    Stmt(sqlite3* db, const std::string& sql) {
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK)
            throw std::runtime_error(std::string("base.database: prepare failed: ")
                                     + sqlite3_errmsg(db));
    }
    ~Stmt() { if (stmt) sqlite3_finalize(stmt); }
    Stmt(const Stmt&) = delete;
    Stmt& operator=(const Stmt&) = delete;
};

} // namespace

class Database {
public:
    Database(std::string db_path, std::string password, std::string salt)
        : db_path_(std::move(db_path)) {
        std::vector<uint8_t> key;
        {
            // KDF + open are pure C++ — release the GIL (19 MB Argon2id pass).
            py::gil_scoped_release release;
            key = derive_key(password, salt);
        }

        if (sqlite3_open(db_path_.c_str(), &db_) != SQLITE_OK) {
            std::string err = db_ ? sqlite3_errmsg(db_) : "out of memory";
            if (db_) { sqlite3_close(db_); db_ = nullptr; }
            sodium_memzero(key.data(), key.size());
            throw std::runtime_error("base.database: sqlite3_open failed: " + err);
        }
        if (sqlite3_key(db_, key.data(), static_cast<int>(key.size())) != SQLITE_OK) {
            sqlite3_close(db_); db_ = nullptr;
            sodium_memzero(key.data(), key.size());
            throw std::runtime_error("base.database: sqlite3_key failed");
        }
        sodium_memzero(key.data(), key.size());

        // Verify the key actually decrypts the file (sqlite3_key never fails
        // on a wrong key; the first real read does).
        char* errmsg = nullptr;
        if (sqlite3_exec(db_, "SELECT count(*) FROM sqlite_master;",
                         nullptr, nullptr, &errmsg) != SQLITE_OK) {
            std::string err = errmsg ? errmsg : "unknown";
            sqlite3_free(errmsg);
            sqlite3_close(db_); db_ = nullptr;
            throw std::runtime_error(
                "base.database: cannot read database — wrong password/salt "
                "or corrupted file (" + err + ")");
        }

        exec_or_throw("PRAGMA foreign_keys = ON;");
        exec_or_throw("PRAGMA journal_mode = WAL;");
        exec_or_throw("PRAGMA busy_timeout = 5000;");
    }

    ~Database() { close_internal(); }
    Database(const Database&) = delete;
    Database& operator=(const Database&) = delete;

    void close() {
        std::lock_guard<std::mutex> lock(mutex_);
        close_internal();
    }

    bool is_open() const { return db_ != nullptr; }

    // ---- generic SQL primitives -------------------------------------

    py::list query(const std::string& sql, py::sequence params) {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        Stmt s(db_, sql);
        bind_all(s.stmt, params);
        py::list rows;
        while (true) {
            int rc = sqlite3_step(s.stmt);
            if (rc == SQLITE_ROW) {
                rows.append(row_to_tuple(s.stmt));
            } else if (rc == SQLITE_DONE) {
                break;
            } else {
                throw std::runtime_error(std::string("base.database: step failed: ")
                                         + sqlite3_errmsg(db_));
            }
        }
        return rows;
    }

    long long execute(const std::string& sql, py::sequence params) {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        Stmt s(db_, sql);
        bind_all(s.stmt, params);
        step_to_done(s.stmt);
        return sqlite3_changes(db_);
    }

    void executemany(const std::string& sql, py::sequence rows) {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        bool own_txn = sqlite3_get_autocommit(db_) != 0;
        if (own_txn) exec_or_throw("BEGIN IMMEDIATE;");
        try {
            Stmt s(db_, sql);
            for (const auto& row : rows) {
                bind_all(s.stmt, row.cast<py::sequence>());
                step_to_done(s.stmt);
                sqlite3_reset(s.stmt);
                sqlite3_clear_bindings(s.stmt);
            }
        } catch (...) {
            if (own_txn) sqlite3_exec(db_, "ROLLBACK;", nullptr, nullptr, nullptr);
            throw;
        }
        if (own_txn) exec_or_throw("COMMIT;");
    }

    long long last_insert_rowid() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        return sqlite3_last_insert_rowid(db_);
    }

    void begin()    { locked_exec("BEGIN IMMEDIATE;"); }
    void commit()   { locked_exec("COMMIT;"); }
    void rollback() { locked_exec("ROLLBACK;"); }

    bool in_transaction() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        return sqlite3_get_autocommit(db_) == 0;
    }

    // ---- schema & maintenance ---------------------------------------

    void apply_ddl(const std::string& sql) { locked_exec(sql); }

    int schema_version() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        // schema_meta may not exist yet on a fresh file.
        Stmt probe(db_,
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='table' AND name='schema_meta';");
        if (sqlite3_step(probe.stmt) != SQLITE_ROW ||
            sqlite3_column_int(probe.stmt, 0) == 0)
            return 0;
        Stmt s(db_, "SELECT value FROM schema_meta WHERE key='schema_version';");
        if (sqlite3_step(s.stmt) == SQLITE_ROW)
            return std::atoi(reinterpret_cast<const char*>(
                sqlite3_column_text(s.stmt, 0)));
        return 0;
    }

    bool has_fts5() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        Stmt s(db_, "PRAGMA compile_options;");
        while (sqlite3_step(s.stmt) == SQLITE_ROW) {
            const char* opt = reinterpret_cast<const char*>(
                sqlite3_column_text(s.stmt, 0));
            if (opt && std::strstr(opt, "ENABLE_FTS5") != nullptr)
                return true;
        }
        return false;
    }

    void vacuum()  { locked_exec("VACUUM;"); }
    void reindex() { locked_exec("REINDEX;"); }

    bool integrity_check() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        Stmt s(db_, "PRAGMA integrity_check;");
        if (sqlite3_step(s.stmt) == SQLITE_ROW) {
            const char* result = reinterpret_cast<const char*>(
                sqlite3_column_text(s.stmt, 0));
            return result && std::strcmp(result, "ok") == 0;
        }
        return false;
    }

    py::dict statistics() {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        py::dict out;
        py::dict tables;
        Stmt list(db_,
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' "
            "ORDER BY name;");
        while (sqlite3_step(list.stmt) == SQLITE_ROW) {
            std::string name = reinterpret_cast<const char*>(
                sqlite3_column_text(list.stmt, 0));
            Stmt count(db_, "SELECT count(*) FROM \"" + name + "\";");
            long long n = 0;
            if (sqlite3_step(count.stmt) == SQLITE_ROW)
                n = sqlite3_column_int64(count.stmt, 0);
            tables[py::str(name)] = py::int_(n);
        }
        out["tables"] = tables;
        std::error_code ec;
        auto size = fs::file_size(db_path_, ec);
        out["file_bytes"] = py::int_(ec ? 0 : static_cast<long long>(size));
        out["schema_version"] = py::int_(schema_version_unlocked());
        return out;
    }

    // ---- embeddings + knn (DB.7 hot path; brute-force until HNSW) ----

    void upsert_embedding(const std::string& owner_type,
                          const std::string& owner_id,
                          const std::string& model,
                          py::array_t<float, py::array::c_style |
                                             py::array::forcecast> vec) {
        auto buf = vec.request();
        if (buf.ndim != 1 || buf.size == 0)
            throw py::value_error(
                "base.database: embedding must be a non-empty 1-D float32 array");
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        Stmt s(db_,
            "INSERT INTO embeddings (owner_type, owner_id, model, dim, vector) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(owner_type, owner_id, model) DO UPDATE SET "
            "dim=excluded.dim, vector=excluded.vector;");
        sqlite3_bind_text(s.stmt, 1, owner_type.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s.stmt, 2, owner_id.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s.stmt, 3, model.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_int (s.stmt, 4, static_cast<int>(buf.size));
        sqlite3_bind_blob(s.stmt, 5, buf.ptr,
                          static_cast<int>(buf.size * sizeof(float)),
                          SQLITE_TRANSIENT);
        step_to_done(s.stmt);
    }

    // Brute-force cosine knn over embeddings(owner_type, model).
    // prefilter_sql, when non-empty, must be a SELECT whose FIRST column
    // yields the allowed owner_ids (e.g. built by search_repo from the
    // structured filters); other rows are excluded before scoring.
    // Returns [(owner_id, score), ...] sorted by descending score.
    py::list knn(const std::string& owner_type,
                 const std::string& model,
                 py::array_t<float, py::array::c_style |
                                    py::array::forcecast> query,
                 int top_k,
                 const std::string& prefilter_sql = "") {
        auto qbuf = query.request();
        if (qbuf.ndim != 1 || qbuf.size == 0)
            throw py::value_error(
                "base.database: query must be a non-empty 1-D float32 array");
        const auto* q = static_cast<const float*>(qbuf.ptr);
        const int dim = static_cast<int>(qbuf.size);
        if (top_k <= 0)
            return py::list();

        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();

        std::string sql =
            "SELECT e.owner_id, e.dim, e.vector FROM embeddings e "
            "WHERE e.owner_type = ? AND e.model = ?";
        if (!prefilter_sql.empty())
            sql += " AND e.owner_id IN (SELECT * FROM (" + prefilter_sql + "))";
        Stmt s(db_, sql);
        sqlite3_bind_text(s.stmt, 1, owner_type.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(s.stmt, 2, model.c_str(), -1, SQLITE_TRANSIENT);

        struct Hit { std::string id; float score; };
        std::vector<Hit> hits;

        float qnorm = 0.f;
        for (int i = 0; i < dim; ++i) qnorm += q[i] * q[i];
        qnorm = std::sqrt(qnorm);

        while (sqlite3_step(s.stmt) == SQLITE_ROW) {
            if (sqlite3_column_int(s.stmt, 1) != dim) continue;
            const auto* v = static_cast<const float*>(
                sqlite3_column_blob(s.stmt, 2));
            if (!v) continue;
            float dot = 0.f, vnorm = 0.f;
            for (int i = 0; i < dim; ++i) {
                dot += q[i] * v[i];
                vnorm += v[i] * v[i];
            }
            float denom = qnorm * std::sqrt(vnorm);
            float score = denom > 1e-10f ? dot / denom : 0.f;
            hits.push_back({reinterpret_cast<const char*>(
                                sqlite3_column_text(s.stmt, 0)),
                            score});
        }

        size_t k = std::min<size_t>(top_k, hits.size());
        std::partial_sort(hits.begin(), hits.begin() + k, hits.end(),
                          [](const Hit& a, const Hit& b) {
                              return a.score > b.score;
                          });
        hits.resize(k);

        py::list out;
        for (const auto& h : hits)
            out.append(py::make_tuple(h.id, h.score));
        return out;
    }

private:
    sqlite3* db_{nullptr};
    std::string db_path_;
    std::mutex mutex_;

    void ensure_open() const {
        if (!db_)
            throw std::runtime_error("base.database: database is closed");
    }

    void close_internal() {
        if (db_) {
            sqlite3_close(db_);
            db_ = nullptr;
        }
    }

    void exec_or_throw(const std::string& sql) {
        char* errmsg = nullptr;
        if (sqlite3_exec(db_, sql.c_str(), nullptr, nullptr, &errmsg)
                != SQLITE_OK) {
            std::string err = errmsg ? errmsg : "unknown";
            sqlite3_free(errmsg);
            throw std::runtime_error("base.database: exec failed: " + err);
        }
    }

    void locked_exec(const std::string& sql) {
        std::lock_guard<std::mutex> lock(mutex_);
        ensure_open();
        exec_or_throw(sql);
    }

    int schema_version_unlocked() {
        Stmt probe(db_,
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='table' AND name='schema_meta';");
        if (sqlite3_step(probe.stmt) != SQLITE_ROW ||
            sqlite3_column_int(probe.stmt, 0) == 0)
            return 0;
        Stmt s(db_, "SELECT value FROM schema_meta WHERE key='schema_version';");
        if (sqlite3_step(s.stmt) == SQLITE_ROW)
            return std::atoi(reinterpret_cast<const char*>(
                sqlite3_column_text(s.stmt, 0)));
        return 0;
    }

    static void bind_all(sqlite3_stmt* stmt, const py::sequence& params) {
        int expected = sqlite3_bind_parameter_count(stmt);
        int given = static_cast<int>(py::len(params));
        if (given != expected)
            throw py::value_error(
                "base.database: statement expects " + std::to_string(expected) +
                " parameters, got " + std::to_string(given));
        int idx = 1;
        for (const auto& value : params)
            bind_value(stmt, idx++, value);
    }

    void step_to_done(sqlite3_stmt* stmt) {
        int rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE && rc != SQLITE_ROW)
            throw std::runtime_error(std::string("base.database: step failed: ")
                                     + sqlite3_errmsg(db_));
    }
};

} // namespace base::database

// ===========================================================================
// pybind11 registration
// ===========================================================================

void register_database(py::module_& m) {
    using base::database::Database;

    m.doc() =
        "Unified Library Database engine (SQLCipher, session-keyed). "
        "Phase DB — replaces base.secret listings CRUD and the PostgreSQL "
        "image index. Argon2id runs once per Database instance.";

    py::class_<Database>(m, "Database")
        .def(py::init<std::string, std::string, std::string>(),
             py::arg("db_path"), py::arg("password"), py::arg("salt"),
             "Open (creating if absent) an encrypted database. Runs the "
             "Argon2id KDF once; raises RuntimeError on a wrong password.")
        .def("close", &Database::close,
             "Close the connection. Further calls raise RuntimeError.")
        .def_property_readonly("is_open", &Database::is_open)
        .def("query", &Database::query,
             py::arg("sql"), py::arg("params") = py::tuple(),
             "Run a SELECT; returns a list of row tuples "
             "(None/int/float/str/bytes).")
        .def("execute", &Database::execute,
             py::arg("sql"), py::arg("params") = py::tuple(),
             "Run a single statement; returns the affected row count.")
        .def("executemany", &Database::executemany,
             py::arg("sql"), py::arg("rows"),
             "Run one statement for each parameter row inside a single "
             "transaction (unless one is already open).")
        .def("last_insert_rowid", &Database::last_insert_rowid)
        .def("begin", &Database::begin)
        .def("commit", &Database::commit)
        .def("rollback", &Database::rollback)
        .def_property_readonly("in_transaction", &Database::in_transaction)
        .def("apply_ddl", &Database::apply_ddl, py::arg("sql"),
             "Execute a multi-statement DDL script.")
        .def("schema_version", &Database::schema_version,
             "Value of schema_meta.schema_version, or 0 when unset.")
        .def("has_fts5", &Database::has_fts5,
             "Whether the linked SQLCipher was compiled with FTS5.")
        .def("vacuum", &Database::vacuum)
        .def("reindex", &Database::reindex)
        .def("integrity_check", &Database::integrity_check,
             "PRAGMA integrity_check == 'ok'.")
        .def("statistics", &Database::statistics,
             "{'tables': {name: rowcount}, 'file_bytes': int, "
             "'schema_version': int}")
        .def("upsert_embedding", &Database::upsert_embedding,
             py::arg("owner_type"), py::arg("owner_id"), py::arg("model"),
             py::arg("vector"),
             "Insert or replace a float32 embedding.")
        .def("knn", &Database::knn,
             py::arg("owner_type"), py::arg("model"), py::arg("query"),
             py::arg("top_k") = 10, py::arg("prefilter_sql") = "",
             "Cosine knn over embeddings. prefilter_sql: optional SELECT "
             "whose first column restricts the candidate owner_ids. Returns "
             "[(owner_id, score), ...] by descending score.")
        .def("__enter__", [](Database& self) -> Database& { return self; })
        .def("__exit__", [](Database& self, py::object, py::object,
                            py::object) { self.close(); return false; });
}

// ===========================================================================
// STUB (SQLCipher / libsodium not available at build time)
// ===========================================================================

#else // !HAVE_SQLCIPHER

void register_database(py::module_& m) {
    m.doc() =
        "Unified Library Database engine — built WITHOUT SQLCipher; "
        "constructing Database raises.";
    struct DatabaseStub {};
    py::class_<DatabaseStub>(m, "Database")
        .def(py::init([](const std::string&, const std::string&,
                         const std::string&) -> DatabaseStub {
                 throw py::type_error(
                     "base.database.Database: base was built without "
                     "SQLCipher/libsodium. Rebuild with both available "
                     "(see build env notes).");
             }),
             py::arg("db_path"), py::arg("password"), py::arg("salt"));
}

#endif // HAVE_SQLCIPHER
