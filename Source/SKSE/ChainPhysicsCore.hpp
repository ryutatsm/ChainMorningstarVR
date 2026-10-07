#pragma once

#include "WeaponDimensions.hpp"
#include "SceneTransformCore.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace cms {

// One native Havok contact sample. All vectors are world-space metres, and
// normalWorld points from the other body towards this weapon head. The native
// bridge supplies the body's centre at the contact callback, not its requested
// (possibly already penetrating) keyframe target. signedDistanceM is Havok's
// signed contact separation: negative means penetration.
struct HeadWorldContact {
    std::uint64_t physicsStep{};
    Vec3 headCenterM{};
    Vec3 normalWorld{};
    Vec3 surfaceVelocityMps{};
    Vec3 headVelocityMps{};
    Vec3 pointM{};
    float signedDistanceM{};
    std::uintptr_t otherBodyIdentity{};
};

struct HeadContactPlane {
    Vec3 centerLimitM{};
    Vec3 normalWorld{};
    Vec3 surfaceVelocityMps{};
    std::uintptr_t otherBodyIdentity{};
    float remainingS{};
};

struct Particle {
    Vec3 position{};
    Vec3 previous{};
    float invMass{1.0f};
};

// Optional second endpoint, in world metres. Native head contacts still win
// over the hand target; holding must never push the ball through scenery.
struct HeadHoldTarget {
    Vec3 positionM{};
    bool active{};
    Mat3 rotation{};
};

// Query-only collision data. These links are never Havok attack bodies and
// never enter the head contact / damage / equipment-drop pipeline.
struct ChainLinkSweep {
    std::size_t linkIndex{};
    Vec3 fromM{}, toM{};
    Vec3 fromAxis{}, toAxis{};
    float radiusM{}, halfSegmentM{};
};

struct ChainLinkContact {
    std::size_t linkIndex{};
    Vec3 surfacePointM{}, normalWorld{}, surfaceVelocityMps{};
    std::uintptr_t otherBodyIdentity{};
};

class IChainCollisionQuery {
public:
    virtual ~IChainCollisionQuery() = default;
    virtual void queryChainContacts(const std::vector<ChainLinkSweep>&,
                                   std::vector<ChainLinkContact>&) {}
    [[nodiscard]] virtual float chainCollisionScale() const { return 1.0f; }
};

struct ChainConfig {
    std::size_t linkCount{kChainLinkCount};
    float firstLinkCenterOffsetM{kFirstLinkOffsetM};
    float linkCenterSpanM{kChainCenterSpanM};
    float headCenterOffsetFromLastLinkM{kLastLinkHeadOffsetM};

    float linkMassKg{0.22f};
    float headMassKg{12.0f};

    float dampingPer90Hz{0.995f};
    float headDampingPer90Hz{0.990f};
    float headStaticFriction{0.80f};
    float headSlidingFriction{0.55f};
    // Same enclosing capsule for all 19 links, scaled with the authored mesh.
    // The hole is intentionally solid for robust contact.
    float linkCollisionRadiusM{0.0474f * kModelScale};
    float linkCollisionHalfSegmentM{0.0234f * kModelScale};
    int solverIterations{96};
    Vec3 gravityMps2{0.0f, 0.0f, -9.80665f};
};

class ChainSolver {
public:
    explicit ChainSolver(ChainConfig cfg = {}) : cfg_(sanitize(cfg)) {
        rebuildLayout();
    }

