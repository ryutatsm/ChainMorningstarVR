#pragma once

#include <RE/Skyrim.h>
#include "../ChainPhysicsCore.hpp"

namespace cms::skyrimvr {

struct NativeWorldSweepResult {
    RE::hkVector4 safeTargetHavok{};
    HeadWorldContact contact{};
    bool hit{};
};

// The caller owns the world's write lock. Uses the head's actual compound and
// current rotation, with the engine's collision filter. This is a translation
// cast against fixed rigid bodies; it does not substitute a sphere for the head
// and does not generate actor damage or equipment-drop evidence.
NativeWorldSweepResult SweepNativeHeadAgainstStaticWorld(
    RE::hkpWorld* world, RE::hkpRigidBody* head,
    const RE::hkVector4& targetHavok, float havokUnitsPerMeter,
    std::uint64_t physicsStep);

} // namespace cms::skyrimvr
