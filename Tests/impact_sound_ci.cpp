#include "Source/SKSE/ChainRuntimeCore.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace cms;

int main() {
    ChainSolver stationary;stationary.reset({0,0,0});
    ChainSoundGate gate;
    assert(gate.update(.01f,stationary).type==ChainSoundEventType::kNone);
    // Resting gravity correction and invalid callback magnitudes stay silent.
    for(float impulse:{0.0f,1.4f,-10.0f,std::numeric_limits<float>::infinity(),
                       std::numeric_limits<float>::quiet_NaN()})
        assert(gate.update(.25f,stationary,impulse).type==ChainSoundEventType::kNone);
    auto hit=gate.update(.01f,stationary,10);
    assert(hit.type==ChainSoundEventType::kHeavyClank&&hit.intensity>=.35f&&hit.intensity<=1);
    assert(gate.update(.10f,stationary,10).type==ChainSoundEventType::kNone);
    assert(gate.update(.13f,stationary,10).type==ChainSoundEventType::kHeavyClank);
    gate.reset(); // unequip/load/teleport must release the cooldown too
    assert(gate.update(.01f,stationary,10).type==ChainSoundEventType::kHeavyClank);

    // A real head collision supplies the impact, not swinging speed alone.
    ChainSolver falling;falling.reset({0,0,0},{1,0,0});
    for(int tick=0;tick<45;++tick)falling.step90Hz({0,0,0});
    gate.reset();
    assert(gate.update(.25f,falling).type!=ChainSoundEventType::kHeavyClank);
    HeadWorldContact c{};
    c.headCenterM=falling.headPosition();c.pointM=c.headCenterM;
    c.normalWorld=-normalized(falling.headVelocity90Hz());c.otherBodyIdentity=1;c.physicsStep=1;
    c.signedDistanceM=-.001f;
    const auto impulse=falling.applyWorldContacts({c});
    assert(impulse>3&&gate.update(.25f,falling,impulse).type==ChainSoundEventType::kHeavyClank);
    assert(falling.applyWorldContacts({c})==0); // repeated native step cannot retrigger
    std::cout<<"HEAVY_IMPACT_SOUND_PASS actual contact impulse, resting rejection, cooldown, reset\n";
}
