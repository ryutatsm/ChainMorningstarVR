#include "Source/SKSE/OffhandGrabCore.hpp"
#include "Source/SKSE/GameBridgeContract.hpp"
#include "Source/SKSE/NativePoseCore.hpp"
#include "Source/SKSE/WeaponMeshContactCore.hpp"
#include <cassert>
#include <iostream>

using namespace cms;
static float angle(const Mat3& a,const Mat3& b) {return weaponmesh::rotationAngle(a,b);}
int main() {
    // Cross the old world-up switch in both hemispheres. The old code makes
    // a 90-degree roll from a 0.05-degree change in the chain's direction.
    float legacyJump=0,maximumStep=0;
    for(float sign:{-1.f,1.f}) {
        const auto direction=[&](float z) {return Vec3{std::sqrt(1-z*z),0,sign*z};};
        legacyJump=std::max(legacyJump,angle(basisFromLocalZ(direction(.8999f)),basisFromLocalZ(direction(.9001f))));
        Mat3 rotation=basisFromLocalZ(direction(.89f));
        for(int i=0;i<=2000;++i) {
            const float z=.89f+.02f*std::sin(i*.01f);
            const Mat3 next=transportLocalZ(rotation,direction(z));
            maximumStep=std::max(maximumStep,angle(rotation,next));
            assert(angle(rotation,next)<.002f);
            assert(approximatelyOrthonormal(next,.0001f));
            assert(length(column(next,2)-direction(z))<1e-5f);
            rotation=next;
        }
        const Mat3 reversed=transportLocalZ(rotation,-column(rotation,2),.05f);
        assert(angle(rotation,reversed)<.0501f);
    }
    assert(legacyJump>1.5f);

    // A rotating compound can report a different support height even though
    // the floor itself is stationary. Its recovery is geometric, not energy.
    // Legacy per-iteration projection produces repeated outward velocities.
    ChainSolver support; support.reset({0,0,.8f},{1,0,0});
    float recoveryUpSpeed=0;
    for(std::uint64_t i=1;i<=1800;++i) {
        support.step90Hz({.03f*std::sin(float(i)*.04f),0,.8f});
        const float centerZ=.15f+.03f*std::sin(float(i)*.10f);
        if(support.headPosition().z<centerZ+.015f) {
            HeadWorldContact c{};c.physicsStep=i;c.headCenterM=support.headPosition();
            c.normalWorld={0,0,1};c.signedDistanceM=c.headCenterM.z-centerZ;
            c.otherBodyIdentity=1;support.applyWorldContacts({c});
        }
        if(i>300) recoveryUpSpeed=std::max(recoveryUpSpeed,support.headVelocity90Hz().z);
    }
    assert(recoveryUpSpeed<.0005f);

    // Floor contact must not reorient a resting spiked head as the chain sags.
    // Compare the held pose to the released pose with a physical support plane.
    ChainController floorController;
    floorController.onEquip({0,0,.8f*kSkyrimUnitsPerMeter},{1,0,0});
    for(int i=0;i<90;++i) floorController.update(1.f/90,{0,0,.8f*kSkyrimUnitsPerMeter},nullptr,
        {{.3f,0,.16f},true,basisFromLocalZ({.5f,0,1})});
    const auto restingRotation=floorController.visualFrame().head.rotation;
    float peakRestSpeed=0;
    for(std::uint64_t i=1;i<=900;++i) {
        HeadWorldContact floor{};floor.physicsStep=i;
        floor.headCenterM=floorController.solver().headPosition();
        floor.normalWorld={0,0,1};floor.signedDistanceM=floor.headCenterM.z-.16f;
        floor.otherBodyIdentity=1;
        floorController.applyWorldContacts({floor});
        floorController.update(1.f/90,{.01f*std::sin(float(i)*.04f)*kSkyrimUnitsPerMeter,0,.8f*kSkyrimUnitsPerMeter});
        assert(angle(restingRotation,floorController.visualFrame().head.rotation)<.001f);
        assert(floorController.solver().headPosition().z>=.1599f);
        if(i>180) {
            peakRestSpeed=std::max(peakRestSpeed,length(floorController.solver().headVelocity90Hz()));
            assert(floorController.solver().headVelocity90Hz().z<.02f);
        }
    }

    // A hand deliberately below the support plane is blocked; after release
    // the accumulated depenetration must not turn into a throw.
    for(int i=0;i<90;++i) floorController.update(1.f/90,{0,0,.8f*kSkyrimUnitsPerMeter},nullptr,
        {{.3f,0,.16f},true,restingRotation});
    HeadWorldContact floor{};floor.physicsStep=1000;floor.headCenterM={.3f,0,.16f};
    floor.normalWorld={0,0,1};floor.signedDistanceM=0;floor.otherBodyIdentity=1;
    floorController.applyWorldContacts({floor});
    for(int i=0;i<3;++i) floorController.update(1.f/90,{0,0,.8f*kSkyrimUnitsPerMeter},nullptr,
        {{.3f,0,.12f},true,restingRotation});
    assert(std::fabs(floorController.solver().headVelocity90Hz().z)<.001f);
    floorController.update(1.f/90,{0,0,.8f*kSkyrimUnitsPerMeter});
    assert(floorController.solver().headVelocity90Hz().z<.02f);

    // Fixed grip means fixed full palm-relative pose, despite right-hand and
    // slack-chain motion. Turning the palm turns the emblem by exactly the
    // same rotation. Repeat across fixed-step/render ratios and release.
    for(float hz:{45.f,50.f,72.f,80.f,90.f,120.f,144.f}) {
        ChainController controller; controller.onEquip({0,0,1.4f*kSkyrimUnitsPerMeter});
        OffhandGrabState grab;
        RigidTransform palm{};palm.translation={.1f,0,.8f};
        // Put the head at a slack, collision-free grasp point.
        for(int i=0;i<int(hz);++i) controller.update(1/hz,{0,0,1.4f*kSkyrimUnitsPerMeter},nullptr,{{0,0,.8f},true,basisFromLocalZ({.2f,.3f,-1})});
        auto head=controller.visualFrame().head;
        const auto initial=head.rotation;
        const Vec3 offset=head.centerM-palm.translation;
        for(int i=0;i<int(hz*5);++i) {
            const float t=i/hz;
            palm.rotation=basisFromLocalZ({0,0,1},t*.2f);
            const Vec3 anchor{.07f*std::sin(t*4),0,1.4f};
            const auto hold=grab.update(true,true,true,true,palm,head.centerM,anchor,.15f,kStraightReachM,1/hz,head.rotation);
            assert(hold.active);
            controller.update(1/hz,anchor*kSkyrimUnitsPerMeter,nullptr,hold);
            head=controller.visualFrame().head;
            assert(head.held);
            assert(angle(head.rotation,mul(palm.rotation,initial))<.001f);
            assert(length(head.centerM-(palm.translation+mul(palm.rotation,offset)))<.001f);
        }
        const auto heldRotation=head.rotation;
        controller.update(1/hz,{0,0,1.4f*kSkyrimUnitsPerMeter});
        assert(!controller.visualFrame().head.held);
        assert(angle(heldRotation,controller.visualFrame().head.rotation)<=6/hz+.0001f);
        controller.onUnequip();controller.onEquip({0,0,100});
        assert(!controller.visualFrame().head.held);
    }

    // Model HIGGS's documented velocity-limit warp before the next cast.
    // Old code casts from this displaced/rotated pose, accumulating a false
    // floor/wall plane. The production continuity helper restores the exact
    // last CMS endpoint and forgets it at a body/world ownership boundary.
    NativePoseContinuity continuity;
    const Vec3 actualBall{.2f,.1f,.3f};
    const Mat3 actualRotation=basisFromLocalZ({0,0,-1});
    continuity.commit(actualBall,actualRotation);
    assert(!continuity.needsRestore(actualBall,actualRotation));
    assert(continuity.needsRestore(actualBall+Vec3{.5f,0,.5f},actualRotation));
    assert(continuity.needsRestore(actualBall,basisFromLocalZ({0,0,-1},1.5707963f)));
    assert(length(continuity.center()-actualBall)==0);
    assert(angle(continuity.rotation(),actualRotation)<.001f);
    continuity.reset();
    assert(!continuity.needsRestore({0,0,0},{}));
    std::cout<<"HEAD_STABILITY_PASS legacy_jump_rad="<<legacyJump<<" continuous_max_step_rad="<<maximumStep
             <<" recovery_up_speed_mps="<<recoveryUpSpeed
             <<" resting_peak_speed_mps="<<peakRestSpeed
             <<"; 7 refresh rates, full grip pose, blocked grip release, resting floor, native warp continuity\n";
}
