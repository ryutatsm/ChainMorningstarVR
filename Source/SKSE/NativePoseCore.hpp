#pragma once
#include "SceneTransformCore.hpp"

namespace cms {
// A keyframed body reaches the submitted endpoint in one physics step. HIGGS
// may subsequently warp this shared weapon body to its normal rigid-weapon
// target (ApplyHardKeyframeVelocityClamped), not just overwrite its velocity.
// Keep CMS's endpoint so the next cast starts at the ball, not at the hand.
// This history is scoped to one certified body/world generation.
class NativePoseContinuity {
public:
    void reset() { *this = {}; }
    void commit(Vec3 center, const Mat3& rotation) {
        if (!isFinite(center) || !approximatelyOrthonormal(rotation,.01f)) return;
        center_=center; rotation_=rotation; valid_=true;
    }
    [[nodiscard]] bool needsRestore(Vec3 center, const Mat3& rotation) const {
        if (!valid_) return false;
        if (!isFinite(center) || !approximatelyOrthonormal(rotation,.01f)) return true;
        if (lengthSq(center-center_) > .002f*.002f) return true;
        for (int i=0;i<3;++i)
            if (lengthSq(column(rotation,i)-column(rotation_,i)) > .005f*.005f) return true;
        return false;
    }
    [[nodiscard]] Vec3 center() const { return center_; }
    [[nodiscard]] const Mat3& rotation() const { return rotation_; }
private:
    Vec3 center_{};
    Mat3 rotation_{};
    bool valid_{};
};
} // namespace cms