    void reset(Vec3 anchor, Vec3 direction = {0.0f, 0.0f, -1.0f}) {
        if (!isFinite(anchor)) return;
        direction = normalized(direction);
        if (lengthSq(direction) < 1.0e-7f) direction = {0.0f, 0.0f, -1.0f};

        points_[0].position = anchor;
        points_[0].previous = anchor;
        for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c) {
            const Vec3 p = points_[c].position + direction * constraintLengthsM_[c];
            points_[c + 1].position = p;
            points_[c + 1].previous = p;
        }
        initialized_ = true;
        clearWorldContacts();
    }

    void teleport(Vec3 anchor, Vec3 direction = {0.0f, 0.0f, -1.0f}) {
        reset(anchor, direction);
    }

    void step90Hz(Vec3 anchor, IChainCollisionQuery* query = nullptr,
                  HeadHoldTarget hold = {}) {
        constexpr float dt = 1.0f / 90.0f;
        if (!isFinite(anchor)) return;
        if (!initialized_) reset(anchor);

        chainContacts_.clear();
        std::vector<Vec3> oldCenters, oldAxes;
        if (query) {
            oldCenters.reserve(linkCount()); oldAxes.reserve(linkCount());
            for (std::size_t i = 0; i < linkCount(); ++i) {
                oldCenters.push_back(pendingChainCenters_.empty() ? linkPosition(i) : pendingChainCenters_[i]);
                oldAxes.push_back(pendingChainAxes_.empty() ? linkAxis(i) : pendingChainAxes_[i]);
            }
            const float scale = query->chainCollisionScale();
            collisionScale_ = std::isfinite(scale) ? std::clamp(scale, 0.25f, 4.0f) : 1.0f;
        }
        pendingChainCenters_.clear(); pendingChainAxes_.clear();

        // Contacts are refreshed by Havok physics steps. A short bounded cache
        // bridges render/physics scheduling without keeping an infinite plane
        // after the head leaves a finite object. Advance moving surfaces once
        // per simulation step, never once per distance-constraint iteration.
        for (auto& contact : contacts_) {
            contact.centerLimitM += contact.surfaceVelocityMps * dt;
            contact.remainingS -= dt;
        }
        std::erase_if(contacts_, [](const HeadContactPlane& c) { return c.remainingS < 0.0f; });

        const Vec3 oldAnchor = points_[0].position;
        points_[0].previous = oldAnchor;
        points_[0].position = anchor;

        const bool held = hold.active && isFinite(hold.positionM) &&
            length(hold.positionM-anchor) <= straightReachM()+0.01f;
        const Vec3 oldHead = headPosition();
        const float headMass = points_.back().invMass;
        if (held) {
            points_.back().invMass = 0.0f;
            points_.back().position = hold.positionM;
            points_.back().previous = oldHead;
            projectHeadOutsideContacts();
        }

        for (std::size_t i = 1; i < points_.size(); ++i) {
            Particle& p = points_[i];
            if (p.invMass == 0.0f) continue;
            const float damp = i + 1 == points_.size() ?
                cfg_.headDampingPer90Hz : cfg_.dampingPer90Hz;
            const Vec3 velocity = (p.position - p.previous) * damp;
            p.previous = p.position;
            p.position += velocity + cfg_.gravityMps2 * (dt * dt);
        }

        solveConstraints(anchor, cfg_.solverIterations);
        if (query) {
            // Sweep after distance solving: otherwise a constraint correction
            // could drag a link straight through a thin wall. Two bounded
            // batches also cover the changed direction around an obstacle.
            for (int pass = 0; pass < 2; ++pass) {
                collectChainContacts(*query, oldCenters, oldAxes);
                if (chainContacts_.empty()) break;
                solveConstraints(anchor, cfg_.solverIterations);
            }
            constrainChainVelocities(oldAxes);
        }
        points_[0].position = anchor;
        if (!held) applySupportFriction(oldHead, dt);
        // Position constraints may pull the head back into a wall. Projection
        // keeps its centre outside; cancel only the remaining inward velocity.
        // Restitution belongs to applyWorldContacts(), once per native sample.
        Vec3 velocity = headVelocity90Hz();
        constrainContactVelocity(velocity);
        if (held && lengthSq(velocity)>64.0f) velocity = normalized(velocity)*8.0f;
        points_.back().previous = points_.back().position - velocity * dt;
        points_.back().invMass = headMass;
    }

    void clearWorldContacts() {
        contacts_.clear();
        chainContacts_.clear();
        pendingChainCenters_.clear(); pendingChainAxes_.clear();
        lastContactPhysicsStep_ = 0;
    }

    // Consume a callback batch before advancing the chain. Only the newest
    // complete physics step is used; stale/repeated steps cannot bounce the
    // head repeatedly or move it back to an earlier collision location.
    float applyWorldContacts(const std::vector<HeadWorldContact>& samples) {
        if (!initialized_ || samples.empty()) return 0.0f;
        std::uint64_t newest = lastContactPhysicsStep_;
        for (const auto& sample : samples)
            if (validContact(sample)) newest = std::max(newest, sample.physicsStep);
        if (newest <= lastContactPhysicsStep_) return 0.0f;

        std::vector<HeadContactPlane> next;
        next.reserve(kMaxContactPlanes);
        for (const auto& sample : samples) {
            if (sample.physicsStep != newest || !validContact(sample)) continue;
            const Vec3 normal = normalized(sample.normalWorld);
            const Vec3 limit = sample.headCenterM - normal * sample.signedDistanceM;
            const auto duplicate = std::find_if(next.begin(), next.end(), [&](const auto& c) {
                return c.otherBodyIdentity == sample.otherBodyIdentity &&
                    dot(c.normalWorld, normal) > 0.995f &&
                    std::fabs(dot(c.centerLimitM - limit, normal)) < 0.005f;
            });
            if (duplicate != next.end()) {
                // Multiple points on the same face describe one impulse plane.
                // Keep the most restrictive centre boundary.
                if (dot(limit - duplicate->centerLimitM, normal) > 0.0f)
                    duplicate->centerLimitM = limit;
                continue;
            }
            if (next.size() == kMaxContactPlanes) break;
            next.push_back({limit, normal, sample.surfaceVelocityMps,
                            sample.otherBodyIdentity, kContactLifetimeS});
        }
        if (next.empty()) return 0.0f;
        contacts_ = std::move(next);
        lastContactPhysicsStep_ = newest;

        Vec3 velocity = headVelocity90Hz();
        const Vec3 originalHead = headPosition();
        projectHeadOutsideContacts();
        // Projection moves previous and current positions together: recovery
        // never becomes an outward Verlet velocity, here or in fixed steps.

        float normalImpulse = 0.0f;
        for (const auto& contact : contacts_) {
            const float gap = dot(headPosition() - contact.centerLimitM, contact.normalWorld);
            if (gap > kContactSlopM * 2.0f) continue;
            const float closing = dot(velocity - contact.surfaceVelocityMps, contact.normalWorld);
            if (closing >= 0.0f) continue;
            // Low restitution suits a heavy iron head. Tangential
            // friction is Coulomb-limited, so a grazing touch cannot erase a
            // fast swing or inject energy. No engine impulse is fabricated.
            const float normalDelta = -(1.0f + kHeadRestitution) * closing;
            velocity += contact.normalWorld * normalDelta;
            const Vec3 relative = velocity - contact.surfaceVelocityMps;
            const Vec3 tangent = relative - contact.normalWorld * dot(relative, contact.normalWorld);
            const float tangentSpeed = length(tangent);
            if (tangentSpeed > 1.0e-6f)
                velocity -= tangent * (std::min(tangentSpeed, kHeadFriction * normalDelta) / tangentSpeed);
            normalImpulse += cfg_.headMassKg * normalDelta;
        }
        // Coupled contact normals (corners) must all have non-inward velocity.
        constrainContactVelocity(velocity);
        points_.back().previous = headPosition() - velocity * (1.0f / 90.0f);
        // Reconcile only actual recovery. Re-solving an already resting chain
        // on every render callback made stiffness depend on headset refresh.
        if (lengthSq(headPosition() - originalHead) > 1.0e-12f)
            reconcileLinksToCorrectedHead(originalHead);
        return normalImpulse;
    }

    [[nodiscard]] std::size_t activeContactCount() const { return contacts_.size(); }
    [[nodiscard]] std::size_t activeChainContactCount() const { return chainContacts_.size(); }
    [[nodiscard]] std::uint64_t lastContactPhysicsStep() const { return lastContactPhysicsStep_; }
    [[nodiscard]] bool headTouchesSurface() const {
        return std::any_of(contacts_.begin(),contacts_.end(),[&](const auto& c) {
            return dot(headPosition()-c.centerLimitM,c.normalWorld)<=kContactSlopM*2;
        });
    }
    [[nodiscard]] float headSurfaceSlipMps() const {
        const auto* contact = supportContact();
        if (!contact) return 0.0f;
        const Vec3 relative = headVelocity90Hz()-contact->surfaceVelocityMps;
        return length(relative-contact->normalWorld*dot(relative,contact->normalWorld));
    }

    [[nodiscard]] const ChainConfig& config() const { return cfg_; }
    [[nodiscard]] const std::vector<Particle>& points() const { return points_; }
    [[nodiscard]] const std::vector<float>& constraintLengthsM() const { return constraintLengthsM_; }

    [[nodiscard]] std::size_t linkCount() const { return cfg_.linkCount; }
    [[nodiscard]] Vec3 anchorPosition() const { return points_.front().position; }
    [[nodiscard]] Vec3 linkPosition(std::size_t i) const { return points_.at(i + 1).position; }
    [[nodiscard]] Vec3 linkAxis(std::size_t i) const {
        Vec3 axis = normalized(points_.at(i + 2).position - points_.at(i).position);
        return lengthSq(axis) > 0.5f ? axis : Vec3{0,0,1};
    }
    [[nodiscard]] Vec3 headPosition() const { return points_.back().position; }

    [[nodiscard]] Vec3 anchorVelocity90Hz() const {
        return (points_.front().position - points_.front().previous) * 90.0f;
    }

    [[nodiscard]] Vec3 linkVelocity90Hz(std::size_t i) const {
        constexpr float invDt = 90.0f;
        const Particle& p = points_.at(i + 1);
        return (p.position - p.previous) * invDt;
    }

    [[nodiscard]] Vec3 headVelocity90Hz() const {
        constexpr float invDt = 90.0f;
        return (points_.back().position - points_.back().previous) * invDt;
    }

    [[nodiscard]] float straightReachM() const {
        float s = 0.0f;
        for (float l : constraintLengthsM_) s += l;
        return s;
    }

    [[nodiscard]] float maxConstraintErrorM() const {
        float e = 0.0f;
        for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c) {
            const float d = length(points_[c + 1].position - points_[c].position);
            e = std::max(e, std::fabs(d - constraintLengthsM_[c]));
        }
        return e;
    }

