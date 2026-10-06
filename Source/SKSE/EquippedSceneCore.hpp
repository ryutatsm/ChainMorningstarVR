#pragma once
#include <string_view>

namespace cms {
template<class Node> struct EquippedChainGraph {
    Node* slot{};
    Node* model{};
    Node* anchor{};
};

// The caller proves which form is equipped and chooses the visible skeleton.
// Engines/mods can rename the model root to WEAPON/SHIELD. Its private anchor
// and direct parent are stable; its original exported root name is not.
template<class Node, class Find, class Parent>
EquippedChainGraph<Node> findEquippedChainGraph(Node* scene, bool inventoryLeft,
                                               Find find, Parent parent)
{
    EquippedChainGraph<Node> result;
    result.slot = find(scene, inventoryLeft ? "SHIELD" : "WEAPON");
    result.anchor = find(result.slot, "CMS_ChainAnchor");
    if (!result.anchor) return result;
    result.model = parent(result.anchor);
    // Require a direct model parent; the caller also checks all 14 links and head.
    if (!result.model || find(result.model, "CMS_ChainAnchor") != result.anchor) {
        result.model = nullptr;
        result.anchor = nullptr;
    }
    return result;
}
} // namespace cms
