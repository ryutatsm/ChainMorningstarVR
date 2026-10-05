#pragma once

#include <cstdint>

namespace cms {

enum class NativeProxyOwnershipState : std::uint8_t {
    kInactive,
    kOwnedByCms,
    kPlayerChanged,
    kCollisionChanged
};

struct NativeProxyOwnershipInput {
    bool active{};
    std::uintptr_t ownerPlayer{};
    std::uintptr_t currentPlayer{};
    std::uintptr_t cmsHeadNode{};
    std::uintptr_t currentCollisionNode{};
};

[[nodiscard]] constexpr NativeProxyOwnershipState evaluateNativeProxyOwnership(
    const NativeProxyOwnershipInput& in) noexcept
{
    if (!in.active) {
        return NativeProxyOwnershipState::kInactive;
    }
    if (!in.ownerPlayer || !in.currentPlayer || in.ownerPlayer != in.currentPlayer) {
        return NativeProxyOwnershipState::kPlayerChanged;
    }
    if (!in.cmsHeadNode || in.currentCollisionNode != in.cmsHeadNode) {
        return NativeProxyOwnershipState::kCollisionChanged;
    }
    return NativeProxyOwnershipState::kOwnedByCms;
}

} // namespace cms
