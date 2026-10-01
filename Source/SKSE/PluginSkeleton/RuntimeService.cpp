#include "RuntimeService.hpp"
#include <SKSE/SKSE.h>

namespace cms::skyrimvr {

RuntimeService::RuntimeService() : driver_(bridge_) {}
RuntimeService& RuntimeService::GetSingleton() { static RuntimeService s; return s; }

void RuntimeService::tick(float frameDt)
{
    if (reacquireRequested_ || !driver_.active()) {
        reacquireRequested_=false;
        if (driver_.active()) driver_.onUnequip();
        driver_.onEquip();
    }
    if (driver_.active()) driver_.update(frameDt);
}

void RuntimeService::shutdown()
{
    if (driver_.active()) driver_.onUnequip();
}

} // namespace cms::skyrimvr
