#pragma once
#include <array>
#include <cstdint>
#include <mutex>

namespace cms {
struct GripInput {
    bool fresh{}, down{}, captured{};
    bool pressed{}, touched{}, accepted{};
    std::uint64_t ageMs{}, serial{};
    // Exact received bits, before CMS masks its selected grab button.
    std::uint64_t receivedPressed{}, receivedTouched{};
    std::uint32_t packet{};
    bool suppress{};
};

// Controller polling and game-thread teardown share ONE lock. Independent
// atomic load/store pairs can resurrect a claim after reset has cleared it.
// This lock protects scalar input only; no engine/API call runs under it.
class GripCaptureState {
public:
    static constexpr std::uint32_t invalidDevice=64;
    bool sample(std::uint32_t device,bool pressed,std::uint64_t now,
                bool accepted=true,bool touched=false,
                std::uint64_t receivedPressed=0,std::uint64_t receivedTouched=0,
                std::uint32_t packet=0) {
        std::lock_guard lock(mutex_);
        if (device>=samples_.size()) return false;
        auto& value=samples_[device];
        const bool down=accepted&&pressed;
        const bool armed=device==armedDevice_&&fresh(armedAt_,now);
        const bool previouslyCaptured=fresh(value.at,now)&&value.captured;
        const bool claimed=down&&(previouslyCaptured||
                                  (armed&&!value.pressed));
        value={now,value.serial+1,receivedPressed,receivedTouched,packet,
            down,claimed,pressed,touched,accepted,previouslyCaptured||claimed};
        return claimed;
    }
    GripInput read(std::uint32_t device,std::uint64_t now) const {
        std::lock_guard lock(mutex_);
        if (device>=samples_.size()) return {};
        const auto& value=samples_[device];
        return {fresh(value.at,now),value.down,value.captured,
            value.pressed,value.touched,value.accepted,
            now>=value.at?now-value.at:0,value.serial,
            value.receivedPressed,value.receivedTouched,value.packet,value.suppress};
    }
    void arm(std::uint32_t device,bool enabled,std::uint64_t now) {
        std::lock_guard lock(mutex_);
        if (device!=leftDevice_) {
            // A device-role change must not consume the new right hand's button.
            clearClaims();
            leftDevice_=device;
        }
        armedDevice_=enabled&&device<samples_.size()?device:invalidDevice;
        armedAt_=now;
    }
    void reset() {
        std::lock_guard lock(mutex_);
        armedDevice_=invalidDevice;
        clearClaims();
        // Preserve raw pressed: a held button needs a physical release before
        // a new capture, even if another callback withdrew accepted input.
    }
private:
    struct Sample {
        std::uint64_t at{},serial{},receivedPressed{},receivedTouched{};
        std::uint32_t packet{};
        bool down{},captured{},pressed{},touched{},accepted{},suppress{};
    };
    static bool fresh(std::uint64_t at,std::uint64_t now) {
        return at!=0&&now>=at&&now-at<150;
    }
    void clearClaims() { for(auto& value:samples_) {value.captured=false;value.suppress=false;} }
    mutable std::mutex mutex_;
    std::array<Sample,64> samples_{};
    std::uint32_t leftDevice_{invalidDevice},armedDevice_{invalidDevice};
    std::uint64_t armedAt_{};
};
} // namespace cms
