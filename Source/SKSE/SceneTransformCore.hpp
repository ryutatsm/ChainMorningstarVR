#pragma once

#include <cmath>
#include "ChainPhysicsCore.hpp"

namespace cms {

struct Mat3 {
    float m[3][3]{
        {1.0f, 0.0f, 0.0f},
        {0.0f, 1.0f, 0.0f},
        {0.0f, 0.0f, 1.0f}
    };
};

inline Vec3 mul(const Mat3& a, Vec3 v) {
    return {
        a.m[0][0]*v.x + a.m[0][1]*v.y + a.m[0][2]*v.z,
        a.m[1][0]*v.x + a.m[1][1]*v.y + a.m[1][2]*v.z,
        a.m[2][0]*v.x + a.m[2][1]*v.y + a.m[2][2]*v.z
    };
}

inline Mat3 mul(const Mat3& a, const Mat3& b) {
    Mat3 out{};
    for (int r=0; r<3; ++r) {
        for (int c=0; c<3; ++c) {
            out.m[r][c] = 0.0f;
            for (int k=0; k<3; ++k) out.m[r][c] += a.m[r][k] * b.m[k][c];
        }
    }
    return out;
}

inline Mat3 transpose(const Mat3& a) {
    Mat3 out{};
    for (int r=0; r<3; ++r)
        for (int c=0; c<3; ++c)
            out.m[r][c] = a.m[c][r];
    return out;
}

inline Vec3 column(const Mat3& a, int c) {
    return {a.m[0][c], a.m[1][c], a.m[2][c]};
}

inline Mat3 basisFromLocalZ(Vec3 zAxis, float rollRadians = 0.0f) {
    Vec3 z = normalized(zAxis);
    if (lengthSq(z) < 1.0e-7f) z = {0,0,1};

    const Vec3 ref = (std::fabs(z.z) < 0.90f) ? Vec3{0,0,1} : Vec3{0,1,0};
    Vec3 x = normalized(cross(ref, z));
    if (lengthSq(x) < 1.0e-7f) x = {1,0,0};
    Vec3 y = normalized(cross(z, x));

    const float c = std::cos(rollRadians);
    const float s = std::sin(rollRadians);
    const Vec3 xr = x*c + y*s;
    const Vec3 yr = y*c - x*s;

    Mat3 out{};
    out.m[0][0]=xr.x; out.m[1][0]=xr.y; out.m[2][0]=xr.z;
    out.m[0][1]=yr.x; out.m[1][1]=yr.y; out.m[2][1]=yr.z;
    out.m[0][2]=z.x;  out.m[1][2]=z.y;  out.m[2][2]=z.z;
    return out;
}

struct RigidTransform {
    Vec3 translation{};
    Mat3 rotation{};
    float scale{1.0f};
};

inline Vec3 localToWorldPoint(const RigidTransform& t, Vec3 local) {
    const float s = (std::fabs(t.scale) > 1.0e-7f) ? t.scale : 1.0f;
    return t.translation + mul(t.rotation, local * s);
}

inline Vec3 worldToLocalPoint(const RigidTransform& t, Vec3 world) {
    const float s = (std::fabs(t.scale) > 1.0e-7f) ? t.scale : 1.0f;
    return mul(transpose(t.rotation), world - t.translation) / s;
}

inline Mat3 worldToLocalRotation(const RigidTransform& parent, const Mat3& worldRotation) {
    return mul(transpose(parent.rotation), worldRotation);
}

inline Mat3 localToWorldRotation(const RigidTransform& parent, const Mat3& localRotation) {
    return mul(parent.rotation, localRotation);
}

inline bool approximatelyOrthonormal(const Mat3& m, float eps=1.0e-4f) {
    const Vec3 x=column(m,0), y=column(m,1), z=column(m,2);
    return std::fabs(length(x)-1.0f)<eps && std::fabs(length(y)-1.0f)<eps &&
           std::fabs(length(z)-1.0f)<eps && std::fabs(dot(x,y))<eps &&
           std::fabs(dot(x,z))<eps && std::fabs(dot(y,z))<eps;
}

} // namespace cms
