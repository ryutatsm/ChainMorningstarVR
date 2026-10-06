#include "PlayerUpdateHook.hpp"
#include "RuntimeService.hpp"
#include "VRFrameContext.hpp"
#include "../../ThirdParty/HIGGS/HiggsInterface001.hpp"
#include <SKSE/SKSE.h>
#include <algorithm>
#include <cmath>

namespace cms::skyrimvr {
namespace {
void AfterTrackedHandsUpdate()
{
    static bool reported = false;
    if (!reported) {
        SKSE::log::info("CMS frame callback alive: post-VRIK/post-HIGGS");
        reported = true;
    }
    const float delta = VRFrameDelta();
    if (std::isfinite(delta))
        RuntimeService::GetSingleton().tick(std::clamp(delta, 0.0f, 0.100f));
}
}

void RegisterHiggsFrameUpdate(cms::higgs::IHiggsInterface001& api)
{
    static bool registered = false;
    if (registered) return;
    // HIGGS hooks.cpp PostVRIKPCUpdateHook updates the skeleton and both
    // hands before invoking this callback. No competing vtable patch.
    api.AddPostVrikPostHiggsCallback(AfterTrackedHandsUpdate);
    registered = true;
    SKSE::log::info("CMS frame callback registered: post-VRIK/post-HIGGS");
}
} // namespace cms::skyrimvr
