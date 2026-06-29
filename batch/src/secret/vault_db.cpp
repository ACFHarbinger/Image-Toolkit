// ---------------------------------------------------------------------------
// batch/src/secret/vault_db.cpp
//
// Encrypted vector database operations.
//
// When HAVE_SQLCIPHER is defined (SQLCipher + libsodium both found):
//   - Full implementation: Argon2id KDF, AES-256 SQLCipher, CRUD,
//     linear-scan cosine search, Apache Arrow C Data Interface export.
//
// Otherwise:
//   - Stubs that raise py::type_error so the Python NativeExt shim
//     falls back to the Rust `base` module.
//
// Phase 4 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 4
// ---------------------------------------------------------------------------

#include "batch/secret/vault_db.hpp"
#include "batch/secret/locked_secret.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

// ===========================================================================
// FULL IMPLEMENTATION (SQLCipher + libsodium present)
// ===========================================================================

#ifdef HAVE_SQLCIPHER

#include <sqlcipher/sqlite3.h>
#include <sodium.h>

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <sstream>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Apache Arrow C Data Interface — minimal inline definitions
// (avoids nanoarrow dependency; sufficient for id+metadata export)
// ---------------------------------------------------------------------------

struct ArrowSchema {
    const char* format{nullptr};
    const char* name{nullptr};
    const char* metadata{nullptr};
    int64_t     flags{0};
    int64_t     n_children{0};
    ArrowSchema** children{nullptr};
    ArrowSchema*  dictionary{nullptr};
    void (*release)(ArrowSchema*){nullptr};
    void*         private_data{nullptr};
};

struct ArrowArray {
    int64_t  length{0};
    int64_t  null_count{0};
    int64_t  offset{0};
    int64_t  n_buffers{0};
    int64_t  n_children{0};
    const void** buffers{nullptr};
    ArrowArray** children{nullptr};
    ArrowArray*  dictionary{nullptr};
    void (*release)(ArrowArray*){nullptr};
    void*         private_data{nullptr};
};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

namespace batch::secret {

static constexpr int SALT_BYTES     = 32;
static constexpr int KEY_BYTES      = 32;   // AES-256
static constexpr int OPSLIMIT       = 3;    // crypto_pwhash_OPSLIMIT_INTERACTIVE
static constexpr int MEMLIMIT       = 1 << 26; // 64 MiB

// RAII wrapper for SQLite3 db handle
struct DbHandle {
    sqlite3* db{nullptr};
    ~DbHandle() { if (db) sqlite3_close(db); }
};

// Derive 32-byte key from password + salt using Argon2id
static std::vector<uint8_t> derive_key(const std::string& password,
                                        const uint8_t*     salt)
{
    std::vector<uint8_t> key(KEY_BYTES, 0);
    if (crypto_pwhash(key.data(), KEY_BYTES,
                      password.c_str(), password.size(),
                      salt,
                      OPSLIMIT, MEMLIMIT,
                      crypto_pwhash_ALG_ARGON2ID13) != 0)
        throw std::runtime_error("batch::secret: Argon2id key derivation out of memory");
    return key;
}

// Load or generate the salt sidecar file ({db_path}.salt)
static std::vector<uint8_t> load_or_create_salt(const std::string& db_path) {
    std::string salt_path = db_path + ".salt";
    std::vector<uint8_t> salt(SALT_BYTES);
    if (fs::exists(salt_path)) {
        std::ifstream f(salt_path, std::ios::binary);
        f.read(reinterpret_cast<char*>(salt.data()), SALT_BYTES);
        if (!f || static_cast<int>(f.gcount()) != SALT_BYTES)
            throw std::runtime_error("batch::secret: corrupt salt file: " + salt_path);
    } else {
        randombytes_buf(salt.data(), SALT_BYTES);
        if (fs::path(db_path).has_parent_path())
            fs::create_directories(fs::path(db_path).parent_path());
        std::ofstream f(salt_path, std::ios::binary);
        f.write(reinterpret_cast<const char*>(salt.data()), SALT_BYTES);
    }
    return salt;
}

// Open (or create) an SQLCipher database, apply the DEK
static DbHandle open_db(const std::string& db_path, const std::string& password) {
    auto salt = load_or_create_salt(db_path);
    auto key  = derive_key(password, salt.data());

    DbHandle h;
    if (sqlite3_open(db_path.c_str(), &h.db) != SQLITE_OK)
        throw std::runtime_error("batch::secret: sqlite3_open failed: " + db_path);

    // Pass the raw 32-byte key via PRAGMA key using blob literal
    std::ostringstream pragma;
    pragma << "PRAGMA key = \"x'";
    for (auto b : key) { pragma << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b); }
    pragma << "'\";";
    sodium_memzero(key.data(), key.size());

