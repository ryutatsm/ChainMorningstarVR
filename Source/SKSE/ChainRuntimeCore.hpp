#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <string_view>
#include <vector>

#include "ChainPhysicsCore.hpp"
#include "MotionAudioCore.hpp"

namespace cms {

constexpr float kPi = 3.14159265358979323846f;
constexpr float kHeadBroadphaseRadiusM = 0.24f * kModelScale;
constexpr float kHeadDamageRadiusM = kHeadBroadphaseRadiusM;

struct LinkPose {
    Vec3 centerM{};
    Vec3 tangent{};
    float rollRadians{};
    Mat3 rotation{basisFromLocalZ(tangent, rollRadians)};
};

struct HeadPose {
    Vec3 centerM{};
    Vec3 chainAxis{};
    Vec3 velocityMps{};
    Mat3 rotation{basisFromLocalZ(chainAxis)};
    bool held{};
};

struct VisualFrame {
    std::vector<LinkPose> links;
    HeadPose head{};
};

inline VisualFrame buildVisualFrame(const ChainSolver& s) {
    VisualFrame out;
    const std::size_t n = s.linkCount();
    out.links.resize(n);

    for (std::size_t i = 0; i < n; ++i) {
        const Vec3 p = s.linkPosition(i);
        const Vec3 tangent = s.linkAxis(i);
        out.links[i] = {p, tangent, (i & 1u) ? (0.5f * kPi) : 0.0f};
    }

    Vec3 axis = normalized(s.headPosition() - s.linkPosition(n - 1));
    if (lengthSq(axis) < 1.0e-7f) axis = {0,0,1};
    out.head = {s.headPosition(), axis, s.headVelocity90Hz()};
    return out;
}

enum class ChainSoundEventType {
    kNone,
    kRattle,
    kHeavyClank
};

struct ChainSoundEvent {
    ChainSoundEventType type{ChainSoundEventType::kNone};
    float intensity{};
};

struct ChainSoundConfig {
    float rattleRelativeSpeedMps{0.85f};
    float rattleCooldownS{0.085f};
    float clankImpulseThreshold{3.0f}; // exclude resting gravity/solver chatter
    float clankCooldownS{0.22f};
};

class ChainSoundGate {
public:
    explicit ChainSoundGate(ChainSoundConfig cfg = {}) : cfg_(cfg) {}

    void reset() {
        rattleCooldown_ = 0.0f;
        clankCooldown_ = 0.0f;
    }

    ChainSoundEvent update(float dt, const ChainSolver& s, float contactImpulse = 0.0f) {
        rattleCooldown_ = std::max(0.0f, rattleCooldown_ - std::max(0.0f, dt));
        clankCooldown_ = std::max(0.0f, clankCooldown_ - std::max(0.0f, dt));

        if (std::isfinite(contactImpulse) && contactImpulse >= cfg_.clankImpulseThreshold && clankCooldown_ <= 0.0f) {
            clankCooldown_ = cfg_.clankCooldownS;
            const float x = (contactImpulse - cfg_.clankImpulseThreshold) / (cfg_.clankImpulseThreshold * 2.0f);
            return {ChainSoundEventType::kHeavyClank, std::clamp(0.35f + x, 0.35f, 1.0f)};
        }

        float rel = 0.0f;
        // Whole-chain translation is not relative link motion.
        Vec3 prevV = s.anchorVelocity90Hz();
        for (std::size_t i = 0; i < s.linkCount(); ++i) {
            const Vec3 v = s.linkVelocity90Hz(i);
            rel = std::max(rel, length(v - prevV));
            prevV = v;
        }
        rel = std::max(rel, length(s.headVelocity90Hz() - prevV));

        if (rel >= cfg_.rattleRelativeSpeedMps && rattleCooldown_ <= 0.0f) {
            rattleCooldown_ = cfg_.rattleCooldownS;
            const float x = (rel - cfg_.rattleRelativeSpeedMps) / 3.0f;
            return {ChainSoundEventType::kRattle, std::clamp(0.20f + x, 0.20f, 1.0f)};
        }
        return {};
    }

private:
    ChainSoundConfig cfg_{};
    float rattleCooldown_{};
    float clankCooldown_{};
};

struct HeadSweep {
    Vec3 fromM{};
    Vec3 toM{};
    float radiusM{kHeadBroadphaseRadiusM};
    float speedMps{};
};

class ChainController {
public:
    explicit ChainController(ChainConfig cfg = {}) : chain_(cfg) {}

    void onEquip(Vec3 anchorWorldSU, Vec3 initialDirectionWorld = {0,0,-1}) {
        if (!isFinite(anchorWorldSU)) {
            onUnequip();
            return;
        }
        equipped_ = true;
        const Vec3 anchorM = anchorWorldSU * kMetersPerSkyrimUnit;
        chain_.reset(anchorM, initialDirectionWorld);
        resetRotations();
        previousHeadM_ = chain_.solver().headPosition();
        lastAnchorM_ = anchorM;
        lastSimulatedDt_ = 0.0f;
        hasPreviousHead_ = true;
        sound_.reset();
        motionSound_.reset();
    }

    void onUnequip() {
        equipped_ = false;
        hasPreviousHead_ = false;
        lastSimulatedDt_ = 0.0f;
        chain_.solver().clearWorldContacts();
        linkRotations_.clear();
        sound_.reset();
        motionSound_.reset();
    }

    // Called on the owning game/update thread after draining native callbacks.
    // Native collectors must also discard their queued contacts on release.
    float applyWorldContacts(const std::vector<HeadWorldContact>& contacts) {
        if (!equipped_) return 0.0f;
        return chain_.solver().applyWorldContacts(contacts);
    }

