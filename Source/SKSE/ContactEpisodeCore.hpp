#pragma once

#include "EquipmentDropCore.hpp"

#include <array>
#include <cmath>
#include <cstdint>

namespace cms {

// Bounded, allocation-free episode aggregation used under the router mutex.
// Different manifold points/bodies belonging to the same equipped part share
// one opportunity. A removed/recreated manifold needs a short real separation;
// mesh and Havok reports of the same strike cannot grant two lottery draws.
class ContactEpisodeTracker {
public:
    void reset() noexcept { groups_ = {}; bodies_ = {}; }

    bool contact(std::uint8_t hand, std::uintptr_t body, std::uint32_t actor,
                 EquipmentContactPart part, double now) noexcept
    {
        if (!valid(hand, actor, part, now) || !body) return false;
        for (const auto& active : bodies_) {
            if (active.body == body && active.hand == hand) return false;
        }
        auto* group = findGroup(hand, actor, part);
        if (!group) return false;
        ActiveBody* empty = nullptr;
        for (auto& active : bodies_) if (!active.body) { empty = &active; break; }
        if (!empty) return false;
        const bool separated = group->activeBodies == 0;
        *empty = {body, hand, actor, part};
        ++group->activeBodies;
        if (!separated || now - group->lastSeparation < kSeparationSeconds ||
            now - group->lastImpact < kSeparationSeconds) return false;
        group->lastImpact = now;
        return true;
    }

    void removed(std::uint8_t hand, std::uintptr_t body, double now) noexcept
    {
        if (!body || !std::isfinite(now)) return;
        for (auto& active : bodies_) {
            if (active.body != body || active.hand != hand) continue;
            if (auto* group = findGroup(hand, active.actor, active.part)) {
                if (group->activeBodies) --group->activeBodies;
                if (!group->activeBodies) group->lastSeparation = now;
            }
            active = {};
            return;
        }
    }

    bool mesh(std::uint8_t hand, std::uint32_t actor, EquipmentContactPart part,
              std::uint64_t token, double now) noexcept
    {
        if (!valid(hand, actor, part, now) || !token) return false;
        auto* group = findGroup(hand, actor, part);
        if (!group || token <= group->lastMeshToken) return false;
        group->lastMeshToken = token; // Losing/rejected episodes are consumed too.
        if (group->activeBodies || now - group->lastImpact < kSeparationSeconds ||
            now - group->lastSeparation < kSeparationSeconds) return false;
        group->lastImpact = now;
        return true;
    }

private:
    static constexpr double kSeparationSeconds = 0.10;
    struct Group {
        std::uint32_t actor{};
        EquipmentContactPart part{};
        std::uint8_t hand{};
        std::uint16_t activeBodies{};
        std::uint64_t lastMeshToken{};
        double lastImpact{-1.0e30};
        double lastSeparation{-1.0e30};
    };
    struct ActiveBody {
        std::uintptr_t body{};
        std::uint8_t hand{};
        std::uint32_t actor{};
        EquipmentContactPart part{};
    };
    static bool valid(std::uint8_t hand, std::uint32_t actor,
                      EquipmentContactPart part, double now) noexcept
    {
        return hand < 2 && actor && std::isfinite(now) &&
            (part == EquipmentContactPart::kHead ||
             part == EquipmentContactPart::kLeftWeapon ||
             part == EquipmentContactPart::kRightWeapon);
    }
    Group* findGroup(std::uint8_t hand, std::uint32_t actor,
                     EquipmentContactPart part) noexcept
    {
        Group* empty = nullptr;
        for (auto& group : groups_) {
            if (group.actor == actor && group.hand == hand && group.part == part) return &group;
            if (!group.actor && !empty) empty = &group;
        }
        if (empty) { empty->actor = actor; empty->hand = hand; empty->part = part; }
        return empty; // Saturation fails closed until the next body/session reset.
    }
    std::array<Group, 128> groups_{};
    std::array<ActiveBody, 128> bodies_{};
};

} // namespace cms
