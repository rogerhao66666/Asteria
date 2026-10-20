// Asteria native compute kernels (D23). A plain C interface over raw column buffers, loaded with
// ctypes (see ../_native.py). Every function does the same arithmetic in the same order as the
// python reference kernel set (kernels/_python.py): no fast-math, no fused multiply-add (the
// build script passes -ffp-contract=off), so results are bit-identical.
//
// Slot-indexed columns are float64 (``double``), int64 or int8 buffers, picked per name by the
// caller. Variable-size results use a caller-owned output buffer: the function returns the count
// it needs; when that is larger than ``cap`` nothing past ``cap`` is written and the caller
// retries with a bigger buffer.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace {

struct CellKey {
    int64_t key;
    int32_t row;
};

inline int64_t cell_key(int64_t cx, int64_t cy) { return (cx << 32) ^ (cy & 0xFFFFFFFFLL); }
inline int64_t cell_of(double v, double cell_size) {
    return static_cast<int64_t>(std::floor(v / cell_size));
}

// every (key, row) of the grid cells the boxes cover, sorted by key then row
std::vector<CellKey> grid_cells(
    const double* x0, const double* y0, const double* x1, const double* y1, int64_t n,
    double cell_size) {
    std::vector<CellKey> cells;
    cells.reserve(static_cast<size_t>(n));
    for (int64_t j = 0; j < n; ++j) {
        const int64_t cx0 = cell_of(x0[j], cell_size), cx1 = cell_of(x1[j], cell_size);
        const int64_t cy0 = cell_of(y0[j], cell_size), cy1 = cell_of(y1[j], cell_size);
        for (int64_t cx = cx0; cx <= cx1; ++cx)
            for (int64_t cy = cy0; cy <= cy1; ++cy)
                cells.push_back({cell_key(cx, cy), static_cast<int32_t>(j)});
    }
    std::sort(cells.begin(), cells.end(), [](const CellKey& l, const CellKey& r) {
        return l.key != r.key ? l.key < r.key : l.row < r.row;
    });
    return cells;
}

int64_t emit(std::vector<int64_t>& found, int64_t* out, int64_t cap) {
    std::sort(found.begin(), found.end());
    found.erase(std::unique(found.begin(), found.end()), found.end());
    const int64_t count = static_cast<int64_t>(found.size());
    const int64_t write = std::min(count, cap);
    for (int64_t k = 0; k < write; ++k) out[k] = found[static_cast<size_t>(k)];
    return count;
}

}  // namespace

