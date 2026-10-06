#pragma once

#include <RE/Skyrim.h>
#include "../ChainPhysicsCore.hpp"

namespace cms::skyrimvr {

// Caller holds the world's read lock and certifies the active HIGGS head.
// Synchronous queries only: no inserted bodies, constraints, contact listeners,
// impulses, native damage, or equipment-drop notifications for chain links.
void QueryNativeChainCollisions(RE::hkpWorld* world, const RE::hkpRigidBody* head,
    float havokUnitsPerMeter, const std::vector<ChainLinkSweep>& sweeps,
    std::vector<ChainLinkContact>& contacts);

} // namespace cms::skyrimvr
