#include "Source/SKSE/GameBridgeContract.hpp"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

struct ContactBridge final : cms::IGameBridge {
    cms::Vec3 anchor{};
    std::vector<cms::HeadWorldContact> pending;
    std::vector<std::string> events;
    cms::HeadPose submitted{};
    cms::HeadSweep sweep{};
    bool anchorValid{true};
    bool acquired{};
    int generation{};
    int contactReads{};
    int nativePoses{};

    bool tryGetChainAnchorWorldSU(cms::Vec3& out, cms::Vec3& direction) override {
        events.emplace_back("anchor");out=anchor;direction={0,0,-1};return anchorValid;
    }
    bool reacquireWeaponNodes() override {
        events.emplace_back("acquire"); acquired=true; ++generation; return true;
    }
    void releaseWeaponNodes() override {
        events.emplace_back("release"); acquired=false; pending.clear();
    }
    void applyVisualFrame(const cms::VisualFrame& frame) override {
        assert(acquired);events.emplace_back("visual");submitted=frame.head;
    }
    bool updateNativeMeleeHeadProxy(const cms::HeadSweep&) override { assert(false);return false; }
    void submitNativePose(const cms::HeadPose& pose,const cms::HeadSweep& headSweep,float dt) override {
        assert(acquired && dt>0);events.emplace_back("pose");submitted=pose;sweep=headSweep;++nativePoses;
    }
    std::vector<cms::HeadWorldContact> consumeWorldContacts() override {
        events.emplace_back("contacts");++contactReads;auto result=pending;pending.clear();return result;
    }
    float consumeWorldContactImpulse() override {events.emplace_back("impulse");return 0;}
    void playChainRattle(float) override {}
    void playChainClank(float) override {}
};

int main() {
    using namespace cms;
    ContactBridge bridge;
    RuntimeDriver driver(bridge);
    driver.onEquip();
    assert(driver.active() && bridge.generation==1);
    bridge.events.clear();
    HeadWorldContact contact{};
    contact.physicsStep=1;contact.headCenterM=driver.controller().solver().headPosition();
    contact.normalWorld={0,0,1};contact.signedDistanceM=-0.02f;
    contact.pointM=contact.headCenterM;contact.otherBodyIdentity=1;
    bridge.pending.push_back(contact);
    driver.update(1.0f/90.0f);
    assert((bridge.events==std::vector<std::string>{"anchor","contacts","visual","pose","impulse"}));
    assert(bridge.submitted.centerM.z >= contact.headCenterM.z+0.019f);
    assert(driver.controller().solver().activeContactCount()==1);

    // Invalid/paused time performs ownership checks only. No pending contacts
    // are drained, no native pose is submitted and no sound impulse is consumed.
    for(float dt : {0.0f,-0.01f,std::numeric_limits<float>::quiet_NaN(),
                    std::numeric_limits<float>::infinity()}) {
        bridge.events.clear();bridge.pending={contact};
        const int reads=bridge.contactReads,poses=bridge.nativePoses;
        driver.update(dt);
        assert((bridge.events==std::vector<std::string>{"anchor"}));
        assert(bridge.contactReads==reads && bridge.nativePoses==poses && bridge.pending.size()==1);
    }

    // A tracked teleport must release the old native owner and discard its
    // contacts before any pose at the new location is submitted.
    bridge.anchor={1000,0,0};bridge.events.clear();
    assert(driver.controller().wouldTeleportReset(bridge.anchor));
    assert(!driver.controller().wouldTeleportReset({std::numeric_limits<float>::quiet_NaN(),0,0}));
    driver.update(1.0f/90.0f);
    assert(driver.active() && bridge.generation==2);
    const auto release=std::find(bridge.events.begin(),bridge.events.end(),"release");
    const auto consume=std::find(bridge.events.begin(),bridge.events.end(),"contacts");
    const auto pose=std::find(bridge.events.begin(),bridge.events.end(),"pose");
    assert(release!=bridge.events.end() && release<pose);
    assert(consume==bridge.events.end() || release<consume);
    assert(bridge.pending.empty());
    assert(driver.controller().solver().activeContactCount()==0);
    assert(driver.controller().solver().lastContactPhysicsStep()==0);
    assert(bridge.submitted.centerM.x>14.0f);
    // There must be no attack path spanning the teleport frame.
    assert(bridge.sweep.speedMps==0.0f && length(bridge.sweep.toM-bridge.sweep.fromM)==0.0f);

    // Even while paused, losing weapon ownership clears the native queue.
    bridge.pending={contact};bridge.anchorValid=false;bridge.events.clear();
    driver.update(0.0f);
    assert(!driver.active() && !bridge.acquired && bridge.pending.empty());
    assert((bridge.events==std::vector<std::string>{"anchor","release"}));
    assert(!driver.controller().wouldTeleportReset({2000,0,0}));
    std::cout << "CMS runtime contact ordering CI PASS\n";
}
