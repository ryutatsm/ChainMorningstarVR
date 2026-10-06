#pragma once

#include "NativePhysicsBackend.hpp"

namespace cms::skyrimvr {

// Game-thread CPU geometry path for NPC weapons without active Havok bodies.
// Uses the actual equipped BIPOBJECT clone and actual BSTriShape triangles.
// Unsupported/GPU-only/skinned data are skipped, never replaced by proximity.
class WeaponMeshContact {
public:
    static WeaponMeshContact& GetSingleton();
    void Update(const NativeHeadSnapshot& head, float frameDeltaS, RE::FormID sourceWeapon);
    void Reset();
};

} // namespace cms::skyrimvr
