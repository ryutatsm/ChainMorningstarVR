#pragma once
#include "SceneTransformCore.hpp"
#include "ChainPhysicsCore.hpp"

namespace cms {

enum class OffhandGrabReason {
    kIdle, kHeld, kInputStale, kHandUnavailable, kGripReleased,
    kInputNotCaptured, kInvalidPose, kNeedsNewPress, kOutsideHeadReach,
    kTrackingJump, kChainOverextended, kHeadObstructed
};

inline const char* offhandGrabReasonName(OffhandGrabReason reason) {
    switch (reason) {
    case OffhandGrabReason::kIdle: return "idle";
    case OffhandGrabReason::kHeld: return "ready";
    case OffhandGrabReason::kInputStale: return "input-stale";
    case OffhandGrabReason::kHandUnavailable: return "hand-unavailable";
    case OffhandGrabReason::kGripReleased: return "grip-released";
    case OffhandGrabReason::kInputNotCaptured: return "input-not-captured";
    case OffhandGrabReason::kInvalidPose: return "invalid-pose";
    case OffhandGrabReason::kNeedsNewPress: return "needs-new-press";
    case OffhandGrabReason::kOutsideHeadReach: return "outside-head-reach";
    case OffhandGrabReason::kTrackingJump: return "tracking-jump";
    case OffhandGrabReason::kChainOverextended: return "chain-overextended";
    case OffhandGrabReason::kHeadObstructed: return "head-obstructed";
    }
    return "unknown";
}

struct OffhandGrabDiagnostic {
    OffhandGrabReason reason{OffhandGrabReason::kIdle};
    float palmDistanceM{-1}, palmStepM{-1}, chainExcessM{-1}, targetErrorM{-1};
};

// A press close to the ball captures its current offset from the palm. No snap
// to the centre, distant pull, toggle lock or transfer of the right-hand weapon.
class OffhandGrabState {
public:
    void reset() { *this = {}; }
    [[nodiscard]] bool held() const { return held_; }
    [[nodiscard]] const OffhandGrabDiagnostic& diagnostic() const { return diagnostic_; }
    HeadHoldTarget update(bool valid, bool down, bool captured, bool freeHand,
                          const RigidTransform& palmM, Vec3 headM, Vec3 anchorM,
                          float radiusM, float reachM, float dt,
                          const Mat3& headRotation = {}) {
        const bool pressed = down && !wasDown_;
        wasDown_ = down;
        diagnostic_ = {};
        const auto stop = [&](OffhandGrabReason reason) -> HeadHoldTarget {
            diagnostic_.reason = reason;
            held_ = false;
            return {};
        };
        if (!valid) return stop(OffhandGrabReason::kInputStale);
        if (!freeHand) return stop(OffhandGrabReason::kHandUnavailable);
        if (!down) return stop(OffhandGrabReason::kGripReleased);
        if (!captured) return stop(OffhandGrabReason::kInputNotCaptured);
        if (!isFinite(headM) ||
            !isFinite(anchorM) || !isFinite(palmM.translation) ||
            !approximatelyOrthonormal(palmM.rotation, .03f) ||
            !approximatelyOrthonormal(headRotation, .03f) ||
            !std::isfinite(radiusM) || radiusM<=0 || !std::isfinite(reachM) ||
            reachM<=0 || !std::isfinite(dt) || dt<=0) {
            return stop(OffhandGrabReason::kInvalidPose);
        }
        diagnostic_.palmDistanceM = length(headM-palmM.translation);
        if (!held_) {
            if (!pressed) return stop(OffhandGrabReason::kNeedsNewPress);
            if (diagnostic_.palmDistanceM>radiusM+.06f)
                return stop(OffhandGrabReason::kOutsideHeadReach);
            offsetM_ = mul(transpose(palmM.rotation), headM-palmM.translation);
            rotationInPalm_ = mul(transpose(palmM.rotation), headRotation);
            previousPalmM_ = palmM.translation;
            held_ = true;
        }
        Vec3 target = palmM.translation + mul(palmM.rotation, offsetM_);
        diagnostic_.palmStepM = length(palmM.translation-previousPalmM_);
        const float targetReach = length(target-anchorM);
        diagnostic_.chainExcessM = std::max(0.0f,targetReach-reachM);
        if (diagnostic_.palmStepM>std::max(.20f,12.0f*dt))
            return stop(OffhandGrabReason::kTrackingJump);

        // A taut chain constrains the ball, not the tracked controller. The
        // previous reach+4cm cutoff released after only ~2.5cm of hand motion
        // once gravity's solver stretch used part of that budget. Project to
        // real reach first; retain the hold while the palm still touches the
        // ball's grab envelope (4cm exit hysteresis). Never lengthen the chain.
        if (targetReach>reachM)
            target=anchorM+normalized(target-anchorM)*reachM;
        if (length(target-palmM.translation)>radiusM+.10f)
            return stop(OffhandGrabReason::kChainOverextended);
        diagnostic_.targetErrorM = length(target-headM);
        if (diagnostic_.targetErrorM>.35f)
            return stop(OffhandGrabReason::kHeadObstructed);
        previousPalmM_ = palmM.translation;
        diagnostic_.reason = OffhandGrabReason::kHeld;
        return {target,true,mul(palmM.rotation,rotationInPalm_)};
    }
private:
    Vec3 offsetM_{}, previousPalmM_{};
    Mat3 rotationInPalm_{};
    bool wasDown_{}, held_{};
    OffhandGrabDiagnostic diagnostic_{};
};
} // namespace cms
