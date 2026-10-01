#include "PlanckBuildProbe.hpp"

#include <SKSE/SKSE.h>
#include <memory>

namespace cms::skyrimvr {
namespace {

struct PlanckApiRequest {
    static constexpr std::uint32_t kMessageGetInterface = 0x92F38745;
    void* (*getApiFunction)(unsigned int revisionNumber) = nullptr;
};

struct PlanckBuildNumberOnly {
    virtual unsigned int GetBuildNumber() = 0;
};

} // namespace

std::optional<std::uint32_t> ProbePlanckBuildNumber()
{
    const auto* messaging = SKSE::GetMessagingInterface();
    if (!messaging) {
        SKSE::log::warn("ChainMorningstarVR: PLANCK probe skipped: SKSE messaging interface unavailable");
        return std::nullopt;
    }

    PlanckApiRequest request{};
    const bool dispatched = messaging->Dispatch(
        PlanckApiRequest::kMessageGetInterface,
        std::addressof(request),
        static_cast<std::uint32_t>(sizeof(PlanckApiRequest*)),
        "PLANCK");

    if (!dispatched || !request.getApiFunction) {
        SKSE::log::info("ChainMorningstarVR: PLANCK API revision 1 not available");
        return std::nullopt;
    }

    auto* api = static_cast<PlanckBuildNumberOnly*>(request.getApiFunction(1));
    if (!api) {
        SKSE::log::warn("ChainMorningstarVR: PLANCK replied but API revision 1 pointer was null");
        return std::nullopt;
    }

    const std::uint32_t build = api->GetBuildNumber();
    SKSE::log::info("ChainMorningstarVR: PLANCK API revision 1 detected; build={}", build);
    return build;
}

} // namespace cms::skyrimvr
