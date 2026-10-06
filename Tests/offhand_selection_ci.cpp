#include "Source/SKSE/OffhandSelectionCore.hpp"
#include "Source/SKSE/GripCaptureCore.hpp"
#include "Source/SKSE/OffhandGrabCore.hpp"
#include <cassert>
#include <iostream>

namespace {
// Reduced ordering from pinned HIGGS Hand::Update/ControllerStateUpdate:
// picking the other weapon enters SelectedTwoHand (CanGrabObject=false), then
// its next grip enters HeldTwoHanded. Both used to prevent CMS from arming.
struct HiggsSelectionFixture {
    enum class State { Idle,SelectedTwoHand,HeldTwoHanded } state{State::Idle};
    void pick(bool weaponFound) {
        if(state!=State::HeldTwoHanded)
            state=weaponFound?State::SelectedTwoHand:State::Idle;
    }
    void grip(bool down) {
        if(state==State::SelectedTwoHand&&down)state=State::HeldTwoHanded;
    }
    bool canGrab() const {return state==State::Idle;}
};
}

int main() {
    constexpr std::uint32_t pick=0x2C;
    constexpr std::uint32_t owned=(23u<<16)|0x8000|(3u<<8)|56;
    cms::OffhandSelectionScope scope;
    assert(!scope.ignore(pick,owned)); // no effect outside HIGGS Update
    assert(!scope.begin(56)); // no certified player group
    assert(!scope.begin((23u<<16)|0x8000|5)); // no native weapon layer guess
    assert(scope.begin(owned));
    assert(scope.ignore(pick,owned));
    assert(scope.ignore(owned,pick));
    assert(scope.ignore(pick,owned|0x4000)); // HIGGS toggles disabled bit
    assert(!scope.ignore(pick,owned^(1u<<8))); // other hand/part
    assert(!scope.ignore(pick,owned^(1u<<16))); // NPC/other group
    assert(!scope.ignore(pick|(1u<<16),owned)); // not exact HIGGS pick sphere
    for(std::uint32_t layer=0;layer<128;++layer) {
        if(layer==pick)continue;
        assert(!scope.ignore(layer,owned)); // walls/floor/NPCs/physical hands
        assert(!scope.ignore(owned,layer));
    }
    assert(scope.end()==3);
    assert(!scope.ignore(pick,owned));

    HiggsSelectionFixture old;
    old.pick(true);
    assert(!old.canGrab()); // rc1 cannot arm when the ball is selected
    old.grip(true);
    assert(old.state==HiggsSelectionFixture::State::HeldTwoHanded); // user log

    cms::GripCaptureState capture;
    HiggsSelectionFixture fixed;
    scope.begin(owned);
    fixed.pick(!scope.ignore(pick,owned));
    scope.end();
    assert(fixed.canGrab());
    capture.arm(1,fixed.canGrab(),1000);
    const bool consumed=capture.sample(1,true,1001);
    fixed.grip(!consumed);
    assert(consumed&&fixed.canGrab());
    const auto input=capture.read(1,1002);
    cms::RigidTransform palm; palm.translation={.152f,0,-.8f};
    cms::OffhandGrabState grab;
    const auto held=grab.update(input.fresh,input.down,input.captured,fixed.canGrab(),
        palm,{0,0,-.8f},{},.153f,cms::kStraightReachM,1.f/90);
    assert(held.active); // in-range failed user's first attempt now has an owner
    capture.sample(1,false,1003);
    const auto release=capture.read(1,1004);
    assert(!grab.update(release.fresh,release.down,release.captured,true,
        palm,held.positionM,{},.153f,cms::kStraightReachM,1.f/90).active);
    assert(!scope.ignore(pick,owned)); // ordinary picking restored after bracket
    std::cout<<"OFFHAND_SELECTION_PASS rc1 two-hand interception reproduced; CMS capture/release; physical filters and other bodies preserved\n";
}