extern "C" {

int32_t ak_abi_version() { return 4; }

// -- broad phase ----------------------------------------------------------------------------
// Pairs i < j of overlapping (or touching) boxes, written as i * n + j, sorted.
int64_t ak_aabb_pairs(
    const double* x0, const double* y0, const double* x1, const double* y1, int64_t n,
    double cell_size, int64_t* out, int64_t cap) {
    if (n < 2) return 0;
    const std::vector<CellKey> cells = grid_cells(x0, y0, x1, y1, n, cell_size);
    std::vector<int64_t> found;
    size_t start = 0;
    while (start < cells.size()) {
        size_t stop = start;
        while (stop < cells.size() && cells[stop].key == cells[start].key) ++stop;
        for (size_t a = start; a < stop; ++a) {
            for (size_t b = a + 1; b < stop; ++b) {
                const int64_t i = cells[a].row, j = cells[b].row;
                if (x0[i] <= x1[j] && x0[j] <= x1[i] && y0[i] <= y1[j] && y0[j] <= y1[i])
                    found.push_back(i * n + j);
            }
        }
        start = stop;
    }
    return emit(found, out, cap);
}

// Pairs (i, j) where box a[i] overlaps box b[j]; ``touching`` counts shared edges. Written as
// i * nb + j, sorted.
int64_t ak_aabb_cross_pairs(
    const double* ax0, const double* ay0, const double* ax1, const double* ay1, int64_t na,
    const double* bx0, const double* by0, const double* bx1, const double* by1, int64_t nb,
    double cell_size, int32_t touching, int64_t* out, int64_t cap) {
    if (na == 0 || nb == 0) return 0;
    const std::vector<CellKey> cells = grid_cells(bx0, by0, bx1, by1, nb, cell_size);
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
    return emit(found, out, cap);
}

// -- particles (rows of a (9, n) row-major float64 matrix) --------------------------------------
// px py vx vy life max_life size_k angle spin. Updates in place; ``alive[i]`` = still alive.
void ak_particle_step(
    double* data, int64_t n, double dt, double gx, double gy, double keep, uint8_t* alive) {
    double *px = data, *py = data + n, *vx = data + 2 * n, *vy = data + 3 * n;
    double *life = data + 4 * n, *max_life = data + 5 * n, *angle = data + 7 * n,
           *spin = data + 8 * n;
    for (int64_t i = 0; i < n; ++i) {
        vx[i] = (vx[i] + gx * dt) * keep;
        vy[i] = (vy[i] + gy * dt) * keep;
        px[i] += vx[i] * dt;
        py[i] += vy[i] * dt;
        life[i] += dt;
        angle[i] += spin[i] * dt;
        alive[i] = life[i] < max_life[i] ? 1 : 0;
    }
}

// Weather rows: x y vy size phase. Writes the rows that left the screen to ``rows`` and whether
// they fell off the bottom to ``fell``; returns how many.
int64_t ak_weather_step(
    double* data, int64_t n, double dt, double wind, double time, int32_t sway, double shift_x,
    double shift_y, double width, double height, int64_t* rows, uint8_t* fell) {
    double *x = data, *y = data + n, *vy = data + 2 * n, *phase = data + 4 * n;
    int64_t count = 0;
    for (int64_t i = 0; i < n; ++i) {
        const double drift = sway ? std::sin(time * 1.7 + phase[i]) * 18.0 : 0.0;
        x[i] += (wind + drift) * dt + shift_x;
        y[i] += vy[i] * dt + shift_y;
        const bool below = y[i] > height + 20;
        if (below || x[i] < -60 || x[i] > width + 60) {
            rows[count] = i;
            fell[count] = below ? 1 : 0;
            ++count;
        }
    }
    return count;
}

// -- projectiles (rows of an (11, n) row-major float64 matrix) --------------------------------
// x y vx vy gravity age life hw hh turn uid. ``rot_c`` / ``rot_s`` are cos / sin of each row's
// per-step turn angle (computed by the caller); ``tx`` / ``ty`` null = no homing.
void ak_projectile_step(
    double* data, int64_t n, double dt, const double* tx, const double* ty, const double* rot_c,
    const double* rot_s) {
    double *x = data, *y = data + n, *vx = data + 2 * n, *vy = data + 3 * n;
    double *gravity = data + 4 * n, *age = data + 5 * n, *turn = data + 9 * n;
    if (tx != nullptr) {
        for (int64_t i = 0; i < n; ++i) {
            if (turn[i] <= 0 || tx[i] != tx[i]) continue;
            const double dx = tx[i] - x[i], dy = ty[i] - y[i];
            const double dist = std::sqrt(dx * dx + dy * dy);
            const double speed = std::sqrt(vx[i] * vx[i] + vy[i] * vy[i]);
            if (dist == 0.0 || speed == 0.0) continue;
            const double c = rot_c[i];
            double s = rot_s[i];
            if ((vx[i] * dx + vy[i] * dy) / (speed * dist) >= c) {
                const double nvx = dx / dist * speed, nvy = dy / dist * speed;
                vx[i] = nvx;
                vy[i] = nvy;
            } else {
                s = (vx[i] * dy - vy[i] * dx > 0) ? s : -s;
                const double nvx = vx[i] * c - vy[i] * s, nvy = vx[i] * s + vy[i] * c;
                vx[i] = nvx;
                vy[i] = nvy;
            }
        }
    }
    for (int64_t i = 0; i < n; ++i) {
        vy[i] += gravity[i] * dt;
        x[i] += vx[i] * dt;
        y[i] += vy[i] * dt;
        age[i] += dt;
    }
}

// -- store rows (an (fields, n) row-major float64 matrix) -------------------------------------
// The rows ``rows`` (negative = from the end) of ``src`` into ``dst`` (fields, m). Returns 0, or
// -1 when a row is out of range (``dst`` is then partly written).
int32_t ak_take_rows(
    const double* src, int64_t fields, int64_t n, const int64_t* rows, int64_t m, double* dst) {
    for (int64_t k = 0; k < m; ++k) {
        const int64_t r = rows[k] < 0 ? rows[k] + n : rows[k];
        if (r < 0 || r >= n) return -1;
        for (int64_t f = 0; f < fields; ++f) dst[f * m + k] = src[f * n + r];
    }
    return 0;
}

// ``values[i] += delta`` for every value.
void ak_offset(double* values, int64_t n, double delta) {
    for (int64_t i = 0; i < n; ++i) values[i] += delta;
}

// -- columns by slot ------------------------------------------------------------------------
void ak_collider_columns(
    const double* tx, const double* ty, const double* ox, const double* oy, const double* w,
    const double* h, const double* r, const int64_t* slots, const uint8_t* circle, int64_t n,
    double* cx, double* cy, double* hw, double* hh) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        cx[k] = tx[s] + ox[s];
        cy[k] = ty[s] + oy[s];
        hw[k] = circle[k] ? r[s] : w[s] / 2;
        hh[k] = circle[k] ? r[s] : h[s] / 2;
    }
}

