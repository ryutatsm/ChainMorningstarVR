#pragma once
#include <array>
#include <cstdint>
#include <mutex>

namespace cms {
struct GripInput { bool fresh{}, down{}, captured{}; };

// Controller polling and game-thread teardown share ONE lock. Independent
// atomic load/store pairs can resurrect a claim after reset has cleared it.
// This lock protects scalar input only; no engine/API call runs under it.
class GripCaptureState {
public:
    static constexpr std::uint32_t invalidDevice=64;
    bool sample(std::uint32_t device,bool down,std::uint64_t now) {
        std::lock_guard lock(mutex_);
        if (device>=samples_.size()) return false;
        auto& value=samples_[device];
        const bool armed=device==armedDevice_&&fresh(armedAt_,now);
        const bool claimed=down&&((fresh(value.at,now)&&value.captured)||
                                  (armed&&!value.down));
        value={now,down,claimed};
        return claimed;
    }
    GripInput read(std::uint32_t device,std::uint64_t now) const {
        std::lock_guard lock(mutex_);
        if (device>=samples_.size()) return {};
        const auto& value=samples_[device];
        return {fresh(value.at,now),value.down,value.captured};
    }
    void arm(std::uint32_t device,bool enabled,std::uint64_t now) {
        std::lock_guard lock(mutex_);
        if (device!=leftDevice_) {
            // A device-role change must not consume the new right hand's grip.
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
        // Preserve down: a held button needs a release before a new capture.
    }
private:
    struct Sample { std::uint64_t at{}; bool down{},captured{}; };
    static bool fresh(std::uint64_t at,std::uint64_t now) {
        return at!=0&&now>=at&&now-at<150;
    }
    void clearClaims() { for(auto& value:samples_) value.captured=false; }
    mutable std::mutex mutex_;
    std::array<Sample,64> samples_{};
    std::uint32_t leftDevice_{invalidDevice},armedDevice_{invalidDevice};
    std::uint64_t armedAt_{};
};
} // namespace cms
