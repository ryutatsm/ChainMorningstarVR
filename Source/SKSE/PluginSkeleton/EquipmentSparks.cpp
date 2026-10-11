#include "EquipmentSparks.hpp"
#include <cmath>

namespace cms::skyrimvr {
bool PlayEquipmentDropSparks(RE::Actor& target, const RE::NiPoint3& position)
{
    if (!std::isfinite(position.x) || !std::isfinite(position.y) || !std::isfinite(position.z))
        return false;
    auto* cell = target.GetParentCell();
    if (!cell || !cell->IsAttached() || !target.Get3D()) return false;

    // Vanilla Skyrim.esm WPNBluntVsMetalImpact (0004BB53) uses this model.
    // Spawn only its short particle burst: no impact sound, decal, hazard,
    // hit event or persistent placed reference. Keep the approved disarm cue.
    // A literal keeps the async model-name storage alive. No target attachment
    // means the effect stays at the hit instead of following the falling item.
    constexpr auto model = "Effects\\ImpactEffects\\FXMetalSparkImpactBlunt.nif";
    const RE::NiPoint3 rotation{0.0f, 0.0f, 0.0f};
    return RE::BSTempEffectParticle::Spawn(cell, 0.35f, model, rotation, position,
                                         1.0f, 0, nullptr) != nullptr;
}
}
