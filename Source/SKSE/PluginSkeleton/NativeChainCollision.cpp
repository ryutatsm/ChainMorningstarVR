#include "NativeChainCollision.hpp"

#include <REL/Relocation.h>
#include <array>
#include <cstddef>
#include <cstring>
#include <limits>

namespace cms::skyrimvr {
namespace {

Vec3 xyz(const RE::hkVector4& v) {
    alignas(16) float a[4]; _mm_store_ps(a, v.quad); return {a[0],a[1],a[2]};
}
float componentW(const RE::hkVector4& v) {
    alignas(16) float a[4]; _mm_store_ps(a, v.quad); return a[3];
}
RE::hkVector4 hk(Vec3 v) { return {v.x,v.y,v.z,0}; }

// CommonLib 67ba410 (3.5.2) declares capsule virtual methods without linkable
// definitions. An owned, aligned descriptor supplies the game's capsule vtable
// and the exact named layout. It lives only during this synchronous query; it
// is never registered, retained, ref-counted, or destroyed by Havok. No engine
// object or HIGGS picking shape is modified. All entry points are VR 1.4.15-only.
struct alignas(16) QueryCapsuleABI {
    std::uintptr_t vtable{};                  // 00 hkBaseObject
    std::uint16_t memSizeAndFlags{};          // 08 hkReferencedObject (external storage)
    std::int16_t referenceCount{1};          // 0A
    std::uint32_t pad0C{};
    RE::bhkShape* userData{};                 // 10 hkpShape
    RE::hkpShapeType type{RE::hkpShapeType::kCapsule}; // 18
    std::uint32_t pad1C{};
    float radius{};                          // 20 hkpConvexShape
    std::uint32_t pad24{}, pad28{}, pad2C{};
    RE::hkVector4 vertexA{}, vertexB{};       // 30, 40 hkpCapsuleShape
};
static_assert(sizeof(QueryCapsuleABI) == sizeof(RE::hkpCapsuleShape));
static_assert(alignof(QueryCapsuleABI) == 16);
static_assert(offsetof(QueryCapsuleABI, radius) == 0x20);
static_assert(offsetof(QueryCapsuleABI, vertexA) == 0x30);
static_assert(offsetof(QueryCapsuleABI, vertexB) == 0x40);
static_assert(sizeof(RE::hkpCollidable) == 0x70);
static_assert(sizeof(RE::hkpCollisionInput) == 0x60);

// Same three virtual slots and base layout as CommonLib's
// hkpCdPointCollector; avoids its undeclared imported destructor/Reset body.
class CollectorABI {
public:
    virtual ~CollectorABI() = default;
    virtual void AddCdPoint(const RE::hkpCdPoint&) = 0;
    virtual void Reset() { earlyOutDistance = std::numeric_limits<float>::max(); }
    float earlyOutDistance{std::numeric_limits<float>::max()};
    std::uint32_t padding{};
};
static_assert(sizeof(CollectorABI) == sizeof(RE::hkpCdPointCollector));

const RE::hkpRigidBody* otherBody(const RE::hkpCdBody* body, const RE::hkpRigidBody* head) {
    if (!body) return nullptr;
    std::size_t depth = 0;
    while (body->parent && depth++ < 64) body = body->parent;
    if (body->parent) return nullptr;
    const auto* collidable = static_cast<const RE::hkpCollidable*>(body);
    if (collidable == &head->collidable || collidable->broadPhaseHandle.type !=
        static_cast<std::int8_t>(RE::hkpWorldObject::BroadPhaseType::kEntity)) return nullptr;
    const auto info = collidable->broadPhaseHandle.collisionFilterInfo;
    const auto playerGroup = head->collidable.broadPhaseHandle.collisionFilterInfo >> 16;
    if (playerGroup && (info >> 16) == playerGroup) return nullptr;
    const auto layer = static_cast<RE::COL_LAYER>(info & 0x7F);
    if (layer == RE::COL_LAYER::kNonCollidable || layer == RE::COL_LAYER::kTrigger ||
        layer == RE::COL_LAYER::kWater || layer == RE::COL_LAYER::kCharController) return nullptr;
    const auto* other = collidable->GetOwner<RE::hkpRigidBody>();
    if (!other || other == head || other->world != head->world) return nullptr;
    // PLANCK's actual ragdoll bodies are accepted. Exclude the player's own
    // body/hands even when another mod uses a different collision group.
    if (other->motion.type != RE::hkpMotion::MotionType::kFixed) {
        using GetReference = RE::TESObjectREFR*(*)(const RE::hkpCollidable*);
        const auto getReference = reinterpret_cast<GetReference>(REL::Module::get().base() + 0x3B4940);
        if (getReference(collidable) == RE::PlayerCharacter::GetSingleton()) return nullptr;
    }
    return other;
}

struct QueryHit {
    ChainLinkContact contact{};
    float order{};
};

class LinkCollector final : public CollectorABI {
public:
    LinkCollector(const RE::hkpRigidBody* source, const ChainLinkSweep& link,
                  float scale, float inflatedRadiusM, bool isCast)
        : head(source), sweep(link), units(scale), radiusM(inflatedRadiusM), cast(isCast) {
        if (cast) earlyOutDistance = 1.0f;
    }
    void AddCdPoint(const RE::hkpCdPoint& point) override {
        const auto* other = otherBody(point.cdBodyB, head);
        if (!other) return;
        const Vec3 n = normalized(xyz(point.contact.separatingNormal));
        const Vec3 p = xyz(point.contact.position);
        const float value = componentW(point.contact.separatingNormal);
        if (!isFinite(n) || !isFinite(p) || !std::isfinite(value) || lengthSq(n) < 0.5f) return;
        Vec3 centerLimit{};
        const Vec3 delta = sweep.toM - sweep.fromM;
        if (cast) {
            // Cast w is a fraction, not a world-space penetration distance.
            if (value < 0 || value > 1 || dot(delta,n) >= -1.0e-8f) return;
            centerLimit = lerp(sweep.fromM,sweep.toM,value);
        } else {
            const float distance = value / units;
            if (distance > 0.002f || distance < -0.4f) return;
            centerLimit = sweep.fromM - n * distance;
        }
        const float support = radiusM + sweep.halfSegmentM * std::fabs(dot(sweep.fromAxis,n));
        Vec3 velocity{};
        if (other->motion.type != RE::hkpMotion::MotionType::kFixed)
            velocity = (xyz(other->motion.linearVelocity) + cross(xyz(other->motion.angularVelocity),
                p - xyz(other->motion.motionState.sweptTransform.centerOfMass1))) / units;
        if (!isFinite(velocity) || lengthSq(velocity) > 2500.0f) return;
        QueryHit hit{{sweep.linkIndex,centerLimit - n*support,n,velocity,
                      reinterpret_cast<std::uintptr_t>(other)},value};
        // Bound triangle/manifold output while retaining distinct corner faces.
        for (std::size_t i = 0; i < count; ++i) {
            if (hits[i].contact.otherBodyIdentity == hit.contact.otherBodyIdentity &&
                dot(hits[i].contact.normalWorld,n) > 0.995f) {
                if (hit.order < hits[i].order) hits[i] = hit;
                return;
            }
        }
        if (count < hits.size()) hits[count++] = hit;
        else {
            auto worst = std::max_element(hits.begin(),hits.end(),[](const auto& a,const auto& b) {return a.order < b.order;});
            if (hit.order < worst->order) *worst = hit;
        }
    }
    void append(std::vector<ChainLinkContact>& output) {
        std::sort(hits.begin(),hits.begin()+static_cast<std::ptrdiff_t>(count),
            [](const auto& a,const auto& b) {return a.order < b.order;});
        for (std::size_t i = 0; i < count; ++i) output.push_back(hits[i].contact);
    }
private:
    const RE::hkpRigidBody* head{};
    const ChainLinkSweep& sweep;
    float units{}, radiusM{};
    bool cast{};
    std::array<QueryHit,3> hits{};
    std::size_t count{};
};

} // namespace

void QueryNativeChainCollisions(RE::hkpWorld* world, const RE::hkpRigidBody* head,
    float units, const std::vector<ChainLinkSweep>& sweeps,
    std::vector<ChainLinkContact>& contacts) {
    if (!world || !head || head->world != world || !world->collisionInput ||
        !std::isfinite(units) || units <= 0 || sweeps.size() > 64) return;
    // Pinned HIGGS 93bf67b, include/RE/offsets.h and src/RE/offsets.cpp.
    using LinearCast = void(*)(RE::hkpWorld*,const RE::hkpCollidable*,
        const RE::hkpLinearCastInput*,CollectorABI*,CollectorABI*);
    using Closest = void(*)(RE::hkpWorld*,const RE::hkpCollidable*,
        const RE::hkpCollisionInput*,CollectorABI*);
    const auto linearCast = reinterpret_cast<LinearCast>(REL::Module::get().base()+0xAB5EC0);
    const auto closest = reinterpret_cast<Closest>(REL::Module::get().base()+0xAB62D0);
    RE::hkpCollisionInput nearInput{};
    // hkpProcessCollisionInput begins with hkpCollisionInput. CommonLib exposes
    // only its forward declaration, so copy this documented base, not a cast
    // through an incomplete type or a modification to the world's tolerance.
    std::memcpy(&nearInput,world->collisionInput,sizeof(nearInput));
    if (!nearInput.dispatcher || !nearInput.filter) return;
    nearInput.tolerance = 0.0015f * units;
    for (const auto& link : sweeps) {
        if (!isFinite(link.fromM) || !isFinite(link.toM) || !isFinite(link.fromAxis) ||
            !isFinite(link.toAxis) || !std::isfinite(link.radiusM) || !std::isfinite(link.halfSegmentM) ||
            lengthSq(link.fromAxis) < 0.5f || lengthSq(link.fromAxis) > 1.5f ||
            lengthSq(link.toAxis) < 0.5f || lengthSq(link.toAxis) > 1.5f ||
            link.radiusM <= 0 || link.radiusM > 0.6f || link.halfSegmentM <= 0 || link.halfSegmentM > 0.6f ||
            lengthSq(link.toM-link.fromM) > 4.0f) continue;
        // A capsule is axis-symmetric: choose the shorter sign-equivalent axis
        // change and inflate by the endpoint displacement to enclose rotation.
        const float turn = std::min(length(link.toAxis-link.fromAxis),length(link.toAxis+link.fromAxis));
        const float radiusM = link.radiusM + link.halfSegmentM * turn;
        QueryCapsuleABI shape{};
        shape.vtable = REL::Relocation<std::uintptr_t>{RE::VTABLE_hkpCapsuleShape[0]}.address();
        shape.radius = radiusM * units;
        // Havok capsule endpoints also encode their collision-sphere radius
        // in W. XYZ alone is sufficient for GJK support but not for every
        // sphere-based terrain agent. Keep both representations consistent.
        const Vec3 end = link.fromAxis * (link.halfSegmentM * units);
        shape.vertexA = RE::hkVector4(-end.x,-end.y,-end.z,shape.radius);
        shape.vertexB = RE::hkVector4( end.x, end.y, end.z,shape.radius);
        RE::hkTransform transform{};
        transform.rotation.col0 = RE::hkVector4(1,0,0,0);
        transform.rotation.col1 = RE::hkVector4(0,1,0,0);
        transform.rotation.col2 = RE::hkVector4(0,0,1,0);
        transform.translation = hk(link.fromM * units);
        RE::hkpCollidable query{};
        query.shape = reinterpret_cast<const RE::hkpShape*>(&shape);
        query.shapeKey = RE::HK_INVALID_SHAPE_KEY;
        query.motion = &transform;
        query.forceCollideOntoPpu = 1u << 3; // SHAPE_UNCHECKED
        query.broadPhaseHandle.type = static_cast<std::int8_t>(RE::hkpWorldObject::BroadPhaseType::kPhantom);
        query.broadPhaseHandle.ownerOffset = -0x24; // handle -> query collidable
        // Query the same physical surfaces as the certified HIGGS head. Its
        // active filter includes world geometry and PLANCK actor bodies; a
        // picking-only filter need not include every solid world layer.
        // Borrowing filter bits cannot generate attacks: this collidable is
        // never inserted into the world or dispatched to a contact listener.
        query.broadPhaseHandle.collisionFilterInfo = head->collidable.broadPhaseHandle.collisionFilterInfo;
        query.allowedPenetrationDepth = -1.0f;
        LinkCollector initial(head,link,units,radiusM,false);
        if (lengthSq(link.toM-link.fromM) > 1.0e-12f) {
            RE::hkpLinearCastInput input{};
            input.to = hk(link.toM * units);
            input.maxExtraPenetration = 0;
            input.startPointTolerance = nearInput.tolerance;
            LinkCollector cast(head,link,units,radiusM,true);
            linearCast(world,&query,&input,&cast,&initial);
            initial.append(contacts);
            cast.append(contacts);
        } else {
            // Moving actors/objects must still displace a stationary chain.
            closest(world,&query,&nearInput,&initial);
            initial.append(contacts);
        }
    }
}

} // namespace cms::skyrimvr