void ak_topdown_prepare(
    const double* ix, const double* iy, double* lock, int8_t* jump, const double* speed,
    const double* override_speed, const double* px, const double* py, const int64_t* slots,
    int64_t n, double dt, double* out_dx, double* out_dy, double* out_mx, double* out_my,
    uint8_t* out_locked) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        double dx = ix[s], dy = iy[s];
        const bool locked = lock[s] > 0.0;
        if (locked) {
            const double remaining = lock[s] - dt;
            lock[s] = remaining < 1e-9 ? 0.0 : remaining;
            dx = dy = 0.0;
            jump[s] = 0;
        }
        const double mag = std::sqrt(dx * dx + dy * dy);
        if (mag > 1.0) {
            dx = dx / mag;
            dy = dy / mag;
        }
        out_dx[k] = dx;
        out_dy[k] = dy;
        const double v = override_speed[s] > 0.0 ? override_speed[s] : speed[s];
        out_mx[k] = (dx * v + px[s]) * dt;
        out_my[k] = (dy * v + py[s]) * dt;
        out_locked[k] = locked ? 1 : 0;
    }
}

void ak_moved_boxes(
    const double* tx, const double* ty, const double* half_w, const double* half_h,
    const int64_t* slots, const double* move_x, const double* move_y, int64_t n, double* x0,
    double* y0, double* x1, double* y1) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        const double x = tx[s] + move_x[k], y = ty[s] + move_y[k];
        x0[k] = x - half_w[s];
        y0[k] = y - half_h[s];
        x1[k] = x + half_w[s];
        y1[k] = y + half_h[s];
    }
}

void ak_add_to_column(double* column, const int64_t* slots, const double* values, int64_t n) {
    for (int64_t k = 0; k < n; ++k) column[slots[k]] += values[k];
}

void ak_decay_push(
    double* px, double* py, const double* decay, const int64_t* slots, int64_t n, double dt,
    double epsilon) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        if (!(px[s] != 0.0 || py[s] != 0.0)) continue;
        const double keep = std::exp(-decay[s] * dt);
        const double x = px[s] * keep, y = py[s] * keep;
        px[s] = std::fabs(x) < epsilon ? 0.0 : x;
        py[s] = std::fabs(y) < epsilon ? 0.0 : y;
    }
}

