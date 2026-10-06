#include "Source/SKSE/GameBridgeContract.hpp"
#include "Source/SKSE/GripCaptureCore.hpp"
#include "Source/SKSE/OffhandGrabCore.hpp"
#include "Source/SKSE/PlayerBodyCollisionCore.hpp"
#include <cassert>
#include <iostream>

namespace {
using namespace cms;
// Runs the real RuntimeDriver order (contact drain -> input/hold -> fixed steps
// -> visual -> native pose). This is a portable adapter fixture, not Havok/VR.
struct InteractionBridge final : IGameBridge {
    GripCaptureState capture;
    OffhandGrabState grab;
    RigidTransform palm{};
    VisualFrame visual{};
    HeadPose native{};
    HeadHoldTarget hold{};
    Vec3 anchor{0,0,1.4f};
    float scale{.85f}, clockMs{1000}, floorZ{-10};
    bool owns{true}, freeHand{true}, floor{}, body{}, poll{true};
    unsigned submitted{}, chainContacts{};
    std::uint64_t step{};
    bool tryGetChainAnchorWorldSU(Vec3& out,Vec3& direction) override {
        out=anchor*kSkyrimUnitsPerMeter;direction={0,0,-1};return owns;
    }
    bool reacquireWeaponNodes() override { return owns; }
    void releaseWeaponNodes() override {capture.reset();grab.reset();hold={};}
    HeadHoldTarget updatePlayerInteraction(const HeadPose& head,Vec3 a,float dt) override {
        const auto input=capture.read(1,std::uint64_t(clockMs));
        const float radius=kHeadBroadphaseRadiusM*scale;
        hold=grab.update(input.fresh,input.down,input.captured,freeHand,
            palm,head.centerM,a,radius,kStraightReachM,dt);
        const bool nearHead=length(palm.translation-head.centerM)<=radius+.06f;
        capture.arm(1,freeHand&&(hold.active||(nearHead&&!input.down)),std::uint64_t(clockMs));
        return hold;
    }
    void applyVisualFrame(const VisualFrame& frame) override {
        visual=frame;
        RigidTransform parent{anchor*kSkyrimUnitsPerMeter,basisFromLocalZ({.2f,.5f,1}),scale};
        // Exercise the same inverse-parent conversion as writeNodeWorldPose.
        const auto local=worldToLocalPoint(parent,frame.head.centerM*kSkyrimUnitsPerMeter);
        assert(length(localToWorldPoint(parent,local)*kMetersPerSkyrimUnit-frame.head.centerM)<1e-5f);
    }
    void submitNativePose(const HeadPose& pose,const HeadSweep&,float) override {
        native=pose;++submitted;
        assert(length(native.centerM-visual.head.centerM)<1e-6f);
    }
    bool updateNativeMeleeHeadProxy(const HeadSweep&) override {return true;}
    std::vector<HeadWorldContact> consumeWorldContacts() override {
        ++step;
        if (!floor||!submitted) return {};
        const float radius=kHeadBroadphaseRadiusM*scale;
        const float gap=native.centerM.z-radius-floorZ;
        if (gap>.02f) return {};
        HeadWorldContact c{};c.physicsStep=step;c.headCenterM=native.centerM;
        c.normalWorld={0,0,1};c.pointM=native.centerM-Vec3{0,0,radius};
        c.signedDistanceM=gap;c.otherBodyIdentity=90;
        return {c};
    }
    void queryChainContacts(const std::vector<ChainLinkSweep>& sweeps,
                            std::vector<ChainLinkContact>& contacts) override {
        if (!body) return;
        const BodyCapsule capsule{{.04f,0,1.1f},{.04f,0,1.0f},
            {.04f,0,1.1f},{.04f,0,1.0f},.035f,1};
        const auto before=contacts.size();
        queryPlayerBodyContacts(sweeps,{capsule},1.f/90,contacts);
        chainContacts+=static_cast<unsigned>(contacts.size()-before);
    }
    float chainCollisionScale() const override {return scale;}
    float consumeWorldContactImpulse() override {return 0;}
    void playChainRattle(float) override {}
    void playChainClank(float) override {}
    void tick(RuntimeDriver& driver,float dt,bool down) {
        clockMs+=dt*1000;
        if (poll) capture.sample(1,down,std::uint64_t(clockMs));
        driver.update(dt);
    }
    void approach(RuntimeDriver& driver,float dt) {
        palm.translation=driver.controller().visualFrame().head.centerM+Vec3{.142f*scale/.85f,0,0};
        tick(driver,dt,false);
    }
};
}

