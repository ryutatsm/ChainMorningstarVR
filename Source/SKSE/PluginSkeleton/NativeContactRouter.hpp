#pragma once

#include "EquipmentDrop.hpp"

#include <cstdint>

namespace cms::skyrimvr {

// Maps contacts using a game-thread snapshot of actual actor scene colliders.
// Havok callbacks only compare opaque body identities and copy bounded records;
// they never walk scene graphs, read inventory or dereference queued pointers.
class NativeContactRouter {
public:
    static NativeContactRouter& GetSingleton();

    // Safe at the physics boundary. Repeated registration of the same session
    // is a no-op. Equipment policy initialization is deferred to the game thread.
    void BeginSession(std::uint64_t generation, RE::hkpRigidBody* ownedBody,
                      bool left, float skyrimUnitsPerHavokUnit = 69.99125f);
    void EndSession();

    void OnContactPoint(const RE::hkpContactPointEvent& event,
                        RE::hkpRigidBody* ownedBody, bool left,
                        std::uint64_t generation, std::uint64_t physicsStep);
    void OnCollisionRemoved(const RE::hkpCollisionEvent& event,
                            RE::hkpRigidBody* ownedBody, bool left,
                            std::uint64_t generation);

    // Game thread, before the next physics step. First drains captured impacts,
    // then snapshots currently worn instances and their real colliders.
    void DrainAndRefresh();
};

// Game thread only, for the exact head-compound/equipped-weapon mesh collector.
// Its token must stay the same until geometric separation and increase for a
// new episode. Router assigns the common monotonic serial shared with Havok.
[[nodiscard]] EquipmentDropResult SubmitWeaponMeshImpact(
    const ConfirmedEquipmentImpact& request, std::uint64_t meshEpisodeToken);

} // namespace cms::skyrimvr