    char* errmsg = nullptr;
    if (sqlite3_exec(h.db, pragma.str().c_str(), nullptr, nullptr, &errmsg) != SQLITE_OK) {
        std::string err = errmsg ? errmsg : "unknown";
        sqlite3_free(errmsg);
        throw std::runtime_error("batch::secret: PRAGMA key failed: " + err);
    }

    // Initialize schema
    const char* schema = R"sql(
        CREATE TABLE IF NOT EXISTS listings (
            id          TEXT PRIMARY KEY,
            embedding   BLOB NOT NULL,
            dim         INTEGER NOT NULL,
            metadata    TEXT NOT NULL DEFAULT '{}'
        );
    )sql";
    if (sqlite3_exec(h.db, schema, nullptr, nullptr, &errmsg) != SQLITE_OK) {
        std::string err = errmsg ? errmsg : "unknown";
        sqlite3_free(errmsg);
        throw std::runtime_error("batch::secret: schema init failed: " + err);
    }
    return h;
}

// Cosine similarity between two float32 vectors
static float cosine_sim(const float* a, const float* b, int dim) {
    float dot = 0.f, na = 0.f, nb = 0.f;
    for (int i = 0; i < dim; ++i) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
    float denom = std::sqrt(na) * std::sqrt(nb);
    return denom > 1e-10f ? dot / denom : 0.f;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void insert_listing_secure(
    const std::string&  db_path,
    const std::string&  password,
    const std::string&  listing_id,
    py::array_t<float>  embedding,
    const std::string&  metadata_json)
{
    auto buf  = embedding.request();
    if (buf.ndim != 1)
        throw py::value_error("batch::secret: embedding must be 1-D float32 array");
    int dim = static_cast<int>(buf.size);
    const float* data = static_cast<const float*>(buf.ptr);

    auto h = open_db(db_path, password);

    const char* sql = R"sql(
        INSERT INTO listings (id, embedding, dim, metadata)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET embedding=excluded.embedding,
                                      dim=excluded.dim,
                                      metadata=excluded.metadata;
    )sql";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(h.db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        throw std::runtime_error("batch::secret: prepare INSERT failed");

    sqlite3_bind_text(stmt, 1, listing_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_blob(stmt, 2, data, dim * sizeof(float), SQLITE_STATIC);
    sqlite3_bind_int (stmt, 3, dim);
    sqlite3_bind_text(stmt, 4, metadata_json.c_str(), -1, SQLITE_STATIC);

    int rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    if (rc != SQLITE_DONE)
        throw std::runtime_error("batch::secret: INSERT failed: " +
                                  std::string(sqlite3_errmsg(h.db)));
}

py::list hybrid_search_secure(
    const std::string& db_path,
    const std::string& password,
    py::array_t<float> query_embedding,
    const std::string& /*bm25_query*/,
    int                top_k)
{
    auto buf = query_embedding.request();
    if (buf.ndim != 1)
        throw py::value_error("batch::secret: query_embedding must be 1-D float32 array");
    int dim = static_cast<int>(buf.size);
    const float* qdata = static_cast<const float*>(buf.ptr);

    auto h = open_db(db_path, password);

    sqlite3_stmt* stmt = nullptr;
    const char* sql = "SELECT id, embedding, dim, metadata FROM listings;";
    if (sqlite3_prepare_v2(h.db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        throw std::runtime_error("batch::secret: prepare SELECT failed");

    struct Hit { std::string id; float score; std::string metadata; };
    std::vector<Hit> hits;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        std::string id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        int row_dim    = sqlite3_column_int(stmt, 2);
        if (row_dim != dim) continue;
        const float* edata = static_cast<const float*>(sqlite3_column_blob(stmt, 1));
        std::string meta   = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3));
        float score = cosine_sim(qdata, edata, dim);
        hits.push_back({std::move(id), score, std::move(meta)});
    }
    sqlite3_finalize(stmt);

    std::partial_sort(hits.begin(),
                      hits.begin() + std::min(top_k, static_cast<int>(hits.size())),
                      hits.end(),
                      [](const Hit& a, const Hit& b){ return a.score > b.score; });
    if (static_cast<int>(hits.size()) > top_k) hits.resize(top_k);

    py::list result;
    for (const auto& h2 : hits)
        result.append(py::make_tuple(h2.id, h2.score, h2.metadata));
    return result;
}

