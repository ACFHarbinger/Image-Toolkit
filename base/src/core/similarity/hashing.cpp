// ---------------------------------------------------------------------------
// base/src/core/similarity/hashing.cpp
// Tier 1 (xxHash64 exact digests) + Tier 2 (pHash / dHash / wHash consensus).
// ---------------------------------------------------------------------------
#include "core/similarity.hpp"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace base::similarity {

// ---------------------------------------------------------------------------
// XXH64 — public-domain xxHash 64-bit algorithm (single-shot implementation)
// ---------------------------------------------------------------------------
namespace {

constexpr uint64_t P1 = 0x9E3779B185EBCA87ULL;
constexpr uint64_t P2 = 0xC2B2AE3D27D4EB4FULL;
constexpr uint64_t P3 = 0x165667B19E3779F9ULL;
constexpr uint64_t P4 = 0x85EBCA77C2B2AE63ULL;
constexpr uint64_t P5 = 0x27D4EB2F165667C5ULL;

inline uint64_t rotl64(uint64_t x, int r) { return (x << r) | (x >> (64 - r)); }

inline uint64_t read64(const uint8_t* p) {
    uint64_t v;
    std::memcpy(&v, p, 8);
    return v;
}
inline uint32_t read32(const uint8_t* p) {
    uint32_t v;
    std::memcpy(&v, p, 4);
    return v;
}

inline uint64_t round64(uint64_t acc, uint64_t input) {
    acc += input * P2;
    acc = rotl64(acc, 31);
    acc *= P1;
    return acc;
}

inline uint64_t merge_round(uint64_t acc, uint64_t val) {
    val = round64(0, val);
    acc ^= val;
    acc = acc * P1 + P4;
    return acc;
}

}  // namespace

uint64_t xxh64_buffer(const void* data, size_t len, uint64_t seed) {
    const uint8_t* p = static_cast<const uint8_t*>(data);
    const uint8_t* end = p + len;
    uint64_t h;

    if (len >= 32) {
        uint64_t v1 = seed + P1 + P2;
        uint64_t v2 = seed + P2;
        uint64_t v3 = seed;
        uint64_t v4 = seed - P1;
        const uint8_t* limit = end - 32;
        do {
            v1 = round64(v1, read64(p));      p += 8;
            v2 = round64(v2, read64(p));      p += 8;
            v3 = round64(v3, read64(p));      p += 8;
            v4 = round64(v4, read64(p));      p += 8;
        } while (p <= limit);
        h = rotl64(v1, 1) + rotl64(v2, 7) + rotl64(v3, 12) + rotl64(v4, 18);
        h = merge_round(h, v1);
        h = merge_round(h, v2);
        h = merge_round(h, v3);
        h = merge_round(h, v4);
    } else {
        h = seed + P5;
    }

    h += static_cast<uint64_t>(len);

    while (p + 8 <= end) {
        h ^= round64(0, read64(p));
        h = rotl64(h, 27) * P1 + P4;
        p += 8;
    }
    if (p + 4 <= end) {
        h ^= static_cast<uint64_t>(read32(p)) * P1;
        h = rotl64(h, 23) * P2 + P3;
        p += 4;
    }
    while (p < end) {
        h ^= (*p) * P5;
        h = rotl64(h, 11) * P1;
        ++p;
    }

    h ^= h >> 33;
    h *= P2;
    h ^= h >> 29;
    h *= P3;
    h ^= h >> 32;
    return h;
}

std::string xxh64_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(f)),
                               std::istreambuf_iterator<char>());
    uint64_t h = xxh64_buffer(data.data(), data.size(), 0);
    std::ostringstream oss;
    oss << std::hex << std::setw(16) << std::setfill('0') << h;
    return oss.str();
}

// ---------------------------------------------------------------------------
// BitHash helpers
// ---------------------------------------------------------------------------

uint32_t hamming_distance(const BitHash& a, const BitHash& b) {
    size_t n = std::min(a.size(), b.size());
    uint32_t d = 0;
    for (size_t i = 0; i < n; ++i)
        d += static_cast<uint32_t>(__builtin_popcountll(a[i] ^ b[i]));
    // Length mismatch counts every extra bit as different
    for (size_t i = n; i < a.size(); ++i)
        d += static_cast<uint32_t>(__builtin_popcountll(a[i]));
    for (size_t i = n; i < b.size(); ++i)
        d += static_cast<uint32_t>(__builtin_popcountll(b[i]));
    return d;
}

std::string bithash_to_hex(const BitHash& h) {
    std::ostringstream oss;
    for (uint64_t w : h)
        oss << std::hex << std::setw(16) << std::setfill('0') << w;
    return oss.str();
}

BitHash bithash_from_hex(const std::string& hex) {
    BitHash h;
    for (size_t i = 0; i + 16 <= hex.size(); i += 16)
        h.push_back(std::stoull(hex.substr(i, 16), nullptr, 16));
    if (h.empty() && !hex.empty())
        h.push_back(std::stoull(hex, nullptr, 16));
    return h;
}

