#pragma once
#include <algorithm>
#include <cmath>

namespace cms {
struct MotionAudioMix { float scrape{}, air{}; };
class MotionAudioGate {
public:
    void reset() { mix_={}; }
    MotionAudioMix update(float dt,float slipMps,float relativeSpeedMps,bool touching,bool held) {
        if(!std::isfinite(dt)||dt<=0||dt>.10f||!std::isfinite(slipMps)||
           !std::isfinite(relativeSpeedMps)||slipMps<0||relativeSpeedMps<0) {
            reset();return mix_;
        }
        // Resting contact is silent. Whole-player translation is removed by
        // measuring airborne speed relative to the chain anchor, not the world.
        const float scrape=touching&&slipMps>.035f?
            std::clamp(.18f+(slipMps-.035f)*.5f,0.0f,.80f):0.0f;
        const float air=!touching&&!held&&relativeSpeedMps>1.8f?
            std::clamp((relativeSpeedMps-1.8f)*.12f,0.0f,.75f):0.0f;
        const auto smooth=[dt](float old,float target) {
            const float rate=target>old?18.0f:30.0f;
            const float value=target+(old-target)*std::exp(-rate*dt);
            return value<.005f?0.0f:value;
        };
        mix_.scrape=smooth(mix_.scrape,scrape);
        mix_.air=smooth(mix_.air,air);
        return mix_;
    }
private:
    MotionAudioMix mix_{};
};
} // namespace cms
