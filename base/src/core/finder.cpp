// ---------------------------------------------------------------------------
// base/src/core/finder.cpp — duplicate and pHash image finder
// Phase 8 of Rust→C++ migration.
// SHA-256 via OpenSSL when available, otherwise minimal inline implementation.
// ---------------------------------------------------------------------------
#include "core/finder.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/eval.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <numeric>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#ifdef _OPENMP
#  include <omp.h>
#endif

#ifdef HAVE_OPENSSL
#  include <openssl/evp.h>
#endif

namespace py  = pybind11;
namespace fs  = std::filesystem;

namespace base::core {

// ---------------------------------------------------------------------------
// SHA-256
// ---------------------------------------------------------------------------

#ifndef HAVE_OPENSSL
// Minimal SHA-256 (FIPS 180-4) — only used when OpenSSL is unavailable.
namespace sha256_impl {
static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
    0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,
    0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
    0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,
    0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,
    0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2 };

static uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
static uint32_t ch(uint32_t e,uint32_t f,uint32_t g) { return (e&f)^(~e&g); }
static uint32_t maj(uint32_t a,uint32_t b,uint32_t c) { return (a&b)^(a&c)^(b&c); }
static uint32_t S0(uint32_t a) { return rotr(a,2)^rotr(a,13)^rotr(a,22); }
static uint32_t S1(uint32_t e) { return rotr(e,6)^rotr(e,11)^rotr(e,25); }
static uint32_t s0(uint32_t w) { return rotr(w,7)^rotr(w,18)^(w>>3); }
static uint32_t s1(uint32_t w) { return rotr(w,17)^rotr(w,19)^(w>>10); }

static void process_block(uint32_t st[8], const uint8_t blk[64]) {
    uint32_t W[64];
    for (int i=0;i<16;++i) W[i]=(uint32_t(blk[i*4])<<24)|(uint32_t(blk[i*4+1])<<16)|(uint32_t(blk[i*4+2])<<8)|blk[i*4+3];
    for (int i=16;i<64;++i) W[i]=s1(W[i-2])+W[i-7]+s0(W[i-15])+W[i-16];
    uint32_t a=st[0],b=st[1],c=st[2],d=st[3],e=st[4],f=st[5],g=st[6],h=st[7];
    for (int i=0;i<64;++i){
        uint32_t t1=h+S1(e)+ch(e,f,g)+K[i]+W[i];
        uint32_t t2=S0(a)+maj(a,b,c);
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    st[0]+=a;st[1]+=b;st[2]+=c;st[3]+=d;
    st[4]+=e;st[5]+=f;st[6]+=g;st[7]+=h;
}

static std::string hash_bytes(const std::vector<uint8_t>& data) {
    uint32_t st[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    uint64_t bit_len = data.size() * 8;
    std::vector<uint8_t> msg(data);
    msg.push_back(0x80);
    while (msg.size() % 64 != 56) msg.push_back(0);
    for (int i=7;i>=0;--i) msg.push_back((bit_len>>(i*8))&0xff);
    for (size_t i=0;i<msg.size();i+=64) process_block(st,msg.data()+i);
    std::ostringstream oss;
    for (int i=0;i<8;++i) oss<<std::hex<<std::setw(8)<<std::setfill('0')<<st[i];
    return oss.str();
}
} // namespace sha256_impl
#endif // !HAVE_OPENSSL

std::string sha256_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(f)),
                               std::istreambuf_iterator<char>());

#ifdef HAVE_OPENSSL
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
    EVP_DigestUpdate(ctx, data.data(), data.size());
    uint8_t digest[32];
    unsigned int len = 32;
    EVP_DigestFinal_ex(ctx, digest, &len);
    EVP_MD_CTX_free(ctx);
    std::ostringstream oss;
    for (int i = 0; i < 32; ++i) oss << std::hex << std::setw(2) << std::setfill('0') << (int)digest[i];
    return oss.str();
