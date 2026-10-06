#pragma once
#include "SceneTransformCore.hpp"

namespace cms {

// A press close to the ball captures its current offset from the palm. No snap
// to the centre, distant pull, toggle lock or transfer of the right-hand weapon.
class OffhandGrabState {
public:
    void reset() { *this = {}; }
    [[nodiscard]] bool held() const { return held_; }
    HeadHoldTarget update(bool valid, bool down, bool captured, bool freeHand,
                          const RigidTransform& palmM, Vec3 headM, Vec3 anchorM,
                          float radiusM, float reachM, float dt) {
        const bool pressed = down && !wasDown_;
        wasDown_ = down;
        if (!valid || !freeHand || !captured || !down || !isFinite(headM) ||
            !isFinite(anchorM) || !isFinite(palmM.translation) ||
            !approximatelyOrthonormal(palmM.rotation, .03f) ||
            !std::isfinite(radiusM) || radiusM<=0 || !std::isfinite(reachM) ||
            reachM<=0 || !std::isfinite(dt) || dt<=0) {
            held_ = false;
            return {};
        }
        if (!held_) {
            if (!pressed || length(headM-palmM.translation)>radiusM+.06f) return {};
            offsetM_ = mul(transpose(palmM.rotation), headM-palmM.translation);
            previousPalmM_ = palmM.translation;
            held_ = true;
        }
        Vec3 target = palmM.translation + mul(palmM.rotation, offsetM_);
        // Physical tracking cannot constrain hands farther apart than the
        // chain. Release on overextension or lost tracking, without a fling.
        if (length(target-anchorM)>reachM+.04f ||
            length(palmM.translation-previousPalmM_)>std::max(.20f,12.0f*dt) ||
            length(target-headM)>.35f) {
            held_ = false;
            return {};
        }
        // Accept the small stretch left by a loaded chain's iterative solver,
        // while the held target itself never extends the authored reach.
        if (length(target-anchorM)>reachM)
            target=anchorM+normalized(target-anchorM)*reachM;
        previousPalmM_ = palmM.translation;
        return {target,true};
    }
private:
    Vec3 offsetM_{}, previousPalmM_{};
    bool wasDown_{}, held_{};
};
} // namespace cms
