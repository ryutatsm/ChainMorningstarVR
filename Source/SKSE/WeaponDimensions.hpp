#pragma once

#include <cstddef>

namespace cms {
// Shared with Source/NIF/weapon_dimensions.py. Scale is baked into vertices,
// node offsets and Havok hulls exactly once; VRIK's live scale is independent.
inline constexpr float kModelScale = 0.75f;
inline constexpr std::size_t kChainLinkCount = 19;
inline constexpr float kUnscaledFirstLinkOffsetM = 0.035f;
inline constexpr float kUnscaledLinkSpacingM = 0.06461538461538462f; // original .840 / 13
inline constexpr float kUnscaledLastLinkHeadOffsetM = 0.190f;
inline constexpr float kFirstLinkOffsetM = kUnscaledFirstLinkOffsetM * kModelScale;
inline constexpr float kLinkSpacingM = kUnscaledLinkSpacingM * kModelScale;
inline constexpr float kChainCenterSpanM = (kChainLinkCount - 1) * kLinkSpacingM;
inline constexpr float kLastLinkHeadOffsetM = kUnscaledLastLinkHeadOffsetM * kModelScale;
inline constexpr float kStraightReachM = kFirstLinkOffsetM + kChainCenterSpanM + kLastLinkHeadOffsetM;
} // namespace cms
