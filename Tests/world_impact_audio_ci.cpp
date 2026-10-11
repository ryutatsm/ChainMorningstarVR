#include "Source/SKSE/GameBridgeContract.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace cms;
HeadWorldContact sample(std::uint64_t step, float speed=4) {
    HeadWorldContact c{}; c.physicsStep=step; c.otherBodyIdentity=1;
    c.normalWorld={0,0,1}; c.headVelocityMps={0,0,-speed}; c.pointM={1,2,3}; return c;
}
struct Bridge : IGameBridge {
    std::vector<HeadWorldContact> pending; int impacts{}; Vec3 point{};
    bool reacquireWeaponNodes() override {return true;}
    bool tryGetChainAnchorWorldSU(Vec3& p,Vec3& d) override {p={};d={0,0,-1};return true;}
    void releaseWeaponNodes() override {pending.clear();}
    void applyVisualFrame(const VisualFrame&) override {}
    bool updateNativeMeleeHeadProxy(const HeadSweep&) override {return true;}
    std::vector<HeadWorldContact> consumeWorldContacts() override {auto c=pending;pending.clear();return c;}
    float consumeWorldContactImpulse() override {return 100;}
    void playChainRattle(float) override {}
    void playChainClank(float) override {assert(false);}
    void playWorldImpact(float volume,Vec3 p) override {assert(volume>=.45f&&volume<=1);++impacts;point=p;}
};
int main() {
    WorldImpactAudioGate gate;
    auto hit=gate.update(1.f/90,{sample(1),sample(1)});
    assert(hit.intensity>0&&hit.closingSpeedMps==4&&hit.pointM.z==3);
    // Native callbacks repeated while pressed into a wall cannot retrigger.
    for(int i=2;i<300;++i)assert(gate.update(1.f/90,{sample(i)}).intensity==0);
    assert(gate.update(.01f,{sample(298)}).intensity==0); // stale
    for(int i=0;i<20;++i)gate.update(.01f,{});
    assert(gate.update(.01f,{sample(300)}).intensity>0); // separated strike
    gate.reset();
    assert(gate.update(.01f,{sample(1,.11f)}).intensity==0); // resting gravity
    auto slide=sample(2,0);slide.headVelocityMps={12,0,0};
    assert(gate.update(.01f,{slide}).intensity==0);
    auto matching=sample(3);matching.surfaceVelocityMps=matching.headVelocityMps;
    assert(gate.update(.01f,{matching}).intensity==0); // relative motion
    assert(gate.update(0,{sample(4)}).intensity==0);
    assert(gate.update(.01f,{sample(4)}).intensity>0); // paused sample not consumed
    gate.reset(); auto invalid=sample(1);invalid.normalWorld={};
    assert(gate.update(.01f,{invalid}).intensity==0);
    invalid=sample(2);invalid.headVelocityMps.z=std::numeric_limits<float>::quiet_NaN();
    assert(gate.update(.01f,{invalid}).intensity==0);
    auto wall=sample(3);wall.normalWorld={1,0,0};wall.headVelocityMps={-8,0,0};
    assert(gate.update(.01f,{wall}).intensity>0);
    gate.reset();
    assert(gate.update(.01f,{sample(1,.8f),sample(1,8)}).closingSpeedMps==8);
    // A rapidly alternating manifold remains bounded by the global cooldown.
    auto other=sample(2);other.otherBodyIdentity=2;
    assert(gate.update(.01f,{other}).intensity==0);
    for(int i=0;i<20;++i)gate.update(.01f,{});
    assert(gate.update(.01f,{sample(3)}).intensity>0);
    gate.update(.01f,{sample(4,-1)}); // real departure rearms same surface
    for(int i=5;i<30;++i)gate.update(.01f,{sample(i,0)});
    assert(gate.update(.01f,{sample(30)}).intensity>0);
    // The old solver impulse is zero for a stationary solver even though the
    // swept/keyframed body has a real incoming impact. Driver must still play.
    Bridge bridge;RuntimeDriver driver(bridge);driver.onEquip();
    auto c=sample(1);c.headCenterM=driver.controller().solver().headPosition();
    ChainSolver stationary;stationary.reset({});
    assert(stationary.applyWorldContacts({c})==0);
    bridge.pending={c};driver.update(1.f/90);
    assert(bridge.impacts==1&&bridge.point.z==3);
    for(int i=2;i<60;++i){c.physicsStep=i;bridge.pending={c};driver.update(1.f/90);}
    assert(bridge.impacts==1); // even legacy impulse=100 cannot double/repeat
    driver.onUnequip();driver.onEquip();c.physicsStep=1;bridge.pending={c};driver.update(1.f/90);
    assert(bridge.impacts==2); // ownership reset clears episodes and step counter
    std::cout<<"WORLD_IMPACT_AUDIO_PASS incoming sweep, floor/wall, relative speed, sustained/stale rejection, spatial position, runtime reset\n";
}