private:
    static constexpr std::size_t kMaxContactPlanes = 12;
    static constexpr float kContactLifetimeS = 0.05f;
    static constexpr float kContactSlopM = 0.0005f;
    static constexpr float kHeadRestitution = 0.025f;
    static constexpr float kHeadFriction = 0.38f;
    static constexpr std::size_t kMaxContactsPerLink = 3;

    const HeadContactPlane* supportContact() const {
        const HeadContactPlane* best=nullptr;
        float load=0.0f;
        for(const auto& c:contacts_) {
            if(dot(headPosition()-c.centerLimitM,c.normalWorld)>kContactSlopM*2) continue;
            const float candidate=-dot(cfg_.gravityMps2,c.normalWorld);
            if(candidate>load) {load=candidate;best=&c;}
        }
        return best;
    }

    void applySupportFriction(Vec3 previousHead,float dt) {
        const auto* contact=supportContact();
        if(!contact || cfg_.headStaticFriction<=0.0f) return;
        const Vec3 relative=headPosition()-previousHead-contact->surfaceVelocityMps*dt;
        const Vec3 tangent=relative-contact->normalWorld*dot(relative,contact->normalWorld);
        const float distance=length(tangent);
        if(distance<=1.0e-9f) return;
        // Gravity's support load survives normal-velocity projection. Apply
        // Coulomb friction ONCE per fixed step, not per callback/manifold or
        // solver iteration. This also resists slow constraint-driven creep.
        const float load=-dot(cfg_.gravityMps2,contact->normalWorld)*dt*dt;
        const float removed=distance<=cfg_.headStaticFriction*load?distance:
            std::min(distance,cfg_.headSlidingFriction*load);
        if(removed<=0.0f) return;
        const Vec3 old=headPosition();
        points_.back().position-=tangent*(removed/distance);
        // Friction changes displacement AND velocity; unlike penetration
        // recovery it must not translate previous along with current.
        reconcileLinksToCorrectedHead(old);
    }

    float linkSupport(std::size_t i, Vec3 normal) const {
        return collisionScale_ * (cfg_.linkCollisionRadiusM +
            cfg_.linkCollisionHalfSegmentM * std::fabs(dot(linkAxis(i), normal)));
    }

    void collectChainContacts(IChainCollisionQuery& query,
                              const std::vector<Vec3>& oldCenters,
                              const std::vector<Vec3>& oldAxes) {
        std::vector<ChainLinkSweep> sweeps;
        sweeps.reserve(linkCount());
        for (std::size_t i = 0; i < linkCount(); ++i)
            sweeps.push_back({i, oldCenters[i], linkPosition(i), oldAxes[i], linkAxis(i),
                cfg_.linkCollisionRadiusM * collisionScale_,
                cfg_.linkCollisionHalfSegmentM * collisionScale_});
        std::vector<ChainLinkContact> found;
        query.queryChainContacts(sweeps, found);
        for (auto contact : found) {
            if (contact.linkIndex >= linkCount() || !contact.otherBodyIdentity ||
                !isFinite(contact.surfacePointM) || !isFinite(contact.normalWorld) ||
                !isFinite(contact.surfaceVelocityMps) ||
                lengthSq(contact.normalWorld) < 0.25f || lengthSq(contact.normalWorld) > 4.0f ||
                lengthSq(contact.surfaceVelocityMps) > 2500.0f ||
                lengthSq(contact.surfacePointM - linkPosition(contact.linkIndex)) > 4.0f) continue;
            contact.normalWorld = normalized(contact.normalWorld);
            const auto duplicate = std::find_if(chainContacts_.begin(), chainContacts_.end(), [&](const auto& c) {
                return c.linkIndex == contact.linkIndex && c.otherBodyIdentity == contact.otherBodyIdentity &&
                    dot(c.normalWorld, contact.normalWorld) > 0.995f;
            });
            if (duplicate != chainContacts_.end()) {
                if (dot(contact.surfacePointM - duplicate->surfacePointM, contact.normalWorld) > 0.0f)
                    *duplicate = contact;
            } else if (std::count_if(chainContacts_.begin(), chainContacts_.end(), [&](const auto& c) {
                return c.linkIndex == contact.linkIndex;
            }) < static_cast<std::ptrdiff_t>(kMaxContactsPerLink)) {
                chainContacts_.push_back(contact);
            }
        }
    }

    void projectChainOutsideContacts() {
        for (int pass = 0; pass < 3; ++pass) {
            for (const auto& c : chainContacts_) {
                auto& point = points_[c.linkIndex + 1];
                const float gap = dot(point.position - c.surfacePointM, c.normalWorld) -
                    linkSupport(c.linkIndex, c.normalWorld);
                if (gap < kContactSlopM) point.position += c.normalWorld * (kContactSlopM - gap);
            }
        }
    }

    void constrainChainVelocities(const std::vector<Vec3>& oldAxes) {
        for (std::size_t i = 0; i < linkCount(); ++i) {
            auto& point = points_[i + 1];
            // A moving object can overlap a previously stationary link.
            // Recover the old position as well, so depenetration itself does
            // not become a large outward Verlet velocity on the next tick.
            for (int pass = 0; pass < 4; ++pass) {
                for (const auto& c : chainContacts_) {
                    if (c.linkIndex != i) continue;
                    const float support = collisionScale_ * (cfg_.linkCollisionRadiusM +
                        cfg_.linkCollisionHalfSegmentM * std::fabs(dot(oldAxes[i], c.normalWorld)));
                    const float gap = dot(point.previous - c.surfacePointM, c.normalWorld) - support;
                    if (gap < 0) point.previous -= c.normalWorld * gap;
                }
            }
            Vec3 velocity = linkVelocity90Hz(i);
            for (int pass = 0; pass < 4; ++pass) {
                for (const auto& c : chainContacts_) {
                    if (c.linkIndex != i) continue;
                    const float gap = dot(point.position - c.surfacePointM, c.normalWorld) -
                        linkSupport(i, c.normalWorld);
                    if (gap > kContactSlopM * 2) continue;
                    const float inward = dot(velocity - c.surfaceVelocityMps, c.normalWorld);
                    if (inward < 0) {
                        velocity -= c.normalWorld * inward; // no restitution on the chain
                        if (pass == 0) {
                            const Vec3 relative = velocity - c.surfaceVelocityMps;
                            const Vec3 tangent = relative - c.normalWorld * dot(relative, c.normalWorld);
                            const float speed = length(tangent);
                            if (speed > 1.0e-6f)
                                velocity -= tangent * (std::min(speed, -inward * 0.32f) / speed);
                        }
                    }
                }
            }
            point.previous = point.position - velocity * (1.0f / 90.0f);
        }
    }

    void solveConstraints(Vec3 anchor, int iterations) {
        for (int iter = 0; iter < iterations; ++iter) {
            points_[0].position = anchor;
            if ((iter & 1) == 0) {
                for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c)
                    solveDistance(c, c + 1, constraintLengthsM_[c]);
            } else {
                for (std::size_t c = constraintLengthsM_.size(); c-- > 0;)
                    solveDistance(c, c + 1, constraintLengthsM_[c]);
            }
            projectHeadOutsideContacts();
            projectChainOutsideContacts();
        }
    }

    bool validContact(const HeadWorldContact& contact) const {
        if (contact.physicsStep == 0 || !isFinite(contact.headCenterM) ||
            !isFinite(contact.normalWorld) || !isFinite(contact.surfaceVelocityMps) ||
            !isFinite(contact.headVelocityMps) || !isFinite(contact.pointM) ||
            !std::isfinite(contact.signedDistanceM)) return false;
        const float normalLength = lengthSq(contact.normalWorld);
        return normalLength > 0.25f && normalLength < 4.0f &&
            contact.signedDistanceM >= -1.0f && contact.signedDistanceM <= 0.03f &&
            lengthSq(contact.surfaceVelocityMps) <= 2500.0f &&
            lengthSq(contact.headCenterM - headPosition()) <= 4.0f;
    }

    void projectHeadOutsideContacts() {
        // A small manifold may contain a floor/wall corner. Projection alone
        // is safe to repeat during distance solving: it never applies impulse.
        for (int pass = 0; pass < 4; ++pass) {
            for (const auto& contact : contacts_) {
                const float distance = dot(headPosition() - contact.centerLimitM, contact.normalWorld);
                if (distance < kContactSlopM) {
                    const Vec3 recovery = contact.normalWorld * (kContactSlopM - distance);
                    points_.back().position += recovery;
                    points_.back().previous += recovery;
                }
            }
        }
    }

    void constrainContactVelocity(Vec3& velocity) const {
        for (int pass = 0; pass < 4; ++pass) {
            for (const auto& contact : contacts_) {
                const float gap = dot(headPosition() - contact.centerLimitM, contact.normalWorld);
                if (gap > kContactSlopM * 2.0f) continue;
                const float inward = dot(velocity - contact.surfaceVelocityMps, contact.normalWorld);
                if (inward < 0.0f) velocity -= contact.normalWorld * inward;
            }
        }
    }

    void reconcileLinksToCorrectedHead(Vec3 originalHead) {
        // A late head correction also moves its links. The next query must
        // sweep that recovery path, not start on the far side of a thin wall.
        if (pendingChainCenters_.empty()) {
            for (std::size_t i = 0; i < linkCount(); ++i) {
                pendingChainCenters_.push_back(linkPosition(i));
                pendingChainAxes_.push_back(i + 1 == linkCount() ?
                    normalized(originalHead - points_[i].position) : linkAxis(i));
            }
        }
        std::vector<Vec3> before;
        before.reserve(points_.size());
        for (const auto& point : points_) before.push_back(point.position);
        const float headInvMass = points_.back().invMass;
        points_.back().invMass = 0.0f;
        for (int iteration = 0; iteration < cfg_.solverIterations; ++iteration) {
            if ((iteration & 1) == 0) {
                for (std::size_t c = 0; c < constraintLengthsM_.size(); ++c)
                    solveDistance(c, c + 1, constraintLengthsM_[c]);
            } else {
                for (std::size_t c = constraintLengthsM_.size(); c-- > 0;)
                    solveDistance(c, c + 1, constraintLengthsM_[c]);
            }
        }
        points_.back().invMass = headInvMass;
        // This is sample reconciliation, not elapsed simulation time. Retain
        // each link's velocity while moving its previous position by the same
        // correction; the following simulation step transmits chain tension.
        for (std::size_t i = 1; i + 1 < points_.size(); ++i)
            points_[i].previous += points_[i].position - before[i];
    }

    static ChainConfig sanitize(ChainConfig cfg) {
        const ChainConfig defaults{};
        if (!std::isfinite(cfg.firstLinkCenterOffsetM)) cfg.firstLinkCenterOffsetM = defaults.firstLinkCenterOffsetM;
        if (!std::isfinite(cfg.linkCenterSpanM)) cfg.linkCenterSpanM = defaults.linkCenterSpanM;
        if (!std::isfinite(cfg.headCenterOffsetFromLastLinkM)) cfg.headCenterOffsetFromLastLinkM = defaults.headCenterOffsetFromLastLinkM;
        if (!std::isfinite(cfg.linkMassKg)) cfg.linkMassKg = defaults.linkMassKg;
        if (!std::isfinite(cfg.headMassKg)) cfg.headMassKg = defaults.headMassKg;
        if (!std::isfinite(cfg.dampingPer90Hz)) cfg.dampingPer90Hz = defaults.dampingPer90Hz;
        if (!std::isfinite(cfg.headDampingPer90Hz)) cfg.headDampingPer90Hz = defaults.headDampingPer90Hz;
        if (!std::isfinite(cfg.headStaticFriction)) cfg.headStaticFriction = defaults.headStaticFriction;
        if (!std::isfinite(cfg.headSlidingFriction)) cfg.headSlidingFriction = defaults.headSlidingFriction;
        if (!std::isfinite(cfg.linkCollisionRadiusM)) cfg.linkCollisionRadiusM = defaults.linkCollisionRadiusM;
        if (!std::isfinite(cfg.linkCollisionHalfSegmentM)) cfg.linkCollisionHalfSegmentM = defaults.linkCollisionHalfSegmentM;
        if (!isFinite(cfg.gravityMps2)) cfg.gravityMps2 = defaults.gravityMps2;
        cfg.linkCount = std::max<std::size_t>(1, cfg.linkCount);
        cfg.firstLinkCenterOffsetM = std::max(0.001f, cfg.firstLinkCenterOffsetM);
        cfg.linkCenterSpanM = std::max(0.0f, cfg.linkCenterSpanM);
        cfg.headCenterOffsetFromLastLinkM = std::max(0.001f, cfg.headCenterOffsetFromLastLinkM);
        cfg.linkMassKg = std::max(0.001f, cfg.linkMassKg);
        cfg.headMassKg = std::max(0.001f, cfg.headMassKg);
        cfg.dampingPer90Hz = std::clamp(cfg.dampingPer90Hz, 0.0f, 1.0f);
        cfg.headDampingPer90Hz = std::clamp(cfg.headDampingPer90Hz, 0.0f, 1.0f);
        cfg.headStaticFriction = std::clamp(cfg.headStaticFriction, 0.0f, 2.0f);
        cfg.headSlidingFriction = std::clamp(cfg.headSlidingFriction, 0.0f, cfg.headStaticFriction);
        cfg.linkCollisionRadiusM = std::clamp(cfg.linkCollisionRadiusM, 0.001f, 0.15f);
        cfg.linkCollisionHalfSegmentM = std::clamp(cfg.linkCollisionHalfSegmentM, 0.001f, 0.15f);
        cfg.solverIterations = std::max(1, cfg.solverIterations);
        return cfg;
    }

    void rebuildLayout() {
        points_.assign(cfg_.linkCount + 2, {});
        points_[0].invMass = 0.0f;
        for (std::size_t i = 0; i < cfg_.linkCount; ++i) {
            points_[i + 1].invMass = 1.0f / cfg_.linkMassKg;
        }
        points_.back().invMass = 1.0f / cfg_.headMassKg;

        constraintLengthsM_.clear();
        constraintLengthsM_.reserve(cfg_.linkCount + 1);
        constraintLengthsM_.push_back(cfg_.firstLinkCenterOffsetM);

        if (cfg_.linkCount > 1) {
            const float centreSpacing = cfg_.linkCenterSpanM / static_cast<float>(cfg_.linkCount - 1);
            for (std::size_t i = 1; i < cfg_.linkCount; ++i) {
                constraintLengthsM_.push_back(centreSpacing);
            }
        }
        constraintLengthsM_.push_back(cfg_.headCenterOffsetFromLastLinkM);
    }

    void solveDistance(std::size_t ia, std::size_t ib, float restLength) {
        Particle& a = points_[ia];
        Particle& b = points_[ib];
        const Vec3 delta = b.position - a.position;
        const float dist = length(delta);
        if (dist < 1.0e-7f) return;

        const float w0 = a.invMass;
        const float w1 = b.invMass;
        const float ws = w0 + w1;
        if (ws <= 0.0f) return;

        const Vec3 correction = delta * ((dist - restLength) / dist);
        if (w0 > 0.0f) a.position += correction * (w0 / ws);
        if (w1 > 0.0f) b.position -= correction * (w1 / ws);
    }

    ChainConfig cfg_{};
    std::vector<Particle> points_{};
    std::vector<float> constraintLengthsM_{};
    bool initialized_{false};
    std::vector<HeadContactPlane> contacts_{};
    std::vector<ChainLinkContact> chainContacts_{};
    std::vector<Vec3> pendingChainCenters_{}, pendingChainAxes_{};
    float collisionScale_{1.0f};
    std::uint64_t lastContactPhysicsStep_{};
};

