#include "Source/SKSE/MotionAudioCore.hpp"
#include <cassert>
#include <limits>
#include <iostream>
int main() {
    using namespace cms;
    for(float hz:{45.f,72.f,90.f,120.f,144.f}) {
        MotionAudioGate gate;
        for(int i=0;i<100;++i) {
            const auto idle=gate.update(1/hz,0,0,true,false);
            assert(idle.scrape==0&&idle.air==0);
        }
        MotionAudioMix moving;
        for(int i=0;i<static_cast<int>(hz);++i)moving=gate.update(1/hz,.8f,4,true,false);
        assert(moving.scrape>.4f && moving.air==0);
        for(int i=0;i<static_cast<int>(hz);++i)moving=gate.update(1/hz,0,4,false,false);
        assert(moving.scrape==0 && moving.air>.25f);
        for(int i=0;i<static_cast<int>(hz);++i)moving=gate.update(1/hz,0,4,false,true);
        assert(moving.scrape==0&&moving.air==0);
        gate.update(1/hz,1,0,true,false);gate.reset();
        assert(gate.update(1/hz,0,0,false,false).scrape==0);
        assert(gate.update(1/hz,0,0,false,false).air==0);
        assert(gate.update(1/hz,0,std::numeric_limits<float>::quiet_NaN(),false,false).air==0);
    }
    std::cout<<"MOTION_AUDIO_PASS stationary silence, scrape/air separation, held suppression, volume smoothing, reset at five refresh rates\n";
}
