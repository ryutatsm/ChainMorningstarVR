#pragma once

#include <array>
#include <cmath>
#include "ChainRuntimeCore.hpp"
#include "SceneTransformCore.hpp"

namespace cms {

constexpr float kHeadCoreRadiusM = 0.160f;
constexpr float kSpikeInnerAxisM = 0.154f;
constexpr float kSpikeOuterAxisM = 0.234f;
constexpr float kSpikeBaseRadiusM = 0.046f;
constexpr std::size_t kSpikeCount = 14;

inline constexpr float kInvSqrt3 = 0.5773502691896258f;
inline constexpr std::array<Vec3, kSpikeCount> kSpikeDirectionsLocal = {{
    { 1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0,-1, 0}, {0,0, 1}, {0,0,-1},
    { kInvSqrt3, kInvSqrt3, kInvSqrt3}, {-kInvSqrt3, kInvSqrt3, kInvSqrt3},
    { kInvSqrt3,-kInvSqrt3, kInvSqrt3}, {-kInvSqrt3,-kInvSqrt3, kInvSqrt3},
    { kInvSqrt3, kInvSqrt3,-kInvSqrt3}, {-kInvSqrt3, kInvSqrt3,-kInvSqrt3},
    { kInvSqrt3,-kInvSqrt3,-kInvSqrt3}, {-kInvSqrt3,-kInvSqrt3,-kInvSqrt3}
}};

struct SpikeProxy {
    Vec3 directionWorld{};
    Vec3 baseCenterM{};
    Vec3 tipM{};
    float baseRadiusM{kSpikeBaseRadiusM};
};

struct HeadCompoundFrame {
    Vec3 coreCenterM{};
    float coreRadiusM{kHeadCoreRadiusM};
    std::array<SpikeProxy,kSpikeCount> spikes{};
    float broadphaseRadiusM{kHeadBroadphaseRadiusM};
};

inline HeadCompoundFrame buildHeadCompoundFrame(const HeadPose& head, float axialRollRadians=0.0f) {
    HeadCompoundFrame out{};
    out.coreCenterM = head.centerM;
    const Mat3 worldR = basisFromLocalZ(head.chainAxis, axialRollRadians);
    for (std::size_t i=0; i<kSpikeCount; ++i) {
        const Vec3 d = normalized(mul(worldR, kSpikeDirectionsLocal[i]));
        out.spikes[i] = {
            d,
            head.centerM + d * kSpikeInnerAxisM,
            head.centerM + d * kSpikeOuterAxisM,
            kSpikeBaseRadiusM
        };
    }
    return out;
}

inline float supportDistanceAlongRay(const HeadCompoundFrame& h, Vec3 rayDirUnit) {
    Vec3 q = normalized(rayDirUnit);
    if (lengthSq(q)<1.0e-7f) return 0.0f;
    float best = h.coreRadiusM;
    for (const auto& s : h.spikes) {
        const float axial = dot(q, s.directionWorld);
        if (axial <= 0.0f) continue;
        const float radial = std::sqrt(std::max(0.0f, 1.0f-axial*axial));
        const float candidate = kSpikeOuterAxisM*axial + s.baseRadiusM*radial;
        best = std::max(best, candidate);
    }
    return std::min(best, h.broadphaseRadiusM);
}

} // namespace cms
