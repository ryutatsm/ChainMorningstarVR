#pragma once
#include <cmath>

namespace cms {

constexpr float kSkyrimUnitsPerMeter = 69.99125f;
constexpr float kMetersPerSkyrimUnit = 1.0f / kSkyrimUnitsPerMeter;

struct Vec3 {
    float x{}, y{}, z{};
};

inline Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline Vec3 operator-(Vec3 a) { return {-a.x, -a.y, -a.z}; }
inline Vec3 operator*(Vec3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
inline Vec3 operator*(float s, Vec3 a) { return a * s; }
inline Vec3 operator/(Vec3 a, float s) { return {a.x / s, a.y / s, a.z / s}; }
inline Vec3& operator+=(Vec3& a, Vec3 b) { a = a + b; return a; }
inline Vec3& operator-=(Vec3& a, Vec3 b) { a = a - b; return a; }

inline float dot(Vec3 a, Vec3 b) { return a.x*b.x + a.y*b.y + a.z*b.z; }
inline Vec3 cross(Vec3 a, Vec3 b) {
    return {a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x};
}
inline float lengthSq(Vec3 a) { return dot(a, a); }
inline float length(Vec3 a) { return std::sqrt(lengthSq(a)); }
inline bool isFinite(Vec3 a) {
    return std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z);
}
inline Vec3 normalized(Vec3 a) {
    const float l = length(a);
    return std::isfinite(l) && l > 1.0e-7f ? a / l : Vec3{};
}
inline Vec3 lerp(Vec3 a, Vec3 b, float t) { return a + (b-a)*t; }

} // namespace cms