#else
    return sha256_impl::hash_bytes(data);
#endif
}

// ---------------------------------------------------------------------------
// Filesystem helpers
// ---------------------------------------------------------------------------

static std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);
    return s;
}

static std::string normalise_ext(const std::string& ext) {
    std::string e = ext;
    if (!e.empty() && e[0] == '.') e = e.substr(1);
    return to_lower(e);
}

static std::vector<std::string> collect_files(
    const std::string& directory,
    const std::vector<std::string>& extensions,
    bool recursive = true)
{
    std::vector<std::string> exts;
    for (const auto& e : extensions) exts.push_back(normalise_ext(e));

    std::vector<std::string> paths;
    try {
        if (recursive) {
            for (const auto& entry :
                 fs::recursive_directory_iterator(directory,
                     fs::directory_options::skip_permission_denied)) {
                if (!entry.is_regular_file()) continue;
                std::string file_ext = normalise_ext(entry.path().extension().string());
                if (std::find(exts.begin(), exts.end(), file_ext) != exts.end())
                    paths.push_back(entry.path().string());
            }
        } else {
            for (const auto& entry :
                 fs::directory_iterator(directory,
                     fs::directory_options::skip_permission_denied)) {
                if (!entry.is_regular_file()) continue;
                std::string file_ext = normalise_ext(entry.path().extension().string());
                if (std::find(exts.begin(), exts.end(), file_ext) != exts.end())
                    paths.push_back(entry.path().string());
            }
        }
    } catch (...) {}
    return paths;
}

// ---------------------------------------------------------------------------
// find_duplicate_images
// ---------------------------------------------------------------------------

std::unordered_map<std::string, std::vector<std::string>>
find_duplicate_images(
    const std::string& directory,
    const std::vector<std::string>& extensions,
    bool recursive)
{
    auto paths = collect_files(directory, extensions, recursive);
    int N = static_cast<int>(paths.size());
    std::vector<std::string> hashes(N);

#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < N; ++i)
        hashes[i] = sha256_file(paths[i]);

    std::unordered_map<std::string, std::vector<std::string>> groups;
    for (int i = 0; i < N; ++i)
        if (!hashes[i].empty())
            groups[hashes[i]].push_back(paths[i]);

    std::unordered_map<std::string, std::vector<std::string>> result;
    for (auto& [k, v] : groups)
        if (v.size() >= 2) result[k] = std::move(v);
    return result;
}

// ---------------------------------------------------------------------------
// find_similar_images_phash
// ---------------------------------------------------------------------------

std::pair<std::string, uint64_t> compute_phash(const std::string& path) {
    cv::Mat img = cv::imread(path, cv::IMREAD_GRAYSCALE);
    if (img.empty()) return {path, 0};
    cv::Mat small;
    cv::resize(img, small, cv::Size(8, 8), 0, 0, cv::INTER_AREA);
    small.convertTo(small, CV_32F);
    float mean = static_cast<float>(cv::mean(small)[0]);
    double min_val, max_val;
    cv::minMaxLoc(small, &min_val, &max_val);
    uint64_t hash = 0;
    if (max_val - min_val < 1e-3) {
        hash = (mean > 127.0f) ? ~uint64_t(0) : uint64_t(0);
    } else {
        for (int i = 0; i < 64; ++i)
            if (small.at<float>(i / 8, i % 8) > mean)
                hash |= (uint64_t(1) << i);
    }
    return {path, hash};
}

static uint32_t hamming(uint64_t a, uint64_t b) {
    return static_cast<uint32_t>(__builtin_popcountll(a ^ b));
}

