#include "Source/SKSE/GripCaptureCore.hpp"
#include <barrier>
#include <cassert>
#include <iostream>
#include <thread>

int main() {
    cms::GripCaptureState state;
    state.arm(1,true,1000);
    assert(!state.sample(2,true,1001)); // never consume the right hand
    assert(state.sample(1,true,1001));
    state.arm(1,false,1002); // obstruction ends hold, not ownership of this press
    assert(state.sample(1,true,1003));
    state.reset();
    assert(!state.sample(1,true,1004));
    state.arm(1,true,1005);
    assert(!state.sample(1,true,1006)); // reset cannot regrab a held button
    assert(!state.sample(1,false,1007));
    assert(state.sample(1,true,1008));
    state.arm(2,true,1009); // left role switches physical devices
    assert(!state.sample(1,true,1010));
    state.sample(2,false,1010);
    assert(state.sample(2,true,1011));
    assert(!state.read(2,1200).fresh);
    assert(!state.sample(2,true,1200)); // stale capture does not suppress input
    state.sample(2,false,1201);
    assert(!state.sample(2,true,1202)); // stale arm cannot claim a press
    assert(!state.sample(100,true,1202));
    assert(!state.read(100,1202).fresh);

    // Withdrawal by an earlier plugin must not turn a still-pressed physical
    // button into a fresh press when that plugin grants input again.
    state.sample(1,false,1300);state.arm(1,true,1301);
    assert(state.sample(1,true,1302));
    assert(!state.sample(1,true,1303,false,true));
    const auto withdrawn=state.read(1,1304);
    assert(withdrawn.fresh&&!withdrawn.down&&!withdrawn.captured);
    assert(withdrawn.pressed&&withdrawn.touched&&!withdrawn.accepted&&withdrawn.ageMs==1);
    assert(!state.sample(1,true,1305));
    assert(state.read(1,1305).serial==withdrawn.serial+1);
    state.sample(1,false,1306);
    assert(state.sample(1,true,1307));

    // Both legal orders of a simultaneous poll/reset must leave capture off.
    // The former independent atomic load/store could restore the old claim.
    std::barrier sync(3);
    constexpr unsigned iterations=10000;
    std::thread poller([&] {
        for(unsigned i=0;i<iterations;++i) {
            sync.arrive_and_wait();state.sample(1,true,2003);
            sync.arrive_and_wait();
        }
    });
    std::thread teardown([&] {
        for(unsigned i=0;i<iterations;++i) {
            sync.arrive_and_wait();state.reset();sync.arrive_and_wait();
        }
    });
    for(unsigned i=0;i<iterations;++i) {
        state.sample(1,false,2000);state.arm(1,true,2001);
        assert(state.sample(1,true,2002));
        sync.arrive_and_wait();sync.arrive_and_wait();
        assert(!state.read(1,2004).captured);
    }
    poller.join();teardown.join();
    std::cout<<"GRIP_CAPTURE_PASS teardown race, role changes, stale input, release/repress\n";
}