namespace {

// Pack a boolean matrix (row-major) into 64-bit words.
BitHash pack_bits(const std::vector<bool>& bits) {
    BitHash h((bits.size() + 63) / 64, 0);
    for (size_t i = 0; i < bits.size(); ++i)
        if (bits[i]) h[i / 64] |= (uint64_t(1) << (i % 64));
    return h;
}

float median_of(std::vector<float> v) {
    if (v.empty()) return 0.f;
    size_t mid = v.size() / 2;
    std::nth_element(v.begin(), v.begin() + mid, v.end());
    return v[mid];
}

// DCT-based pHash: resize to 4S x 4S, DCT, take top-left S x S block,
// threshold against the median (DC term excluded from the median).
BitHash phash_of(const cv::Mat& gray, int S) {
    cv::Mat img;
    cv::resize(gray, img, cv::Size(4 * S, 4 * S), 0, 0, cv::INTER_AREA);
    img.convertTo(img, CV_32F);
    cv::Mat freq;
    cv::dct(img, freq);
    cv::Mat block = freq(cv::Rect(0, 0, S, S)).clone();

    std::vector<float> vals;
    vals.reserve(S * S - 1);
    for (int r = 0; r < S; ++r)
        for (int c = 0; c < S; ++c)
            if (r != 0 || c != 0) vals.push_back(block.at<float>(r, c));
    float med = median_of(vals);

    std::vector<bool> bits(S * S);
    for (int r = 0; r < S; ++r)
        for (int c = 0; c < S; ++c)
            bits[r * S + c] = block.at<float>(r, c) > med;
    return pack_bits(bits);
}

// dHash: resize to (S+1) x S, compare horizontally adjacent pixels.
BitHash dhash_of(const cv::Mat& gray, int S) {
    cv::Mat img;
    cv::resize(gray, img, cv::Size(S + 1, S), 0, 0, cv::INTER_AREA);
    std::vector<bool> bits(S * S);
    for (int r = 0; r < S; ++r)
        for (int c = 0; c < S; ++c)
            bits[r * S + c] = img.at<uint8_t>(r, c) < img.at<uint8_t>(r, c + 1);
    return pack_bits(bits);
}

// wHash: Haar wavelet decomposition — keep the LL band down to S x S,
// threshold against the median.
BitHash whash_of(const cv::Mat& gray, int S) {
    // Start from the nearest power-of-two square >= 2S for clean halving.
    int side = 1;
    while (side < 2 * S) side <<= 1;
    cv::Mat img;
    cv::resize(gray, img, cv::Size(side, side), 0, 0, cv::INTER_AREA);
    img.convertTo(img, CV_32F, 1.0 / 255.0);

    // Haar LL: average 2x2 blocks until we reach S x S.
    while (img.rows > S) {
        cv::Mat next(img.rows / 2, img.cols / 2, CV_32F);
        for (int r = 0; r < next.rows; ++r)
            for (int c = 0; c < next.cols; ++c)
                next.at<float>(r, c) = 0.25f * (img.at<float>(2 * r, 2 * c) +
                                                img.at<float>(2 * r, 2 * c + 1) +
                                                img.at<float>(2 * r + 1, 2 * c) +
                                                img.at<float>(2 * r + 1, 2 * c + 1));
        img = next;
    }

    std::vector<float> vals;
    vals.reserve(S * S);
    for (int r = 0; r < S; ++r)
        for (int c = 0; c < S; ++c)
            vals.push_back(img.at<float>(r, c));
    float med = median_of(vals);

    std::vector<bool> bits(S * S);
    for (int r = 0; r < S; ++r)
        for (int c = 0; c < S; ++c)
            bits[r * S + c] = img.at<float>(r, c) > med;
    return pack_bits(bits);
}

}  // namespace

PerceptualHashes compute_perceptual_hashes(const std::string& path, int hash_size) {
    PerceptualHashes out;
    if (hash_size != 8 && hash_size != 16 && hash_size != 32) hash_size = 8;
    cv::Mat gray = cv::imread(path, cv::IMREAD_GRAYSCALE);
    if (gray.empty()) return out;
    out.phash = phash_of(gray, hash_size);
    out.dhash = dhash_of(gray, hash_size);
    out.whash = whash_of(gray, hash_size);
    out.ok = true;
    return out;
}

BitHash phash_from_buffer(const void* data, size_t len, int hash_size) {
    if (hash_size != 8 && hash_size != 16 && hash_size != 32) hash_size = 8;
    std::vector<uint8_t> buf(static_cast<const uint8_t*>(data),
                             static_cast<const uint8_t*>(data) + len);
    cv::Mat raw(1, static_cast<int>(buf.size()), CV_8U, buf.data());
    cv::Mat gray = cv::imdecode(raw, cv::IMREAD_GRAYSCALE);
    if (gray.empty()) return {};
    return phash_of(gray, hash_size);
}

double consensus_confidence(const PerceptualHashes& a, const PerceptualHashes& b,
                            int hash_size) {
    if (!a.ok || !b.ok) return 0.0;
    const double total_bits = static_cast<double>(hash_size) * hash_size;
    // pHash is the most discriminative; dHash catches gradients; wHash textures.
    const double weights[3] = {0.5, 0.25, 0.25};
    const uint32_t dists[3] = {
        hamming_distance(a.phash, b.phash),
        hamming_distance(a.dhash, b.dhash),
        hamming_distance(a.whash, b.whash),
    };
    double conf = 0.0;
    for (int i = 0; i < 3; ++i) {
        double sim = 1.0 - std::min(1.0, dists[i] / (total_bits * 0.5));
        conf += weights[i] * sim;
    }
    return std::max(0.0, std::min(1.0, conf));
}

}  // namespace base::similarity
