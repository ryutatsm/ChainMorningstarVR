#pragma once

#include <array>
#include <cmath>
#include "ChainRuntimeCore.hpp"
#include "SceneTransformCore.hpp"

namespace cms {

constexpr float kHeadCoreRadiusM = 0.160f * kModelScale;
constexpr float kSpikeInnerAxisM = 0.154f * kModelScale;
constexpr float kSpikeOuterAxisM = 0.240f * kModelScale;
constexpr float kSpikeBaseRadiusM = 0.046f * kModelScale;
constexpr std::size_t kSpikeCount = 14;

inline constexpr float kRimCos = 0.9238795325112867f;
inline constexpr float kRimSin = 0.3826834323650898f;
inline constexpr float kObliqueRim = 0.7683749084919419f;
inline constexpr float kObliqueRimHalf = 0.3841874542459709f;
inline constexpr float kObliqueRimZ = 0.6654321903845650f;
// Keep in the same order as generate_visual_nif.py: eight rim spikes, then
// three front and three rear spikes. The rim is rotated pi/8 so the -Z chain
// socket stays clear; the center of the dragon plaque also stays clear.
inline constexpr std::array<Vec3, kSpikeCount> kSpikeDirectionsLocal = {{
    {kRimCos,0,kRimSin}, {kRimSin,0,kRimCos}, {-kRimSin,0,kRimCos}, {-kRimCos,0,kRimSin},
    {-kRimCos,0,-kRimSin}, {-kRimSin,0,-kRimCos}, {kRimSin,0,-kRimCos}, {kRimCos,0,-kRimSin},
    {kObliqueRim,-0.64f,0}, {-kObliqueRimHalf,-0.64f,kObliqueRimZ},
    {-kObliqueRimHalf,-0.64f,-kObliqueRimZ},
    {kObliqueRim,0.64f,0}, {-kObliqueRimHalf,0.64f,kObliqueRimZ},
    {-kObliqueRimHalf,0.64f,-kObliqueRimZ}
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
    const Mat3 worldR = mul(head.rotation, basisFromLocalZ({0,0,1}, axialRollRadians));
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
    // This is a support-plane projection of the compound, not the distance to
    // its surface along a ray. It must not be used as a narrowphase ray hit.
    Vec3 q = normalized(rayDirUnit);
    if (lengthSq(q)<1.0e-7f) return 0.0f;
    float best = h.coreRadiusM;
    for (const auto& s : h.spikes) {
        const float axial = std::clamp(dot(q, s.directionWorld), -1.0f, 1.0f);
        const float radial = std::sqrt(std::max(0.0f, 1.0f-axial*axial));
        // A cone's support lies on either the base disk or its tip. Adding the
        // base radius at the tip (the old formula) inflated each cone to a cylinder.
        const float candidate = std::max(dot(q, s.tipM-h.coreCenterM),
            dot(q, s.baseCenterM-h.coreCenterM) + s.baseRadiusM*radial);
        best = std::max(best, candidate);
    }
    return std::min(best, h.broadphaseRadiusM);
}

} // namespace cms
