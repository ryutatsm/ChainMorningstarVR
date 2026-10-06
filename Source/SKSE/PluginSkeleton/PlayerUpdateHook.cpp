#include "PlayerUpdateHook.hpp"
#include "RuntimeService.hpp"
#include "NativePhysicsBackend.hpp"
#include "VRFrameContext.hpp"
#include "../../ThirdParty/HIGGS/HiggsInterface001.hpp"
#include <SKSE/SKSE.h>
#include <algorithm>
#include <cmath>

namespace cms::skyrimvr {
namespace {
void BeforeHiggsUpdate() {
    NativePhysicsBackend::GetSingleton().BeginHiggsSelectionQueries();
}
void AfterHiggsUpdate() {
    NativePhysicsBackend::GetSingleton().EndHiggsSelectionQueries();
}
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
    // Pinned HIGGS hooks.cpp PlayerCharacterUpdateHook brackets Update with
    // these callbacks even when Update returns early (e.g. menus).
    api.AddPreVrikPreHiggsCallback(BeforeHiggsUpdate);
    api.AddPreVrikPostHiggsCallback(AfterHiggsUpdate);
    // HIGGS hooks.cpp PostVRIKPCUpdateHook updates the skeleton and both
    // hands before invoking this callback. No competing vtable patch.
    api.AddPostVrikPostHiggsCallback(AfterTrackedHandsUpdate);
    registered = true;
    SKSE::log::info("CMS frame callback registered: post-VRIK/post-HIGGS");
    SKSE::log::info("CMS offhand selection guard registered: HIGGS-update-only CustomPick2 exclusion; no settings changed");
}
} // namespace cms::skyrimvr
