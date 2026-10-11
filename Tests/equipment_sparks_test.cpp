// Compiles the production effect adapter against a recording engine boundary.
#include "Source/SKSE/PluginSkeleton/EquipmentSparks.cpp"
#include <cassert>
#include <iostream>
#include <limits>

int main()
{
    using RE::BSTempEffectParticle;
    using cms::skyrimvr::PlayEquipmentDropSparks;
    RE::TESObjectCELL cell;
    RE::NiAVObject node;
    RE::Actor actor{&cell, &node};
    const RE::NiPoint3 hit{125.0f, -456.0f, 789.0f};
    assert(PlayEquipmentDropSparks(actor, hit));
    assert(BSTempEffectParticle::calls == 1);
    assert(BSTempEffectParticle::spawnedCell == &cell);
    assert(BSTempEffectParticle::position.x == hit.x && BSTempEffectParticle::position.y == hit.y && BSTempEffectParticle::position.z == hit.z);
    assert(BSTempEffectParticle::model == "Effects\\ImpactEffects\\FXMetalSparkImpactBlunt.nif");
    assert(BSTempEffectParticle::lifetime > 0 && BSTempEffectParticle::lifetime < 1);
    assert(BSTempEffectParticle::target == nullptr && BSTempEffectParticle::flags == 0);
    assert(BSTempEffectParticle::scale == 1.0f);

    // Invalid coordinates must never reach the engine particle allocator.
    for (float invalid : {std::numeric_limits<float>::quiet_NaN(),
                          std::numeric_limits<float>::infinity(),
                          -std::numeric_limits<float>::infinity()}) {
        assert(!PlayEquipmentDropSparks(actor, {invalid, 0, 0}));
        assert(!PlayEquipmentDropSparks(actor, {0, invalid, 0}));
        assert(!PlayEquipmentDropSparks(actor, {0, 0, invalid}));
    }
    actor.cell = nullptr;
    assert(!PlayEquipmentDropSparks(actor, hit));
    actor.cell = &cell; cell.attached = false;
    assert(!PlayEquipmentDropSparks(actor, hit));
    cell.attached = true; actor.node = nullptr;
    assert(!PlayEquipmentDropSparks(actor, hit));
    assert(BSTempEffectParticle::calls == 1);

    // Resource allocation failure has no retry, persistent state or attachment.
    actor.node = &node; BSTempEffectParticle::accept = false;
    assert(!PlayEquipmentDropSparks(actor, hit));
    assert(BSTempEffectParticle::calls == 2);
    BSTempEffectParticle::accept = true;
    assert(PlayEquipmentDropSparks(actor, {-5, 10, 0}));
    assert(BSTempEffectParticle::calls == 3 && BSTempEffectParticle::position.x == -5);
    std::cout << "PASS: production spark adapter; world position, transient lifetime, no attachment, unloaded/nonfinite rejection, allocation failure\n";
}
