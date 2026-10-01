#pragma once

#include "SkyrimVRSceneBridge.hpp"

namespace cms::skyrimvr {

class RuntimeService {
public:
    static RuntimeService& GetSingleton();
    void requestReacquire() noexcept { reacquireRequested_=true; }
    void tick(float frameDt);
    void shutdown();

private:
    RuntimeService();
    SkyrimVRSceneBridge bridge_{};
    RuntimeDriver driver_;
    bool reacquireRequested_{true};
};

} // namespace cms::skyrimvr