void ak_box_columns(
    const double* tx, const double* ty, const double* bx, const double* by, const double* bw,
    const double* bh, const int8_t* follow, const int64_t* slots, const int64_t* codes, int64_t n,
    double* x0, double* y0, double* x1, double* y1) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        double ox = bx[s], oy = by[s], w = bw[s], h = bh[s];
        if (follow[s]) {
            if (codes[k] == 2) {
                ox = -ox;
            } else if (codes[k] == 0) {
                const double nox = -oy, noy = ox;
                ox = nox;
                oy = noy;
                const double nw = h, nh = w;
                w = nw;
                h = nh;
            } else if (codes[k] == 1) {
                const double nox = oy, noy = -ox;
                ox = nox;
                oy = noy;
                const double nw = h, nh = w;
                w = nw;
                h = nh;
            }
        }
        const double cx = tx[s] + ox, cy = ty[s] + oy;
        x0[k] = cx - w / 2;
        y0[k] = cy - h / 2;
        x1[k] = cx + w / 2;
        y1[k] = cy + h / 2;
    }
}

// ``blocked[i]`` is set for movers blocked by a wall among the candidate pairs (i, j).
void ak_blocked_rows(
    const double* x0, const double* y0, const double* x1, const double* y1, const double* cx,
    const double* cy, const double* radius, const int64_t* pairs, int64_t npairs,
    const int64_t* mover_mask, const int64_t* mover_row, const int64_t* wall_bit,
    const uint8_t* wall_one_way, const uint8_t* wall_circle, uint8_t* blocked) {
    for (int64_t p = 0; p < npairs; ++p) {
        const int64_t i = pairs[2 * p], j = pairs[2 * p + 1];
        if (blocked[i] || j == mover_row[i] || wall_one_way[j] || !(mover_mask[i] & wall_bit[j]))
            continue;
        if (wall_circle[j]) {
            const double nx = std::min(std::max(cx[j], x0[i]), x1[i]);
            const double ny = std::min(std::max(cy[j], y0[i]), y1[i]);
            const double d = std::sqrt((nx - cx[j]) * (nx - cx[j]) + (ny - cy[j]) * (ny - cy[j]));
            if (d > radius[j]) continue;
        }
        blocked[i] = 1;
    }
}

// Movers (boxes x0..y1) blocked by a wall (boxes bx0..by1; shared edges count): the broad phase
// of ak_aabb_cross_pairs and the test of ak_blocked_rows in one pass, with no pair list between
// them (building it, and turning it into Python tuples and back, cost more than both tests).
void ak_blocked_boxes(
    const double* x0, const double* y0, const double* x1, const double* y1, int64_t na,
    const double* bx0, const double* by0, const double* bx1, const double* by1, int64_t nb,
    double cell_size, const double* cx, const double* cy, const double* radius,
    const int64_t* mover_mask, const int64_t* mover_row, const int64_t* wall_bit,
    const uint8_t* wall_one_way, const uint8_t* wall_circle, uint8_t* blocked) {
    if (na == 0 || nb == 0) return;
    const std::vector<CellKey> cells = grid_cells(bx0, by0, bx1, by1, nb, cell_size);
    for (int64_t i = 0; i < na; ++i) {
        const int64_t cx0 = cell_of(x0[i], cell_size), cx1 = cell_of(x1[i], cell_size);
        const int64_t cy0 = cell_of(y0[i], cell_size), cy1 = cell_of(y1[i], cell_size);
        for (int64_t gx = cx0; gx <= cx1 && !blocked[i]; ++gx) {
            for (int64_t gy = cy0; gy <= cy1 && !blocked[i]; ++gy) {
                const int64_t key = cell_key(gx, gy);
                auto it = std::lower_bound(
                    cells.begin(), cells.end(), key,
                    [](const CellKey& c, int64_t k) { return c.key < k; });
                for (; it != cells.end() && it->key == key; ++it) {
                    const int64_t j = it->row;
                    if (!(x0[i] <= bx1[j] && bx0[j] <= x1[i] && y0[i] <= by1[j] &&
                          by0[j] <= y1[i]))
                        continue;
                    if (j == mover_row[i] || wall_one_way[j] || !(mover_mask[i] & wall_bit[j]))
                        continue;
                    if (wall_circle[j]) {
                        const double nx = std::min(std::max(cx[j], x0[i]), x1[i]);
                        const double ny = std::min(std::max(cy[j], y0[i]), y1[i]);
                        const double d =
                            std::sqrt((nx - cx[j]) * (nx - cx[j]) + (ny - cy[j]) * (ny - cy[j]));
                        if (d > radius[j]) continue;
                    }
                    blocked[i] = 1;
                    break;
                }
            }
        }
    }
}