class FixedStepChain {
public:
    explicit FixedStepChain(ChainConfig cfg = {}) : solver_(cfg) {}

    void reset(Vec3 anchor, Vec3 direction = {0,0,-1}) {
        if (!isFinite(anchor)) return;
        accumulator_ = 0.0f;
        solver_.reset(anchor, direction);
        lastInputAnchor_ = anchor;
        hasInputAnchor_ = true;
        lastHold_ = {};
    }

    int update(float frameDt, Vec3 anchor, IChainCollisionQuery* query = nullptr,
               HeadHoldTarget hold = {}) {
        // Invalid tracking/time samples must never poison the persistent simulation.
        if (!std::isfinite(frameDt) || !isFinite(anchor)) return 0;
        frameDt = std::clamp(frameDt, 0.0f, 0.05f);
        if (!hasInputAnchor_) {
            lastInputAnchor_ = anchor;
            hasInputAnchor_ = true;
        }
        if (frameDt <= 0.0f) {
            lastInputAnchor_ = anchor;
            lastHold_ = {};
            return 0;
        }

        // A float 1/90 is slightly too long: the old accumulator lost an entire
        // fixed step at 72/80/144 Hz. Keep clock arithmetic in double precision.
        constexpr double h = 1.0 / 90.0;
        const double accumulatorAtFrameStart = accumulator_;
        accumulator_ += frameDt;

        int steps = 0;
        const Vec3 holdStart = lastHold_.active ? lastHold_.positionM : solver_.headPosition();
        double sampleTimeInFrame = h - accumulatorAtFrameStart;
        while (accumulator_ >= h && steps < 5) {
            const float alpha = static_cast<float>(std::clamp(sampleTimeInFrame / frameDt, 0.0, 1.0));
            HeadHoldTarget sampled = hold;
            if (hold.active) sampled.positionM = lerp(holdStart, hold.positionM, alpha);
            solver_.step90Hz(lerp(lastInputAnchor_, anchor, alpha), query, sampled);
            accumulator_ -= h;
            sampleTimeInFrame += h;
            ++steps;
        }

        if (steps == 5 && accumulator_ >= h) accumulator_ = 0.0f;
        lastInputAnchor_ = anchor;
        lastHold_ = hold;
        return steps;
    }

