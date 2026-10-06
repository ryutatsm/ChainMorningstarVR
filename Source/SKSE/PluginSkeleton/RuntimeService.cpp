#include "RuntimeService.hpp"
#include <algorithm>
#include <cmath>
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {

RuntimeService::RuntimeService() : driver_(bridge_) {}
// Retained engine NiPointers must not destruct after the engine heap shuts down.
RuntimeService& RuntimeService::GetSingleton() { static auto* s = new RuntimeService; return *s; }

void RuntimeService::tick(float frameDt)
{
    if (suspended_ || !std::isfinite(frameDt)) return;
    auto* ui = RE::UI::GetSingleton();
    if (!ui || ui->GameIsPaused()) {
        if (!wasPaused_) driver_.onUnequip();
        wasPaused_ = true;
        return;
    }
    if (frameDt <= 0.0f) return;
    // Controller poses may change while menus suspend the game. Start from the
    // resumed pose rather than turning that discontinuity into chain velocity.
    if (wasPaused_) {
        wasPaused_ = false;
        requestReacquire();
    }
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
    suspended_ = true;
    wasPaused_ = false;
    reacquireRequested_ = false;
    reacquireCooldownS_ = 0.0f;
    // Also clears a partially acquired graph if a previous acquisition failed.
    driver_.onUnequip();
}

} // namespace cms::skyrimvr