    bool update(float frameDt, Vec3 anchorWorldSU, IChainCollisionQuery* query = nullptr,
                HeadHoldTarget hold = {}) {
        if (!equipped_) return false;
        if (!std::isfinite(frameDt) || !isFinite(anchorWorldSU)) {
            previousHeadM_ = chain_.solver().headPosition();
            lastSimulatedDt_ = 0.0f;
            return false;
        }
        const Vec3 anchorM = anchorWorldSU * kMetersPerSkyrimUnit;

        if (wouldTeleportReset(anchorWorldSU)) {
            chain_.reset(anchorM, {0,0,-1});
            resetRotations();
            previousHeadM_ = chain_.solver().headPosition();
            lastSimulatedDt_ = 0.0f;
            hasPreviousHead_ = true;
            sound_.reset();
            motionSound_.reset();
        } else {
            if (hasPreviousHead_) previousHeadM_ = chain_.solver().headPosition();
            const int steps = chain_.update(frameDt, anchorM, query, hold);
            lastSimulatedDt_ = static_cast<float>(steps) * (1.0f / 90.0f);
            const auto frame = buildVisualFrame(chain_.solver());
            held_ = hold.active && approximatelyOrthonormal(hold.rotation, .03f);
            // A resting head must not drill its spikes into the floor merely
            // because a slack end-link is settling. Resume alignment in flight.
            if (held_) headRotation_=hold.rotation;
            else if (chain_.solver().activeContactCount()==0)
                headRotation_=transportLocalZ(headRotation_,frame.head.chainAxis,
                    6.0f * std::clamp(frameDt, 0.0f, .05f));
            for (std::size_t i=0;i<linkRotations_.size();++i)
                linkRotations_[i] = transportLocalZ(linkRotations_[i], frame.links[i].tangent);
        }
        lastAnchorM_ = anchorM;
        hasPreviousHead_ = true;
        return true;
    }

    // The native owner must release/reacquire before draining callbacks when
    // tracking crosses the same threshold used by update(). This lets the
    // RuntimeDriver discard old-generation contacts and suppress damage sweeps.
    [[nodiscard]] bool wouldTeleportReset(Vec3 anchorWorldSU) const {
        if (!equipped_ || !isFinite(anchorWorldSU)) return false;
        const Vec3 anchorM = anchorWorldSU * kMetersPerSkyrimUnit;
        return length(anchorM - lastAnchorM_) > teleportResetDistanceM_;
    }

    [[nodiscard]] bool equipped() const { return equipped_; }
    [[nodiscard]] const ChainSolver& solver() const { return chain_.solver(); }
    [[nodiscard]] VisualFrame visualFrame() const {
        auto frame = buildVisualFrame(chain_.solver());
        frame.head.rotation = headRotation_;
        frame.head.held = held_;
        for (std::size_t i=0;i<linkRotations_.size();++i) frame.links[i].rotation=linkRotations_[i];
        return frame;
    }

    [[nodiscard]] HeadSweep headSweep() const {
        const Vec3 now = chain_.solver().headPosition();
        const Vec3 from = hasPreviousHead_ ? previousHeadM_ : now;
        const float speed = (lastSimulatedDt_ > 1.0e-6f) ?
            (length(now - from) / lastSimulatedDt_) : 0.0f;
        return {from, now, kHeadDamageRadiusM, speed};
    }

    ChainSoundEvent soundEvent(float frameDt, float contactImpulse = 0.0f) {
        return sound_.update(frameDt, chain_.solver(), contactImpulse);
    }
    MotionAudioMix motionAudio(float dt) {
        const auto& s=chain_.solver();
        return motionSound_.update(dt,s.headSurfaceSlipMps(),
            s.headPosition()-s.anchorPosition(),s.headVelocity90Hz()-s.anchorVelocity90Hz(),
            s.headTouchesSurface(),held_);
    }

    void setTeleportResetDistanceM(float d) { teleportResetDistanceM_ = std::max(0.25f, d); }

private:
    void resetRotations() {
        const auto frame = buildVisualFrame(chain_.solver());
        headRotation_ = frame.head.rotation;
        held_ = false;
        linkRotations_.clear();
        for (const auto& link : frame.links) linkRotations_.push_back(link.rotation);
    }
    FixedStepChain chain_{};
    Mat3 headRotation_{};
    std::vector<Mat3> linkRotations_;
    bool held_{};
    ChainSoundGate sound_{};
    MotionAudioGate motionSound_{};
    Vec3 previousHeadM_{};
    Vec3 lastAnchorM_{};
    float teleportResetDistanceM_{1.5f};
    float lastSimulatedDt_{};
    bool equipped_{};
    bool hasPreviousHead_{};
};

inline constexpr std::string_view kChainAnchorNode = "CMS_ChainAnchor";
inline constexpr std::string_view kHeadNode = "CMS_HeadNode";
inline constexpr std::array<std::string_view,kChainLinkCount> kLinkNodes = {
    "CMS_LinkNode_00", "CMS_LinkNode_01", "CMS_LinkNode_02", "CMS_LinkNode_03",
    "CMS_LinkNode_04", "CMS_LinkNode_05", "CMS_LinkNode_06", "CMS_LinkNode_07",
    "CMS_LinkNode_08", "CMS_LinkNode_09", "CMS_LinkNode_10", "CMS_LinkNode_11",
    "CMS_LinkNode_12", "CMS_LinkNode_13", "CMS_LinkNode_14", "CMS_LinkNode_15",
    "CMS_LinkNode_16", "CMS_LinkNode_17", "CMS_LinkNode_18"
};

} // namespace cms
