#pragma once

namespace cms::skyrimvr {

// Adds one Chain Morningstar when Eorlund's chest base contains none.
// Existing positive stock is preserved. This does not reset a saved reference
// inventory or establish that the barter menu has already refreshed.
bool EnsureEorlundSellsChainMorningstar();

} // namespace cms::skyrimvr
