#include "Source/SKSE/MotionAudioCore.hpp"
#include <cassert>
#include <limits>
#include <iostream>
#include <vector>

namespace {
using namespace cms;
constexpr float tau=6.28318530718f;
Vec3 plane(Vec3 v,int p) {
    if(p==1) return {v.x,0,v.y};
    if(p==2) return {0,v.x,v.y};
    return v;
}
void spacing(const std::vector<float>& events) {
    for(std::size_t i=1;i<events.size();++i) assert(events[i]-events[i-1]>=.2799f);
}
std::vector<float> circle(float hz,float turnsPerSecond,int p=0) {
    MotionAudioGate gate;
    std::vector<float> events;
    const float dt=1/hz,omega=tau*turnsPerSecond;
    for(int i=0;i<static_cast<int>(12*hz);++i) {
        const float t=static_cast<float>(i)*dt,a=omega*t;
        const auto mix=gate.update(dt,0,plane({.6f*std::cos(a),.6f*std::sin(a),0},p),
            plane({-.6f*omega*std::sin(a),.6f*omega*std::cos(a),0},p),false,false);
        assert(mix.scrape==0&&!mix.airStopped);
        if(mix.air>0) {assert(mix.air>=.30f&&mix.air<=.78f);events.push_back(t);}
    }
    spacing(events);return events;
}
}
int main() {
    using namespace cms;
    for(float hz:{45.f,72.f,90.f,120.f,144.f}) {
        const float dt=1/hz;
        // Sustained circular movement gives one complete sample per revolution
        // at normal rates, independent of rotation plane and render rate.
        for(int p=0;p<3;++p) for(float turns:{.5f,1.f,2.f,3.f}) {
            const auto events=circle(hz,turns,p);
            assert(events.size()==static_cast<std::size_t>(12*turns));
            for(std::size_t i=1;i<events.size();++i)
                assert(std::abs((events[i]-events[0])-static_cast<float>(i)/turns)<2*dt);
        }
        const auto fast=circle(hz,10);
        assert(fast.size()>30&&fast.size()<=43); // no frame-rate machine gun
        MotionAudioGate gate;
        MotionAudioMix moving;
        for(int i=0;i<static_cast<int>(hz);++i) {
            moving=gate.update(dt,.8f,{0,0,-.6f},{4,0,0},true,false);
            assert(moving.air==0&&moving.airStopped);
        }
        assert(moving.scrape>.4f);
        for(int i=0;i<static_cast<int>(hz);++i) {
            moving=gate.update(dt,0,{0,0,-.6f},{4,0,0},false,true);
            assert(moving.air==0&&moving.airStopped);
        }
        assert(moving.scrape==0);
        // Uniform whole-player translation supplies zero relative velocity.
        for(int i=0;i<static_cast<int>(hz);++i)
            assert(gate.update(dt,0,{0,0,-.6f},{},false,false).air==0);
        // Isolated velocity spikes and threshold noise cannot qualify a swing.
        for(int i=0;i<static_cast<int>(hz)*2;++i)
            assert(gate.update(dt,0,{0,0,-.6f},{i%2?0.f:4.f,0,0},false,false).air==0);
        gate.reset();
        // A radial pull has no rotation: play the stroke once, never a timer loop.
        int radial=0;
        for(int i=0;i<static_cast<int>(hz)*2;++i)
            radial+=gate.update(dt,0,{0,0,-.6f-4*i*dt},{0,0,-4},false,false).air>0;
        assert(radial==1);
        gate.reset();
        // Backstrokes reverse the angular axis; each fast stroke should sound
        // once even though no complete revolution is performed.
        std::vector<float> strokes;
        for(int i=0;i<static_cast<int>(hz)*12;++i) {
            const float t=i*dt,phase=tau*.75f*t;
            const float a=1.15f*std::sin(phase),omega=1.15f*tau*.75f*std::cos(phase);
            const auto mix=gate.update(dt,0,{.6f*std::sin(a),0,-.6f*std::cos(a)},
                {.6f*omega*std::cos(a),0,.6f*omega*std::sin(a)},false,false);
            if(mix.air>0) strokes.push_back(t);
        }
        assert(strokes.size()>=18&&strokes.size()<=19);spacing(strokes);
        // Quick contact/release must not evade the 280 ms inter-shot guard.
        gate.reset();
        std::vector<float> interrupted;
        for(int i=0;i<static_cast<int>(hz)*3;++i) {
            const bool touching=i%5==4;
            const auto mix=gate.update(dt,0,{0,0,-.6f},{4,0,0},touching,false);
            if(touching) assert(mix.airStopped&&mix.air==0);
            if(mix.air>0) interrupted.push_back(i*dt);
        }
        spacing(interrupted);
        gate.reset();
        assert(gate.update(dt,0,{0,0,-.1f},{20,0,0},false,false).airStopped);
        for(float bad:{0.f,-1.f,.2f,std::numeric_limits<float>::quiet_NaN()}) {
            const auto mix=gate.update(bad,0,{0,0,-.6f},{4,0,0},false,false);
            assert(mix.airStopped&&mix.air==0&&mix.scrape==0);
        }
        assert(gate.update(dt,0,{0,0,-.6f},{std::numeric_limits<float>::infinity(),0,0},false,false).airStopped);
    }
    std::cout<<"MOTION_AUDIO_PASS discrete turns/backstrokes at five rates and three planes, bounded rapid swings, no radial retrigger, scrape/held/contact separation, spike rejection and reset\n";
}
