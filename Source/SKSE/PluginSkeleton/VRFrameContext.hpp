#pragma once
#include <RE/Skyrim.h>

namespace cms::skyrimvr {
// Read-only Skyrim VR 1.4.15 globals. PluginSkeleton rejects any other runtime.
// HIGGS 93bf67b src/RE/offsets.cpp: g_deltaTime.
inline float VRFrameDelta() {
    return *reinterpret_cast<const float*>(REL::Module::get().base() + 0x1EC8278);
}
// SKSEVR (Odie/sksevr-mirror 7ed497e), skse64/GameInput.cpp:
// g_leftHandedMode. HIGGS Hand::GetWeaponNode uses the same XOR mapping.
inline bool VRLeftHandedMode() {
    return *reinterpret_cast<const bool*>(REL::Module::get().base() + 0x1E71778);
}
inline bool InventoryLeftHand(bool physicalLeft) {
    return physicalLeft != VRLeftHandedMode();
}
} // namespace cms::skyrimvr