int main() {
    using namespace cms;
    for (float hz:{45.f,50.f,72.f,80.f,90.f,120.f,144.f}) {
        for (float scale:{.85f,1.f,1.2f}) {
            InteractionBridge bridge;bridge.scale=scale;
            RuntimeDriver driver{bridge};driver.onEquip();
            const float dt=1/hz;
            for (int i=0;i<int(hz*2);++i) bridge.tick(driver,dt,false);
            bridge.approach(driver,dt);
            const auto start=bridge.palm.translation;
            const float loadedReach=length(driver.controller().solver().headPosition()-bridge.anchor);
            bool crossedOldCutoff=false;
            for (int i=0;i<int(hz*3);++i) {
                const float t=i/hz;
                // Slow 7cm outward movement, then lift/sweep with both hands.
                const float outward=std::min(.07f,.2f*t);
                const float lift=t>1?std::min(.3f,.3f*(t-1)):0;
                const float travel=t>1?.07f*(t-1):0;
                bridge.anchor.x=travel;
                bridge.palm.translation=start+Vec3{travel,0,lift-outward};
                bridge.tick(driver,dt,true);
                crossedOldCutoff|=loadedReach+outward>kStraightReachM+.04f;
                assert(bridge.grab.held());
                assert(bridge.hold.active);
                assert(length(bridge.hold.positionM-bridge.anchor)<=kStraightReachM+1e-5f);
                assert(length(bridge.native.centerM-bridge.hold.positionM)<.025f);
                assert(isFinite(bridge.native.centerM));
            }
            assert(crossedOldCutoff); // this sequence fails rc2 at ~140ms/50Hz
            const auto releasedAt=bridge.native.centerM;
            for(int i=0;i<int(hz*.2f);++i)bridge.tick(driver,dt,false);
            assert(!bridge.grab.held());
            assert(bridge.native.centerM.z<releasedAt.z-.02f);
            assert(length(driver.controller().solver().headVelocity90Hz())<8.1f);

            // Regrabs, menu-equivalent teardown and loss of scene ownership.
            for(int repeat=0;repeat<4;++repeat) {
                bridge.approach(driver,dt);bridge.tick(driver,dt,true);
                assert(bridge.grab.held());
                driver.onUnequip();assert(!bridge.grab.held());
                driver.onEquip();bridge.approach(driver,dt);
            }
            bridge.tick(driver,dt,true);assert(bridge.grab.held());
            bridge.owns=false;bridge.tick(driver,dt,true);
            assert(!driver.active()&&!bridge.grab.held());
        }
    }
    // Real contact feedback remains authoritative while held. Player-body
    // link sweeps run in the same fixed step, not in a disconnected solver test.
    InteractionBridge bridge;RuntimeDriver driver{bridge};driver.onEquip();
    for(int i=0;i<100;++i)bridge.tick(driver,.02f,false);
    bridge.approach(driver,.02f);bridge.tick(driver,.02f,true);
    assert(bridge.grab.held());
    const float restingZ=bridge.native.centerM.z;
    bridge.floor=true;bridge.floorZ=restingZ-kHeadBroadphaseRadiusM*bridge.scale;
    bridge.body=true;
    for(int i=0;i<100;++i) {
        if(i<10)bridge.palm.translation.z-=.002f;
        bridge.tick(driver,.02f,true);
        assert(bridge.grab.held());
        assert(bridge.native.centerM.z>=restingZ-1e-4f);
    }
    assert(bridge.chainContacts>0);
    // A long polling outage really releases; normal stable input did not.
    bridge.poll=false;
    for(int i=0;i<9;++i)bridge.tick(driver,.02f,true);
    assert(!bridge.grab.held());
    assert(bridge.grab.diagnostic().reason==OffhandGrabReason::kInputStale);
    std::cout<<"OFFHAND_RUNTIME_PASS 21 frame-rate/scale cases, taut lift/sweep, release/regrab, lifecycle, native/visual contract, floor and body contacts, input timeout\n";
}
