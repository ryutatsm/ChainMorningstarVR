#include "Source/SKSE/OffhandInputCore.hpp"
#include <cassert>
#include <cstring>
#include <iostream>

namespace {
// Independent OpenVR ABI expectations: do not derive these from the decoder.
constexpr std::uint64_t trigger=1ull<<33,grip=1ull<<2,stick=1ull<<32,other=1ull<<7;
cms::ControllerState state(std::uint64_t pressed,std::uint32_t packet=73) {
    cms::ControllerState s{};s.packet=packet;s.pressed=pressed;s.touched=trigger|grip|stick|other;
    for(int i=0;i<10;++i)s.axes[i]=.05f*float(i+1);
    return s;
}
void equal(const cms::ControllerState& a,const cms::ControllerState& b) {
    assert(a.packet==b.packet&&a.pressed==b.pressed&&a.touched==b.touched);
    assert(std::memcmp(a.axes,b.axes,sizeof a.axes)==0);
}
}

int main() {
    cms::OffhandTriggerInput input;
    input.arm(1,true,1000);
    auto s=state(grip|stick|other),expected=s;
    assert(!input.sample(1,s,1001));equal(s,expected);
    assert(!input.read(1,1001).down); // a sheath press must not become a ball grab
    // Merely touching the trigger is not a squeeze.
    assert(!input.sample(1,s,1002));equal(s,expected);
    s=state(trigger|grip|stick|other);expected=s;
    expected.pressed&=~trigger;expected.touched&=~trigger;
    assert(input.sample(1,s,1003));equal(s,expected);
    const auto captured=input.read(1,1004);
    assert(captured.fresh&&captured.down&&captured.captured&&captured.pressed);
    assert(captured.receivedPressed==(trigger|grip|stick|other));
    // HIGGS delayed replay cannot leak our owned trigger to Skyrim.
    s.pressed|=trigger;s.touched|=trigger;
    input.filterFinal(1,s,1004);equal(s,expected);
    input.arm(1,false,1005);
    s=state(trigger);assert(input.sample(1,s,1006));assert(!(s.pressed&trigger));
    // The falling-edge sample also blocks delayed replay, then ownership ends.
    s=state(grip);assert(!input.sample(1,s,1007));
    expected=s;s.pressed|=trigger;s.touched|=trigger;
    input.filterFinal(1,s,1007);equal(s,expected);
    s=state(grip);expected=s;assert(!input.sample(1,s,1008));
    input.filterFinal(1,s,1008);equal(s,expected);
    // Ordinary HIGGS grabs (not armed), right-hand combat, and declined input
    // retain all original controller bytes.
    s=state(trigger|grip);expected=s;assert(!input.sample(1,s,1009));equal(s,expected);
    input.arm(1,true,1010);
    assert(!input.sample(2,s,1011));equal(s,expected);
    assert(!input.sample(1,s,1012));equal(s,expected); // do not steal a held trigger
    s=state(0);input.sample(1,s,1013);
    s=state(trigger|grip);expected=s;assert(!input.sample(1,s,1014,false));equal(s,expected);
    assert(!input.sample(1,s,1015));equal(s,expected); // no false edge on acceptance
    s=state(0);input.sample(1,s,1016);
    s=state(trigger|grip);assert(input.sample(1,s,1017));
    input.reset();
    s=state(trigger|grip);expected=s;input.filterFinal(1,s,1018);equal(s,expected);
    input.arm(1,true,1018);assert(!input.sample(1,s,1019));equal(s,expected);
    s=state(0);input.sample(1,s,1020);
    s=state(trigger);assert(input.sample(1,s,1021));
    s=state(trigger,74);expected=s;input.filterFinal(1,s,1022);equal(s,expected); // not our poll
    s=state(trigger);expected=s;input.filterFinal(1,s,1200);equal(s,expected); // expired
    assert(!input.sample(64,s,1201));equal(s,expected);
    std::cout<<"OFFHAND_INPUT_PASS trigger decoding, side-grip/axes/right-hand preservation, delayed replay, release, reset, stale and accepted input\n";
}
