#pragma once
#include "GripCaptureCore.hpp"
#include <cstddef>

namespace cms {
// SKSEVR/OpenVR 1.0.12 controller ABI. Keep the actual button decoder in the
// portable path: testing only an abstract 'down' bool hid the wrong-button bug.
struct ControllerState {
    std::uint32_t packet{};
    std::uint64_t pressed{}, touched{};
    float axes[10]{};
};
static_assert(sizeof(ControllerState)==64 && offsetof(ControllerState,pressed)==8);
inline constexpr std::uint64_t kOffhandTriggerMask=1ull<<33; // SteamVR_Trigger
inline constexpr std::uint64_t kSideGripMask=1ull<<2;

class OffhandTriggerInput {
public:
    bool sample(std::uint32_t device,ControllerState& input,std::uint64_t now,
                bool accepted=true) {
        const bool claimed=capture_.sample(device,(input.pressed&kOffhandTriggerMask)!=0,
            now,accepted,(input.touched&kOffhandTriggerMask)!=0,
            input.pressed,input.touched,input.packet);
        filterFinal(device,input,now);
        return claimed;
    }
    void filterFinal(std::uint32_t device,ControllerState& input,std::uint64_t now) const {
        const auto value=capture_.read(device,now);
        // HIGGS can replay a delayed trigger after our priority-65 callback.
        // Clear only our owned trigger, including its release sample. Never
        // overwrite the callback acceptance flag, grip, axes, or other buttons.
        if(value.fresh&&value.suppress&&value.packet==input.packet) {
            input.pressed&=~kOffhandTriggerMask;
            input.touched&=~kOffhandTriggerMask;
        }
    }
    GripInput read(std::uint32_t device,std::uint64_t now) const {return capture_.read(device,now);}
    void arm(std::uint32_t device,bool enabled,std::uint64_t now) {capture_.arm(device,enabled,now);}
    void reset() {capture_.reset();}
private:
    GripCaptureState capture_;
};
} // namespace cms
