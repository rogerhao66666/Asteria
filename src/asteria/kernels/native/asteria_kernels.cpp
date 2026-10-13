// Asteria native compute kernels (D23). A plain C interface over raw column buffers, loaded with
// ctypes (see ../_native.py). Every function gives results identical to the python reference
// kernel set: no fast-math, no fused multiply-add (the build script passes -ffp-contract=off).
//
// Variable-size results use a caller-owned output buffer: the function returns the count it
// needs; when that is larger than ``cap`` nothing past ``cap`` is written and the caller retries
// with a bigger buffer.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

extern "C" {

int32_t ak_abi_version() { return 1; }

namespace {

struct CellKey {
    int64_t key;
    int32_t row;
};

inline int64_t cell_key(int64_t cx, int64_t cy) {
    return (cx << 32) ^ (cy & 0xFFFFFFFFLL);
}

inline int64_t cell_of(double v, double cell_size) {
    return static_cast<int64_t>(std::floor(v / cell_size));
}

}  // namespace

// Pairs (i, j) where box a[i] overlaps box b[j]; ``touching`` counts shared edges. Written as
// i * nb + j, sorted ascending and unique. Returns the pair count.
int64_t ak_aabb_cross_pairs(
    const double* ax0, const double* ay0, const double* ax1, const double* ay1, int64_t na,
    const double* bx0, const double* by0, const double* bx1, const double* by1, int64_t nb,
    double cell_size, int32_t touching, int64_t* out, int64_t cap) {
    if (na == 0 || nb == 0) return 0;
    std::vector<CellKey> cells;
    cells.reserve(static_cast<size_t>(nb));
    for (int64_t j = 0; j < nb; ++j) {
        const int64_t cx0 = cell_of(bx0[j], cell_size), cx1 = cell_of(bx1[j], cell_size);
        const int64_t cy0 = cell_of(by0[j], cell_size), cy1 = cell_of(by1[j], cell_size);
        for (int64_t cx = cx0; cx <= cx1; ++cx)
            for (int64_t cy = cy0; cy <= cy1; ++cy)
                cells.push_back({cell_key(cx, cy), static_cast<int32_t>(j)});
    }
    std::sort(cells.begin(), cells.end(), [](const CellKey& l, const CellKey& r) {
        return l.key != r.key ? l.key < r.key : l.row < r.row;
    });
    std::vector<int64_t> found;
    for (int64_t i = 0; i < na; ++i) {
        const int64_t cx0 = cell_of(ax0[i], cell_size), cx1 = cell_of(ax1[i], cell_size);
        const int64_t cy0 = cell_of(ay0[i], cell_size), cy1 = cell_of(ay1[i], cell_size);
        for (int64_t cx = cx0; cx <= cx1; ++cx) {
            for (int64_t cy = cy0; cy <= cy1; ++cy) {
                const int64_t key = cell_key(cx, cy);
                auto it = std::lower_bound(
                    cells.begin(), cells.end(), key,
                    [](const CellKey& c, int64_t k) { return c.key < k; });
                for (; it != cells.end() && it->key == key; ++it) {
                    const int64_t j = it->row;
                    const bool hit = touching
                        ? (ax0[i] <= bx1[j] && bx0[j] <= ax1[i] && ay0[i] <= by1[j] &&
                           by0[j] <= ay1[i])
                        : (ax0[i] < bx1[j] && bx0[j] < ax1[i] && ay0[i] < by1[j] &&
                           by0[j] < ay1[i]);
                    if (hit) found.push_back(i * nb + j);
                }
            }
        }
    }
    std::sort(found.begin(), found.end());
    found.erase(std::unique(found.begin(), found.end()), found.end());
    const int64_t count = static_cast<int64_t>(found.size());
    const int64_t write = std::min(count, cap);
    for (int64_t k = 0; k < write; ++k) out[k] = found[static_cast<size_t>(k)];
    return count;
}

}  // extern "C"
