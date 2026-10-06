#pragma once

#include <array>
#include <cstdint>
#include <random>

namespace cms {

// An equipment decision is valid only after a real iron-ball collision has been
// attributed by the native physics adapter. A generic TESHitEvent, proximity to
// the head, and HIGGS' anonymous collision callback do not establish that fact.
enum class EquipmentContactPart : std::uint8_t {
    kUnknown,
    kHead,
    kLeftWeapon,
    kRightWeapon,
};

enum class EquipmentDropDecision : std::uint8_t {
    kUnverifiedContact,
    kWrongSession,
    kInvalidIdentity,
    kDuplicateImpact,
    kNotEnemy,
    kNoEligibleEquipment,
    kKeptByChance,
    kDrop,
};

struct EquipmentImpactEvidence {
    std::uint64_t session{};
    // Strictly increasing within each source hand and session. The physics
    // collector must reuse this serial for every callback from one impact,
    // including contact persistence. A new frame is NOT a new impact.
    std::uint64_t impactSerial{};
    // Identity of the actual hkpRigidBody that produced the contact. Never
    // populated from a weapon form ID, TESHitEvent, or graphical Ni node.
    std::uintptr_t contactSourceBody{};
    std::uint32_t targetActor{};
    std::uint32_t equippedBaseForm{};
    std::uintptr_t equippedInstance{};
    EquipmentContactPart part{EquipmentContactPart::kUnknown};
    std::uint8_t sourceHand{};  // 0 = right, 1 = left
    bool verifiedIronBallContact{};
    bool enemyOfPlayer{};
    bool exactInstanceStillEquipped{};
    bool droppable{};
};

class EquipmentDropPolicy {
public:
    // Advance the generation on load/new game and body ownership changes. Old
    // queued contacts then fail closed even if an actor/form ID gets reused.
    void beginSession(std::uint64_t generation, std::uintptr_t rightHeadBody,
                      std::uintptr_t leftHeadBody) noexcept
    {
        session_ = generation;
        lastSerial_ = {};
        headBodies_ = {rightHeadBody, leftHeadBody};
        if (rightHeadBody != 0 && rightHeadBody == leftHeadBody) headBodies_ = {};
    }

    template <class UniformRandomBitGenerator>
    EquipmentDropDecision evaluate(const EquipmentImpactEvidence& impact,
                                   UniformRandomBitGenerator& generator)
    {
        if (!impact.verifiedIronBallContact) {
            return EquipmentDropDecision::kUnverifiedContact;
        }
        if (session_ == 0 || impact.session != session_) {
            return EquipmentDropDecision::kWrongSession;
        }
        if (impact.sourceHand >= lastSerial_.size() || impact.impactSerial == 0 ||
            impact.targetActor == 0 ||
            (impact.part != EquipmentContactPart::kHead &&
             impact.part != EquipmentContactPart::kLeftWeapon &&
             impact.part != EquipmentContactPart::kRightWeapon)) {
            return EquipmentDropDecision::kInvalidIdentity;
        }
        if (impact.contactSourceBody == 0 ||
            impact.contactSourceBody != headBodies_[impact.sourceHand]) {
            return EquipmentDropDecision::kUnverifiedContact;
        }
        auto& last = lastSerial_[impact.sourceHand];
        if (impact.impactSerial <= last) {
            return EquipmentDropDecision::kDuplicateImpact;
        }
        // Consume this impact even when it finds no droppable equipment or its
        // random draw fails. Persistent contact may never grant another roll.
        last = impact.impactSerial;
        if (!impact.enemyOfPlayer) {
            return EquipmentDropDecision::kNotEnemy;
        }
        if (impact.equippedBaseForm == 0 || impact.equippedInstance == 0 ||
            !impact.exactInstanceStillEquipped || !impact.droppable) {
            return EquipmentDropDecision::kNoEligibleEquipment;
        }
        // uniform_int_distribution uses rejection as necessary, unlike % 3 on
        // a general RNG range. Each eligible, distinct impact has exactly 1/3
        // probability; it is not a guaranteed drop every third impact.
        return std::uniform_int_distribution<unsigned>{0, 2}(generator) == 0
            ? EquipmentDropDecision::kDrop
            : EquipmentDropDecision::kKeptByChance;
    }

private:
    std::uint64_t session_{};
    std::array<std::uint64_t, 2> lastSerial_{};
    std::array<std::uintptr_t, 2> headBodies_{};
};

} // namespace cms
