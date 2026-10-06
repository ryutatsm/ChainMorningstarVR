#include "Source/SKSE/OffhandGrabCore.hpp"
#include "Source/SKSE/PlayerBodyCollisionCore.hpp"
#include "Source/SKSE/GameBridgeContract.hpp"
#include <cassert>
#include <iostream>
#include <limits>

int main() {
    using namespace cms;
    OffhandGrabState grab;
    RigidTransform palm; palm.translation={.08f,0,-.8f};
    const Vec3 head{0,0,-.8f};
    const auto sample=[&](bool down,bool captured,bool free,Vec3 p) {
        palm.translation=p;
        return grab.update(true,down,captured,free,palm,head,{},.15f,kStraightReachM,1.0f/90);
    };
    assert(!sample(false,false,true,palm.translation).active);
    auto hold=sample(true,true,true,palm.translation);
    assert(hold.active&&length(hold.positionM-head)<1e-6f); // no snap on grab
    hold=sample(true,true,true,{.12f,0,-.8f});
    assert(hold.active&&std::fabs(hold.positionM.x-.04f)<1e-6f);
    assert(!sample(false,false,true,palm.translation).active);
    assert(!sample(true,true,false,palm.translation).active); // occupied offhand
    assert(!sample(true,true,true,palm.translation).active); // needs a new press
    sample(false,false,true,{.5f,0,-.8f});
    assert(!sample(true,true,true,{.5f,0,-.8f}).active); // no remote pull
    sample(false,false,true,{.08f,0,-.8f});
    assert(sample(true,true,true,{.08f,0,-.8f}).active);
    assert(!sample(true,true,true,{2,0,0}).active); // tracking jump/overextension
    grab.reset();
    assert(!grab.held());
    const Vec3 tautHead{0,0,-kStraightReachM-.01f};
    palm.translation=tautHead+Vec3{.08f,0,0};
    const auto taut=grab.update(true,true,true,true,palm,tautHead,{},.15f,kStraightReachM,1.f/90);
    assert(taut.active&&length(taut.positionM)<=kStraightReachM+.0001f);
    grab.reset();

    // Release diagnostics must distinguish each fail-closed branch, rather
    // than turning every short hold into an unexplained "released" entry.
    const auto startHold=[&] {
        grab.reset();palm={};palm.translation={.08f,0,-.8f};
        assert(sample(true,true,true,palm.translation).active);
    };
    startHold();
    assert(!sample(false,false,true,palm.translation).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kGripReleased);
    startHold();
    assert(!sample(true,false,true,palm.translation).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kInputNotCaptured);
    startHold();
    assert(!sample(true,true,false,palm.translation).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kHandUnavailable);
    assert(!sample(true,true,true,palm.translation).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kNeedsNewPress);
    startHold();
    assert(!grab.update(false,true,true,true,palm,head,{},.15f,kStraightReachM,1.f/90).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kInputStale);
    startHold();palm.rotation.m[0][0]=2;
    assert(!sample(true,true,true,palm.translation).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kInvalidPose);
    startHold();
    assert(!sample(true,true,true,{.5f,0,-.8f}).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kTrackingJump);
    startHold();
    assert(!grab.update(true,true,true,true,palm,head+Vec3{.4f,0,0},{},.15f,kStraightReachM,1.f/90).active);
    assert(grab.diagnostic().reason==OffhandGrabReason::kHeadObstructed);
    startHold();
    for(int i=1;i<=30&&grab.held();++i)
        grab.update(true,true,true,true,palm,head,{0,0,.025f*i},.15f,kStraightReachM,1.f/90);
    assert(!grab.held()&&grab.diagnostic().reason==OffhandGrabReason::kChainOverextended);

    // A second endpoint must remain fixed while the 19 links sag. Releasing
    // resumes gravity; sampled movement must not inject unbounded throw speed.
    for (float hz:{45.f,72.f,90.f,120.f,144.f}) {
        FixedStepChain chain;
        chain.reset({0,0,1.2f},{1,0,-.1f});
        const Vec3 target{.6f,0,.7f};
        for (int i=0;i<int(hz*2);++i) chain.update(1/hz,{0,0,1.2f},nullptr,{target,true});
        assert(length(chain.solver().headPosition()-target)<1e-4f);
        assert(chain.solver().maxConstraintErrorM()<.012f);
        const float z=chain.solver().headPosition().z;
        for (int i=0;i<10;++i) chain.update(1/hz,{0,0,1.2f});
        assert(chain.solver().headPosition().z<z);
        assert(length(chain.solver().headVelocity90Hz())<8.1f);
    }
    ChainSolver solver;
    solver.reset({0,0,1.2f});
    HeadWorldContact floor{};floor.physicsStep=1;floor.headCenterM=solver.headPosition();
    floor.normalWorld={0,0,1};floor.pointM=floor.headCenterM;floor.signedDistanceM=-.01f;
    floor.otherBodyIdentity=55;solver.applyWorldContacts({floor});
    solver.step90Hz({0,0,1.2f},nullptr,{{0,0,.16f},true});
    assert(solver.headPosition().z>=floor.headCenterM.z+.009f); // floor beats hand

    const BodyCapsule torso{{0,0,-.5f},{0,0,.5f},{0,0,-.5f},{0,0,.5f},.15f,1};
    ChainLinkSweep sweep{5,{-1,0,0},{1,0,0},{0,0,1},{0,0,1},.03f,.02f};
    std::vector<ChainLinkContact> contacts;
    queryPlayerBodyContacts({sweep},{torso},1.f/90,contacts);
    assert(contacts.size()==1&&contacts[0].normalWorld.x<-.99f); // full crossing
    assert(contacts[0].linkIndex==5&&contacts[0].otherBodyIdentity==1);
    contacts.clear();sweep.fromM=sweep.toM={-.2f,0,0};
    queryPlayerBodyContacts({sweep},{torso},1.f/90,contacts);
    assert(contacts.empty()); // small near miss
    sweep.fromM=sweep.toM={-.17f,0,0};
    queryPlayerBodyContacts({sweep},{torso},1.f/90,contacts);
    assert(contacts.size()==1); // resting overlap
    contacts.clear();sweep.fromM=sweep.toM={0,0,0};
    BodyCapsule moving=torso;moving.previousA.x=moving.previousB.x=-1;
    moving.a.x=moving.b.x=1;
    queryPlayerBodyContacts({sweep},{moving},.05f,contacts);
    assert(contacts.size()==1&&contacts[0].normalWorld.x>.99f);
    assert(length(contacts[0].surfaceVelocityMps)<=10.01f);
    contacts.clear();moving.radiusM=std::numeric_limits<float>::quiet_NaN();
    queryPlayerBodyContacts({sweep},{moving},.05f,contacts);
    assert(contacts.empty());
    queryPlayerBodyContacts({sweep},{},.05f,contacts);
    assert(contacts.empty()); // no persistent self-body planes after removal
    std::cout<<"PLAYER_INTERACTION_PASS grip offset/release/ownership, pinned head, gravity, body sweep/overlap/motion\n";
}
