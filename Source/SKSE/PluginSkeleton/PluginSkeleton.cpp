#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <spdlog/sinks/basic_file_sink.h>

#include "RuntimeService.hpp"
#include "PlayerUpdateHook.hpp"
#include "PlanckBuildProbe.hpp"

namespace {

bool setupFileLogger()
{
    auto logsFolder = SKSE::log::log_directory();
    if (!logsFolder) {
        return false;
    }

    const auto logPath = *logsFolder / "ChainMorningstarVR.log";
    auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(logPath.string(), true);
    auto logger = std::make_shared<spdlog::logger>("ChainMorningstarVR", std::move(sink));
    spdlog::set_default_logger(std::move(logger));
    spdlog::set_level(spdlog::level::trace);
    spdlog::flush_on(spdlog::level::info);
    return true;
}

void onSKSEMessage(SKSE::MessagingInterface::Message* msg)
{
    if (!msg) return;
    auto& runtime = cms::skyrimvr::RuntimeService::GetSingleton();
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

    if (!setupFileLogger()) {
        return false;
    }

    if (!REL::Module::IsVR()) {
        SKSE::log::critical("Refusing to load: Skyrim VR runtime was not detected.");
        return false;
    }

    auto* messaging = SKSE::GetMessagingInterface();
    if (!messaging) {
        SKSE::log::critical("Refusing to load: SKSE messaging interface is unavailable.");
        return false;
    }

#if CMS_ENABLE_READONLY_VRMELEE_PROBE
    constexpr auto probeMode = "ON (read-only; no VRMeleeData writes)";
#else
    constexpr auto probeMode = "OFF";
#endif

    SKSE::log::info(
        "ChainMorningstarVR {} loading (VR-only; native melee proxy fail-closed; VRMeleeData probe={})",
        CMS_VERSION_STRING,
        probeMode);

    if (!cms::skyrimvr::InstallPlayerUpdateHook()) {
        SKSE::log::critical("PlayerCharacter VR Update hook installation failed.");
        return false;
    }

    const bool registered = messaging->RegisterListener(onSKSEMessage);
    SKSE::log::info("SKSE message listener registration: {}", registered ? "OK" : "FAILED");
    return registered;
}
