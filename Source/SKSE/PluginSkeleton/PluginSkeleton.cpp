#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>

#include "RuntimeService.hpp"
#include "PlayerUpdateHook.hpp"
#include "PlanckBuildProbe.hpp"

namespace {

void onSKSEMessage(SKSE::MessagingInterface::Message* msg)
{
    if (!msg) return;
    auto& runtime=cms::skyrimvr::RuntimeService::GetSingleton();
    switch (msg->type) {
    case SKSE::MessagingInterface::kPostPostLoad:
        cms::skyrimvr::ProbePlanckBuildNumber();
        break;
    case SKSE::MessagingInterface::kDataLoaded:
    case SKSE::MessagingInterface::kPostLoadGame:
    case SKSE::MessagingInterface::kNewGame:
        runtime.requestReacquire();
        break;
    default:
        break;
    }
}

} // namespace

SKSEPluginLoad(const SKSE::LoadInterface* skse)
{
    SKSE::Init(skse);
    if (!REL::Module::IsVR()) return false;
    auto* messaging=SKSE::GetMessagingInterface();
    if (!messaging) return false;
    SKSE::log::info("ChainMorningstarVR {} loading (VR-only, v0.4 scene bridge; native proxy fail-closed)", CMS_VERSION_STRING);
    if (!cms::skyrimvr::InstallPlayerUpdateHook()) return false;
    return messaging->RegisterListener(onSKSEMessage);
}