void ak_facing_codes(
    const double* dx, const double* dy, const int64_t* current, const uint8_t* locked, int64_t n,
    int64_t* out) {
    for (int64_t k = 0; k < n; ++k) {
        const double x = dx[k], y = dy[k];
        if (locked[k]) {
            out[k] = current[k];
        } else if (std::fabs(x) >= std::fabs(y) && x > 1e-9) {
            out[k] = 3;
        } else if (std::fabs(x) >= std::fabs(y) && x < -1e-9) {
            out[k] = 2;
        } else if (y > 1e-9) {
            out[k] = 0;
        } else if (y < -1e-9) {
            out[k] = 1;
        } else {
            out[k] = current[k];
        }
    }
}

// Field AI reaction and steering. Writes ``mode`` and the controllers' intents; ``rest[k]`` is set
// for entities whose mode is patrol or wander (the caller steers those itself).
void ak_fieldai_step(
    int64_t* mode, const double* home_x, const double* home_y, const double* detect,
    const double* lose, const double* arrive, const double* x, const double* y, double* ix,
    double* iy, const double* speed, const int64_t* slots, int64_t n, const int64_t* behaviour,
    const double* target_x, const double* target_y, const uint8_t* has_target, double dt,
    uint8_t* rest) {
    for (int64_t k = 0; k < n; ++k) {
        const int64_t s = slots[k];
        ix[s] = iy[s] = 0.0;
        const int64_t b = behaviour[k];
        int64_t m = mode[s];
        if ((b == 3 || b == 4) && has_target[k]) {
            const double dxt = target_x[k] - x[s], dyt = target_y[k] - y[s];
            const double distance = std::sqrt(dxt * dxt + dyt * dyt);
            if (m == 3 || m == 4) {
                if (distance > lose[s]) m = 5;
            } else if (distance <= detect[s]) {
                m = b;
            }
        }
        if ((m == 3 || m == 4) && !has_target[k]) m = 5;
        if (m == 3 || m == 4 || m == 5) {
            const bool away = m == 4;
            const double gx = m == 5 ? home_x[s] : target_x[k];
            const double gy = m == 5 ? home_y[s] : target_y[k];
            double dx = gx - x[s], dy = gy - y[s];
            if (away) {
                dx = -dx;
                dy = -dy;
            }
            const double d = std::sqrt(dx * dx + dy * dy);
            if (d <= (away ? 0.0 : arrive[s])) {
                if (m == 5) m = 0;
            } else {
                const double scale =
                    away ? 1.0 : std::min(1.0, d / std::max(speed[s] * dt, 1e-9));
                ix[s] = dx / d * scale;
                iy[s] = dy / d * scale;
            }
        } else if (b == 1 || b == 2) {
            m = b;
            rest[k] = 1;
        } else {
            m = 0;
        }
        mode[s] = m;
    }
}

}  // extern "C"
