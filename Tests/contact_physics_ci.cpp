#include "Source/SKSE/ChainRuntimeCore.hpp"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <vector>

using namespace cms;

static HeadWorldContact planeContact(const ChainSolver& solver, std::uint64_t step,
                                    Vec3 normal, Vec3 centreLimit, std::uintptr_t body=1) {
    HeadWorldContact sample{};
    sample.physicsStep=step;
    sample.headCenterM=solver.headPosition();
    sample.normalWorld=normal;
    sample.headVelocityMps=solver.headVelocity90Hz();
    sample.signedDistanceM=dot(sample.headCenterM-centreLimit,normal);
    sample.pointM=centreLimit;
    sample.otherBodyIdentity=body;
    return sample;
}

int main() {
    // A head falling through a late-reported floor is corrected outside it;
    // recovery is not interpreted as a high outward velocity. Its links follow.
    ChainSolver falling{};
    falling.reset({0,0,0},{1,0,0});
    for(int i=0;i<35;++i) falling.step90Hz({0,0,0});
    const Vec3 incoming=falling.headVelocity90Hz();
    assert(incoming.z < -0.5f);
    const float floorCentreZ=falling.headPosition().z+0.04f;
    auto floor=planeContact(falling,1,{0,0,1},{0,0,floorCentreZ});
    const float impulse=falling.applyWorldContacts({floor,floor,floor});
    assert(impulse>0.0f);
    assert(falling.activeContactCount()==1);
    assert(falling.headPosition().z >= floorCentreZ);
    assert(falling.headVelocity90Hz().z>0.0f);
    assert(falling.headVelocity90Hz().z < -incoming.z*0.09f);
    assert(length(falling.headVelocity90Hz()) <= length(incoming)+0.001f);
    assert(falling.maxConstraintErrorM()<0.004f);

    // Re-delivery and older physics steps cannot kick the head a second time.
    const Vec3 positionOnce=falling.headPosition();
    const Vec3 velocityOnce=falling.headVelocity90Hz();
    assert(falling.applyWorldContacts({floor})==0.0f);
    assert(length(falling.headPosition()-positionOnce)==0.0f);
    assert(length(falling.headVelocity90Hz()-velocityOnce)==0.0f);
    assert(falling.lastContactPhysicsStep()==1);

    // Resting contact must oppose gravity across many solver iterations without
    // accumulating an impulse once per iteration or creeping through the floor.
    for(std::uint64_t i=2;i<182;++i) {
        falling.step90Hz({0,0,0});
        const auto next=planeContact(falling,i,{0,0,1},{0,0,floorCentreZ});
        falling.applyWorldContacts({next});
        assert(falling.headPosition().z >= floorCentreZ-0.00001f);
        assert(isFinite(falling.headPosition()) && isFinite(falling.headVelocity90Hz()));
        assert(length(falling.headVelocity90Hz())<10.0f);
    }

    // Missing callbacks have a bounded lifetime. A finite object's former
    // contact plane must not become a permanent invisible wall.
    for(int i=0;i<6;++i) falling.step90Hz({0,0,0});
    assert(falling.activeContactCount()==0);

    // A moving support carries the resting head at the support's velocity.
    ChainSolver moving{};
    moving.reset({0,0,0},{1,0,0});
    auto support=planeContact(moving,1,{0,0,1},{0,0,0});
    support.surfaceVelocityMps={0,0,0.25f};
    moving.applyWorldContacts({support});
    moving.step90Hz({0,0,0});
    assert(moving.headPosition().z >= 0.25f/90.0f);
    assert(moving.headVelocity90Hz().z >= 0.249f);

    // A late high-speed wall sample corrects the whole overshoot, rather than
    // applying penetration each iteration or allowing a target beyond the wall.
    ChainSolver fast{};
    fast.reset({0,0,0},{0,0,-1});
    for(int i=1;i<=16;++i) fast.step90Hz({0.035f*static_cast<float>(i),0,0});
    const Vec3 fastIncoming=fast.headVelocity90Hz();
    const Vec3 fastCentre=fast.headPosition();
    const float wallCentreX=fastCentre.x-0.20f;
    auto wall=planeContact(fast,22,{-1,0,0},{wallCentreX,0,0});
    fast.applyWorldContacts({wall});
    assert(fast.headPosition().x<=wallCentreX);
    assert(length(fast.headVelocity90Hz()) <= length(fastIncoming)+0.01f);
    for(int i=0;i<3;++i) {
        fast.step90Hz({0.56f,0,0});
        assert(fast.headPosition().x<=wallCentreX+0.0001f);
    }

    // Two different bodies in a corner must both constrain the head, including
    // when only the latest of multiple queued physics steps should be applied.
    ChainSolver corner{};
    corner.reset({0,0,0},{1,0,0});
    auto side=planeContact(corner,4,{-1,0,0},{1.055f,0,0},1);
    auto base=planeContact(corner,4,{0,0,1},{0,0,0.005f},2);
    auto stale=planeContact(corner,3,{1,0,0},{1.5f,0,0},3);
    corner.applyWorldContacts({stale,side,base});
    assert(corner.activeContactCount()==2);
    assert(corner.headPosition().x<=1.055f && corner.headPosition().z>=0.005f);
    corner.step90Hz({0,0,0});
    assert(corner.headPosition().x<=1.0551f && corner.headPosition().z>=0.0049f);

    // Invalid native data cannot poison position, velocity or the accepted-step
    // watermark (a valid sample with that sequence must still be accepted).
    auto bad=planeContact(corner,50,{0,0,1},{0,0,0.005f});
    const Vec3 beforeBad=corner.headPosition();
    bad.normalWorld.x=std::numeric_limits<float>::quiet_NaN();
    assert(corner.applyWorldContacts({bad})==0.0f);
    assert(corner.lastContactPhysicsStep()==4);
    assert(length(corner.headPosition()-beforeBad)==0.0f);
    bad.normalWorld={0,0,0};
    assert(corner.applyWorldContacts({bad})==0.0f);
    bad.normalWorld={0,0,1};
    bad.signedDistanceM=-2.0f;
    assert(corner.applyWorldContacts({bad})==0.0f);

    // Render/physics scheduling: the same controller motion and floor must
    // settle within 5 mm at supported HMD refresh rates, even when one callback
    // covers two 90 Hz solver steps. The floor is always measured in world space.
    Vec3 rateReference{};
    float maximumRateDelta=0.0f;
    for(float hz : {90.0f,45.0f,72.0f,80.0f,120.0f,144.0f}) {
        ChainController rateController{};
        rateController.onEquip({0,0,0},{1,0,0});
        std::uint64_t nativeStep=0;
        for(int frame=1;frame<=static_cast<int>(2.0f*hz);++frame) {
            const float time=static_cast<float>(frame)/hz;
            rateController.update(1.0f/hz,{0.10f*time*kSkyrimUnitsPerMeter,0,0});
            const auto& state=rateController.solver();
            if(state.headPosition().z < -0.449f) {
                const auto sample=planeContact(state,++nativeStep,{0,0,1},{0,0,-0.45f});
                rateController.applyWorldContacts({sample});
                assert(state.headPosition().z>=-0.45001f);
            }
        }
        const Vec3 settled=rateController.solver().headPosition();
        if(hz==90.0f) rateReference=settled;
        maximumRateDelta=std::max(maximumRateDelta,length(settled-rateReference));
        assert(length(settled-rateReference)<0.005f);
        assert(rateController.solver().maxConstraintErrorM()<0.004f);
    }

    // Ownership/lifecycle boundaries clear both cached contacts and sequence
    // state. A new native body starts its own contact sequence safely.
    ChainController controller{};
    controller.onEquip({0,0,0},{1,0,0});
    auto owned=planeContact(controller.solver(),90,{0,0,1},{0,0,0});
    controller.applyWorldContacts({owned});
    assert(controller.solver().activeContactCount()==1);
    controller.onUnequip();
    assert(controller.solver().activeContactCount()==0);
    assert(controller.applyWorldContacts({owned})==0.0f);
    controller.onEquip({0,0,0},{1,0,0});
    assert(controller.solver().lastContactPhysicsStep()==0);
    owned.physicsStep=1;
    controller.applyWorldContacts({owned});
    assert(controller.solver().lastContactPhysicsStep()==1);
    controller.update(1.0f/90.0f,{1000,0,0});
    assert(controller.solver().activeContactCount()==0);
    assert(controller.headSweep().speedMps==0.0f);

    std::cout << "CMS world contact feedback CI PASS\n";
    std::cout << "fall_contact_impulse_kg_mps=" << impulse << "\n";
    std::cout << "45_144_hz_contact_max_delta_m=" << maximumRateDelta << "\n";
}
