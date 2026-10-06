#pragma once

namespace cms::skyrimvr {

// Adds exactly one Chain Morningstar to Eorlund Gray-Mane's merchant chest base
// in memory. Safe to call repeatedly: an existing entry is left unchanged.
bool EnsureEorlundSellsChainMorningstar();

} // namespace cms::skyrimvr

// verification-only R6 marker
