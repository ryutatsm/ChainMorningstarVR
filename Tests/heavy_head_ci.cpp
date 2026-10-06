#include "Source/SKSE/ChainPhysicsCore.hpp"
#include <cassert>
#include <iostream>

using namespace cms;

struct MotionMeasure { float settlingSpeedSquared{},peakSwingSpeed{}; };
static MotionMeasure swingAndStop(ChainConfig cfg) {
    ChainSolver s(cfg);s.reset({0,0,0});
    MotionMeasure measure;
    for(int tick=1;tick<=360;++tick) {
        // Move the hand 35 cm, then keep its exact tracked position fixed.
        const Vec3 anchor{.35f*std::min(tick/36.0f,1.0f),0,0};
        s.step90Hz(anchor);
        assert(length(s.anchorPosition()-anchor)==0);
        assert(isFinite(s.headPosition()) && isFinite(s.headVelocity90Hz()));
        if(tick<=90)measure.peakSwingSpeed=std::max(measure.peakSwingSpeed,length(s.headVelocity90Hz()));
        if(tick>270)measure.settlingSpeedSquared+=lengthSq(s.headVelocity90Hz());
    }
    assert(s.maxConstraintErrorM()<.004f);
    return measure;
}
int main() {
    ChainConfig previous;
    previous.headMassKg=8;previous.headDampingPer90Hz=.995f;previous.solverIterations=80;
    const auto light=swingAndStop(previous),heavy=swingAndStop({});
    assert(heavy.peakSwingSpeed>.3f); // still responds to a real controller swing
    assert(heavy.settlingSpeedSquared<light.settlingSpeedSquared*.75f);
    std::cout<<"CMS heavy-head motion CI PASS\nsettling_motion_ratio="
             <<heavy.settlingSpeedSquared/light.settlingSpeedSquared
             <<"\npeak_swing_speed_mps="<<heavy.peakSwingSpeed<<"\n";
}
