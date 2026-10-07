#pragma once
#include <algorithm>
#include <cmath>
#include "VectorMath.hpp"

namespace cms {
// air is a one-frame request to play a complete short swing sample, not gain
// for a continuous loop. airStopped immediately cancels it on contact/holding.
struct MotionAudioMix { float scrape{}, air{}; bool airStopped{true}; };
class MotionAudioGate {
public:
    void reset() { *this=MotionAudioGate{}; }
    MotionAudioMix update(float dt,float slipMps,Vec3 headFromAnchorM,
                         Vec3 relativeVelocityMps,bool touching,bool held) {
        if(!std::isfinite(dt)||dt<=0||dt>.10f||!std::isfinite(slipMps)||
           !isFinite(headFromAnchorM)||!isFinite(relativeVelocityMps)||slipMps<0) {
            reset();return mix_;
        }
        // Resting contact is silent. Whole-player translation is removed by
        // measuring airborne speed relative to the chain anchor, not the world.
        const float scrape=touching&&slipMps>.035f?
            std::clamp(.18f+(slipMps-.035f)*.5f,0.0f,.80f):0.0f;
        const auto smooth=[dt](float old,float target) {
            const float rate=target>old?18.0f:30.0f;
            const float value=target+(old-target)*std::exp(-rate*dt);
            return value<.005f?0.0f:value;
        };
        mix_.scrape=smooth(mix_.scrape,scrape);
        mix_.air=0;
        mix_.airStopped=touching||held;
        cooldown_=std::max(0.0f,cooldown_-dt);
        const float radiusSq=lengthSq(headFromAnchorM);
        const float speed=length(relativeVelocityMps);
        if(mix_.airStopped||radiusSq<.18f*.18f||!std::isfinite(radiusSq)||!std::isfinite(speed)) {
            clearSwing();mix_.airStopped=true;return mix_;
        }
        // Hysteresis and a short qualification period reject single-frame speed
        // spikes and stop threshold chatter from restarting the sample.
        if(speed<(active_?1.2f:1.8f)) {
            if(!active_) qualifiedTime_=0;
            quietTime_+=dt;
            if(quietTime_>=.045f) clearSwing();
            return mix_;
        }
        quietTime_=0;
        const Vec3 angular=cross(headFromAnchorM,relativeVelocityMps)/radiusSq;
        const float omega=length(angular);
        if(!std::isfinite(omega)) {reset();return mix_;}
        const Vec3 axis=normalized(angular);
        // A backstroke is a new swing. A circular swing keeps the same angular
        // axis even when its velocity points the opposite way half a turn later.
        if(active_&&omega>.5f&&dot(axis,turnAxis_)<-.5f) clearSwing();
        if(omega>.5f) turnAxis_=axis;
        if(!active_) {
            qualifiedTime_+=dt;
            if(qualifiedTime_>=.035f&&cooldown_<=0) {
                active_=true;phase_=0;requestSwing(speed);
            }
        } else {
            // Integrate actual angular motion, not a fixed repeating timer.
            // At ordinary swing rates one complete turn produces one "boon".
            constexpr float turn=6.28318530718f;
            phase_=std::min(2*turn,phase_+std::min(omega,40.0f)*dt);
            if(phase_>=turn&&cooldown_<=0&&speed>=1.8f) {
                phase_=std::fmod(phase_,turn);requestSwing(speed);
            }
        }
        return mix_;
    }
private:
    void clearSwing() {
        active_=false;phase_=0;quietTime_=0;qualifiedTime_=0;turnAxis_={};
        // Preserve the inter-shot guard through contact and threshold changes.
    }
    void requestSwing(float speed) {
        mix_.air=std::clamp(.30f+(speed-1.8f)*.075f,.30f,.78f);
        cooldown_=.28f; // 240 ms sample + at least 40 ms between dense swings.
    }
    MotionAudioMix mix_{};
    Vec3 turnAxis_{};
    float phase_{},cooldown_{},quietTime_{},qualifiedTime_{};
    bool active_{};
};
} // namespace cms
