#include "RuntimeService.hpp"
#include <algorithm>
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {

RuntimeService::RuntimeService() : driver_(bridge_) {}
RuntimeService& RuntimeService::GetSingleton() { static RuntimeService s; return s; }

void RuntimeService::tick(float frameDt)
{
    frameDt = std::clamp(frameDt, 0.0f, 0.100f);
    reacquireCooldownS_ = std::max(0.0f, reacquireCooldownS_ - frameDt);

    const bool shouldTryNow =
        reacquireRequested_ ||
        (!driver_.active() && reacquireCooldownS_ <= 0.0f);

    if (shouldTryNow) {
        reacquireRequested_ = false;
        if (driver_.active()) {
            driver_.onUnequip();
        }
        driver_.onEquip();

        // When another weapon is equipped, CMS_ChainAnchor is absent by design.
        // Avoid traversing both VR hand scene graphs every frame; explicit SKSE load/new-game
        // messages still force an immediate retry.
        if (!driver_.active()) {
            reacquireCooldownS_ = kInactiveRetryIntervalS;
        }
    }

    if (driver_.active()) {
        driver_.update(frameDt);
    }
}

void RuntimeService::shutdown()
{
    if (driver_.active()) driver_.onUnequip();
}

} // namespace cms::skyrimvr
