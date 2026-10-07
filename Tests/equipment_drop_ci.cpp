#include "Source/SKSE/EquipmentDropCore.hpp"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>

// A complete three-value uniform generator makes exact 1/3 partitioning and
// RNG consumption observable without relying on a lucky finite random sample.
struct TernaryGenerator {
    using result_type = unsigned;
    static constexpr result_type min() { return 0; }
    static constexpr result_type max() { return 2; }
    unsigned draws{};
    result_type operator()() { return draws++ % 3; }
};

static cms::EquipmentImpactEvidence eligible(std::uint64_t serial = 1)
{
    cms::EquipmentImpactEvidence impact{};
    impact.session = 10;
    impact.impactSerial = serial;
    impact.contactSourceBody = 0xCAFE;
    impact.targetActor = 0x1234;
    impact.equippedBaseForm = 0x4567;
    impact.equippedInstance = 0x12345678;
    impact.part = cms::EquipmentContactPart::kHead;
    impact.verifiedIronBallContact = true;
    impact.enemyOfPlayer = true;
    impact.exactInstanceStillEquipped = true;
    impact.droppable = true;
    return impact;
}

int main()
{
    using Decision = cms::EquipmentDropDecision;
    cms::EquipmentDropPolicy policy;
    TernaryGenerator random;
    auto impact = eligible();

    // Disabled until a native body lifetime explicitly begins a session.
    assert(policy.evaluate(impact, random) == Decision::kWrongSession);
    assert(random.draws == 0);
    policy.beginSession(10, 0xCAFE, 0xBEEF);
    impact.verifiedIronBallContact = false;
    assert(policy.evaluate(impact, random) == Decision::kUnverifiedContact);
    assert(random.draws == 0);
    impact = eligible();
    impact.contactSourceBody = 0;
    assert(policy.evaluate(impact, random) == Decision::kUnverifiedContact);
    impact.contactSourceBody = 0xBEEF;  // other hand's body is not this weapon
    assert(policy.evaluate(impact, random) == Decision::kUnverifiedContact);
    impact.contactSourceBody = 0x9999;  // e.g. HIGGS' original handle collider
    assert(policy.evaluate(impact, random) == Decision::kUnverifiedContact);
    impact.contactSourceBody = 0xCAFE;
    assert(policy.evaluate(impact, random) == Decision::kDrop);
    for (int i = 0; i < 1000; ++i) {
        assert(policy.evaluate(impact, random) == Decision::kDuplicateImpact);
    }
    assert(random.draws == 1);

    // A losing draw also consumes the entire impact. A long manifold is not
    // another chance each frame, and changing its item does not rearm it.
    impact.impactSerial = 2;
    assert(policy.evaluate(impact, random) == Decision::kKeptByChance);
    impact.equippedInstance += 16;
    assert(policy.evaluate(impact, random) == Decision::kDuplicateImpact);
    assert(random.draws == 2);
    impact.impactSerial = 1;
    assert(policy.evaluate(impact, random) == Decision::kDuplicateImpact);

    // Both source hands have independent monotonic contact serials.
    impact.sourceHand = 1;
    impact.contactSourceBody = 0xBEEF;
    assert(policy.evaluate(impact, random) == Decision::kKeptByChance);
    impact.sourceHand = 2;
    assert(policy.evaluate(impact, random) == Decision::kInvalidIdentity);
    impact = eligible(3);
    impact.enemyOfPlayer = false;
    assert(policy.evaluate(impact, random) == Decision::kNotEnemy);
    impact.enemyOfPlayer = true;
    assert(policy.evaluate(impact, random) == Decision::kDuplicateImpact);
    assert(random.draws == 3);

    // No helmet, quest/nonplayable item, or changed equipment is a skip. An
    // invalid instance never becomes a random inventory/base-form replacement.
    for (int reason = 0; reason < 4; ++reason) {
        impact = eligible(static_cast<std::uint64_t>(reason + 4));
        if (reason == 0) impact.equippedInstance = 0;
        if (reason == 1) impact.equippedBaseForm = 0;
        if (reason == 2) impact.exactInstanceStillEquipped = false;
        if (reason == 3) impact.droppable = false;
        assert(policy.evaluate(impact, random) == Decision::kNoEligibleEquipment);
        assert(policy.evaluate(impact, random) == Decision::kDuplicateImpact);
    }
    assert(random.draws == 3);
    impact = eligible(8);
    impact.part = cms::EquipmentContactPart::kUnknown;
    assert(policy.evaluate(impact, random) == Decision::kInvalidIdentity);
    impact.part = static_cast<cms::EquipmentContactPart>(255);
    assert(policy.evaluate(impact, random) == Decision::kInvalidIdentity);
    impact = eligible(0);
    assert(policy.evaluate(impact, random) == Decision::kInvalidIdentity);
    impact = eligible(8);
    impact.targetActor = 0;
    assert(policy.evaluate(impact, random) == Decision::kInvalidIdentity);

    // Old queued contacts cannot survive world/body generation changes.
    policy.beginSession(11, 0xCAFE, 0xBEEF);
    impact = eligible(100);
    assert(policy.evaluate(impact, random) == Decision::kWrongSession);
    impact.session = 11;
    impact.impactSerial = 1;
    assert(policy.evaluate(impact, random) == Decision::kDrop);

    // Exactly one branch of the uniform three-way outcome drops. Head and
    // either hand use the same probability, with independent real impacts.
    unsigned drops = 0;
    for(auto part:{cms::EquipmentContactPart::kHead,cms::EquipmentContactPart::kLeftHand,
                   cms::EquipmentContactPart::kRightHand}) {
        policy.beginSession(10, 0xCAFE, 0xBEEF);
        random.draws = 0;
        drops=0;
        for (std::uint64_t i = 1; i <= 300; ++i) {
            impact = eligible(i);
            impact.part = part;
            drops += policy.evaluate(impact, random) == Decision::kDrop;
        }
        assert(drops == 100 && random.draws == 300);
    }

    // A real full-range RNG has the expected frequency over many distinct
    // impacts. This catches accidental always-drop / integer division errors.
    policy.beginSession(10, 0xCAFE, 0xBEEF);
    std::mt19937 engine{0xC05E};
    drops = 0;
    constexpr std::uint64_t trials = 300000;
    for (std::uint64_t i = 1; i <= trials; ++i) {
        impact = eligible(i);
        drops += policy.evaluate(impact, engine) == Decision::kDrop;
    }
    assert(std::abs(static_cast<double>(drops) / trials - 1.0 / 3.0) < 0.005);
    std::cout << "PASS: equipment drop policy; exactly 1/3 outcome mapping, one roll per impact, stale-session rejection, enemy and exact-instance gates\n";
}
