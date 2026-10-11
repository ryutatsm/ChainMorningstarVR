#pragma once
#include <RE/Skyrim.h>

namespace cms::skyrimvr {
// Game thread only, after RemoveItem returned an actual dropped reference.
// A transient visual at the captured contact; never retains the actor or 3D.
[[nodiscard]] bool PlayEquipmentDropSparks(RE::Actor& target, const RE::NiPoint3& position);
}
