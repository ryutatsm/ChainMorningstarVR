#pragma once

#include "SkyrimVRSceneBridge.hpp"

namespace cms::skyrimvr {

class RuntimeService {
public:
    static RuntimeService& GetSingleton();
    void requestReacquire() noexcept {
        suspended_ = false;
        reacquireRequested_ = true;
        reacquireCooldownS_ = 0.0f;
    }
    void tick(float frameDt);
    void shutdown();

private:
    RuntimeService();
    SkyrimVRSceneBridge bridge_{};
    RuntimeDriver driver_;
    bool suspended_{true};
    bool wasPaused_{};
    bool reacquireRequested_{true};
    float reacquireCooldownS_{0.0f};
    static constexpr float kInactiveRetryIntervalS = 0.50f;
};

} // namespace cms::skyrimvr
