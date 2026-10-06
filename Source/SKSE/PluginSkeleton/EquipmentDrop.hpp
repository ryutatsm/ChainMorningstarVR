#pragma once

#include "../EquipmentDropCore.hpp"

#include <RE/Skyrim.h>
#include <cstdint>

namespace cms::skyrimvr {

// Integration boundary, deliberately NOT an ordinary hit-event listener.
// The native contact collector must first prove that its CMS iron-ball body
// touched the named enemy part, and supply one serial per physical impact.
struct ConfirmedEquipmentImpact {
    EquipmentImpactEvidence evidence{};
    RE::ActorHandle target{};
    RE::FormID sourceWeapon{};
    RE::NiPoint3 contactPosition{};  // Skyrim world units, captured at contact
    // Captured by the game-thread equipment snapshot before the physical step.
    // A fatal physical hit may complete before the queued drop is handled.
    bool enemyAliveAtImpact{};
};

struct WornEquipmentInstance {
    RE::FormID baseForm{};
    // Identity only. Never dereference a stored value; resolve it in inventory
    // again immediately before mutation. No extra-list pointer crosses threads.
    std::uintptr_t instance{};
};

// Game thread only. Head requests may omit baseForm to choose the currently
// worn head/hair/circlet item, in that priority order. Ambiguous worn instances
// are rejected. Weapon requests identify both the hand and base form.
[[nodiscard]] WornEquipmentInstance ResolveWornEquipment(
    RE::Actor& actor, EquipmentContactPart part, RE::FormID baseForm = 0);

struct EquipmentDropResult {
    EquipmentDropDecision decision{EquipmentDropDecision::kUnverifiedContact};
    RE::ObjectRefHandle droppedObject{};
};

// These calls MUST run on the game thread, never inside a Havok callback.
// Session values must be nonzero and unique across world/body lifetimes.
// Identities are the owned hkpRigidBody pointers for each iron ball, never
// HIGGS' handle collider or a visual node. A missing hand uses zero.
void BeginEquipmentDropSession(std::uint64_t generation,
                               std::uintptr_t rightHeadBody,
                               std::uintptr_t leftHeadBody);

// Rechecks actor hostility, source weapon, hand, equipment base and exact extra
// list identity immediately before mutation. It removes ONE actual instance
// through Skyrim's drop path: no PlaceAtMe duplication and no base-form-only
// replacement that loses tempering, custom enchantment or ownership data.
[[nodiscard]] EquipmentDropResult TryDropForConfirmedImpact(
    const ConfirmedEquipmentImpact& impact);

} // namespace cms::skyrimvr
