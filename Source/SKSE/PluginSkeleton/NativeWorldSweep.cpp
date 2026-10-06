#include "NativeWorldSweep.hpp"

#include <REL/Relocation.h>
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace cms::skyrimvr {
namespace {

Vec3 xyz(const RE::hkVector4& vector) {
    alignas(16) float values[4];
    _mm_store_ps(values, vector.quad);
    return {values[0], values[1], values[2]};
}

float w(const RE::hkVector4& vector) {
    alignas(16) float values[4];
    _mm_store_ps(values, vector.quad);
    return values[3];
}

// CommonLibSSE-NG 3.5.2 declares the Havok collector's destructor and Reset
// without definitions. This owned ABI adapter supplies those same three slots
// (destructor, AddCdPoint, Reset) and the same 0x10-byte base, rather than calling
// a missing imported destructor. Layout is taken from hkpCdPointCollector.h;
// query semantics and the native entry point are from pinned HIGGS 93bf67b,
// src/physics.cpp:23-50 and include/RE/offsets.h:98 / src/RE/offsets.cpp:79.
class CollectorABI {
public:
    virtual ~CollectorABI() = default;
    virtual void AddCdPoint(const RE::hkpCdPoint&) = 0;
    virtual void Reset() { earlyOutDistance = 1.0f; }

    float earlyOutDistance{1.0f};
    std::uint32_t padding{};
};
static_assert(sizeof(CollectorABI) == sizeof(RE::hkpCdPointCollector));
static_assert(sizeof(RE::hkpCdPoint) == 0x40);
static_assert(sizeof(RE::hkpLinearCastInput) == 0x20);

const RE::hkpRigidBody* fixedBody(const RE::hkpCdBody* body,
                                const RE::hkpRigidBody* head) {
    if (!body) return nullptr;
    // Lists/MOPPs hand a child body to the collector. Follow the engine-owned
    // parent chain to the root collidable before asking for its entity owner.
    std::size_t depth = 0;
    while (body->parent && depth++ < 64) body = body->parent;
    if (body->parent) return nullptr;
    const auto* collidable = static_cast<const RE::hkpCollidable*>(body);
    if (collidable == &head->collidable ||
        collidable->broadPhaseHandle.type !=
            static_cast<std::int8_t>(RE::hkpWorldObject::BroadPhaseType::kEntity)) return nullptr;
    const auto* other = collidable->GetOwner<RE::hkpRigidBody>();
    if (!other || other == head || other->world != head->world ||
        other->motion.type != RE::hkpMotion::MotionType::kFixed) return nullptr;
    return other;
}

class StaticCollector final : public CollectorABI {
public:
    StaticCollector(const RE::hkpRigidBody* source, Vec3 movement, bool startPoints)
        : head(source), delta(movement), isStart(startPoints) {}

    void AddCdPoint(const RE::hkpCdPoint& point) override {
        const auto* other = fixedBody(point.cdBodyB, head);
        if (!other) return;
        const Vec3 n = normalized(xyz(point.contact.separatingNormal));
        const Vec3 p = xyz(point.contact.position);
        const float distance = w(point.contact.separatingNormal);
        if (!isFinite(n) || !isFinite(p) || !std::isfinite(distance) ||
            lengthSq(n) < 0.5f) return;
        if (isStart) {
            // The start collector reports actual penetration distance, whereas
            // the cast collector reports a dimensionless fraction of the path.
            if (distance >= 0.0f || (hasHit && distance >= nearest)) return;
        } else {
            if (distance < 0.0f || distance > 1.0f ||
                dot(delta, n) >= -1.0e-7f || (hasHit && distance >= nearest)) return;
            earlyOutDistance = distance;
        }
        hasHit = true;
        nearest = distance;
        normal = n;
        position = p;
        identity = reinterpret_cast<std::uintptr_t>(other);
    }

    void Reset() override {
        CollectorABI::Reset();
        hasHit = false;
        nearest = 1.0f;
        normal = {};
        position = {};
        identity = 0;
    }

    const RE::hkpRigidBody* head{};
    Vec3 delta{};
    bool isStart{};
    bool hasHit{};
    float nearest{1.0f};
    Vec3 normal{}, position{};
    std::uintptr_t identity{};
};

} // namespace

NativeWorldSweepResult SweepNativeHeadAgainstStaticWorld(
    RE::hkpWorld* world, RE::hkpRigidBody* head,
    const RE::hkVector4& targetHavok, float units, std::uint64_t physicsStep) {
    NativeWorldSweepResult result{};
    result.safeTargetHavok = targetHavok;
    if (!world || !head || head->world != world || !head->collidable.shape ||
        !physicsStep || !std::isfinite(units) || units <= 0.0f) return result;
    const Vec3 start = xyz(head->motion.motionState.transform.translation);
    const Vec3 target = xyz(targetHavok);
    const Vec3 delta = target - start;
    if (!isFinite(start) || !isFinite(target) || lengthSq(delta) < 1.0e-12f) return result;

    RE::hkpLinearCastInput input{};
    input.to = targetHavok;
    input.maxExtraPenetration = 0.0f;
    input.startPointTolerance = 0.0005f * units;
    StaticCollector cast(head, delta, false);
    StaticCollector initial(head, delta, true);
    using LinearCast = void(*)(RE::hkpWorld*, const RE::hkpCollidable*,
        const RE::hkpLinearCastInput*, CollectorABI*, CollectorABI*);
    const auto query = reinterpret_cast<LinearCast>(REL::Module::get().base() + 0xAB5EC0);
    query(world, &head->collidable, &input, &cast, &initial);

    constexpr float skinM = 0.0005f;
    const float skin = skinM * units;
    Vec3 safe = target;
    const StaticCollector* selected = nullptr;
    if (cast.hasHit) {
        // Retreat along the path just enough to preserve 0.5 mm along the hit
        // normal. The fraction is never confused with a world-space distance.
        const float approach = -dot(delta, cast.normal);
        const float fraction = std::max(0.0f, cast.nearest - skin / approach);
        safe = start + delta * fraction;
        selected = &cast;
    }
    if (initial.hasHit) {
        const float projectedSeparation = initial.nearest + dot(safe - start, initial.normal);
        if (projectedSeparation < skin) {
            safe += initial.normal * (skin - projectedSeparation);
            selected = &initial;
        }
    }
    if (!selected || !isFinite(safe)) return result;
    result.safeTargetHavok = RE::hkVector4(safe.x, safe.y, safe.z, 0.0f);
    result.hit = true;
    result.contact.physicsStep = physicsStep;
    result.contact.headCenterM = safe / units;
    result.contact.normalWorld = selected->normal;
    result.contact.headVelocityMps = xyz(head->motion.linearVelocity) / units;
    result.contact.pointM = selected->position / units;
    result.contact.signedDistanceM = 0.0f;
    result.contact.otherBodyIdentity = selected->identity;
    return result;
}

} // namespace cms::skyrimvr