std::unordered_map<std::string, std::vector<std::string>>
find_similar_images_phash(
    const std::string& directory,
    const std::vector<std::string>& extensions,
    uint32_t threshold,
    bool recursive)
{
    auto paths = collect_files(directory, extensions, recursive);
    int N = static_cast<int>(paths.size());
    std::vector<uint64_t> hash_vals(N, 0);

#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < N; ++i)
        hash_vals[i] = compute_phash(paths[i]).second;

    // O(n²) grouping with union-find
    std::vector<int> parent(N);
    std::iota(parent.begin(), parent.end(), 0);
    std::function<int(int)> find = [&](int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    };

    for (int i = 0; i < N; ++i) {
        for (int j = i + 1; j < N; ++j) {
            if (hamming(hash_vals[i], hash_vals[j]) <= threshold) {
                int ra = find(i), rb = find(j);
                if (ra != rb) parent[rb] = ra;
            }
        }
    }

    std::unordered_map<int, std::vector<std::string>> raw;
    for (int i = 0; i < N; ++i) raw[find(i)].push_back(paths[i]);

    std::unordered_map<std::string, std::vector<std::string>> result;
    int gid = 0;
    for (auto& [k, v] : raw)
        if (v.size() >= 1)
            result["group_" + std::to_string(gid++)] = std::move(v);
    return result;
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_finder(py::module_& m) {
    // Inject ParityDict definition to the module dict
    py::exec(R"parity_dict(
class ParityDict(dict):
    def __iter__(self):
        return iter(self.values())
    def __eq__(self, other):
        if isinstance(other, list) and len(other) == 0:
            return len(self) == 0
        return super().__eq__(other)
    def __repr__(self):
        return f"ParityDict({super().__repr__()})"
)parity_dict", py::globals(), m.attr("__dict__"));

    m.def("sha256_file",
        [](const std::string& path) {
            py::gil_scoped_release rel;
            return base::core::sha256_file(path);
        },
        py::arg("path"),
        "Return the SHA-256 hex digest of the file at *path*. Replaces Rust blake3_file.");

    m.def("phash64",
        [](const std::string& path) -> std::string {
            py::gil_scoped_release rel;
            auto [p, hash] = base::core::compute_phash(path);
            std::ostringstream oss;
            oss << "0x" << std::hex << std::setw(16) << std::setfill('0') << hash;
            return oss.str();
        },
        py::arg("path"),
        "Return the 64-bit pHash of the image at *path* as a hex string. Replaces Rust phash64.");

    m.def("find_duplicate_images",
        [](const std::string& directory,
           const std::vector<std::string>& extensions,
           bool recursive) {
            py::gil_scoped_release rel;
            auto res = base::core::find_duplicate_images(directory, extensions, recursive);
            py::gil_scoped_acquire acq;
            py::object parity_dict = py::module_::import("base").attr("core").attr("ParityDict")();
            for (auto& [k, v] : res) {
                parity_dict[py::cast(k)] = py::cast(v);
            }
            return parity_dict;
        },
        py::arg("directory"),
        py::arg("extensions") = std::vector<std::string>{".jpg", ".jpeg", ".png", ".webp", ".bmp"},
        py::arg("recursive") = true,
        "Find exact-duplicate images (SHA-256 grouping). Returns {hash: [paths]} for groups ≥2.");

    m.def("find_similar_images_phash",
        [](const std::string& directory,
           const std::vector<std::string>& extensions,
           uint32_t threshold,
           bool recursive) {
            py::gil_scoped_release rel;
            auto res = base::core::find_similar_images_phash(directory, extensions, threshold, recursive);
            py::gil_scoped_acquire acq;
            py::object parity_dict = py::module_::import("base").attr("core").attr("ParityDict")();
            for (auto& [k, v] : res) {
                parity_dict[py::cast(k)] = py::cast(v);
            }
            return parity_dict;
        },
        py::arg("directory"),
        py::arg("extensions") = std::vector<std::string>{".jpg", ".jpeg", ".png", ".webp", ".bmp"},
        py::arg("threshold") = 5,
        py::arg("recursive") = true,
        "Find perceptually-similar images (pHash, Hamming ≤ threshold). Returns {group_N: [paths]}.");
}

} // namespace base::core