py::list fetch_all_listings_secure(
    const std::string& db_path,
    const std::string& password)
{
    auto h = open_db(db_path, password);

    sqlite3_stmt* stmt = nullptr;
    const char* sql = "SELECT id, metadata FROM listings;";
    if (sqlite3_prepare_v2(h.db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        throw std::runtime_error("batch::secret: prepare SELECT failed");

    py::list result;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        std::string id   = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        std::string meta = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        result.append(py::make_tuple(id, meta));
    }
    sqlite3_finalize(stmt);
    return result;
}

bool delete_listing_secure(
    const std::string& db_path,
    const std::string& password,
    const std::string& listing_id)
{
    auto h = open_db(db_path, password);

    sqlite3_stmt* stmt = nullptr;
    const char* sql = "DELETE FROM listings WHERE id = ?;";
    if (sqlite3_prepare_v2(h.db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        throw std::runtime_error("batch::secret: prepare DELETE failed");
    sqlite3_bind_text(stmt, 1, listing_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_step(stmt);
    int changed = sqlite3_changes(h.db);
    sqlite3_finalize(stmt);
    return changed > 0;
}

// Arrow export: id (utf8) + metadata (utf8) columns only.
// Returns (array_ptr: int, schema_ptr: int) as a Python tuple.
// The caller is responsible for releasing via the release callback.
py::tuple fetch_listings_as_arrow_pointers(
    const std::string& db_path,
    const std::string& password)
{
    auto hdl = open_db(db_path, password);

    sqlite3_stmt* stmt = nullptr;
    const char* sql = "SELECT id, metadata FROM listings;";
    if (sqlite3_prepare_v2(hdl.db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        throw std::runtime_error("batch::secret: prepare SELECT (Arrow) failed");

    // Buffer all rows
    std::vector<std::string> ids, metas;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        ids.push_back(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
        metas.push_back(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1)));
    }
    sqlite3_finalize(stmt);

    int64_t n = static_cast<int64_t>(ids.size());

    // Build a minimal Arrow array for the "id" utf8 column.
    // Layout: null bitmap (nullptr = no nulls), offsets (int32), data (utf8 bytes).
    // We heap-allocate everything and encode the pointer in private_data for the
    // release callback to free.

    struct ColData {
        std::vector<int32_t> offsets;
        std::string          flat_buf;
    };

    auto build_col = [&](const std::vector<std::string>& strs) {
        ColData col;
        col.offsets.reserve(strs.size() + 1);
        col.offsets.push_back(0);
        for (const auto& s : strs) {
            col.flat_buf += s;
            col.offsets.push_back(static_cast<int32_t>(col.flat_buf.size()));
        }
        return col;
    };

    auto id_col   = new ColData(build_col(ids));
    auto meta_col = new ColData(build_col(metas));

    // ArrowArray for id column
    auto* arr_id              = new ArrowArray();
    arr_id->length            = n;
    arr_id->null_count        = 0;
    arr_id->n_buffers         = 3;
    auto** bufs_id            = new const void*[3];
    bufs_id[0]                = nullptr;  // no null bitmap
    bufs_id[1]                = id_col->offsets.data();
    bufs_id[2]                = id_col->flat_buf.data();
    arr_id->buffers           = bufs_id;
    arr_id->private_data      = id_col;
    arr_id->release           = [](ArrowArray* a) {
        delete static_cast<ColData*>(a->private_data);
        delete[] a->buffers;
        a->release = nullptr;
    };

    // ArrowArray for metadata column
    auto* arr_meta            = new ArrowArray();
    arr_meta->length          = n;
    arr_meta->null_count      = 0;
    arr_meta->n_buffers       = 3;
    auto** bufs_meta          = new const void*[3];
    bufs_meta[0]              = nullptr;
    bufs_meta[1]              = meta_col->offsets.data();
    bufs_meta[2]              = meta_col->flat_buf.data();
    arr_meta->buffers         = bufs_meta;
    arr_meta->private_data    = meta_col;
    arr_meta->release         = [](ArrowArray* a) {
        delete static_cast<ColData*>(a->private_data);
        delete[] a->buffers;
        a->release = nullptr;
    };

    // Wrap both in a struct (parent ArrowArray with two children)
    struct RootData { ArrowArray* id_child; ArrowArray* meta_child; };
    auto* root_data           = new RootData{arr_id, arr_meta};
    auto* root_arr            = new ArrowArray();
    root_arr->length          = n;
    root_arr->null_count      = 0;
    root_arr->n_buffers       = 1;
    auto** root_bufs          = new const void*[1];
    root_bufs[0]              = nullptr;
    root_arr->buffers         = root_bufs;
    root_arr->n_children      = 2;
    auto** children           = new ArrowArray*[2];
    children[0]               = arr_id;
    children[1]               = arr_meta;
    root_arr->children        = children;
    root_arr->private_data    = root_data;
    root_arr->release         = [](ArrowArray* a) {
        auto* rd = static_cast<RootData*>(a->private_data);
        if (rd->id_child->release)   rd->id_child->release(rd->id_child);
        if (rd->meta_child->release) rd->meta_child->release(rd->meta_child);
        delete rd->id_child;
        delete rd->meta_child;
        delete rd;
        delete[] a->buffers;
        delete[] a->children;
        a->release = nullptr;
    };

    // Schema
    auto* schema              = new ArrowSchema();
    schema->format            = "+s";   // struct
    schema->name              = "";
    schema->n_children        = 2;
    auto** sch_children       = new ArrowSchema*[2];
    auto* sch_id              = new ArrowSchema();
    sch_id->format            = "u";    // utf8
    sch_id->name              = "id";
    sch_id->release           = [](ArrowSchema* s) { s->release = nullptr; };
    auto* sch_meta            = new ArrowSchema();
    sch_meta->format          = "u";
    sch_meta->name            = "metadata";
    sch_meta->release         = [](ArrowSchema* s) { s->release = nullptr; };
    sch_children[0]           = sch_id;
    sch_children[1]           = sch_meta;
    schema->children          = sch_children;
    schema->release           = [](ArrowSchema* s) {
        if (s->children) {
            for (int64_t i = 0; i < s->n_children; ++i)
                if (s->children[i] && s->children[i]->release)
                    s->children[i]->release(s->children[i]);
            delete[] s->children;
        }
        s->release = nullptr;
    };

    return py::make_tuple(
        reinterpret_cast<intptr_t>(root_arr),
        reinterpret_cast<intptr_t>(schema));
}

} // namespace batch::secret

// ===========================================================================
// STUB IMPLEMENTATION (SQLCipher / libsodium not available)
// ===========================================================================

#else // !HAVE_SQLCIPHER

namespace batch::secret {

void insert_listing_secure(
    const std::string&, const std::string&, const std::string&,
    py::array_t<float>, const std::string&)
{
    throw py::type_error(
        "batch.secret.insert_listing_secure: built without SQLCipher. "
        "Falling back to Rust base module.");
}

py::list hybrid_search_secure(
    const std::string&, const std::string&, py::array_t<float>,
    const std::string&, int)
{
    throw py::type_error(
        "batch.secret.hybrid_search_secure: built without SQLCipher. "
        "Falling back to Rust base module.");
}

py::list fetch_all_listings_secure(const std::string&, const std::string&) {
    throw py::type_error(
        "batch.secret.fetch_all_listings_secure: built without SQLCipher. "
        "Falling back to Rust base module.");
}

bool delete_listing_secure(
    const std::string&, const std::string&, const std::string&)
{
    throw py::type_error(
        "batch.secret.delete_listing_secure: built without SQLCipher. "
        "Falling back to Rust base module.");
}

py::tuple fetch_listings_as_arrow_pointers(const std::string&, const std::string&) {
    throw py::type_error(
        "batch.secret.fetch_listings_as_arrow_pointers: built without SQLCipher. "
        "Falling back to Rust base module.");
}

} // namespace batch::secret

#endif // HAVE_SQLCIPHER

// ===========================================================================
// pybind11 registration (called from bindings.cpp)
// ===========================================================================

void register_secret(py::module_& m) {
    m.doc() =
#ifdef HAVE_SQLCIPHER
        "Encrypted vector database (SQLCipher + Argon2id + Arrow C Data Interface). "
        "Phase 4 — replaces Rust secure_vector_db.";
#else
        "Encrypted vector database (SQLCipher). "
        "Phase 4 — built without SQLCipher; all functions raise so NativeExt falls "
        "back to the Rust base module.";
#endif

    m.def("insert_listing_secure",
          &batch::secret::insert_listing_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("listing_id"),
          py::arg("embedding"),
          py::arg("metadata_json") = "{}",
          "Insert or update a listing in the encrypted database.");

    m.def("hybrid_search_secure",
          &batch::secret::hybrid_search_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("query_embedding"),
          py::arg("bm25_query")    = "",
          py::arg("top_k")         = 10,
          "Cosine-similarity search over encrypted listings. "
          "Returns list of (id, score, metadata_json) tuples.");

    m.def("fetch_all_listings_secure",
          &batch::secret::fetch_all_listings_secure,
          py::arg("db_path"),
          py::arg("password"),
          "Fetch all (id, metadata_json) pairs from the encrypted database.");

    m.def("delete_listing_secure",
          &batch::secret::delete_listing_secure,
          py::arg("db_path"),
          py::arg("password"),
          py::arg("listing_id"),
          "Delete a listing by ID. Returns True if found and deleted.");

    m.def("fetch_listings_as_arrow_pointers",
          &batch::secret::fetch_listings_as_arrow_pointers,
          py::arg("db_path"),
          py::arg("password"),
          "Zero-copy bulk export via Apache Arrow C Data Interface. "
          "Returns (array_ptr: int, schema_ptr: int). "
          "Call ArrowArray.release / ArrowSchema.release to free.");
}