    [[nodiscard]] ChainSolver& solver() { return solver_; }
    [[nodiscard]] const ChainSolver& solver() const { return solver_; }
    [[nodiscard]] float accumulatorSeconds() const { return static_cast<float>(accumulator_); }

private:
    ChainSolver solver_;
    Vec3 lastInputAnchor_{};
    HeadHoldTarget lastHold_{};
    double accumulator_{};
    bool hasInputAnchor_{};
};

struct SweepHit {
    bool hit{false};
    float t{1.0f};
    Vec3 point{};
};

inline SweepHit sweptSphereVsSphere(Vec3 start, Vec3 end, float movingRadius,
                                    Vec3 targetCenter, float targetRadius) {
    if (!isFinite(start) || !isFinite(end) || !isFinite(targetCenter) ||
        !std::isfinite(movingRadius) || !std::isfinite(targetRadius) ||
        movingRadius < 0.0f || targetRadius < 0.0f) return {};
    const double r = static_cast<double>(movingRadius) + targetRadius;
    const Vec3 v = end - start;
    const Vec3 m = start - targetCenter;
    if (!isFinite(v) || !isFinite(m)) return {};
    const auto preciseDot = [](Vec3 a, Vec3 b) {
        return static_cast<double>(a.x)*b.x + static_cast<double>(a.y)*b.y +
            static_cast<double>(a.z)*b.z;
    };
    const double c = preciseDot(m,m) - r*r;
    if (c <= 0.0f) return {true, 0.0f, start};
    const double a = preciseDot(v,v);
    if (a < 1.0e-10f) return {};
    const double b = preciseDot(m,v);
    if (b > 0.0f) return {};
    const double disc = b*b - a*c;
    if (disc < 0.0f) return {};
    // A ray intersection past end is not a segment hit. Clamping it to 1 used
    // to fabricate contacts with distant targets in the swing direction.
    const double entry = (-b - std::sqrt(disc)) / a;
    if (entry < 0.0 || entry > 1.0) return {};
    const float t = static_cast<float>(entry);
    return {true, t, lerp(start,end,t)};
}

inline float chainExtension(const ChainSolver& s) {
    return length(s.headPosition() - s.anchorPosition());
}

} // namespace cms
