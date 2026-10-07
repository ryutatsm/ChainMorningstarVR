#include "../Source/SKSE/ContactEpisodeCore.hpp"

#include <cassert>
#include <limits>

using cms::ContactEpisodeTracker;
using cms::EquipmentContactPart;

int main()
{
    constexpr auto head = EquipmentContactPart::kHead;
    constexpr auto weapon = EquipmentContactPart::kRightHand;
    ContactEpisodeTracker episodes;
    assert(episodes.contact(0, 10, 100, head, 1.0));
    for (int i = 0; i < 1000; ++i) assert(!episodes.contact(0, 10, 100, head, 1.0 + i * 0.01));
    // A second collider of the same equipment part does not grant another roll.
    assert(!episodes.contact(0, 11, 100, head, 12.0));
    episodes.removed(0, 10, 12.1);
    assert(!episodes.contact(0, 10, 100, head, 12.2));
    episodes.removed(0, 10, 12.3);
    episodes.removed(0, 11, 12.3);
    // Brief manifold churn is still the previous impact.
    assert(!episodes.contact(0, 10, 100, head, 12.35));
    episodes.removed(0, 10, 12.36);
    assert(episodes.contact(0, 10, 100, head, 12.5));
    // Different target parts and source hands retain independent episodes.
    assert(episodes.contact(0, 20, 100, weapon, 12.5));
    assert(episodes.contact(1, 10, 100, head, 12.5));
    assert(episodes.contact(0, 30, 200, head, 12.5));
    assert(!episodes.mesh(0, 100, weapon, 1, 14.0)); // Actual body is still touching.
    episodes.removed(0, 20, 14.1);
    assert(!episodes.mesh(0, 100, weapon, 1, 14.3)); // Suppressed token was consumed.
    episodes.meshRemoved(0, 100, weapon, 1, 14.1);
    assert(episodes.mesh(0, 100, weapon, 2, 14.3));
    assert(!episodes.mesh(0, 100, weapon, 2, 20.0));
    // A long weapon overlap followed by direct hand contact is still ONE
    // strike, even long after the old 100 ms cooldown has expired.
    assert(!episodes.contact(0, 20, 100, weapon, 20.1));
    episodes.meshRemoved(0, 100, weapon, 1, 20.2); // Stale token cannot end it.
    episodes.removed(0, 20, 20.3);
    assert(!episodes.contact(0, 20, 100, weapon, 21.0));
    episodes.meshRemoved(0, 100, weapon, 2, 21.1);
    assert(!episodes.mesh(0, 100, weapon, 3, 21.5)); // Hand is still touching.
    episodes.removed(0, 20, 21.6);
    episodes.meshRemoved(0, 100, weapon, 3, 21.7);
    assert(!episodes.contact(0, 20, 100, weapon, 21.75)); // Too brief separation.
    episodes.removed(0, 20, 21.76);
    assert(episodes.mesh(0, 100, weapon, 4, 22.0));
    assert(!episodes.contact(2, 1, 1, head, 1.0));
    assert(!episodes.contact(0, 0, 1, head, 1.0));
    assert(!episodes.contact(0, 1, 0, head, 1.0));
    assert(!episodes.contact(0, 1, 1, EquipmentContactPart::kUnknown, 1.0));
    assert(!episodes.contact(0, 1, 1, head, std::numeric_limits<double>::quiet_NaN()));
    assert(!episodes.mesh(0, 100, weapon, 0, 15.0));
    episodes.reset();
    assert(episodes.contact(0, 10, 100, head, 1.0));
    assert(episodes.mesh(0, 100, weapon, 1, 1.0));
}
