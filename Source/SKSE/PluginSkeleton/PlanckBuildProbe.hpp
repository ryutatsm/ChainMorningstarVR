#pragma once

#include <cstdint>
#include <optional>

namespace cms::skyrimvr {

std::optional<std::uint32_t> ProbePlanckBuildNumber();
std::optional<std::uint32_t> GetDetectedPlanckBuildNumber() noexcept;

// Native melee proxy is intentionally restricted to the exact PLANCK build
// observed and diagnosed on the target test machine until broader validation exists.
inline constexpr std::uint32_t kValidatedNativeProxyPlanckBuild = 80100;

} // namespace cms::skyrimvr
