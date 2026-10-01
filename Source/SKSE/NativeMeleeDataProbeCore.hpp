#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace cms {

struct NativeVRMeleeDataProbeLayout {
    std::array<std::byte,0x10> pad00{};
    std::uintptr_t world{};
    std::uintptr_t collisionNode{};
    std::uintptr_t offsetNode{};
    std::array<std::byte,0x7C> pad28{};
    float linearVelocityThreshold{};
    std::array<std::byte,0x14> padA8{};
    std::uint8_t enableCollision{};
    std::uint8_t applyImpulseOnHit{};
    std::array<std::byte,2> padBE{};
    std::uint32_t swingDirection{};
    float cooldown{};
    float duration{};
    std::uint32_t unkCC{};
};
static_assert(offsetof(NativeVRMeleeDataProbeLayout, world)==0x10);
static_assert(offsetof(NativeVRMeleeDataProbeLayout, collisionNode)==0x18);
static_assert(offsetof(NativeVRMeleeDataProbeLayout, offsetNode)==0x20);
static_assert(offsetof(NativeVRMeleeDataProbeLayout, linearVelocityThreshold)==0xA4);
static_assert(offsetof(NativeVRMeleeDataProbeLayout, enableCollision)==0xBC);
static_assert(sizeof(NativeVRMeleeDataProbeLayout)==0xD0);

inline constexpr std::size_t kPlanckRightVRMeleeDataOffset = 0x710;
inline constexpr std::size_t kPlanckLeftVRMeleeDataOffset = 0x710 + 0xD0;

enum class NativeMeleeProbeStatus : std::uint8_t {
    kPlausible,
    kNullWorld,
    kNullCollisionNode,
    kOffsetNodeMismatch,
    kInvalidThreshold,
    kInvalidCollisionFlag,
    kInvalidImpulseFlag,
    kInvalidSwingDirection
};

struct NativeMeleeProbeResult {
    NativeMeleeProbeStatus status{NativeMeleeProbeStatus::kNullWorld};
    std::uintptr_t world{};
    std::uintptr_t collisionNode{};
    std::uintptr_t offsetNode{};
    float linearVelocityThreshold{};
    bool enableCollision{};
    bool applyImpulseOnHit{};

    [[nodiscard]] bool plausible() const noexcept { return status==NativeMeleeProbeStatus::kPlausible; }
};

inline NativeMeleeProbeResult inspectNativeMeleeDataReadOnly(
    const NativeVRMeleeDataProbeLayout& d,
    std::uintptr_t expectedOffsetNode) noexcept
{
    NativeMeleeProbeResult r{};
    r.world=d.world;
    r.collisionNode=d.collisionNode;
    r.offsetNode=d.offsetNode;
    r.linearVelocityThreshold=d.linearVelocityThreshold;
    r.enableCollision=d.enableCollision!=0;
    r.applyImpulseOnHit=d.applyImpulseOnHit!=0;

    if (!d.world) { r.status=NativeMeleeProbeStatus::kNullWorld; return r; }
    if (!d.collisionNode) { r.status=NativeMeleeProbeStatus::kNullCollisionNode; return r; }
    if (!expectedOffsetNode || d.offsetNode!=expectedOffsetNode) {
        r.status=NativeMeleeProbeStatus::kOffsetNodeMismatch; return r;
    }
    if (!std::isfinite(d.linearVelocityThreshold) || d.linearVelocityThreshold<0.0f || d.linearVelocityThreshold>100.0f) {
        r.status=NativeMeleeProbeStatus::kInvalidThreshold; return r;
    }
    if (d.enableCollision>1) { r.status=NativeMeleeProbeStatus::kInvalidCollisionFlag; return r; }
    if (d.applyImpulseOnHit>1) { r.status=NativeMeleeProbeStatus::kInvalidImpulseFlag; return r; }
    if (d.swingDirection==2 || d.swingDirection>6) {
        r.status=NativeMeleeProbeStatus::kInvalidSwingDirection; return r;
    }
    r.status=NativeMeleeProbeStatus::kPlausible;
    return r;
}

} // namespace cms
