#include "Source/SKSE/ChainRuntimeCore.hpp"
#include <cassert>
#include <iostream>
using namespace cms;

static void floorContact(ChainSolver& s,std::uint64_t step,Vec3 surface={}) {
    HeadWorldContact c{};
    c.physicsStep=step;c.headCenterM=s.headPosition();c.normalWorld={0,0,1};
    c.pointM={s.headPosition().x,s.headPosition().y,.18f};
    c.signedDistanceM=s.headPosition().z-.18f;c.otherBodyIdentity=1;
    c.surfaceVelocityMps=surface;
    s.applyWorldContacts({c,c,c});
}
static float drag(float friction,float pullSpeed=.10f) {
    ChainConfig cfg;cfg.headStaticFriction=friction;cfg.headSlidingFriction=friction*.6875f;
    ChainSolver s(cfg);const Vec3 anchor{0,0,.7f};s.reset(anchor);
    for(std::uint64_t i=1;i<=90;++i) {
        s.step90Hz(anchor,nullptr,{{.35f,0,.1805f},true});floorContact(s,i);
    }
    const auto start=s.headPosition();
    for(std::uint64_t i=91;i<=360;++i) {
        floorContact(s,i);
        s.step90Hz({pullSpeed*static_cast<float>(i-90)/90,0,.7f});
        assert(s.headPosition().z>=.1799f);
        assert(isFinite(s.headVelocity90Hz()));
        assert(s.maxConstraintErrorM()<.006f);
    }
    return length(s.headPosition()-start);
}
int main() {
    const float oldDrift=drag(0),newDrift=drag(.8f);
    std::cout<<"Floor drag old="<<oldDrift<<"m new="<<newDrift<<"m\n";
    assert(oldDrift>.02f && newDrift<oldDrift*.2f && newDrift<.01f);
    assert(drag(.8f,.50f)>.2f); // A taut, deliberately pulled chain still drags it.
    // No floor evidence means the free swing remains identical.
    ChainConfig off;off.headStaticFriction=off.headSlidingFriction=0;
    ChainSolver a,b(off);a.reset({0,0,1},{1,0,0});b.reset({0,0,1},{1,0,0});
    for(int i=0;i<180;++i){a.step90Hz({0,0,1});b.step90Hz({0,0,1});}
    assert(length(a.headPosition()-b.headPosition())<1e-6f);
    assert(a.headSurfaceSlipMps()==0&&!a.headTouchesSurface());
    // The held endpoint stays at the palm despite resting-floor friction.
    a.reset({0,0,.7f});
    for(std::uint64_t i=1;i<90;++i) {
        const Vec3 target{.2f+.001f*static_cast<float>(i),0,.1805f};
        floorContact(a,i);a.step90Hz({0,0,.7f},nullptr,{target,true});
        assert(length(a.headPosition()-target)<.002f);
    }
    for(int i=0;i<6;++i)a.step90Hz({0,0,.7f});
    assert(!a.headTouchesSurface() && a.headSurfaceSlipMps()==0);
    ChainSolver platform;platform.reset({0,0,.7f});
    for(std::uint64_t i=1;i<90;++i) {
        platform.step90Hz({0,0,.7f},nullptr,{{.3f,0,.1805f},true});floorContact(platform,i);
    }
    const auto before=platform.headPosition();
    for(std::uint64_t i=90;i<270;++i) {
        floorContact(platform,i,{.05f,0,0});platform.step90Hz({0,0,.7f});
    }
    assert(platform.headPosition().x-before.x>.085f); // Friction is surface-relative.
    std::cout<<"SURFACE_FRICTION_PASS sustained support, triple-manifold deduplication, free swing, held motion, contact expiry\n";
}
